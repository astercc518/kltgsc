"""
worker_persona_service — 单点入口取某 worker 账号的人设。

约定:
- 有 worker_personas 行 → 返回 DB 值 + source='db'
- 无 行 → 返回 DEFAULT_PERSONA 的副本 + source='fallback'

参考: spec §6.3 (兜底 Persona) + plan Phase 3a Task 1
"""
import copy
import logging
from typing import Optional

from sqlmodel import select

from app.core.group_reply_config import DEFAULT_PERSONA
from app.models.worker_persona import WorkerPersona

logger = logging.getLogger(__name__)


def get_persona_for_account(*, session, account_id: int) -> dict:
    """
    返回 dict (不是 ORM 对象), 字段统一好兜底, 便于下游纯函数消费。

    Schema (dict 形式, key 与 spec §4.2 / DEFAULT_PERSONA 一致):
      display_name, region, occupation, speaking_style,
      catchphrases, active_hours,
      daily_reply_quota, per_chat_daily_quota, per_chat_cooldown_minutes,
      daily_chitchat_quota,
      observation_window_seconds_range, typing_delay_seconds_range,
      source: 'db' | 'fallback'
    """
    row = session.exec(
        select(WorkerPersona).where(WorkerPersona.account_id == account_id)
    ).first()

    if row is None:
        result = copy.deepcopy(DEFAULT_PERSONA)
        result["source"] = "fallback"
        return result

    result = {
        "display_name": row.display_name or DEFAULT_PERSONA["display_name"],
        "region": row.region,
        "occupation": row.occupation,
        "speaking_style": row.speaking_style or "casual",
        "catchphrases": list(row.catchphrases or []),
        "active_hours": (
            dict(row.active_hours) if row.active_hours
            else copy.deepcopy(DEFAULT_PERSONA["active_hours"])
        ),
        "daily_reply_quota": int(row.daily_reply_quota or DEFAULT_PERSONA["daily_reply_quota"]),
        "per_chat_daily_quota": int(row.per_chat_daily_quota or DEFAULT_PERSONA["per_chat_daily_quota"]),
        "per_chat_cooldown_minutes": int(row.per_chat_cooldown_minutes or DEFAULT_PERSONA["per_chat_cooldown_minutes"]),
        "daily_chitchat_quota": int(row.daily_chitchat_quota or DEFAULT_PERSONA["daily_chitchat_quota"]),
        "observation_window_seconds_range": list(
            row.observation_window_seconds_range or DEFAULT_PERSONA["observation_window_seconds_range"]
        ),
        "typing_delay_seconds_range": list(
            row.typing_delay_seconds_range or DEFAULT_PERSONA["typing_delay_seconds_range"]
        ),
        "source": "db",
    }
    return result
