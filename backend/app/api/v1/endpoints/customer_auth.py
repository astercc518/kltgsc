"""
Customer-facing authentication endpoints.

Separate from /login (internal admin/sales) — these are for paying customers
who subscribe to the TG1.AI platform. See [[project-business-model-aas]].

Flow:
    POST /customer/register   create a new customer (status=pending)
    POST /customer/login      exchange email+password for a customer JWT
    GET  /customer/me         introspect the authenticated customer
"""
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlmodel import Session, select

from app.api.deps_customer import (
    create_customer_access_token,
    get_current_customer,
)
from app.core import security
from app.core.db import get_session
from app.models.customer import (
    Customer,
    CustomerCreate,
    CustomerRead,
    STATUS_PENDING,
)


router = APIRouter()


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class CustomerToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
    customer: CustomerRead


class CustomerLoginRequest(BaseModel):
    email: str
    password: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/register", response_model=CustomerToken, status_code=201)
def register_customer(
    payload: CustomerCreate,
    request: Request,
    session: Session = Depends(get_session),
) -> Any:
    """Create a new customer account (status=pending, no plan yet).

    The returned token can be used immediately to fetch /customer/me but most
    resource-creating endpoints will reject until a subscription is activated
    via the Epic 2 billing flow.
    """
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

    token = create_customer_access_token(customer)
    return CustomerToken(
        access_token=token,
        customer=CustomerRead.model_validate(customer.model_dump()),
    )


@router.post("/login", response_model=CustomerToken)
def login_customer(
    payload: CustomerLoginRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> Any:
    """Exchange email + password for a customer access token."""
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


@router.get("/me", response_model=CustomerRead)
def read_customer_me(
    customer: Customer = Depends(get_current_customer),
) -> Any:
    """Return the authenticated customer's profile, plan, and quota usage."""
    return CustomerRead.model_validate(customer.model_dump())
