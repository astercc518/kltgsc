"""
将账号 81/82（KB 采集号）所在的公开群组（成员数 > MIN_MEMBERS）整理到 SourceGroup（流量源管理）。

数据来源：group_message 中 account_id IN (81, 82) AND chat_type IN ('group','supergroup')
        AND chat_username IS NOT NULL AND chat_username != ''
验证：用 VERIFY_ACCOUNT_ID（默认 71，active support 号）的 Pyrogram session 调 get_chat
     拉真实 members_count
过滤：members_count > MIN_MEMBERS（默认 100）才入库
入库：SourceGroup(link='https://t.me/{username}', name=chat_title, member_count=N,
                type='traffic', risk_level='low', status='active')
幂等：已存在的 link 跳过

环境变量：
  VERIFY_ACCOUNT_ID  查询用账号 id (默认 71)
  MIN_MEMBERS        成员数阈值 (默认 100)
  SLEEP_SEC          每次 get_chat 间隔秒数 (默认 1.5)
  DRY_RUN            1 = 只查不写库
"""
import asyncio
import logging
import os
from datetime import datetime

from pyrogram import Client
from pyrogram.errors import (
    BadRequest,
    ChannelInvalid,
    ChannelPrivate,
    FloodWait,
    RPCError,
    UsernameInvalid,
    UsernameNotOccupied,
)
from sqlmodel import Session, select

from app.core.db import engine
from app.models.account import Account
from app.models.group_message import GroupMessage
from app.models.source_group import SourceGroup
from app.services.device_generator import DeviceGenerator
from app.services.session_converter import (
    convert_telethon_to_pyrogram,
    is_telethon_session,
)
from app.services.telegram_client import decrypted_session_file, get_proxy_dict


COLLECTOR_ACCOUNT_IDS = [81, 82]
VERIFY_ACCOUNT_ID = int(os.environ.get("VERIFY_ACCOUNT_ID", "71"))
MIN_MEMBERS = int(os.environ.get("MIN_MEMBERS", "100"))
SLEEP_SEC = float(os.environ.get("SLEEP_SEC", "1.5"))
DRY_RUN = os.environ.get("DRY_RUN", "0") == "1"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("import-81-82")


