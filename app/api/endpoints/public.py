from fastapi import APIRouter, Depends, HTTPException

from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.video import VideoResponse
from app.models.user import User
from app.models.video import Video
from app.models.channel import Channel
from app.services.auth_service import get_current_user_from_cookie
from app.services.video_service import get_video_by_public_id

router = APIRouter(prefix="/videos")

@router.get("/{public_id}", response_model=VideoResponse)
async def get_video(
    public_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie),
):
    """
    Get complete video details including HLS manifest URL, thumbnail, etc.
    """

    video = get_video_by_public_id(db, public_id, current_user)
    # Return all fields required by VideoResponse
    return VideoResponse(   
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
        published_at=video.published_at,
        updated_at=video.updated_at,
    )