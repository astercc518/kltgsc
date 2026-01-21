from datetime import timedelta
from typing import Any
import redis
import pyotp
from fastapi import APIRouter, Depends, HTTPException, status, Form, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select
from pydantic import BaseModel

from app.core.config import settings
from app.core import security
from app.core.db import get_session
from app.api.deps import get_current_user
from app.models.token import Token
from app.models.user import User

router = APIRouter()
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

class LoginRequest(BaseModel):
    username: str
    password: str
    totp_code: str = None

@router.post("/login/access-token", response_model=Token)
def login_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session)
) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests
    """
    # Rate Limiting
    ip = request.client.host
    key = f"login_attempts:{ip}"
    attempts = redis_client.get(key)
    if attempts and int(attempts) > 5:
        security.create_log(session, "login", form_data.username, "Too many attempts", ip, "failed")
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again later.")

    # Authenticate
    user = session.exec(select(User).where(User.username == form_data.username)).first()
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        redis_client.incr(key)
        redis_client.expire(key, 900) # 15 minutes block
        security.create_log(session, "login", form_data.username, "Incorrect credentials", ip, "failed")
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    # Reset attempts
    redis_client.delete(key)
    
    security.create_log(session, "login", user.username, "Login successful", ip, "success")
        
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return {
        "access_token": security.create_access_token(
            subject=user.username, expires_delta=access_token_expires
        ),
        "token_type": "bearer",
    }

@router.post("/auth/setup-2fa")
def setup_2fa(
    session: Session = Depends(get_session),
    current_user: str = Depends(get_current_user)
):
    """生成 2FA 密钥"""
    # TODO: 实现 2FA 设置逻辑
    pass

class TOTPVerify(BaseModel):
    code: str

@router.post("/auth/verify-2fa")
def verify_2fa(
    data: TOTPVerify,
    session: Session = Depends(get_session),
    # current_user ...
):
    pass
