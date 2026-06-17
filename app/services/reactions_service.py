from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ReactionNotFound, ReactionTypeMismatch
from app.schemas.reaction import ReactionCreate, ReactionUpdate
from app.crud.reaction import reaction as reaction_crud


class ReactionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def set_reaction(self, requesting_user_id: int, reaction_type: str, video_id: int):
        existing_db_reaction = await reaction_crud.get_by_video_and_user(
            db=self.db, user_id=requesting_user_id, video_id=video_id
        )

        if not existing_db_reaction:
            obj_in = ReactionCreate(type=reaction_type, video_id=video_id)
            await reaction_crud.create(self.db, obj_in, requesting_user_id)  # ← was missing await
            return {"status": "created", "type": reaction_type}

        elif existing_db_reaction.type == reaction_type:
            return {"status": "unchanged", "type": reaction_type}

        else:
            obj_in = ReactionUpdate(type=reaction_type)
            await reaction_crud.update(self.db, existing_db_reaction, obj_in)  # ← was missing await
            return {"status": "changed", "type": reaction_type}

    async def delete_reaction(  # ← was missing async
            self, reaction_type: str, requesting_user_id: int, video_id: int
    ):
        existing = await reaction_crud.get_by_video_and_user(  # ← was missing await
            db=self.db, user_id=requesting_user_id, video_id=video_id
        )
        if not existing:
            raise ReactionNotFound(f"No reaction for user={requesting_user_id} video={video_id}")
        elif existing.type != reaction_type:
            raise ReactionTypeMismatch(f"Expected {reaction_type}, found {existing.type}")
        await reaction_crud.delete(self.db, existing)  # ← was missing await
        return {"message": "reaction deleted"}