# app/crud/comment.py
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.models.comment import Comment
from app.schemas.comment import CommentCreate, CommentUpdate

class CRUDComment:
    def __init__(self, model=Comment):
        self.model = model

    def get(self, db: Session, id: int) -> Optional[Comment]:
        return db.query(self.model).filter(
            and_(
                self.model.id == id,
                self.model.deleted_at.is_(None)
            )
        ).first()

    def get_by_video(
        self, 
        db: Session, 
        *, 
        video_id: int,
        skip: int = 0,
        limit: int = 20
    ) -> Tuple[List[Comment], int]:
        query = db.query(self.model).filter(
            and_(
                self.model.video_id == video_id,
                self.model.deleted_at.is_(None),
                self.model.parent_id.is_(None)
            )
        )
        
        total = query.count()
        comments = query.order_by(
            self.model.is_pinned.desc(),
            self.model.created_at.desc()
        ).offset(skip).limit(limit).all()
        
        return comments, total
    
    def get_replies(
        self, 
        db: Session, 
        *, 
        parent_id: int,
        skip: int = 0,
        limit: int = 10
    ) -> Tuple[List[Comment], int]:
        query = db.query(self.model).filter(
            and_(
                self.model.parent_id == parent_id,
                self.model.deleted_at.is_(None)
            )
        )
        
        total = query.count()
        replies = query.order_by(self.model.created_at.asc())\
            .offset(skip).limit(limit).all()
        
        return replies, total
    
    def create(self, db: Session, *, obj_in: CommentCreate, user_id: int) -> Comment:
        db_obj = self.model(
            user_id=user_id,
            video_id=obj_in.video_id,
            body=obj_in.body,
            parent_id=obj_in.parent_id,
            is_approved=False  # New comments need approval by default
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def update(
        self,
        db: Session,
        *,
        db_obj: Comment,
        obj_in: CommentUpdate
    ) -> Comment:
        update_data = obj_in.dict(exclude_unset=True)
        
        if 'body' in update_data:
            db_obj.body = update_data['body']
            db_obj.is_edited = True
        
        if 'is_pinned' in update_data:
            db_obj.is_pinned = update_data['is_pinned']
        
        if 'is_approved' in update_data:
            db_obj.is_approved = update_data['is_approved']
        
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def soft_delete(self, db: Session, *, comment: Comment) -> Comment:
        comment.deleted_at = func.now()
        db.add(comment)
        db.commit()
        db.refresh(comment)
        return comment
    
    def approve_comment(self, db: Session, *, comment: Comment) -> Comment:
        comment.is_approved = True
        db.add(comment)
        db.commit()
        db.refresh(comment)
        return comment

comment = CRUDComment(Comment)