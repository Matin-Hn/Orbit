import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, EmailStr, field_validator
from pydantic_settings import SettingsConfigDict



class PasswordValidationMixin:
    @field_validator('password')
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        pattern = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&#])[A-Za-z\d@$!%*?&#]{8,32}$"
        
        if not re.match(pattern, v):
            raise ValueError(
                "Password must contain at least 8 characters, including "
                "uppercase, lowercase, number and special character."
            )
        return v

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v, info):
        password = info.data.get("password")
        if password is None:
            return v
        if v != password:
            raise ValueError("Password confirmation must match the password")
        return v


class UserBase(BaseModel):
    username: str
    email: EmailStr


class UserCreate(UserBase, PasswordValidationMixin):
    password: str = Field(...)
    confirm_password: str = Field(description="Confirm password")
    phone: str
    avatar_url = str


class UserLogin(BaseModel):
    username: str
    email: str
    password: str


class UserUpdate(UserBase, PasswordValidationMixin):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: str
    avatar_url = str
    password: Optional[str] = Field(
        min_length=6, description="New password (optional)"
    )


class UserResponse(UserBase):
    id: int
    is_active: bool
    created_date: datetime
    updated_date: datetime

    model_config = SettingsConfigDict(from_attributes=True)


class UserInDBBase(UserBase):
    id: int
    password_hash: str
    phone: str
    avatar_url: str
    last_login: datetime
    is_verified: bool
    is_active: bool
    two_factor_enables: bool
    role: str
    language: str
    theme: str 
    created_date: datetime
    updated_date: datetime

    model_config = SettingsConfigDict(from_attributes=True)


class UserToken(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str


class UserTokenData(BaseModel):
    user_id: Optional[int] = None
    username: Optional[str] = None


class UserRefreshToken(BaseModel):
    refresh: str = Field(..., description="refresh token of the user")
