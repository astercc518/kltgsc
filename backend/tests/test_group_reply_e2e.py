"""端到端: msg → pipeline → scanner → sent (mocks Telethon + LLM + billing)

完整路径:
  1. 创建 Customer / Account / KeywordMonitor 测试数据
  2. 调 group_reply_pipeline.entrypoint → 写 pending_replies (status=observing)
  3. fast-forward fire_at 到过期
  4. 调 scan_and_process_due_replies() (mock LLM + Telethon + billing)
  5. 断言 status='sent', reply_text 非空

架构说明:
  pipeline / scanner 内部均使用 Session(app.core.db.engine)，不经过 pytest
  的 session fixture。因此把 app.core.db.engine patch 成与 Postgres 相同的 engine，
  使两侧读写同一个库。

  PendingReply 使用 BigInteger 主键，SQLite 不支持自增 BigInteger，
  因此本测试在无 Postgres 时跳过（参见 test_pending_reply_model.py 同策略）。
"""
import os
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.pending_reply import PendingReply, PendingReplyStatus


# ---------------------------------------------------------------------------
# Skip guard (must be top-level so fixture collection also skips cleanly)
# ---------------------------------------------------------------------------

def _require_postgres():
    db = os.environ.get("DATABASE_URL", "")
    if not db.startswith(("postgresql", "postgres")):
        pytest.skip("E2E requires Postgres (BigInteger PK unsupported in SQLite)")


# ---------------------------------------------------------------------------
# Fixture: create temp DB rows, yield, clean up
# ---------------------------------------------------------------------------

@pytest.fixture
def e2e_fixtures():
    """
    Creates a fresh Postgres session + Customer / Account / KeywordMonitor.
    Patches app.core.db.engine to use the same Postgres engine so that
    pipeline/scanner/dispatcher reads/writes land in the same DB.
    Cleans up in FK-safe order after the test.
    """
    _require_postgres()

    from app.models.customer import Customer
    from app.models.account import Account
    from app.models.keyword_monitor import KeywordMonitor
    import app.core.db as _db
    import app.models  # noqa — ensure all tables are registered

    db_url = os.environ["DATABASE_URL"]
    test_engine = create_engine(db_url, pool_pre_ping=True)
    SQLModel.metadata.create_all(test_engine)

    with Session(test_engine) as session:
        # --- Customer ---
        customer = Customer(
            email="e2e_smoke_pytest@test.local",
            hashed_password="not-a-real-hash",
            name="E2E Smoke Customer",
        )
        session.add(customer)
        session.commit()
        session.refresh(customer)

        # --- Account (role=worker, status=active, customer-owned) ---
        account = Account(
            phone_number="+85299999999",
            session_string="",
            status="active",
            role="worker",
            customer_id=customer.id,
        )
        session.add(account)
        session.commit()
        session.refresh(account)

        # --- KeywordMonitor ---
        monitor = KeywordMonitor(
            keyword="USDT",
            match_type="partial",
            action_type="notify",
            customer_id=customer.id,
            keyword_filters={"include": ["USDT"], "exclude": [], "mode": "any"},
        )
        session.add(monitor)
        session.commit()
        session.refresh(monitor)

    # Capture IDs for later lookup/cleanup (avoid detached-instance issues).
    customer_id = customer.id
    account_id = account.id
    monitor_id = monitor.id

    # Patch app.core.db.engine so pipeline/scanner use the same test engine.
    _orig_engine = _db.engine
    _db.engine = test_engine

    try:
        yield customer_id, account_id, monitor_id, test_engine
    finally:
        _db.engine = _orig_engine

        # Cleanup in FK-safe order.
        with Session(test_engine) as s:
            for pr in s.exec(
                select(PendingReply).where(PendingReply.customer_id == customer_id)
            ).all():
                s.delete(pr)
            mon = s.get(KeywordMonitor, monitor_id)
            if mon:
                s.delete(mon)
            acc = s.get(Account, account_id)
            if acc:
                s.delete(acc)
            cust = s.get(Customer, customer_id)
            if cust:
                s.delete(cust)
            s.commit()

        test_engine.dispose()


# ---------------------------------------------------------------------------
# Fake Telethon message
# ---------------------------------------------------------------------------

class FakeMsg:
    def __init__(self, text, chat_id, message_id, sender_id):
        self.text = text
        self.chat_id = chat_id
        self.id = message_id
        self.sender_id = sender_id


# ---------------------------------------------------------------------------
# E2E test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_e2e_happy_path(e2e_fixtures):
    """Full pipeline: msg hit → pending_reply observing → scanner → sent."""
    customer_id, account_id, monitor_id, test_engine = e2e_fixtures

    # Re-fetch live objects from the test DB.
    from app.models.account import Account
    from app.models.keyword_monitor import KeywordMonitor

    with Session(test_engine) as s:
        account = s.get(Account, account_id)
        monitor = s.get(KeywordMonitor, monitor_id)

    fake_msg = FakeMsg(
        text="求 USDT 100k 渠道",
        chat_id=-100999888,
        message_id=99999,
        sender_id=8888888,
    )

    # ── Act 1: pipeline entrypoint ──────────────────────────────────────────
    from app.services import group_reply_pipeline
    with patch("app.services.group_reply_pipeline.GROUP_AI_REPLY_ENABLED", True):
        result = await group_reply_pipeline.entrypoint(fake_msg, account, monitor)

    assert "pending_reply_id" in result, (
        f"expected pending_reply_id in result, got {result}"
    )
    pr_id = result["pending_reply_id"]

    # Verify row exists with status=observing.
    with Session(test_engine) as s:
        pr = s.get(PendingReply, pr_id)
        assert pr is not None, f"PendingReply id={pr_id} not found in DB"
        assert pr.status == PendingReplyStatus.OBSERVING.value, (
            f"expected observing, got {pr.status}"
        )

    # ── Fast-forward fire_at ────────────────────────────────────────────────
    with Session(test_engine) as s:
        pr_db = s.get(PendingReply, pr_id)
        pr_db.fire_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        s.add(pr_db)
        s.commit()

    # ── Act 2: scanner ──────────────────────────────────────────────────────
    from app.workers.group_reply_scanner import scan_and_process_due_replies

    with patch(
        "app.services.reply_composer.kb_retrieve_top_k",
        new=AsyncMock(return_value=[{"text": "USDT 大额场外", "score": 0.9}]),
    ), patch(
        "app.services.reply_composer.llm_generate_reply",
        new=AsyncMock(return_value="USDT 大额 T+0 直接到账 私聊我"),
    ), patch(
        "app.services.group_dispatcher._telethon_send_to_group",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.services.group_dispatcher._charge_customer",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.services.group_dispatcher.asyncio.sleep", new=AsyncMock()
    ):
        n = await scan_and_process_due_replies()

    assert n == 1, f"scanner should process 1 row, got {n}"

    # ── Assert: status=sent, reply_text set ────────────────────────────────
    with Session(test_engine) as s:
        pr_final = s.get(PendingReply, pr_id)
        assert pr_final is not None
        assert pr_final.status == PendingReplyStatus.SENT.value, (
            f"expected sent, got {pr_final.status}"
        )
        assert pr_final.reply_text is not None, (
            "reply_text should not be None after send"
        )
        assert "USDT" in pr_final.reply_text, (
            f"reply_text should contain USDT, got: {pr_final.reply_text}"
        )
