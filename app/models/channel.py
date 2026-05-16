from sqlalchemy import Column, Integer, BigInteger, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base  


class Channel(Base):
    __tablename__ = "channels"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    name = Column(String(100), nullable=False, unique=True)
    handle = Column(String(30), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    avatar_url = Column(String(500), nullable=True)
    banner_url = Column(String(500), nullable=True)
    website = Column(String(500), nullable=True)
    contact_email = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    is_suspended = Column(Boolean, default=False)
    verified_badge = Column(Boolean, default=False)

    # Relationships
    user = relationship("User", back_populates="channel")
    videos = relationship("Video", back_populates="channel")

    def __repr__(self):
        return f"<Channel(id={self.id}, handle='{self.handle}', name='{self.name}')>"