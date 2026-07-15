from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.services.channel_service import ChannelService

router = APIRouter(prefix="/channels", tags=["channels"])


def get_channel_service(db: AsyncSession = Depends(get_db)) -> ChannelService:
    return ChannelService(db)

# CREATE - POST /channels
@router.post(
    "/",
    response_model=ChannelResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new channel"
)
async def create_channel(
    channel: ChannelCreate,
    current_user: User = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db),
    channel_service: ChannelService = Depends(get_channel_service)
):
    """
    Create a new channel with the provided data.

    - **name**: Unique channel name (1-100 characters)
    - **handle**: Unique channel handle with alphanumeric characters and underscores only
    - **user_id**: Owner user ID (must exist and not have another channel)
    """
    
    response = await channel_service.create_channel(channel, current_user)
    return response

@router.get(
    "/{handle}",
    response_model=ChannelResponse,
    summary="Get channel by handle"
)
async def get_channel_by_handle(
    handle: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve a specific channel by its unique handle.

    - **handle**: The unique handle of the channel
    """
    result = await db.execute(select(Channel).filter(Channel.handle == handle))
    channel = result.scalar_one_or_none()
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
async def list_channels(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search in name, handle, or description"),
    is_suspended: Optional[bool] = Query(None, description="Filter by suspended status"),
    verified_badge: Optional[bool] = Query(None, description="Filter by verification status"),
    db: AsyncSession = Depends(get_db)
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
    query = select(Channel)
    count_query = select(func.count()).select_from(Channel)

    # Apply filters
    if search:
        search_term = f"%{search}%"
        search_filter = or_(
            Channel.name.ilike(search_term),
            Channel.handle.ilike(search_term),
            Channel.description.ilike(search_term)
        )
        query = query.filter(search_filter)
        count_query = count_query.filter(search_filter)

    if is_suspended is not None:
        query = query.filter(Channel.is_suspended == is_suspended)
        count_query = count_query.filter(Channel.is_suspended == is_suspended)

    if verified_badge is not None:
        query = query.filter(Channel.verified_badge == verified_badge)
        count_query = count_query.filter(Channel.verified_badge == verified_badge)

    # Get total count
    total = (await db.execute(count_query)).scalar_one()

    # Calculate pages
    pages = (total + size - 1) // size if total > 0 else 0

    # Apply pagination
    offset = (page - 1) * size
    result = await db.execute(
        query.order_by(Channel.created_at.desc()).offset(offset).limit(size)
    )
    channels = result.scalars().all()

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
async def update_channel(
    channel_id: int,
    channel_update: ChannelUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie),
    channel_service: ChannelService = Depends(get_channel_service)
):
    """
    Update an existing channel partially or fully.
    Only provided fields will be updated.

    - **channel_id**: The ID of the channel to update
    - Fields to update (all optional)
    """

    response = await channel_service.update_channel(channel_id, channel_update, current_user)
    return response


# DELETE - DELETE /channels/{channel_id}
@router.delete(
    "/{channel_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a channel"
)
async def delete_channel(
    channel_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a channel by its ID.
    This will also delete all related content due to cascading deletes.

    - **channel_id**: The ID of the channel to delete
    """
    result = await db.execute(select(Channel).filter(Channel.id == channel_id))
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel with ID {channel_id} not found"
        )

    await db.delete(channel)
    await db.commit()

    return None  # 204 No Content


# PATCH - PATCH /channels/{channel_id}/suspend
@router.patch(
    "/{channel_id}/suspend",
    response_model=ChannelResponse,
    summary="Suspend or unsuspend a channel"
)
async def toggle_channel_suspension(
    channel_id: int,
    suspend: bool = Query(..., description="True to suspend, False to unsuspend"),
    db: AsyncSession = Depends(get_db)
):
    """
    Toggle the suspension status of a channel.

    - **channel_id**: The ID of the channel
    - **suspend**: True to suspend, False to unsuspend
    """
    result = await db.execute(select(Channel).filter(Channel.id == channel_id))
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel with ID {channel_id} not found"
        )

    channel.is_suspended = suspend
    await db.commit()
    await db.refresh(channel)

    return channel


# PATCH - PATCH /channels/{channel_id}/verify
@router.patch(
    "/{channel_id}/verify",
    response_model=ChannelResponse,
    summary="Verify or unverify a channel"
)
async def toggle_channel_verification(
    channel_id: int,
    verify: bool = Query(..., description="True to verify, False to unverify"),
    db: AsyncSession = Depends(get_db)
):
    """
    Toggle the verification badge of a channel.

    - **channel_id**: The ID of the channel
    - **verify**: True to verify, False to unverify
    """
    result = await db.execute(select(Channel).filter(Channel.id == channel_id))
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel with ID {channel_id} not found"
        )

    channel.verified_badge = verify
    await db.commit()
    await db.refresh(channel)

    return channel