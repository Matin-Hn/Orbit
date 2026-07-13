from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from redis.asyncio import Redis

from app.api.deps import get_db
from app.schemas.video import VideoDetailResponse
from app.models.user import User
from app.services.auth_service import get_optional_current_user_from_cookie
from app.services.video_service import get_video_by_public_id
from app.services.video_stats_counter import VideoStatsCounter
from app.crud.reaction import reaction as reaction_crud
from app.core.redis import get_redis

router = APIRouter(prefix="/videos")

@router.get("/{public_id}", response_model=VideoDetailResponse)
async def get_video(
    public_id: str,
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: Optional[User] = Depends(get_optional_current_user_from_cookie),
):
    """
    Get complete video details including HLS manifest URL, thumbnail, etc.
    """

    video = await get_video_by_public_id(db, public_id, current_user.id if current_user else None)

    # `video.channel` is a lazily-loaded relationship. Accessing it directly
    # here (after the await above has returned) triggers a synchronous
    # lazy-load on what is actually an AsyncSession, which raises
    # sqlalchemy.exc.MissingGreenlet ("greenlet_spawn has not been called").
    # Explicitly awaiting db.refresh(..., attribute_names=["channel"]) loads
    # the relationship safely within an async context before we touch it.
    if "channel" not in video.__dict__:
        await db.refresh(video, attribute_names=["channel"])
    if "stats" not in video.__dict__:
        await db.refresh(video, attribute_names=["stats"])

    current_user_reaction = None
    if current_user:
        user_reaction = await reaction_crud.get_by_video_and_user(db=db, user_id=current_user.id, video_id=video.id)
        if user_reaction:
            current_user_reaction = user_reaction.type.value

    like_count = await VideoStatsCounter(redis=redis, db=db).likes.get(video.id)

    # Return all fields required by VideoDetailResponse
    return VideoDetailResponse(   
        id=video.id,
        status=video.status,
        title=video.title,
        description=video.description,
        channel_name=video.channel.name,
        duration_seconds=video.duration_seconds,
        thumbnail_url=video.thumbnail_url,
        hls_manifest_url=video.hls_manifest_url,
        sprite_url=video.sprite_url,
        sprite_vtt_url=video.sprite_vtt_url,
        sprite_tile_width=video.sprite_tile_width,
        sprite_tile_height=video.sprite_tile_height,
        sprite_columns=video.sprite_columns,
        sprite_rows=video.sprite_rows,
        created_at=video.created_at,
        channel_id=video.channel_id,
        file_url=video.file_url,
        like_count=like_count,
        comment_count=video.stats.comments_count if video.stats else 0,
        view_count=video.stats.views_count if video.stats else 0,
        current_user_reaction=current_user_reaction,
        is_published=video.is_published,
        can_edit=(current_user.id == video.channel.user_id if current_user else False),
        published_at=video.published_at,
        updated_at=video.updated_at,
    )