import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, EmailStr, field_validator
from pydantic_settings import SettingsConfigDict



class PasswordValidationMixin:
    @field_validator('password', check_fields=False)
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        pattern = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&#])[A-Za-z\d@$!%*?&#]{8,32}$"
        
        if not re.match(pattern, v):
            raise ValueError(
                "Password must contain at least 8 characters, including "
                "uppercase, lowercase, number and special character."
            )
        return v

    @field_validator("confirm_password", check_fields=False)
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
    phone: Optional[str] = Field(default=None, min_length=11, max_length=11)
    avatar_url: Optional[str] = None
    
    @field_validator('phone')
    @classmethod
    def validate_iran_phone(cls, v):
        if v is not None:
            # Iranian mobile: starts with 09 and has 11 digits total
            if not re.match(r'^09[0-9]{9}$', v):
                raise ValueError('Invalid Iranian phone number. Must be 11 digits starting with 09')
        return v

class UserLogin(BaseModel):
    username: str
    password: str


class UserUpdate(UserBase, PasswordValidationMixin):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: str
    avatar_url: Optional[str] = None
    password: Optional[str] = Field(
        min_length=6, description="New password (optional)"
    )


class UserResponse(UserBase):
    id: int
    email: EmailStr
    phone: str | None
    avatar_url: Optional[str] = None

    model_config = SettingsConfigDict(from_attributes=True)


class UserInDBBase(UserBase):
    id: int
    password_hash: str
    phone: str
    avatar_url: Optional[str] = None
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

