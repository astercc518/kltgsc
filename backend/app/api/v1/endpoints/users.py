from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.core.db import get_session
from app.models.user import User
from app.api.deps import get_current_user

router = APIRouter()

# Simple user management endpoints
# In a real app we might want Pydantic schemas for UserRead, UserCreate, etc.
# For now, we'll just return the User model (excluding hashed_password usually, but for simplicity here...)

# We should use a UserRead schema to avoid leaking password hashes
from pydantic import BaseModel

class UserRead(BaseModel):
    id: int
    username: str
    is_active: bool
    is_superuser: bool

@router.get("/me", response_model=UserRead)
def read_user_me(
    current_user: User = Depends(get_current_user),
):
    """
    Get current user.
    """
    return current_user

@router.get("/", response_model=List[UserRead])
def read_users(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    Retrieve users.
    """
    # Only superuser can list all users? Or anyone? Let's allow any logged in user for now
    users = session.exec(select(User).offset(skip).limit(limit)).all()
    return users
