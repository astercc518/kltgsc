"""
Celery beat 任务: 每 30s 扫到期 pending_replies → RiskController → Composer → Dispatch。

参考: spec §2.1

DB 查询使用同步 Session(engine) 模式，与 Task 7 (group_reply_pipeline) 一致。
get_session() (async) 不在此处使用。
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta

from sqlmodel import Session, select

from app.core.celery_app import celery_app
from app.core.db import engine
from app.core.group_reply_config import DEFAULT_PERSONA, SCAN_INTERVAL_SECONDS
from app.models.account import Account
from app.models.pending_reply import PendingReply, PendingReplyStatus
from app.services.reply_composer import compose_reply_phase1
from app.services.risk_controller import decide_phase1
from app.services.group_dispatcher import dispatch_send

logger = logging.getLogger(__name__)


async def scan_and_process_due_replies() -> int:
    """主入口。返回处理条数。"""
    due = await _fetch_due_pending_replies()
    if not due:
        return 0

    processed = 0
    for pr in due:
        try:
            await _process_one(pr)
            processed += 1
        except Exception:
            logger.exception("scanner failed to process pending_reply id=%s", pr.id)
    return processed


async def _process_one(pr: PendingReply) -> None:
    inputs = await _gather_risk_inputs(pr)
    decision = decide_phase1(
        pending=pr,
        candidate_accounts=inputs.get("candidate_accounts", []),
        same_lead_sent_within_48h=inputs.get("same_lead_sent_within_48h", []),
        account_daily_sent_count=inputs.get("account_daily_sent_count", {}),
        account_last_sent_in_chat=inputs.get("account_last_sent_in_chat", {}),
        cooldown_minutes=DEFAULT_PERSONA["per_chat_cooldown_minutes"],
        daily_quota=DEFAULT_PERSONA["daily_reply_quota"],
    )

    if decision.action == "skip":
        await _mark_status(pr, decision.skip_reason)
        return

    # compose 路径
    pr.responder_account_id = decision.responder_account_id
    reply = await compose_reply_phase1(
        customer_id=pr.customer_id,
        source_text=pr.source_text,
        solution_topic=pr.source_text,  # Phase 1 无 Layer 3, 用 source_text 兜底
    )
    if reply is None:
        # Phase 1: 失败 → status=failed (Phase 4 改 suggested)
        await _mark_status(pr, PendingReplyStatus.FAILED.value, skip_reason="compose_failed")
        return

    pr.reply_text = reply
    await dispatch_send(pr)


async def _fetch_due_pending_replies() -> list:
    """同步 Session(engine) 包装在 async 函数中，保持接口可 mock。"""
    now = datetime.now(timezone.utc)
    with Session(engine) as session:
        result = session.exec(
            select(PendingReply)
            .where(
                PendingReply.status == PendingReplyStatus.OBSERVING.value,
                PendingReply.fire_at <= now,
            )
            .order_by(PendingReply.fire_at)
            .limit(50)
        )
        return list(result.all())


async def _gather_risk_inputs(pr) -> dict:
    """聚合 RiskController 决策所需 DB 上下文。同步 Session(engine) 查询。"""
    now = datetime.now(timezone.utc)
    window_48h = now - timedelta(hours=48)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    with Session(engine) as session:
        # 候选 worker 账号 (同 customer + role=worker + active)
        candidate_accounts = list(session.exec(
            select(Account).where(
                Account.customer_id == pr.customer_id,
                Account.role == "worker",
                Account.status == "active",
            )
        ).all())

        # 同 (chat, source_user) 48h 内已发过的
        same_lead_sent = list(session.exec(
            select(PendingReply).where(
                PendingReply.chat_id == pr.chat_id,
                PendingReply.source_user_id == pr.source_user_id,
                PendingReply.status == PendingReplyStatus.SENT.value,
                PendingReply.sent_at >= window_48h,
                PendingReply.id != pr.id,
            )
        ).all())

        # 每个候选账号今日已发计数
        if candidate_accounts:
            sent_today_rows = list(session.exec(
                select(PendingReply).where(
                    PendingReply.status == PendingReplyStatus.SENT.value,
                    PendingReply.sent_at >= today_start,
                    PendingReply.responder_account_id.in_(
                        [a.id for a in candidate_accounts]
                    ),
                )
            ).all())
        else:
            sent_today_rows = []

        daily_count: dict = {}
        for row in sent_today_rows:
            daily_count[row.responder_account_id] = (
                daily_count.get(row.responder_account_id, 0) + 1
            )

        # 每个候选账号在本 chat 的最近发送时间
        last_sent_in_chat: dict = {}
        for acc in candidate_accounts:
            row = session.exec(
                select(PendingReply.sent_at).where(
                    PendingReply.responder_account_id == acc.id,
                    PendingReply.chat_id == pr.chat_id,
                    PendingReply.status == PendingReplyStatus.SENT.value,
                ).order_by(PendingReply.sent_at.desc()).limit(1)
            ).first()
            last_sent_in_chat[(acc.id, pr.chat_id)] = row if row else None

    return {
        "candidate_accounts": candidate_accounts,
        "same_lead_sent_within_48h": same_lead_sent,
        "account_daily_sent_count": daily_count,
        "account_last_sent_in_chat": last_sent_in_chat,
    }


async def _mark_status(pr, status_value: str, skip_reason: str | None = None) -> None:
    """更新 pending_reply 内存状态 + 持久化到 DB (sync Session)。"""
    pr.status = status_value
    if skip_reason and not pr.skip_reason:
        pr.skip_reason = skip_reason
    pr.decided_at = datetime.now(timezone.utc)

    pr_id = getattr(pr, "id", None)
    if pr_id is None:
        return

    try:
        with Session(engine) as session:
            db_row = session.get(PendingReply, pr_id)
            if db_row is None:
                return
            db_row.status = status_value
            if skip_reason and not db_row.skip_reason:
                db_row.skip_reason = skip_reason
            db_row.decided_at = pr.decided_at
            session.add(db_row)
            session.commit()
    except Exception:
        logger.exception("_mark_status failed for pending_reply id=%s", pr_id)


# === Celery task 包装 ===

@celery_app.task(name="group_reply_scanner.tick")
def scan_tick():
    """beat 调用入口。同步包装 async 主逻辑。"""
    return asyncio.run(scan_and_process_due_replies())
