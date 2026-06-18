import logging
import asyncio

from fastapi import HTTPException
from sqlalchemy.exc import OperationalError, DatabaseError
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.core.celery_app import celery_app
from app.core.config import settings
from app.services.reactions_service import ReactionService

logger = logging.getLogger(__name__)


def _make_session() -> async_sessionmaker[AsyncSession]:
    """Create a fresh engine+session per task — avoids cross-loop pool contamination."""
    engine = create_async_engine(settings.SQLALCHEMY_DATABASE_URL, pool_size=1, max_overflow=0)
    return async_sessionmaker(engine, expire_on_commit=False)


@celery_app.task(bind=True, max_retries=2)
def upsert_video_reaction(self, requesting_user_id: int, reaction_type: str, video_id: int):
    asyncio.run(_upsert(self, requesting_user_id, reaction_type, video_id))


async def _upsert(task, requesting_user_id: int, reaction_type: str, video_id: int):
    async with _make_session()() as db:
        try:
            await ReactionService(db).set_reaction(requesting_user_id, reaction_type, video_id)
            await db.commit()
            logger.info("Reaction record wrote successfully")
        except Exception as e:
            await db.rollback()
            logger.error(f"Reaction writing failed: {e}")
            raise task.retry(exc=e, countdown=60)


@celery_app.task(bind=True, max_retries=2)
def delsert_video_reaction(self, reaction_type: str, requesting_user_id: int, video_id: int):
    asyncio.run(_delsert(self, reaction_type, requesting_user_id, video_id))


async def _delsert(task, reaction_type: str, requesting_user_id: int, video_id: int):
    async with _make_session()() as db:
        try:
            await ReactionService(db).delete_reaction(reaction_type, requesting_user_id, video_id)
            await db.commit()
            logger.info("Reaction record deleted successfully")
        except HTTPException as e:
            logger.warning(f"Reaction delete skipped (logical conflict): {e.detail}")
            return
        except (OperationalError, DatabaseError) as e:
            await db.rollback()
            logger.error(f"Transient DB error, retrying: {e}")
            raise task.retry(exc=e, countdown=60)
        except Exception as e:
            await db.rollback()
            logger.error(f"Unexpected error during reaction delete: {e}")
            raise task.retry(exc=e, countdown=60)