from typing import Any
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from app.schemas.user import UserUpdate, UserPublic

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    Response,
    Request
)
from fastapi.responses import JSONResponse

from app.models.user import User
from app.api.deps import get_db, check_admin_or_author
from app.services.auth_service import (
    get_current_user_from_cookie,
    require_admin
)
from app.crud.users_crud import create_admin_user, get_user_by_id

router = APIRouter(
    prefix="/users",
    tags=["users"]
)

@router.get("/me", response_model=UserPublic)
async def get_current_user_info(
    current_user: User = Depends(get_current_user_from_cookie)
) -> Any:
    """
    Get current authenticated user's information.
    
    Returns:
        UserMeResponse: User details including profile, preferences, and metadata
        
    Raises:
        401: If token is missing or invalid
        403: If user account is disabled
    """
    return current_user


@router.get("/")
def retrieve_users(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Retrieve all users"""
    return db.query(User).all()


@router.get("/{user_id}", response_model=UserPublic)
def retrieve_user(
    user_id: int,
    current_user: User = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db)
):
    """Retrieve single user"""
    db_user = get_user_by_id(db, user_id)
    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )
    if check_admin_or_author(user_id, current_user):
        return db_user

@router.put("/{user_id}")
def update_user(
    request: UserUpdate,
    current_user: User = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db)
):
    db_user = db.query(User).filter(User.id == request.id).one_or_none()
    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )
    if check_admin_or_author(request.id, current_user):
        request_json = request.model_dump(exclude_unset=True)
        for key, value in request_json.items():
            setattr(db_user, key, value)
        db_user.updated_date = datetime.now(timezone.utc).replace(microsecond=0, tzinfo=None)
        db.commit()
        db.refresh(db_user)
        return db_user


@router.post(
        "/create-admin",
        description="Development"
)
async def create_new_admin(
    email: str,
    username: str,
    password: str,
    admin: User = Depends(get_current_user_from_cookie),  # -- TODO -- it should be change to admin in prod
    db: Session = Depends(get_db)
):
    """Create a new admin user (only existing admins)"""
    
    # Check if user already exists
    existing_user = db.query(User).filter(
        (User.email == email) | (User.username == username)
    ).first()
    
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists")
    
    # Create new admin
    new_admin = create_admin_user(
        db=db,
        email=email,
        username=username,
        password=password,
        creator_admin_id=admin.id
    )
    
    return {
        "message": "Admin user created successfully",
        "user": {
            "id": new_admin.id,
            "email": new_admin.email,
            "username": new_admin.username,
            "role": new_admin.role
        }
    }