from fastapi import APIRouter, Depends, HTTPException

from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.video import VideoResponse
from app.models.user import User
from app.models.video import Video
from app.models.channel import Channel
from app.services.auth_service import get_current_user_from_cookie

router = APIRouter(prefix="/videos")

@router.get("/{video_id}", response_model=VideoResponse)
async def get_video(
    video_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie),
):
    """
    Get complete video details including HLS manifest URL, thumbnail, etc.
    """
    video = db.query(Video).filter(
        Video.id == video_id,
        Video.deleted_at.is_(None)
    ).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Check access permissions
    is_owner = video.channel.user_id == current_user.id
    if not is_owner and video.visibility != "public":
        raise HTTPException(status_code=403, detail="You do not have permission to view this video")
    
    channel = db.query(Channel).filter(Channel.id==video.channel_id).first()
    # Return all fields required by VideoResponse
    return VideoResponse(
        id=video.id,
        public_id=video.public_id,
        status=video.status,
        title=video.title,
        description=video.description,
        channel_name=channel.name,
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