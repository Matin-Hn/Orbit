from typing import Optional
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.video_stats import VideoStats
from app.models.video_reaction import VideoReaction, ReactionType


# Like keys
LIKES_KEY = "video:{video_id}:likes"
LIKED_KEY = "video:{video_id}:user:{user_id}:liked"
LIKE_COUNTER_TTL = 60 * 60 * 24 * 7              # 7 days — refresh on access
LIKED_KEY_TTL = 60 * 60 * 24 * 90           # 90 days

# Views keys
VISITED_KEY = "video:{video_id}:user:{user_id}:visited"
VIEWS_KEY = "video:{video_id}:views"
VIEW_DEDUP_TTL = 60 * 60 * 12  # 12h: same user/video view won't double-count
VIEWS_COUNTER_TTL = 60 * 5


# Like key formatters
def _liked_key(video_id: int, user_id: int) -> str:
    return LIKED_KEY.format(video_id=video_id, user_id=user_id)

def _likes_key(video_id: int) -> str:
    return LIKES_KEY.format(video_id=video_id)

# View key formatters
def _views_key(video_id: int) -> str:
    return VIEWS_KEY.format(video_id=video_id)

def _visited_key(video_id: int, user_id: int) -> str:
    return VISITED_KEY.format(video_id=video_id, user_id=user_id)


class LikeCounter:
    def __init__(self, redis: Redis, db: AsyncSession):
        self.redis = redis
        self.db = db

    async def _seed_from_db(self, video_id: int) -> int:
        """Cold-start: count from Postgres and seed Redis."""
        result = await self.db.execute(
            select(func.count(VideoReaction.id)).where(
                VideoReaction.video_id == video_id,
                VideoReaction.type == ReactionType.LIKE,
            )
        )
        count = result.scalar_one_or_none() or 0

        key = _likes_key(video_id)
        # SET only if key doesn't exist — avoids race with another request
        await self.redis.set(key, count, ex=LIKE_COUNTER_TTL, nx=True)

        # Re-read to handle the race: another request may have won the SET
        current = await self.redis.get(key)
        return int(current) if current is not None else count



    async def increment(self, video_id: int, user_id: int) -> int:
        liked_key = _liked_key(video_id, user_id)
        already_liked = not await self.redis.set(liked_key, 1, ex=LIKED_KEY_TTL, nx=True)
        if already_liked:
            return await self.get(video_id)

        key = _likes_key(video_id)
        # Ensure key exists before atomic INCR
        await self._seed_from_db(video_id)

        new_count = await self.redis.incr(key)
        await self.redis.expire(key, LIKE_COUNTER_TTL)
        return new_count

    async def decrement(self, video_id: int, user_id: int) -> Optional[int]:
        liked_key = _liked_key(video_id, user_id)

        # Atomic GET+DELETE — avoids TOCTOU between two separate calls
        existed = await self.redis.getdel(liked_key)
        if not existed:
            return None  # user never liked — no decrement

        key = _likes_key(video_id)
        new_count = await self.redis.decr(key)
        if new_count < 0:
            # Counter was missing or corrupt — clamp and reset TTL
            await self.redis.set(key, 0, ex=LIKE_COUNTER_TTL)
            return 0
        await self.redis.expire(key, LIKE_COUNTER_TTL)
        return new_count

    async def get(self, video_id: int) -> int:
        """Read current count — with cold-start fallback."""
        key = _likes_key(video_id)
        value = await self.redis.get(key)
        if value is None:
            return await self._seed_from_db(video_id)
        return int(value)


class ViewCounter:
    """
    Dedup + hot counter for views.
    - SETNX dedup key (per user+video) with TTL
    - On new view: INCR redis hot counter + push event to flush queue
    - Returns db_count + redis_delta
    """

    HOT_KEY_PREFIX = "views:hot"          # views:hot:{video_id}
    DEDUP_KEY_PREFIX = "views:dedup"      # views:dedup:{video_id}:{user_id}
    PENDING_SET_KEY = "views:pending"     # set of video_ids with unflushed deltas

    def __init__(self, redis: Redis, db: AsyncSession):
        self.redis = redis
        self.db = db

    def _hot_key(self, video_id: int) -> str:
        return f"{self.HOT_KEY_PREFIX}:{video_id}"

    def _dedup_key(self, video_id: int, user_id: int) -> str:
        return f"{self.DEDUP_KEY_PREFIX}:{video_id}:{user_id}"

    async def increment(self, video_id: int, user_id: int) -> int:
        """
        Dedup-checked view increment.
        Returns combined count = db_count + redis_delta.
        """
        dedup_key = self._dedup_key(video_id, user_id)

        # SETNX with TTL — atomic "first view in window" check
        is_new = await self.redis.set(dedup_key, "1", nx=True, ex=VIEW_DEDUP_TTL)

        if is_new:
            async with self.redis.pipeline(transaction=True) as pipe:
                await pipe.incr(self._hot_key(video_id))
                await pipe.sadd(self.PENDING_SET_KEY, video_id)
                await pipe.execute()

            # results[0] is the new hot counter value, but we still need
            # db_count to return the combined total
        # else: not a new view, just return current combined count

        return await self.get(video_id)

    async def get(self, video_id: int) -> int:
        """
        Combined count = persisted db_count + unflushed redis_delta.
        """
        redis_delta_raw = await self.redis.get(self._hot_key(video_id))
        redis_delta = int(redis_delta_raw) if redis_delta_raw else 0

        result = await self.db.execute(
            select(VideoStats.views_count).where(VideoStats.video_id == video_id)
        )
        db_count = result.scalar_one_or_none() or 0

        return db_count + redis_delta