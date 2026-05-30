"""
Tests for JoinAttempt and CaptchaEvent SQLModels (Phase 8 Task 1).

test_models_importable  — pure import/attribute check, no DB required
test_migration_round_trip — alembic upgrade/downgrade/upgrade (Postgres only)
"""
import os
import pytest


def test_models_importable():
    from app.models.join_attempt import JoinAttempt, STATUS_PENDING, STATUS_JOINED, STATUS_FAILED
    from app.models.captcha_event import CaptchaEvent, HANDLER_INLINE_BUTTON, HANDLER_TEXT_QA

    assert JoinAttempt.__tablename__ == "join_attempt"
    assert CaptchaEvent.__tablename__ == "captcha_event"

    # Verify key fields exist on JoinAttempt
    ja_fields = JoinAttempt.model_fields
    for field in (
        "customer_id", "account_id", "discovered_group_id",
        "chat_link", "status", "captcha_type", "captcha_attempts",
        "last_error", "metadata_json", "created_at", "updated_at",
    ):
        assert field in ja_fields, f"JoinAttempt missing field: {field}"

    # Verify status constants
    assert STATUS_PENDING == "pending"
    assert STATUS_JOINED == "joined"
    assert STATUS_FAILED == "failed"

    # Verify key fields exist on CaptchaEvent
    ce_fields = CaptchaEvent.model_fields
    for field in (
        "join_attempt_id", "handler", "input_summary",
        "output_summary", "succeeded", "error_message",
        "metadata_json", "created_at",
    ):
        assert field in ce_fields, f"CaptchaEvent missing field: {field}"

    # Verify handler constants
    assert HANDLER_INLINE_BUTTON == "inline_button"
    assert HANDLER_TEXT_QA == "text_qa"


def test_migration_round_trip():
    db = os.environ.get("DATABASE_URL", "")
    if not db.startswith(("postgresql", "postgres")):
        pytest.skip("requires Postgres")

    import subprocess
    cwd = os.path.join(os.path.dirname(__file__), "..")
    subprocess.run(["alembic", "upgrade", "head"], cwd=cwd, check=True)
    subprocess.run(["alembic", "downgrade", "-1"], cwd=cwd, check=True)
    subprocess.run(["alembic", "upgrade", "head"], cwd=cwd, check=True)
