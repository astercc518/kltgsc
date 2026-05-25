"""
Authentication endpoints — all auth in one place.

Three router objects are exported so the mount path / OAuth2 token URLs stay
identical to the previous file split (deps.py and deps_customer.py bind the
admin and customer OAuth2 schemes to specific URLs that must not move):

    admin_router       (mounted with no prefix)
        POST /login/access-token   admin OAuth2 form login (+ optional 2FA)
        POST /logout               revoke current admin JWT
        POST /auth/setup-2fa       generate TOTP secret for current admin
        POST /auth/verify-2fa      verify TOTP code and activate 2FA

    customer_router    (mounted with prefix /customer)
        POST /customer/register    create a new customer account
        POST /customer/login       customer email+password → customer JWT
                                   (legacy; the SPA now uses /auth/login.
                                   Kept because deps_customer.OAuth2 scheme
                                   tokenUrl points here, and smoke tests
                                   still call it directly.)
        GET  /customer/me          introspect the authenticated customer

    unified_router     (mounted with prefix /auth)
        POST /auth/login           single SPA entry — identifier may be
                                   email (→ customer JWT) or username
                                   (→ admin JWT). 2FA admins fall back to
                                   the legacy /login/access-token route.
"""
from datetime import timedelta, datetime
from typing import Any

import pyotp
import redis
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from jose import jwt, JWTError
from pydantic import BaseModel
from sqlmodel import Session, select

from app.api.deps import get_current_user
from app.api.deps_customer import (
    create_customer_access_token,
    get_current_customer,
)
from app.core import security
from app.core.config import settings
from app.core.db import get_session
from app.core.security import ALGORITHM, revoke_token
from app.models.customer import (
    Customer,
    CustomerCreate,
    CustomerRead,
    STATUS_PENDING,
)
from app.models.token import Token, TokenPayload
from app.models.user import User


# Routers --------------------------------------------------------------------

admin_router = APIRouter()
customer_router = APIRouter()
unified_router = APIRouter()


# Shared infra ---------------------------------------------------------------

_redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

# OAuth2 scheme bound to the legacy admin token URL — used by /logout to
# extract the raw bearer token for revocation. Don't move this URL.
_admin_oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token"
)


# Schemas --------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str
    password: str
    totp_code: str | None = None


class TOTPVerify(BaseModel):
    code: str


class Setup2FAResponse(BaseModel):
    secret: str
    provisioning_uri: str
    message: str


class Verify2FAResponse(BaseModel):
    message: str


class LogoutResponse(BaseModel):
    message: str


class CustomerToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
    customer: CustomerRead


class CustomerLoginRequest(BaseModel):
    email: str
    password: str


class UnifiedLoginRequest(BaseModel):
    identifier: str  # email for customers, username for admin/sales
    password: str


class UnifiedLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str  # 'customer' | 'admin' | 'sales'
    redirect_to: str


# ============================================================================
# Admin auth — OAuth2 + 2FA
# ============================================================================

