# app/schemas/comment.py
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class CommentBase(BaseModel):
    body: str = Field(..., min_length=1, max_length=5000)
    parent_id: Optional[int] = None

class CommentCreate(CommentBase):
    video_id: int
    user_id: int

class CommentUpdate(BaseModel):
    body: Optional[str] = Field(None, min_length=1, max_length=5000)
    is_approved: Optional[bool] = None
    is_pinned: Optional[bool] = None

class CommentResponse(CommentBase):
    id: int
    user_id: int
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