from fastapi import HTTPException, status

from app.crud.comment import CommentCRUD
from app.schemas.comment import (
    CommentCreate, 
    CommentUpdate, 
    CommentResponse, 
    CommentListResponse
)
from app.models.comment import Comment

class CommentService:
    def __init__(self, comment_repo: CommentCRUD):
        self.comment_repo = comment_repo
    
    def _to_response(self, comment: Comment, reply_count: int = 0) -> CommentResponse:
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
            reply_count=reply_count
        )
    
    def create_comment(self, comment_data: CommentCreate) -> CommentResponse:
        # Validate parent comment if provided
        if comment_data.parent_id:
            parent_comment = self.comment_repo.get_by_id(comment_data.parent_id)
            if not parent_comment:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Parent comment not found"
                )
            # Ensure reply is to a root comment, not nested
            if parent_comment.parent_id is not None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot reply to a reply. Only one level of nesting allowed."
                )
        
        comment = self.comment_repo.create(
            user_id=comment_data.user_id,
            video_id=comment_data.video_id,
            body=comment_data.body,
            parent_id=comment_data.parent_id
        )
        
        return self._to_response(comment)
    
    def get_comment(self, comment_id: int) -> CommentResponse:
        comment = self.comment_repo.get_by_id(comment_id)
        if not comment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Comment not found"
            )
        
        reply_count = self.comment_repo.get_comment_count_for_video(comment.video_id)
        return self._to_response(comment, reply_count)
    
    def get_video_comments(
        self, 
        video_id: int, 
        page: int = 1, 
        per_page: int = 20
    ) -> CommentListResponse:
        comments, total = self.comment_repo.get_by_video(
            video_id=video_id,
            page=page,
            per_page=per_page
        )
        
        comment_responses = []
        for comment in comments:
            reply_count = len(comment.replies) if comment.replies else 0
            comment_responses.append(self._to_response(comment, reply_count))
        
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
        per_page: int = 10
    ) -> CommentListResponse:
        # Verify parent comment exists
        parent_comment = self.comment_repo.get_by_id(comment_id)
        if not parent_comment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parent comment not found"
            )
        
        replies, total = self.comment_repo.get_replies(
            parent_id=comment_id,
            page=page,
            per_page=per_page
        )
        
        reply_responses = [self._to_response(reply) for reply in replies]
        
        return CommentListResponse(
            total=total,
            comments=reply_responses,
            page=page,
            per_page=per_page
        )
    
    def update_comment(self, comment_id: int, user_id: int, update_data: CommentUpdate) -> CommentResponse:
        comment = self.comment_repo.get_by_id(comment_id)
        if not comment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Comment not found"
            )
        
        # Authorization check - only comment owner can update body
        if update_data.body and comment.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only edit your own comments"
            )
        
        # Only moderators/admins can update approval and pin status
        if (update_data.is_approved is not None or update_data.is_pinned is not None):
            # Add your authorization logic here for moderators
            pass
        
        update_dict = update_data.dict(exclude_unset=True)
        comment = self.comment_repo.update(comment, update_dict)
        
        return self._to_response(comment)
    
    def delete_comment(self, comment_id: int, user_id: int):
        comment = self.comment_repo.get_by_id(comment_id)
        if not comment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Comment not found"
            )
        
        # Authorization check
        if comment.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only delete your own comments"
            )
        
        self.comment_repo.soft_delete(comment)