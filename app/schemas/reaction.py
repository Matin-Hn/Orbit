from typing import Literal, Optional
from pydantic import BaseModel, Field


class ReactionBase(BaseModel):
    type: Literal["like", "dislike"] = Field(..., description="Type of reaction (like/dislike)")

class ReactionPayload(ReactionBase):
    pass
    
class ReactionCreate(ReactionBase):
    video_id: int

class ReactionUpdate(BaseModel):
    type: Optional[Literal["like", "dislike"]] = Field(None, description="New reaction type")

class ReactionResponse(BaseModel):
    video_public_id: str
    likes_count: int