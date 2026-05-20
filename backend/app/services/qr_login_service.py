"""
Epic 5.0 — Customer main-account QR login.

State machine per token:
    pending           — QR token issued, waiting for user to scan
    password_required — user scanned, account has 2FA, awaiting password
    success           — session captured, encrypted, Account row written
    expired           — token expired (120s default) without success
    error             — Pyrogram / encryption failure

In-memory `_qr_sessions[token]` holds the live Pyrogram client + asyncio
task during the login window. Final state is also mirrored to Redis
(`qr:<token>`) so polling endpoints don't need to touch the in-memory dict.

MOCK_QR_AUTOACCEPT=1 (env):
    bypasses Pyrogram entirely; start_qr returns a fake token+url+png and
    auto-completes after 1s with a synthetic session_string. Used by
    smoke_epic5_qr.py so the test suite doesn't need a real TG number.
"""
from __future__ import annotations

import asyncio
import base64
import io
import logging
import os
import secrets
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import redis
from sqlmodel import Session, select

from app.core.config import settings
from app.core.db import engine
from app.core.encryption import encrypt_session_string
from app.models.account import Account
from app.models.customer import Customer

logger = logging.getLogger(__name__)

QR_TIMEOUT_SECONDS = 120
QR_REDIS_PREFIX = "qr:"

STATE_PENDING = "pending"
STATE_PASSWORD_REQUIRED = "password_required"
STATE_SUCCESS = "success"
STATE_EXPIRED = "expired"
STATE_ERROR = "error"

MOCK_MODE = os.environ.get("MOCK_QR_AUTOACCEPT", "").strip() == "1"


# ── In-memory session registry ─────────────────────────────────────────

@dataclass
class _QRSession:
    token: str
    customer_id: int
    state: str
    qr_url: str
    expires_at: float
    client: Optional[object] = None        # Pyrogram Client or None in mock
    qr: Optional[object] = None            # QRLogin object
    password_event: Optional[asyncio.Event] = None
    password_value: Optional[str] = None
    error: Optional[str] = None
    task: Optional[asyncio.Task] = None


_sessions: dict[str, _QRSession] = {}
_redis: Optional[redis.Redis] = None


def _get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


def _redis_set_state(token: str, state: str, extra: Optional[dict] = None) -> None:
    payload = {"state": state, **(extra or {})}
    _get_redis().hset(QR_REDIS_PREFIX + token, mapping=payload)
    _get_redis().expire(QR_REDIS_PREFIX + token, QR_TIMEOUT_SECONDS + 60)


# ── QR-image helper ────────────────────────────────────────────────────

def _render_qr_png_b64(url: str) -> str:
    """Render the QR as a base64-encoded PNG; frontend can `<img src=data:...>`.

    We try `qrcode` if installed; otherwise return empty string and let the
    frontend render via its own qrcode component using qr.url.
    """
    try:
        import qrcode
        from qrcode.image.pil import PilImage
        img = qrcode.make(url)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception as e:  # noqa: BLE001
        logger.debug("qrcode lib unavailable, returning empty PNG: %s", e)
        return ""


# ── MOCK path (test fixture only) ──────────────────────────────────────

async def _mock_complete(session: _QRSession) -> None:
    """Pretend the user scanned the QR after 1s; fabricate a session_string."""
    await asyncio.sleep(1.0)
    fake_session = f"MOCK_SESSION_{secrets.token_hex(16)}"
    fake_phone = "+1" + str(int(time.time()))[-10:]
    fake_username = f"mockuser_{secrets.token_hex(3)}"
    try:
        _persist_main_account(
            customer_id=session.customer_id,
            session_string=fake_session,
            phone=fake_phone,
            first_name="Mock",
            last_name="User",
            username=fake_username,
            telegram_user_id=int(secrets.token_hex(4), 16),
        )
        session.state = STATE_SUCCESS
        _redis_set_state(session.token, STATE_SUCCESS,
                         {"username": fake_username, "phone_last4": fake_phone[-4:]})
        logger.info("QR mock: completed token=%s customer=%s",
                    session.token, session.customer_id)
    except Exception as e:  # noqa: BLE001
        session.state = STATE_ERROR
        session.error = repr(e)
        _redis_set_state(session.token, STATE_ERROR, {"error": str(e)})
        logger.exception("QR mock complete failed: %s", e)


