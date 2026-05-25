"""
ActivationCode service — generate / redeem / revoke.

Epic 1 — see docs/superpowers/plans/2026-05-22-epic1-levels-and-activation-codes.md
"""
from __future__ import annotations

import logging
import secrets
import string
import uuid
from datetime import datetime, timedelta
from typing import Optional

from sqlmodel import Session, select

from app.models.activation_code import (
    ActivationCode,
    CODE_UNUSED,
    CODE_REDEEMED,
    CODE_REVOKED,
)
from app.models.customer import PLAN_CODES, Customer
from app.models.subscription import (
    Subscription,
    SUB_PENDING,
)

logger = logging.getLogger(__name__)


class ActivationCodeError(Exception):
    """Validation / state errors. Mapped to 400/404/409 at the API layer."""


_CODE_ALPHABET = string.ascii_uppercase + string.digits  # 36 chars
_CODE_LENGTH = 12


def _generate_code_string() -> str:
    """12-char [A-Z0-9] random code. Caller checks DB collision."""
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))


def generate_codes(
    session: Session,
    admin_user_id: int,
    plan: str,
    count: int = 1,
    duration_days: int = 30,
    notes: Optional[str] = None,
) -> list[ActivationCode]:
    """Generate `count` unused codes for `plan`, all sharing one batch_id."""
    if plan not in PLAN_CODES:
        raise ActivationCodeError(f"Unknown plan: {plan}")
    if not (1 <= count <= 500):
        raise ActivationCodeError(f"count must be 1..500, got {count}")
    if not (1 <= duration_days <= 365):
        raise ActivationCodeError(f"duration_days must be 1..365, got {duration_days}")

    batch_id = uuid.uuid4().hex
    created: list[ActivationCode] = []

    for _ in range(count):
        # Retry on collision (vanishingly rare with 36^12 space)
        for _attempt in range(5):
            code_str = _generate_code_string()
            existing = session.exec(
                select(ActivationCode).where(ActivationCode.code == code_str)
            ).first()
            if not existing:
                break
        else:
            raise ActivationCodeError("Failed to generate unique code after 5 retries")

        ac = ActivationCode(
            code=code_str,
            plan=plan,
            duration_days=duration_days,
            batch_id=batch_id,
            status=CODE_UNUSED,
            created_by_admin_id=admin_user_id,
            notes=notes,
        )
        session.add(ac)
        created.append(ac)

    session.commit()
    for ac in created:
        session.refresh(ac)
    logger.info(
        "Generated %d activation codes for plan=%s batch=%s by admin=%d",
        count, plan, batch_id, admin_user_id,
    )
    return created


def redeem_code(session: Session, customer: Customer, code_str: str) -> Subscription:
    """Redeem a bearer activation code → create active Subscription.

    Normalization:
      - Strip dashes and whitespace
      - Uppercase
      - Must match ^[A-Z0-9]{12}$ after normalization

    Race-safety: SELECT ... FOR UPDATE locks the row in PostgreSQL for the
    duration of this transaction, so two concurrent customers redeeming the
    same code are serialized. The second one finds status=='redeemed' and
    raises. SQLite (test env, single-writer) silently ignores the hint.
    """
    from app.services.billing_service import _apply_subscription_activation, BillingError

    normalized = code_str.replace("-", "").replace(" ", "").upper()
    if len(normalized) != _CODE_LENGTH or not all(c in _CODE_ALPHABET for c in normalized):
        raise ActivationCodeError(f"Invalid code format")

    code = session.exec(
        select(ActivationCode)
        .where(ActivationCode.code == normalized)
        .with_for_update()
    ).first()
    if not code:
        raise ActivationCodeError("Code not found")
    if code.status == CODE_REDEEMED:
        raise ActivationCodeError("Code already redeemed")
    if code.status == CODE_REVOKED:
        raise ActivationCodeError("Code has been revoked")

    # Create Subscription tagged with activation provenance
    now = datetime.utcnow()
    sub = Subscription(
        customer_id=customer.id,
        plan=code.plan,
        status=SUB_PENDING,
        period_start=now,
        period_end=now + timedelta(days=code.duration_days),
        activated_via="code",
        activation_code_id=code.id,
    )
    session.add(sub)
    session.flush()  # need sub.id

    # Mark code redeemed BEFORE applying activation, so the helper's
    # commit-batch includes the code transition.
    code.status = CODE_REDEEMED
    code.redeemed_by_customer_id = customer.id
    code.redeemed_subscription_id = sub.id
    code.redeemed_at = now
    session.add(code)
    session.commit()
    session.refresh(sub)

    # Apply shared activation pipeline (cancel-priors, set-active,
    # refresh-customer, enable-features, provision_customer)
    return _apply_subscription_activation(session, customer, sub)


def revoke_code(session: Session, code_id: int, admin_user_id: int) -> ActivationCode:
    """Revoke an unused code. Idempotent on already-revoked codes.
    Rejects (409) if code is already redeemed (terminal state)."""
    code = session.get(ActivationCode, code_id)
    if not code:
        raise ActivationCodeError("Code not found")
    if code.status == CODE_REDEEMED:
        raise ActivationCodeError("Code already redeemed; cannot revoke")
    if code.status == CODE_REVOKED:
        return code  # idempotent
    code.status = CODE_REVOKED
    session.add(code)
    session.commit()
    session.refresh(code)
    logger.info("Revoked code %s by admin=%d", code.code, admin_user_id)
    return code
