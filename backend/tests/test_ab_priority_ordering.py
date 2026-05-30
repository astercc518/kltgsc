"""
Phase 6 Task 4 — A/B priority ordering tests.

Verifies that find_applicable_experiments returns experiments sorted by scope
priority: monitor (0) > customer (1) > global (2).
"""
from unittest.mock import MagicMock

from app.services.ab_assignment_service import find_applicable_experiments


def _make_exp(exp_id: int, scope: str, scope_value=None):
    e = MagicMock()
    e.id = exp_id
    e.scope = scope
    e.scope_value = scope_value
    return e


def _fake_session(experiments):
    """Return a session mock whose exec().all() yields the given list."""
    session = MagicMock()
    session.exec.return_value.all.return_value = experiments
    return session


# ---------------------------------------------------------------------------
# Test 1: all three scope types present — monitor comes first, global last
# ---------------------------------------------------------------------------
def test_all_three_scopes_sorted_monitor_customer_global():
    """When global, customer, and monitor experiments all match, order is
    monitor → customer → global regardless of the order returned by the DB."""
    g = _make_exp(10, "global")
    c = _make_exp(20, "customer", scope_value=1)
    m = _make_exp(30, "monitor", scope_value=5)

    # Deliberately hand them in reverse priority order so the sort is exercised.
    result = find_applicable_experiments(
        session=_fake_session([g, c, m]),
        customer_id=1,
        monitor_id=5,
    )

    scopes = [e.scope for e in result]
    assert scopes == ["monitor", "customer", "global"], (
        f"Expected ['monitor', 'customer', 'global'], got {scopes}"
    )


# ---------------------------------------------------------------------------
# Test 2: monitor beats customer when both are present
# ---------------------------------------------------------------------------
def test_monitor_precedes_customer():
    """monitor-scope experiment must sort before customer-scope experiment."""
    c = _make_exp(1, "customer", scope_value=7)
    m = _make_exp(2, "monitor", scope_value=42)

    result = find_applicable_experiments(
        session=_fake_session([c, m]),
        customer_id=7,
        monitor_id=42,
    )

    scopes = [e.scope for e in result]
    assert scopes[0] == "monitor", (
        f"Expected first scope 'monitor', got '{scopes[0]}'"
    )
    assert scopes[1] == "customer"


# ---------------------------------------------------------------------------
# Test 3: customer beats global when both are present (no monitor)
# ---------------------------------------------------------------------------
def test_customer_precedes_global():
    """customer-scope experiment must sort before global-scope experiment."""
    g = _make_exp(5, "global")
    c = _make_exp(6, "customer", scope_value=3)

    result = find_applicable_experiments(
        session=_fake_session([g, c]),
        customer_id=3,
        monitor_id=99,
    )

    scopes = [e.scope for e in result]
    assert scopes[0] == "customer", (
        f"Expected first scope 'customer', got '{scopes[0]}'"
    )
    assert scopes[1] == "global"
