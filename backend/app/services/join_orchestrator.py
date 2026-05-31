"""
join_orchestrator — 加群编排.

Phase 9 wires up the real Pyrogram join flow:

  pending → joining: short-lived Pyrogram client.join_chat(chat_link)
  joining → joined:  no captcha detected; lifecycle 'first_seen' recorded
  joining → captcha: captcha_detector returned non 'no_captcha'
  captcha → joined:  handler returned success
  captcha → failed:  handler failed AND captcha_attempts >= MAX_CAPTCHA_ATTEMPTS
  joining → failed:  client/network/permission error (no recovery this run)

The orchestrator owns ALL persistence; captcha handlers only return result dicts.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Session

from app.core.db import engine
from app.models.captcha_event import CaptchaEvent
from app.models.join_attempt import (
    JoinAttempt,
    STATUS_CAPTCHA,
    STATUS_FAILED,
    STATUS_JOINED,
    STATUS_JOINING,
    STATUS_PENDING,
)
from app.services.account_lifecycle_tracker import record_event

logger = logging.getLogger(__name__)

MAX_CAPTCHA_ATTEMPTS = 3
JOIN_OBSERVATION_SECONDS = 10
RECENT_MESSAGES_LIMIT = 5
ADMIN_DM_WINDOW_SECONDS = 60


def queue_join(
    *,
    customer_id: int,
    account_id: int,
    chat_link: str,
    discovered_group_id: Optional[int] = None,
) -> int:
    """Insert a pending join_attempt row. Returns join_attempt.id."""
    now = datetime.now(timezone.utc)
    attempt = JoinAttempt(
        customer_id=customer_id,
        account_id=account_id,
        chat_link=chat_link,
        discovered_group_id=discovered_group_id,
        status=STATUS_PENDING,
        captcha_attempts=0,
        created_at=now,
        updated_at=now,
    )
    with Session(engine) as session:
        session.add(attempt)
        session.commit()
        session.refresh(attempt)
    logger.info(
        "queue_join: id=%s customer=%s account=%s link=%s",
        attempt.id, customer_id, account_id, chat_link,
    )
    return attempt.id


async def process_attempt(*, attempt_id: int) -> str:
    """
    Process one join_attempt end-to-end. Returns final status string.

    Single-session pattern at each persistence boundary so concurrent scanner
    picks can't interleave between a status read and write.

    Order of operations:
      1. Claim the row by flipping pending|captcha → joining (atomically).
      2. Open a short-lived Pyrogram client, call join_chat.
      3. Sleep, fetch recent group messages + admin DMs, run detector.
      4. If no captcha → mark joined + first_seen.
      5. Otherwise dispatch handler. On handler success → joined + first_seen;
         on failure with attempts < MAX → stay in captcha for next scan;
         on failure with attempts >= MAX → failed + kicked_from_chat.
    """
    # ── 1. claim ──
    claim = _claim_for_processing(attempt_id)
    if claim is None:
        return "not_found"
    if claim["already_settled"]:
        return claim["status"]

    chat_link = claim["chat_link"]
    account_id = claim["account_id"]
    customer_id = claim["customer_id"]
    prior_attempts = claim["captcha_attempts"]

    # ── 2-5. real telegram work ──
    from app.services.pyrogram_client_manager import short_lived_client

    async with short_lived_client(account_id=account_id) as client:
        if client is None:
            _finalize_failed(attempt_id, account_id, reason="client_unavailable")
            return STATUS_FAILED

        join_result = await _do_join_chat(client, chat_link)
        if join_result["already_member"]:
            _finalize_joined(attempt_id, account_id)
            return STATUS_JOINED
        if not join_result["ok"]:
            _finalize_failed(
                attempt_id, account_id,
                reason=f"join_error:{join_result['error']}",
            )
            return STATUS_FAILED

        await asyncio.sleep(JOIN_OBSERVATION_SECONDS)

        try:
            recent, chat_id, admin_user_id = await _fetch_recent_messages(
                client, chat_link,
            )
            admin_dms = await _fetch_admin_dms(client)
        except Exception as exc:
            logger.exception("observe phase failed for attempt=%s", attempt_id)
            _finalize_failed(
                attempt_id, account_id, reason=f"observe_error:{exc}",
            )
            return STATUS_FAILED

        from app.services.captcha_detector import detect_captcha_type

        detection = detect_captcha_type(
            recent_messages=recent, admin_dms_after_join=admin_dms,
        )
        ctype = detection["type"]

        if ctype == "no_captcha":
            _finalize_joined(attempt_id, account_id, chat_id=chat_id)
            return STATUS_JOINED

        new_attempts = prior_attempts + 1
        _update_attempt(
            attempt_id=attempt_id,
            status=STATUS_CAPTCHA,
            captcha_type=ctype,
            captcha_attempts=new_attempts,
        )

        result = await _dispatch_handler(
            client=client,
            ctype=ctype,
            detection=detection,
            chat_id=chat_id,
            admin_user_id=admin_user_id,
            customer_id=customer_id,
        )

        _insert_captcha_event(
            join_attempt_id=attempt_id,
            handler=ctype,
            succeeded=bool(result.get("success")),
            input_summary=str(detection.get("evidence", ""))[:500],
            output_summary=str(result)[:500],
            error_message=result.get("error"),
        )

        if result.get("success"):
            _finalize_joined(attempt_id, account_id, chat_id=chat_id)
            return STATUS_JOINED

        if new_attempts >= MAX_CAPTCHA_ATTEMPTS:
            _finalize_failed(
                attempt_id, account_id,
                reason=f"captcha_failed:{ctype}:{result.get('error')}",
            )
            return STATUS_FAILED

        # Stay in CAPTCHA so the scanner picks us up again next tick.
        return STATUS_CAPTCHA


# ── internal helpers ─────────────────────────────────────────────────────────

def _claim_for_processing(attempt_id: int) -> Optional[dict]:
    """
    Atomically read & flip pending|captcha → joining.

    Returns None if row missing. Returns dict with already_settled=True if the
    row is already past the work-eligible state.
    """
    with Session(engine) as session:
        attempt = session.get(JoinAttempt, attempt_id)
        if attempt is None:
            logger.warning("process_attempt: attempt_id=%s not found", attempt_id)
            return None
        if attempt.status not in (STATUS_PENDING, STATUS_CAPTCHA):
            logger.info(
                "process_attempt: attempt_id=%s already status=%s",
                attempt_id, attempt.status,
            )
            return {"already_settled": True, "status": attempt.status}

        snapshot = {
            "already_settled": False,
            "chat_link": attempt.chat_link,
            "account_id": attempt.account_id,
            "customer_id": attempt.customer_id,
            "captcha_attempts": attempt.captcha_attempts or 0,
        }
        attempt.status = STATUS_JOINING
        attempt.updated_at = datetime.now(timezone.utc)
        session.add(attempt)
        session.commit()
    return snapshot


async def _do_join_chat(client, chat_link: str) -> dict:
    """
    Call pyrogram client.join_chat. Returns:
      {"ok": bool, "already_member": bool, "error": str | None}
    """
    try:
        await client.join_chat(chat_link)
        return {"ok": True, "already_member": False, "error": None}
    except Exception as exc:
        name = type(exc).__name__
        if "AlreadyParticipant" in name:
            return {"ok": True, "already_member": True, "error": None}
        return {"ok": False, "already_member": False, "error": f"{name}:{exc}"}


async def _fetch_recent_messages(client, chat_link: str):
    """
    Fetch the most recent N group messages after join.

    Returns: (list[detector_dict], chat_id, admin_user_id_or_None)
    """
    messages = []
    async for m in client.get_chat_history(chat_link, limit=RECENT_MESSAGES_LIMIT):
        messages.append(m)

    chat_id = None
    admin_user_id = None
    out = []
    for m in messages:
        chat_obj = getattr(m, "chat", None)
        if chat_id is None and chat_obj is not None:
            chat_id = getattr(chat_obj, "id", None)

        from_user = getattr(m, "from_user", None)
        is_bot = bool(getattr(from_user, "is_bot", False)) if from_user else False
        if admin_user_id is None and from_user is not None and not is_bot:
            uid = getattr(from_user, "id", None)
            if uid:
                admin_user_id = uid

        buttons_text = []
        rm = getattr(m, "reply_markup", None)
        if rm is not None:
            keyboard = getattr(rm, "inline_keyboard", None)
            if isinstance(keyboard, (list, tuple)):
                for row in keyboard:
                    for btn in row:
                        t = getattr(btn, "text", None)
                        if t:
                            buttons_text.append(t)

        out.append({
            "text": getattr(m, "text", None) or getattr(m, "caption", "") or "",
            "buttons": buttons_text,
            "has_photo": bool(getattr(m, "photo", None)),
            "from_bot": is_bot,
            "_message": m,  # kept so handlers can drive click/download on it
        })
    return out, chat_id, admin_user_id


async def _fetch_admin_dms(client) -> list[dict]:
    """
    Scan recent DMs (incoming) for messages received in the join window.

    Pyrogram does not expose a global 'recent DMs' iterator; we approximate by
    walking get_dialogs and reading the latest message of any private chat
    whose top message is within ADMIN_DM_WINDOW_SECONDS of now.
    """
    cutoff = datetime.now(timezone.utc).timestamp() - ADMIN_DM_WINDOW_SECONDS
    out: list[dict] = []
    try:
        async for dialog in client.get_dialogs(limit=20):
            chat = getattr(dialog, "chat", None)
            if chat is None:
                continue
            chat_type = getattr(chat, "type", None)
            type_name = getattr(chat_type, "name", str(chat_type) or "")
            if "PRIVATE" not in type_name.upper():
                continue
            top = getattr(dialog, "top_message", None)
            if top is None:
                continue
            ts = getattr(top, "date", None)
            ts_epoch = ts.timestamp() if hasattr(ts, "timestamp") else 0
            if ts_epoch < cutoff:
                continue
            from_user = getattr(top, "from_user", None)
            uid = getattr(from_user, "id", None) if from_user else None
            text = getattr(top, "text", None) or getattr(top, "caption", "") or ""
            out.append({"text": text, "from_user_id": uid, "_message": top})
    except Exception as exc:
        logger.warning("fetch_admin_dms scan failed: %s", exc)
    return out


async def _dispatch_handler(
    *,
    client,
    ctype: str,
    detection: dict,
    chat_id,
    admin_user_id,
    customer_id: int,
) -> dict:
    """Route to the appropriate captcha handler."""
    evidence = detection.get("evidence", {})

    if ctype == "inline_button":
        from app.services.captcha_handlers.inline_button import solve_inline_button
        raw_msg = evidence.get("message", {})
        msg = raw_msg.get("_message") if isinstance(raw_msg, dict) else raw_msg
        return await solve_inline_button(client=client, message=msg)

    if ctype == "vision_with_buttons":
        # Phase 12 hybrid: Gemini Vision reads the image and picks a button.
        from app.services.captcha_handlers.vision_button_hybrid import (
            solve_vision_button_hybrid,
        )
        raw_msg = evidence.get("message", {})
        msg = raw_msg.get("_message") if isinstance(raw_msg, dict) else raw_msg
        return await solve_vision_button_hybrid(client=client, message=msg)

    if ctype == "text_qa":
        from app.services.captcha_handlers.text_qa import solve_text_qa
        question = evidence.get("question", "")
        template = _customer_join_template(customer_id)
        return await solve_text_qa(
            client=client,
            chat_id=chat_id,
            question=question,
            customer_join_template=template,
        )

    if ctype == "vision":
        from app.services.captcha_handlers.vision import solve_vision
        raw_msg = evidence.get("message", {})
        msg = raw_msg.get("_message") if isinstance(raw_msg, dict) else raw_msg
        return await solve_vision(client=client, message=msg)

    if ctype == "admin_dm":
        from app.services.captcha_handlers.admin_dm import solve_admin_dm
        target_uid = admin_user_id
        if not target_uid:
            dms = evidence.get("dms", [])
            for d in dms:
                target_uid = d.get("from_user_id")
                if target_uid:
                    break
        template = _customer_intro_template(customer_id)
        return await solve_admin_dm(
            client=client,
            admin_user_id=target_uid or 0,
            customer_intro_template=template,
        )

    # ctype 'unknown' — no handler available, treat as failure
    return {"success": False, "error": f"unsupported_captcha_type:{ctype}"}


def _customer_join_template(customer_id: int) -> Optional[str]:
    """
    Look up the customer's text-Q&A join template (Phase 10 column).

    Returns the stripped template string when set, else None so the handler
    falls back to its built-in default ("我是行业内朋友推荐知道的").
    """
    from app.models.customer import Customer
    with Session(engine) as s:
        c = s.get(Customer, customer_id)
        if c is None:
            return None
        tmpl = getattr(c, "captcha_join_template", None)
        return tmpl.strip() if tmpl and tmpl.strip() else None


def _customer_intro_template(customer_id: int) -> Optional[str]:
    """
    Look up the customer's admin-DM intro template (Phase 10 column).

    Returns None when unset; admin_dm handler then short-circuits with
    'no_template_set' rather than DMing the admin with empty content.
    """
    from app.models.customer import Customer
    with Session(engine) as s:
        c = s.get(Customer, customer_id)
        if c is None:
            return None
        tmpl = getattr(c, "captcha_intro_template", None)
        return tmpl.strip() if tmpl and tmpl.strip() else None


def _finalize_joined(attempt_id: int, account_id: int, *, chat_id=None) -> None:
    """Mark joined + record lifecycle 'first_seen'."""
    _update_attempt(attempt_id=attempt_id, status=STATUS_JOINED, last_error=None)
    try:
        with Session(engine) as s:
            record_event(
                session=s,
                account_id=account_id,
                event_type="first_seen",
                chat_id=chat_id,
                reason="join_attempt_succeeded",
            )
    except Exception:
        logger.warning("lifecycle 'first_seen' failed", exc_info=True)


def _finalize_failed(attempt_id: int, account_id: int, *, reason: str) -> None:
    """Mark failed + record lifecycle 'kicked_from_chat'."""
    _update_attempt(
        attempt_id=attempt_id, status=STATUS_FAILED, last_error=reason[:500],
    )
    try:
        with Session(engine) as s:
            record_event(
                session=s,
                account_id=account_id,
                event_type="kicked_from_chat",
                reason=reason[:500],
            )
    except Exception:
        logger.warning("lifecycle 'kicked_from_chat' failed", exc_info=True)


def _update_attempt(*, attempt_id: int, **fields) -> None:
    """Sync helper: update arbitrary fields on a JoinAttempt row."""
    with Session(engine) as session:
        attempt = session.get(JoinAttempt, attempt_id)
        if attempt is None:
            logger.warning("_update_attempt: attempt_id=%s not found", attempt_id)
            return
        for k, v in fields.items():
            setattr(attempt, k, v)
        attempt.updated_at = datetime.now(timezone.utc)
        session.add(attempt)
        session.commit()


def _insert_captcha_event(
    *,
    join_attempt_id: int,
    handler: str,
    succeeded: bool,
    input_summary: str = "",
    output_summary: str = "",
    error_message: Optional[str] = None,
    metadata_json: Optional[dict] = None,
) -> None:
    """Sync helper: write a CaptchaEvent audit row."""
    with Session(engine) as session:
        evt = CaptchaEvent(
            join_attempt_id=join_attempt_id,
            handler=handler,
            input_summary=input_summary,
            output_summary=output_summary,
            succeeded=succeeded,
            error_message=error_message,
            metadata_json=metadata_json,
            created_at=datetime.now(timezone.utc),
        )
        session.add(evt)
        session.commit()
