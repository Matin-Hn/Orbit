from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
import uuid

from app.services.auth_service import get_current_user_from_cookie, get_current_channel
from app.api.deps import get_db
from app.models.video import Video
from app.models.channel import Channel
from app.models.user import User                     # adjust
from app.schemas.video import (
    UploadUrlResponse,
    VideoCompleteRequest,
    VideoCompleteResponse,
    VideoResponse
)
from app.services.storage import storage_service
from app.core.config import settings
from app.tasks.video_tasks import transcode_video_task


router = APIRouter(prefix="/videos", tags=["video operations"])

# Helper: generate a unique S3 key for the video
def generate_video_key(original_filename: str) -> str:
    """Generate a unique S3 key for the original uploaded video."""
    ext = original_filename.split('.')[-1] if '.' in original_filename else 'mp4'
    unique_id = uuid.uuid4().hex
    return f"originals/{unique_id}.{ext}"


@router.get(
    "/upload-url",
    response_model=UploadUrlResponse,
    status_code=status.HTTP_201_CREATED
)
async def request_video_upload(
    filename: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie),
    current_channel: Channel = Depends(get_current_channel)
):
    """
    Step 1: Create video record and return a pre‑signed POST URL.
    The client will upload directly to S3 using this URL.
    """

    # 1. Verify the user owns the channel
    channel = db.query(Channel).filter(
        Channel.id == current_channel.id,
        Channel.user_id == current_user.id,
        Channel.is_suspended == False
    ).first()
    if not channel:
        raise HTTPException(
            status_code=403,
            detail="Channel not found or you do not own it"
        )

    object_key = generate_video_key(filename)

    # 4. Generate pre‑signed POST for the final key
    try:
        presigned_url = await storage_service.generate_presigned_put_url(
            object_key=object_key,
            expiration= 3600,
            content_type= "video/mp4"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not create upload URL: {str(e)}")

    return UploadUrlResponse(
        upload_url=presigned_url,
        object_key=object_key,
        expires_in=3600
    )

@router.get("/thumbnail-upload-url", response_model=UploadUrlResponse)
async def get_thumbnail_upload_url(
    filename: str = "thumbnail.jpg",
    db: Session = Depends(get_db),
    content_type: str = "image/jpeg",
    current_user: User = Depends(get_current_user_from_cookie),
    current_channel: Channel = Depends(get_current_channel)
):
    """Return presigned PUT URL for a custom thumbnail."""
    # Verify channel ownership (same as video upload)
    channel = db.query(Channel).filter(
        Channel.id == current_channel.id,
        Channel.user_id == current_user.id,
        Channel.is_suspended == False
    ).first()
    if not channel:
        raise HTTPException(status_code=403, detail="Channel not owned by user")

    # Generate unique key for thumbnail
    ext = filename.split('.')[-1]
    thumbnail_key = f"thumbnails/{current_user.id}/{uuid.uuid4().hex}.{ext}"
    try:
        presigned_url = await storage_service.generate_presigned_put_url(
            object_key=thumbnail_key,
            expiration=3600,
            content_type=content_type
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not generate thumbnail upload URL: {str(e)}")

    return UploadUrlResponse(
        upload_url=presigned_url,
        object_key=thumbnail_key,
        expires_in=3600
    )

@router.post("/complete", status_code=status.HTTP_202_ACCEPTED, response_model=VideoCompleteResponse)
async def complete_upload(
    payload: VideoCompleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie),
    current_channel: Channel = Depends(get_current_channel)
):
    """
    Step 2: Client calls this after a successful direct upload to S3.
    Creates Video record, triggers transcoding job.
    """
    # Verify channel ownership
    channel = db.query(Channel).filter(
        Channel.id == current_channel.id,
        Channel.user_id == current_user.id,
        Channel.is_suspended == False
    ).first()
    if not channel:
        raise HTTPException(status_code=403, detail="Channel not found or not owned")
    
    # Optional: check that the object actually exists in S3
    if not await storage_service.object_exists(payload.object_key):
        raise HTTPException(status_code=400, detail="File not found in storage. Upload may have failed.")
    
    # Create video record
    db_video = Video(
        channel_id=channel.id,
        title=payload.title,
        description=payload.description,
        original_filename=payload.original_filename,
        file_size=payload.file_size,
        mime_type=payload.mime_type,
        original_key=payload.object_key,
        file_url=payload.object_key,      # keep for backward compatibility
        thumbnail_url=payload.thumbnail_key,
        duration_seconds=None,            # will be set by worker
        status="processing",
        visibility=payload.visibility or "public",
        category_id=payload.category_id,
        language=payload.language or "en",
        allow_comments=payload.allow_comments if payload.allow_comments is not None else True,
        is_made_for_kids=payload.is_made_for_kids or False,
        is_short=payload.is_short or False
    )

    if payload.thumbnail_key:
        # Optionally verify the thumbnail exists
        if await storage_service.object_exists(payload.thumbnail_key):
            db_video.thumbnail_key = payload.thumbnail_key
            db_video.thumbnail_url = storage_service.get_public_url(payload.thumbnail_key)

    db.add(db_video)
    db.commit()
    db.refresh(db_video)

    # Trigger Celery task
    transcode_video_task.delay(
        video_id=db_video.id,
        original_key=payload.object_key,
        bucket=settings.S3_BUCKET_NAME
    )

    return VideoCompleteResponse(
        video_id=db_video.id,
        status="processing",
        message="Video accepted for transcoding"
    )