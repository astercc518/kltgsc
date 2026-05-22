"""ActivationCodeService — generate/redeem/revoke unit tests."""
import re
from datetime import datetime, timedelta

import pytest
from sqlmodel import select

from app.models.activation_code import (
    ActivationCode,
    CODE_UNUSED,
    CODE_REDEEMED,
    CODE_REVOKED,
)
from app.models.customer import Customer, STATUS_ACTIVE
from app.models.subscription import Subscription, SUB_ACTIVE
from app.services.activation_code_service import (
    ActivationCodeError,
    generate_codes,
    redeem_code,
    revoke_code,
)


# ── generate_codes ─────────────────────────────────────────────────────

def test_generate_codes_returns_requested_count(session):
    codes = generate_codes(session, admin_user_id=1, plan="starter", count=5)
    assert len(codes) == 5
    for c in codes:
        assert c.status == CODE_UNUSED
        assert c.plan == "starter"
        assert c.duration_days == 30
        assert re.fullmatch(r"[A-Z0-9]{12}", c.code), f"bad code format: {c.code}"


def test_generate_codes_assigns_same_batch_id(session):
    codes = generate_codes(session, admin_user_id=1, plan="growth", count=3)
    batch_ids = {c.batch_id for c in codes}
    assert len(batch_ids) == 1


def test_generate_codes_different_calls_get_different_batches(session):
    a = generate_codes(session, admin_user_id=1, plan="starter", count=2)
    b = generate_codes(session, admin_user_id=1, plan="starter", count=2)
    assert a[0].batch_id != b[0].batch_id


def test_generate_codes_rejects_invalid_plan(session):
    with pytest.raises(ActivationCodeError):
        generate_codes(session, admin_user_id=1, plan="freemium", count=1)


def test_generate_codes_persists_to_db(session):
    generate_codes(session, admin_user_id=1, plan="pro", count=4)
    rows = session.exec(select(ActivationCode).where(ActivationCode.plan == "pro")).all()
    assert len(rows) == 4


def test_generate_codes_codes_are_unique(session):
    codes = generate_codes(session, admin_user_id=1, plan="starter", count=20)
    seen = {c.code for c in codes}
    assert len(seen) == 20


def test_generate_codes_respects_duration_days(session):
    codes = generate_codes(session, admin_user_id=1, plan="starter", count=1, duration_days=90)
    assert codes[0].duration_days == 90
