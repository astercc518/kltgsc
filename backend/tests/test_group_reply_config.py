from app.core.group_reply_config import (
    DEFAULT_PERSONA, OBSERVATION_WINDOW_SECONDS, TYPING_DELAY_SECONDS,
    GROUP_AI_REPLY_ENABLED, BILLING_PER_REPLY_USD,
)


def test_default_persona_has_required_fields():
    required = {
        "display_name", "speaking_style", "daily_reply_quota",
        "per_chat_daily_quota", "per_chat_cooldown_minutes",
        "daily_chitchat_quota",
        "observation_window_seconds_range", "typing_delay_seconds_range",
    }
    assert required.issubset(DEFAULT_PERSONA.keys())


def test_default_persona_conservative_values():
    assert DEFAULT_PERSONA["daily_reply_quota"] == 3
    assert DEFAULT_PERSONA["per_chat_daily_quota"] == 1
    assert DEFAULT_PERSONA["per_chat_cooldown_minutes"] == 240
    assert DEFAULT_PERSONA["daily_chitchat_quota"] == 0


def test_billing_amount():
    assert BILLING_PER_REPLY_USD == 0.50


def test_observation_window_default_range():
    assert OBSERVATION_WINDOW_SECONDS == (60, 900)


def test_typing_delay_default_range():
    assert TYPING_DELAY_SECONDS == (30, 120)
