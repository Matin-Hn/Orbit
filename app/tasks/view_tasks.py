import logging
import asyncio

from sqlalchemy import update
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.dialects.postgresql import insert as pg_insert
import redis.asyncio as aioredis

from app.core.celery_app import celery_app
from app.core.config import settings
from app.models.video_stats import VideoStats

logger = logging.getLogger(__name__)


def _make_redis() -> aioredis.Redis:
    """Fresh Redis client per task — avoids closed-loop connection reuse."""
    return aioredis.from_url(
        settings.CELERY_BROKER_URL,
        encoding="utf-8",
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )


def _make_session():
    engine = create_async_engine(settings.SQLALCHEMY_DATABASE_URL, pool_size=1, max_overflow=0)
    return async_sessionmaker(engine, expire_on_commit=False)


@celery_app.task(name="flush_view_counters")
def flush_view_counters():
    asyncio.run(_flush_view_counters_async())


async def _flush_view_counters_async():
    redis = _make_redis()
    SessionLocal = _make_session()

    try:
        video_ids = await redis.smembers("views:pending")
        if not video_ids:
            return

        for video_id_str in video_ids:
            video_id = int(video_id_str)
            hot_key = f"views:hot:{video_id}"

            delta_raw = await redis.getdel(hot_key)
            delta = int(delta_raw) if delta_raw else 0
            await redis.srem("views:pending", video_id_str)

            if delta == 0:
                continue

            async with SessionLocal() as db:
                try:
                    await db.execute(
                        pg_insert(VideoStats)
                        .values(video_id=video_id, views_count=delta)
                        .on_conflict_do_update(
                            index_elements=["video_id"],
                            set_={"views_count": VideoStats.views_count + delta}
                        )
                    )
                    await db.commit()
                    logger.info(f"Flushed {delta} views for video {video_id}")
                except Exception:
                    await db.rollback()
                    logger.error(
                        "Failed to flush view counter, restoring to redis",
                        extra={"video_id": video_id, "delta": delta},
                        exc_info=True,
                    )
                    async with redis.pipeline(transaction=True) as pipe:
                        pipe.incrby(hot_key, delta)
                        pipe.sadd("views:pending", video_id)
                        await pipe.execute()
    finally:
        await redis.aclose()