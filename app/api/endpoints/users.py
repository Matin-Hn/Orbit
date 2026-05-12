from typing import Any, Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.schemas.user import UserUpdate, UserPublic, UserListResponse
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
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
from app.crud.users_crud import (
    create_admin_user,
    get_user_by_id,
    delete_user_from_db
)

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


@router.get("/", dependencies=[Depends(require_admin)], response_model=UserListResponse)
async def retrieve_users(
    db: Session = Depends(get_db),
    search: Optional[str] = Query(None, description="Search by username (partial, case-insensitive)"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    role: Optional[str] = Query(None, description="Filter by role (exact match)"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """Retrieve all users with optimized filtering and pagination"""
    query = db.query(User)

    # Build filters efficiently
    filters = []
    
    # 1. Search on username (case-insensitive partial match)
    # With pg_trgm, ILIKE queries use the trigram index
    if search:
        # Method 1: Simple ILIKE (uses trigram index)
        filters.append(User.username.ilike(f"%{search}%"))
        
        # Method 2: Alternative using similarity for better results (optional)
        # query = query.filter(func.similarity(User.username, search) > 0.3)
        # query = query.order_by(func.similarity(User.username, search).desc())
    
    # 2. Filter by is_active
    if is_active is not None:
        filters.append(User.is_active == is_active)
    
    # 3. Filter by role
    if role:
        filters.append(User.role == role)
    
    # Apply all filters at once (Postgres optimizes this)
    if filters:
        query = query.filter(and_(*filters))
    
    # Get total count before pagination
    total_count = query.count()
    
    # Add ordering (important for consistent pagination)
    query = query.order_by(User.created_date.desc(), User.id.desc())
    
    # Apply pagination
    offset = (page - 1) * per_page
    users = query.offset(offset).limit(per_page).all()
    
    # Return with pagination metadata
    return {
        "users": users,
        "total": total_count,
        "page": page,
        "per_page": per_page,
        "total_pages": (total_count + per_page - 1) // per_page  # Ceiling division
    }


@router.get("/{user_id}", response_model=UserPublic)
async def retrieve_user(
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

@router.put("/{user_id}", response_model=UserPublic)
async def update_user(
    request: UserUpdate,
    current_user: User = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db)
):
    db_user = get_user_by_id(db, request.id)
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


@router.delete("/{user_id}", response_model=UserPublic)
async def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db)
):
    db_user = get_user_by_id(db, user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if check_admin_or_author(user_id, current_user):
        delete_user_from_db(user_id, db_user)

        raise HTTPException(status_code=status.HTTP_204_NO_CONTENT)


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