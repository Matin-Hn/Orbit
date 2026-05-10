from fastapi import HTTPException, status

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
    if current_user.role == UserRole.ADMIN:
        return True
    
    # Check if user is the author
    if current_user.id != object_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You don't have permission to access this {resource_type}"
        )
    
    return True
