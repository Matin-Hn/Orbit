from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException, status

from app.models.video import Video, VideoVisibility
from app.models.video_public_id import VideoPublicId
from app.crud.video import video as video_crud


async def get_video_by_public_id(
    db: Session,
    public_id: str,
    requesting_user_id: int | None,  # None = unauthenticated
) -> Video:
    video = await video_crud.get_by_public_id(db, public_id)

    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found.")

    # Visibility rules
    if video.visibility == VideoVisibility.PUBLIC:
        return video

    # Private and unlisted require the requester to be authenticated
    if requesting_user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

    if video.visibility == VideoVisibility.PRIVATE:
        if "channel" not in video.__dict__:
            await db.refresh(video, attribute_names=["channel"])
        # Fixed: Channel model uses `user_id`, not `owner_user_id`
        if video.channel.user_id != requesting_user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    # Unlisted: any authenticated user with the link can access — no ownership check needed

    return video