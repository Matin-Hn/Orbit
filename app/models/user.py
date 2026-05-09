from sqlalchemy import (
     Column,
     String,
     Boolean,
     DateTime,
     func,
     Integer
)

from app.core.database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(30), unique=True, index=True, nullable=False)
    email = Column(String(250), unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False) 
    phone = Column(String(20), unique=True)
    avatar_url = Column(String(500))
    last_login = Column(DateTime)
    is_verified = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    two_factor_enables = Column(Boolean, default=False)
    role = Column(String(20), default="user")
    language = Column(String(10), default="en")
    theme = Column(String(10), default="dark")
    created_date = Column(DateTime, server_default=func.now())
    updated_date = Column(DateTime, server_default=func.now(),server_onupdate=func.now())

