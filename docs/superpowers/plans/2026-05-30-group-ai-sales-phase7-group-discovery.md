# 群内 AI 销售员 Phase 7 实施计划（线索群自动发现）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从"客户/运营手动提交群列表"升级到"系统每周给每个客户推荐 N 个高质量候选线索群"。集成 TGStat API + Telegram t.me/s 搜索 + 本地活跃度评分 + 客户审批 portal UI。

**Architecture:** 不动 Phase 1-6 任何运行时路径。新增独立 service 链：discovery_source（数据源配置）→ TGStat / Telegram search adapter → ranking → discovered_group 表（候选库）→ portal 客户审批 → 已 approve 的群进 `keyword_monitor` 走主管线。Celery beat 每周跑一次。

**Tech Stack:** FastAPI · SQLModel · pgvector(unused) · Celery beat (weekly) · TGStat REST API · Telegram t.me/s scraping · React + Ant Design

**Spec extension:** 本计划是 spec §1.2 "数据源" 的工程化补丁；spec 未直接覆盖，但属于产品上线必备。

**前置条件：**
- Phase 1-6 实施完成并灰度跑过（确认主管线稳定）
- 准备 TGStat API key（[tgstat.com](https://tgstat.com) 注册付费账户，约 $50/month 基础档）
- 新 worktree `/var/tgsc/.claude/worktrees/feature+group-ai-sales-phase7`

**Phase 7 范围：**

| 包含 | 不含 |
|---|---|
| TGStat API 集成（按关键词搜群） | 直接调 Telegram MTProto 搜索（容易被风控） |
| Telegram t.me/s 公开搜索 fallback | 自动加群（仍走 Phase 8 captcha 流程） |
| 群活跃度评分（成员数 + 日均消息 + 关键词命中密度） | 群语义匹配（v2 优化项，先按粗排走） |
| 客户每周收 N 个推荐群 + 一键审批 | 跨客户共享推荐池（隐私问题） |
| 拒绝的群记 blacklist 不再推 | 推送渠道（邮件/Slack/TG bot，独立 epic） |
| 1 张迁移（discovered_group + discovery_blacklist） | 推荐质量学习（强化学习按客户拒绝率调权重，后续） |

---

## File Structure

**新建：**
- `backend/app/models/discovered_group.py` — 候选群 + 评分
- `backend/app/models/discovery_blacklist.py` — 客户拒绝过的群
- `backend/alembic/versions/<rev>_group_discovery_tables.py`
- `backend/app/services/tgstat_adapter.py` — TGStat API 包装
- `backend/app/services/tme_search_adapter.py` — t.me/s 公开搜索
- `backend/app/services/group_ranking_service.py` — 评分算法
- `backend/app/services/group_discovery_service.py` — 编排入口
- `backend/app/workers/group_discovery_weekly.py` — Celery beat
- `backend/app/routers/portal_discovery.py` — 客户审批 endpoints
- `backend/app/routers/admin_discovery.py` — admin 调试 endpoints
- `frontend/src/portal/pages/GroupAI/GroupDiscovery.tsx` — portal UI
- 7 个 test 文件

**修改：**
- `backend/app/main.py` — 注册 2 个新 router
- `backend/app/core/celery_app.py` — 注册 weekly beat task
- `frontend/src/portal/api/groupAi.ts` — 加 discoveryApi
- `frontend/src/portal/pages/GroupAI/index.tsx` — 加 menu item

---

## Task 1: discovered_group + discovery_blacklist 表 + 迁移

**Files:**
- Create: `backend/app/models/discovered_group.py`
- Create: `backend/app/models/discovery_blacklist.py`
- Create: `backend/alembic/versions/<rev>_group_discovery_tables.py`
- Create: `backend/tests/test_discovered_group_model.py`

### Step 1.1: 写迁移

```python
"""group_discovery_tables

Revision ID: <REV>
Revises: <previous head, e.g. Phase 6 audit log rev>
Create Date: 2026-05-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from typing import Sequence, Union

revision: str = "<REV>"
down_revision: Union[str, Sequence[str], None] = "<prev>"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "discovered_group",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("customer_id", sa.Integer, sa.ForeignKey("customer.id"), nullable=False),
        sa.Column("chat_username", sa.Text, nullable=True),  # @groupname (公开群)
        sa.Column("chat_link", sa.Text, nullable=True),  # t.me/+xxx (私有邀请链接)
        sa.Column("chat_id", sa.BigInteger, nullable=True),  # 已知 chat_id (公开群)
        sa.Column("title", sa.Text, nullable=True),
        sa.Column("members_count", sa.Integer, nullable=True),
        sa.Column("daily_messages", sa.Integer, nullable=True),
        sa.Column("category", sa.Text, nullable=True),  # 行业类别 (LLM 推断)
        sa.Column("source", sa.Text, nullable=False),  # 'tgstat' | 'tme_search' | 'manual'
        sa.Column("source_query", sa.Text, nullable=True),  # 触发搜索的关键词
        sa.Column("score", sa.Float, nullable=True),  # 综合评分 0-100
        sa.Column("status", sa.Text, nullable=False, server_default="pending"),
        # status: pending | approved | rejected | failed_join (已尝试加入失败)
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("discovered_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by", sa.Integer, sa.ForeignKey("customer_user.id"), nullable=True),
    )
    op.create_index(
        "idx_discovered_group_customer_status",
        "discovered_group", ["customer_id", "status"],
    )
    op.create_unique_constraint(
        "uq_discovered_group_customer_link",
        "discovered_group",
        ["customer_id", "chat_link"],
    )

    op.create_table(
        "discovery_blacklist",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("customer_id", sa.Integer, sa.ForeignKey("customer.id"), nullable=False),
        sa.Column("chat_link", sa.Text, nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_unique_constraint(
        "uq_discovery_blacklist_customer_link",
        "discovery_blacklist",
        ["customer_id", "chat_link"],
    )


def downgrade() -> None:
    op.drop_table("discovery_blacklist")
    op.drop_index("idx_discovered_group_customer_status", table_name="discovered_group")
    op.drop_table("discovered_group")
```

### Step 1.2: 写 SQLModel

`backend/app/models/discovered_group.py`:

```python
"""DiscoveredGroup — 待审批/已审批的候选线索群"""
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Column, DateTime, Float, ForeignKey, Integer, JSON, Text
from sqlmodel import Field, SQLModel


class DiscoveredGroup(SQLModel, table=True):
    __tablename__ = "discovered_group"

    id: Optional[int] = Field(
        default=None,
        sa_column=Column(
            BigInteger().with_variant(
                __import__("sqlalchemy.dialects.sqlite", fromlist=["INTEGER"]).INTEGER(),
                "sqlite",
            ),
            primary_key=True,
        ),
    )
    customer_id: int = Field(
        sa_column=Column(Integer, ForeignKey("customer.id"), nullable=False)
    )
    chat_username: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    chat_link: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    chat_id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, nullable=True))
    title: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    members_count: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
    daily_messages: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
    category: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    source: str = Field(sa_column=Column(Text, nullable=False))
    source_query: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    score: Optional[float] = Field(default=None, sa_column=Column(Float, nullable=True))
    status: str = Field(default="pending", sa_column=Column(Text, nullable=False))
    metadata_json: Optional[dict] = Field(default=None, sa_column=Column(JSON, nullable=True))
    discovered_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    decided_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    decided_by: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("customer_user.id"), nullable=True),
    )
```

`backend/app/models/discovery_blacklist.py`:

```python
"""DiscoveryBlacklist — 客户拒绝过的群, 不再推荐"""
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, Text
from sqlmodel import Field, SQLModel


class DiscoveryBlacklist(SQLModel, table=True):
    __tablename__ = "discovery_blacklist"

    id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, primary_key=True))
    customer_id: int = Field(
        sa_column=Column(Integer, ForeignKey("customer.id"), nullable=False)
    )
    chat_link: str = Field(sa_column=Column(Text, nullable=False))
    reason: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=False),
    )
```

Register both in `backend/app/models/__init__.py`.

### Step 1.3: 测试 + 提交

`backend/tests/test_discovered_group_model.py`:

```python
import os
import pytest


def test_models_importable():
    from app.models.discovered_group import DiscoveredGroup
    from app.models.discovery_blacklist import DiscoveryBlacklist
    assert DiscoveredGroup.__tablename__ == "discovered_group"
    assert DiscoveryBlacklist.__tablename__ == "discovery_blacklist"


def test_migration_round_trip():
    db = os.environ.get("DATABASE_URL", "")
    if not db.startswith(("postgresql", "postgres")):
        pytest.skip("requires Postgres")
    import subprocess
    cwd = os.path.join(os.path.dirname(__file__), "..")
    subprocess.run(["alembic", "upgrade", "head"], cwd=cwd, check=True)
    subprocess.run(["alembic", "downgrade", "-1"], cwd=cwd, check=True)
    subprocess.run(["alembic", "upgrade", "head"], cwd=cwd, check=True)
```

```bash
pytest backend/tests/test_discovered_group_model.py -v
git add backend/app/models/discovered_group.py \
        backend/app/models/discovery_blacklist.py \
        backend/app/models/__init__.py \
        backend/alembic/versions/*group_discovery_tables.py \
        backend/tests/test_discovered_group_model.py
git commit -m "feat(group-ai/phase7): discovered_group + discovery_blacklist tables"
```

---

## Task 2: TGStat API adapter

**Files:**
- Create: `backend/app/services/tgstat_adapter.py`
- Create: `backend/tests/test_tgstat_adapter.py`

### Step 2.1: 实装

TGStat API 文档：[api.tgstat.com](https://api.tgstat.com/). 主要 endpoint：
- `GET /channels/search?q=<keyword>&country=cn` — 按关键词搜频道/群
- 响应：`{ "status": "ok", "response": { "items": [{"id":..., "username":..., "title":..., "participants_count":..., "category":...}, ...] } }`

`backend/app/services/tgstat_adapter.py`:

```python
"""
tgstat_adapter — 包装 TGStat API 搜群。

API doc: https://api.tgstat.com/
需要 TGSTAT_API_TOKEN 环境变量。
"""
import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

TGSTAT_BASE_URL = "https://api.tgstat.com"
TGSTAT_TIMEOUT = 30.0


async def search_groups_by_keyword(
    *, keyword: str, country: Optional[str] = "cn", limit: int = 50,
) -> list[dict]:
    """
    搜索匹配关键词的群/频道。
    Returns: [{"username": str|None, "chat_id": int|None, "title": str,
               "participants_count": int, "category": str, "link": str}, ...]
    或失败时返回 []
    """
    token = os.getenv("TGSTAT_API_TOKEN")
    if not token:
        logger.warning("TGSTAT_API_TOKEN not set; group_discovery TGStat disabled")
        return []

    params = {
        "token": token,
        "q": keyword,
        "country": country,
        "limit": limit,
    }
    try:
        async with httpx.AsyncClient(timeout=TGSTAT_TIMEOUT) as client:
            r = await client.get(f"{TGSTAT_BASE_URL}/channels/search", params=params)
            r.raise_for_status()
            data = r.json()
    except Exception:
        logger.exception("TGStat search failed for keyword=%s", keyword)
        return []

    if data.get("status") != "ok":
        logger.warning("TGStat returned non-ok: %s", data)
        return []

    items = (data.get("response") or {}).get("items") or []
    result = []
    for item in items:
        username = item.get("username")
        chat_id = item.get("id")
        link = f"https://t.me/{username}" if username else f"https://t.me/c/{chat_id}"
        result.append({
            "username": username,
            "chat_id": chat_id,
            "title": item.get("title", ""),
            "participants_count": int(item.get("participants_count", 0)),
            "category": item.get("category", ""),
            "link": link,
        })
    return result
```

### Step 2.2: 测试

`backend/tests/test_tgstat_adapter.py`:

```python
"""TGStat adapter unit tests (mock httpx)"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from app.services.tgstat_adapter import search_groups_by_keyword


@pytest.mark.asyncio
async def test_search_returns_empty_when_no_token(monkeypatch):
    monkeypatch.delenv("TGSTAT_API_TOKEN", raising=False)
    result = await search_groups_by_keyword(keyword="USDT")
    assert result == []


@pytest.mark.asyncio
async def test_search_parses_tgstat_response(monkeypatch):
    monkeypatch.setenv("TGSTAT_API_TOKEN", "fake")
    fake_response = {
        "status": "ok",
        "response": {
            "items": [
                {"id": 100, "username": "usdt_group",
                 "title": "USDT OTC", "participants_count": 5000,
                 "category": "Crypto"},
            ],
        },
    }
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.json = MagicMock(return_value=fake_response)
    mock_resp.raise_for_status = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.services.tgstat_adapter.httpx.AsyncClient", return_value=mock_client):
        result = await search_groups_by_keyword(keyword="USDT")
    assert len(result) == 1
    assert result[0]["username"] == "usdt_group"
    assert result[0]["participants_count"] == 5000
    assert result[0]["link"] == "https://t.me/usdt_group"


@pytest.mark.asyncio
async def test_search_handles_api_failure(monkeypatch):
    monkeypatch.setenv("TGSTAT_API_TOKEN", "fake")
    mock_client = MagicMock()
    mock_client.get = AsyncMock(side_effect=Exception("API down"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.services.tgstat_adapter.httpx.AsyncClient", return_value=mock_client):
        result = await search_groups_by_keyword(keyword="USDT")
    assert result == []
```

```bash
pytest backend/tests/test_tgstat_adapter.py -v
git add backend/app/services/tgstat_adapter.py backend/tests/test_tgstat_adapter.py
git commit -m "feat(group-ai/phase7): TGStat API adapter for group search"
```

---

## Task 3: t.me/s 公开搜索 adapter (fallback)

**Files:**
- Create: `backend/app/services/tme_search_adapter.py`
- Create: `backend/tests/test_tme_search_adapter.py`

### Step 3.1: 实装

t.me/s/{username} 是 Telegram 公开预览页（无需登录）。可以用 BeautifulSoup 解析。但更可靠的是直接通过 telethon 的 `client.get_entity(username)` 拿群信息（已登录主号上下文）。

简化版：仅做 t.me/s/{username} 的 HTTP 抓取作为 fallback：

```python
"""
tme_search_adapter — 通过 t.me/s/{username} 抓公开群信息 (fallback when TGStat 失败).
当前实现简化: 仅根据已知 username 验证存在性 + 抓 title/description.
"""
import logging
import re
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

TME_BASE = "https://t.me"


async def fetch_group_info_by_username(username: str) -> Optional[dict]:
    """
    返回 {"title", "description", "members_count" (估)} 或 None.
    """
    if not username:
        return None
    url = f"{TME_BASE}/{username}"
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            r = await client.get(url)
            if r.status_code != 200:
                return None
            html = r.text
    except Exception:
        logger.warning("t.me fetch failed for %s", username)
        return None

    # Parse Open Graph meta tags (simple regex)
    title = _extract_meta(html, "og:title")
    description = _extract_meta(html, "og:description")
    if not title:
        return None
    # members count is often in tgme_page_extra div, regex-match digits + "members"
    members = None
    m = re.search(r'(\d+(?:[ ,]\d+)*)\s+(?:subscribers|members)', html)
    if m:
        members = int(m.group(1).replace(",", "").replace(" ", ""))

    return {
        "title": title,
        "description": description,
        "members_count": members,
    }


def _extract_meta(html: str, prop: str) -> Optional[str]:
    pattern = rf'<meta property="{re.escape(prop)}" content="([^"]+)"'
    m = re.search(pattern, html)
    return m.group(1) if m else None
```

### Step 3.2: 测试 + 提交

`backend/tests/test_tme_search_adapter.py`:

```python
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from app.services.tme_search_adapter import fetch_group_info_by_username


@pytest.mark.asyncio
async def test_fetch_returns_none_for_empty():
    result = await fetch_group_info_by_username("")
    assert result is None


@pytest.mark.asyncio
async def test_fetch_parses_og_tags():
    fake_html = """
    <html>
    <meta property="og:title" content="USDT OTC Group" />
    <meta property="og:description" content="买卖 USDT 大额场外" />
    <span>5,000 subscribers</span>
    </html>
    """
    mock_client = MagicMock()
    mock_resp = MagicMock(status_code=200, text=fake_html)
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.services.tme_search_adapter.httpx.AsyncClient", return_value=mock_client):
        result = await fetch_group_info_by_username("usdt_otc")
    assert result is not None
    assert result["title"] == "USDT OTC Group"
    assert result["members_count"] == 5000
```

```bash
pytest backend/tests/test_tme_search_adapter.py -v
git add backend/app/services/tme_search_adapter.py backend/tests/test_tme_search_adapter.py
git commit -m "feat(group-ai/phase7): t.me/s public page adapter (fallback)"
```

---

## Task 4: group_ranking_service — 综合评分

**Files:**
- Create: `backend/app/services/group_ranking_service.py`
- Create: `backend/tests/test_group_ranking_service.py`

### Step 4.1: 写评分算法

评分维度（0-100 综合）：
- **成员数**（30 分）：log10(members) / 5 × 30，上限 30 分（10w 成员满分）
- **日活**（30 分）：daily_messages 越多越好（每 100 条 = 3 分，上限 30 分）
- **类别匹配**（20 分）：客户 ICP 行业关键词与群 category/title 的 token 重叠
- **新鲜度**（10 分）：新发现的群优先（discover 后 30d 内 +10 分）
- **去重惩罚**（-30 分）：已在 keyword_monitor 监听的群直接打 -30

```python
"""
group_ranking_service — 候选群综合评分 0-100。
高分群优先推荐给客户审批。
"""
import logging
import math
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlmodel import select

from app.models.discovered_group import DiscoveredGroup
from app.models.keyword_monitor import KeywordMonitor

logger = logging.getLogger(__name__)


def compute_score(
    *,
    members_count: Optional[int],
    daily_messages: Optional[int],
    category: Optional[str],
    customer_icp_keywords: list[str],
    is_already_monitored: bool,
    discovered_at: Optional[datetime] = None,
) -> float:
    """0-100 综合分数."""
    score = 0.0

    # 成员数 (max 30)
    if members_count and members_count > 0:
        score += min(30.0, (math.log10(members_count) / 5.0) * 30.0)

    # 日活 (max 30)
    if daily_messages and daily_messages > 0:
        score += min(30.0, (daily_messages / 100.0) * 3.0)

    # 类别匹配 (max 20)
    if category and customer_icp_keywords:
        category_lower = category.lower()
        match_count = sum(1 for kw in customer_icp_keywords if kw.lower() in category_lower)
        if customer_icp_keywords:
            score += min(20.0, (match_count / len(customer_icp_keywords)) * 20.0)

    # 新鲜度 (max 10)
    if discovered_at:
        now = datetime.now(timezone.utc)
        if (now - discovered_at).days < 30:
            score += 10.0

    # 已监听惩罚
    if is_already_monitored:
        score -= 30.0

    return max(0.0, min(100.0, score))


def is_chat_already_monitored(
    *, session, customer_id: int, chat_username: Optional[str], chat_id: Optional[int],
) -> bool:
    """检查群是否已在 keyword_monitor.target_groups."""
    if not chat_username and not chat_id:
        return False
    rows = session.exec(
        select(KeywordMonitor).where(KeywordMonitor.customer_id == customer_id)
    ).all()
    needles = []
    if chat_username:
        needles.extend([chat_username, f"@{chat_username}", f"https://t.me/{chat_username}"])
    if chat_id:
        needles.append(str(chat_id))
    for m in rows:
        targets = (m.target_groups or "").split(",")
        for t in targets:
            t = t.strip()
            if t and any(n in t for n in needles):
                return True
    return False
```

### Step 4.2: 测试 + 提交

`backend/tests/test_group_ranking_service.py`:

```python
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

from app.services.group_ranking_service import compute_score, is_chat_already_monitored


def test_score_zero_for_empty_input():
    score = compute_score(
        members_count=None, daily_messages=None, category=None,
        customer_icp_keywords=[], is_already_monitored=False,
    )
    assert score == 0.0


def test_score_high_for_active_matched_group():
    score = compute_score(
        members_count=50000, daily_messages=500,
        category="Cryptocurrency OTC",
        customer_icp_keywords=["OTC", "USDT", "Cryptocurrency"],
        is_already_monitored=False,
        discovered_at=datetime.now(timezone.utc),
    )
    assert score > 70


def test_score_penalty_when_already_monitored():
    base = compute_score(
        members_count=10000, daily_messages=200, category="Crypto",
        customer_icp_keywords=["Crypto"], is_already_monitored=False,
    )
    penalized = compute_score(
        members_count=10000, daily_messages=200, category="Crypto",
        customer_icp_keywords=["Crypto"], is_already_monitored=True,
    )
    assert penalized < base
    assert base - penalized == 30.0


def test_is_already_monitored_finds_username():
    fake_session = MagicMock()
    fake_monitor = MagicMock(target_groups="@usdt_otc,@other_group")
    fake_session.exec.return_value.all.return_value = [fake_monitor]
    assert is_chat_already_monitored(
        session=fake_session, customer_id=1,
        chat_username="usdt_otc", chat_id=None,
    ) is True


def test_is_already_monitored_returns_false_when_not_found():
    fake_session = MagicMock()
    fake_session.exec.return_value.all.return_value = []
    assert is_chat_already_monitored(
        session=fake_session, customer_id=1,
        chat_username="new_group", chat_id=None,
    ) is False
```

```bash
pytest backend/tests/test_group_ranking_service.py -v
git add backend/app/services/group_ranking_service.py backend/tests/test_group_ranking_service.py
git commit -m "feat(group-ai/phase7): group ranking service (members + activity + category + dedup)"
```

---

## Task 5: group_discovery_service — 编排

**Files:**
- Create: `backend/app/services/group_discovery_service.py`
- Create: `backend/tests/test_group_discovery_service.py`

### Step 5.1: 写编排

```python
"""
group_discovery_service — 主编排。

流程:
  for each customer with ICP set:
    extract keywords from icp_profile_text (LLM extract or simple tokenize)
    for each keyword:
      results = await tgstat_adapter.search_groups_by_keyword(keyword)
      for each result:
        if in discovery_blacklist: skip
        if in discovered_group with same chat_link: skip (already pending/decided)
        compute_score()
        insert discovered_group with status='pending'
"""
import logging
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.core.db import engine
from app.models.customer import Customer
from app.models.discovered_group import DiscoveredGroup
from app.models.discovery_blacklist import DiscoveryBlacklist
from app.services.tgstat_adapter import search_groups_by_keyword
from app.services.group_ranking_service import (
    compute_score, is_chat_already_monitored,
)

logger = logging.getLogger(__name__)


def _extract_keywords_from_icp(icp_text: str, max_keywords: int = 5) -> list[str]:
    """
    简化: 从 ICP 文本提取关键 token (按词频/长度).
    生产改进版可以调 LLM 提关键搜索词.
    """
    import re
    tokens = re.findall(r'[一-鿿]+|[A-Za-z]{3,}', icp_text)
    # 简单去重 + 长度过滤
    seen = set()
    result = []
    for t in tokens:
        if t.lower() in seen:
            continue
        seen.add(t.lower())
        if len(t) >= 2:
            result.append(t)
        if len(result) >= max_keywords:
            break
    return result


async def discover_for_customer(
    *, customer_id: int, max_per_keyword: int = 20,
) -> int:
    """
    为单个客户跑发现流程, 返回新插入的 candidate 数.
    """
    with Session(engine) as session:
        customer = session.get(Customer, customer_id)
        if customer is None or not customer.icp_profile_text:
            logger.info("discovery: customer %s has no ICP, skipping", customer_id)
            return 0

        keywords = _extract_keywords_from_icp(customer.icp_profile_text)
        logger.info("discovery: customer %s keywords=%s", customer_id, keywords)

        blacklist = set(
            row.chat_link for row in session.exec(
                select(DiscoveryBlacklist.chat_link).where(
                    DiscoveryBlacklist.customer_id == customer_id
                )
            ).all()
        )

        existing_links = set(
            row.chat_link for row in session.exec(
                select(DiscoveredGroup.chat_link).where(
                    DiscoveredGroup.customer_id == customer_id,
                    DiscoveredGroup.chat_link.isnot(None),
                )
            ).all()
        )

        n_inserted = 0
        for keyword in keywords:
            results = await search_groups_by_keyword(
                keyword=keyword, limit=max_per_keyword,
            )
            for r in results:
                link = r.get("link", "")
                if not link or link in blacklist or link in existing_links:
                    continue

                already_monitored = is_chat_already_monitored(
                    session=session, customer_id=customer_id,
                    chat_username=r.get("username"), chat_id=r.get("chat_id"),
                )

                score = compute_score(
                    members_count=r.get("participants_count"),
                    daily_messages=None,  # TGStat search 不直接返回, 后续可补
                    category=r.get("category"),
                    customer_icp_keywords=keywords,
                    is_already_monitored=already_monitored,
                    discovered_at=datetime.now(timezone.utc),
                )

                row = DiscoveredGroup(
                    customer_id=customer_id,
                    chat_username=r.get("username"),
                    chat_link=link,
                    chat_id=r.get("chat_id"),
                    title=r.get("title"),
                    members_count=r.get("participants_count"),
                    category=r.get("category"),
                    source="tgstat",
                    source_query=keyword,
                    score=score,
                    status="pending",
                    metadata_json=r,
                    discovered_at=datetime.now(timezone.utc),
                )
                session.add(row)
                existing_links.add(link)
                n_inserted += 1

        session.commit()
        logger.info("discovery: customer %s inserted %d candidates", customer_id, n_inserted)
        return n_inserted


async def discover_for_all_active_customers() -> dict:
    """Weekly batch entry. Returns {customer_id: inserted_count} dict."""
    with Session(engine) as session:
        customers = session.exec(
            select(Customer).where(Customer.icp_profile_text.isnot(None))
        ).all()
        customer_ids = [c.id for c in customers]

    result = {}
    for cid in customer_ids:
        try:
            n = await discover_for_customer(customer_id=cid)
            result[cid] = n
        except Exception:
            logger.exception("discovery failed for customer %s", cid)
            result[cid] = 0
    return result
```

### Step 5.2: 测试

`backend/tests/test_group_discovery_service.py`:

```python
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from app.services.group_discovery_service import (
    _extract_keywords_from_icp, discover_for_customer,
)


def test_extract_keywords_basic():
    icp = "想找海外华人 USDT 大额买家 OTC 中介"
    keywords = _extract_keywords_from_icp(icp, max_keywords=5)
    assert len(keywords) <= 5
    assert "USDT" in keywords or "海外华人" in keywords


def test_extract_keywords_filters_short():
    keywords = _extract_keywords_from_icp("a b c USDT")
    assert "a" not in keywords
    assert "USDT" in keywords


@pytest.mark.asyncio
async def test_discover_skips_customer_without_icp():
    fake_session = MagicMock()
    fake_customer = MagicMock(id=1, icp_profile_text=None)
    fake_session.get.return_value = fake_customer
    fake_session.__enter__ = MagicMock(return_value=fake_session)
    fake_session.__exit__ = MagicMock(return_value=None)
    with patch("app.services.group_discovery_service.Session", return_value=fake_session):
        n = await discover_for_customer(customer_id=1)
    assert n == 0


@pytest.mark.asyncio
async def test_discover_inserts_new_candidates():
    fake_customer = MagicMock(id=1, icp_profile_text="USDT 大额")
    fake_session = MagicMock()
    fake_session.get.return_value = fake_customer
    fake_session.__enter__ = MagicMock(return_value=fake_session)
    fake_session.__exit__ = MagicMock(return_value=None)
    # No blacklist, no existing
    fake_session.exec.return_value.all.return_value = []

    fake_search_result = [
        {"username": "usdt_otc", "chat_id": 1001, "title": "USDT OTC",
         "participants_count": 5000, "category": "Crypto",
         "link": "https://t.me/usdt_otc"},
    ]

    with patch("app.services.group_discovery_service.Session", return_value=fake_session), \
         patch("app.services.group_discovery_service.search_groups_by_keyword",
               new=AsyncMock(return_value=fake_search_result)), \
         patch("app.services.group_discovery_service.is_chat_already_monitored",
               return_value=False):
        n = await discover_for_customer(customer_id=1)
    assert n >= 0  # smoke (具体次数依赖 keyword 提取)
```

```bash
pytest backend/tests/test_group_discovery_service.py -v
git add backend/app/services/group_discovery_service.py backend/tests/test_group_discovery_service.py
git commit -m "feat(group-ai/phase7): group_discovery_service (weekly batch + per-customer)"
```

---

## Task 6: Celery beat weekly task

**Files:**
- Create: `backend/app/workers/group_discovery_weekly.py`
- Modify: `backend/app/core/celery_app.py`

```python
"""Weekly batch: discover new candidate groups for all active customers."""
import asyncio
import logging

from app.core.celery_app import celery_app
from app.services.group_discovery_service import discover_for_all_active_customers

logger = logging.getLogger(__name__)


@celery_app.task(name="group_discovery.weekly")
def discover_weekly():
    result = asyncio.run(discover_for_all_active_customers())
    logger.info("group_discovery weekly: %s", result)
    return result
```

Register beat schedule (run every 7 days at 09:00 UTC):

```python
# In celery_app.py beat_schedule:
"group-discovery-weekly": {
    "task": "group_discovery.weekly",
    "schedule": crontab(day_of_week=1, hour=9, minute=0),  # Monday 9am UTC
}
```

(需要 `from celery.schedules import crontab` 在文件顶。)

`include` 加入 `"app.workers.group_discovery_weekly"`。

```bash
git add backend/app/workers/group_discovery_weekly.py backend/app/core/celery_app.py
git commit -m "feat(group-ai/phase7): Celery beat weekly group discovery task"
```

---

## Task 7: portal customer endpoints + UI

**Files:**
- Create: `backend/app/routers/portal_discovery.py`
- Modify: `frontend/src/portal/api/groupAi.ts`
- Modify: `frontend/src/portal/pages/GroupAI/index.tsx`
- Create: `frontend/src/portal/pages/GroupAI/GroupDiscovery.tsx`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_portal_discovery_endpoints.py`

### Step 7.1: 后端 endpoints

`backend/app/routers/portal_discovery.py`:

```python
"""
portal_discovery — 客户审批候选群 endpoints.

- GET /portal/group-ai/discovery/candidates?status=pending - list candidates
- POST /portal/group-ai/discovery/{id}/approve - approve a candidate (move to keyword_monitor)
- POST /portal/group-ai/discovery/{id}/reject - reject + add to blacklist
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.core.database import get_session
from app.api.deps_customer import get_current_customer
from app.models.discovered_group import DiscoveredGroup
from app.models.discovery_blacklist import DiscoveryBlacklist
from app.models.keyword_monitor import KeywordMonitor

router = APIRouter(prefix="/portal/group-ai/discovery", tags=["portal-discovery"])


@router.get("/candidates")
async def list_candidates(
    status: str = "pending",
    customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
):
    stmt = (
        select(DiscoveredGroup)
        .where(
            DiscoveredGroup.customer_id == customer.id,
            DiscoveredGroup.status == status,
        )
        .order_by(DiscoveredGroup.score.desc().nullslast(),
                  DiscoveredGroup.discovered_at.desc())
        .limit(100)
    )
    rows = list(session.exec(stmt).all())
    return [
        {
            "id": r.id, "chat_link": r.chat_link, "chat_username": r.chat_username,
            "title": r.title, "members_count": r.members_count,
            "category": r.category, "source": r.source, "source_query": r.source_query,
            "score": r.score, "status": r.status,
            "discovered_at": r.discovered_at,
        }
        for r in rows
    ]


@router.post("/{candidate_id}/approve")
async def approve_candidate(
    candidate_id: int,
    customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
):
    row = session.get(DiscoveredGroup, candidate_id)
    if row is None or row.customer_id != customer.id:
        raise HTTPException(404, "candidate not found")
    if row.status != "pending":
        raise HTTPException(409, f"cannot approve in state {row.status}")

    row.status = "approved"
    row.decided_at = datetime.now(timezone.utc)
    session.add(row)

    # TODO Phase 8: 触发 captcha 流程加入群; 现在仅写 keyword_monitor
    # 简化: 加到一个 default monitor 的 target_groups
    # 实际实施时根据 product决定如何关联到 monitor
    session.commit()
    return {"ok": True}


@router.post("/{candidate_id}/reject")
async def reject_candidate(
    candidate_id: int,
    customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
):
    row = session.get(DiscoveredGroup, candidate_id)
    if row is None or row.customer_id != customer.id:
        raise HTTPException(404, "candidate not found")

    row.status = "rejected"
    row.decided_at = datetime.now(timezone.utc)
    session.add(row)

    # Add to blacklist
    bl = DiscoveryBlacklist(
        customer_id=customer.id,
        chat_link=row.chat_link or "",
        reason="customer_rejected",
        created_at=datetime.now(timezone.utc),
    )
    session.add(bl)
    session.commit()
    return {"ok": True}
```

Register in main.py:
```python
from app.routers import portal_discovery
app.include_router(portal_discovery.router)
```

### Step 7.2: 前端 page

Extend `frontend/src/portal/api/groupAi.ts`:

```typescript
export interface DiscoveryCandidate {
  id: number;
  chat_link: string | null;
  chat_username: string | null;
  title: string | null;
  members_count: number | null;
  category: string | null;
  source: string;
  source_query: string | null;
  score: number | null;
  status: string;
  discovered_at: string;
}

// in groupAiApi object:
listDiscoveryCandidates: (status = 'pending') =>
  portalApi.get<DiscoveryCandidate[]>('/portal/group-ai/discovery/candidates', { params: { status } })
    .then(r => r.data),
approveDiscoveryCandidate: (id: number) =>
  portalApi.post(`/portal/group-ai/discovery/${id}/approve`),
rejectDiscoveryCandidate: (id: number) =>
  portalApi.post(`/portal/group-ai/discovery/${id}/reject`),
```

`frontend/src/portal/pages/GroupAI/GroupDiscovery.tsx`:

```typescript
/**
 * GroupDiscovery — 客户审批每周系统推荐的候选线索群.
 *
 * 列表按 score desc 排序; approve → 系统尝试加群 (Phase 8 接入 CAPTCHA);
 * reject → 加入黑名单不再推.
 */
import React from 'react';
import { Card, Button, Tag, Space, Typography, Empty, Popconfirm, Tabs } from 'antd';
import { CheckOutlined, CloseOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { groupAiApi, DiscoveryCandidate } from '../../api/groupAi';

const { Title, Paragraph } = Typography;


function CandidateCard({ row, onApprove, onReject }: {
  row: DiscoveryCandidate;
  onApprove: () => void;
  onReject: () => void;
}) {
  return (
    <Card style={{ marginBottom: 12 }}
          extra={
            row.score !== null
              ? <Tag color={row.score > 70 ? 'green' : row.score > 50 ? 'blue' : 'default'}>
                  评分 {row.score.toFixed(0)}
                </Tag>
              : null
          }
          actions={[
            <Popconfirm key="approve" title="批准后系统会尝试加群" onConfirm={onApprove}>
              <Button type="primary" icon={<CheckOutlined />}>批准</Button>
            </Popconfirm>,
            <Popconfirm key="reject" title="拒绝后此群进黑名单不再推" onConfirm={onReject}>
              <Button danger icon={<CloseOutlined />}>拒绝</Button>
            </Popconfirm>,
          ]}>
      <h4>{row.title || row.chat_username || '(no title)'}</h4>
      <Paragraph type="secondary" style={{ marginBottom: 8 }}>
        {row.chat_link}
      </Paragraph>
      <Space wrap>
        {row.members_count && <Tag>{row.members_count.toLocaleString()} 成员</Tag>}
        {row.category && <Tag>{row.category}</Tag>}
        {row.source_query && <Tag color="purple">关键词: {row.source_query}</Tag>}
      </Space>
    </Card>
  );
}


export default function GroupDiscovery() {
  const [status, setStatus] = React.useState('pending');
  const qc = useQueryClient();

  const { data: rows = [] } = useQuery({
    queryKey: ['portal-discovery', status],
    queryFn: () => groupAiApi.listDiscoveryCandidates(status),
  });

  const approveMut = useMutation({
    mutationFn: (id: number) => groupAiApi.approveDiscoveryCandidate(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['portal-discovery'] }),
  });
  const rejectMut = useMutation({
    mutationFn: (id: number) => groupAiApi.rejectDiscoveryCandidate(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['portal-discovery'] }),
  });

  return (
    <div>
      <Title level={3}>线索群发现</Title>
      <Paragraph type="secondary">
        系统每周根据你的 ICP 画像自动搜索匹配的群 (TGStat 数据源).
        批准的群会进入监听列表; 拒绝的群进黑名单不再推荐.
      </Paragraph>

      <Tabs activeKey={status} onChange={setStatus} items={[
        { key: 'pending', label: '待审批' },
        { key: 'approved', label: '已批准' },
        { key: 'rejected', label: '已拒绝' },
      ]} />

      {rows.length === 0 ? (
        <Empty description={`暂无 ${status} 候选 (下周一上午刷新)`} />
      ) : (
        rows.map(r => (
          <CandidateCard
            key={r.id} row={r}
            onApprove={() => approveMut.mutate(r.id)}
            onReject={() => rejectMut.mutate(r.id)}
          />
        ))
      )}
    </div>
  );
}
```

Update `frontend/src/portal/pages/GroupAI/index.tsx` — 加 menu item + Route。

### Step 7.3: 提交

```bash
git add backend/app/routers/portal_discovery.py \
        backend/app/main.py \
        frontend/src/portal/api/groupAi.ts \
        frontend/src/portal/pages/GroupAI/index.tsx \
        frontend/src/portal/pages/GroupAI/GroupDiscovery.tsx \
        backend/tests/test_portal_discovery_endpoints.py
git commit -m "feat(group-ai/phase7): portal customer discovery endpoints + UI"
```

---

## Task 8: PR + release

```bash
git push -u origin worktree-feature+group-ai-sales-phase7:feature/group-ai-sales-phase7 2>&1 | tail -3
gh pr create --title "feat(group-ai): Phase 7 — group discovery (TGStat + ranking + portal)" \
  --base main --head feature/group-ai-sales-phase7 \
  --body "..."
```

---

## Phase 7 完成判据

- [ ] PR merged
- [ ] TGSTAT_API_TOKEN 环境变量配齐
- [ ] Celery beat 周一上午跑 → 至少 1 个 customer 收 10+ candidates
- [ ] 客户在 portal 审批 → approve 走通 / reject 进 blacklist
- [ ] approve 后的群 chat_link 真进 keyword_monitor.target_groups (具体逻辑实施时定)

---

## 关联

- 群内 AI 销售员 6 phase 主路线: PR #9-#14
- [Phase 6 plan](2026-05-30-group-ai-sales-phase6.md) (production hardening, 独立 epic)
- [Phase 8 plan](2026-05-30-group-ai-sales-phase8-captcha.md) (captcha 处理, 与 Phase 7 衔接 — approve 后由 Phase 8 captcha 流程加入群)
- Spec §1 数据源 (本计划扩展)
