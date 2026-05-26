# app/crud/video.py
from typing import Optional
from sqlalchemy.orm import Session
from app.models.video import Video

class CRUDVideo:
    def __init__(self, model=Video):
        self.model = model

    def get(self, db: Session, id: int) -> Optional[Video]:
        """Get video by ID"""
        return db.query(self.model).filter(
            self.model.id == id,
            self.model.deleted_at.is_(None)
        ).first()
    
    def get_published(self, db: Session, id: int) -> Optional[Video]:
        """Get published video by ID"""
        return db.query(self.model).filter(
            self.model.id == id,
            self.model.deleted_at.is_(None),
            self.model.is_published == True
        ).first()
    
    def exists(self, db: Session, id: int) -> bool:
        """Check if video exists (simple existence check)"""
        return db.query(self.model.id).filter(
            self.model.id == id,
            self.model.deleted_at.is_(None)
        ).first() is not None

video = CRUDVideo(Video)