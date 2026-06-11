from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException, status

from app.models.video import Video, VideoVisibility
from app.models.video_public_id import VideoPublicId
from app.crud.video import video as video_crud


def get_video_by_public_id(
    db: Session,
    public_id: str,
    requesting_user_id: int | None,  # None = unauthenticated
) -> Video:
    video = video_crud.get_by_public_id(db, public_id)

    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found.")

    # Visibility rules
    if video.visibility == VideoVisibility.PUBLIC:
        return video

    # Private and unlisted require the requester to own the video (or be authenticated at minimum)
    if requesting_user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

    if video.visibility == VideoVisibility.PRIVATE:
        # Only the channel owner can see their own private videos
        # Assumes Channel model has an owner_user_id — adjust to your field name
        if video.channel.owner_user_id != requesting_user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    # Unlisted: authenticated users can access via direct link — no ownership check needed

    return video