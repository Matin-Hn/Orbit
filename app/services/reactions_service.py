from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ReactionNotFound, ReactionTypeMismatch
from app.models.video_reaction import ReactionType
from app.models.video_stats import VideoStats
from app.schemas.reaction import ReactionCreate, ReactionUpdate
from app.crud.reaction import reaction as reaction_crud


class ReactionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _increment_dislike_count(self, video_id: int, delta: int):
        await self.db.execute(
            pg_insert(VideoStats)
            .values(video_id=video_id, dislikes_count=delta)
            .on_conflict_do_update(
                index_elements=["video_id"],
                set_={"dislikes_count": VideoStats.dislikes_count + delta}
            )
        )

    async def _get_existing_reaction(self, user_id: int, video_id: int):
        return await reaction_crud.get_by_video_and_user(
            db=self.db, user_id=user_id, video_id=video_id
        )

    async def set_reaction(self, requesting_user_id: int, reaction_type: str, video_id: int):
        existing_db_reaction = await self._get_existing_reaction(requesting_user_id, video_id)

        if not existing_db_reaction:
            obj_in = ReactionCreate(type=reaction_type, video_id=video_id)
            await reaction_crud.create(self.db, obj_in, requesting_user_id)
            if reaction_type == "dislike":
                await self._increment_dislike_count(video_id, 1)
            return {"status": "created", "type": reaction_type}

        elif existing_db_reaction.type == reaction_type:
            return {"status": "unchanged", "type": reaction_type}

        else:
            if existing_db_reaction.type == "dislike":
                await self._increment_dislike_count(video_id, -1)
            if reaction_type == "dislike":
                await self._increment_dislike_count(video_id, 1)

            obj_in = ReactionUpdate(type=reaction_type)
            await reaction_crud.update(self.db, existing_db_reaction, obj_in)
            return {"status": "changed", "type": reaction_type}

    async def delete_reaction(
            self, reaction_type: str, requesting_user_id: int, video_id: int
    ):
        existing = await self._get_existing_reaction(requesting_user_id, video_id)
        if not existing:
            raise ReactionNotFound(f"No reaction for user={requesting_user_id} video={video_id}")
        elif existing.type != reaction_type:
            raise ReactionTypeMismatch(f"Expected {reaction_type}, found {existing.type}")

        if reaction_type == "dislike":
            await self._increment_dislike_count(video_id, -1)

        await reaction_crud.delete(self.db, existing)
        return {"message": "reaction deleted"}

    async def delete_reaction(  # ← was missing async
            self, reaction_type: str, requesting_user_id: int, video_id: int
    ):
        existing = await reaction_crud.get_by_video_and_user(  # ← was missing await
            db=self.db, user_id=requesting_user_id, video_id=video_id
        )
        if not existing:
            raise ReactionNotFound(f"No reaction for user={requesting_user_id} video={video_id}")
        elif existing.type != reaction_type:
            raise ReactionTypeMismatch(f"Expected {reaction_type}, found {existing.type}")
        await reaction_crud.delete(self.db, existing)  # ← was missing await
        return {"message": "reaction deleted"}