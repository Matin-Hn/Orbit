# app/crud/video.py
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.models.video import Video
from app.models.video_public_id import VideoPublicId

class CRUDVideo:
    def __init__(self, model=Video):
        self.model = model

    async def get(self, db: AsyncSession, id: int) -> Optional[Video]:
        result = await db.execute(
            select(Video)
            .options(selectinload(Video.channel))
            .where(Video.id == id)
        )
        return result.scalar_one_or_none()

    async def get_by_public_id(self, db: AsyncSession, public_id: str):
        result = await db.execute(
            select(Video)
            .join(VideoPublicId, VideoPublicId.internal_id == Video.id)
            .options(joinedload(Video.public_id), joinedload(Video.stats))
            .filter(VideoPublicId.public_id == public_id)
            .filter(Video.deleted_at.is_(None))  # soft-delete guard
        )
        return result.unique().scalar_one_or_none()

    async def get_published(self, db: AsyncSession, id: int) -> Optional[Video]:
        """Get published video by ID"""
        result = await db.execute(
            select(self.model).filter(
                self.model.id == id,
                self.model.deleted_at.is_(None),
                self.model.is_published == True
            )
        )
        return result.scalar_one_or_none()

    async def exists(self, db: AsyncSession, id: int) -> bool:
        """Check if video exists (simple existence check)"""
        result = await db.execute(
            select(self.model.id).filter(
                self.model.id == id,
                self.model.deleted_at.is_(None)
            )
        )
        return result.first() is not None

video = CRUDVideo(Video)