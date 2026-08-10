"""
group_reply_pipeline — 群内 AI 销售员管线入口 (Phase 2a 三层版)。

Phase 1: msg → Layer 1 only → insert observing
Phase 2a: msg → Layer 1+2+3 → insert observing OR insert borderline

参考: spec §2.1
"""
import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlmodel import Session

from app.core.db import engine
from app.core.group_reply_config import DEFAULT_PERSONA, GROUP_AI_REPLY_ENABLED
from app.models.customer import Customer
from app.models.pending_reply import PendingReply, PendingReplyStatus
from app.services.lead_detector import run_all_layers

logger = logging.getLogger(__name__)


async def entrypoint(msg, account, monitor) -> dict:
    """
    Returns:
        {"skipped": <reason>} — Layer pass fail (non-borderline)
        {"skipped": "borderline", "pending_reply_id": <id>} — borderline (also written)
        {"pending_reply_id": <id>} — all layers pass, queued observing
    """
    if not GROUP_AI_REPLY_ENABLED:
        return {"skipped": "feature_off"}

    if getattr(account, "role", None) == "collector":
        return {"skipped": "collector_role"}

    customer_id = getattr(account, "customer_id", None)
    if customer_id is None:
        return {"skipped": "no_customer"}

    if getattr(monitor, "customer_id", None) is None:
        return {"skipped": "monitor_no_customer"}

    text = getattr(msg, "text", None) or ""
    if not text:
        return {"skipped": "empty_text"}

    with Session(engine) as session:
        customer = session.get(Customer, customer_id)
        if customer is None:
            return {"skipped": "customer_not_found"}

        result = await run_all_layers(
            session=session, customer=customer, monitor=monitor,
            text=text, chat_id=msg.chat_id,
        )

        if not result["pass"]:
            if result.get("borderline"):
                pr = _insert_borderline(
                    session=session,
                    customer_id=customer_id, monitor_id=monitor.id,
                    chat_id=msg.chat_id, message_id=msg.id,
                    source_user_id=msg.sender_id, source_text=text,
                    layer1_matched=result["layer1_matched"],
                    layer2_similarity=result["layer2_similarity"],
                    layer3=result.get("layer3"),
                    skip_reason=result["skip_reason"],
                )
                return {"skipped": "borderline", "pending_reply_id": pr.id}
            return {"skipped": result["skip_reason"]}

        # All layers pass → queue observing
        obs_min, obs_max = DEFAULT_PERSONA["observation_window_seconds_range"]
        obs_seconds = random.randint(obs_min, obs_max)
        pr = _insert_observing(
            session=session,
            customer_id=customer_id, monitor_id=monitor.id,
            chat_id=msg.chat_id, message_id=msg.id,
            source_user_id=msg.sender_id, source_text=text,
            layer1_matched=result["layer1_matched"],
            layer2_similarity=result["layer2_similarity"],
            layer3=result["layer3"],
            observation_window_seconds=obs_seconds,
        )
        logger.info(
            "pipeline: pending_reply id=%s queued (window=%ss, score=%s)",
            pr.id, obs_seconds, result["layer3"]["score"],
        )
        return {"pending_reply_id": pr.id}


def _insert_observing(
    *, session, customer_id, monitor_id, chat_id, message_id, source_user_id,
    source_text, layer1_matched, layer2_similarity, layer3, observation_window_seconds,
) -> PendingReply:
    now = datetime.now(timezone.utc)
    pr = PendingReply(
        customer_id=customer_id, monitor_id=monitor_id,
        chat_id=chat_id, message_id=message_id, source_user_id=source_user_id,
        source_text=source_text,
        layer1_matched={"matched": layer1_matched},
        layer2_similarity=layer2_similarity,
        layer3_score=layer3["score"],
        layer3_needs=layer3.get("extracted_needs", []),
        layer3_solution_topic=layer3.get("suggested_solution_topic", ""),
        layer3_confidence=layer3["confidence"],
        status=PendingReplyStatus.OBSERVING.value,
        fire_at=now + timedelta(seconds=observation_window_seconds),
        created_at=now,
    )
    session.add(pr)
    session.commit()
    session.refresh(pr)
    return pr


def _insert_borderline(
    *, session, customer_id, monitor_id, chat_id, message_id, source_user_id,
    source_text, layer1_matched, layer2_similarity, layer3, skip_reason,
) -> PendingReply:
    """borderline 写库供后续训练阈值, 不走 observing 流程。"""
    now = datetime.now(timezone.utc)
    pr = PendingReply(
        customer_id=customer_id, monitor_id=monitor_id,
        chat_id=chat_id, message_id=message_id, source_user_id=source_user_id,
        source_text=source_text,
        layer1_matched={"matched": layer1_matched},
        layer2_similarity=layer2_similarity,
        layer3_score=layer3.get("score") if layer3 else None,
        layer3_needs=layer3.get("extracted_needs", []) if layer3 else None,
        layer3_solution_topic=layer3.get("suggested_solution_topic", "") if layer3 else None,
        layer3_confidence=layer3.get("confidence") if layer3 else None,
        status=PendingReplyStatus.SKIPPED_BORDERLINE.value,
        skip_reason=skip_reason,
        created_at=now,
        decided_at=now,
    )
    session.add(pr)
    session.commit()
    session.refresh(pr)
    return pr
