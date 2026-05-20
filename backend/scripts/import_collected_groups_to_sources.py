"""
将账号 81/82（KB 采集号）抓取过的群组导入到 SourceGroup（流量源管理）。

数据来源：group_message 表中 account_id IN (81, 82) 且 chat_type IN ('group','supergroup')
去重键：SourceGroup.link = https://t.me/{chat_username}

仅纳入有公开 username 的群组；私有群（无 username）跳过。
幂等：已存在的 link 跳过。
"""
from datetime import datetime
from sqlmodel import Session, select

from app.core.db import engine
from app.models.group_message import GroupMessage
from app.models.source_group import SourceGroup


COLLECTOR_ACCOUNT_IDS = [81, 82]


def main() -> None:
    with Session(engine) as s:
        rows = s.exec(
            select(
                GroupMessage.chat_id,
                GroupMessage.chat_title,
                GroupMessage.chat_username,
                GroupMessage.chat_type,
            )
            .where(GroupMessage.account_id.in_(COLLECTOR_ACCOUNT_IDS))
            .where(GroupMessage.chat_type.in_(["group", "supergroup"]))
            .where(GroupMessage.chat_username.is_not(None))
            .where(GroupMessage.chat_username != "")
            .distinct()
        ).all()

        seen: dict[str, dict] = {}
        for chat_id, chat_title, chat_username, chat_type in rows:
            link = f"https://t.me/{chat_username}"
            if link not in seen:
                seen[link] = {
                    "link": link,
                    "name": chat_title or str(chat_id),
                    "chat_type": chat_type,
                }

        existing_links = set(
            s.exec(
                select(SourceGroup.link).where(SourceGroup.link.in_(list(seen.keys())))
            ).all()
        )

        created = 0
        skipped = 0
        now = datetime.utcnow()
        for link, info in seen.items():
            if link in existing_links:
                skipped += 1
                continue
            s.add(
                SourceGroup(
                    link=link,
                    name=info["name"],
                    type="traffic",
                    risk_level="low",
                    status="active",
                    created_at=now,
                )
            )
            created += 1

        s.commit()
        print(f"distinct_groups={len(seen)} created={created} skipped={skipped}")


if __name__ == "__main__":
    main()
