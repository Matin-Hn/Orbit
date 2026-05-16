from pydantic import BaseModel, Field, HttpUrl, EmailStr
from datetime import datetime
from typing import Optional

# Base schema with common attributes
class ChannelBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    handle: str = Field(..., min_length=1, max_length=30, pattern=r'^[a-zA-Z0-9_]+$')
    description: Optional[str] = Field(None, max_length=10000)
    avatar_url: Optional[HttpUrl] = Field(None, max_length=500)
    banner_url: Optional[HttpUrl] = Field(None, max_length=500)
    website: Optional[HttpUrl] = Field(None, max_length=500)
    contact_email: Optional[EmailStr] = Field(None, max_length=255)

# Schema for creating a new channel
class ChannelCreate(ChannelBase):
    is_suspended: Optional[bool] = False
    verified_badge: Optional[bool] = False

# Schema for updating an existing channel
class ChannelUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    handle: Optional[str] = Field(None, min_length=1, max_length=30, pattern=r'^[a-zA-Z0-9_]+$')
    description: Optional[str] = Field(None, max_length=10000)
    avatar_url: Optional[HttpUrl] = Field(None, max_length=500)
    banner_url: Optional[HttpUrl] = Field(None, max_length=500)
    website: Optional[HttpUrl] = Field(None, max_length=500)
    contact_email: Optional[EmailStr] = Field(None, max_length=255)
    is_suspended: Optional[bool] = None
    verified_badge: Optional[bool] = None

# Schema for response (includes all fields)
class ChannelResponse(ChannelBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    is_suspended: bool
    verified_badge: bool

    class Config:
        from_attributes = True  # For Pydantic v2 (was orm_mode in v1)

# Schema for database operation (internal use)
class ChannelInDB(ChannelResponse):
    pass

# Schema for channel list response with pagination
class ChannelListResponse(BaseModel):
    items: list[ChannelResponse]
    total: int
    page: int
    size: int
    pages: int