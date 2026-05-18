from fastapi import APIRouter, Depends, HTTPException

from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.video import VideoResponse
from app.models.user import User
from app.models.video import Video
from app.services.auth_service import get_current_user_from_cookie

router = APIRouter()

@router.get("{/{video_id}", response_model=VideoResponse)
async def get_video(
    video_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Check visibility permissions
    if video.visibility == "private" and (not current_user or video.channel.user_id != current_user.id):
        raise HTTPException(status_code=403, detail="Video is private")
    
    return video