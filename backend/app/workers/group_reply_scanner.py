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
from app.core.group_reply_config import SCAN_INTERVAL_SECONDS
from app.models.account import Account
from app.models.pending_reply import PendingReply, PendingReplyStatus
from app.services.reply_composer import compose_reply_phase3
from app.services.risk_controller import decide_phase3
from app.services.group_dispatcher import dispatch_send
from app.services.copilot_suggestion_service import save_suggested_reply
from app.services.worker_persona_service import get_persona_for_account
from app.services.human_reply_detector import has_human_or_other_account_replied

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


def _generate_fallback_suggestion(pr) -> str:
    """没生成可发回复时, 给销售一个 placeholder 引导文。"""
    topic = pr.layer3_solution_topic or "业务"
    return (
        f"[AI 草稿生成失败] 客户在群里发: 「{pr.source_text}」. "
        f"主题: {topic}. 请人工写回复或忽略。"
    )


async def _process_one(pr: PendingReply) -> None:
    try:
        # 1. Gather phase3 inputs
        inputs = await _gather_risk_inputs_phase3(pr)

        # 2. Decide phase3
        decision = decide_phase3(
            pending=pr,
            candidate_accounts=inputs.get("candidate_accounts", []),
            personas_by_account=inputs.get("personas_by_account", {}),
            same_lead_sent_within_48h=inputs.get("same_lead_sent_within_48h", []),
            account_daily_sent_count=inputs.get("account_daily_sent_count", {}),
            account_last_sent_in_chat=inputs.get("account_last_sent_in_chat", {}),
            human_reply_signal=inputs.get("human_reply_signal", {"detected": False}),
        )

        # 3. Handle action
        if decision.action == "postpone":
            await _postpone_pending_reply(pr, decision.postpone_to)
            return

        if decision.action == "skip":
            await _mark_status(pr, decision.skip_reason or "skipped_unknown")
            return

        # action == "compose"
        pr.responder_account_id = decision.responder_account_id
        persona = inputs["personas_by_account"].get(decision.responder_account_id)

        topic = pr.layer3_solution_topic or pr.source_text
        with Session(engine) as session:
            reply = await compose_reply_phase3(
                customer_id=pr.customer_id,
                source_text=pr.source_text,
                solution_topic=topic,
                session=session,
                persona=persona,
            )
        if reply is None:
            # Phase 4a: compose 2 次反幻觉失败 → 走副驾驶兜底, 让销售改写
            suggested = _generate_fallback_suggestion(pr)
            await save_suggested_reply(pending_reply=pr, suggested_text=suggested)
            return

        pr.reply_text = reply
        await dispatch_send(pr)
    except Exception as e:
        logger.exception("scanner._process_one crashed for pr.id=%s", pr.id)
        try:
            await _mark_status(
                pr, PendingReplyStatus.FAILED.value,
                skip_reason=f"exception: {type(e).__name__}",
            )
        except Exception:
            logger.exception("also failed to mark status; pr may stay stuck")


async def _fetch_due_pending_replies() -> list:
    """Atomically claim due rows by flipping status observing → risk_check.

    Uses SELECT … FOR UPDATE SKIP LOCKED so concurrent beat ticks don't
    block each other and never pick the same row twice.  The status flip
    happens inside the same transaction as the lock acquisition, so by the
    time the lock is released the row is no longer visible to other ticks
    (which filter on status == 'observing').
    """
    now = datetime.now(timezone.utc)
    with Session(engine) as session:
        stmt = (
            select(PendingReply)
            .where(
                PendingReply.status == PendingReplyStatus.OBSERVING.value,
                PendingReply.fire_at <= now,
            )
            .order_by(PendingReply.fire_at)
            .limit(50)
            .with_for_update(skip_locked=True)
        )
        rows = list(session.exec(stmt).all())
        # Atomically flip status before releasing lock so other ticks skip these rows
        for pr in rows:
            pr.status = PendingReplyStatus.RISK_CHECK.value
            session.add(pr)
        session.commit()
        # Refresh + detach so callers can use objects outside the session
        for pr in rows:
            session.refresh(pr)
        for pr in rows:
            session.expunge(pr)
        return rows


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


async def _gather_risk_inputs_phase3(pr) -> dict:
    """Phase 3a 升级: 加 personas + human_reply_signal"""
    base = await _gather_risk_inputs(pr)
    candidate_accounts = base.get("candidate_accounts", [])

    with Session(engine) as session:
        personas_by_account = {
            acc.id: get_persona_for_account(session=session, account_id=acc.id)
            for acc in candidate_accounts
        }
        human_reply = has_human_or_other_account_replied(
            session=session,
            customer_id=pr.customer_id, chat_id=pr.chat_id,
            source_message_id=pr.message_id, source_user_id=pr.source_user_id,
            solution_topic=pr.layer3_solution_topic,
            since=pr.created_at, window_minutes=5,
        )

    base["personas_by_account"] = personas_by_account
    base["human_reply_signal"] = human_reply
    return base


async def _postpone_pending_reply(pr, fire_at) -> None:
    """更新 pr.fire_at, 维持 status=observing 让下一 tick 再扫"""
    with Session(engine) as session:
        obj = session.get(PendingReply, pr.id)
        if obj is None:
            logger.warning("postpone: pr %s not found", pr.id)
            return
        obj.fire_at = fire_at
        obj.status = PendingReplyStatus.OBSERVING.value
        session.add(obj)
        session.commit()


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
