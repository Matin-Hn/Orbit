from sqlalchemy import Column, Integer, BigInteger, String, Text, Boolean, ForeignKey, TIMESTAMP, CheckConstraint, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base

class Video(Base):
    __tablename__ = "videos"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    channel_id = Column(BigInteger, ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    thumbnail_url = Column(String(500), nullable=True)
    file_url = Column(String(500), nullable=False)
    visibility = Column(String(10), nullable=False, default="public")
    scheduled_at = Column(TIMESTAMP(timezone=True), nullable=True)
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    language = Column(String(50), nullable=False, default="en")
    license = Column(String(20), nullable=False, default="standard")
    allow_comments = Column(Boolean, nullable=False, default=True)
    is_made_for_kids = Column(Boolean, nullable=False, default=False)
    is_short = Column(Boolean, nullable=False, default=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    published_at = Column(TIMESTAMP(timezone=True), nullable=True)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    deleted_at = Column(TIMESTAMP(timezone=True), nullable=True)
    
    # Relationships
    channel = relationship("Channel", back_populates="videos")
    category = relationship("Category", back_populates="videos")
    
    # Table constraints
    __table_args__ = (
        CheckConstraint("duration_seconds > 0", name="check_duration_positive"),
        CheckConstraint("visibility IN ('public','unlisted','private','scheduled')", name="check_visibility"),
        CheckConstraint("license IN ('standard','cc')", name="check_license"),
        Index("idx_videos_channel_id", "channel_id"),
        Index("idx_videos_visibility_published", "visibility", "published_at"),
        Index("idx_videos_created_at", "created_at"),
        Index("idx_videos_deleted_at", "deleted_at"),
    )
    
    @property
    def is_published(self) -> bool:
        """Check if video is published (not deleted and published_at <= now)"""
        if self.deleted_at:
            return False
        if self.visibility == "scheduled" and self.scheduled_at:
            return self.scheduled_at <= datetime.utcnow()
        return self.visibility != "private"
    
    def __repr__(self):
        return f"<Video(id={self.id}, title={self.title}, channel_id={self.channel_id})>"