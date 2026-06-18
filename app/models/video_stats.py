from sqlalchemy import Column, BigInteger, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class VideoStats(Base):
    __tablename__ = "video_stats"

    video_id = Column(
        BigInteger, 
        ForeignKey("videos.id", ondelete="CASCADE"), 
        primary_key=True
    )
    views_count = Column(BigInteger, default=0)
    likes_count = Column(BigInteger, default=0)
    dislikes_count = Column(BigInteger, default=0)
    comments_count = Column(BigInteger, default=0)
    # shares_count = Column(BigInteger, default=0) # TODO: Later
    # saves_count = Column(BigInteger, default=0)

    video = relationship("Video", back_populates="stats")