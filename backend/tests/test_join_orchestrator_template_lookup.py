"""
Phase 10: orchestrator reads captcha templates from the Customer row.

Phase 9 stubs returned None unconditionally. Phase 10 reads the real columns
and strips whitespace; blank/whitespace-only values still resolve to None
so handlers fall back to defaults.
"""
import os
from datetime import datetime, timezone

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from sqlmodel import SQLModel, Session, create_engine

from app.models.customer import Customer


def _make_engine():
    from app.models import account  # noqa: F401 ensure FK target available
    eng = create_engine("sqlite:///:memory:", echo=False)
    SQLModel.metadata.create_all(eng)
    return eng


def _seed(session, **fields) -> Customer:
    defaults = dict(
        email="t10@example.test",
        hashed_password="x",
        status="active",
        plan="starter",
        account_quota=3,
        group_quota=500,
        token_quota=2_000_000,
        seat_quota=1,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    defaults.update(fields)
    c = Customer(**defaults)
    session.add(c); session.commit(); session.refresh(c)
    return c


@pytest.fixture
def patched_orch(monkeypatch):
    eng = _make_engine()
    from app.services import join_orchestrator as orch
    monkeypatch.setattr(orch, "engine", eng)
    return eng, orch


def test_lookup_returns_none_for_missing_customer(patched_orch):
    _, orch = patched_orch
    assert orch._customer_join_template(9999) is None
    assert orch._customer_intro_template(9999) is None


def test_lookup_returns_none_when_columns_unset(patched_orch):
    eng, orch = patched_orch
    with Session(eng) as s:
        c = _seed(s)
    assert orch._customer_join_template(c.id) is None
    assert orch._customer_intro_template(c.id) is None


def test_lookup_returns_stripped_value(patched_orch):
    eng, orch = patched_orch
    with Session(eng) as s:
        c = _seed(
            s,
            email="stripped@example.test",
            captcha_join_template="  hello team  ",
            captcha_intro_template="\n你好 admin\n",
        )
    assert orch._customer_join_template(c.id) == "hello team"
    assert orch._customer_intro_template(c.id) == "你好 admin"


def test_lookup_blank_string_falls_back_to_none(patched_orch):
    eng, orch = patched_orch
    with Session(eng) as s:
        c = _seed(
            s,
            email="blank@example.test",
            captcha_join_template="   ",
            captcha_intro_template="",
        )
    assert orch._customer_join_template(c.id) is None
    assert orch._customer_intro_template(c.id) is None
