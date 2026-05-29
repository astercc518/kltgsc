"""
GroupDispatcher — 随机 typing 时延 + Telethon 发群 + billing 扣费。

参考: spec §2.1 + §8.1 集成点 3

桥接说明:
  _telethon_send_to_group: 按 account_id 从 DB 查 Account 对象，再调
      shill_dispatcher.send_message_with_client_reply(account, chat_id, text)
      该函数返回 (success: bool, msg_id_or_err) tuple。

  _charge_customer: 调用 feature_billing.charge(session, customer_id,
      slug='ai_marketing_group_reply', units=1,
      idempotency_key=f'group_reply:{pending_reply.id}')
      成功返回 WalletTransaction；余额不足或 feature 未开通则抛 Exception。
"""
import asyncio
import logging
import random
from datetime import datetime, timezone

from app.core.group_reply_config import BILLING_PER_REPLY_USD, TYPING_DELAY_SECONDS
from app.models.pending_reply import PendingReplyStatus

logger = logging.getLogger(__name__)


async def dispatch_send(pending_reply) -> None:
    """
    主入口: 等 typing 时延 → Telethon 发群 → 扣费 → 落 sent。

    失败时只 warn, status 由调用方在异常路径写。
    """
    delay = _pick_typing_delay()
    logger.info(
        "dispatch pending_reply id=%s: delaying %ss before send",
        pending_reply.id, delay,
    )
    await asyncio.sleep(delay)

    sent_ok = await _telethon_send_to_group(
        account_id=pending_reply.responder_account_id,
        chat_id=pending_reply.chat_id,
        text=pending_reply.reply_text,
    )

    if not sent_ok:
        logger.warning("dispatch send failed pending_reply id=%s", pending_reply.id)
        await _mark_status(pending_reply, PendingReplyStatus.FAILED, skip_reason="send_failed")
        return

    charged = await _charge_customer(pending_reply=pending_reply, amount_usd=BILLING_PER_REPLY_USD)
    if not charged:
        logger.warning(
            "billing charge failed pending_reply id=%s (kept as sent)", pending_reply.id
        )

    await _mark_status(pending_reply, PendingReplyStatus.SENT, sent_at=datetime.now(timezone.utc))


def _pick_typing_delay() -> int:
    lo, hi = TYPING_DELAY_SECONDS
    return random.randint(lo, hi)


async def _telethon_send_to_group(*, account_id: int, chat_id: int, text: str) -> bool:
    """通过 account_id 从 DB 取 Account 对象，再调 shill_dispatcher.send_message_with_client_reply。

    shill_dispatcher.send_message_with_client_reply(account, chat_id, text)
    返回 (success: bool, msg_id_or_error)。取 success 作为返回值。
    """
    from sqlmodel import Session, select
    from app.core.db import engine
    from app.models.account import Account
    from app.services import shill_dispatcher

    try:
        with Session(engine) as session:
            account = session.exec(
                select(Account).where(Account.id == account_id)
            ).first()

        if account is None:
            logger.warning("_telethon_send_to_group: account_id=%s not found", account_id)
            return False

        success, _res = await shill_dispatcher.send_message_with_client_reply(
            account=account,
            chat_id=str(chat_id),
            text=text,
        )
        return bool(success)
    except Exception:
        logger.exception("telethon send failed for account_id=%s", account_id)
        return False


async def _charge_customer(*, pending_reply, amount_usd: float) -> bool:
    """调用 feature_billing.charge 扣费。

    使用 slug='ai_marketing_group_reply', units=1,
    idempotency_key=f'group_reply:{pending_reply.id}'。

    注意: amount_usd 参数由调用方传入 (BILLING_PER_REPLY_USD = $0.50)，
    但 feature_billing.charge 以 cents 计价，单价由 FeatureRegistry 配置决定。
    amount_usd 在此仅用于日志记录；实际扣费金额由 registry 的 unit_price_cents 决定。
    """
    from sqlmodel import Session
    from app.core.db import engine
    from app.services import feature_billing

    try:
        with Session(engine) as session:
            feature_billing.charge(
                session=session,
                customer_id=pending_reply.customer_id,
                slug="ai_marketing_group_reply",
                units=1,
                idempotency_key=f"group_reply:{pending_reply.id}",
                description=f"Group AI reply pending_reply#{pending_reply.id}",
            )
        return True
    except Exception:
        logger.exception(
            "billing charge failed for pending_reply id=%s customer_id=%s",
            pending_reply.id, pending_reply.customer_id,
        )
        return False


async def _mark_status(pending_reply, status: PendingReplyStatus, **fields) -> None:
    """更新 pending_reply 行的 status + 其它字段, 持久化。

    使用 sync Session(engine) 模式，与 group_reply_pipeline._insert_pending_reply 一致。
    如果 pending_reply 是 MagicMock（测试中）或 id 为 None，跳过 DB 写入。
    """
    from sqlmodel import Session
    from app.core.db import engine
    from app.models.pending_reply import PendingReply

    pending_reply.status = status.value
    for k, v in fields.items():
        setattr(pending_reply, k, v)

    pr_id = getattr(pending_reply, "id", None)
    if pr_id is None:
        return

    try:
        with Session(engine) as session:
            db_row = session.get(PendingReply, pr_id)
            if db_row is None:
                return
            db_row.status = status.value
            for k, v in fields.items():
                setattr(db_row, k, v)
            session.add(db_row)
            session.commit()
    except Exception:
        logger.exception("_mark_status failed for pending_reply id=%s", pr_id)