@admin_router.post("/login/access-token", response_model=Token)
def login_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests.

    If the user has 2FA enabled, the client must pass the TOTP code either
    appended to the password as ``password|123456`` or in the ``client_secret``
    OAuth2 form field.
    """
    ip = request.client.host
    key = f"login_attempts:{ip}"
    attempts = _redis_client.get(key)
    if attempts and int(attempts) > 5:
        security.create_log(
            session, "login", form_data.username,
            "Too many attempts", ip, "failed",
        )
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Try again later.",
        )

    raw_password = form_data.password
    totp_code: str | None = None
    if "|" in raw_password:
        raw_password, totp_code = raw_password.rsplit("|", 1)
    if not totp_code and form_data.client_secret:
        totp_code = form_data.client_secret

    user = session.exec(
        select(User).where(User.username == form_data.username)
    ).first()

    if not user or not security.verify_password(raw_password, user.hashed_password):
        _redis_client.incr(key)
        _redis_client.expire(key, 900)
        security.create_log(
            session, "login", form_data.username,
            "Incorrect credentials", ip, "failed",
        )
        raise HTTPException(
            status_code=400,
            detail="Incorrect email or password",
        )

    if user.totp_enabled and user.totp_secret:
        if not totp_code:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="2FA code required",
            )
        totp = pyotp.TOTP(user.totp_secret)
        if not totp.verify(totp_code, valid_window=1):
            _redis_client.incr(key)
            _redis_client.expire(key, 900)
            security.create_log(
                session, "login", user.username,
                "Invalid 2FA code", ip, "failed",
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid 2FA code",
            )

    _redis_client.delete(key)
    security.create_log(
        session, "login", user.username, "Login successful", ip, "success",
    )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return {
        "access_token": security.create_access_token(
            subject=user.username, expires_delta=access_token_expires,
        ),
        "token_type": "bearer",
    }


@admin_router.post("/logout", response_model=LogoutResponse)
def logout(
    token: str = Depends(_admin_oauth2_scheme),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Revoke the current admin JWT so it can no longer be used."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        token_data = TokenPayload(**payload)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )

    if not token_data.jti:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token does not contain a jti claim",
        )

    now_ts = int(datetime.utcnow().timestamp())
    exp_ts = int(payload.get("exp", now_ts))
    remaining_ttl = max(exp_ts - now_ts, 1)

    revoke_token(token_data.jti, remaining_ttl)
    return {"message": "Successfully logged out"}


@admin_router.post("/auth/setup-2fa", response_model=Setup2FAResponse)
def setup_2fa(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Generate a TOTP secret for the authenticated admin (not yet activated)."""
    secret = pyotp.random_base32()

    current_user.totp_secret = secret
    current_user.totp_enabled = False
    session.add(current_user)
    session.commit()

    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(
        name=current_user.username,
        issuer_name=settings.PROJECT_NAME,
    )

    return {
        "secret": secret,
        "provisioning_uri": provisioning_uri,
        "message": "Scan the QR code with your authenticator app, then verify with /auth/verify-2fa",
    }


