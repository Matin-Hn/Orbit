# app/services/comment_service.py
from typing import Optional, List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.crud.comment import comment as comment_crud
from app.crud.video import video as video_crud
from app.schemas.comment import CommentCreate, CommentUpdate, CommentResponse, CommentListResponse
from app.models.user import User
from app.models.channel import Channel
from app.services.authorization_service import AuthorizationService

class CommentService:
    def __init__(self, db: Session):
        self.db = db
        self.auth_service = AuthorizationService(db)
    
    def _to_response(self, comment) -> CommentResponse:
        return CommentResponse(
            id=comment.id,
            user_id=comment.user_id,
            video_id=comment.video_id,
            parent_id=comment.parent_id,
            body=comment.body,
            is_pinned=comment.is_pinned,
            is_edited=comment.is_edited,
            is_approved=comment.is_approved,
            created_at=comment.created_at,
            updated_at=comment.updated_at,
            reply_count=len(comment.replies) if comment.replies else 0
        )
    
    def create_comment(
        self, 
        comment_data: CommentCreate, 
        current_user: User
    ) -> CommentResponse:
        """Create a new comment - requires authentication"""
        # Validate parent comment if replying
        video_existing = video_crud.get(self.db, id=comment_data.video_id)
        if not video_existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video with id {comment_data.video_id} is not exist."
            )            
        if comment_data.parent_id:
            parent_comment = comment_crud.get(self.db, id=comment_data.parent_id)
            if not parent_comment:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Parent comment not found"
                )
            if parent_comment.parent_id is not None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot reply to a reply. Only one level of nesting allowed."
                )
        
        comment = comment_crud.create(
            self.db, 
            obj_in=comment_data, 
            user_id=current_user.id
        )
        
        return self._to_response(comment)
    
    def get_comment(self, comment_id: int) -> CommentResponse:
        """Get a single comment - public access"""
        comment = comment_crud.get(self.db, id=comment_id)
        if not comment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Comment not found"
            )
        
        # Only show approved comments to non-privileged users
        # This check would be in a separate method if you want to filter
        return self._to_response(comment)
    
    def get_video_comments(
        self, 
        video_id: int, 
        page: int = 1, 
        per_page: int = 20,
        current_user: Optional[User] = None
    ) -> CommentListResponse:
        """Get video comments - public access with optional approval filtering"""
        skip = (page - 1) * per_page
        comments, total = comment_crud.get_by_video(
            self.db,
            video_id=video_id,
            skip=skip,
            limit=per_page
        )
        
        # Filter unapproved comments for non-privileged users
        if current_user:
            is_privileged = (
                self.auth_service.is_admin_or_superuser(current_user) or
                self.auth_service.is_channel_owner(current_user, video_id)
            )
        else:
            is_privileged = False
        
        if not is_privileged:
            comments = [c for c in comments if c.is_approved]
        
        comment_responses = [self._to_response(c) for c in comments]
        
        return CommentListResponse(
            total=total,
            comments=comment_responses,
            page=page,
            per_page=per_page
        )
    
    def get_comment_replies(
        self, 
        comment_id: int, 
        page: int = 1, 
        per_page: int = 10,
        current_user: Optional[User] = None
    ) -> CommentListResponse:
        """Get comment replies - public access"""
        parent_comment = comment_crud.get(self.db, id=comment_id)
        if not parent_comment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parent comment not found"
            )
        
        skip = (page - 1) * per_page
        replies, total = comment_crud.get_replies(
            self.db,
            parent_id=comment_id,
            skip=skip,
            limit=per_page
        )
        
        reply_responses = [self._to_response(r) for r in replies]
        
        return CommentListResponse(
            total=total,
            comments=reply_responses,
            page=page,
            per_page=per_page
        )
    
    def update_comment(
        self, 
        comment_id: int, 
        update_data: CommentUpdate,
        current_user: User
    ) -> CommentResponse:
        """Update comment - requires proper authorization"""
        comment = comment_crud.get(self.db, id=comment_id)
        if not comment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Comment not found"
            )
        
        # Check modification permissions
        if not self.auth_service.can_modify_comment(current_user, comment):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to modify this comment"
            )
        
        # Only channel owner or admin/superuser can pin comments
        if update_data.is_pinned is not None:
            if not self.auth_service.can_pin_comment(current_user, comment):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have permission to pin/unpin this comment"
                )
        
        # Only channel owner or admin can approve comments
        if update_data.is_approved is not None:
            if not self.auth_service.can_approve_comment(current_user, comment):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have permission to approve this comment"
                )
        
        comment = comment_crud.update(
            self.db,
            db_obj=comment,
            obj_in=update_data
        )
        
        return self._to_response(comment)
    
    def delete_comment(
        self, 
        comment_id: int,
        current_user: User
    ) -> None:
        """Soft delete comment - requires proper authorization"""
        comment = comment_crud.get(self.db, id=comment_id)
        if not comment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Comment not found"
            )
        
        # Check deletion permissions
        if not self.auth_service.can_modify_comment(current_user, comment):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to delete this comment"
            )
        
        comment_crud.soft_delete(self.db, comment=comment)
    
    def approve_comment(
        self, 
        comment_id: int,
        current_user: User,
        current_channel: Channel
    ) -> CommentResponse:
        """Approve a comment - requires admin or channel owner privileges"""
        comment = comment_crud.get(self.db, id=comment_id)
        if not comment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Comment not found"
            )
        
        # Check approval permissions
        if not self.auth_service.can_approve_comment(current_user, current_channel):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to approve comments"
            )
        
        comment = comment_crud.approve_comment(self.db, comment=comment)
        return self._to_response(comment)