# 群内 AI 销售员 Phase 8 实施计划（加群人机验证处理）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** worker 账号加入新群时，自动识别并通过常见人机验证（inline 按钮 / 文字 Q&A / 图片 CAPTCHA / 管理员 DM），失败的群进入"待人工处理"队列让客户/运营在 portal 看到。把"可加群率"从手工的不确定状态变成可量化（自动通过率 + 人工兜底比例）。

**Architecture:** 新增 `join_attempt` 状态机表 + 4 个 CAPTCHA handler（按 type 分发）+ failed_joins 队列 + portal UI。复用 Phase 1 main account 接管 + Phase 5 account_lifecycle_events 跟踪。

**Tech Stack:** FastAPI · SQLModel · Telethon · LLM (LLMService.generate for text Q&A) · Gemini Vision API (图片 CAPTCHA) · React

**Spec extension:** spec §1.2 提"自动加群"但未细化人机验证。本计划补全。

**前置条件：**
- Phase 1-7 全部 merge（Phase 7 的 discovery approve 是本 phase 输入源）
- Telethon 已配齐 worker session
- Gemini Vision API key（GEMINI_VISION_API_KEY 环境变量；可与现有 Gemini key 复用）
- 新 worktree `/var/tgsc/.claude/worktrees/feature+group-ai-sales-phase8`

**Phase 8 范围：**

| 包含 | 不含 |
|---|---|
| join_attempt 状态机 (pending / captcha / joined / failed) | 高级反爬（手机号验证 / 人脸） |
| Inline 按钮 CAPTCHA 自动 click | 邀请码 / 付费群处理 |
| 文字 Q&A LLM 回答 (含客户预设话术) | 邀请关系图（找熟人邀请） |
| 图片 CAPTCHA via Gemini Vision (识别 + click) | CAPTCHA 模板学习（reuse 答案） |
| 管理员 DM 申请模板 + 自动发送 | 多 worker 互助验证（一号请 admin，二号过 captcha） |
| 失败队列 portal UI + manual override | 退群后重加（cooldown 不在范围） |
| 1 张迁移（join_attempt + captcha_event） | 跨客户 captcha 答案共享 |

---

## File Structure

**新建：**
- `backend/app/models/join_attempt.py` — 加群尝试状态机表
- `backend/app/models/captcha_event.py` — 单次 CAPTCHA 事件 (handler/result)
- `backend/alembic/versions/<rev>_join_attempt_captcha.py`
- `backend/app/services/join_orchestrator.py` — 编排入口（Phase 7 approve 调）
- `backend/app/services/captcha_detector.py` — 识别 CAPTCHA 类型
- `backend/app/services/captcha_handlers/__init__.py`
- `backend/app/services/captcha_handlers/inline_button.py`
- `backend/app/services/captcha_handlers/text_qa.py`
- `backend/app/services/captcha_handlers/vision.py`
- `backend/app/services/captcha_handlers/admin_dm.py`
- `backend/app/services/gemini_vision_adapter.py`
- `backend/app/workers/join_attempt_scanner.py` — Celery beat 处理 pending
- `backend/app/routers/portal_join_failures.py`
- `backend/app/routers/admin_join_attempts.py`
- `frontend/src/portal/pages/GroupAI/JoinFailures.tsx`
- 7+ test 文件

**修改：**
- Phase 7 `portal_discovery.approve_candidate` — approve 后调 `join_orchestrator.queue_join`
- `backend/app/services/account_assignment.py` — 选 worker account 加群时挂 lifecycle hook
- `backend/app/main.py` — 注册 2 个新 router
- `backend/app/core/celery_app.py` — 注册 join_attempt scanner

---

## Task 1: join_attempt + captcha_event 表 + 迁移

**Files:**
- Create: `backend/app/models/join_attempt.py`
- Create: `backend/app/models/captcha_event.py`
- Create: `backend/alembic/versions/<rev>_join_attempt_captcha.py`
- Create: `backend/tests/test_join_attempt_model.py`

### Step 1.1: 迁移

