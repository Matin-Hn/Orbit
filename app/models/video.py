import enum
from sqlalchemy import Column, Integer, BigInteger, String, Text, Boolean, ForeignKey, TIMESTAMP, CheckConstraint, Index, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from app.core.database import Base


class VideoStatus(str, enum.Enum):  # TODO: change the keys to uppercase
    uploading = "uploading"
    processing = "processing"
    ready = "ready"
    failed = "failed"

class VideoVisibility(str, enum.Enum):
    PUBLIC = "public"
    UNLISTED = "unlisted"
    PRIVATE = "private"
    SCHEDULED = "scheduled"


class Video(Base):
    __tablename__ = "videos"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    channel_id = Column(BigInteger, ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    thumbnail_url = Column(String(500), nullable=True)

    # New columns for the async flow
    file_url = Column(String(500), nullable=False)
    original_filename = Column(String(255), nullable=True)
    file_size = Column(BigInteger, nullable=True)          # bytes
    mime_type = Column(String(100), nullable=True)
    original_key = Column(String(500), nullable=False)     # S3 key of uploaded file
    
    hls_manifest_url = Column(String(500), nullable=True)  # URL to master.m3u8
    poster_url = Column(String(500), nullable=True)        # generated poster image
    processing_error = Column(Text, nullable=True)

    # columns for sprite image
    sprite_url = Column(String(500), nullable=True)      # URL to sprite image (e.g., sprites.jpg)
    sprite_vtt_url = Column(String(500), nullable=True)  # URL to WebVTT file for sprite mapping
    sprite_tile_width = Column(Integer, nullable=True)   # width of each tile in pixels
    sprite_tile_height = Column(Integer, nullable=True)  # height of each tile in pixels
    sprite_columns = Column(Integer, nullable=True)      # number of columns in sprite grid
    sprite_rows = Column(Integer, nullable=True)         # number of rows in sprite grid


    status = Column(
        Enum(VideoStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False
    )
    visibility = Column(
        Enum(VideoVisibility, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=VideoVisibility.PUBLIC
    )
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
    channel = relationship("Channel", back_populates="videos", uselist=False)
    category = relationship("Category", back_populates="videos")
    comments = relationship("Comment", back_populates="video", cascade="all, delete-orphan")
    public_id = relationship("VideoPublicId", back_populates="video", uselist=False)
    stats = relationship("VideoStats", back_populates="video", uselist=False)
    reactions = relationship("VideoReaction", back_populates="video")

    
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
        if self.deleted_at:
            return False
        if self.visibility == VideoVisibility.SCHEDULED and self.scheduled_at:
            return self.scheduled_at <= datetime.now(timezone.utc)  # fixed
        return self.visibility != VideoVisibility.PRIVATE
    
    @property
    def public_id_str(self) -> str | None:
        return self.public_id.public_id if self.public_id else None
    
    def __repr__(self):
        return f"<Video(id={self.id}, title={self.title}, channel_id={self.channel_id})>"