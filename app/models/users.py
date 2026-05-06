from sqlalchemy import (
     Column,
     Integer,
     String,
     Text,
     Boolean,
     DateTime,
     func,
     ForeignKey,
     BigInteger,
     
)
from pydantic import EmailStr

from core.database import Base


class users(Base):
    __tablename__: "users"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    username = Column(String(30), unique=True, index=True, nullable=False)
    email: EmailStr = Column(String(250), unique=True, index=True, nullable=False)
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
    updated_date = Column(DateTime, server_default=func.now(),
                           server_onupdate=func.now())
    