```python
"""join_attempt_captcha

Revision ID: <REV>
Revises: <Phase 7 head rev>
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
        "join_attempt",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("customer_id", sa.Integer, sa.ForeignKey("customer.id"), nullable=False),
        sa.Column("account_id", sa.Integer, sa.ForeignKey("account.id"), nullable=False),
        sa.Column("discovered_group_id", sa.BigInteger,
                  sa.ForeignKey("discovered_group.id"), nullable=True),
        # discovered_group_id 可空: 也允许手工触发 join
        sa.Column("chat_link", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="pending"),
        # pending → joining → captcha → joined / failed / abandoned
        sa.Column("captcha_type", sa.Text, nullable=True),
        # inline_button | text_qa | vision | admin_dm | unknown
        sa.Column("captcha_attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "idx_join_attempt_status",
        "join_attempt", ["status", "updated_at"],
    )

    op.create_table(
        "captcha_event",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("join_attempt_id", sa.BigInteger,
                  sa.ForeignKey("join_attempt.id"), nullable=False),
        sa.Column("handler", sa.Text, nullable=False),
        sa.Column("input_summary", sa.Text, nullable=True),
        # e.g. "Click 'I am human' button" or "Q: 你怎么知道这群?"
        sa.Column("output_summary", sa.Text, nullable=True),
        # e.g. "Clicked button" or "Answered: 朋友推荐"
        sa.Column("succeeded", sa.Boolean, nullable=False),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "idx_captcha_event_attempt",
        "captcha_event", ["join_attempt_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_captcha_event_attempt", table_name="captcha_event")
    op.drop_table("captcha_event")
    op.drop_index("idx_join_attempt_status", table_name="join_attempt")
    op.drop_table("join_attempt")
```

### Step 1.2: SQLModel

`backend/app/models/join_attempt.py`:

```python
"""JoinAttempt — 加群尝试状态机"""
from datetime import datetime
from typing import Optional
from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, JSON, Text
from sqlmodel import Field, SQLModel


class JoinAttempt(SQLModel, table=True):
    __tablename__ = "join_attempt"

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
    customer_id: int = Field(sa_column=Column(Integer, ForeignKey("customer.id"), nullable=False))
    account_id: int = Field(sa_column=Column(Integer, ForeignKey("account.id"), nullable=False))
    discovered_group_id: Optional[int] = Field(
        default=None,
        sa_column=Column(BigInteger, ForeignKey("discovered_group.id"), nullable=True),
    )
    chat_link: str = Field(sa_column=Column(Text, nullable=False))
    status: str = Field(default="pending", sa_column=Column(Text, nullable=False))
    captcha_type: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    captcha_attempts: int = Field(default=0, sa_column=Column(Integer, nullable=False))
    last_error: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    metadata_json: Optional[dict] = Field(default=None, sa_column=Column(JSON, nullable=True))
    created_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=False),
    )
```

`backend/app/models/captcha_event.py`: similar pattern.

Register both in `models/__init__.py`.

### Step 1.3: 测试 + 提交

```bash
git commit -m "feat(group-ai/phase8): join_attempt + captcha_event tables"
```

---

## Task 2: captcha_detector — 识别 CAPTCHA 类型

**Files:**
- Create: `backend/app/services/captcha_detector.py`
- Create: `backend/tests/test_captcha_detector.py`

加入群后，监听前 5 条消息（10s 内）。识别 CAPTCHA 类型规则：
- 含 inline button 且按钮文字含 "human"/"verify"/"我不是机器人"/"点击"/"按钮" → inline_button
- 含问号且短文本 (< 50 char) → text_qa
- 含图片 + 提示文字 → vision
- 没新消息但 admin 私聊我 (新 DM) → admin_dm
- 既没消息也没 DM 且加群 30s 后已能发言 → no_captcha (直接成功)

