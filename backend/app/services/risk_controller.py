"""
RiskController — pending_reply 决策中央。

Phase 1: 3 条规则
  ① 同线索 48h 去重
  ② 账号日额配额
  ③ 同账号同群 cooldown

Phase 2/3 升级: 真人接话检测 (Phase 3) + active_hours (Phase 3)
              + 加权随机选号 (Phase 3) + Layer 2/3 边界值 (Phase 2)

参考: spec §5
"""
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional

from app.models.pending_reply import PendingReplyStatus


@dataclass
class RiskDecision:
    action: str                              # 'compose' | 'skip'
    skip_reason: Optional[str] = None        # PendingReplyStatus value (skipped_*)
    responder_account_id: Optional[int] = None


def decide_phase1(
    *,
    pending,                                 # PendingReply 实例
    candidate_accounts: list,                # list[Account] 同 customer 的 worker
    same_lead_sent_within_48h: list,         # list[PendingReply] (status=sent, 同 chat+user)
    account_daily_sent_count: dict,          # {account_id: count_today}
    account_last_sent_in_chat: dict,         # {(account_id, chat_id): Optional[datetime]}
    cooldown_minutes: int,
    daily_quota: int,
) -> RiskDecision:
    """Phase 1 决策序列。返回 RiskDecision。"""

    # 规则 ①: 同线索 48h 去重
    if same_lead_sent_within_48h:
        return RiskDecision(
            action="skip",
            skip_reason=PendingReplyStatus.SKIPPED_DUP.value,
        )

    # 规则 ②/③: 筛符合配额 + cooldown 的候选
    now = datetime.now(timezone.utc)
    eligible = []
    for acc in candidate_accounts:
        sent_today = account_daily_sent_count.get(acc.id, 0)
        if sent_today >= daily_quota:
            continue

        last_sent = account_last_sent_in_chat.get((acc.id, pending.chat_id))
        if last_sent is not None:
            elapsed = now - last_sent
            if elapsed < timedelta(minutes=cooldown_minutes):
                continue

        eligible.append(acc)

    if not candidate_accounts:
        return RiskDecision(
            action="skip",
            skip_reason=PendingReplyStatus.SKIPPED_NO_ACCOUNT.value,
        )

    if not eligible:
        return RiskDecision(
            action="skip",
            skip_reason=PendingReplyStatus.SKIPPED_THROTTLED.value,
        )

    # Phase 1: 取第一个 (Phase 3 升级为加权随机)
    chosen = eligible[0]
    return RiskDecision(action="compose", responder_account_id=chosen.id)
