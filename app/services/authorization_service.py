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
        """Check if user has admin or superuser privileges"""
        return user.role is UserRole.ADMIN or channel.user_id == user.id
    
    def can_modify_comment(self, user: User, comment: Comment, channel: Channel) -> bool:
        """Check if user can modify (update/delete) a comment"""
        # Admins, comment owner and channel owner can modify
        if self.is_admin_or_channel_owner(user, channel) or self.is_comment_owner:
            return True
        
        # 
        video = self.db.query(Video).filter(Video.id == comment.video_id).first()
        if video and self.is_video_owner(user, video):
            return True
        
        # Superuser can modify any comment
        if user.role == UserRole.SUPERUSER:
            return True
        
        return False
    
    def can_approve_comment(self, user: User, channel: Channel) -> bool:
        """Check if user can approve comments"""
        # Admins and channel owner can approve comment
        if self.is_admin_or_channel_owner(user, channel):
            return True
        
        return False
    
    def can_pin_comment(self, user: User, comment: Comment, channel: Channel) -> bool:
        """Check if user can pin/unpin comments"""
        # Only channel owner or admin can pin
        video = self.db.query(Video).filter(Video.id == comment.video_id).first()
        if video and self.is_admin_or_channel_owner(user, channel):
            return True
            
        return False