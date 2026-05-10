from typing import Optional

from sqlalchemy.orm import Session

from app.schemas.user import UserCreate
from app.models.user import User, UserRole
from app.core.security import verify_password, get_password_hash


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """Get user by username"""
    return db.query(User).filter(User.username == username).first()

def get_user_by_id(db: Session, user_id: str) -> Optional[User]:
    """Get user by username"""
    return db.query(User).filter(User.id == user_id).first()

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Get user by email"""
    return db.query(User).filter(User.email == email).first()

def create_user(db: Session, user:UserCreate):
    """Create new user"""
    db_user = User(**user)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def delete_user_from_db(db: Session, db_user: User):
    db.delete(db_user)
    db.commit()

# Dummy hash to use for timing attack prevention when user is not found
# This is an Argon2 hash of a random password, used to ensure constant-time comparison
DUMMY_HASH = "$argon2id$v=19$m=65536,t=3,p=4$MjQyZWE1MzBjYjJlZTI0Yw$YTU4NGM5ZTZmYjE2NzZlZjY0ZWY3ZGRkY2U2OWFjNjk"


def authenticate(db: Session, username: str, password: str):
    db_user = db.query(User).filter(User.username == username).first()
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
        db.commit()
        db.refresh(db_user)
    return db_user


def create_admin_user(db: Session, email: str, username: str, password: str, creator_admin_id: int = None):
    """Create a new admin user"""
    hashed_password = get_password_hash(password)
    
    admin_user = User(
        email=email,
        username=username,
        hashed_password=hashed_password,
        role=UserRole.ADMIN,
        created_by_admin_id=creator_admin_id
    )
    
    db.add(admin_user)
    db.commit()
    db.refresh(admin_user)
    return admin_user