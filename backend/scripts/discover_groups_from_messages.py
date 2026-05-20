"""
主动找群 - 第 1 步：从已采集的群消息里抽取被分享的 t.me/{handle} 链接，
入库到 SourceGroup 作为候选（status='pending'），等待后续验证脚本判定类型。

数据来源：group_message 表中 account_id IN (81, 82) 且 chat_type IN ('group','supergroup')
入库：SourceGroup(link='https://t.me/{handle}', type='traffic', status='pending')
幂等：已存在的 link 跳过。
"""
import re
from datetime import datetime
from sqlmodel import Session, select

from app.core.db import engine
from app.models.group_message import GroupMessage
from app.models.source_group import SourceGroup


COLLECTOR_ACCOUNT_IDS = [81, 82]

# t.me 链接里非"群/频道用户名"的关键字，必须排除
TME_RESERVED = {
    "joinchat", "addstickers", "addemoji", "addlist", "addtheme",
    "share", "iv", "c", "contact", "proxy", "socks",
    "setlanguage", "login", "confirmphone", "bg",
}

LINK_RE = re.compile(r"(?:https?://)?t\.me/([A-Za-z0-9_]{4,32})\b", re.IGNORECASE)


def extract_handles(text: str) -> set[str]:
    out: set[str] = set()
    for m in LINK_RE.finditer(text or ""):
        h = m.group(1).lower()
        if h in TME_RESERVED:
            continue
        if h.startswith("+"):
            continue
        out.add(h)
    return out


def main() -> None:
    with Session(engine) as s:
        rows = s.exec(
            select(GroupMessage.content)
            .where(GroupMessage.account_id.in_(COLLECTOR_ACCOUNT_IDS))
            .where(GroupMessage.chat_type.in_(["group", "supergroup"]))
            .where(GroupMessage.content.is_not(None))
        ).all()

        all_handles: set[str] = set()
        for content in rows:
            all_handles |= extract_handles(content)

        candidate_links = {f"https://t.me/{h}" for h in all_handles}

        existing = set(
            s.exec(
                select(SourceGroup.link).where(SourceGroup.link.in_(list(candidate_links)))
            ).all()
        )

        now = datetime.utcnow()
        created = 0
        for link in candidate_links:
            if link in existing:
                continue
            s.add(
                SourceGroup(
                    link=link,
                    name=None,
                    type="traffic",
                    risk_level="low",
                    status="pending",
                    created_at=now,
                )
            )
            created += 1

        s.commit()
        print(
            f"distinct_handles={len(all_handles)} "
            f"already_in_sourcegroup={len(existing)} "
            f"created={created}"
        )


if __name__ == "__main__":
    main()
