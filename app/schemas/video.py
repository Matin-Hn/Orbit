from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Optional, List
from enum import Enum

class VisibilityEnum(str, Enum):
    PUBLIC = "public"
    UNLISTED = "unlisted"
    PRIVATE = "private"
    SCHEDULED = "scheduled"

class LicenseEnum(str, Enum):
    STANDARD = "standard"
    CC = "cc"

# Base schema
class VideoBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = Field(None, max_length=5000)
    visibility: VisibilityEnum = VisibilityEnum.PUBLIC
    scheduled_at: Optional[datetime] = None
    category_id: Optional[int] = None
    language: str = Field("en", max_length=50)
    license: LicenseEnum = LicenseEnum.STANDARD
    allow_comments: bool = True
    is_made_for_kids: bool = False
    is_short: bool = False
    
    @validator("scheduled_at")
    def validate_scheduled_at(cls, v, values):
        if v and values.get("visibility") != VisibilityEnum.SCHEDULED:
            raise ValueError("scheduled_at only allowed for scheduled videos")
        if v and v <= datetime.utcnow():
            raise ValueError("scheduled_at must be in the future")
        return v

# Create video request
class VideoCreate(VideoBase):
    channel_id: int  # Will be taken from authenticated user
    duration_seconds: Optional[int] = Field(None, gt=0, le=43200)  # Max 12 hours
    
    @validator("duration_seconds")
    def validate_duration(cls, v):
        if v and v <= 0:
            raise ValueError("duration_seconds must be positive")
        return v

# Update video request
class VideoUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = Field(None, max_length=5000)
    visibility: Optional[VisibilityEnum] = None
    scheduled_at: Optional[datetime] = None
    category_id: Optional[int] = None
    language: Optional[str] = Field(None, max_length=50)
    license: Optional[LicenseEnum] = None
    allow_comments: Optional[bool] = None
    is_made_for_kids: Optional[bool] = None
    
    @validator("scheduled_at")
    def validate_scheduled_at(cls, v, values):
        if v and v <= datetime.utcnow():
            raise ValueError("scheduled_at must be in the future")
        return v

# Video response schema
class VideoResponse(VideoBase):
    id: int
    channel_id: int
    duration_seconds: Optional[int] = None
    thumbnail_url: Optional[str] = None
    file_url: str
    created_at: datetime
    published_at: Optional[datetime] = None
    updated_at: datetime
    
    class Config:
        from_attributes = True

# Detailed video response (for watch page)
class VideoDetailResponse(VideoResponse):
    channel_name: Optional[str] = None
    channel_avatar_url: Optional[str] = None
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    
    # Video availability
    is_published: bool
    can_edit: bool = False  # For current user
    
    class Config:
        from_attributes = True

# Video list response
class VideoListResponse(BaseModel):
    items: List[VideoResponse]
    total: int
    page: int
    page_size: int
    has_next: bool

# Upload video response (after S3 upload)
class VideoUploadResponse(BaseModel):
    video_id: int
    title: str
    file_url: str
    upload_url: str  # Presigned URL for direct upload
    expires_in: int = 3600
    message: str

# Search/filter parameters
class VideoFilterParams(BaseModel):
    channel_id: Optional[int] = None
    category_id: Optional[int] = None
    visibility: Optional[VisibilityEnum] = None
    is_short: Optional[bool] = None
    query: Optional[str] = Field(None, min_length=1, max_length=100)
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    min_duration: Optional[int] = Field(None, gt=0)
    max_duration: Optional[int] = Field(None, gt=0)
    
    class Config:
        arbitrary_types_allowed = True