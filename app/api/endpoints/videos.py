import asyncio
import uuid
import jwt
import logging
from datetime import timedelta
from sqlalchemy.orm import Session


from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect

from app.services.auth_service import (
    get_current_user_from_cookie,
    get_current_channel,
    create_access_token
)
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
from app.ws.manager import manager


router = APIRouter(prefix="/videos", tags=["video operations"])
logger = logging.getLogger(__name__)


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

@router.get("/{video_id}/signed-url")
async def get_video_signed_manifest_url(
    video_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie),
):
    """
    Returns a short-lived signed URL for the HLS manifest (.m3u8).
    Only accessible if the video is ready and the user has viewing rights.
    """
    video = db.query(Video).filter(
        Video.id == video_id,
        Video.deleted_at.is_(None)
    ).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # 1. Video must be in 'ready' state
    if video.status != "ready":
        raise HTTPException(status_code=400, detail="Video is not ready for playback")

    # 2. Access control
    #    - Owner (channel owner) can always access
    #    - Public videos are accessible to any authenticated user
    #    - Unlisted / scheduled videos are treated as private for simplicity
    is_owner = video.channel.user_id == current_user.id
    if not is_owner and video.visibility != "public":
        raise HTTPException(status_code=403, detail="You do not have permission to view this video")

    # 3. Determine the S3 key of the HLS manifest.
    #    Based on the transcoding task, the manifest is stored at:
    #       processed/{video_id}/hls/master.m3u8
    manifest_key = f"processed/{video_id}/hls/master.m3u8"

    # 4. Generate a presigned URL valid for 60 seconds (short-lived)
    try:
        signed_url = storage_service.generate_presigned_get_url(
            object_key=manifest_key,
            expiration=60
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not generate signed URL: {str(e)}")

    return {"signed_url": signed_url}

@router.websocket("/ws/video/{video_id}")
async def websocket_video_status(
    websocket: WebSocket,
    video_id: int,
    db: Session = Depends(get_db)
):
    """
    Real‑time video processing status via WebSocket.
    Authentication is handled in the first message, NOT during the handshake.
    """
    # 1. Accept immediately (no token in URL / cookies)
    await websocket.accept()

    # 2. Wait for auth message (5s timeout)
    try:
        auth_message = await asyncio.wait_for(websocket.receive_json(), timeout=5.0)
    except asyncio.TimeoutError:
        await websocket.send_json({"type": "auth_error", "message": "Authentication timeout"})
        await websocket.close(code=4001)
        return

    if auth_message.get("type") != "auth" or not auth_message.get("token"):
        await websocket.send_json({"type": "auth_error", "message": "Invalid auth message"})
        await websocket.close(code=4001)
        return

    # 3. Verify JWT
    token = auth_message["token"]
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except jwt.ExpiredSignatureError:
        await websocket.send_json({"type": "auth_error", "message": "Token expired"})
        await websocket.close(code=4001)
        return
    except jwt.InvalidTokenError:
        await websocket.send_json({"type": "auth_error", "message": "Invalid token"})
        await websocket.close(code=4001)
        return

    user_id = payload.get("sub") or payload.get("user_id")
    if not user_id:
        await websocket.send_json({"type": "auth_error", "message": "Token malformed"})
        await websocket.close(code=4001)
        return

    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        await websocket.send_json({"type": "auth_error", "message": "User not found"})
        await websocket.close(code=4001)
        return

    # 4. Authorisation: video must belong to the user
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        await websocket.send_json({"type": "video.error", "videoId": video_id, "error": "Video not found"})
        await websocket.close(code=4004)
        return

    channel = db.query(Channel).filter(
        Channel.id == video.channel_id,
        Channel.user_id == user.id
    ).first()
    if not channel:
        await websocket.send_json({"type": "auth_error", "message": "Access denied"})
        await websocket.close(code=4003)
        return

    # 5. Success
    await websocket.send_json({"type": "auth_ok"})

    # 6. Immediate response if already processed
    if video.status == "ready":
        await websocket.send_json({"type": "video.ready", "videoId": video_id})
        await websocket.close()
        return
    if video.status == "failed":
        await websocket.send_json({
            "type": "video.error",
            "videoId": video_id,
            "error": video.processing_error or "Transcoding failed"
        })
        await websocket.close()
        return

    # 7. Subscribe to Redis for updates
    await manager.connect(video_id, websocket)
    try:
        await manager.subscribe(video_id, websocket)
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for video {video_id}")
    except Exception as e:
        logger.error(f"WebSocket error for video {video_id}: {e}")
        try:
            await websocket.send_json({"type": "error", "message": "Internal error"})
        except Exception:
            pass
    finally:
        manager.disconnect(video_id, websocket)
        try:
            await websocket.close()
        except Exception:
            pass


# Generate short-lived token for websocket
@router.get("/ws-token")
async def get_websocket_token(
    current_user: User = Depends(get_current_user_from_cookie)
):
    """
    Returns a short-lived token for WebSocket authentication.
    The HttpOnly cookie is sent automatically with this request.
    """
    # Generate a short-lived WebSocket-specific token (5 minutes)
    ws_token = create_access_token(
        subject=current_user.id,
        expires_delta=timedelta(minutes=5)
    )
    return {"token": ws_token, "expires_in": 300}