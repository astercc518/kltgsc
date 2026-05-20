"""
主动找群 - 第 2 步：用一个 active 账号逐个 get_chat 验证 SourceGroup(status='pending')，
- group/supergroup -> status='active'，补充 name/member_count
- channel/bot/private -> 删除（不是群）
- 用户名不存在/无效 -> 删除

控速：每次 get_chat 间隔 SLEEP 秒，遇 FloodWait 自动 sleep 后继续。
"""
import asyncio
import logging
import os
import sys
from datetime import datetime
from typing import Optional

from pyrogram import Client, enums
from pyrogram.errors import FloodWait, UsernameNotOccupied, UsernameInvalid, ChannelInvalid, ChannelPrivate, BadRequest, RPCError
from sqlmodel import Session, select

from app.core.db import engine
from app.models.account import Account
from app.models.source_group import SourceGroup
from app.services.device_generator import DeviceGenerator
from app.services.session_converter import is_telethon_session, convert_telethon_to_pyrogram
from app.services.telegram_client import decrypted_session_file, get_proxy_dict

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("verify")

SLEEP_SEC = float(os.environ.get("VERIFY_SLEEP_SEC", "1.5"))
MAX_HANDLES = int(os.environ.get("VERIFY_MAX", "0"))  # 0 = no limit
ACCOUNT_ID = int(os.environ.get("VERIFY_ACCOUNT_ID", "71"))


def _classify(chat) -> str:
    t = str(chat.type).lower()
    if "supergroup" in t:
        return "supergroup"
    if "group" in t and "super" not in t:
        return "group"
    if "channel" in t:
        return "channel"
    if "private" in t:
        return "private"
    if "bot" in t:
        return "bot"
    return t


async def _verify_one(client: Client, link: str):
    handle = link.rsplit("/", 1)[-1]
    chat = await client.get_chat(handle)
    kind = _classify(chat)
    return kind, chat


async def run():
    with Session(engine) as s:
        account = s.get(Account, ACCOUNT_ID)
        if not account:
            log.error(f"account {ACCOUNT_ID} not found")
            return
        if account.status != "active":
            log.warning(f"account {ACCOUNT_ID} status={account.status}; proceeding anyway")

        pending = s.exec(
            select(SourceGroup).where(SourceGroup.status == "pending")
        ).all()
        if MAX_HANDLES > 0:
            pending = pending[:MAX_HANDLES]

        log.info(f"to_verify={len(pending)} using account_id={ACCOUNT_ID}")

        if not pending:
            return

        sfp = account.session_file_path
        if not sfp or not os.path.exists(sfp):
            log.error("no session file")
            return

        if not account.device_model:
            dev = DeviceGenerator.generate()
            account.device_model = dev["device_model"]
            account.system_version = dev["system_version"]
            account.app_version = dev["app_version"]
            s.add(account)
            s.commit()
            s.refresh(account)

        proxy = account.proxy
        proxy_dict = get_proxy_dict(proxy) if proxy else None

        client_params = dict(
            api_id=account.api_id or 6,
            api_hash=account.api_hash or "eb06d4abfb49dc3eeb1aeb98ae0f581e",
            proxy=proxy_dict,
            device_model=account.device_model,
            system_version=account.system_version,
            app_version=account.app_version,
            lang_code="en",
        )

        counts = {"group": 0, "supergroup": 0, "channel": 0, "private": 0, "bot": 0, "not_found": 0, "error": 0}

        with decrypted_session_file(sfp) as (actual_path, session_dir):
            if is_telethon_session(actual_path):
                if not convert_telethon_to_pyrogram(actual_path):
                    log.error("failed to convert telethon session")
                    return
            session_name = os.path.splitext(os.path.basename(actual_path))[0]
            client = Client(
                name=session_name,
                workdir=session_dir or os.path.dirname(os.path.abspath(actual_path)),
                **client_params,
            )
            await client.connect()
            try:
                for idx, sg in enumerate(pending, 1):
                    try:
                        kind, chat = await _verify_one(client, sg.link)
                    except FloodWait as fw:
                        log.warning(f"[{idx}/{len(pending)}] FloodWait {fw.value}s on {sg.link}")
                        await asyncio.sleep(min(fw.value, 60))
                        try:
                            kind, chat = await _verify_one(client, sg.link)
                        except Exception as e:
                            log.warning(f"  retry failed: {e}")
                            counts["error"] += 1
                            await asyncio.sleep(SLEEP_SEC)
                            continue
                    except (UsernameNotOccupied, UsernameInvalid):
                        counts["not_found"] += 1
                        # peer 不存在直接删
                        sg_db = s.get(SourceGroup, sg.id)
                        if sg_db and sg_db.status == "pending":
                            s.delete(sg_db)
                            s.commit()
                        await asyncio.sleep(SLEEP_SEC)
                        continue
                    except (ChannelInvalid, ChannelPrivate, BadRequest) as e:
                        log.info(f"[{idx}] {sg.link} bad: {e}")
                        counts["error"] += 1
                        sg_db = s.get(SourceGroup, sg.id)
                        if sg_db and sg_db.status == "pending":
                            s.delete(sg_db)
                            s.commit()
                        await asyncio.sleep(SLEEP_SEC)
                        continue
                    except RPCError as e:
                        log.warning(f"[{idx}] {sg.link} rpc: {e}")
                        counts["error"] += 1
                        await asyncio.sleep(SLEEP_SEC)
                        continue
                    except Exception as e:
                        log.warning(f"[{idx}] {sg.link} unknown: {e!r}")
                        counts["error"] += 1
                        await asyncio.sleep(SLEEP_SEC)
                        continue

                    counts[kind] = counts.get(kind, 0) + 1

                    sg_db = s.get(SourceGroup, sg.id)
                    if not sg_db:
                        await asyncio.sleep(SLEEP_SEC)
                        continue

                    if kind in ("group", "supergroup"):
                        sg_db.status = "active"
                        sg_db.name = getattr(chat, "title", None) or sg_db.name
                        try:
                            sg_db.member_count = int(getattr(chat, "members_count", 0) or 0)
                        except Exception:
                            pass
                        s.add(sg_db)
                        s.commit()
                        log.info(f"[{idx}/{len(pending)}] OK group: {sg.link} -> {sg_db.name} ({sg_db.member_count})")
                    else:
                        # channel / private / bot -> not a group, remove
                        s.delete(sg_db)
                        s.commit()
                        log.info(f"[{idx}/{len(pending)}] drop {kind}: {sg.link}")

                    await asyncio.sleep(SLEEP_SEC)
            finally:
                if client.is_connected:
                    await client.disconnect()

        log.info(f"done: counts={counts}")


if __name__ == "__main__":
    asyncio.run(run())
