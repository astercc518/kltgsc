"""
Customer-admin endpoints for managing sub-users (sales employees).

Mounted at /customer/sales-users. The authenticated customer (parent
tenant) creates / lists / updates / deletes CustomerUser rows that share
their tenant scope. Enforces seat_quota.
"""
import json
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.api.deps_customer import get_current_customer
from app.core import security
from app.core.db import get_session
from app.models.customer import Customer
from app.models.customer_user import (
    CustomerUser,
    CustomerUserCreate,
    CustomerUserRead,
    CustomerUserUpdate,
)


router = APIRouter()


@router.get("", response_model=List[CustomerUserRead])
def list_sales_users(
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
) -> Any:
    rows = session.exec(
        select(CustomerUser)
        .where(CustomerUser.customer_id == customer.id)
        .order_by(CustomerUser.created_at.desc())
    ).all()
    return [CustomerUserRead.from_orm_with_json(u) for u in rows]


@router.post("", response_model=CustomerUserRead, status_code=201)
def create_sales_user(
    payload: CustomerUserCreate,
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
) -> Any:
    if customer.seat_used >= customer.seat_quota:
        raise HTTPException(
            status_code=400,
            detail=f"seat quota exhausted ({customer.seat_used}/{customer.seat_quota})",
        )

    # Enforce email uniqueness globally (CustomerUser.email is unique
    # and we shouldn't collide with Customer.email either).
    email = payload.email.lower().strip()
    if session.exec(select(CustomerUser).where(CustomerUser.email == email)).first():
        raise HTTPException(status_code=409, detail="email already in use")
    if session.exec(select(Customer).where(Customer.email == email)).first():
        raise HTTPException(status_code=409, detail="email collides with a customer account")

    cu = CustomerUser(
        customer_id=customer.id,
        email=email,
        hashed_password=security.get_password_hash(payload.password),
        name=payload.name,
        industry_filter_json=json.dumps(payload.industry_filter or []),
    )
    session.add(cu)
    customer.seat_used += 1
    session.add(customer)
    session.commit()
    session.refresh(cu)
    return CustomerUserRead.from_orm_with_json(cu)


def _own_or_404(session: Session, customer_id: int, user_id: int) -> CustomerUser:
    cu = session.get(CustomerUser, user_id)
    if not cu or cu.customer_id != customer_id:
        raise HTTPException(status_code=404, detail="sales user not found")
    return cu


@router.get("/{user_id}", response_model=CustomerUserRead)
def get_sales_user(
    user_id: int,
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
) -> Any:
    cu = _own_or_404(session, customer.id, user_id)
    return CustomerUserRead.from_orm_with_json(cu)


@router.patch("/{user_id}", response_model=CustomerUserRead)
def update_sales_user(
    user_id: int,
    payload: CustomerUserUpdate,
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
) -> Any:
    cu = _own_or_404(session, customer.id, user_id)
    if payload.name is not None:
        cu.name = payload.name
    if payload.password:
        cu.hashed_password = security.get_password_hash(payload.password)
    if payload.industry_filter is not None:
        cu.industry_filter_json = json.dumps(payload.industry_filter)
    if payload.enabled is not None:
        cu.enabled = payload.enabled
    session.add(cu)
    session.commit()
    session.refresh(cu)
    return CustomerUserRead.from_orm_with_json(cu)


@router.delete("/{user_id}")
def delete_sales_user(
    user_id: int,
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
) -> Any:
    cu = _own_or_404(session, customer.id, user_id)
    session.delete(cu)
    if customer.seat_used > 0:
        customer.seat_used -= 1
        session.add(customer)
    session.commit()
    return {"ok": True}
