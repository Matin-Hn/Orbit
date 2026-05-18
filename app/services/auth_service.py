from typing import Any
import uuid
import hashlib
import jwt
from jwt.exceptions import DecodeError,InvalidSignatureError, ExpiredSignatureError
from datetime import timedelta, datetime, timezone
from http.cookies import SimpleCookie
import logging


from fastapi import HTTPException, Request, status, Depends, WebSocket, WebSocketDisconnect

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User, UserRole
from app.models.channel import Channel
from app.api.deps import get_db
from app.core.database import SessionLocal


logger = logging.getLogger(__name__)

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


async def get_current_user_from_cookie_ws(websocket: WebSocket) -> User:
    """
    Authenticate WebSocket by extracting JWT from cookies.
    Works with browser's automatic cookie sending.
    """
    # Extract cookies from WebSocket headers
    cookie_header = websocket.headers.get("cookie", "")
    
    if not cookie_header:
        await websocket.close(code=4001, reason="No authentication cookie")
        raise WebSocketDisconnect(code=4001)
    
    # Parse cookies
    cookies = SimpleCookie()
    cookies.load(cookie_header)
    
    # Get your session token - adjust cookie name to match your app
    token = None
    for cookie_name in ["session", "access_token", "jwt"]:
        if cookie_name in cookies:
            token = cookies[cookie_name].value
            break
    
    if not token:
        await websocket.close(code=4001, reason="Authentication token not found")
        raise WebSocketDisconnect(code=4001)
    
    # Verify token and get user
    try:
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
        user_id = payload.get("sub")
        
        if not user_id:
            raise ValueError("No user_id in token")
        
        # Get user from database
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                await websocket.close(code=4001, reason="User not found")
                raise WebSocketDisconnect(code=4001)
            if not user.is_active:
                await websocket.close(code=4001, reason="Account disabled")
                raise WebSocketDisconnect(code=4001)
            return user
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"WebSocket auth failed: {e}")
        await websocket.close(code=4001, reason="Invalid authentication")
        raise WebSocketDisconnect(code=4001)