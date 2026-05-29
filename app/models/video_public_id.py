from datetime import datetime, timezone 

from sqlalchemy import Column, BigInteger, ForeignKey, DateTime, String
from sqlalchemy.orm import relationship

from app.core.database import Base


class VideoPublicId(Base):
    """Maps a public-facing short ID to an internal video ID."""
    __tablename__ = "video_public_ids"

    public_id = Column(String(8), primary_key=True)
    internal_id = Column(BigInteger, ForeignKey("videos.id"), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    video = relationship("Video", back_populates="public_id", uselist=False)