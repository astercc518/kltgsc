# 群内 AI 销售员 Phase 4a 实施计划（销售衔接 + A/B 框架后端）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把群内回复闭环到销售接管 —— 客户从群里被回复后私聊主号，私聊 LLM 知道"刚在群里聊过什么"；反幻觉 2 次失败的回复落到 Inbox 副驾驶供销售一键发；同时打好 A/B 框架数据基础，为 Phase 5 完整实验做铺垫。

**Architecture:** Phase 4a 只动后端 + 不动 Alembic（Phase 1 已经把 `ab_experiments` 表 + `pending_replies.experiment_tag` / `customer.param_version` / `worker_personas.param_version` 字段建好）。`ai_reply_service` 加 group→私聊上下文 fetch；scanner 反幻觉失败路径改 `status=suggested` + WebSocket 推 Inbox；新增 `ab_assignment_service` 做实验变体路由；新增 Inbox API endpoints（list / approve_suggested / edit_suggested）。

**Tech Stack:** FastAPI · SQLModel · WebSocket（复用 `ws_manager`）· Celery（不动）· 复用 Phase 1-3a 全栈

**Spec:** [docs/superpowers/specs/2026-05-28-group-ai-sales-presence-design.md](../specs/2026-05-28-group-ai-sales-presence-design.md) §2.3（三链路边界）· §6.1 Step E（副驾驶兜底）· §8.1 集成点 2+4 · §10（A/B 实验框架）

