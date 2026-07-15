from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

from fastapi import HTTPException, status

from app.models.channel import Channel
from app.models.user import User
from app.schemas.channel import ChannelUpdate, ChannelCreate
from app.services.authorization_service import AuthorizationService



class ChannelService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.auth_service = AuthorizationService(db)

    async def create_channel(
        self,
        channel: ChannelCreate,
        current_user: User
    ):
        # Check if handle already exists
        result = await self.db.execute(select(Channel).filter(Channel.handle == channel.handle))
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Channel with handle '{channel.handle}' already exists"
            )

        # Check if name already exists
        result = await self.db.execute(select(Channel).filter(Channel.name == channel.name))
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Channel with name '{channel.name}' already exists"
            )

        # Check if user already has a channel
        result = await self.db.execute(select(Channel).filter(Channel.user_id == current_user.id))
        channel_existing = result.scalar_one_or_none()
        if channel_existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"You already have a channel: [{channel_existing.name}]"
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
        self.db.add(db_channel)
        await self.db.commit()
        await self.db.refresh(db_channel)

        return db_channel


    async def update_channel(
        self,
        channel_id: int,
        channel_update: ChannelUpdate,
        current_user: User
):
        result = await self.db.execute(select(Channel).filter(Channel.id == channel_id))
        channel = result.scalar_one_or_none()
        # Check access
        if not self.auth_service.is_admin_or_channel_owner(current_user, channel):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can't update others channel" 
            )
        # Find the channel
        if not channel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Channel with ID {channel_id} not found"
            )

        # Get only the fields that were actually provided
        update_data = channel_update.model_dump(exclude_unset=True, mode="json")

        # Check unique constraints if handle or name are being updated
        if "handle" in update_data and update_data["handle"] != channel.handle:
            result = await self.db.execute(select(Channel).filter(Channel.handle == update_data["handle"]))
            if result.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Channel with handle '{update_data['handle']}' already exists"
                )

        if "name" in update_data and update_data["name"] != channel.name:
            result = await self.db.execute(select(Channel).filter(Channel.name == update_data["name"]))
            if result.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Channel with name '{update_data['name']}' already exists"
                )

        # Update the channel
        for field, value in update_data.items():
            setattr(channel, field, value)

        await self.db.commit()
        await self.db.refresh(channel)

        return channel
