# app/schemas/comment.py
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class CommentBase(BaseModel):
    body: str = Field(..., min_length=1, max_length=5000)
    parent_id: Optional[int] = Field(None, description="Parent comment ID for replies")

class CommentCreate(CommentBase):
    video_id: int = Field(..., description="Video ID to comment on")

class CommentUpdate(BaseModel):
    body: Optional[str] = Field(None, min_length=1, max_length=5000)
    is_pinned: Optional[bool] = Field(None, description="Pin/Unpin comment")
    is_approved: Optional[bool] = Field(None, description="Approve/Unapprove comment")

class CommentApprove(BaseModel):
    """Schema for approval endpoint - explicit about what's being changed"""
    pass  # No body needed, just the action

class CommentResponse(CommentBase):
    id: int
    user_id: int
    username: str
    video_id: int
    is_pinned: bool
    is_edited: bool
    is_approved: bool
    created_at: datetime
    updated_at: datetime
    reply_count: int = 0
    
    class Config:
        from_attributes = True

class CommentListResponse(BaseModel):
    total: int
    comments: List[CommentResponse]
    page: int
    per_page: int