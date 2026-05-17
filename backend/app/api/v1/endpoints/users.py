from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from pydantic import BaseModel, Field
from app.core.db import get_session
from app.models.user import User, USER_ROLES, USER_ROLE_ADMIN, USER_ROLE_SALES
from app.api.deps import get_current_user, get_current_admin
from app.core.security import verify_password, get_password_hash

router = APIRouter()

# ========== Pydantic Schemas ==========

class UserRead(BaseModel):
    id: int
    username: str
    is_active: bool
    is_superuser: bool
    role: str

class PasswordChangeRequest(BaseModel):
    """修改密码请求"""
    current_password: str = Field(..., min_length=1, description="当前密码")
    new_password: str = Field(..., min_length=8, max_length=128, description="新密码(至少8位)")
    confirm_password: str = Field(..., min_length=8, description="确认新密码")

class PasswordChangeResponse(BaseModel):
    success: bool
    message: str


class UserCreateRequest(BaseModel):
    """admin 创建新用户（包含销售）"""
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=8, max_length=128)
    role: str = Field(default=USER_ROLE_SALES)
    is_active: bool = True


# ========== API Endpoints ==========

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
    users = session.exec(select(User).offset(skip).limit(limit)).all()
    return users


@router.post("/", response_model=UserRead)
def create_user(
    body: UserCreateRequest,
    current_user: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """
    admin 创建新用户（用于添加销售账号）。
    """
    if body.role not in USER_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"角色必须是 {sorted(USER_ROLES)} 之一",
        )

    existing = session.exec(
        select(User).where(User.username == body.username)
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="用户名已存在")

    new_user = User(
        username=body.username,
        hashed_password=get_password_hash(body.password),
        role=body.role,
        is_active=body.is_active,
        is_superuser=False,
    )
    session.add(new_user)
    session.commit()
    session.refresh(new_user)
    return new_user


@router.post("/change-password", response_model=PasswordChangeResponse)
def change_password(
    request: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    修改当前用户密码
    """
    user = current_user
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 验证新密码和确认密码一致
    if request.new_password != request.confirm_password:
        raise HTTPException(status_code=400, detail="新密码和确认密码不一致")
    
    # 验证当前密码
    if not verify_password(request.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="当前密码错误")
    
    # 检查新密码不能和旧密码相同
    if verify_password(request.new_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="新密码不能与当前密码相同")
    
    # 密码强度检查
    if len(request.new_password) < 8:
        raise HTTPException(status_code=400, detail="新密码长度至少为8位")
    
    has_upper = any(c.isupper() for c in request.new_password)
    has_lower = any(c.islower() for c in request.new_password)
    has_digit = any(c.isdigit() for c in request.new_password)
    
    if not (has_upper and has_lower and has_digit):
        raise HTTPException(
            status_code=400, 
            detail="密码必须包含大写字母、小写字母和数字"
        )
    
    # 更新密码
    user.hashed_password = get_password_hash(request.new_password)
    session.add(user)
    session.commit()
    
    return PasswordChangeResponse(success=True, message="密码修改成功")
