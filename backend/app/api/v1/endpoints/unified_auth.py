"""
Unified login endpoint.

Single SPA login page calls this endpoint instead of the role-specific
`/login/access-token` (admin) or `/customer/login` (customer). The response
tells the frontend which token storage key to use and where to redirect.

Resolution rule:
  - identifier contains '@'  → look up Customer.email (customer JWT)
  - otherwise                → look up User.username  (admin JWT)

Admin accounts with 2FA enabled fall back to the legacy /login route (which
already handles the TOTP exchange).
"""
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlmodel import Session, select

from app.api.deps_customer import create_customer_access_token
from app.core import security
from app.core.db import get_session
from app.models.customer import Customer
from app.models.user import User


router = APIRouter()


class UnifiedLoginRequest(BaseModel):
    identifier: str  # email for customers, username for admin/sales
    password: str


class UnifiedLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str  # 'customer' | 'admin' | 'sales'
    redirect_to: str  # SPA path the frontend should navigate to


@router.post("/login", response_model=UnifiedLoginResponse)
def unified_login(
    payload: UnifiedLoginRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> Any:
    ip = request.client.host if request.client else None
    ident = (payload.identifier or "").strip()
    pwd = payload.password or ""

    if not ident or not pwd:
        raise HTTPException(status_code=400, detail="Incorrect identifier or password")

    # ── Customer path ──────────────────────────────────────────────────
    if "@" in ident:
        email = ident.lower()
        customer = session.exec(
            select(Customer).where(Customer.email == email)
        ).first()
        if customer and security.verify_password(pwd, customer.hashed_password):
            customer.last_login_at = datetime.utcnow()
            session.add(customer)
            session.commit()
            session.refresh(customer)
            security.create_log(
                session, "unified_login", customer.email,
                f"customer id={customer.id}", ip, "success",
            )
            return UnifiedLoginResponse(
                access_token=create_customer_access_token(customer),
                role="customer",
                redirect_to="/portal/dashboard",
            )
        security.create_log(
            session, "unified_login", email, "customer invalid", ip, "failed",
        )
        raise HTTPException(status_code=400, detail="Incorrect identifier or password")

    # ── Admin / sales path ─────────────────────────────────────────────
    user = session.exec(select(User).where(User.username == ident)).first()
    if not user or not user.is_active:
        security.create_log(
            session, "unified_login", ident, "user not found/inactive", ip, "failed",
        )
        raise HTTPException(status_code=400, detail="Incorrect identifier or password")

    if not security.verify_password(pwd, user.hashed_password):
        security.create_log(
            session, "unified_login", user.username, "bad password", ip, "failed",
        )
        raise HTTPException(status_code=400, detail="Incorrect identifier or password")

    if getattr(user, "totp_enabled", False):
        # 2FA accounts must use the legacy /login/access-token + verify flow.
        raise HTTPException(
            status_code=400,
            detail="2FA enabled — please use the legacy /login page",
        )

    security.create_log(
        session, "unified_login", user.username,
        f"user id={user.id}", ip, "success",
    )
    role = "admin" if user.is_superuser else (getattr(user, "role", "sales") or "sales")
    return UnifiedLoginResponse(
        access_token=security.create_access_token(user.username),
        role=role,
        redirect_to="/dashboard" if role == "admin" else "/inbox",
    )
