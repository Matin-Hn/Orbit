from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import func

from app.models.video_stats import VideoStats


class VideoStatsService:
    """
    Direct (non-Redis) stat mutations for low-frequency events.

    Comments are written infrequently enough that a direct DB UPDATE per
    operation is cheaper and simpler than batching through Redis.  The update
    runs inside the caller's existing session, so it commits atomically with
    the comment row itself — no eventual-consistency lag, no separate flush.

    Usage inside CommentService
    ---------------------------
        self._stats = VideoStatsService(db)

        # on create:
        await self._stats.increment_comments(video_id)

        # on soft-delete:
        await self._stats.decrement_comments(video_id)
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def increment_comments(self, video_id: int) -> None:
        await self._apply_comments_delta(video_id, +1)

    async def decrement_comments(self, video_id: int) -> None:
        await self._apply_comments_delta(video_id, -1)

    async def _apply_comments_delta(self, video_id: int, delta: int) -> None:
        """
        UPSERT so the first comment on a new video creates the stats row.
        GREATEST(0, ...) guards against the count going negative if a delete
        races ahead of the matching create (shouldn't happen, but safe is safe).
        """
        await self._db.execute(
            pg_insert(VideoStats)
            .values(video_id=video_id, comments_count=max(0, delta))
            .on_conflict_do_update(
                index_elements=["video_id"],
                set_={
                    "comments_count": func.greatest(
                        0, VideoStats.comments_count + delta
                    )
                },
            )
        )
        # No commit here — caller's transaction owns the commit boundary,
        # so comment row + stats update land in the same atomic write.