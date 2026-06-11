from sqlalchemy import Column, BigInteger, Enum, TIMESTAMP, UniqueConstraint, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.core.database import Base


class ReactionType(str, enum.Enum):
    LIKE = "like"
    DISLIKE = "dislike"

class VideoReaction(Base):
    __tablename__ = "video_reactions"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    video_id = Column(BigInteger, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False)
    type = Column(Enum(ReactionType), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)

    video = relationship("Video", back_populates="reactions")
    user = relationship("User", back_populates="reactions")

    __table_args__ = (
        UniqueConstraint("user_id", "video_id", name="uq_user_video_reaction"),
        Index("ix_video_reactions_video_id", "video_id"),   # for count queries
        Index("ix_video_reactions_user_id", "user_id"),     # for user history queries
    )
