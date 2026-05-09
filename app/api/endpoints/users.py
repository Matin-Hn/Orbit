from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

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
from ...api.deps import get_db


router = APIRouter(
    tags=["users"]
)

@router.get("/users")
def retrieve_users(
    db: Session = Depends(get_db)
):
    """Retrieve all users"""
    return db.query(User).all()