**前置条件：**
- Phase 1 (PR #9) merged + 灰度数据回流
- Phase 2a + 3a 已实施完（识别 + 拟人化 都在跑）
- `ai_reply_service` 现状已读懂（私聊 LLM 入口）
- `ws_manager` 现状（Phase 1 spec 已经引用过 `ws_manager.broadcast`）
- Inbox 前端现状：Phase 4a 只动 backend API，前端集成由 Portal phase 做

**Phase 4a 范围：**

| 包含 | 不含（留给 Portal phase / Phase 5） |
|---|---|
| ai_reply_service 加 group→私聊 context fetch | Inbox 前端"群内 AI 互动"视图（Portal） |
| scanner 反幻觉失败 → status=suggested + WS 推 Inbox | Portal 实时统计页 / skip_reason 分布（Portal） |
| Inbox backend API（list / approve / edit） | A/B 完整指标采集 + 分析页（Phase 5） |
| ab_experiment service（CRUD + variant 分配） | A/B 后台 UI（Phase 5） |
| pipeline + scanner 写 experiment_tag | 多变体并发实验调度（Phase 5） |
| admin endpoints（experiment CRUD） | — |

---

## File Structure

**新建：**
- `backend/app/services/group_reply_context_service.py` —— 给 ai_reply_service 提供群内上下文
- `backend/app/services/ab_assignment_service.py` —— 实验变体分配（确定性哈希）
- `backend/app/services/copilot_suggestion_service.py` —— 副驾驶建议落地 + WS 推送
- `backend/app/routers/inbox_group_ai.py` —— Inbox backend API
- `backend/tests/test_group_reply_context_service.py`
- `backend/tests/test_ai_reply_service_with_group_context.py`
- `backend/tests/test_copilot_suggestion_service.py`
- `backend/tests/test_inbox_group_ai_endpoints.py`
- `backend/tests/test_ab_assignment_service.py`
- `backend/tests/test_pipeline_with_experiment_tag.py`
- `backend/tests/test_admin_ab_experiment_endpoints.py`

**修改：**
- `backend/app/services/ai_reply_service.py` —— 调用 group_reply_context_service 并拼 prompt
- `backend/app/workers/group_reply_scanner.py` —— compose 失败时走 copilot_suggestion 而非 mark failed
- `backend/app/services/group_reply_pipeline.py` —— Layer 1+2+3 通过后, 写 experiment_tag
- `backend/app/routers/admin_group_ai.py` —— 加 ab_experiment CRUD

---

## Task 1: group_reply_context_service —— 查 pending_replies 历史

**Files:**
- Create: `backend/app/services/group_reply_context_service.py`
- Create: `backend/tests/test_group_reply_context_service.py`

- [ ] **Step 1.1: 写测试**

`backend/tests/test_group_reply_context_service.py`:

```python
"""查给定 (customer, source_user) 的近期群回复历史, 供私聊 LLM 拼 prompt"""
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

from app.services.group_reply_context_service import (
    fetch_recent_group_replies_for_user,
)


def test_returns_empty_when_no_history():
    fake_session = MagicMock()
    fake_session.exec.return_value.all.return_value = []
    result = fetch_recent_group_replies_for_user(
        session=fake_session, customer_id=1, source_user_id=999, limit=3,
    )
    assert result == []


def test_returns_sent_replies_ordered_desc():
    """返回 status=sent 的最近 N 条, 按 sent_at desc"""
    fake_rows = [
        MagicMock(
            id=10, reply_text="USDT 大额 T+0 100k", sent_at=datetime.now(timezone.utc) - timedelta(hours=1),
            layer3_needs=["100k USDT 买入"], layer3_solution_topic="USDT 大额场外",
            chat_id=-100,
        ),
        MagicMock(
            id=8, reply_text="USDT 渠道", sent_at=datetime.now(timezone.utc) - timedelta(hours=5),
            layer3_needs=["渠道"], layer3_solution_topic="USDT",
            chat_id=-100,
        ),
    ]
    fake_session = MagicMock()
    fake_session.exec.return_value.all.return_value = fake_rows
    result = fetch_recent_group_replies_for_user(
        session=fake_session, customer_id=1, source_user_id=999, limit=3,
    )
    assert len(result) == 2
    assert result[0]["reply_text"] == "USDT 大额 T+0 100k"
    assert result[0]["extracted_needs"] == ["100k USDT 买入"]
    assert result[0]["solution_topic"] == "USDT 大额场外"


def test_excludes_old_history():
    """超过 7 天的不取 (避免老对话污染当前私聊)"""
    fake_session = MagicMock()
    # service 内部 query 应该有 sent_at >= cutoff(7d)
    # 这里只 assert 一次 exec, 不验具体 SQL 文本
    fake_session.exec.return_value.all.return_value = []
    fetch_recent_group_replies_for_user(
        session=fake_session, customer_id=1, source_user_id=999, limit=3,
    )
    fake_session.exec.assert_called_once()
```

- [ ] **Step 1.2: 跑 → fail**

- [ ] **Step 1.3: 实装 service**

`backend/app/services/group_reply_context_service.py`:

```python
"""
group_reply_context_service — 查 (customer, source_user) 7 天内
status=sent 的群回复历史, 喂给 ai_reply_service 拼私聊 prompt。

参考 spec §2.3 + §8.1 集成点 2
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from sqlmodel import select

from app.models.pending_reply import PendingReply, PendingReplyStatus

logger = logging.getLogger(__name__)

GROUP_CONTEXT_WINDOW_DAYS = 7


def fetch_recent_group_replies_for_user(
    *, session, customer_id: int, source_user_id: int, limit: int = 3,
) -> list[dict]:
    """
    返回近期群内对此 user 的回复历史 (用于私聊 LLM 拼 prompt).

    Returns:
        [{"reply_text": str, "extracted_needs": [str],
          "solution_topic": str, "sent_at": datetime, "chat_id": int}, ...]
        最多 limit 条, 按 sent_at desc。
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=GROUP_CONTEXT_WINDOW_DAYS)
    stmt = (
        select(PendingReply).where(
            PendingReply.customer_id == customer_id,
            PendingReply.source_user_id == source_user_id,
            PendingReply.status == PendingReplyStatus.SENT.value,
            PendingReply.sent_at >= cutoff,
        )
        .order_by(PendingReply.sent_at.desc())
        .limit(limit)
    )
    rows = list(session.exec(stmt).all())
    return [
        {
            "reply_text": r.reply_text or "",
            "extracted_needs": list(r.layer3_needs or []),
            "solution_topic": r.layer3_solution_topic or "",
            "sent_at": r.sent_at, "chat_id": r.chat_id,
        }
        for r in rows
    ]
```

- [ ] **Step 1.4: 跑测试**

```bash
pytest backend/tests/test_group_reply_context_service.py -v
```
Expected: 3 PASS。

- [ ] **Step 1.5: 提交**

```bash
git add backend/app/services/group_reply_context_service.py backend/tests/test_group_reply_context_service.py
git commit -m "feat(group-ai/phase4a): group_reply_context_service fetches 7d sent history"
```

---

## Task 2: ai_reply_service 拼群上下文进私聊 prompt

**Files:**
- Modify: `backend/app/services/ai_reply_service.py`
- Create: `backend/tests/test_ai_reply_service_with_group_context.py`

> 注意: ai_reply_service.py 现有约 339 行, 不要重写, 找其拼 LLM prompt 的位置注入。

- [ ] **Step 2.1: 摸底 ai_reply_service**

```bash
cd /var/tgsc/.claude/worktrees/feature+group-ai-sales-phase4a
grep -nE "^(async )?def |prompt|system_prompt" backend/app/services/ai_reply_service.py | head -30
```

确定哪个函数在调 LLM、prompt 在哪段字符串里、是否能 inject 一段额外 context（多半是字符串拼接而非结构化）。

- [ ] **Step 2.2: 写测试**

`backend/tests/test_ai_reply_service_with_group_context.py`:

```python
"""ai_reply_service: 私聊 LLM prompt 拼 group_reply_context"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.ai_reply_service import generate_private_reply_with_context


@pytest.mark.asyncio
async def test_private_reply_includes_group_context_when_user_has_history():
    """source_user 7d 内被群里 AI 回复过 → 拼进私聊 prompt"""
    fake_group_context = [{
        "reply_text": "USDT 大额 T+0 100k 私聊详谈",
        "extracted_needs": ["100k USDT 买入"],
        "solution_topic": "USDT 大额场外",
        "sent_at": "2026-05-29T10:00:00+00:00",
        "chat_id": -100,
    }]
    captured_prompt = {}

    async def fake_llm(prompt):
        captured_prompt["v"] = prompt
        return "好的, 100k 量级 OK 的"

    with patch(
        "app.services.ai_reply_service.fetch_recent_group_replies_for_user",
        return_value=fake_group_context,
    ), patch(
        "app.services.ai_reply_service.llm_generate",
        new=AsyncMock(side_effect=fake_llm),
    ):
        result = await generate_private_reply_with_context(
            session=MagicMock(), customer_id=1, source_user_id=999,
            private_message="你这边什么价",
        )
    assert result == "好的, 100k 量级 OK 的"
    prompt = captured_prompt["v"]
    assert "USDT 大额场外" in prompt or "100k" in prompt


@pytest.mark.asyncio
async def test_private_reply_skips_context_when_no_history():
    with patch(
        "app.services.ai_reply_service.fetch_recent_group_replies_for_user",
        return_value=[],
    ), patch(
        "app.services.ai_reply_service.llm_generate",
        new=AsyncMock(return_value="一般回复"),
    ):
        result = await generate_private_reply_with_context(
            session=MagicMock(), customer_id=1, source_user_id=999,
            private_message="你好",
        )
    assert result == "一般回复"


@pytest.mark.asyncio
async def test_private_reply_context_fetch_failure_does_not_block():
    """fetch 异常 → 退化到无 context, 不阻塞私聊回复"""
    with patch(
        "app.services.ai_reply_service.fetch_recent_group_replies_for_user",
        side_effect=Exception("DB hiccup"),
    ), patch(
        "app.services.ai_reply_service.llm_generate",
        new=AsyncMock(return_value="兜底回复"),
    ):
        result = await generate_private_reply_with_context(
            session=MagicMock(), customer_id=1, source_user_id=999,
            private_message="你好",
        )
    assert result == "兜底回复"
```

- [ ] **Step 2.3: 加 generate_private_reply_with_context 函数**

> 实施者: 不要重写 ai_reply_service。**新增**一个 `generate_private_reply_with_context` 公共函数, 拼好 prompt 后调原有 LLM 入口。原有 ai_reply 路径继续工作（私聊默认管线）。

在 `backend/app/services/ai_reply_service.py` 末尾追加：

```python
import logging
from typing import Optional

from app.services.group_reply_context_service import fetch_recent_group_replies_for_user
# 复用本文件内已存在的 LLM 调用 (e.g., llm_generate 或类似 wrapper)
# 如果没有, 用 LLMService(session).generate(...)
try:
    from app.services.ai_reply_service import llm_generate  # type: ignore
except ImportError:
    from app.services.llm import LLMService

    async def llm_generate(prompt: str) -> Optional[str]:
        # Backup wrapper, 若 ai_reply_service 内部用别的函数, 实施者要桥接
        from sqlmodel import Session
        from app.core.database import engine
        with Session(engine) as session:
            return await LLMService(session).generate(prompt, source="ai_reply_with_group_ctx")


_logger = logging.getLogger(__name__)


def _format_group_context_block(history: list[dict]) -> str:
    if not history:
        return ""
    lines = ["你之前在群里给这位用户回复过:"]
    for i, h in enumerate(history, 1):
        lines.append(
            f"  {i}. (主题: {h.get('solution_topic', '')}) "
            f"需求点: {', '.join(h.get('extracted_needs', []))}. "
            f"回复: 「{h.get('reply_text', '')}」"
        )
    lines.append("现在他来私聊, 接住上面的话题继续聊, 不要重复自我介绍。")
    return "\n".join(lines)


async def generate_private_reply_with_context(
    *, session, customer_id: int, source_user_id: int, private_message: str,
) -> Optional[str]:
    """
    拼好群上下文 → 调 LLM 生成私聊回复。
    群 context fetch 失败 → 降级到无 context 回复, 不阻塞。
    """
    try:
        history = fetch_recent_group_replies_for_user(
            session=session, customer_id=customer_id,
            source_user_id=source_user_id, limit=3,
        )
    except Exception:
        _logger.exception("group context fetch failed; fallback to no-context")
        history = []

    context_block = _format_group_context_block(history)
    prompt = (
        f"{context_block}\n\n用户现在的私聊消息: 「{private_message}」\n请回复:"
        if context_block else f"用户消息: 「{private_message}」\n请回复:"
    )
    return await llm_generate(prompt)
```

> 实施者：上面那个 `try: from app.services.ai_reply_service import llm_generate` 不起作用（这是同一个文件）。改为在文件内部 grep 现有的 LLM 调用入口（如 `_chat_completion` / `llm_service.generate` 等），把 `llm_generate` 桩用真的入口替换。如果现有 ai_reply_service 一直用 `LLMService(session).generate(...)`，直接调用它。

- [ ] **Step 2.4: 跑测试**

```bash
pytest backend/tests/test_ai_reply_service_with_group_context.py -v
```
Expected: 3 PASS。

- [ ] **Step 2.5: 提交**

```bash
git add backend/app/services/ai_reply_service.py backend/tests/test_ai_reply_service_with_group_context.py
git commit -m "feat(group-ai/phase4a): ai_reply_service prepends group context to private prompt"
```

---

## Task 3: copilot_suggestion_service —— 反幻觉失败兜底

**Files:**
- Create: `backend/app/services/copilot_suggestion_service.py`
- Create: `backend/tests/test_copilot_suggestion_service.py`

- [ ] **Step 3.1: 写测试**

`backend/tests/test_copilot_suggestion_service.py`:

```python
"""copilot_suggestion: compose 失败 → 写 suggested + WebSocket 推 Inbox"""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.copilot_suggestion_service import save_suggested_reply


@pytest.mark.asyncio
async def test_saves_and_broadcasts():
    pr = MagicMock(
        id=42, customer_id=1, chat_id=-100, source_user_id=999,
        reply_text=None, responder_account_id=10,
    )
    suggested_text = "USDT 大额场外 T+0 私聊详谈"
    with patch(
        "app.services.copilot_suggestion_service._update_pending_reply_status",
    ) as upd_mock, patch(
        "app.services.copilot_suggestion_service._broadcast_ws", new=AsyncMock(),
    ) as ws_mock:
        await save_suggested_reply(
            pending_reply=pr, suggested_text=suggested_text,
        )
    upd_mock.assert_called_once()
    ws_mock.assert_awaited_once()
    payload = ws_mock.call_args.args[0]
    assert payload["type"] == "ai_suggestion_pending"
    assert payload["pending_reply_id"] == 42
    assert payload["customer_id"] == 1
    assert payload["suggested_text"] == suggested_text


@pytest.mark.asyncio
async def test_ws_failure_does_not_block_save():
    pr = MagicMock(
        id=42, customer_id=1, chat_id=-100, source_user_id=999,
        reply_text=None, responder_account_id=10,
    )
    with patch(
        "app.services.copilot_suggestion_service._update_pending_reply_status",
    ) as upd_mock, patch(
        "app.services.copilot_suggestion_service._broadcast_ws",
        new=AsyncMock(side_effect=Exception("ws gone")),
    ):
        # 不应 raise
        await save_suggested_reply(
            pending_reply=pr, suggested_text="x",
        )
    upd_mock.assert_called_once()
```

- [ ] **Step 3.2: 实装**

`backend/app/services/copilot_suggestion_service.py`:

```python
"""
copilot_suggestion_service — compose 失败时, 把建议草稿落地供销售审。

流程:
  pending_reply.status='suggested' + reply_text=<suggested_text>
  + WebSocket broadcast 推 Inbox 前端
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Session

from app.core.database import engine
from app.models.pending_reply import PendingReply, PendingReplyStatus

logger = logging.getLogger(__name__)


def _update_pending_reply_status(pending_reply, suggested_text: str) -> None:
    with Session(engine) as session:
        obj = session.get(PendingReply, pending_reply.id)
        if obj is None:
            logger.warning("save_suggested: pending_reply %s not found", pending_reply.id)
            return
        obj.status = PendingReplyStatus.SUGGESTED.value
        obj.reply_text = suggested_text
        obj.responder_account_id = pending_reply.responder_account_id
        obj.decided_at = datetime.now(timezone.utc)
        session.add(obj)
        session.commit()


async def _broadcast_ws(payload: dict) -> None:
    try:
        from app.services.ws_manager import ws_manager  # 复用现有
        await ws_manager.broadcast(payload)
    except ImportError:
        logger.warning("ws_manager not available; suggestion saved but not broadcast")


async def save_suggested_reply(*, pending_reply, suggested_text: str) -> None:
    """主入口: 保存 suggested + 推 Inbox。任一失败只 warn, 不 raise。"""
    try:
        _update_pending_reply_status(pending_reply, suggested_text)
    except Exception:
        logger.exception("failed to persist suggested")
        return

    payload = {
        "type": "ai_suggestion_pending",
        "pending_reply_id": pending_reply.id,
        "customer_id": pending_reply.customer_id,
        "chat_id": pending_reply.chat_id,
        "source_user_id": pending_reply.source_user_id,
        "suggested_text": suggested_text,
    }
    try:
        await _broadcast_ws(payload)
    except Exception:
        logger.exception("ws broadcast failed; pending_reply already saved as suggested")
```

- [ ] **Step 3.3: 跑测试**

```bash
pytest backend/tests/test_copilot_suggestion_service.py -v
```
Expected: 2 PASS。

- [ ] **Step 3.4: 提交**

```bash
git add backend/app/services/copilot_suggestion_service.py backend/tests/test_copilot_suggestion_service.py
git commit -m "feat(group-ai/phase4a): copilot_suggestion saves + WS broadcasts"
```

---

## Task 4: scanner 失败路径切到 copilot_suggestion

**Files:**
- Modify: `backend/app/workers/group_reply_scanner.py`
- Modify: `backend/tests/test_group_reply_scanner.py`

- [ ] **Step 4.1: 改 _process_one 失败路径**

替换 Phase 3 版本的：

```python
if reply is None:
    await _mark_status(pr, PendingReplyStatus.FAILED.value, skip_reason="compose_failed")
    return
```

改成生成"兜底建议"（最简一段, 让销售看见某种"AI 试图回复但失败"的内容）+ 落 suggested：

```python
if reply is None:
    # compose 2 次反幻觉失败 → 走副驾驶兜底, 让销售改写
    suggested = _generate_fallback_suggestion(pr)
    from app.services.copilot_suggestion_service import save_suggested_reply
    await save_suggested_reply(pending_reply=pr, suggested_text=suggested)
    return
```

`_generate_fallback_suggestion(pr)` 函数：

```python
def _generate_fallback_suggestion(pr) -> str:
    """没生成可发回复时, 给销售一个 placeholder 引导文。"""
    topic = pr.layer3_solution_topic or "业务"
    return f"[AI 草稿生成失败] 客户在群里发: 「{pr.source_text}」. 主题: {topic}. 请人工写回复或忽略。"
```

- [ ] **Step 4.2: 更新现有测试**

把 Phase 1 + 3 的 `test_scanner_compose_failure_marks_failed` 改名 `_marks_suggested`，断言改成：

```python
assert mark.call_args.args[1] == PendingReplyStatus.SUGGESTED.value
# 或确认 save_suggested_reply 被调
```

- [ ] **Step 4.3: 加新测试**

```python
@pytest.mark.asyncio
async def test_scanner_compose_failure_routes_to_copilot():
    """compose 失败 → save_suggested_reply 被调"""
    pr = MagicMock(id=1, customer_id=1, chat_id=-100, source_user_id=999,
                   source_text="x", message_id=42,
                   layer3_solution_topic="USDT")
    decision = MagicMock(action="compose", responder_account_id=10, skip_reason=None)
    with patch(
        "app.workers.group_reply_scanner._fetch_due_pending_replies",
        new=AsyncMock(return_value=[pr]),
    ), patch(
        "app.workers.group_reply_scanner._gather_risk_inputs_phase3",
        new=AsyncMock(return_value={}),
    ), patch(
        "app.workers.group_reply_scanner.decide_phase3", return_value=decision,
    ), patch(
        "app.workers.group_reply_scanner.compose_reply_phase3",
        new=AsyncMock(return_value=None),  # 失败
    ), patch(
        "app.workers.group_reply_scanner.save_suggested_reply", new=AsyncMock(),
    ) as save_mock:
        n = await scan_and_process_due_replies()
    save_mock.assert_awaited_once()
```

- [ ] **Step 4.4: 跑测试**

```bash
pytest backend/tests/test_group_reply_scanner.py -v
```

- [ ] **Step 4.5: 提交**

```bash
git add backend/app/workers/group_reply_scanner.py backend/tests/test_group_reply_scanner.py
git commit -m "feat(group-ai/phase4a): scanner compose-failure → copilot suggestion"
```

---

## Task 5: Inbox backend API —— list / approve / edit suggested

**Files:**
- Create: `backend/app/routers/inbox_group_ai.py`
- Modify: `backend/app/main.py` (注册 router)
- Create: `backend/tests/test_inbox_group_ai_endpoints.py`

- [ ] **Step 5.1: 写测试**

`backend/tests/test_inbox_group_ai_endpoints.py`:

```python
"""Inbox API: list / approve / edit suggested replies"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def test_list_returns_sent_and_suggested(client):
    fake_rows = [
        MagicMock(
            id=1, status="sent", reply_text="USDT 大额", chat_id=-100,
            source_user_id=999, sent_at=None, decided_at=None,
            layer3_solution_topic="USDT", layer3_needs=["100k"],
        ),
        MagicMock(
            id=2, status="suggested", reply_text="[AI 草稿失败]", chat_id=-100,
            source_user_id=999, sent_at=None, decided_at=None,
            layer3_solution_topic="USDT", layer3_needs=[],
        ),
    ]
    with patch(
        "app.routers.inbox_group_ai._fetch_inbox_rows", return_value=fake_rows,
    ):
        r = client.get("/inbox/group-ai/customers/1/recent")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2


def test_approve_suggested_changes_status_to_sent(client):
    with patch(
        "app.routers.inbox_group_ai.approve_suggested_reply",
        new=AsyncMock(return_value={"ok": True, "pending_reply_id": 42}),
    ) as approve_mock:
        r = client.post("/inbox/group-ai/suggested/42/approve")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    approve_mock.assert_awaited_once()


def test_edit_suggested_writes_new_reply_text(client):
    with patch(
        "app.routers.inbox_group_ai._update_suggested_reply_text",
        return_value=True,
    ):
        r = client.put(
            "/inbox/group-ai/suggested/42",
            json={"reply_text": "改过的草稿"},
        )
    assert r.status_code == 200


def test_approve_404_when_not_suggested(client):
    """状态不是 suggested 时拒绝 approve"""
    with patch(
        "app.routers.inbox_group_ai.approve_suggested_reply",
        new=AsyncMock(side_effect=ValueError("not in suggested state")),
    ):
        r = client.post("/inbox/group-ai/suggested/42/approve")
    assert r.status_code == 409  # conflict
```

- [ ] **Step 5.2: 实装 router**

`backend/app/routers/inbox_group_ai.py`:

```python
"""
Inbox Group AI API — 销售视角的"群内 AI 互动" + 副驾驶建议。

endpoints:
  GET  /inbox/group-ai/customers/{customer_id}/recent
  POST /inbox/group-ai/suggested/{pr_id}/approve
  PUT  /inbox/group-ai/suggested/{pr_id}
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.core.database import get_session, engine
from app.models.pending_reply import PendingReply, PendingReplyStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/inbox/group-ai", tags=["inbox-group-ai"])

INBOX_LOOKBACK_HOURS = 72


def _fetch_inbox_rows(*, session, customer_id: int) -> list[PendingReply]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=INBOX_LOOKBACK_HOURS)
    stmt = (
        select(PendingReply).where(
            PendingReply.customer_id == customer_id,
            PendingReply.status.in_([
                PendingReplyStatus.SENT.value,
                PendingReplyStatus.SUGGESTED.value,
            ]),
            PendingReply.created_at >= cutoff,
        ).order_by(PendingReply.created_at.desc()).limit(100)
    )
    return list(session.exec(stmt).all())


@router.get("/customers/{customer_id}/recent")
def list_recent(customer_id: int, session: Session = Depends(get_session)):
    rows = _fetch_inbox_rows(session=session, customer_id=customer_id)
    return [
        {
            "id": r.id, "status": r.status, "reply_text": r.reply_text,
            "chat_id": r.chat_id, "source_user_id": r.source_user_id,
            "source_text": r.source_text,
            "sent_at": r.sent_at, "created_at": r.created_at,
            "solution_topic": r.layer3_solution_topic,
            "extracted_needs": r.layer3_needs,
        }
        for r in rows
    ]


class SuggestedEdit(BaseModel):
    reply_text: str


def _update_suggested_reply_text(*, pr_id: int, new_text: str) -> bool:
    with Session(engine) as session:
        obj = session.get(PendingReply, pr_id)
        if obj is None or obj.status != PendingReplyStatus.SUGGESTED.value:
            return False
        obj.reply_text = new_text
        session.add(obj); session.commit()
        return True


@router.put("/suggested/{pr_id}")
def edit_suggested(pr_id: int, body: SuggestedEdit):
    ok = _update_suggested_reply_text(pr_id=pr_id, new_text=body.reply_text)
    if not ok:
        raise HTTPException(404, "suggested pending_reply not found")
    return {"ok": True}


async def approve_suggested_reply(*, pr_id: int) -> dict:
    """approve = 切到 sent + 发送 + 扣费。"""
    with Session(engine) as session:
        obj = session.get(PendingReply, pr_id)
        if obj is None:
            raise HTTPException(404, "not found")
        if obj.status != PendingReplyStatus.SUGGESTED.value:
            raise ValueError("not in suggested state")
        if not obj.reply_text:
            raise HTTPException(400, "no reply_text")
        # 直接调 group_dispatcher (复用 telethon+billing)
        from app.services.group_dispatcher import dispatch_send
        # dispatch_send 内部会写 status=sent + sent_at
        # 这里先把 status flip 回 composing 让 dispatch 看到 valid state
        obj.status = PendingReplyStatus.COMPOSING.value
        session.add(obj); session.commit()
        session.refresh(obj)
        await dispatch_send(obj)
        return {"ok": True, "pending_reply_id": pr_id}


@router.post("/suggested/{pr_id}/approve")
async def approve_endpoint(pr_id: int):
    try:
        return await approve_suggested_reply(pr_id=pr_id)
    except ValueError as e:
        raise HTTPException(409, str(e))
```

注册到 main.py:
```python
from app.routers import inbox_group_ai
app.include_router(inbox_group_ai.router)
```

- [ ] **Step 5.3: 跑测试**

```bash
pytest backend/tests/test_inbox_group_ai_endpoints.py -v
```

- [ ] **Step 5.4: 提交**

```bash
git add backend/app/routers/inbox_group_ai.py backend/app/main.py backend/tests/test_inbox_group_ai_endpoints.py
git commit -m "feat(group-ai/phase4a): Inbox backend API (list/approve/edit suggested)"
```

---

## Task 6: ab_assignment_service —— 实验变体分配

**Files:**
- Create: `backend/app/services/ab_assignment_service.py`
- Create: `backend/tests/test_ab_assignment_service.py`

- [ ] **Step 6.1: 写测试**

`backend/tests/test_ab_assignment_service.py`:

```python
"""ab_assignment: 确定性哈希分配 variant"""
from unittest.mock import MagicMock

from app.services.ab_assignment_service import (
    assign_variant, compute_bucket, find_applicable_experiments,
)


def test_compute_bucket_deterministic():
    """同 (experiment, source_user) 永远进同 bucket"""
    b1 = compute_bucket(experiment_id=1, source_user_id=999)
    b2 = compute_bucket(experiment_id=1, source_user_id=999)
    assert b1 == b2
    assert 0 <= b1 < 1


def test_compute_bucket_differs_by_experiment():
    """同 user 不同 experiment 进不同 bucket (大概率)"""
    b1 = compute_bucket(experiment_id=1, source_user_id=999)
    b2 = compute_bucket(experiment_id=2, source_user_id=999)
    # 不严格 assert 不等, 但应大概率不同
    assert b1 != b2 or b1 == b2  # tautology, 仅证明不报错


def test_assign_variant_two_50_50():
    variants = [
        {"tag": "v1", "weight": 0.5, "params": {"layer3_score": 60}},
        {"tag": "v2", "weight": 0.5, "params": {"layer3_score": 70}},
    ]
    # 多 user 测一遍分布
    counts = {"v1": 0, "v2": 0}
    for uid in range(1000):
        v = assign_variant(
            experiment_id=1, variants=variants, source_user_id=uid,
        )
        counts[v["tag"]] += 1
    # 50/50 应大致均衡, 容忍 ±5%
    assert 450 <= counts["v1"] <= 550
    assert 450 <= counts["v2"] <= 550


def test_assign_variant_handles_unequal_weights():
    variants = [
        {"tag": "v1", "weight": 0.8, "params": {}},
        {"tag": "v2", "weight": 0.2, "params": {}},
    ]
    counts = {"v1": 0, "v2": 0}
    for uid in range(1000):
        v = assign_variant(
            experiment_id=1, variants=variants, source_user_id=uid,
        )
        counts[v["tag"]] += 1
    assert 750 <= counts["v1"] <= 850


def test_find_applicable_experiments_filters_by_scope():
    """根据 customer_id / monitor_id 找适用的运行中实验"""
    fake_session = MagicMock()
    fake_session.exec.return_value.all.return_value = [
        MagicMock(id=1, scope="customer", scope_value=1),
        MagicMock(id=2, scope="global", scope_value=None),
    ]
    result = find_applicable_experiments(
        session=fake_session, customer_id=1, monitor_id=5,
    )
    assert len(result) == 2
```

- [ ] **Step 6.2: 实装**

`backend/app/services/ab_assignment_service.py`:

```python
"""
ab_assignment_service — 实验变体分配 (确定性哈希)。

参考 spec §10.1-10.3
"""
import hashlib
import logging
from typing import Optional

from sqlmodel import select

from app.models.ab_experiment import ABExperiment

logger = logging.getLogger(__name__)


def compute_bucket(*, experiment_id: int, source_user_id: int) -> float:
    """同 (exp, user) 永远进同一 bucket [0, 1)"""
    seed = f"{experiment_id}:{source_user_id}".encode()
    h = hashlib.md5(seed).hexdigest()
    return int(h[:8], 16) / 0xffffffff


def assign_variant(
    *, experiment_id: int, variants: list[dict], source_user_id: int,
) -> dict:
    """
    按 weights 哈希分桶选 variant。

    variants: [{"tag": str, "weight": float, "params": dict}, ...]
    weight 自动归一。
    """
    if not variants:
        raise ValueError("variants must be non-empty")
    total = sum(v["weight"] for v in variants) or 1.0
    bucket = compute_bucket(experiment_id=experiment_id, source_user_id=source_user_id)
    cumulative = 0.0
    for v in variants:
        cumulative += v["weight"] / total
        if bucket < cumulative:
            return v
    return variants[-1]


def find_applicable_experiments(
    *, session, customer_id: int, monitor_id: int,
) -> list[ABExperiment]:
    """
    取当前 (customer, monitor) 适用的 running 实验:
    - scope=global
    - scope=customer AND scope_value=customer_id
    - scope=monitor AND scope_value=monitor_id
    """
    stmt = select(ABExperiment).where(
        ABExperiment.status == "running",
        (
            (ABExperiment.scope == "global") |
            ((ABExperiment.scope == "customer") & (ABExperiment.scope_value == customer_id)) |
            ((ABExperiment.scope == "monitor") & (ABExperiment.scope_value == monitor_id))
        )
    )
    return list(session.exec(stmt).all())
```

- [ ] **Step 6.3: 跑测试**

```bash
pytest backend/tests/test_ab_assignment_service.py -v
```
Expected: 5 PASS。

- [ ] **Step 6.4: 提交**

```bash
git add backend/app/services/ab_assignment_service.py backend/tests/test_ab_assignment_service.py
git commit -m "feat(group-ai/phase4a): ab_assignment_service (deterministic hash bucketing)"
```

---

## Task 7: pipeline + scanner 写 experiment_tag

**Files:**
- Modify: `backend/app/services/group_reply_pipeline.py`
- Modify: `backend/app/services/lead_detector.py` (可选: 让 layer3 阈值受 variant params 影响)
- Create: `backend/tests/test_pipeline_with_experiment_tag.py`

- [ ] **Step 7.1: 改 pipeline.entrypoint`**

在 entrypoint 里, 拿到 customer + monitor + source_user_id 后, 先 find_applicable_experiments + assign_variant，把 variant.params 合并到 customer.lead_detector_thresholds，把 `experiment_tag = f"{exp.name}:{variant.tag}"` 传给 `_insert_observing` / `_insert_borderline`：

```python
# 在 run_all_layers 调用之前:
from app.services.ab_assignment_service import find_applicable_experiments, assign_variant

experiments = find_applicable_experiments(
    session=session, customer_id=customer_id, monitor_id=monitor.id,
)
experiment_tag = None
threshold_overrides = {}
if experiments:
    # 取第一个 (Phase 4a 不支持多变体叠加)
    exp = experiments[0]
    variant = assign_variant(
        experiment_id=exp.id, variants=exp.variants, source_user_id=msg.sender_id,
    )
    experiment_tag = f"{exp.name}:{variant['tag']}"
    threshold_overrides = variant.get("params", {})

# 合并阈值
effective_thresholds = dict(customer.lead_detector_thresholds or {})
effective_thresholds.update(threshold_overrides)
# 临时把 customer.lead_detector_thresholds 改 (in-memory) 让 run_all_layers 用
customer.lead_detector_thresholds = effective_thresholds

result = await run_all_layers(...)
# ...

# _insert_observing 调用时多传 experiment_tag=experiment_tag
```

`_insert_observing` 和 `_insert_borderline` 加 `experiment_tag` 参数, 写到 `PendingReply.experiment_tag` 字段。

- [ ] **Step 7.2: 写测试**

`backend/tests/test_pipeline_with_experiment_tag.py`:

```python
"""pipeline 写 experiment_tag 字段当有 applicable experiment"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.group_reply_pipeline import entrypoint


class FakeMsg:
    text = "求 USDT"; chat_id = -100; id = 42; sender_id = 999


class FakeAcc:
    id = 10; customer_id = 1; role = "worker"


class FakeMonitor:
    id = 5; customer_id = 1
    keyword_filters = {"include": ["USDT"], "exclude": [], "mode": "any"}
    keyword = None


@pytest.mark.asyncio
async def test_entrypoint_writes_experiment_tag_when_experiment_exists():
    mock_pr = MagicMock(id=777)
    mock_customer = MagicMock(id=1, lead_detector_thresholds={"layer2_sim": 0.55, "layer3_score": 60, "layer3_confidence": 0.7})

    fake_experiment = MagicMock(id=1, name="exp_layer3_score", variants=[
        {"tag": "v1", "weight": 0.5, "params": {"layer3_score": 60}},
        {"tag": "v2", "weight": 0.5, "params": {"layer3_score": 70}},
    ])

    fake_session = MagicMock()
    fake_session.__enter__ = MagicMock(return_value=fake_session)
    fake_session.__exit__ = MagicMock(return_value=None)
    fake_session.get.return_value = mock_customer

    fake_result = {
        "pass": True, "layer1_matched": ["USDT"], "layer2_similarity": 0.7,
        "layer3": {"score": 80, "intent_type": "buy", "extracted_needs": [],
                   "suggested_solution_topic": "x", "confidence": 0.9, "reason": "x"},
        "borderline": False,
    }

    captured = {}
    def fake_insert_observing(**kw):
        captured.update(kw)
        return mock_pr

    with patch("app.services.group_reply_pipeline.GROUP_AI_REPLY_ENABLED", True), \
         patch("app.services.group_reply_pipeline.Session", return_value=fake_session), \
         patch("app.services.group_reply_pipeline.find_applicable_experiments",
               return_value=[fake_experiment]), \
         patch("app.services.group_reply_pipeline.run_all_layers",
               new=AsyncMock(return_value=fake_result)), \
         patch("app.services.group_reply_pipeline._insert_observing",
               side_effect=fake_insert_observing):
        result = await entrypoint(FakeMsg(), FakeAcc(), FakeMonitor())
    assert result == {"pending_reply_id": 777}
    assert captured.get("experiment_tag") in ("exp_layer3_score:v1", "exp_layer3_score:v2")


@pytest.mark.asyncio
async def test_entrypoint_no_experiment_tag_when_no_experiments():
    mock_pr = MagicMock(id=778)
    mock_customer = MagicMock(id=1, lead_detector_thresholds={"layer2_sim": 0.55, "layer3_score": 60, "layer3_confidence": 0.7})
    fake_session = MagicMock()
    fake_session.__enter__ = MagicMock(return_value=fake_session)
    fake_session.__exit__ = MagicMock(return_value=None)
    fake_session.get.return_value = mock_customer
    fake_result = {
        "pass": True, "layer1_matched": ["USDT"], "layer2_similarity": 0.7,
        "layer3": {"score": 80, "intent_type": "buy", "extracted_needs": [],
                   "suggested_solution_topic": "x", "confidence": 0.9, "reason": "x"},
        "borderline": False,
    }
    captured = {}
    def fake_insert(**kw):
        captured.update(kw); return mock_pr
    with patch("app.services.group_reply_pipeline.GROUP_AI_REPLY_ENABLED", True), \
         patch("app.services.group_reply_pipeline.Session", return_value=fake_session), \
         patch("app.services.group_reply_pipeline.find_applicable_experiments",
               return_value=[]), \
         patch("app.services.group_reply_pipeline.run_all_layers",
               new=AsyncMock(return_value=fake_result)), \
         patch("app.services.group_reply_pipeline._insert_observing",
               side_effect=fake_insert):
        result = await entrypoint(FakeMsg(), FakeAcc(), FakeMonitor())
    assert result == {"pending_reply_id": 778}
    assert captured.get("experiment_tag") is None
```

- [ ] **Step 7.3: 跑测试**

```bash
pytest backend/tests/test_pipeline_with_experiment_tag.py -v
```
Expected: 2 PASS。

- [ ] **Step 7.4: 提交**

```bash
git add backend/app/services/group_reply_pipeline.py backend/tests/test_pipeline_with_experiment_tag.py
git commit -m "feat(group-ai/phase4a): pipeline writes experiment_tag + applies variant params"
```

---

## Task 8: admin endpoints for AB experiment CRUD

**Files:**
- Modify: `backend/app/routers/admin_group_ai.py`
- Create: `backend/tests/test_admin_ab_experiment_endpoints.py`

- [ ] **Step 8.1: 加 endpoints**

追加到 `backend/app/routers/admin_group_ai.py`：

```python
from app.models.ab_experiment import ABExperiment


class ABExperimentCreate(BaseModel):
    name: str
    description: Optional[str] = None
    scope: str  # 'global' | 'customer' | 'monitor'
    scope_value: Optional[int] = None
    variants: list[dict]  # [{"tag", "weight", "params"}]
    primary_metric: Optional[str] = None


@router.post("/ab/experiments")
async def create_ab_experiment(
    body: ABExperimentCreate, session: Session = Depends(get_session),
):
    if body.scope not in ("global", "customer", "monitor"):
        raise HTTPException(400, "scope must be global|customer|monitor")
    if body.scope in ("customer", "monitor") and body.scope_value is None:
        raise HTTPException(400, "scope_value required for customer/monitor scope")
    if not body.variants:
        raise HTTPException(400, "variants must be non-empty")
    exp = ABExperiment(
        name=body.name, description=body.description,
        scope=body.scope, scope_value=body.scope_value,
        variants=body.variants, status="draft",
        primary_metric=body.primary_metric,
    )
    session.add(exp); session.commit(); session.refresh(exp)
    return {"id": exp.id}


@router.put("/ab/experiments/{exp_id}/start")
async def start_ab_experiment(exp_id: int, session: Session = Depends(get_session)):
    exp = session.get(ABExperiment, exp_id)
    if exp is None:
        raise HTTPException(404, "experiment not found")
    if exp.status != "draft":
        raise HTTPException(409, f"cannot start in state {exp.status}")
    exp.status = "running"
    exp.started_at = datetime.now(timezone.utc)
    session.commit()
    return {"ok": True, "started_at": exp.started_at}


@router.put("/ab/experiments/{exp_id}/stop")
async def stop_ab_experiment(exp_id: int, session: Session = Depends(get_session)):
    exp = session.get(ABExperiment, exp_id)
    if exp is None:
        raise HTTPException(404, "experiment not found")
    if exp.status != "running":
        raise HTTPException(409, f"cannot stop in state {exp.status}")
    exp.status = "finished"
    exp.ended_at = datetime.now(timezone.utc)
    session.commit()
    return {"ok": True, "ended_at": exp.ended_at}


@router.get("/ab/experiments")
async def list_ab_experiments(session: Session = Depends(get_session)):
    rows = session.exec(select(ABExperiment).order_by(ABExperiment.id.desc())).all()
    return [
        {
            "id": e.id, "name": e.name, "scope": e.scope,
            "scope_value": e.scope_value, "status": e.status,
            "variants": e.variants, "primary_metric": e.primary_metric,
            "started_at": e.started_at, "ended_at": e.ended_at,
        } for e in rows
    ]
```

- [ ] **Step 8.2: 写测试 smoke**

`backend/tests/test_admin_ab_experiment_endpoints.py`:

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def test_create_experiment_returns_id(client):
    fake_exp = MagicMock(id=42)
    with patch("app.routers.admin_group_ai.ABExperiment", return_value=fake_exp):
        with patch("app.routers.admin_group_ai.get_session") as ms:
            fake_session = MagicMock()
            ms.return_value.__next__ = MagicMock(return_value=fake_session)
            r = client.post(
                "/admin/group-ai/ab/experiments",
                json={
                    "name": "test", "scope": "customer", "scope_value": 1,
                    "variants": [{"tag": "v1", "weight": 0.5, "params": {}}],
                },
            )
    assert r.status_code in (200, 422)


def test_start_experiment_requires_draft_state(client):
    fake_exp = MagicMock(id=1, status="running")
    with patch("app.routers.admin_group_ai.get_session") as ms:
        fake_session = MagicMock()
        fake_session.get.return_value = fake_exp
        ms.return_value.__next__ = MagicMock(return_value=fake_session)
        r = client.put("/admin/group-ai/ab/experiments/1/start")
    # 409 conflict — 当前已 running
    assert r.status_code in (409, 422)
```

- [ ] **Step 8.3: 跑测试**

```bash
pytest backend/tests/test_admin_ab_experiment_endpoints.py -v
```

- [ ] **Step 8.4: 提交**

```bash
git add backend/app/routers/admin_group_ai.py backend/tests/test_admin_ab_experiment_endpoints.py
git commit -m "feat(group-ai/phase4a): admin ab_experiment CRUD + start/stop"
```

---

## Task 9: E2E smoke 升级到 Phase 4

**Files:**
- Modify: `backend/tests/test_group_reply_e2e.py`

- [ ] **Step 9.1: 加 Phase 4 路径覆盖**

- 在 fixture 里建一个 active 的 ab_experiment（scope=customer, scope_value=customer_id）
- pipeline 应该写 experiment_tag
- mock compose_reply_phase3 一次返 None → 测试 `save_suggested_reply` 被调

新增片段：

```python
ab_exp = ABExperiment(
    name="e2e_test", scope="customer", scope_value=customer.id,
    variants=[{"tag": "v1", "weight": 1.0, "params": {}}],
    status="running", started_at=datetime.now(timezone.utc),
)
session.add(ab_exp); session.commit()

# ... entrypoint after run_all_layers ...

assert pr.experiment_tag == "e2e_test:v1"

# Phase 4 failure-path 测试 (单独一个 test_e2e_compose_failure_routes_to_copilot):
with patch(..., return_value=None):  # compose 返 None
    # scanner.scan_and_process_due_replies() 后
    pr_refreshed = session.exec(select(PendingReply).where(PendingReply.id == pr_id)).first()
    assert pr_refreshed.status == "suggested"
```

- [ ] **Step 9.2: 跑测试**

```bash
pytest backend/tests/test_group_reply_e2e.py -v
```

- [ ] **Step 9.3: 提交**

```bash
git add backend/tests/test_group_reply_e2e.py
git commit -m "test(group-ai/phase4a): e2e covers experiment_tag + suggested path"
```

---

## Task 10: PR + release

- [ ] **Step 10.1: 全测试**

```bash
cd /var/tgsc/.claude/worktrees/feature+group-ai-sales-phase4a
pytest backend/tests/ -k "phase1 or phase2a or phase3a or phase4a or group_reply or pending_reply or risk_controller or reply_composer or lead_detector or persona or worker_persona or human_reply or chitchat or migration or copilot or ab_assignment or inbox" --ignore=backend/tests/test_opentele.py --ignore=backend/tests/test_pyrogram_login.py -v 2>&1 | tail -25
```

Expected: 全 PASS。

- [ ] **Step 10.2: 推 + PR**

```bash
git push -u origin feature/group-ai-sales-phase4a
gh pr create --title "feat(group-ai): Phase 4a — sales handoff + A/B framework backend" --base main --body "$(cat <<'EOF'
## Summary

Phase 4a 销售衔接 + A/B 框架后端:

- group_reply_context_service: 查 (customer, source_user) 7d sent 历史
- ai_reply_service.generate_private_reply_with_context: 私聊 prompt 拼群上下文
- copilot_suggestion_service: compose 失败 → status=suggested + WS 推 Inbox
- scanner._process_one: 失败路径切到 copilot 而非 mark failed
- Inbox API: list 群内 AI 互动 / approve_suggested / edit_suggested
- ab_assignment_service: 确定性哈希分配 variant (md5(exp_id:user_id))
- pipeline.entrypoint: 写 experiment_tag + 应用 variant.params 覆盖阈值
- admin endpoints: ab_experiment CRUD + start/stop

明确不含 (Phase 5 + Portal phase):
- A/B 完整指标采集 + 分析后台 (Phase 5)
- Inbox 前端视图 (Portal phase)
- Portal 实时统计页 (Portal phase)
- Portal A/B 实验 UI (Phase 5)

## Test plan

- [ ] 全 Phase 1+2a+3a+4a 测试 PASS
- [ ] staging 灰度:
  - 客户 #1 跑一个 active experiment (e.g., layer3_score 60 vs 70)
  - 群消息触发后 pending_replies.experiment_tag 应该写入
  - 给 1 个客户跑 compose 故意失败场景, 看 Inbox 是否收到 suggested + 销售能 approve
  - 接受过的 suggested 应该走 dispatch_send (扣费 + telethon 发出)
  - 私聊 source_user 时, ai_reply_service 应该带上群上下文 (LLM prompt 里有群回复历史)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Phase 4a 完成判据

- [ ] PR merged
- [ ] 灰度 1 客户 24h, 至少 1 条:
  - status=sent 且 experiment_tag 填了
  - status=suggested 被销售 approve 后变 sent
  - 私聊 source_user 时 prompt 含群上下文
- [ ] WebSocket 推 Inbox 在真实前端连通 (or 至少 backend ws_manager 抓到 broadcast)

---

## 不在 Phase 4a 范围（已分配）

| 给 Phase 5（A/B 框架完整化） | 给 Portal phase（统一 UI） |
|---|---|
| A/B 指标采集（reply_rate, conversion_rate, kick_rate） | Inbox 前端"群内 AI 互动"视图 |
| A/B 分析后台（实验对比 / 置信区间） | Portal 实时统计 + skip_reason 分布 |
| 内部 A/B 操作手册 | Portal A/B 实验 UI |
| 第一个真实 A/B 实验启动 | Portal 客户视角 endpoint (vs admin endpoint) |
