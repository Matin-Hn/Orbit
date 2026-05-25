from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.models.comment import Comment

class CommentCRUD:
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, user_id: int, video_id: int, body: str, parent_id: Optional[int] = None) -> Comment:
        comment = Comment(
            user_id=user_id,
            video_id=video_id,
            body=body,
            parent_id=parent_id
        )
        self.db.add(comment)
        self.db.commit()
        self.db.refresh(comment)
        return comment
    
    def get_by_id(self, comment_id: int, include_deleted: bool = False) -> Optional[Comment]:
        query = self.db.query(Comment).filter(Comment.id == comment_id)
        if not include_deleted:
            query = query.filter(Comment.deleted_at.is_(None))
        return query.first()
    
    def get_by_video(
        self, 
        video_id: int, 
        page: int = 1, 
        per_page: int = 20,
        include_replies: bool = False
    ) -> Tuple[List[Comment], int]:
        # Base query for root comments (no parent_id)
        query = self.db.query(Comment).filter(
            and_(
                Comment.video_id == video_id,
                Comment.deleted_at.is_(None),
                Comment.parent_id.is_(None) if not include_replies else True
            )
        )
        
        # Get total count
        total = query.count()
        
        # Apply pagination and ordering
        comments = query.order_by(
            Comment.is_pinned.desc(),
            Comment.created_at.desc()
        ).offset((page - 1) * per_page).limit(per_page).all()
        
        return comments, total
    
    def get_replies(self, parent_id: int, page: int = 1, per_page: int = 10) -> Tuple[List[Comment], int]:
        query = self.db.query(Comment).filter(
            and_(
                Comment.parent_id == parent_id,
                Comment.deleted_at.is_(None)
            )
        )
        
        total = query.count()
        replies = query.order_by(Comment.created_at.asc())\
            .offset((page - 1) * per_page)\
            .limit(per_page)\
            .all()
        
        return replies, total
    
    def update(self, comment: Comment, update_data: dict) -> Comment:
        for key, value in update_data.items():
            if hasattr(comment, key) and value is not None:
                setattr(comment, key, value)
        
        if 'body' in update_data and update_data['body'] is not None:
            comment.is_edited = True
        
        self.db.commit()
        self.db.refresh(comment)
        return comment
    
    def soft_delete(self, comment: Comment) -> Comment:
        comment.deleted_at = func.now()
        self.db.commit()
        self.db.refresh(comment)
        return comment
    
    def get_comment_count_for_video(self, video_id: int) -> int:
        return self.db.query(Comment).filter(
            and_(
                Comment.video_id == video_id,
                Comment.deleted_at.is_(None)
            )
        ).count()