# ── Real Pyrogram path ─────────────────────────────────────────────────

async def _run_qr_login(session: _QRSession, api_id: int, api_hash: str) -> None:
    """Background coroutine: drives the Pyrogram qr_login lifecycle."""
    try:
        from pyrogram import Client
        from pyrogram.errors import SessionPasswordNeeded
    except ImportError:
        session.state = STATE_ERROR
        session.error = "pyrogram not installed"
        _redis_set_state(session.token, STATE_ERROR, {"error": "pyrogram missing"})
        return

    try:
        client: Client = session.client  # type: ignore
        qr = session.qr

        # First wait — may raise SessionPasswordNeeded if account has 2FA
        try:
            signed_in = await qr.wait(timeout=QR_TIMEOUT_SECONDS)
        except SessionPasswordNeeded:
            session.state = STATE_PASSWORD_REQUIRED
            _redis_set_state(session.token, STATE_PASSWORD_REQUIRED)
            # Block until the customer submits the 2FA password
            await session.password_event.wait()
            try:
                signed_in = await client.check_password(session.password_value or "")
            except Exception as e:  # noqa: BLE001
                session.state = STATE_ERROR
                session.error = f"2FA check failed: {e!r}"
                _redis_set_state(session.token, STATE_ERROR,
                                 {"error": session.error})
                return

        # Capture session + identity
        me = await client.get_me()
        session_str = await client.export_session_string()
        await client.disconnect()

        _persist_main_account(
            customer_id=session.customer_id,
            session_string=session_str,
            phone=getattr(me, "phone_number", None) or "",
            first_name=getattr(me, "first_name", None),
            last_name=getattr(me, "last_name", None),
            username=getattr(me, "username", None),
            telegram_user_id=int(getattr(me, "id", 0)),
        )
        session.state = STATE_SUCCESS
        _redis_set_state(session.token, STATE_SUCCESS, {
            "username": getattr(me, "username", "") or "",
            "phone_last4": (getattr(me, "phone_number", "") or "")[-4:],
        })
        logger.info("QR login success: customer=%s username=%s",
                    session.customer_id, getattr(me, "username", "?"))
    except asyncio.TimeoutError:
        session.state = STATE_EXPIRED
        _redis_set_state(session.token, STATE_EXPIRED)
    except Exception as e:  # noqa: BLE001
        session.state = STATE_ERROR
        session.error = repr(e)
        _redis_set_state(session.token, STATE_ERROR, {"error": str(e)})
        logger.exception("QR login failed: %s", e)
    finally:
        # Drop strong references so GC can clean up after a short delay
        async def _cleanup():
            await asyncio.sleep(60)
            _sessions.pop(session.token, None)
        asyncio.create_task(_cleanup())


def _persist_main_account(
    *, customer_id: int, session_string: str,
    phone: str, first_name: Optional[str], last_name: Optional[str],
    username: Optional[str], telegram_user_id: int,
) -> Account:
    """Insert Account(role=main, is_customer_main=True, encrypted session) and
    point Customer.main_account_id at it.

    Idempotent at the customer level: if a main account already exists for the
    customer, the new session replaces it (old row disconnected).
    """
    encrypted = encrypt_session_string(session_string)
    with Session(engine) as s:
        customer = s.get(Customer, customer_id)
        if not customer:
            raise RuntimeError(f"customer {customer_id} not found")

        # Disconnect previous main, if any
        if customer.main_account_id:
            prev = s.get(Account, customer.main_account_id)
            if prev:
                prev.is_customer_main = False
                prev.status = "disconnected"
                s.add(prev)

        # The phone_number column is unique; use the real phone if available,
        # otherwise synthesize a stable placeholder tied to telegram_user_id
        # so two customers can't collide on empty/repeated phones.
        phone_value = phone or f"main:{telegram_user_id}"
        existing = s.exec(
            select(Account).where(Account.phone_number == phone_value)
        ).first()

        if existing:
            # Reuse the row (e.g., customer reconnects same phone) — overwrite session
            existing.session_string = encrypted
            existing.session_string_encrypted = True
            existing.is_customer_main = True
            existing.role = "main"
            existing.customer_id = customer_id
            existing.status = "active"
            account = existing
        else:
            account = Account(
                phone_number=phone_value,
                session_string=encrypted,
                session_string_encrypted=True,
                status="active",
                role="main",
                is_customer_main=True,
                combat_role="cannon",     # never used (excluded from listener/alloc)
                customer_id=customer_id,
                tags=f"main_account,customer_{customer_id}",
            )
        s.add(account)
        s.commit()
        s.refresh(account)

        customer.main_account_id = account.id
        customer.updated_at = datetime.utcnow()
        s.add(customer)
        s.commit()
        return account


