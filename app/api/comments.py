# app/api/v1/endpoints/comments.py
from fastapi import APIRouter, Depends, Query, Path
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.comment import (
    CommentCreate, 
    CommentUpdate, 
    CommentResponse, 
    CommentListResponse
)
from app.services.comment_service import CommentService
from app.crud.comment import CommentCRUD

router = APIRouter(prefix="/comments", tags=["comments"])

def get_comment_service(db: Session = Depends(get_db)) -> CommentService:
    comment_repo = CommentCRUD(db)
    return CommentService(comment_repo)

@router.post("/", response_model=CommentResponse, status_code=201)
async def create_comment(
    comment_data: CommentCreate,
    comment_service: CommentService = Depends(get_comment_service)
):
    """
    Create a new comment or reply to an existing comment.
    """
    return comment_service.create_comment(comment_data)

@router.get("/{comment_id}", response_model=CommentResponse)
async def get_comment(
    comment_id: int = Path(..., gt=0),
    comment_service: CommentService = Depends(get_comment_service)
):
    """
    Get a specific comment by ID.
    """
    return comment_service.get_comment(comment_id)

@router.get("/video/{video_id}", response_model=CommentListResponse)
async def get_video_comments(
    video_id: int = Path(..., gt=0),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    comment_service: CommentService = Depends(get_comment_service)
):
    """
    Get all root comments for a video with pagination.
    """
    return comment_service.get_video_comments(video_id, page, per_page)

@router.get("/{comment_id}/replies", response_model=CommentListResponse)
async def get_comment_replies(
    comment_id: int = Path(..., gt=0),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=50),
    comment_service: CommentService = Depends(get_comment_service)
):
    """
    Get replies for a specific comment with pagination.
    """
    return comment_service.get_comment_replies(comment_id, page, per_page)

@router.put("/{comment_id}", response_model=CommentResponse)
async def update_comment(
    comment_id: int = Path(..., gt=0),
    update_data: CommentUpdate = ...,
    user_id: int = Query(..., description="Current user ID"),
    comment_service: CommentService = Depends(get_comment_service)
):
    """
    Update a comment. Only the owner can edit the body.
    Moderators can update approval and pin status.
    """
    return comment_service.update_comment(comment_id, user_id, update_data)

@router.delete("/{comment_id}", status_code=204)
async def delete_comment(
    comment_id: int = Path(..., gt=0),
    user_id: int = Query(..., description="Current user ID"),
    comment_service: CommentService = Depends(get_comment_service)
):
    """
    Soft delete a comment. Only the owner can delete their comment.
    """
    comment_service.delete_comment(comment_id, user_id)