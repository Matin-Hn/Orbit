from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.video_reaction import VideoReaction
from app.schemas.reaction import ReactionCreate, ReactionUpdate


class CRUDReaction:
    def __init__(self, model=VideoReaction):
        self.model = model

    async def create(self, db: AsyncSession, obj_in: ReactionCreate, user_id: int):
        db_obj = VideoReaction(
            user_id=user_id,
            type=obj_in.type,
            video_id=obj_in.video_id
        )
        db.add(db_obj)
        await db.flush()
        await db.refresh(db_obj)
        return db_obj

    async def get_by_video_and_user(self, db: AsyncSession, user_id: int, video_id: int) -> Optional[VideoReaction]:
        result = await db.execute(
            select(self.model).filter(
                self.model.user_id == user_id,
                self.model.video_id == video_id
            )
        )
        return result.scalar_one_or_none()

    async def update(
            self,
            db: AsyncSession,
            db_obj: VideoReaction,
            obj_in: ReactionUpdate
    ) -> VideoReaction:
        update_data = obj_in.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(db_obj, field, value)

        await db.flush()
        await db.refresh(db_obj)
        return db_obj

    async def delete(
            self,
            db: AsyncSession,
            db_obj: VideoReaction
    ):
        await db.delete(db_obj)
        await db.flush() 


reaction = CRUDReaction(VideoReaction)