```python
"""
captcha_detector — 识别加群后遇到的 CAPTCHA 类型.

调用时机: 加群后等 10s 拉前 5 条新消息.
返回: 'inline_button' | 'text_qa' | 'vision' | 'admin_dm' | 'no_captcha' | 'unknown'
"""
import logging

logger = logging.getLogger(__name__)


INLINE_KEYWORDS = ["human", "verify", "我不是", "robot", "captcha", "点击", "tap", "按一下"]
QA_INDICATORS = ["?", "？"]


def detect_captcha_type(
    *, recent_messages: list[dict], admin_dms_after_join: list[dict],
) -> dict:
    """
    recent_messages: [{"text": str, "buttons": [str], "has_photo": bool, "from_bot": bool}, ...]
    admin_dms_after_join: [{"text": str, "from_user_id": int}, ...]
    Returns: {"type": str, "evidence": {...}}
    """
    if not recent_messages and not admin_dms_after_join:
        return {"type": "no_captcha", "evidence": {}}

    # Check inline button
    for msg in recent_messages:
        if msg.get("buttons"):
            text = (msg.get("text") or "").lower()
            buttons_text = " ".join(msg.get("buttons", [])).lower()
            combined = text + " " + buttons_text
            if any(kw in combined for kw in INLINE_KEYWORDS):
                return {
                    "type": "inline_button",
                    "evidence": {"message": msg},
                }

    # Check vision (image + bot)
    for msg in recent_messages:
        if msg.get("has_photo") and msg.get("from_bot"):
            return {
                "type": "vision",
                "evidence": {"message": msg},
            }

    # Check text Q&A
    for msg in recent_messages:
        text = msg.get("text") or ""
        if msg.get("from_bot") and any(q in text for q in QA_INDICATORS) and len(text) < 100:
            return {
                "type": "text_qa",
                "evidence": {"question": text, "message": msg},
            }

    # Admin DM check
    if admin_dms_after_join:
        return {
            "type": "admin_dm",
            "evidence": {"dms": admin_dms_after_join},
        }

    return {"type": "unknown", "evidence": {"messages": recent_messages}}
```

### Step 2.2: 测试

`backend/tests/test_captcha_detector.py`:

```python
from app.services.captcha_detector import detect_captcha_type


def test_no_captcha_when_no_messages():
    result = detect_captcha_type(recent_messages=[], admin_dms_after_join=[])
    assert result["type"] == "no_captcha"


def test_inline_button_detection():
    msg = {"text": "Click button to verify", "buttons": ["I am human"], "has_photo": False, "from_bot": True}
    result = detect_captcha_type(recent_messages=[msg], admin_dms_after_join=[])
    assert result["type"] == "inline_button"


def test_text_qa_detection():
    msg = {"text": "你怎么知道这群的?", "buttons": [], "has_photo": False, "from_bot": True}
    result = detect_captcha_type(recent_messages=[msg], admin_dms_after_join=[])
    assert result["type"] == "text_qa"


def test_vision_detection():
    msg = {"text": "请选择所有汽车", "buttons": [], "has_photo": True, "from_bot": True}
    result = detect_captcha_type(recent_messages=[msg], admin_dms_after_join=[])
    assert result["type"] == "vision"


def test_admin_dm_detection():
    dm = {"text": "你为什么想加我们群?", "from_user_id": 5000}
    result = detect_captcha_type(recent_messages=[], admin_dms_after_join=[dm])
    assert result["type"] == "admin_dm"


def test_unknown_when_no_match():
    msg = {"text": "Hello", "buttons": [], "has_photo": False, "from_bot": False}
    result = detect_captcha_type(recent_messages=[msg], admin_dms_after_join=[])
    assert result["type"] == "unknown"
```

```bash
pytest backend/tests/test_captcha_detector.py -v
git add backend/app/services/captcha_detector.py backend/tests/test_captcha_detector.py
git commit -m "feat(group-ai/phase8): captcha_detector (inline/qa/vision/admin_dm/no_captcha)"
```

---

## Task 3: inline_button handler

**Files:**
- Create: `backend/app/services/captcha_handlers/inline_button.py`
- Create: `backend/tests/test_captcha_handler_inline_button.py`

```python
"""Handle inline button CAPTCHA: click the verify button."""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


VERIFY_BUTTON_KEYWORDS = ["human", "verify", "我不是机器人", "通过", "i am", "yes", "确认"]


async def solve_inline_button(*, telethon_client, message, dry_run: bool = False) -> dict:
    """
    message: telethon Message with reply_markup (inline keyboard).
    返回: {"success": bool, "clicked_button": str | None, "error": str | None}
    """
    if not message.reply_markup:
        return {"success": False, "clicked_button": None, "error": "no_keyboard"}

    target_button = None
    for row in message.buttons or []:
        for btn in row:
            btn_text = (btn.text or "").lower()
            if any(kw.lower() in btn_text for kw in VERIFY_BUTTON_KEYWORDS):
                target_button = btn
                break
        if target_button:
            break

    if not target_button:
        return {"success": False, "clicked_button": None, "error": "no_verify_button_found"}

    if dry_run:
        return {"success": True, "clicked_button": target_button.text, "error": None}

    try:
        await target_button.click()
        return {"success": True, "clicked_button": target_button.text, "error": None}
    except Exception as e:
        logger.exception("inline button click failed")
        return {"success": False, "clicked_button": target_button.text, "error": str(e)}
```

