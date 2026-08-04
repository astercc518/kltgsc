from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from sqlalchemy import update
from pydantic import BaseModel, Field
from app.core.db import get_session
from app.models.user import User, USER_ROLES, USER_ROLE_ADMIN, USER_ROLE_SALES
from app.models.lead import Lead
from app.models.subscription import Invoice
from app.api.deps import get_current_user, get_current_admin
from app.core.security import verify_password, get_password_hash

router = APIRouter()


def _validate_password_strength(pw: str) -> Optional[str]:
    """Return None if OK, else error message."""
    if len(pw) < 8:
        return "密码长度至少为8位"
    if not any(c.isupper() for c in pw):
        return "密码必须包含大写字母"
    if not any(c.islower() for c in pw):
        return "密码必须包含小写字母"
    if not any(c.isdigit() for c in pw):
        return "密码必须包含数字"
    return None


def _count_active_admins(session: Session, exclude_user_id: Optional[int] = None) -> int:
    """Count admin users that are active, optionally excluding one id."""
    stmt = select(User).where(
        User.role == USER_ROLE_ADMIN,
        User.is_active == True,  # noqa: E712
    )
    if exclude_user_id is not None:
        stmt = stmt.where(User.id != exclude_user_id)
    return len(session.exec(stmt).all())

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


class UserUpdateRequest(BaseModel):
    """admin 编辑用户（role / is_active）。username 不可改，密码走 reset-password。"""
    role: Optional[str] = None
    is_active: Optional[bool] = None


class AdminResetPasswordRequest(BaseModel):
    """admin 替别人重置密码（无需当前密码）。"""
    new_password: str = Field(..., min_length=8, max_length=128)


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
    current_user: User = Depends(get_current_admin),
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
    err = _validate_password_strength(request.new_password)
    if err:
        raise HTTPException(status_code=400, detail=err)

    # 更新密码
    user.hashed_password = get_password_hash(request.new_password)
    session.add(user)
    session.commit()

    return PasswordChangeResponse(success=True, message="密码修改成功")


@router.put("/{user_id}", response_model=UserRead)
def update_user(
    user_id: int,
    body: UserUpdateRequest,
    current_user: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """admin 编辑用户角色或启用状态。

    保护规则：
    - 不能修改自己的 role 或 is_active（防止把自己锁出 admin 角色）
    - 不能让最后一个 active admin 流失（降级 / 禁用）
    """
    target = session.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 防自残
    if target.id == current_user.id and (body.role is not None or body.is_active is not None):
        raise HTTPException(
            status_code=400,
            detail="不能修改自己的角色或启用状态（请使用其它 admin 账号操作）",
        )

    # 校验 role
    if body.role is not None and body.role not in USER_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"角色必须是 {sorted(USER_ROLES)} 之一",
        )

    # 计算变更后是否会导致最后一个 active admin 流失
    target_currently_admin = (target.role == USER_ROLE_ADMIN and target.is_active)
    new_role = body.role if body.role is not None else target.role
    new_active = body.is_active if body.is_active is not None else target.is_active
    target_after_admin = (new_role == USER_ROLE_ADMIN and new_active)

    if target_currently_admin and not target_after_admin:
        # 该用户即将从 active admin 变为非 admin / 禁用 — 检查池子里还有别人吗
        remaining = _count_active_admins(session, exclude_user_id=target.id)
        if remaining < 1:
            raise HTTPException(
                status_code=400,
                detail="至少需要保留 1 个 active admin",
            )

    if body.role is not None:
        target.role = body.role
    if body.is_active is not None:
        target.is_active = body.is_active

    session.add(target)
    session.commit()
    session.refresh(target)
    return target


@router.delete("/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """admin 真删除用户。

    先 NULL 掉外键引用（lead.assigned_to_user_id / invoice.paid_by_admin），
    再 DELETE。保护规则：
    - 不能删除自己
    - 不能删除最后一个 active admin
    """
    target = session.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")

    if target.id == current_user.id:
        raise HTTPException(status_code=400, detail="不能删除自己")

    # 删除后是否还有 active admin?
    if target.role == USER_ROLE_ADMIN and target.is_active:
        remaining = _count_active_admins(session, exclude_user_id=target.id)
        if remaining < 1:
            raise HTTPException(
                status_code=400,
                detail="至少需要保留 1 个 active admin",
            )

    # 先解除外键引用（保留历史业务数据但清空 FK）
    session.exec(
        update(Lead).where(Lead.assigned_to_user_id == user_id).values(assigned_to_user_id=None)
    )
    session.exec(
        update(Invoice).where(Invoice.paid_by_admin == user_id).values(paid_by_admin=None)
    )

    session.delete(target)
    session.commit()
    return None


@router.post("/{user_id}/reset-password", response_model=PasswordChangeResponse)
def admin_reset_password(
    user_id: int,
    body: AdminResetPasswordRequest,
    current_user: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """admin 替别人重置密码（无需提供当前密码）。

    密码强度校验复用 change-password 的规则。
    不记录密码明文到任何日志。
    """
    target = session.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")

    err = _validate_password_strength(body.new_password)
    if err:
        raise HTTPException(status_code=400, detail=err)

    target.hashed_password = get_password_hash(body.new_password)
    session.add(target)
    session.commit()
    return PasswordChangeResponse(
        success=True,
        message=f"已重置 {target.username} 的密码",
    )


# ── Phase F3: industry filter for platform sales ────────────────────────


class IndustryFilterRequest(BaseModel):
    industry_filter: list[str]


@router.patch("/{user_id}/industry-filter")
def set_industry_filter(
    user_id: int,
    body: IndustryFilterRequest,
    _admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """Set the per-user industry_filter for a platform sales account.
    Only meaningful when target.role='sales'. Stored as JSON array on
    User.industry_filter_json — empty list = see all internal-pool leads.
    """
    import json
    target = session.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="user not found")
    if target.role != "sales" and not target.is_superuser:
        raise HTTPException(status_code=400, detail="user is not a sales/admin")
    target.industry_filter_json = json.dumps(body.industry_filter or [])
    session.add(target)
    session.commit()
    return {
        "ok": True,
        "user_id": target.id,
        "username": target.username,
        "industry_filter": body.industry_filter,
    }


# ── Admin impersonation (login as another user) ──────────────────────────


@router.post("/{user_id}/impersonate")
def impersonate_user(
    user_id: int,
    admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """Issue an access token for the target user. Admin-only; useful for
    "log in as this sales rep to verify their inbox view".

    Returns the token + role + suggested redirect target. The frontend
    opens a new tab with the token in a URL fragment, which the SPA picks
    up and stores under the right localStorage key — admin's own session
    is left untouched.

    Audit-logged. Rejects: self, inactive target, superuser target.
    """
    from app.core.security import create_access_token, create_log
    target = session.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="user not found")
    if target.id == admin.id:
        raise HTTPException(status_code=400, detail="cannot impersonate self")
    if not target.is_active:
        raise HTTPException(status_code=400, detail="target user is inactive")
    if target.is_superuser:
        raise HTTPException(status_code=403, detail="cannot impersonate a superuser")

    token = create_access_token(target.username)

    # Where the frontend should drop them after handoff.
    if getattr(target, "role", "") == "sales":
        redirect_to = "/sales/inbox"
    else:
        redirect_to = "/dashboard"

    create_log(
        session, "admin_impersonate", admin.username,
        f"impersonated user_id={target.id} ({target.username}) role={target.role}",
        None, "success",
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "target_user_id": target.id,
        "target_username": target.username,
        "target_role": target.role,
        "redirect_to": redirect_to,
    }
