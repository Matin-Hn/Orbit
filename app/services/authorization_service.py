# app/services/authorization_service.py
from typing import Optional
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.models.comment import Comment
from app.models.video import Video
from app.models.channel import Channel

class AuthorizationService:
    def __init__(self, db: Session):
        self.db = db
    
    def is_comment_owner(self, user: User, comment: Comment) -> bool:
        """Check if user is the comment owner"""
        return comment.user_id == user.id
    
    def is_admin_or_channel_owner(self, user: User, channel: Channel) -> bool:
        """Check if user has admin or channel owner privileges"""
        # Check if channel exists (might be None)
        if channel is None:
            return user.role in [UserRole.ADMIN, UserRole.SUPERUSER]
        
        # Admin, superuser, or channel owner
        return (
            user.role in [UserRole.ADMIN, UserRole.SUPERUSER] or 
            channel.user_id == user.id
        )
    
    def is_video_owner(self, user: User, video: Video) -> bool:
        """Check if user owns the video's channel"""
        if not video or not video.channel:
            return False
        return video.channel.user_id == user.id
    
    def can_modify_comment(self, user: User, comment: Comment) -> bool:
        """Check if user can modify (update/delete) a comment"""
        # Comment owner can always modify their own comment
        if self.is_comment_owner(user, comment):
            return True
        
        # Superuser can modify any comment
        if user.role == UserRole.SUPERUSER:
            return True
        
        # Get the video and check if user owns the channel
        video = self.db.query(Video).filter(Video.id == comment.video_id).first()
        if video and video.channel and self.is_video_owner(user, video):
            return True
        
        # Admin can modify comments on their own channel's videos
        if user.role == UserRole.ADMIN:
            if video and video.channel and self.is_admin_or_channel_owner(user, video.channel):
                return True
        
        return False
    
    def can_approve_comment(self, user: User, channel: Channel) -> bool:
        """Check if user can approve comments"""
        # Channel owner, admin, or superuser can approve
        if self.is_admin_or_channel_owner(user, channel):
            return True
        
        return False
    
    def can_pin_comment(self, user: User, comment: Comment) -> bool:
        """Check if user can pin/unpin comments"""
        # Get the video associated with the comment
        video = self.db.query(Video).filter(Video.id == comment.video_id).first()
        if not video:
            return False
        
        # Superuser can pin any comment
        if user.role == UserRole.SUPERUSER:
            return True
        
        # Channel owner or admin can pin comments on their videos
        if video.channel and self.is_admin_or_channel_owner(user, video.channel):
            return True
        
        return False