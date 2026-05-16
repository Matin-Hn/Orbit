from fastapi import HTTPException

from app.models.user import User, UserRole
from app.core.database import SessionLocal


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_admin_or_author(
    object_id: int,
    current_user: User,
    resource_type: str = "resource"  # For better error messages
) -> bool:
    """
    Check if user is admin or the author of a resource.
    
    Args:
        object_id: ID of the resource being accessed
        current_user: Currently authenticated user
        resource_type: Type of resource for error messages
        
    Returns:
        True if authorized
        
    Raises:
        HTTPException: 403 if user is not authorized
    """
    # Admin has full access
    is_admin = current_user.role == UserRole.ADMIN
    is_self = current_user.id == object_id
    
    # Authorization
    if not (is_admin or is_self):
        raise HTTPException(status_code=403, detail=f"You have not access to this {resource_type}")
    return is_admin, is_self


