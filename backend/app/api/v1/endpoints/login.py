from datetime import timedelta, datetime
from typing import Any

import pyotp
import redis
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from jose import jwt, JWTError
from pydantic import BaseModel
from sqlmodel import Session, select

from app.core.config import settings
from app.core import security
from app.core.security import ALGORITHM, revoke_token, is_token_revoked
from app.core.db import get_session
from app.api.deps import get_current_user
from app.models.token import Token, TokenPayload
from app.models.user import User

router = APIRouter()
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

# Reuse the same OAuth2 scheme for extracting the raw token in logout
_oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token"
)


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

@router.post("/login/access-token", response_model=Token)
def login_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests.

    If the user has 2FA enabled, the client must pass the TOTP code as the
    ``client_secret`` field of the OAuth2 form (or via the ``totp_code``
    scope hack).  A cleaner approach is to include it in the ``password``
    field separated by a pipe, e.g. ``password|123456``.
    """
    # Rate Limiting
    ip = request.client.host
    key = f"login_attempts:{ip}"
    attempts = redis_client.get(key)
    if attempts and int(attempts) > 5:
        security.create_log(
            session, "login", form_data.username,
            "Too many attempts", ip, "failed",
        )
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Try again later.",
        )

    # Authenticate -- support password|totp_code format
    raw_password = form_data.password
    totp_code: str | None = None
    if "|" in raw_password:
        raw_password, totp_code = raw_password.rsplit("|", 1)

    # Also accept totp_code from client_secret (OAuth2 form field)
    if not totp_code and form_data.client_secret:
        totp_code = form_data.client_secret

    user = session.exec(
        select(User).where(User.username == form_data.username)
    ).first()

    if not user or not security.verify_password(raw_password, user.hashed_password):
        redis_client.incr(key)
        redis_client.expire(key, 900)  # 15 minutes block
        security.create_log(
            session, "login", form_data.username,
            "Incorrect credentials", ip, "failed",
        )
        raise HTTPException(
            status_code=400,
            detail="Incorrect email or password",
        )

    # 2FA check -- if the user has TOTP enabled, a valid code is required
    if user.totp_enabled and user.totp_secret:
        if not totp_code:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="2FA code required",
            )
        totp = pyotp.TOTP(user.totp_secret)
        if not totp.verify(totp_code, valid_window=1):
            redis_client.incr(key)
            redis_client.expire(key, 900)
            security.create_log(
                session, "login", user.username,
                "Invalid 2FA code", ip, "failed",
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid 2FA code",
            )

    # Reset attempts on success
    redis_client.delete(key)

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


# ---------------------------------------------------------------------------
# Logout (token revocation)
# ---------------------------------------------------------------------------

@router.post("/logout", response_model=LogoutResponse)
def logout(
    token: str = Depends(_oauth2_scheme),
    current_user: str = Depends(get_current_user),
) -> Any:
    """
    Revoke the current JWT so it can no longer be used.
    """
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[ALGORITHM],
        )
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

    # Calculate remaining TTL so the Redis key expires automatically
    now_ts = int(datetime.utcnow().timestamp())
    exp_ts = int(payload.get("exp", now_ts))
    remaining_ttl = max(exp_ts - now_ts, 1)

    revoke_token(token_data.jti, remaining_ttl)
    return {"message": "Successfully logged out"}


# ---------------------------------------------------------------------------
# 2FA Setup
# ---------------------------------------------------------------------------

@router.post("/auth/setup-2fa", response_model=Setup2FAResponse)
def setup_2fa(
    session: Session = Depends(get_session),
    current_user: str = Depends(get_current_user),
) -> Any:
    """
    Generate a new TOTP secret for the authenticated user.

    Returns the secret and a provisioning URI that can be encoded into a
    QR code by the frontend.  2FA is **not** activated until the user
    verifies a code via ``/auth/verify-2fa``.
    """
    user = session.exec(
        select(User).where(User.username == current_user)
    ).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Generate a fresh TOTP secret
    secret = pyotp.random_base32()

    # Store the secret on the user (not yet activated)
    user.totp_secret = secret
    user.totp_enabled = False  # will be enabled after verification
    session.add(user)
    session.commit()

    # Build provisioning URI for authenticator apps
    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(
        name=user.username,
        issuer_name=settings.PROJECT_NAME,
    )

    return {
        "secret": secret,
        "provisioning_uri": provisioning_uri,
        "message": "Scan the QR code with your authenticator app, then verify with /auth/verify-2fa",
    }


# ---------------------------------------------------------------------------
# 2FA Verification (activation)
# ---------------------------------------------------------------------------

@router.post("/auth/verify-2fa", response_model=Verify2FAResponse)
def verify_2fa(
    data: TOTPVerify,
    session: Session = Depends(get_session),
    current_user: str = Depends(get_current_user),
) -> Any:
    """
    Verify a TOTP code and activate 2FA for the user.

    The user must have already called ``/auth/setup-2fa`` to generate a
    secret.  After successful verification the ``totp_enabled`` flag is
    set to ``True`` and all future logins will require a TOTP code.
    """
    user = session.exec(
        select(User).where(User.username == current_user)
    ).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if not user.totp_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA has not been set up. Call /auth/setup-2fa first.",
        )

    totp = pyotp.TOTP(user.totp_secret)
    if not totp.verify(data.code, valid_window=1):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid TOTP code",
        )

    # Activate 2FA
    user.totp_enabled = True
    session.add(user)
    session.commit()

    return {"message": "2FA has been activated successfully"}
