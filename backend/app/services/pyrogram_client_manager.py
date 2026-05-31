"""
pyrogram_client_manager — short-lived Pyrogram client for one-shot join attempts.

listener_service owns long-lived clients for message reception. For per-attempt
work (Phase 9 join flow) we need a separate short-lived client that:
  1. Looks up Account by id
  2. Decrypts session file to a temp workdir
  3. Converts Telethon → Pyrogram session if needed
  4. Starts a fresh Client
  5. Yields it to caller (async with)
  6. Stops the client + removes the temp workdir on exit

The setup mirrors listener_service.start() lines ~780-840 so behaviour stays
consistent with the long-lived listener path.
"""
import contextlib
import logging
import os
import shutil
import tempfile
from typing import AsyncIterator, Optional

from pyrogram import Client
from sqlmodel import Session

from app.core.db import engine
from app.models.account import Account
from app.services.telegram_client import get_proxy_dict

logger = logging.getLogger(__name__)


@contextlib.asynccontextmanager
async def short_lived_client(
    *,
    account_id: int,
) -> AsyncIterator[Optional[Client]]:
    """
    Yield a started Pyrogram Client for the given account, or None if unusable.

    Use as: `async with short_lived_client(account_id=N) as client:`.
    On exit, the client is stopped and the temp workdir is removed even if the
    caller raises.
    """
    with Session(engine) as session:
        account = session.get(Account, account_id)

    if account is None:
        logger.warning("short_lived_client: account_id=%s not found", account_id)
        yield None
        return
    if not account.session_file_path:
        logger.warning(
            "short_lived_client: account_id=%s has no session_file_path", account_id
        )
        yield None
        return

    sfp = account.session_file_path
    if not os.path.exists(sfp):
        logger.warning("short_lived_client: session file missing %s", sfp)
        yield None
        return

    temp_workdir = tempfile.mkdtemp(prefix="tgsc_join_")
    actual_path = sfp
    try:
        try:
            from app.core.encryption import (
                get_encryption_service,
                is_session_encrypted,
            )
            if is_session_encrypted(sfp):
                enc = get_encryption_service()
                decrypted = enc.decrypt_to_memory(sfp)
                fname = os.path.basename(sfp)
                actual_path = os.path.join(temp_workdir, fname)
                with open(actual_path, "wb") as f:
                    f.write(decrypted)
        except Exception as exc:
            logger.warning(
                "short_lived_client decrypt failed for %s: %s — using raw file",
                sfp, exc,
            )
            actual_path = sfp

        try:
            from app.services.session_converter import (
                convert_telethon_to_pyrogram,
                is_telethon_session,
            )
            if is_telethon_session(actual_path):
                if not convert_telethon_to_pyrogram(actual_path):
                    logger.error(
                        "short_lived_client: telethon→pyrogram convert failed "
                        "account_id=%s", account_id,
                    )
                    yield None
                    return
        except Exception as exc:
            logger.warning("short_lived_client converter probe failed: %s", exc)

        session_name = os.path.splitext(os.path.basename(actual_path))[0]
        workdir = os.path.dirname(os.path.abspath(actual_path))

        proxy_dict = get_proxy_dict(account.proxy) if account.proxy else None
        client = Client(
            name=session_name,
            workdir=workdir,
            api_id=account.api_id or 6,
            api_hash=account.api_hash or "eb06d4abfb49dc3eeb1aeb98ae0f581e",
            proxy=proxy_dict,
            device_model=account.device_model,
            system_version=account.system_version,
            app_version=account.app_version,
        )
        try:
            await client.start()
        except Exception as exc:
            logger.warning(
                "short_lived_client start failed account_id=%s: %s",
                account_id, exc,
            )
            yield None
            return

        try:
            yield client
        finally:
            try:
                await client.stop()
            except Exception:
                logger.warning("short_lived_client stop failed", exc_info=True)
    finally:
        shutil.rmtree(temp_workdir, ignore_errors=True)
