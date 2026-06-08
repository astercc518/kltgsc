"""Per-customer bulk-send pricing override.

bulk_send 单价默认走累计阶梯价 (calculate_tier_unit_price_cents)；当 admin 给客户
在 `bulk_send_message` slug 上设了 custom_price_cents，则该客户群发改用这个**扁平价**
（绕过阶梯）。未设置时行为与改造前完全一致。
"""
import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.models.feature import CustomerFeature
from app.services.feature_billing import get_customer_price_override_cents


@pytest.fixture
def session():
    eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(eng)
    with Session(eng) as s:
        yield s


# ── get_customer_price_override_cents ────────────────────────────────────

def test_override_none_when_no_row(session):
    assert get_customer_price_override_cents(session, 1, "bulk_send_message") is None


def test_override_none_when_row_has_no_custom_price(session):
    session.add(CustomerFeature(customer_id=1, feature_slug="bulk_send_message",
                                enabled=True, custom_price_cents=None))
    session.commit()
    assert get_customer_price_override_cents(session, 1, "bulk_send_message") is None


def test_override_returns_custom_price(session):
    session.add(CustomerFeature(customer_id=1, feature_slug="bulk_send_message",
                                enabled=True, custom_price_cents=8))
    session.commit()
    assert get_customer_price_override_cents(session, 1, "bulk_send_message") == 8


# ── resolve_bulk_unit_price_cents ────────────────────────────────────────

def test_resolve_falls_back_to_tier_when_no_override(session, monkeypatch):
    import app.services.bulk_dispatch_service as bd
    # No override → must use the spend-tier path (unchanged behavior).
    monkeypatch.setattr(bd, "_total_spent_cents", lambda s, cid: 0)
    # spent 0 → tier returns 15 (per calculate_tier_unit_price_cents)
    assert bd.resolve_bulk_unit_price_cents(session, 1) == 15


def test_resolve_uses_override_and_ignores_tier(session, monkeypatch):
    import app.services.bulk_dispatch_service as bd
    session.add(CustomerFeature(customer_id=1, feature_slug="bulk_send_message",
                                enabled=True, custom_price_cents=6))
    session.commit()
    # Even with huge spend (would be cheapest tier=5), override 6 wins flat.
    monkeypatch.setattr(bd, "_total_spent_cents", lambda s, cid: 999_999_00)
    assert bd.resolve_bulk_unit_price_cents(session, 1) == 6


# ── preview_cost_cents honours the flat override ─────────────────────────

def test_preview_flat_when_override_set(session, monkeypatch):
    import app.services.bulk_send_service as bs

    class _W:
        total_spent_cents = 0
        balance_cents = 10_000
    monkeypatch.setattr(bs, "get_or_create_wallet", lambda s, cid: _W())
    session.add(CustomerFeature(customer_id=1, feature_slug="bulk_send_message",
                                enabled=True, custom_price_cents=9))
    session.commit()

    out = bs.preview_cost_cents(session, 1, 100)
    assert out["current_tier_unit_cents"] == 9
    assert out["total_cost_cents"] == 900            # flat 9¢ × 100, no tier walking
    assert out["breakdown"] == [{"count": 100, "unit_cents": 9, "subtotal_cents": 900}]


def test_preview_tier_path_unchanged_without_override(session, monkeypatch):
    import app.services.bulk_send_service as bs

    class _W:
        total_spent_cents = 0
        balance_cents = 10_000
    monkeypatch.setattr(bs, "get_or_create_wallet", lambda s, cid: _W())

    out = bs.preview_cost_cents(session, 1, 100)
    # spent 0 → first tier 15¢ × 100
    assert out["current_tier_unit_cents"] == 15
    assert out["total_cost_cents"] == 1500
