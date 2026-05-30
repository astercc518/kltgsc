"""PendingReply CRUD + status 状态机字段验证"""
import os
import pytest
from datetime import datetime, timezone, timedelta
from sqlmodel import Session, select

from app.models.pending_reply import PendingReply, PendingReplyStatus


def _skip_if_not_postgres():
    db = os.environ.get("DATABASE_URL", "")
    if not db.startswith(("postgresql", "postgres")):
        pytest.skip("requires Postgres")


def test_pending_reply_status_enum_values():
    """必须包含 spec §4.2 定义的全部 11 个状态"""
    expected = {
        "observing", "risk_check", "composing", "sent",
        "skipped_human_replied", "skipped_throttled", "skipped_dup",
        "skipped_borderline", "skipped_no_account", "failed", "suggested",
    }
    actual = {s.value for s in PendingReplyStatus}
    assert expected == actual, f"missing {expected - actual}, extras {actual - expected}"


def test_pending_reply_model_importable():
    """model 可 import, 字段完整"""
    fields = PendingReply.model_fields
    expected_fields = {
        "id", "customer_id", "monitor_id", "responder_account_id",
        "chat_id", "message_id", "source_user_id", "source_text",
        "layer1_matched", "layer2_similarity", "layer3_score",
        "layer3_needs", "layer3_solution_topic", "layer3_confidence",
        "status", "fire_at", "created_at", "decided_at", "sent_at",
        "skip_reason", "reply_text", "lead_id", "experiment_tag",
    }
    missing = expected_fields - set(fields.keys())
    assert not missing, f"missing fields: {missing}"


def test_pending_reply_create_with_observing_status(session):
    _skip_if_not_postgres()
    pr = PendingReply(
        customer_id=1, monitor_id=1,
        chat_id=-100123456, message_id=42, source_user_id=9999,
        source_text="想买 100k USDT",
        layer1_matched={"matched": ["USDT", "100k"]},
        status=PendingReplyStatus.OBSERVING.value,
        fire_at=datetime.now(timezone.utc) + timedelta(seconds=120),
        created_at=datetime.now(timezone.utc),
    )
    session.add(pr)
    session.commit()
    session.refresh(pr)
    try:
        assert pr.id is not None
        assert pr.status == PendingReplyStatus.OBSERVING.value
        assert pr.layer1_matched == {"matched": ["USDT", "100k"]}
    finally:
        # cleanup
        session.delete(pr)
        session.commit()
