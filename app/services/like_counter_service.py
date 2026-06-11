from typing import Optional
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.video_reaction import VideoReaction, ReactionType

LIKES_KEY = "video:{video_id}:likes"
COUNTER_TTL = 60 * 60 * 24 * 7              # 7 days — refresh on access
LIKED_KEY_TTL = 60 * 60 * 24 * 90           # 90 days
LIKED_KEY = "video:{video_id}:user:{user_id}:liked"

def _liked_key(video_id: int, user_id: int) -> str:
    return LIKED_KEY.format(video_id=video_id, user_id=user_id)

def _key(video_id: int) -> str:
    return LIKES_KEY.format(video_id=video_id)


class LikeCounter:
    def __init__(self, redis: Redis, db: AsyncSession):
        self.redis = redis
        self.db = db

    async def _seed_from_db(self, video_id: int) -> int:
        """Cold-start: count from Postgres and seed Redis."""
        count = self.db.scalar(
            select(func.count(VideoReaction.id)).where(
                VideoReaction.video_id == video_id,
                VideoReaction.type == ReactionType.LIKE,
            )
        ) or 0

        key = _key(video_id)
        # SET only if key doesn't exist — avoids race with another request
        await self.redis.set(key, count, ex=COUNTER_TTL, nx=True)

        # Re-read to handle the race: another request may have won the SET
        current = await self.redis.get(key)
        return int(current) if current is not None else count
    
    

    async def increment(self, video_id: int, user_id: int) -> int:
        liked_key = _liked_key(video_id, user_id)
        already_liked = not await self.redis.set(liked_key, 1, ex=LIKED_KEY_TTL, nx=True)
        if already_liked:
            return await self.get(video_id)

        key = _key(video_id)
        # Ensure key exists before atomic INCR
        await self._seed_from_db(video_id)  

        new_count = await self.redis.incr(key)
        await self.redis.expire(key, COUNTER_TTL)
        return new_count

    async def decrement(self, video_id: int, user_id: int) -> Optional[int]:
        liked_key = _liked_key(video_id, user_id)
        
        # Atomic GET+DELETE — avoids TOCTOU between two separate calls
        existed = await self.redis.getdel(liked_key)
        if not existed:
            return None  # user never liked — no decrement

        key = _key(video_id)
        new_count = await self.redis.decr(key)
        if new_count < 0:
            # Counter was missing or corrupt — clamp and reset TTL
            await self.redis.set(key, 0, ex=COUNTER_TTL)
            return 0
        await self.redis.expire(key, COUNTER_TTL)
        return new_count

    async def get(self, video_id: int) -> int:
        """Read current count — with cold-start fallback."""
        key = _key(video_id)
        value = await self.redis.get(key)
        if value is None:
            return await self._seed_from_db(video_id)
        return int(value)