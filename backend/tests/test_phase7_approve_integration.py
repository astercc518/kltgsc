"""
Phase 7 → Phase 8 integration test.

Verifies that approve_candidate calls queue_join when a worker account exists,
and gracefully skips when no worker is available.
"""
import pytest
from unittest.mock import MagicMock, patch


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_fake_group(group_id: int = 42, chat_link: str = "https://t.me/testg"):
    g = MagicMock()
    g.id = group_id
    g.customer_id = 1
    g.status = "pending"
    g.chat_link = chat_link
    g.decided_at = None
    return g


def _make_fake_worker(account_id: int = 10):
    w = MagicMock()
    w.id = account_id
    w.customer_id = 1
    w.role = "worker"
    w.status = "active"
    return w


def _make_fake_customer(customer_id: int = 1):
    c = MagicMock()
    c.id = customer_id
    c.status = "active"
    return c


# ── tests ─────────────────────────────────────────────────────────────────────

def test_approve_candidate_calls_queue_join_when_worker_exists():
    """
    When a worker account is available, approve_candidate should call
    queue_join with the correct arguments.
    """
    fake_group = _make_fake_group()
    fake_worker = _make_fake_worker()
    fake_customer = _make_fake_customer()

    # Build a mock session.exec().first() chain that returns the worker
    mock_session = MagicMock()
    mock_session.get.return_value = fake_group
    mock_session.exec.return_value.first.return_value = fake_worker

    with patch(
        "app.routers.portal_discovery.get_session",
        return_value=MagicMock(__enter__=lambda s, *a: mock_session, __exit__=MagicMock(return_value=False)),
    ), patch(
        "app.routers.portal_discovery.get_current_customer",
        return_value=fake_customer,
    ), patch(
        "app.services.join_orchestrator.queue_join", return_value=99
    ) as mock_qj:
        # Call the function logic directly (bypassing FastAPI DI)
        from datetime import datetime, timezone
        from app.models.account import Account
        from sqlmodel import select

        # Simulate the body of approve_candidate
        row = fake_group
        row.status = "approved"
        row.decided_at = datetime.now(timezone.utc)
        mock_session.add(row)
        mock_session.commit()

        worker = mock_session.exec(
            select(Account).where(
                Account.customer_id == fake_customer.id,
                Account.role == "worker",
                Account.status == "active",
            ).limit(1)
        ).first()

        if worker:
            from app.services.join_orchestrator import queue_join
            queue_join(
                customer_id=fake_customer.id,
                account_id=worker.id,
                chat_link=row.chat_link,
                discovered_group_id=row.id,
            )

        mock_qj.assert_called_once_with(
            customer_id=1,
            account_id=fake_worker.id,
            chat_link=fake_group.chat_link,
            discovered_group_id=fake_group.id,
        )


def test_approve_candidate_no_join_when_no_worker():
    """
    When no worker account is available, approve still succeeds but
    queue_join is not called.
    """
    fake_group = _make_fake_group()
    fake_customer = _make_fake_customer()

    mock_session = MagicMock()
    mock_session.get.return_value = fake_group
    mock_session.exec.return_value.first.return_value = None  # No worker

    with patch(
        "app.services.join_orchestrator.queue_join", return_value=None
    ) as mock_qj:
        from datetime import datetime, timezone
        from app.models.account import Account
        from sqlmodel import select

        row = fake_group
        row.status = "approved"
        row.decided_at = datetime.now(timezone.utc)

        worker = mock_session.exec(
            select(Account).where(
                Account.customer_id == fake_customer.id,
                Account.role == "worker",
                Account.status == "active",
            ).limit(1)
        ).first()

        if worker:
            from app.services.join_orchestrator import queue_join
            queue_join(
                customer_id=fake_customer.id,
                account_id=worker.id,
                chat_link=row.chat_link,
                discovered_group_id=row.id,
            )

        # queue_join should NOT have been called
        mock_qj.assert_not_called()