Test (mock telethon button):

```python
import pytest
from unittest.mock import MagicMock, AsyncMock

from app.services.captcha_handlers.inline_button import solve_inline_button


@pytest.mark.asyncio
async def test_clicks_verify_button():
    fake_btn = MagicMock(text="I am human")
    fake_btn.click = AsyncMock()
    fake_msg = MagicMock(
        reply_markup=MagicMock(),
        buttons=[[fake_btn]],
    )
    result = await solve_inline_button(telethon_client=None, message=fake_msg)
    assert result["success"] is True
    fake_btn.click.assert_awaited_once()


@pytest.mark.asyncio
async def test_dry_run_no_click():
    fake_btn = MagicMock(text="Verify")
    fake_btn.click = AsyncMock()
    fake_msg = MagicMock(reply_markup=MagicMock(), buttons=[[fake_btn]])
    result = await solve_inline_button(telethon_client=None, message=fake_msg, dry_run=True)
    assert result["success"] is True
    fake_btn.click.assert_not_awaited()
```

```bash
git commit -m "feat(group-ai/phase8): inline_button captcha handler"
```

---

## Task 4: text_qa handler

**Files:**
- Create: `backend/app/services/captcha_handlers/text_qa.py`
- Create: `backend/tests/test_captcha_handler_text_qa.py`

LLM 生成回答。客户在 portal 预先填一段 "我们怎么知道这群的"模板（如 "看 @xxx 推荐的 / 行业群朋友介绍"），LLM 据此回答。

```python
"""Handle text Q&A captcha: LLM generates answer using customer-provided context."""
import logging
from typing import Optional

from sqlmodel import Session

from app.core.db import engine
from app.services.llm import LLMService

logger = logging.getLogger(__name__)


async def solve_text_qa(
    *, telethon_client, chat_id: int, question: str,
    customer_join_template: Optional[str], dry_run: bool = False,
) -> dict:
    """
    customer_join_template: 客户预填的"我们如何知道这个群" 上下文.
    返回: {"success", "answer", "error"}
    """
    if not question or not question.strip():
        return {"success": False, "answer": None, "error": "empty_question"}

    template_block = customer_join_template or "我是行业内朋友推荐知道的"
    prompt = f"""你是一个加入 TG 群的新成员, 群里 bot 问了一个验证问题. 简短回答 (不超 30 字), 用日常口语:

背景 (你为什么加这群): {template_block}

问题: {question}

回答:
"""

    with Session(engine) as session:
        svc = LLMService(session)
        answer = await svc.generate(prompt, source="captcha_text_qa")

    if not answer or len(answer) > 100:
        return {"success": False, "answer": answer, "error": "bad_llm_response"}

    if dry_run:
        return {"success": True, "answer": answer, "error": None}

    try:
        await telethon_client.send_message(chat_id, answer)
        return {"success": True, "answer": answer, "error": None}
    except Exception as e:
        logger.exception("text_qa send failed")
        return {"success": False, "answer": answer, "error": str(e)}
```

```bash
pytest backend/tests/test_captcha_handler_text_qa.py -v
git commit -m "feat(group-ai/phase8): text_qa captcha handler (LLM + customer template)"
```

---

## Task 5: gemini_vision_adapter + vision handler

**Files:**
- Create: `backend/app/services/gemini_vision_adapter.py`
- Create: `backend/app/services/captcha_handlers/vision.py`
- Create: tests

### Step 5.1: vision adapter

