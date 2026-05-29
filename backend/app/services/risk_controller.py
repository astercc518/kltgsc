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


# ---------------------------------------------------------------------------
# Phase 3: active_hours + 真人接话 + 加权随机选号
# ---------------------------------------------------------------------------
import random  # noqa: E402


@dataclass
class ActiveHoursResult:
    in_window: bool
    next_window_start: Optional[datetime]  # in_window=False 时, 下次开窗时间


WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _is_within_active_hours(persona: dict, now: datetime) -> ActiveHoursResult:
    """
    按 persona.active_hours 判断当前时间是否在窗口内。

    active_hours 格式: {"mon": [[9, 18]], ...}
    时间用 UTC 简化处理 (Phase 3a 不做时区精细化)。

    Returns:
        in_window=True, next_window_start=None
        或 in_window=False, next_window_start=<下次开窗的 datetime>
    """
    hours_map = persona.get("active_hours") or {}
    weekday = now.weekday()  # 0=Mon
    today_key = WEEKDAYS[weekday]
    today_windows = hours_map.get(today_key, [])
    hour = now.hour
    for start_h, end_h in today_windows:
        if start_h <= hour < end_h:
            return ActiveHoursResult(in_window=True, next_window_start=None)

    # 不在窗口 → 找下次开窗
    # 今日剩余窗口
    for start_h, end_h in today_windows:
        if start_h > hour:
            target = now.replace(hour=start_h, minute=0, second=0, microsecond=0)
            return ActiveHoursResult(in_window=False, next_window_start=target)

    # 未来 7 天找最近开窗
    for offset in range(1, 8):
        future = now + timedelta(days=offset)
        future_key = WEEKDAYS[future.weekday()]
        future_windows = hours_map.get(future_key, [])
        if future_windows:
            start_h = future_windows[0][0]
            target = future.replace(hour=start_h, minute=0, second=0, microsecond=0)
            return ActiveHoursResult(in_window=False, next_window_start=target)

    # 一周无窗口 (极端配置) → 推迟 24h 兜底
    return ActiveHoursResult(
        in_window=False, next_window_start=now + timedelta(hours=24),
    )


@dataclass
class RiskDecisionPhase3:
    action: str                        # 'compose' | 'skip' | 'postpone'
    skip_reason: Optional[str] = None
    responder_account_id: Optional[int] = None
    postpone_to: Optional[datetime] = None


def decide_phase3(
    *,
    pending,
    candidate_accounts: list,
    personas_by_account: dict,            # {acc_id: persona_dict}
    same_lead_sent_within_48h: list,
    account_daily_sent_count: dict,
    account_last_sent_in_chat: dict,
    human_reply_signal: dict,              # from human_reply_detector
    seed: Optional[int] = None,
) -> RiskDecisionPhase3:
    """
    Phase 3a 决策序列:
      1. 活跃窗口检查 (所有候选都不在 → postpone)
      2. 真人接话检测 (detected → skip)
      3. 同线索 48h 去重
      4. 候选过滤 (active_hours + 日额 + cooldown)
      5. 加权随机选号
    """
    now = datetime.now(timezone.utc)

    if not candidate_accounts:
        return RiskDecisionPhase3(
            action="skip",
            skip_reason=PendingReplyStatus.SKIPPED_NO_ACCOUNT.value,
        )

    # 规则 1: 活跃窗口 (整体检查)
    in_window_accounts = []
    earliest_next_open = None
    for acc in candidate_accounts:
        p = personas_by_account.get(acc.id, {})
        ah = _is_within_active_hours(p, now)
        if ah.in_window:
            in_window_accounts.append(acc)
        elif ah.next_window_start:
            if earliest_next_open is None or ah.next_window_start < earliest_next_open:
                earliest_next_open = ah.next_window_start

    if not in_window_accounts:
        if earliest_next_open is None:
            # fallback 推迟 1h
            earliest_next_open = now + timedelta(hours=1)
        # 加 0-30min 随机抖动
        jitter = random.Random(seed).randint(0, 1800)
        return RiskDecisionPhase3(
            action="postpone",
            postpone_to=earliest_next_open + timedelta(seconds=jitter),
        )

    # 规则 2: 真人接话
    if human_reply_signal.get("detected"):
        return RiskDecisionPhase3(
            action="skip",
            skip_reason=PendingReplyStatus.SKIPPED_HUMAN_REPLIED.value,
        )

    # 规则 3: 同线索 48h 去重
    if same_lead_sent_within_48h:
        return RiskDecisionPhase3(
            action="skip",
            skip_reason=PendingReplyStatus.SKIPPED_DUP.value,
        )

    # 规则 4: 配额 + cooldown 过滤
    eligible = []
    for acc in in_window_accounts:
        p = personas_by_account.get(acc.id, {})
        sent_today = account_daily_sent_count.get(acc.id, 0)
        quota = p.get("daily_reply_quota", 3)
        if sent_today >= quota:
            continue
        last_sent = account_last_sent_in_chat.get((acc.id, pending.chat_id))
        cooldown_min = p.get("per_chat_cooldown_minutes", 240)
        if last_sent is not None:
            if (now - last_sent) < timedelta(minutes=cooldown_min):
                continue
        eligible.append((acc, p, sent_today))

    if not eligible:
        return RiskDecisionPhase3(
            action="skip",
            skip_reason=PendingReplyStatus.SKIPPED_THROTTLED.value,
        )

    # 规则 5: 加权随机
    weights = []
    for acc, p, sent_today in eligible:
        quota = p.get("daily_reply_quota", 3)
        remaining = max(1, quota - sent_today)
        last_sent = account_last_sent_in_chat.get((acc.id, pending.chat_id))
        if last_sent is None:
            time_score = 1.0
        else:
            elapsed_min = (now - last_sent).total_seconds() / 60
            cooldown_min = p.get("per_chat_cooldown_minutes", 240)
            time_score = min(1.0, elapsed_min / max(cooldown_min, 1) / 2)
        weights.append(remaining * 0.5 + time_score * remaining * 0.5)

    rng = random.Random(seed)
    chosen_idx = rng.choices(range(len(eligible)), weights=weights, k=1)[0]
    chosen_acc = eligible[chosen_idx][0]
    return RiskDecisionPhase3(
        action="compose",
        responder_account_id=chosen_acc.id,
    )
