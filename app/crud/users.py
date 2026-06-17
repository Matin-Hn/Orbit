from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.user import UserCreate
from app.models.user import User, UserRole
from app.core.security import verify_password, get_password_hash


async def get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
    """Get user by username"""
    result = await db.execute(select(User).filter(User.username == username))
    return result.scalar_one_or_none()

async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
    """Get user by id"""
    result = await db.execute(select(User).filter(User.id == int(user_id)))
    return result.scalar_one_or_none()

async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """Get user by email"""
    result = await db.execute(select(User).filter(User.email == email))
    return result.scalar_one_or_none()

async def create_user(db: AsyncSession, user: UserCreate):
    """Create new user"""
    db_user = User(**user)
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

async def delete_user_from_db(db: AsyncSession, db_user: User):
    await db.delete(db_user)
    await db.commit()

# Dummy hash to use for timing attack prevention when user is not found
# This is an Argon2 hash of a random password, used to ensure constant-time comparison
DUMMY_HASH = "$argon2id$v=19$m=65536,t=3,p=4$MjQyZWE1MzBjYjJlZTI0Yw$YTU4NGM5ZTZmYjE2NzZlZjY0ZWY3ZGRkY2U2OWFjNjk"


async def authenticate(db: AsyncSession, username: str, password: str):
    result = await db.execute(select(User).filter(User.username == username))
    db_user = result.scalar_one_or_none()
    if not db_user:
        # Prevent timing attacks by running password verification even when user doesn't exist
        # This ensures the response time is similar whether or not the email exists
        verify_password(password, DUMMY_HASH)
        return None
    verified, updated_password_hash = verify_password(password, db_user.password_hash)
    if not verified:
        return None
    if updated_password_hash:
        db_user.password_hash = updated_password_hash
        db.add(db_user)
        await db.commit()
        await db.refresh(db_user)
    return db_user


async def create_admin_user(db: AsyncSession, email: str, username: str, password: str, creator_admin_id: int = None):
    """Create a new admin user"""
    hashed_password = get_password_hash(password)

    admin_user = User(
        email=email,
        username=username,
        password_hash=hashed_password,
        role=UserRole.ADMIN,
        created_by_admin_id=creator_admin_id
    )

    db.add(admin_user)
    await db.commit()
    await db.refresh(admin_user)
    return admin_user