```python
"""
gemini_vision_adapter — 调 Gemini Pro Vision 识别 CAPTCHA 图片.
Returns: 文本描述图片内容 + 建议的 click action.
"""
import base64
import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


GEMINI_VISION_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-1.5-flash:generateContent"
)


async def analyze_captcha_image(
    *, image_bytes: bytes, prompt_hint: str = "",
) -> Optional[str]:
    """
    image_bytes: raw 图片 bytes (PNG/JPEG)
    prompt_hint: 群 bot 的提示文字 e.g. "请选择所有汽车"
    Returns: LLM 的描述 + 建议 (e.g. "图片显示 6 个格子, 第 1,3,5 格是汽车")
    或 None on failure.
    """
    key = os.getenv("GEMINI_VISION_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not key:
        logger.warning("GEMINI_VISION_API_KEY not set; vision captcha disabled")
        return None

    b64 = base64.b64encode(image_bytes).decode("ascii")
    body = {
        "contents": [{
            "parts": [
                {"text": f"分析这张 CAPTCHA 图片. {prompt_hint}\n描述图片内容并建议如何回答."},
                {"inline_data": {"mime_type": "image/png", "data": b64}},
            ],
        }],
        "generationConfig": {"maxOutputTokens": 200},
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                f"{GEMINI_VISION_URL}?key={key}", json=body,
            )
            r.raise_for_status()
            data = r.json()
    except Exception:
        logger.exception("Gemini Vision call failed")
        return None

    candidates = data.get("candidates", [])
    if not candidates:
        return None
    content = candidates[0].get("content", {}).get("parts", [])
    if not content:
        return None
    return content[0].get("text", "").strip()
```

### Step 5.2: vision handler

```python
"""Vision CAPTCHA handler: download image → Gemini Vision → answer/click."""
import logging
from typing import Optional

from app.services.gemini_vision_adapter import analyze_captcha_image

logger = logging.getLogger(__name__)


async def solve_vision(
    *, telethon_client, message, dry_run: bool = False,
) -> dict:
    """
    返回: {"success", "analysis", "action_taken", "error"}
    """
    if not message.photo:
        return {"success": False, "analysis": None, "action_taken": None, "error": "no_photo"}

    try:
        image_bytes = await telethon_client.download_media(message, file=bytes)
    except Exception as e:
        return {"success": False, "analysis": None, "action_taken": None, "error": f"download_failed: {e}"}

    prompt_hint = message.text or ""
    analysis = await analyze_captcha_image(image_bytes=image_bytes, prompt_hint=prompt_hint)
    if not analysis:
        return {"success": False, "analysis": None, "action_taken": None, "error": "vision_api_failed"}

    # Phase 8 简化: vision 仅做 analysis + 标记 success
    # 实际 click action 依赖 captcha 形式 (inline button 通常配合 vision)
    # 如果有 inline button, 由 inline_button handler 接管
    # 这里仅返回 analysis 供后续处理 / 人工 review
    if dry_run:
        return {"success": True, "analysis": analysis, "action_taken": None, "error": None}

    # 简化: vision 单独不能自动通过, 标记 success_partial
    return {
        "success": False,  # Phase 8 起点: vision 仅分析, 标记 manual review
        "analysis": analysis,
        "action_taken": "manual_review_needed",
        "error": None,
    }
```

```bash
git commit -m "feat(group-ai/phase8): Gemini Vision adapter + vision captcha handler"
```

> **Note**: vision CAPTCHA full automation (识别 + click 正确位置) 复杂度高，Phase 8 仅做 analysis + 人工 review。完整自动化是后续 epic.

---

## Task 6: admin_dm handler

**Files:**
- Create: `backend/app/services/captcha_handlers/admin_dm.py`
- Create: tests

```python
"""Admin DM handler: send customer-template intro DM to group admin."""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def solve_admin_dm(
    *, telethon_client, admin_user_id: int,
    customer_intro_template: Optional[str], dry_run: bool = False,
) -> dict:
    """
    customer_intro_template: 客户预填的"申请加群"模板.
    e.g. "你好, 看到xx推荐的, 想加群学习交流."
    """
    if not customer_intro_template:
        return {"success": False, "answer": None, "error": "no_template_set"}

    if dry_run:
        return {"success": True, "answer": customer_intro_template, "error": None}

    try:
        await telethon_client.send_message(admin_user_id, customer_intro_template)
        return {"success": True, "answer": customer_intro_template, "error": None}
    except Exception as e:
        return {"success": False, "answer": None, "error": str(e)}
```

