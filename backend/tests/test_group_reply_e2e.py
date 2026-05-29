"""端到端: msg → pipeline (三层) → scanner → sent (mocks Telethon + LLM + billing)

完整路径:
  1. 创建 Customer (含 icp_profile_text + icp_profile_embedding + 低阈值)
     / Account / KeywordMonitor / WorkerPersona 测试数据
  2. 调 group_reply_pipeline.entrypoint → run_all_layers (Layer 1+2+3 全 mock)
     → 写 pending_replies (status=observing, layer3 字段已写入)
  3. fast-forward fire_at 到过期
  4. 调 scan_and_process_due_replies() (mock LLM reply + Telethon + billing +
     human_reply_detector + persona_rewriter)
  5. 断言 status='sent', reply_text 含 USDT + 结尾是 "咯" (persona 已应用),
     layer3_score/layer3_solution_topic 已写

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
from app.models.ab_experiment import ABExperiment


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
    Creates a fresh Postgres session + Customer / Account / KeywordMonitor /
    WorkerPersona (Phase 3a: 24/7 active_hours, daily_chitchat_quota=0).
    Customer includes icp_profile_text + icp_profile_embedding + lowered
    lead_detector_thresholds so mock data passes all three layers.
    Patches app.core.db.engine to use the same Postgres engine so that
    pipeline/scanner/dispatcher reads/writes land in the same DB.
    Cleans up in FK-safe order after the test.
    """
    _require_postgres()

    from app.models.customer import Customer
    from app.models.account import Account
    from app.models.keyword_monitor import KeywordMonitor
    from app.models.worker_persona import WorkerPersona
    import app.core.db as _db
    import app.models  # noqa — ensure all tables are registered

    db_url = os.environ["DATABASE_URL"]
    test_engine = create_engine(db_url, pool_pre_ping=True)
    SQLModel.metadata.create_all(test_engine)

    with Session(test_engine) as session:
        # --- Customer (Phase 2a: with ICP fields + lowered thresholds) ---
        customer = Customer(
            email="e2e_smoke_pytest@test.local",
            hashed_password="not-a-real-hash",
            name="E2E Smoke Customer",
            icp_profile_text="想找 USDT 大额买家",
            icp_profile_embedding=[0.5] * 768,
            lead_detector_thresholds={
                "layer2_sim": 0.3,    # lowered so mock cosine 0.5*0.5 passes
                "layer3_score": 50,   # lowered so mock score=80 passes
                "layer3_confidence": 0.5,  # lowered so mock confidence=0.9 passes
            },
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

        # --- Phase 3a: WorkerPersona (24/7 active window, no chitchat quota) ---
        persona = WorkerPersona(
            account_id=account.id,
            customer_id=customer.id,
            display_name="e2e",
            speaking_style="casual",
            catchphrases=[],
            active_hours={
                "mon": [[0, 24]], "tue": [[0, 24]], "wed": [[0, 24]],
                "thu": [[0, 24]], "fri": [[0, 24]], "sat": [[0, 24]], "sun": [[0, 24]],
            },
            daily_reply_quota=5,
            per_chat_daily_quota=2,
            per_chat_cooldown_minutes=0,   # no cooldown for test
            daily_chitchat_quota=0,        # don't trigger chitchat in e2e
        )
        session.add(persona)
        session.commit()
        session.refresh(persona)

        # --- Phase 4a: ABExperiment (scope=customer, single variant weight=1.0) ---
        ab_exp = ABExperiment(
            name="e2e_test",
            scope="customer",
            scope_value=customer.id,
            variants=[{"tag": "v1", "weight": 1.0, "params": {}}],
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        session.add(ab_exp)
        session.commit()
        session.refresh(ab_exp)

    # Capture IDs for later lookup/cleanup (avoid detached-instance issues).
    customer_id = customer.id
    account_id = account.id
    monitor_id = monitor.id
    persona_id = persona.id
    ab_experiment_id = ab_exp.id

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
            wp = s.get(WorkerPersona, persona_id)
            if wp:
                s.delete(wp)
            mon = s.get(KeywordMonitor, monitor_id)
            if mon:
                s.delete(mon)
            acc = s.get(Account, account_id)
            if acc:
                s.delete(acc)
            # Phase 4a: delete ABExperiment before Customer (scope_value → customer.id)
            ab = s.get(ABExperiment, ab_experiment_id)
            if ab:
                s.delete(ab)
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
    """Full Phase 3a pipeline: msg hit → 3-layer detection → observing → scanner → sent.

    Covers:
    - Layer 1 keyword match (USDT hit)
    - Layer 2 ICP embedding similarity (embed_text mocked)
    - Layer 3 LLM score (_score_lead mocked, returns score=80)
    - PendingReply written with layer3_score + layer3_solution_topic
    - Scanner: human_reply_detector returns detected=False (no human takeover)
    - Scanner: compose_reply_phase2a mocked, apply_persona appends "咯"
    - Dispatcher sends + charges (both mocked)
    - Final status=sent, reply_text contains USDT + ends with "咯" (persona applied)
    """
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

    # Layer 3 fake result (score=80, confidence=0.9 — both exceed lowered thresholds)
    fake_score = {
        "score": 80, "intent_type": "buy",
        "extracted_needs": ["100k USDT"],
        "suggested_solution_topic": "USDT 大额场外",
        "confidence": 0.9, "reason": "x",
    }

    # ── Act 1: pipeline entrypoint (all three layers mocked) ────────────────
    from app.services import group_reply_pipeline
    with patch("app.services.group_reply_pipeline.GROUP_AI_REPLY_ENABLED", True), \
         patch(
             "app.services.lead_detector.embed_text",
             return_value=[0.5] * 768,
         ), patch(
             "app.services.lead_detector._score_lead",
             new=AsyncMock(return_value=fake_score),
         ), patch(
             "app.services.lead_detector._fetch_kb_top3",
             new=AsyncMock(return_value=[]),
         ), patch(
             "app.services.lead_detector._fetch_recent_context",
             new=AsyncMock(return_value=[]),
         ):
        result = await group_reply_pipeline.entrypoint(fake_msg, account, monitor)

    assert "pending_reply_id" in result, (
        f"expected pending_reply_id in result, got {result}"
    )
    pr_id = result["pending_reply_id"]

    # Verify row exists with status=observing and layer3 fields populated.
    with Session(test_engine) as s:
        pr = s.get(PendingReply, pr_id)
        assert pr is not None, f"PendingReply id={pr_id} not found in DB"
        assert pr.status == PendingReplyStatus.OBSERVING.value, (
            f"expected observing, got {pr.status}"
        )
        # Phase 2a: layer3 fields should be written at pipeline time
        assert pr.layer3_score == 80, (
            f"expected layer3_score=80, got {pr.layer3_score}"
        )
        assert pr.layer3_solution_topic == "USDT 大额场外", (
            f"unexpected layer3_solution_topic: {pr.layer3_solution_topic}"
        )
        # Phase 4a: experiment_tag should be written (single-variant weight=1.0 → always v1)
        assert pr.experiment_tag == "e2e_test:v1", (
            f"expected experiment_tag='e2e_test:v1', got {pr.experiment_tag!r}"
        )

    # ── Fast-forward fire_at ────────────────────────────────────────────────
    with Session(test_engine) as s:
        pr_db = s.get(PendingReply, pr_id)
        pr_db.fire_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        s.add(pr_db)
        s.commit()

    # ── Act 2: scanner (reply composer + dispatcher + Phase 3 mocked) ────────
    from app.workers.group_reply_scanner import scan_and_process_due_replies

    with patch(
        "app.services.reply_composer.kb_retrieve_top_k",
        new=AsyncMock(return_value=[{"text": "USDT T+0", "score": 0.9}]),
    ), patch(
        "app.services.reply_composer.find_case_top_k",
        return_value=[],
    ), patch(
        "app.services.reply_composer.llm_generate_reply",
        new=AsyncMock(return_value="USDT 大额 T+0 直达 私聊"),
    ), patch(
        # Phase 3a: human-reply check — no takeover detected
        "app.workers.group_reply_scanner.has_human_or_other_account_replied",
        return_value={"detected": False, "reason": None, "matched_message_id": None},
    ), patch(
        # Phase 3a: phase3 calls phase2a internally — mock at call-site module
        "app.services.reply_composer.compose_reply_phase2a",
        new=AsyncMock(return_value="USDT 大额 T+0 100k 直达 私聊"),
    ), patch(
        # Phase 3a: apply_persona imported into reply_composer — mock local reference
        "app.services.reply_composer.apply_persona",
        side_effect=lambda text, persona, seed=None: text + "咯",
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

    # ── Assert: status=sent, reply_text set, layer3 fields intact ──────────
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
        # Phase 3a: persona was applied (apply_persona appended "咯" in mock)
        assert pr_final.reply_text.endswith("咯"), (
            f"reply_text should end with '咯' (persona applied), got: {pr_final.reply_text}"
        )
        # Phase 2a: layer3 fields survive the scanner round-trip
        assert pr_final.layer3_score == 80, (
            f"layer3_score should remain 80 after send, got {pr_final.layer3_score}"
        )
        assert pr_final.layer3_solution_topic == "USDT 大额场外", (
            f"layer3_solution_topic should survive, got {pr_final.layer3_solution_topic}"
        )


# ---------------------------------------------------------------------------
# Phase 4a: suggested path (compose_reply_phase3 → None → save_suggested_reply)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_e2e_compose_failure_routes_to_suggested(e2e_fixtures):
    """Phase 4a: when compose_reply_phase3 returns None the scanner saves a
    suggested draft (status='suggested', reply_text contains placeholder).

    Complements unit tests:
      - test_copilot_suggestion_service (save_suggested_reply persists correctly)
      - test_scanner_compose_failure_routes_to_copilot (calls save_suggested_reply)
    This test verifies the full DB round-trip in a real Postgres session.
    """
    customer_id, account_id, monitor_id, test_engine = e2e_fixtures

    from app.models.account import Account
    from app.models.keyword_monitor import KeywordMonitor

    with Session(test_engine) as s:
        account = s.get(Account, account_id)
        monitor = s.get(KeywordMonitor, monitor_id)

    fake_msg = FakeMsg(
        text="求 USDT 200k 紧急",
        chat_id=-100999777,
        message_id=88888,
        sender_id=7777777,
    )

    fake_score = {
        "score": 80, "intent_type": "buy",
        "extracted_needs": ["200k USDT"],
        "suggested_solution_topic": "USDT 大额场外",
        "confidence": 0.9, "reason": "x",
    }

    # ── Act 1: pipeline entrypoint (all three layers mocked) ────────────────
    from app.services import group_reply_pipeline
    with patch("app.services.group_reply_pipeline.GROUP_AI_REPLY_ENABLED", True), \
         patch(
             "app.services.lead_detector.embed_text",
             return_value=[0.5] * 768,
         ), patch(
             "app.services.lead_detector._score_lead",
             new=AsyncMock(return_value=fake_score),
         ), patch(
             "app.services.lead_detector._fetch_kb_top3",
             new=AsyncMock(return_value=[]),
         ), patch(
             "app.services.lead_detector._fetch_recent_context",
             new=AsyncMock(return_value=[]),
         ):
        result = await group_reply_pipeline.entrypoint(fake_msg, account, monitor)

    assert "pending_reply_id" in result, (
        f"expected pending_reply_id in result, got {result}"
    )
    pr_id = result["pending_reply_id"]

    # Phase 4a: experiment_tag should be written for this row too
    with Session(test_engine) as s:
        pr_check = s.get(PendingReply, pr_id)
        assert pr_check is not None
        assert pr_check.experiment_tag == "e2e_test:v1", (
            f"expected experiment_tag='e2e_test:v1', got {pr_check.experiment_tag!r}"
        )

    # ── Fast-forward fire_at ────────────────────────────────────────────────
    with Session(test_engine) as s:
        pr_db = s.get(PendingReply, pr_id)
        pr_db.fire_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        s.add(pr_db)
        s.commit()

    # ── Act 2: scanner with compose_reply_phase3 returning None ────────────
    from app.workers.group_reply_scanner import scan_and_process_due_replies

    with patch(
        "app.workers.group_reply_scanner.has_human_or_other_account_replied",
        return_value={"detected": False, "reason": None, "matched_message_id": None},
    ), patch(
        # compose returns None → triggers save_suggested_reply path
        "app.workers.group_reply_scanner.compose_reply_phase3",
        new=AsyncMock(return_value=None),
    ), patch(
        # avoid real WebSocket broadcast
        "app.services.copilot_suggestion_service._broadcast_ws",
        new=AsyncMock(return_value=None),
    ):
        n = await scan_and_process_due_replies()

    assert n == 1, f"scanner should process 1 row, got {n}"

    # ── Assert: status=suggested, reply_text contains fallback placeholder ──
    with Session(test_engine) as s:
        pr_final = s.get(PendingReply, pr_id)
        assert pr_final is not None
        assert pr_final.status == PendingReplyStatus.SUGGESTED.value, (
            f"expected suggested, got {pr_final.status}"
        )
        assert pr_final.reply_text is not None, (
            "reply_text should not be None after suggested save"
        )
        assert "AI 草稿生成失败" in pr_final.reply_text, (
            f"fallback placeholder missing from reply_text: {pr_final.reply_text!r}"
        )
