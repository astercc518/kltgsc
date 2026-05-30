"""worker_persona_service: 取 account 的 persona, 没有则 fallback default"""
from unittest.mock import patch, MagicMock

from app.services.worker_persona_service import get_persona_for_account


def test_get_persona_returns_db_when_exists():
    fake_session = MagicMock()
    fake_persona = MagicMock(
        account_id=10, customer_id=1, display_name="阿强",
        speaking_style="casual", daily_reply_quota=5,
        per_chat_daily_quota=2, per_chat_cooldown_minutes=120,
        daily_chitchat_quota=7,
        observation_window_seconds_range=[60, 900],
        typing_delay_seconds_range=[30, 120],
        active_hours={"mon": [[9, 18]]}, catchphrases=["搞不好"],
        region="香港", occupation="OTC 中介",
    )
    fake_session.exec.return_value.first.return_value = fake_persona
    p = get_persona_for_account(session=fake_session, account_id=10)
    assert p["display_name"] == "阿强"
    assert p["daily_reply_quota"] == 5
    assert p["catchphrases"] == ["搞不好"]
    assert p.get("source") == "db"


def test_get_persona_returns_fallback_when_missing():
    fake_session = MagicMock()
    fake_session.exec.return_value.first.return_value = None
    p = get_persona_for_account(session=fake_session, account_id=999)
    # 兜底是 DEFAULT_PERSONA 的副本
    assert p["display_name"] == "用户"
    assert p["daily_reply_quota"] == 3
    assert p["per_chat_daily_quota"] == 1
    assert p["per_chat_cooldown_minutes"] == 240
    assert p["daily_chitchat_quota"] == 0
    assert p.get("source") == "fallback"


def test_get_persona_normalizes_active_hours_into_dict():
    """DB 里若 active_hours 是 None, 兜底用 default"""
    fake_session = MagicMock()
    fake_persona = MagicMock(
        account_id=10, customer_id=1, display_name="x",
        speaking_style="casual", daily_reply_quota=5,
        per_chat_daily_quota=2, per_chat_cooldown_minutes=120,
        daily_chitchat_quota=7,
        observation_window_seconds_range=[60, 900],
        typing_delay_seconds_range=[30, 120],
        active_hours=None,  # 故意 None
        catchphrases=None,
        region=None, occupation=None,
    )
    fake_session.exec.return_value.first.return_value = fake_persona
    p = get_persona_for_account(session=fake_session, account_id=10)
    assert isinstance(p["active_hours"], dict)
    assert "mon" in p["active_hours"]
    assert p["catchphrases"] == []