```bash
git commit -m "feat(group-ai/phase8): admin_dm captcha handler (template-based intro DM)"
```

---

## Task 7: join_orchestrator — 主编排

**Files:**
- Create: `backend/app/services/join_orchestrator.py`
- Create: `backend/tests/test_join_orchestrator.py`

整合：detector + handlers + state machine 写入 join_attempt + lifecycle_event.

```python
"""
join_orchestrator — 加群编排.

调用时机:
  - Phase 7 portal_discovery.approve_candidate 调 queue_join()
  - admin 手工触发也调 queue_join()

Celery beat scanner 处理 status='pending' 的行.

状态机:
  pending  → joining: telethon JoinChannelRequest sent
  joining  → captcha: detector 返回非 'no_captcha'
  captcha  → joined: handler success + 能发言
  joining  → joined: 直接成功 (no captcha)
  captcha  → failed: handler 失败 N 次 (3)
  joining/captcha → failed: telethon 异常 / chat 私有不可达
"""
import asyncio
import logging
from datetime import datetime, timezone

from sqlmodel import Session

from app.core.db import engine
from app.models.join_attempt import JoinAttempt
from app.models.captcha_event import CaptchaEvent
from app.services.captcha_detector import detect_captcha_type
from app.services.captcha_handlers import (
    inline_button, text_qa, vision, admin_dm,
)

logger = logging.getLogger(__name__)

MAX_CAPTCHA_ATTEMPTS = 3


def queue_join(
    *, customer_id: int, account_id: int, chat_link: str,
    discovered_group_id: int | None = None,
) -> int:
    """Insert pending row. Returns join_attempt.id"""
    now = datetime.now(timezone.utc)
    attempt = JoinAttempt(
        customer_id=customer_id, account_id=account_id,
        chat_link=chat_link, discovered_group_id=discovered_group_id,
        status="pending", captcha_attempts=0,
        created_at=now, updated_at=now,
    )
    with Session(engine) as session:
        session.add(attempt)
        session.commit()
        session.refresh(attempt)
    return attempt.id


async def process_attempt(*, attempt_id: int) -> str:
    """
    Process one attempt end-to-end. Returns final status.
    """
    with Session(engine) as session:
        attempt = session.get(JoinAttempt, attempt_id)
        if attempt is None:
            return "not_found"
        if attempt.status not in ("pending", "captcha"):
            return attempt.status

    # ... (Telethon client lookup by account_id, join via JoinChannelRequest)
    # ... (after join: wait 10s, fetch recent messages + check admin DMs)
    # ... (detect_captcha_type → dispatch handler)
    # ... (handler success → update status='joined', save lifecycle event)
    # ... (handler fail + attempts < MAX: retry; >= MAX: status='failed')

    # 实施者: 这部分 Telethon 集成需要根据现有 listener_service 的 client 管理方式
    # 来实现. 简化伪代码:
    #
    # client = await get_telethon_client(account_id)
    # await client(JoinChannelRequest(chat_link))
    # await asyncio.sleep(10)
    # msgs = await client.get_messages(chat_link, limit=5)
    # detection = detect_captcha_type(...)
    # if detection['type'] == 'inline_button':
    #     result = await inline_button.solve_inline_button(...)
    # elif ... etc
    #
    # _update_attempt(attempt_id, status=..., captcha_type=..., last_error=...)
    # _insert_captcha_event(...)

    return "joined"  # 占位; 实际依实施


def _update_attempt(*, attempt_id: int, **fields) -> None:
    with Session(engine) as session:
        attempt = session.get(JoinAttempt, attempt_id)
        if attempt is None:
            return
        for k, v in fields.items():
            setattr(attempt, k, v)
        attempt.updated_at = datetime.now(timezone.utc)
        session.add(attempt)
        session.commit()


def _insert_captcha_event(
    *, join_attempt_id: int, handler: str,
    succeeded: bool, input_summary: str = "", output_summary: str = "",
    error_message: str | None = None,
) -> None:
    with Session(engine) as session:
        evt = CaptchaEvent(
            join_attempt_id=join_attempt_id, handler=handler,
            input_summary=input_summary, output_summary=output_summary,
            succeeded=succeeded, error_message=error_message,
            created_at=datetime.now(timezone.utc),
        )
        session.add(evt)
        session.commit()
```

