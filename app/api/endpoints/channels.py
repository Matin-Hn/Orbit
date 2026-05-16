from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.api.deps import get_db
from app.models.channel import Channel
from app.models.user import User
from app.schemas.channel import (
    ChannelCreate,
    ChannelUpdate,
    ChannelResponse,
    ChannelListResponse
)
from app.services.auth_service import get_current_user_from_cookie

router = APIRouter(prefix="/channels",tags=["channels"])


# CREATE - POST /channels
@router.post(
    "/",
    response_model=ChannelResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new channel"
)
def create_channel(
    channel: ChannelCreate,
    current_user: User = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db)
):
    """
    Create a new channel with the provided data.
    
    - **name**: Unique channel name (1-100 characters)
    - **handle**: Unique channel handle with alphanumeric characters and underscores only
    - **user_id**: Owner user ID (must exist and not have another channel)
    """
    # Check if handle already exists
    if db.query(Channel).filter(Channel.handle == channel.handle).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Channel with handle '{channel.handle}' already exists"
        )
    
    # Check if name already exists
    if db.query(Channel).filter(Channel.name == channel.name).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Channel with name '{channel.name}' already exists"
        )
    
    # Check if user already has a channel
    channel_existing = db.query(Channel).filter(Channel.user_id == current_user.id).first()
    if channel_existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"You already have a channel {channel_existing.name}"
        )
    
    # Add user_id manually
    channel_dict = channel.model_dump()

    # Convert HttpUrl objects to strings
    for field in ['avatar_url', 'banner_url', 'website']:
        if channel_dict.get(field):
            channel_dict[field] = str(channel_dict[field])

    channel_dict["user_id"] = current_user.id
    # Create new channel
    db_channel = Channel(**channel_dict)
    db.add(db_channel)
    db.commit()
    db.refresh(db_channel)
    
    return db_channel


@router.get(
    "/{handle}",
    response_model=ChannelResponse,
    summary="Get channel by handle"
)
def get_channel_by_handle(
    handle: str,
    db: Session = Depends(get_db)
):
    """
    Retrieve a specific channel by its unique handle.
    
    - **handle**: The unique handle of the channel
    """
    channel = db.query(Channel).filter(Channel.handle == handle).first()
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel with handle '{handle}' not found"
        )
    
    return channel


@router.get(
    "/",
    response_model=ChannelListResponse,
    summary="List channels with pagination"
)
def list_channels(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search in name, handle, or description"),
    is_suspended: Optional[bool] = Query(None, description="Filter by suspended status"),
    verified_badge: Optional[bool] = Query(None, description="Filter by verification status"),
    db: Session = Depends(get_db)
):
    """
    List channels with pagination and optional filters.
    
    - **page**: Page number (starting from 1)
    - **size**: Number of items per page (1-100)
    - **search**: Optional search term for name, handle, or description
    - **is_suspended**: Optional filter for suspended channels
    - **verified_badge**: Optional filter for verified channels
    """
    # Base query
    query = db.query(Channel)
    
    # Apply filters
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Channel.name.ilike(search_term),
                Channel.handle.ilike(search_term),
                Channel.description.ilike(search_term)
            )
        )
    
    if is_suspended is not None:
        query = query.filter(Channel.is_suspended == is_suspended)
    
    if verified_badge is not None:
        query = query.filter(Channel.verified_badge == verified_badge)
    
    # Get total count
    total = query.count()
    
    # Calculate pages
    pages = (total + size - 1) // size if total > 0 else 0
    
    # Apply pagination
    offset = (page - 1) * size
    channels = query.order_by(Channel.created_at.desc()).offset(offset).limit(size).all()
    
    return ChannelListResponse(
        items=channels,
        total=total,
        page=page,
        size=size,
        pages=pages
    )


# UPDATE - PUT /channels/{channel_id}
@router.put(
    "/{channel_id}",
    response_model=ChannelResponse,
    summary="Update an existing channel"
)
def update_channel(
    channel_id: int,
    channel_update: ChannelUpdate,
    db: Session = Depends(get_db)
):
    """
    Update an existing channel partially or fully.
    Only provided fields will be updated.
    
    - **channel_id**: The ID of the channel to update
    - Fields to update (all optional)
    """
    # Find the channel
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel with ID {channel_id} not found"
        )
    
    # Get only the fields that were actually provided
    update_data = channel_update.model_dump(exclude_unset=True)
    
    # Check unique constraints if handle or name are being updated
    if "handle" in update_data and update_data["handle"] != channel.handle:
        if db.query(Channel).filter(Channel.handle == update_data["handle"]).first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Channel with handle '{update_data['handle']}' already exists"
            )
    
    if "name" in update_data and update_data["name"] != channel.name:
        if db.query(Channel).filter(Channel.name == update_data["name"]).first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Channel with name '{update_data['name']}' already exists"
            )
    
    # Update the channel
    for field, value in update_data.items():
        setattr(channel, field, value)
    
    db.commit()
    db.refresh(channel)
    
    return channel


# DELETE - DELETE /channels/{channel_id}
@router.delete(
    "/{channel_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a channel"
)
def delete_channel(
    channel_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a channel by its ID.
    This will also delete all related content due to cascading deletes.
    
    - **channel_id**: The ID of the channel to delete
    """
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel with ID {channel_id} not found"
        )
    
    db.delete(channel)
    db.commit()
    
    return None  # 204 No Content


# PATCH - PATCH /channels/{channel_id}/suspend
@router.patch(
    "/{channel_id}/suspend",
    response_model=ChannelResponse,
    summary="Suspend or unsuspend a channel"
)
def toggle_channel_suspension(
    channel_id: int,
    suspend: bool = Query(..., description="True to suspend, False to unsuspend"),
    db: Session = Depends(get_db)
):
    """
    Toggle the suspension status of a channel.
    
    - **channel_id**: The ID of the channel
    - **suspend**: True to suspend, False to unsuspend
    """
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel with ID {channel_id} not found"
        )
    
    channel.is_suspended = suspend
    db.commit()
    db.refresh(channel)
    
    return channel


# PATCH - PATCH /channels/{channel_id}/verify
@router.patch(
    "/{channel_id}/verify",
    response_model=ChannelResponse,
    summary="Verify or unverify a channel"
)
def toggle_channel_verification(
    channel_id: int,
    verify: bool = Query(..., description="True to verify, False to unverify"),
    db: Session = Depends(get_db)
):
    """
    Toggle the verification badge of a channel.
    
    - **channel_id**: The ID of the channel
    - **verify**: True to verify, False to unverify
    """
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel with ID {channel_id} not found"
        )
    
    channel.verified_badge = verify
    db.commit()
    db.refresh(channel)
    
    return channel