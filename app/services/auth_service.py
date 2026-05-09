# services/auth_service.py
from typing import Any
import uuid
import hashlib
import jwt
from datetime import timedelta, datetime, timezone

from fastapi import HTTPException, Response

from sqlalchemy.orm import Session

from app.core.config import settings


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