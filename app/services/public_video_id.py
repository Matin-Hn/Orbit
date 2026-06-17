from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.models.video_public_id import VideoPublicId
from app.utils.public_id import generate_candidate, _MAX_RETRIES


class PublicIdCollisionError(Exception):
    """Raised when a unique public_id cannot be generated after max retries."""
    pass


async def create_public_id(db: AsyncSession, internal_id: int) -> VideoPublicId:
    """
    Generate a unique public_id and persist it linked to the given internal_id.
    Must be called within an existing transaction (same session as video creation).
    """
    for attempt in range(1, _MAX_RETRIES + 1):
        candidate = generate_candidate()
        mapping = VideoPublicId(public_id=candidate, internal_id=internal_id)

        try:
            db.add(mapping)
            await db.flush()  # ← hit the DB to check uniqueness, but don't commit yet
            return mapping

        except IntegrityError:
            await db.rollback()  # ← roll back only the flush, not the whole transaction
            if attempt == _MAX_RETRIES:
                raise PublicIdCollisionError(
                    f"Could not generate a unique public_id after {_MAX_RETRIES} attempts."
                )

    # never reached, but satisfies type checkers
    raise PublicIdCollisionError("Unreachable.")