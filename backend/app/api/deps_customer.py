"""
Customer (tenant) authentication dependencies.

Customer tokens are issued by /api/v1/customer/login and live in a separate
OAuth2 scheme from the internal admin/sales User token. The JWT payload has
`type="customer"` and `customer_id` to prevent mix-ups; even if someone
manages to obtain a User token, calling get_current_customer will reject it.
"""
from datetime import datetime, timedelta
from typing import Any, Optional, Union
import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlmodel import Session

from app.core.config import settings
from app.core.db import get_session
from app.core.security import ALGORITHM, is_token_revoked
from app.models.customer import Customer, STATUS_CANCELED


CUSTOMER_TOKEN_TYPE = "customer"

# Customer 端独立 OAuth2 scheme
customer_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/customer/login",
    auto_error=True,
)


def create_customer_access_token(
    customer: Customer,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Build a JWT for a customer login.

    Distinct from User tokens via `type` claim — see get_current_customer.
    """
    now = datetime.utcnow()
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = now + expires_delta
    payload: dict[str, Any] = {
        "exp": expire,
        "iat": int(now.timestamp()),
        "jti": str(uuid.uuid4()),
        "sub": customer.email,
        "type": CUSTOMER_TOKEN_TYPE,
        "customer_id": customer.id,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def get_current_customer(
    token: str = Depends(customer_oauth2),
    session: Session = Depends(get_session),
) -> Customer:
    """Resolve the current customer from a customer-scoped JWT.

    Rejects User tokens (wrong `type` claim), revoked tokens (jti in blocklist),
    and customers whose status is canceled.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate customer credentials",
        )

    if payload.get("type") != CUSTOMER_TOKEN_TYPE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a customer token",
        )

    jti = payload.get("jti")
    if jti and is_token_revoked(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
        )

    customer_id = payload.get("customer_id")
    if not customer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token missing customer_id",
        )

    customer = session.get(Customer, customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Customer not found",
        )
    if customer.status == STATUS_CANCELED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Customer account has been canceled",
        )
    return customer


def get_active_customer(
    customer: Customer = Depends(get_current_customer),
) -> Customer:
    """Same as get_current_customer but additionally requires status=active.

    Use this on endpoints that consume quota / mutate billable resources;
    keep get_current_customer for read-only profile endpoints so pending
    customers can still see their account state before paying.
    """
    if customer.status != "active":
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Subscription not active (current status: {customer.status})",
        )
    return customer
