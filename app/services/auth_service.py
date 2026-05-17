# services/auth_service.py
from typing import Any
import uuid
import hashlib
import jwt
from jwt.exceptions import DecodeError,InvalidSignatureError, ExpiredSignatureError
from datetime import timedelta, datetime, timezone

from fastapi import HTTPException, Request, status, Depends

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User, UserRole
from app.models.channel import Channel
from app.api.deps import get_db


def create_access_token(
        subject: str | Any,
        expires_delta: timedelta = timedelta(minutes=15)
) -> str:
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode = {
        "exp": expire, 
        "sub": str(subject),
        "type": "access"  # Helps identify token type
    }
    access_token = jwt.encode(
        to_encode, 
        settings.SECRET_KEY, 
        algorithm=settings.ALGORITHM
    )

    return access_token


def create_refresh_token(
        subject: str | Any,
        expires_delta: timedelta = timedelta(days=7)
) -> str:
    jti = str(uuid.uuid4())
    expire = datetime.now(timezone.utc) + expires_delta
    
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "type": "refresh",
        "jti": jti
    }
    return jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )


def decode_refresh_token(refresh_token: str) -> str:    
    # Decode and verify
    try:
        payload = jwt.decode(
            refresh_token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        user_id = payload.get("sub")
        return user_id
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid refresh token")
    


async def get_current_user_from_cookie(
    request: Request,
    db: Session = Depends(get_db)
) -> User:
    """Alternative: Extract JWT from cookie"""
    
    token = request.cookies.get("access_token")
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    # Same decoding logic as above
    try:
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
        user_id: int = int(payload.get("sub"))
        
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token, user_id is missing"
            )
        
        user = db.query(User).filter(User.id == user_id).first()
        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )
        return user
            
    except DecodeError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication error, decode failed")
    except InvalidSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication error, invalid signature")
    except ExpiredSignatureError:
        
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication error, token expired")        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Authentication error, {e}")


def require_admin(current_user: User = Depends(get_current_user_from_cookie)):
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user


def get_current_channel(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie)
) -> Channel:
    """Return the channel owned by the current user."""
    channel = db.query(Channel).filter(
        Channel.user_id == current_user.id,
        Channel.is_suspended == False
    ).first()
    if not channel:
        raise HTTPException(
            status_code=404,
            detail="Channel not found. Please create a channel first."
        )
    return channel