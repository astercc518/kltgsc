from typing import Generator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from pydantic import ValidationError
from sqlmodel import Session, select

from app.core.config import settings
from app.core.db import get_session
from app.core.security import ALGORITHM, is_token_revoked
from app.models.token import TokenPayload
from app.models.user import User, USER_ROLE_ADMIN, USER_ROLE_SALES

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token"
)


def _decode_token(token: str) -> TokenPayload:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        token_data = TokenPayload(**payload)
    except (JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )

    if token_data.jti and is_token_revoked(token_data.jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
        )

    if not token_data.sub:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid token subject",
        )
    return token_data


def get_current_user(
    token: str = Depends(reusable_oauth2),
    session: Session = Depends(get_session),
) -> User:
    """
    返回当前登录的 User 对象（多用户模式下按 username 查表）。
    """
    token_data = _decode_token(token)

    user = session.exec(
        select(User).where(User.username == token_data.sub)
    ).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not found",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive",
        )
    return user


def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    """要求当前用户是 admin（或 superuser）。"""
    if current_user.role != USER_ROLE_ADMIN and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return current_user


def get_current_sales_or_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """sales / admin / superuser 都可。其它角色拒绝。"""
    if (
        current_user.role not in {USER_ROLE_ADMIN, USER_ROLE_SALES}
        and not current_user.is_superuser
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sales or admin role required",
        )
    return current_user


# ── 向后兼容入口：旧代码 `current_user: str = Depends(get_current_user)` 仍然可用 ──
# 部分接口的 type hint 写的是 str（实际拿到的是 User），不会 runtime 报错，
# 但只要它们用到 `current_user`（被当作 username 字符串）的地方，必须改成
# `current_user.username`。详见 day-4 修补清单。

def get_current_username(
    current_user: User = Depends(get_current_user),
) -> str:
    """供仍按 username 字符串使用的旧调用点平滑迁移。"""
    return current_user.username