# ── Public API (called by FastAPI endpoints) ───────────────────────────

async def start_qr(customer_id: int, api_id: int, api_hash: str) -> dict:
    """Initiate a QR login. Returns {token, qr_url, qr_png_b64, expires_at, state}."""
    token = uuid.uuid4().hex
    expires_at = time.time() + QR_TIMEOUT_SECONDS

    if MOCK_MODE:
        qr_url = f"tg://login?token=MOCK_{token[:12]}"
        sess = _QRSession(
            token=token, customer_id=customer_id, state=STATE_PENDING,
            qr_url=qr_url, expires_at=expires_at,
        )
        _sessions[token] = sess
        _redis_set_state(token, STATE_PENDING, {"mock": "1"})
        sess.task = asyncio.create_task(_mock_complete(sess))
        return {
            "token": token,
            "qr_url": qr_url,
            "qr_png_b64": _render_qr_png_b64(qr_url),
            "expires_at": expires_at,
            "state": STATE_PENDING,
            "mock": True,
        }

    # Real Pyrogram path
    try:
        from pyrogram import Client
    except ImportError as e:
        raise RuntimeError("pyrogram not installed") from e

    client = Client(
        name=f"qr_tmp_{token[:8]}",
        api_id=api_id,
        api_hash=api_hash,
        in_memory=True,
    )
    await client.connect()
    qr = await client.qr_login()
    qr_url = getattr(qr, "url", None) or ""

    sess = _QRSession(
        token=token, customer_id=customer_id, state=STATE_PENDING,
        qr_url=qr_url, expires_at=expires_at,
        client=client, qr=qr,
        password_event=asyncio.Event(),
    )
    _sessions[token] = sess
    _redis_set_state(token, STATE_PENDING)

    # Drive the wait loop in the background
    sess.task = asyncio.create_task(_run_qr_login(sess, api_id, api_hash))

    return {
        "token": token,
        "qr_url": qr_url,
        "qr_png_b64": _render_qr_png_b64(qr_url),
        "expires_at": expires_at,
        "state": STATE_PENDING,
        "mock": False,
    }


def get_state(token: str) -> dict:
    """Return the current state. Reads in-memory first, falls back to Redis."""
    sess = _sessions.get(token)
    if sess is not None:
        return {
            "token": token,
            "state": sess.state,
            "error": sess.error,
            "expires_at": sess.expires_at,
        }
    raw = _get_redis().hgetall(QR_REDIS_PREFIX + token)
    if not raw:
        return {"token": token, "state": STATE_EXPIRED, "error": None}
    return {"token": token, **raw}


def submit_password(token: str, password: str) -> dict:
    """Provide the 2FA password for a session waiting on password_required."""
    sess = _sessions.get(token)
    if not sess:
        return {"ok": False, "reason": "token unknown or expired"}
    if sess.state != STATE_PASSWORD_REQUIRED:
        return {"ok": False, "reason": f"unexpected state: {sess.state}"}
    sess.password_value = password
    if sess.password_event:
        sess.password_event.set()
    return {"ok": True}


def revoke(token: str) -> None:
    """Cancel an in-flight QR session and clear state."""
    sess = _sessions.pop(token, None)
    if sess and sess.task and not sess.task.done():
        sess.task.cancel()
    _get_redis().delete(QR_REDIS_PREFIX + token)