### Step 7.2: 测试 (mock 重)

简化测试覆盖 state machine 转换：

```python
# Test queue_join, _update_attempt status flow, _insert_captcha_event
# Real Telethon 集成测试留到 staging
```

```bash
git commit -m "feat(group-ai/phase8): join_orchestrator state machine + handlers dispatch"
```

---

## Task 8: Celery beat scanner

```python
"""Celery beat task: scan pending join_attempts and process."""
import asyncio
import logging
from datetime import datetime, timezone, timedelta

from sqlmodel import Session, select

from app.core.celery_app import celery_app
from app.core.db import engine
from app.models.join_attempt import JoinAttempt
from app.services.join_orchestrator import process_attempt

logger = logging.getLogger(__name__)


async def scan_and_process() -> int:
    """Process pending + captcha-state attempts older than 10s."""
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=10)
    with Session(engine) as session:
        rows = session.exec(
            select(JoinAttempt.id).where(
                JoinAttempt.status.in_(["pending", "captcha"]),
                JoinAttempt.updated_at <= cutoff,
            ).limit(50)
        ).all()
        ids = [r for r in rows]

    n = 0
    for attempt_id in ids:
        try:
            await process_attempt(attempt_id=attempt_id)
            n += 1
        except Exception:
            logger.exception("join scanner failed for %s", attempt_id)
    return n


@celery_app.task(name="join_attempt.scan")
def scan_tick():
    return asyncio.run(scan_and_process())
```

Register beat schedule (run every 60s).

```bash
git commit -m "feat(group-ai/phase8): Celery beat scanner for join_attempt processing"
```

---

## Task 9: portal failure queue UI + endpoints

**Files:**
- Create: `backend/app/routers/portal_join_failures.py`
- Modify: `frontend/src/portal/api/groupAi.ts`
- Create: `frontend/src/portal/pages/GroupAI/JoinFailures.tsx`

客户在 portal 看到 failed join 列表 + 手动处理建议（"找熟人邀请" / "买邀请码" / "放弃"）。

Endpoints:
- `GET /portal/group-ai/join/failures` — list failed join_attempts
- `POST /portal/group-ai/join/{id}/abandon` — mark abandoned (不再 retry)

Portal page: Table + Action buttons.

```bash
git commit -m "feat(group-ai/phase8): portal failure queue UI + endpoints"
```

---

## Task 10: Phase 7 integration

修改 Phase 7 `portal_discovery.approve_candidate` —— 在 approve 后调 `join_orchestrator.queue_join`:

```python
# In approve_candidate, after status='approved' commit:
from app.services.join_orchestrator import queue_join
from app.services.account_assignment import pick_worker_account_for_chat

worker_acc = pick_worker_account_for_chat(
    session=session, customer_id=customer.id, chat_link=row.chat_link,
)
if worker_acc:
    queue_join(
        customer_id=customer.id,
        account_id=worker_acc.id,
        chat_link=row.chat_link,
        discovered_group_id=row.id,
    )
```

```bash
git commit -m "feat(group-ai/phase8): Phase 7 approve → queue_join integration"
```

---

## Task 11: 全测试 + PR

```bash
pytest backend/tests/ -k "phase8 or join_attempt or captcha or vision or join_orchestrator" -v
git push -u origin worktree-feature+group-ai-sales-phase8:feature/group-ai-sales-phase8
gh pr create --title "feat(group-ai): Phase 8 — captcha handling for auto-join" ...
```

---

## Phase 8 完成判据

- [ ] PR merged
- [ ] 灰度: queue 10 个 Phase 7 approve 的群
- [ ] 至少 4 个自动通过 (inline_button + text_qa)
- [ ] 至少 1 个进 failure queue (vision 或 admin_dm)
- [ ] 客户在 portal 能看到 failure 队列 + 操作
- [ ] account_lifecycle_events 写入 join_succeeded / join_failed

---

## 关联

- [Phase 7 plan](2026-05-30-group-ai-sales-phase7-group-discovery.md) — 群发现 (Phase 8 输入)
- [Phase 6 plan](2026-05-30-group-ai-sales-phase6.md) — 生产强化 (account_lifecycle_events 复用)
- Spec §1.2 (扩展)
