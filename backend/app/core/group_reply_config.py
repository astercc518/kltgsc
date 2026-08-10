"""群内 AI 销售员管线 Phase 1 共享配置 + 兜底 persona。

参考: docs/superpowers/specs/2026-05-28-group-ai-sales-presence-design.md §6.3
"""
import os


GROUP_AI_REPLY_ENABLED = os.getenv("GROUP_AI_REPLY_ENABLED", "false").lower() == "true"

BILLING_PER_REPLY_USD = 0.50

OBSERVATION_WINDOW_SECONDS = (60, 900)
TYPING_DELAY_SECONDS = (30, 120)

DEFAULT_PERSONA = {
    "display_name": "用户",
    "region": None,
    "occupation": None,
    "speaking_style": "casual",
    "catchphrases": [],
    "active_hours": {
        "mon": [[9, 22]], "tue": [[9, 22]], "wed": [[9, 22]],
        "thu": [[9, 22]], "fri": [[9, 22]], "sat": [[10, 20]], "sun": [[10, 20]],
    },
    "daily_reply_quota": 3,
    "per_chat_daily_quota": 1,
    "per_chat_cooldown_minutes": 240,
    "daily_chitchat_quota": 0,
    "observation_window_seconds_range": [120, 900],
    "typing_delay_seconds_range": [45, 120],
}

SCAN_INTERVAL_SECONDS = 30
