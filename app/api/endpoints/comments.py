# app/api/v1/endpoints/comments.py
from fastapi import APIRouter, Depends, Query, Path, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Literal

from app.api.deps import get_db
from app.schemas.comment import (
    CommentCreate, 
    CommentUpdate, 
    CommentResponse, 
    CommentListResponse,
    CommentApprove
)
from app.services.auth_service import get_current_user_from_cookie, get_current_channel, get_optional_current_user_from_cookie
from app.services.comment_service import CommentService
from app.services.video_service import get_video_by_public_id
from app.models.user import User
from app.models.channel import Channel

router = APIRouter(prefix="/comments", tags=["comments"])

def get_comment_service(db: AsyncSession = Depends(get_db)) -> CommentService:
    return CommentService(db)

@router.post("/", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
async def create_comment(
    comment_data: CommentCreate,
    current_user: User = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db),
    comment_service: CommentService = Depends(get_comment_service)
):
    """
    Create a new comment or reply to an existing comment.
    **Requires authentication**
    """
    video = await get_video_by_public_id(db, comment_data.public_id, current_user)
    comment_data.video_id = video.id
    response = await comment_service.create_comment(comment_data, current_user)
    return response

@router.get("/{comment_id}", response_model=CommentResponse)
async def get_comment(
    comment_id: int = Path(..., gt=0),
    comment_service: CommentService = Depends(get_comment_service)
):
    """
    Get a specific comment by ID.
    **Public access**
    """
    return await comment_service.get_comment(comment_id)

@router.get("/video/{public_id}", response_model=CommentListResponse)
async def get_video_comments(
    public_id: str = Path(...),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    sort_by: Literal["newest", "popular"] = Query("newest", description="Sort order for comments"),
    current_user: Optional[User] = Depends(get_optional_current_user_from_cookie),
    db: AsyncSession = Depends(get_db),
    comment_service: CommentService = Depends(get_comment_service)
):
    """
    Get all root comments for a video with pagination.
    **Public access** - Unapproved comments are hidden from regular users
    """
    video = await get_video_by_public_id(db, public_id=public_id, requesting_user_id=current_user.id if current_user else None)
    comments = await comment_service.get_video_comments(
        video_id=video.id,
        page=page,
        per_page=per_page,
        sort_by = sort_by,
        current_user=current_user if current_user else None
    )
    return comments

@router.get("/{comment_id}/replies", response_model=CommentListResponse)
async def get_comment_replies(
    comment_id: int = Path(..., gt=0),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=50),
    comment_service: CommentService = Depends(get_comment_service)
):
    """
    Get replies for a specific comment with pagination.
    **Public access**
    """
    return await comment_service.get_comment_replies(comment_id, page, per_page)

@router.put("/{comment_id}", response_model=CommentResponse)
async def update_comment(
    comment_id: int = Path(..., gt=0),
    update_data: CommentUpdate = ...,
    current_user: User = Depends(get_current_user_from_cookie),
    comment_service: CommentService = Depends(get_comment_service)
):
    """
    Update a comment.
    **Permissions:**
    - Comment owner can edit body
    - Channel owner can edit any field
    - Superuser can edit any field
    - Only channel owner or admin can change approval/pin status
    """
    return await comment_service.update_comment(comment_id, update_data, current_user)

@router.delete("/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    comment_id: int = Path(..., gt=0),
    current_user: User = Depends(get_current_user_from_cookie),
    comment_service: CommentService = Depends(get_comment_service)
):
    """
    Soft delete a comment.
    **Permissions:**
    - Comment owner
    - Channel owner
    - Superuser
    """
    await comment_service.delete_comment(comment_id, current_user)

@router.post("/{comment_id}/approve", response_model=CommentResponse)
async def approve_comment(
    comment_id: int = Path(..., gt=0),
    current_user: User = Depends(get_current_user_from_cookie),
    comment_service: CommentService = Depends(get_comment_service),
):
    """
    Approve a comment.
    **Permissions:**
    - Channel owner
    - Admin
    - Superuser
    """
    return await comment_service.approve_comment(comment_id, current_user)