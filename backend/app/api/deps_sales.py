"""
Sales authentication dependencies (Epic C1+E).

Two kinds of "sales" exist in the system:

  1. Platform sales — a User row with role='sales' or is_superuser. Lives
     in the User table, JWT type 'access' (the legacy admin OAuth scheme).
     Can see leads across all customers.

  2. Customer sales — a CustomerUser row with role='sales' inside a
     Customer tenant. JWT type 'customer_sales' issued by auth.unified_login.
     Can only see leads belonging to its parent customer.

This module exposes a single `get_current_sales` dependency that resolves
either kind from the bearer token and returns a uniform SalesContext.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional
import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlmodel import Session

from app.core.config import settings
from app.core.db import get_session
from app.core.security import ALGORITHM, is_token_revoked
from app.models.customer_user import CustomerUser
from app.models.user import User


CUSTOMER_SALES_TOKEN_TYPE = "customer_sales"

# Shared scheme — the actual token URL is /auth/login (unified). The
# `auto_error=False` lets get_current_sales return a 401 with a more useful
# message than the OAuth2 default.
sales_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login",
    auto_error=False,
)


@dataclass
class SalesContext:
    """Uniform view over a logged-in sales identity.

    `kind` distinguishes 'platform' (User row, customer_id=None → no tenant
    scope) from 'customer' (CustomerUser row scoped to one customer_id).
    `user_id` is the row PK in whichever table; combine with `kind` to look
    up details.
    """
    kind: str            # 'platform' | 'customer'
    user_id: int
    email: str
    customer_id: Optional[int]   # None for platform sales
    role: str            # 'sales' or 'admin' (platform may be superuser)


def create_customer_sales_access_token(
    customer_user: CustomerUser,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Issue a customer_sales JWT for a CustomerUser login."""
    now = datetime.utcnow()
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = now + expires_delta
    payload: dict[str, Any] = {
        "exp": expire,
        "iat": int(now.timestamp()),
        "jti": str(uuid.uuid4()),
        "sub": customer_user.email,
        "type": CUSTOMER_SALES_TOKEN_TYPE,
        "customer_user_id": customer_user.id,
        "customer_id": customer_user.customer_id,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def _decode(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate sales credentials",
        )


def get_current_sales(
    token: Optional[str] = Depends(sales_oauth2),
    session: Session = Depends(get_session),
) -> SalesContext:
    """Resolve the current sales identity from a bearer token.

    Accepts:
      - customer_sales JWT  →  CustomerUser row
      - admin/access JWT    →  User row with role='sales' or is_superuser

    Rejects everything else with 403.
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication",
        )
    payload = _decode(token)

    jti = payload.get("jti")
    if jti and is_token_revoked(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
        )

    tok_type = payload.get("type")

    if tok_type == CUSTOMER_SALES_TOKEN_TYPE:
        cu_id = payload.get("customer_user_id")
        cu = session.get(CustomerUser, cu_id) if cu_id else None
        if not cu or not cu.enabled:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Sales user disabled or not found")
        return SalesContext(
            kind="customer",
            user_id=cu.id,
            email=cu.email,
            customer_id=cu.customer_id,
            role=cu.role,
        )

    # Platform path: admin access JWT (subject = User.username)
    if tok_type and tok_type != "access":
        # Legacy admin tokens have no explicit type field (older code), so
        # accept both None and 'access' as platform-side tokens.
        if tok_type != "access":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Not a sales token")

    from sqlmodel import select
    username = payload.get("sub")
    user = None
    if username:
        user = session.exec(
            select(User).where(User.username == username)
        ).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="User not found or inactive")
    if not (user.is_superuser or getattr(user, "role", None) == "sales"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Not a sales user")
    return SalesContext(
        kind="platform",
        user_id=user.id,
        email=getattr(user, "email", "") or user.username,
        customer_id=None,
        role="admin" if user.is_superuser else "sales",
    )
