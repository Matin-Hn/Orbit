import logging

from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError, DatabaseError

from fastapi import HTTPException

from app.core.celery_app import celery_app
from app.services.reactions_service import ReactionService
from app.models.user import User
from app.schemas.reaction import ReactionCreate
from app.core.database import SessionLocal


logger = logging.getLogger(__name__)

@celery_app.task(bind=True, max_retries=2)
def upsert_video_reaction(
    self,
    requesting_user_id: int,
    reaction_type: str,
    video_id: int
):
    db: Session = SessionLocal()
    reaction_service = ReactionService(db)
    try:
        reaction_service.set_reaction(requesting_user_id, reaction_type, video_id)
        return logger.info(f"Reaction record wrote successfully")
    except Exception as e:
        logger.error(f"Reaction writing failed: {e}")
        raise self.retry(exc=e, countdown=60)


@celery_app.task(bind=True, max_retries=2)
def delsert_video_reaction(
    self,
    reaction_type: str,
    requesting_user_id: int,
    video_id: int
):
    db: Session = SessionLocal()
    reaction_service = ReactionService(db)
    try:
        reaction_service.delete_reaction(
            reaction_type,
            requesting_user_id,
            video_id
        )
        return logger.info(f"Reaction record deleted successfully")
    except HTTPException as e:
        # Permanent logical error — retrying won't help
        logger.warning(f"Reaction delete skipped (logical conflict): {e.detail}")
        return  # Acknowledge the task, don't retry

    except (OperationalError, DatabaseError) as e:
        # Transient DB error — worth retrying
        logger.error(f"Transient DB error, retrying: {e}")
        raise self.retry(exc=e, countdown=60)

    except Exception as e:
        # Unexpected — log and retry cautiously
        logger.error(f"Unexpected error during reaction delete: {e}")
        raise self.retry(exc=e, countdown=60)

    finally:
        db.close()