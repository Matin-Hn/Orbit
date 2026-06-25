# app/services/comment_service.py
from typing import Optional, List
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.comment import comment as comment_crud
from app.crud.video import video as video_crud
from app.schemas.comment import CommentCreate, CommentUpdate, CommentResponse, CommentListResponse
from app.models.user import User
from app.models.channel import Channel
from app.models.video import Video
from app.services.authorization_service import AuthorizationService

class CommentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.auth_service = AuthorizationService(db)
    
    def _to_response(self, comment) -> CommentResponse:
        # Get username from the user relationship only if it is already present
        username = "User"
        # avoid attribute access that could trigger lazy loads; check __dict__ for loaded attributes
        cdict = getattr(comment, "__dict__", {})
        if 'user' in cdict and cdict.get('user') is not None:
            username = cdict['user'].username
        elif 'username' in cdict and cdict.get('username'):
            username = cdict['username']

        # prefer a pre-computed reply_count if present, otherwise only use loaded replies
        if 'reply_count' in cdict:
            reply_count = int(cdict.get('reply_count') or 0)
        elif 'replies' in cdict:
            replies_val = cdict.get('replies') or []
            reply_count = len(replies_val)
        else:
            reply_count = 0

        return CommentResponse(
            id=comment.id,
            user_id=comment.user_id,
            username=username,  # ADDED: Username from user relationship
            video_id=comment.video_id,
            parent_id=comment.parent_id,
            body=comment.body,
            is_pinned=comment.is_pinned,
            is_edited=comment.is_edited,
            is_approved=comment.is_approved,
            created_at=comment.created_at,
            updated_at=comment.updated_at,
            reply_count=reply_count
        )
    
    async def create_comment(
        self, 
        comment_data: CommentCreate, 
        current_user: User
    ) -> CommentResponse:
        """Create a new comment - requires authentication"""
        # Validate parent comment if replying
        video_existing = await video_crud.get(self.db, id=comment_data.video_id)
        if not video_existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video with id {comment_data.video_id} is not exist."
            )            
        if comment_data.parent_id:
            parent_comment = await comment_crud.get(self.db, id=comment_data.parent_id)
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
        
        comment = await comment_crud.create(
            self.db, 
            obj_in=comment_data, 
            user_id=current_user.id
        )
        
        return self._to_response(comment)
    
    async def get_comment(self, comment_id: int) -> CommentResponse:
        """Get a single comment - public access"""
        comment = await comment_crud.get(self.db, id=comment_id)
        if not comment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Comment not found"
            )
        
        return self._to_response(comment)
    
    async def get_video_comments(
        self, 
        video_id: int,
        sort_by: str,
        page: int = 1, 
        per_page: int = 20,
        current_user: Optional[User] = None
    ) -> CommentListResponse:
        """Get video comments - public access with optional approval filtering"""
        skip = (page - 1) * per_page
        comments, total = await comment_crud.get_by_video(
            self.db,
            video_id=video_id,
            skip=skip,
            limit=per_page,
            sort_by=sort_by
        )
        
        # Filter unapproved comments for non-privileged users
        if current_user:
            video = await video_crud.get(self.db, id=video_id)
            if video:
                is_privileged = self.auth_service.is_admin_or_channel_owner(current_user, video.channel)
            else:
                is_privileged = False
        else:
            is_privileged = False
        
        if not is_privileged:
            comments = [c for c in comments if c.is_approved]
            # Update total count for filtered results
            total = len(comments)
        
        comment_responses = [self._to_response(c) for c in comments]
        
        return CommentListResponse(
            total=total,
            comments=comment_responses,
            page=page,
            per_page=per_page
        )
    
    async def get_comment_replies(
        self, 
        comment_id: int, 
        page: int = 1, 
        per_page: int = 10,
        current_user: Optional[User] = None
    ) -> CommentListResponse:
        """Get comment replies - public access"""
        parent_comment = await comment_crud.get(self.db, id=comment_id)
        if not parent_comment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parent comment not found"
            )
        
        skip = (page - 1) * per_page
        replies, total = await comment_crud.get_replies(
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
    
    async def update_comment(
        self, 
        comment_id: int, 
        update_data: CommentUpdate,
        current_user: User
    ) -> CommentResponse:
        """Update comment - requires proper authorization"""
        comment = await comment_crud.get(self.db, id=comment_id)
        if not comment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Comment not found"
            )
        
        # Check modification permissions
        if not await self.auth_service.can_modify_comment(current_user, comment):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to modify this comment"
            )
        
        # Only channel owner or admin/superuser can pin comments
        if update_data.is_pinned is not None:
            if not await self.auth_service.can_pin_comment(current_user, comment):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have permission to pin/unpin this comment"
                )
        
        # Only channel owner or admin can approve comments
        if update_data.is_approved is not None:
            video = await video_crud.get(self.db, id=comment.video_id)
            video_channel = video.channel if video else None
            if not self.auth_service.can_approve_comment(current_user, video_channel):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have permission to approve this comment"
                )
        
        comment = await comment_crud.update(
            self.db,
            db_obj=comment,
            obj_in=update_data
        )
        
        return self._to_response(comment)
    
    async def delete_comment(
        self, 
        comment_id: int,
        current_user: User
    ) -> None:
        """Soft delete comment - requires proper authorization"""
        comment = await comment_crud.get(self.db, id=comment_id)
        if not comment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Comment not found"
            )
        
        # Check deletion permissions
        if not await self.auth_service.can_modify_comment(current_user, comment):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to delete this comment"
            )
        
        await comment_crud.soft_delete(self.db, comment=comment)
    
    async def approve_comment(
        self, 
        comment_id: int,
        current_user: User,
    ) -> CommentResponse:
        """Approve a comment - requires admin or channel owner privileges"""
        comment = await comment_crud.get(self.db, id=comment_id)
        if not comment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Comment not found"
            )
        
        # Check approval permissions
        video = await video_crud.get(self.db, id=comment.video_id)
        video_channel = video.channel if video else None
        if not self.auth_service.can_approve_comment(current_user, video_channel):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to approve comments"
            )
        
        comment = await comment_crud.approve_comment(self.db, comment=comment)
        return self._to_response(comment)