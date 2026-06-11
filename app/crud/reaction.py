from typing import Optional
from sqlalchemy.orm import Session

from app.models.video_reaction import VideoReaction
from app.schemas.reaction import ReactionCreate, ReactionUpdate


class CRUDReaction:
    def __init__(self, model=VideoReaction):
        self.model = model

    def create(self, db: Session,obj_in: ReactionCreate , user_id: int):
        db_obj = VideoReaction(
            user_id=user_id,
            type=obj_in.type,
            video_id=obj_in.video_id
        )
        db.add(db_obj)
        db.flush()
        db.refresh(db_obj)
        return db_obj
    
    def get_by_video_and_user(self, db: Session, user_id: int, video_id: int) -> Optional[VideoReaction]:
        return db.query(self.model).filter(
            self.model.user_id == user_id,
            self.model.video_id == video_id
        ).first()
    
    def update(
            self,
            db: Session,
            db_obj: VideoReaction,
            obj_in: ReactionUpdate
    ) -> VideoReaction:
        # db_obj = db.query
        update_data = obj_in.model_dump(exclude_unset=True)
        
        for field, value in update_data.items():
            setattr(db_obj, field, value) 
        
        db.flush()
        db.refresh(db_obj)
        return db_obj
    
    def delete(
            self,
            db: Session,
            db_obj: VideoReaction
    ):
        db.delete(db_obj)
        db.commit()
        

reaction = CRUDReaction(VideoReaction)
    