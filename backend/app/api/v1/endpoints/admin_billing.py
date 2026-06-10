"""
Admin-facing billing endpoints (Epic 2 MVP).

Used by ops to manually confirm USDT payments and activate subscriptions.
Future Epic 2.5 will add an automated webhook from a USDT gateway (e.g.
NowPayments) — see [[project-payment-decision]].
"""
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.api.deps import get_current_admin
from app.core.db import get_session
from app.models.customer import Customer, CustomerRead
from app.models.subscription import (
    ActivateSubscriptionRequest,
    Invoice,
    InvoiceRead,
    SubscriptionRead,
)
from app.models.user import User
from app.services.billing_service import BillingError, activate_invoice
from app.services.allocation_service import (
    allocate_accounts_for_customer,
    allocate_groups_for_customer,
)


router = APIRouter()


@router.get("/customers", response_model=List[CustomerRead])
def list_customers(
    _admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
    status_filter: str | None = Query(None, alias="status"),
    plan_filter: str | None = Query(None, alias="plan"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> Any:
    """List all customers (admin only)."""
    stmt = select(Customer)
    if status_filter:
        stmt = stmt.where(Customer.status == status_filter)
    if plan_filter:
        stmt = stmt.where(Customer.plan == plan_filter)
    rows = session.exec(
        stmt.order_by(Customer.created_at.desc()).offset(skip).limit(limit)
    ).all()
    return [CustomerRead.model_validate(r.model_dump()) for r in rows]


@router.get("/invoices", response_model=List[InvoiceRead])
def list_all_invoices(
    _admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
    status_filter: str | None = Query(None, alias="status"),
    customer_id: int | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> Any:
    """List invoices across all customers (admin only).

    Common use: status=pending to find invoices needing confirmation.
    """
    stmt = select(Invoice)
    if status_filter:
        stmt = stmt.where(Invoice.status == status_filter)
    if customer_id:
        stmt = stmt.where(Invoice.customer_id == customer_id)
    rows = session.exec(
        stmt.order_by(Invoice.created_at.desc()).offset(skip).limit(limit)
    ).all()
    return [InvoiceRead.model_validate(r.model_dump()) for r in rows]


@router.post(
    "/customers/{customer_id}/activate-subscription",
    response_model=SubscriptionRead,
)
def activate_subscription(
    customer_id: int,
    payload: ActivateSubscriptionRequest,
    admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    """Confirm an on-chain USDT transfer and activate the subscription.

    Ops workflow:
      1. Customer transfers USDT to the address shown in their invoice
      2. Ops sees the tx on chain explorer, copies tx_hash
      3. Ops calls this endpoint with invoice_id + tx_hash
      4. Service marks invoice paid, activates subscription, sets quota

    Idempotent: calling again for an already-paid invoice returns the
    same subscription without side effects.
    """
    invoice = session.get(Invoice, payload.invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if invoice.customer_id != customer_id:
        raise HTTPException(
            status_code=400,
            detail=f"Invoice {invoice.id} does not belong to customer {customer_id}",
        )

    try:
        subscription = activate_invoice(
            session,
            invoice=invoice,
            tx_hash=payload.tx_hash,
            admin_user_id=admin.id,
        )
    except BillingError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return SubscriptionRead.model_validate(subscription.model_dump())


# ──────────────────────────────────────────────────────────────────────────
# Epic 3 — manual reallocation endpoints
# ──────────────────────────────────────────────────────────────────────────

@router.post("/customers/{customer_id}/reallocate-accounts")
def reallocate_accounts(
    customer_id: int,
    _admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    """Top up the customer's allocated accounts to quota (idempotent).

    Use when activation-time provisioning failed or quota was bumped.
    """
    from app.models.customer import Customer
    customer = session.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    result = allocate_accounts_for_customer(session, customer)
    return {
        "allocated": len(result.accounts),
        "customized": result.customized,
        "industry": result.industry,
        "account_ids": [a.id for a in result.accounts],
    }


@router.post("/customers/{customer_id}/reallocate-groups")
def reallocate_groups(
    customer_id: int,
    _admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    """Top up the customer's allocated source groups to quota (best-effort)."""
    from app.models.customer import Customer
    customer = session.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    result = allocate_groups_for_customer(session, customer)
    return {
        "allocated": len(result.groups),
        "industry_pool_size": result.pool_size,
        "industry": result.industry,
        "group_ids": [g.id for g in result.groups],
    }


@router.post("/customers/{customer_id}/regenerate-kb")
def regenerate_kb(
    customer_id: int,
    _admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    """Wipe + regenerate the customer's auto industry KB.

    Use when customer changes industry or KB prompts are upgraded. Returns
    counts; the actual KB rows are visible via /customer/knowledge-bases.
    """
    from app.models.customer import Customer
    from app.services.industry_kb_service import regenerate_kb_for_customer
    customer = session.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    result = regenerate_kb_for_customer(session, customer)
    return {
        "industry": result.industry,
        "created": len(result.created),
        "embedded": result.embedded,
        "skipped": result.skipped,
        "kb_ids": [k.id for k in result.created],
    }


@router.get("/customers/{customer_id}/wallet")
def admin_get_customer_wallet(
    customer_id: int,
    _admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    """客户钱包余额（admin 视角，供充值前后展示）。"""
    if not session.get(Customer, customer_id):
        raise HTTPException(status_code=404, detail="Customer not found")
    from app.services.wallet_service import get_or_create_wallet
    w = get_or_create_wallet(session, customer_id)
    return {
        "customer_id": customer_id,
        "balance_cents": w.balance_cents,
        "total_topup_cents": w.total_topup_cents,
        "total_spent_cents": w.total_spent_cents,
    }


# ──────────────────────────────────────────────────────────────────────────
# Quick-provision (admin one-click setup)
# ──────────────────────────────────────────────────────────────────────────

from pydantic import BaseModel, Field
from datetime import datetime, timedelta

from app.core import security
from app.models.customer import (
    PLAN_CODES, PLAN_PRICE_USD, PLAN_QUOTA, STATUS_ACTIVE,
)
from app.models.subscription import (
    SUB_ACTIVE, INV_PAID, NETWORK_TRC20,
)
from app.services.wallet_service import admin_credit_wallet


class QuickProvisionRequest(BaseModel):
    # Either pick an existing customer...
    customer_id: int | None = None
    # ...or create one inline:
    new_customer_email: str | None = None
    new_customer_password: str | None = Field(default=None, min_length=8)
    new_customer_name: str | None = None
    new_customer_industry: str | None = None

    # Subscription: leave plan=None to skip
    plan: str | None = None    # 'starter' | 'growth' | 'pro'

    # Wallet credit (cents). 0 = skip
    wallet_credit_cents: int = Field(default=0, ge=0, le=10_000_000)
    note: str = Field(default="admin quick-provision", max_length=200)


@router.post("/quick-provision")
def quick_provision(
    payload: QuickProvisionRequest,
    admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    """One-call admin setup: create-or-pick customer, activate subscription
    (bypassing USDT payment, marked tx_hash='admin_manual'), credit wallet,
    and trigger Epic 3 allocation + Epic 4 KB generation.

    Use for: trial onboarding, internal QA, migration imports, or whenever
    a sales rep wants to spin up a customer without making them pay first.
    Every side effect is idempotent on the underlying invoice/transaction
    keys, so calling twice with the same inputs won't double-bill.
    """
    from app.models.customer import Customer, STATUS_PENDING
    from app.services.billing_service import create_pending_invoice

    # Step 1 — resolve or create customer
    customer: Customer | None = None
    created_customer = False
    if payload.customer_id:
        customer = session.get(Customer, payload.customer_id)
        if not customer:
            raise HTTPException(status_code=404, detail="customer not found")
    else:
        if not (payload.new_customer_email and payload.new_customer_password):
            raise HTTPException(
                status_code=400,
                detail="provide customer_id, or new_customer_email + new_customer_password",
            )
        email = payload.new_customer_email.lower().strip()
        existing = session.exec(
            select(Customer).where(Customer.email == email)
        ).first()
        if existing:
            customer = existing
        else:
            customer = Customer(
                email=email,
                hashed_password=security.get_password_hash(payload.new_customer_password),
                name=payload.new_customer_name or email.split("@", 1)[0],
                industry=payload.new_customer_industry,
                status=STATUS_PENDING,
            )
            session.add(customer)
            session.commit()
            session.refresh(customer)
            created_customer = True
            security.create_log(
                session, "admin_quick_provision_create_customer",
                customer.email, f"id={customer.id} by admin {admin.username}",
                None, "success",
            )

    # Step 2 — activate subscription (if plan given AND customer doesn't
    # already have an active matching one — otherwise no-op to keep this
    # endpoint safely re-callable as a "make sure it's set up" idempotent op).
    activated_plan = None
    if payload.plan:
        if payload.plan not in PLAN_CODES:
            raise HTTPException(status_code=400, detail=f"unknown plan: {payload.plan}")
        from app.models.subscription import Subscription
        already_on_plan = session.exec(
            select(Subscription).where(
                Subscription.customer_id == customer.id,
                Subscription.status == SUB_ACTIVE,
                Subscription.plan == payload.plan,
            )
        ).first()
        if already_on_plan:
            activated_plan = None  # skipped — already on this plan
        else:
            # Reuse the same pending-invoice path then activate it. This way
            # Subscription / Invoice / Customer.status / quota / Epic 3
            # allocation / Epic 4 KB all fire through their normal codepaths.
            try:
                invoice = create_pending_invoice(session, customer, payload.plan, NETWORK_TRC20)
                activate_invoice(
                    session, invoice=invoice,
                    tx_hash=f"admin_manual:{admin.id}:{invoice.id}",
                    admin_user_id=admin.id,
                )
                activated_plan = payload.plan
            except BillingError as e:
                raise HTTPException(status_code=400, detail=f"activate: {e}")

    # Step 3 — wallet credit (if > 0)
    wallet_credit_txn_id = None
    if payload.wallet_credit_cents > 0:
        idem = f"admin-credit:{customer.id}:{admin.id}:{payload.wallet_credit_cents}:{int(datetime.utcnow().timestamp())}"
        txn = admin_credit_wallet(
            session,
            customer_id=customer.id,
            amount_cents=payload.wallet_credit_cents,
            description=f"{payload.note} (admin {admin.username})",
            idempotency_key=idem,
        )
        wallet_credit_txn_id = txn.id

    session.refresh(customer)

    # Return a summary so the admin UI can show "what just happened".
    from app.models.wallet import CustomerWallet
    wallet = session.get(CustomerWallet, customer.id)
    from app.models.subscription import Subscription
    sub = session.exec(
        select(Subscription).where(
            Subscription.customer_id == customer.id,
            Subscription.status == SUB_ACTIVE,
        ).order_by(Subscription.created_at.desc())
    ).first()

    return {
        "ok": True,
        "customer_id": customer.id,
        "customer_email": customer.email,
        "customer_status": customer.status,
        "created_customer": created_customer,
        "plan_activated": activated_plan,
        "subscription_id": sub.id if sub else None,
        "current_period_end": sub.period_end.isoformat() if sub and sub.period_end else None,
        "account_quota": customer.account_quota,
        "account_used": customer.account_used,
        "group_quota": customer.group_quota,
        "wallet_balance_cents": wallet.balance_cents if wallet else 0,
        "wallet_credit_txn_id": wallet_credit_txn_id,
    }


# ──────────────────────────────────────────────────────────────────────────
# Phase F1 — internal lead pool provisioning
# ──────────────────────────────────────────────────────────────────────────


class ProvisionInternalPoolRequest(BaseModel):
    email: str = Field(..., description="logical id for the pool, e.g. 'internal-crypto@platform.local'")
    name: str = Field(..., description="display name in admin UI")
    industry: str | None = Field(None, description="default industry for leads in this pool")
    account_ids: list[int] = Field(default_factory=list,
        description="TG accounts to assign to this pool (will set their customer_id)")


@router.post("/provision-internal-pool")
def provision_internal_pool(
    payload: ProvisionInternalPoolRequest,
    admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    """Create (or find) a Customer flagged is_internal_pool=true. Skips
    subscription and wallet billing — internal pools are platform-owned
    lead containers, not paying customers. Optionally reassigns TG
    accounts into the pool so the listener starts collecting leads
    under it.

    Idempotent: if a Customer with this email already exists and is
    flagged as internal pool, returns it; if it exists but isn't internal
    pool, flips the flag.
    """
    from app.models.account import Account
    from app.models.customer import Customer, STATUS_ACTIVE

    email = payload.email.lower().strip()
    cust = session.exec(select(Customer).where(Customer.email == email)).first()
    created = False
    if cust:
        if not cust.is_internal_pool:
            cust.is_internal_pool = True
        cust.status = STATUS_ACTIVE  # internal pools always active
        if payload.industry and not cust.industry:
            cust.industry = payload.industry
        session.add(cust)
    else:
        cust = Customer(
            email=email,
            hashed_password=security.get_password_hash("internal-pool-no-login-" + str(admin.id)),
            name=payload.name,
            industry=payload.industry,
            status=STATUS_ACTIVE,
            is_internal_pool=True,
        )
        session.add(cust)
        created = True
    session.commit()
    session.refresh(cust)
    security.create_log(
        session, "admin_provision_internal_pool",
        cust.email, f"id={cust.id} by admin {admin.username}",
        None, "success",
    )

    # Reassign accounts (only if explicitly listed)
    reassigned: list[int] = []
    if payload.account_ids:
        for aid in payload.account_ids:
            acc = session.get(Account, aid)
            if not acc:
                continue
            acc.customer_id = cust.id
            session.add(acc)
            reassigned.append(aid)
        session.commit()

    return {
        "ok": True,
        "customer_id": cust.id,
        "customer_email": cust.email,
        "is_internal_pool": cust.is_internal_pool,
        "industry": cust.industry,
        "created": created,
        "reassigned_account_ids": reassigned,
    }


# ── Epic 1 — Activation codes ─────────────────────────────────────────
from typing import Optional as _Optional

from app.models.activation_code import (
    ActivationCode,
    ActivationCodeGenerateRequest,
    ActivationCodeGenerateResponse,
    ActivationCodeRead,
)
from app.services.activation_code_service import (
    ActivationCodeError,
    generate_codes as ac_generate,
    revoke_code as ac_revoke,
)


@router.post(
    "/activation-codes/generate",
    response_model=ActivationCodeGenerateResponse,
)
def admin_generate_activation_codes(
    request: ActivationCodeGenerateRequest,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
) -> Any:
    """Generate a batch of bearer activation codes for a given plan."""
    try:
        codes = ac_generate(
            session,
            admin_user_id=admin.id,
            plan=request.plan,
            count=request.count,
            duration_days=request.duration_days,
            notes=request.notes,
        )
    except ActivationCodeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ActivationCodeGenerateResponse(
        batch_id=codes[0].batch_id,
        codes=[ActivationCodeRead.model_validate(c) for c in codes],
    )


@router.get(
    "/activation-codes",
    response_model=List[ActivationCodeRead],
)
def admin_list_activation_codes(
    status: _Optional[str] = Query(None),
    plan: _Optional[str] = Query(None),
    batch_id: _Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    _admin: User = Depends(get_current_admin),
) -> Any:
    """List activation codes with optional filters."""
    stmt = select(ActivationCode)
    if status:
        stmt = stmt.where(ActivationCode.status == status)
    if plan:
        stmt = stmt.where(ActivationCode.plan == plan)
    if batch_id:
        stmt = stmt.where(ActivationCode.batch_id == batch_id)
    stmt = stmt.order_by(ActivationCode.created_at.desc()).offset(offset).limit(limit)
    rows = session.exec(stmt).all()
    return [ActivationCodeRead.model_validate(r) for r in rows]


@router.get(
    "/activation-codes/{code_id}",
    response_model=ActivationCodeRead,
)
def admin_get_activation_code(
    code_id: int,
    session: Session = Depends(get_session),
    _admin: User = Depends(get_current_admin),
) -> Any:
    """Fetch a single activation code by its database ID."""
    code = session.get(ActivationCode, code_id)
    if not code:
        raise HTTPException(status_code=404, detail="Code not found")
    return ActivationCodeRead.model_validate(code)


@router.post(
    "/activation-codes/{code_id}/revoke",
    response_model=ActivationCodeRead,
)
def admin_revoke_activation_code(
    code_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
) -> Any:
    """Revoke an unused activation code. Idempotent on already-revoked codes."""
    try:
        code = ac_revoke(session, code_id, admin_user_id=admin.id)
    except ActivationCodeError as e:
        msg = str(e)
        if "not found" in msg.lower():
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=409, detail=msg)
    return ActivationCodeRead.model_validate(code)


@router.get("/internal-pools")
def list_internal_pools(
    _admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    """List all is_internal_pool=true customers with their account / lead counts."""
    from app.models.account import Account
    from app.models.customer import Customer
    from app.models.lead import Lead
    from sqlalchemy import func

    pools = session.exec(
        select(Customer).where(Customer.is_internal_pool.is_(True))
        .order_by(Customer.created_at.desc())
    ).all()
    out = []
    for p in pools:
        acc_count = session.exec(
            select(func.count(Account.id)).where(Account.customer_id == p.id)
        ).one()
        lead_count = session.exec(
            select(func.count(Lead.id)).where(Lead.customer_id == p.id)
        ).one()
        out.append({
            "id": p.id,
            "email": p.email,
            "name": p.name,
            "industry": p.industry,
            "account_count": acc_count,
            "lead_count": lead_count,
            "created_at": p.created_at.isoformat(),
        })
    return out