async def run() -> None:
    with Session(engine) as s:
        rows = s.exec(
            select(
                GroupMessage.chat_id,
                GroupMessage.chat_username,
                GroupMessage.chat_title,
                GroupMessage.chat_type,
            )
            .where(GroupMessage.account_id.in_(COLLECTOR_ACCOUNT_IDS))
            .where(GroupMessage.chat_type.in_(["group", "supergroup"]))
            .where(GroupMessage.chat_username.is_not(None))
            .where(GroupMessage.chat_username != "")
            .distinct()
        ).all()

        candidates: dict[str, dict] = {}
        for chat_id, username, title, chat_type in rows:
            link = f"https://t.me/{username}"
            if link in candidates:
                continue
            candidates[link] = {
                "link": link,
                "username": username,
                "name": title or str(chat_id),
                "chat_type": chat_type,
            }
        log.info(f"distinct_public_groups_from_81_82={len(candidates)}")

        if not candidates:
            log.info("nothing to do")
            return

        existing_rows = s.exec(
            select(SourceGroup).where(SourceGroup.link.in_(list(candidates.keys())))
        ).all()
        existing_by_link: dict[str, SourceGroup] = {sg.link: sg for sg in existing_rows}
        log.info(f"already_in_sourcegroup={len(existing_by_link)}")

        account = s.get(Account, VERIFY_ACCOUNT_ID)
        if not account:
            log.error(f"account {VERIFY_ACCOUNT_ID} not found")
            return
        if account.status != "active":
            log.warning(f"account {VERIFY_ACCOUNT_ID} status={account.status}; proceeding anyway")
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

        proxy_dict = get_proxy_dict(account.proxy) if account.proxy else None
        client_params = dict(
            api_id=account.api_id or 6,
            api_hash=account.api_hash or "eb06d4abfb49dc3eeb1aeb98ae0f581e",
            proxy=proxy_dict,
            device_model=account.device_model,
            system_version=account.system_version,
            app_version=account.app_version,
            lang_code="en",
        )

        stats = {
            "checked": 0,
            "imported_new": 0,
            "refreshed_active": 0,
            "deactivated_below": 0,
            "deactivated_not_group": 0,
            "deactivated_not_found": 0,
            "errors": 0,
        }

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
                items = list(candidates.values())
                for idx, info in enumerate(items, 1):
                    link = info["link"]
                    prefix = f"[{idx}/{len(items)}]"
                    existing = existing_by_link.get(link)

                    try:
                        chat = await client.get_chat(info["username"])
                    except FloodWait as fw:
                        log.warning(f"{prefix} FloodWait {fw.value}s on {link}")
                        await asyncio.sleep(min(fw.value, 60))
                        try:
                            chat = await client.get_chat(info["username"])
                        except Exception as e:
                            log.warning(f"{prefix} retry failed: {e}")
                            stats["errors"] += 1
                            await asyncio.sleep(SLEEP_SEC)
                            continue
                    except (UsernameNotOccupied, UsernameInvalid):
                        stats["deactivated_not_found"] += 1
                        log.info(f"{prefix} NOT FOUND {link}")
                        if existing and not DRY_RUN:
                            existing.status = "inactive"
                            s.add(existing)
                            s.commit()
                        await asyncio.sleep(SLEEP_SEC)
                        continue
                    except (ChannelInvalid, ChannelPrivate, BadRequest) as e:
                        stats["errors"] += 1
                        log.warning(f"{prefix} {link}: {e}")
                        await asyncio.sleep(SLEEP_SEC)
                        continue
                    except RPCError as e:
                        stats["errors"] += 1
                        log.warning(f"{prefix} {link} rpc: {e}")
                        await asyncio.sleep(SLEEP_SEC)
                        continue
                    except Exception as e:
                        stats["errors"] += 1
                        log.warning(f"{prefix} {link} unknown: {e!r}")
                        await asyncio.sleep(SLEEP_SEC)
                        continue

                    stats["checked"] += 1
                    kind = str(chat.type).lower()
                    members = int(getattr(chat, "members_count", 0) or 0)
                    title = getattr(chat, "title", None) or info["name"]

                    if not ("group" in kind or "supergroup" in kind):
                        stats["deactivated_not_group"] += 1
                        log.info(f"{prefix} not a group ({kind}): {link}")
                        if existing and not DRY_RUN:
                            existing.status = "inactive"
                            s.add(existing)
                            s.commit()
                        await asyncio.sleep(SLEEP_SEC)
                        continue

                    passes = members >= MIN_MEMBERS

                    if existing is None:
                        if not passes:
                            stats["deactivated_below"] += 1
                            log.info(f"{prefix} BELOW (skip new) {link} ({title}) members={members}")
                            await asyncio.sleep(SLEEP_SEC)
                            continue
                        if DRY_RUN:
                            stats["imported_new"] += 1
                            log.info(f"{prefix} [DRY] NEW {link} ({title}) members={members}")
                        else:
                            s.add(
                                SourceGroup(
                                    link=link,
                                    name=title,
                                    type="traffic",
                                    risk_level="low",
                                    status="active",
                                    member_count=members,
                                    created_at=datetime.utcnow(),
                                )
                            )
                            s.commit()
                            stats["imported_new"] += 1
                            log.info(f"{prefix} NEW {link} ({title}) members={members}")
                    else:
                        existing.name = title
                        existing.member_count = members
                        existing.status = "active" if passes else "inactive"
                        if not DRY_RUN:
                            s.add(existing)
                            s.commit()
                        if passes:
                            stats["refreshed_active"] += 1
                            log.info(f"{prefix} REFRESH active {link} ({title}) members={members}")
                        else:
                            stats["deactivated_below"] += 1
                            log.info(f"{prefix} REFRESH below->inactive {link} ({title}) members={members}")
                    await asyncio.sleep(SLEEP_SEC)
            finally:
                if client.is_connected:
                    await client.disconnect()

        log.info(f"done: stats={stats}")


if __name__ == "__main__":
    asyncio.run(run())
