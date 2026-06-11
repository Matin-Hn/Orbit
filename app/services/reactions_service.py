from fastapi import HTTPException, status

from sqlalchemy.orm import Session

from app.models.user import User
from app.core.exceptions import ReactionNotFound, ReactionTypeMismatch
from app.schemas.reaction import ReactionCreate, ReactionUpdate
from app.crud.reaction import reaction as reaction_crud

class ReactionService:
    def __init__(self, db: Session):
        self.db = db

    def set_reaction(
            self,
            requesting_user_id: int,
            reaction_type:str,
            video_id: int
    ):
        # Check if user exist
        existing_db_reaction = reaction_crud.get_by_video_and_user(
            db=self.db, user_id=requesting_user_id, video_id=video_id
        )
        
        if not existing_db_reaction:
            obj_in = ReactionCreate(
                type=reaction_type,
                video_id=video_id
            )
            new_reaction = reaction_crud.create(self.db, obj_in, requesting_user_id)
            return {"status": "created", "type": reaction_type}

        # Check if user already reacted with same type 
        elif existing_db_reaction.type == reaction_type:
            return {"status": "unchanged", "type": reaction_type}
        
        else:
            obj_in = ReactionUpdate(
                type=reaction_type
            )
            reaction_crud.update(self.db, existing_db_reaction, obj_in)
            return {"status": "changed", "type": reaction_type}
        
    def delete_reaction(
            self,
            reaction_type: str,
            requesting_user_id: int,
            video_id: int
    ):
        existing = reaction_crud.get_by_video_and_user(
            db=self.db, user_id=requesting_user_id, video_id=video_id
        )
        if not existing:
            raise ReactionNotFound(f"No reaction for user={requesting_user_id} video={video_id}")
        elif existing.type != reaction_type:
            raise ReactionTypeMismatch(f"Expected {reaction_type}, found {existing.type}")
        reaction_crud.delete(self.db, existing)
        return {"message": "reaction deleted"}