@admin_router.post("/auth/verify-2fa", response_model=Verify2FAResponse)
def verify_2fa(
    data: TOTPVerify,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Verify a TOTP code and activate 2FA for the user."""
    if not current_user.totp_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA has not been set up. Call /auth/setup-2fa first.",
        )

    totp = pyotp.TOTP(current_user.totp_secret)
    if not totp.verify(data.code, valid_window=1):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid TOTP code",
        )

    current_user.totp_enabled = True
    session.add(current_user)
    session.commit()
    return {"message": "2FA has been activated successfully"}


# ============================================================================
# Customer auth — register / legacy login / me
# ============================================================================

@customer_router.post("/register", response_model=CustomerToken, status_code=201)
def register_customer(
    payload: CustomerCreate,
    request: Request,
    session: Session = Depends(get_session),
) -> Any:
    """Create a new customer account (status=pending, no plan yet)."""
    existing = session.exec(
        select(Customer).where(Customer.email == payload.email.lower())
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    if len(payload.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters",
        )

    customer = Customer(
        email=payload.email.lower(),
        hashed_password=security.get_password_hash(payload.password),
        name=payload.name,
        company=payload.company,
        industry=payload.industry,
        status=STATUS_PENDING,
    )
    session.add(customer)
    session.commit()
    session.refresh(customer)

    security.create_log(
        session, "customer_register", customer.email,
        f"id={customer.id}", request.client.host if request.client else None,
        "success",
    )

    # ── Landing trial grant (PR5) ──────────────────────────────────────
    # If the registration carries `ref=landing`, credit the wallet with
    # a fixed $20 USDT-equivalent. The amount is SERVER-SIDE FIXED — we
    # don't read it from the payload to prevent trivial inflation. The
    # idempotency key is anchored to customer.id so re-running with the
    # same ref can't double-credit.
    if (payload.ref or "").strip().lower() == "landing":
        try:
            from app.services.wallet_service import admin_credit_wallet
            admin_credit_wallet(
                session,
                customer_id=customer.id,
                amount_cents=2000,
                idempotency_key=f"trial-landing:{customer.id}",
                description="Landing $20 free trial credit",
            )
            security.create_log(
                session, "trial_grant", customer.email,
                f"customer_id={customer.id} amount_cents=2000 source=landing",
                request.client.host if request.client else None,
                "success",
            )
        except Exception as e:  # noqa: BLE001
            # Don't fail registration if the grant misfires — log + move on.
            import logging
            logging.getLogger(__name__).warning(
                "Trial credit grant failed for customer %s: %s", customer.id, e,
            )

    token = create_customer_access_token(customer)
    return CustomerToken(
        access_token=token,
        customer=CustomerRead.model_validate(customer.model_dump()),
    )


@customer_router.post("/login", response_model=CustomerToken, deprecated=True)
def login_customer(
    payload: CustomerLoginRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> Any:
    """Legacy customer login. Prefer POST /auth/login from the SPA.

    Kept because deps_customer.OAuth2PasswordBearer.tokenUrl points here, and
    smoke tests still call it directly.
    """
    ip = request.client.host if request.client else None
    email = payload.email.lower()

    customer = session.exec(
        select(Customer).where(Customer.email == email)
    ).first()

    if not customer or not security.verify_password(
        payload.password, customer.hashed_password
    ):
        security.create_log(
            session, "customer_login", email,
            "Invalid credentials", ip, "failed",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect email or password",
        )

    customer.last_login_at = datetime.utcnow()
    session.add(customer)
    session.commit()
    session.refresh(customer)

    security.create_log(
        session, "customer_login", customer.email,
        f"id={customer.id}", ip, "success",
    )

    token = create_customer_access_token(customer)
    return CustomerToken(
        access_token=token,
        customer=CustomerRead.model_validate(customer.model_dump()),
    )


@customer_router.get("/me", response_model=CustomerRead)
def read_customer_me(
    customer: Customer = Depends(get_current_customer),
) -> Any:
    """Return the authenticated customer's profile, plan, and quota usage."""
    return CustomerRead.model_validate(customer.model_dump())


# ============================================================================
# Unified login — single SPA entry
# ============================================================================

@unified_router.post("/login", response_model=UnifiedLoginResponse)
def unified_login(
    payload: UnifiedLoginRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> Any:
    """Identifier with '@' → customer (lookup Customer.email).
    Otherwise → admin/sales (lookup User.username).
    2FA admins return a 2FA hint so the SPA falls back to /login/access-token.
    """
    ip = request.client.host if request.client else None
    ident = (payload.identifier or "").strip()
    pwd = payload.password or ""

    if not ident or not pwd:
        raise HTTPException(status_code=400, detail="Incorrect identifier or password")

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

        # Epic C1: customer-internal sales (CustomerUser) fall-through
        from app.models.customer_user import CustomerUser
        from app.api.deps_sales import create_customer_sales_access_token
        cu = session.exec(
            select(CustomerUser).where(CustomerUser.email == email)
        ).first()
        if cu and cu.enabled and security.verify_password(pwd, cu.hashed_password):
            cu.last_login_at = datetime.utcnow()
            session.add(cu)
            session.commit()
            session.refresh(cu)
            security.create_log(
                session, "unified_login", cu.email,
                f"customer_user id={cu.id} (customer {cu.customer_id})", ip, "success",
            )
            return UnifiedLoginResponse(
                access_token=create_customer_sales_access_token(cu),
                role="sales",
                redirect_to="/sales/inbox",
            )

        security.create_log(
            session, "unified_login", email, "customer/sales invalid", ip, "failed",
        )
        raise HTTPException(status_code=400, detail="Incorrect identifier or password")

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
        redirect_to="/dashboard" if role == "admin" else "/sales/inbox",
    )
