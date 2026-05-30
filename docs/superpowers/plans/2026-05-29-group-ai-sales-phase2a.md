# 群内 AI 销售员 Phase 2a 实施计划（智能识别 + 案例库后端）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 LeadDetector 从只用 Layer 1 关键词升级到 Layer 1+2+3 三层过滤，让 ReplyComposer 能引用真实成交案例 + 数字一致性反幻觉。识别精度从"关键词"升级到"AI 理解客户需求 + ICP 画像匹配"，回复从"KB 套话"升级到"真实案例 + 具体数字"。

**Architecture:** Phase 2a 只动后端 + Alembic 不动（Phase 1 已经把 case_studies / customer.icp_* / lead_detector_thresholds 字段都建好了）。新增：embedding 服务薄包装、`icp_embedding_match.py` Layer 2、`llm.score_lead_message` Layer 3、`case_study_service.py`（CRUD + 自动抽取）、`reply_composer` Step B（案例匹配）+ Step D 升级（数字一致性反幻觉）。Customer/CaseStudy 的客户端配置走 admin API + admin SQL（portal UI 由 Phase 2b 接）。

**Tech Stack:** FastAPI · SQLModel · pgvector · Vertex Gemini Embedding `gemini-embedding-001` (768d) · Vertex Gemini Flash · 复用 Phase 1 `reply_composer` / `lead_detector` / `pipeline.entrypoint` 骨架

**Spec:** [docs/superpowers/specs/2026-05-28-group-ai-sales-presence-design.md](../specs/2026-05-28-group-ai-sales-presence-design.md) §3.2 / §3.3 / §6.1-6.4

**前置条件：**
- Phase 1 PR #9 必须已 merge 到 main（迁移 `41f948211e5f` 已应用 → 表 `case_studies` 和 `customer.icp_*` 字段存在）
- `industry_kb_service._embed_text(session, text)` 可用（复用做 embedding）
- `LLMService.generate` 可用（生成 JSON 输出）
- Phase 1 灰度运行至少 24h，回流以下信号供本期调阈值：
  - 关键词命中率 / 误报样本（看 layer1_matched JSONB 内容）
  - 反幻觉失败率（status='failed' 比例）
  - 计数偏差（pending_replies 总量 vs sent 比例）
- Worktree 在 `/var/tgsc/.claude/worktrees/feature+group-ai-sales-phase2a`（新 worktree，与 Phase 1 不同）；或在 PR #9 merge 后从 main 拉新分支

**Phase 2a 范围（明确包含 / 不含）：**

| 包含 | 不含（留给 Phase 2b / 后续） |
|---|---|
| 复用 `_embed_text` 做 ICP 和案例 embedding | Portal "ICP 编辑器" / "案例库" 前端页（Phase 2b） |
| Layer 2 ICP embedding 相似度匹配 | Portal 阈值滑块 UI（Phase 2b） |
| Layer 3 `LLMService.score_lead_message` 新方法 | Portal "扫描历史" 按钮（Phase 2b） |
| Lead detector 三层串联（早返 + borderline） | Real-time 统计页（Phase 2b） |
| CaseStudy CRUD admin endpoint（admin 操作） | 客户视角的 CRUD endpoint（Phase 2b） |
| Reply composer 接入 case_studies | persona_rewriter 实装（Phase 3） |
| 数字一致性反幻觉 filter | worker_persona 实际读取（Phase 3） |
| 案例库自动抽取脚本 + admin 触发 endpoint | ChitchatScheduler（Phase 3） |
| 灰度 thresholds 自动写入 / 调整 admin endpoint | 真人接话检测（Phase 3） |

---

## File Structure

**新建文件：**
- `backend/app/services/embedding_service.py` —— 薄包装 `_embed_text`，统一供 ICP / case 双方调用
- `backend/app/services/icp_embedding_match.py` —— Layer 2 实现
- `backend/app/services/case_study_service.py` —— CaseStudy CRUD + auto-extract
- `backend/app/services/case_study_extractor.py` —— 从历史聊天 LLM 抽取案例的脚本
- `backend/app/routers/admin_group_ai.py` —— admin 端 endpoint（ICP / case / threshold 配置）
- `backend/tests/test_embedding_service.py`
- `backend/tests/test_icp_embedding_match.py`
- `backend/tests/test_llm_score_lead_message.py`
- `backend/tests/test_lead_detector_layers123.py`
- `backend/tests/test_case_study_service.py`
- `backend/tests/test_case_study_extractor.py`
- `backend/tests/test_reply_composer_phase2a.py`
- `backend/tests/test_admin_group_ai_endpoints.py`

**修改文件：**
- `backend/app/services/lead_detector.py` —— 加 Layer 2 / Layer 3 函数 + 三层 orchestrator
- `backend/app/services/llm.py` —— 加 `score_lead_message` 方法
- `backend/app/services/group_reply_pipeline.py` —— entrypoint 从只跑 Layer 1 → 跑全三层
- `backend/app/services/reply_composer.py` —— Step B（案例匹配）+ Step D 升级（数字一致性）
- `backend/app/workers/group_reply_scanner.py` —— `_process_one` 把 `layer3_solution_topic` 传给 composer 而非 `source_text` 兜底
- `backend/app/main.py` —— 注册 `admin_group_ai` router

每个 service 文件保持 < 300 行；admin router < 200 行。

---

## Task 1: embedding_service 薄包装

**Files:**
- Create: `backend/app/services/embedding_service.py`
- Create: `backend/tests/test_embedding_service.py`

- [ ] **Step 1.1: 写测试**

`backend/tests/test_embedding_service.py`:

```python
"""embedding_service: 薄包装 industry_kb_service._embed_text, 统一调用入口"""
from unittest.mock import patch, MagicMock

from app.services.embedding_service import embed_text


def test_embed_text_returns_768d_vector():
    """成功路径: 返回 768 维 float list"""
    fake_vec = [0.1] * 768
    with patch(
        "app.services.embedding_service._embed_text_raw",
        return_value=fake_vec,
    ):
        result = embed_text(session=MagicMock(), text="test ICP")
    assert isinstance(result, list)
    assert len(result) == 768


def test_embed_text_none_on_empty():
    """空文本不调 embedding, 直接 None"""
    result = embed_text(session=MagicMock(), text="")
    assert result is None
    result2 = embed_text(session=MagicMock(), text=None)
    assert result2 is None


def test_embed_text_none_on_underlying_failure():
    """底层服务挂 → None (调用方 fail-soft)"""
    with patch(
        "app.services.embedding_service._embed_text_raw",
        return_value=None,
    ):
        result = embed_text(session=MagicMock(), text="x")
    assert result is None
```

- [ ] **Step 1.2: 跑 → 应 ImportError**

```bash
cd /var/tgsc/.claude/worktrees/feature+group-ai-sales-phase2a
pwd
pytest backend/tests/test_embedding_service.py -v
```

- [ ] **Step 1.3: 实装 embedding_service**

`backend/app/services/embedding_service.py`:

```python
"""
embedding_service — 统一 768 维 embedding 入口。

薄包装 industry_kb_service._embed_text. ICP 画像 / case_studies / 群消息
Layer 2 匹配 都通过本模块调用, 方便未来切 Vertex/OpenAI/本地模型。

参考 spec §3.2 (Layer 2 ICP embedding)
"""
import logging
from typing import Optional

from app.services.industry_kb_service import _embed_text as _embed_text_raw

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 768


def embed_text(*, session, text: Optional[str], timeout: float = 15.0) -> Optional[list[float]]:
    """
    返回 768 维 float list, 失败/空文本返回 None。

    Args:
        session: SQLModel Session (industry_kb_service._embed_text 内部需要它读 ai_config)
        text: 待 embed 的文本
        timeout: 秒
    """
    if not text or not text.strip():
        return None
    try:
        return _embed_text_raw(session, text, timeout=timeout)
    except Exception:
        logger.exception("embed_text failed for text len=%d", len(text))
        return None
```

- [ ] **Step 1.4: 跑测试**

```bash
pytest backend/tests/test_embedding_service.py -v
```
Expected: 3 PASS。

- [ ] **Step 1.5: 提交**

```bash
pwd  # confirm worktree path
git add backend/app/services/embedding_service.py backend/tests/test_embedding_service.py
git commit -m "feat(group-ai/phase2a): embedding_service unified 768d entry point"
```

---

## Task 2: Customer ICP embedding auto-regenerate hook

**Files:**
- Modify: `backend/app/services/customer_service.py` 或 `customer.py` (找 customer.update 的实际入口)
- Create: `backend/tests/test_customer_icp_embedding.py`

- [ ] **Step 2.1: 找 customer 更新入口**

```bash
cd /var/tgsc/.claude/worktrees/feature+group-ai-sales-phase2a
grep -rnE "def (update_customer|patch_customer|customer\.icp_profile_text\s*=)" backend/app/ | head -10
ls backend/app/services/ | grep -i customer
ls backend/app/routers/ | grep -i customer
```

确定客户更新 ICP 文本的入口在哪个 service / router。可能没有专门的 service，是 admin router 直接改字段。

- [ ] **Step 2.2: 写测试**

`backend/tests/test_customer_icp_embedding.py`:

```python
"""Customer.icp_profile_text 变更后, 应自动更新 icp_profile_embedding"""
import os
import pytest
from unittest.mock import patch, MagicMock

from app.services.customer_icp_service import (
    set_customer_icp_text_and_embed,
)


def test_set_icp_text_calls_embedding():
    """正常路径: 设新 ICP → 调 embed → 写回 embedding 字段"""
    fake_session = MagicMock()
    fake_customer = MagicMock(id=1, icp_profile_text=None, icp_profile_embedding=None)
    fake_session.get.return_value = fake_customer
    fake_vec = [0.1] * 768
    with patch(
        "app.services.customer_icp_service.embed_text", return_value=fake_vec,
    ):
        ok = set_customer_icp_text_and_embed(
            session=fake_session, customer_id=1, new_text="我的理想客户"
        )
    assert ok is True
    assert fake_customer.icp_profile_text == "我的理想客户"
    assert fake_customer.icp_profile_embedding == fake_vec
    fake_session.commit.assert_called_once()


def test_set_icp_text_embedding_failure_keeps_text():
    """embedding 失败时, 仍写 text 但 embedding=None (Layer 2 会自动降级)"""
    fake_session = MagicMock()
    fake_customer = MagicMock(id=1)
    fake_session.get.return_value = fake_customer
    with patch(
        "app.services.customer_icp_service.embed_text", return_value=None,
    ):
        ok = set_customer_icp_text_and_embed(
            session=fake_session, customer_id=1, new_text="x"
        )
    assert ok is True  # 不算失败, embedding 后续可以重跑
    assert fake_customer.icp_profile_text == "x"
    assert fake_customer.icp_profile_embedding is None


def test_set_icp_text_empty_clears_both():
    """传空文本: 清空 text 和 embedding"""
    fake_session = MagicMock()
    fake_customer = MagicMock(id=1, icp_profile_text="old", icp_profile_embedding=[1.0]*768)
    fake_session.get.return_value = fake_customer
    ok = set_customer_icp_text_and_embed(
        session=fake_session, customer_id=1, new_text=""
    )
    assert ok is True
    assert fake_customer.icp_profile_text is None
    assert fake_customer.icp_profile_embedding is None


def test_set_icp_text_unknown_customer_returns_false():
    fake_session = MagicMock()
    fake_session.get.return_value = None
    ok = set_customer_icp_text_and_embed(
        session=fake_session, customer_id=999, new_text="x"
    )
    assert ok is False
```

- [ ] **Step 2.3: 跑 → ImportError**

- [ ] **Step 2.4: 实装 customer_icp_service.py**

`backend/app/services/customer_icp_service.py`:

```python
"""
customer_icp_service — 写客户 ICP 画像 + 自动 embedding。

调用方: admin endpoint POST /admin/group-ai/customers/{id}/icp。
触发条件: icp_profile_text 变更时。
"""
import logging
from typing import Optional

from app.models.customer import Customer
from app.services.embedding_service import embed_text

logger = logging.getLogger(__name__)


def set_customer_icp_text_and_embed(
    *, session, customer_id: int, new_text: Optional[str],
) -> bool:
    """
    更新 customer.icp_profile_text + 同步 embedding。

    Args:
        session: SQLModel Session
        customer_id: 客户 ID
        new_text: 新的 ICP 文本, None/空 表示清空

    Returns:
        True 客户存在并已更新; False 客户不存在
    """
    customer = session.get(Customer, customer_id)
    if customer is None:
        logger.warning("set_customer_icp_text: customer %d not found", customer_id)
        return False

    cleaned = (new_text or "").strip()
    if not cleaned:
        customer.icp_profile_text = None
        customer.icp_profile_embedding = None
    else:
        customer.icp_profile_text = cleaned
        vec = embed_text(session=session, text=cleaned)
        # 失败时 embedding 留 None, Layer 2 会自动降级跳过
        customer.icp_profile_embedding = vec
        if vec is None:
            logger.warning(
                "set_customer_icp_text: embedding generation failed for customer %d, "
                "text saved but Layer 2 disabled until manual re-embed",
                customer_id,
            )

    session.add(customer)
    session.commit()
    return True
```

- [ ] **Step 2.5: 跑测试**

```bash
pytest backend/tests/test_customer_icp_embedding.py -v
```
Expected: 4 PASS。

- [ ] **Step 2.6: 提交**

```bash
git add backend/app/services/customer_icp_service.py backend/tests/test_customer_icp_embedding.py
git commit -m "feat(group-ai/phase2a): customer ICP text + auto-embedding service"
```

---

## Task 3: Layer 2 ICP embedding match

**Files:**
- Create: `backend/app/services/icp_embedding_match.py`
- Modify: `backend/app/services/lead_detector.py` (加 layer2 函数)
- Create: `backend/tests/test_icp_embedding_match.py`

- [ ] **Step 3.1: 写测试**

`backend/tests/test_icp_embedding_match.py`:

```python
"""Layer 2: ICP embedding cosine 相似度匹配"""
from unittest.mock import patch, MagicMock

from app.services.lead_detector import layer2_icp_similarity


def test_layer2_passes_when_above_threshold():
    """模拟相似度 0.6 > 阈值 0.55 → PASS"""
    icp_vec = [1.0, 0.0, 0.0] + [0.0] * 765
    msg_vec = [0.9, 0.1, 0.0] + [0.0] * 765
    fake_session = MagicMock()
    with patch(
        "app.services.lead_detector.embed_text", return_value=msg_vec,
    ):
        result = layer2_icp_similarity(
            session=fake_session, text="求 USDT", icp_embedding=icp_vec,
            threshold=0.55,
        )
    assert result["pass"] is True
    assert result["similarity"] > 0.55


def test_layer2_blocks_below_threshold():
    """相似度 0.3 < 0.55 → block"""
    icp_vec = [1.0, 0.0] + [0.0] * 766
    msg_vec = [0.3, 0.95] + [0.0] * 766
    fake_session = MagicMock()
    with patch(
        "app.services.lead_detector.embed_text", return_value=msg_vec,
    ):
        result = layer2_icp_similarity(
            session=fake_session, text="今天天气", icp_embedding=icp_vec,
            threshold=0.55,
        )
    assert result["pass"] is False
    assert result["similarity"] < 0.55


def test_layer2_degrades_when_icp_embedding_missing():
    """customer.icp_profile_embedding=None → degrade pass (Layer 2 跳过)"""
    fake_session = MagicMock()
    result = layer2_icp_similarity(
        session=fake_session, text="任何", icp_embedding=None, threshold=0.55,
    )
    assert result["pass"] is True
    assert result["similarity"] is None
    assert result.get("degraded") is True


def test_layer2_degrades_when_message_embed_fails():
    """消息 embedding 服务挂 → degrade pass (不阻塞管线)"""
    icp_vec = [1.0] * 768
    fake_session = MagicMock()
    with patch(
        "app.services.lead_detector.embed_text", return_value=None,
    ):
        result = layer2_icp_similarity(
            session=fake_session, text="x", icp_embedding=icp_vec, threshold=0.55,
        )
    assert result["pass"] is True
    assert result["similarity"] is None
    assert result.get("degraded") is True


def test_layer2_borderline_flag():
    """边界值 (threshold-0.05 .. threshold) → pass=False 但 borderline=True"""
    icp_vec = [1.0, 0.0] + [0.0] * 766
    # 构造相似度 ≈ 0.52 (落在 [0.50, 0.55) 区间)
    import math
    angle = math.acos(0.52)
    msg_vec = [math.cos(angle), math.sin(angle)] + [0.0] * 766
    fake_session = MagicMock()
    with patch(
        "app.services.lead_detector.embed_text", return_value=msg_vec,
    ):
        result = layer2_icp_similarity(
            session=fake_session, text="x", icp_embedding=icp_vec, threshold=0.55,
        )
    assert result["pass"] is False
    assert result.get("borderline") is True
    assert 0.50 <= result["similarity"] < 0.55
```

- [ ] **Step 3.2: 跑 → ImportError**

- [ ] **Step 3.3: 实装 cosine + layer2 函数**

加到 `backend/app/services/lead_detector.py` 末尾（不创建新文件，与 Layer 1 同居）：

```python
import math
from typing import Optional
from app.services.embedding_service import embed_text  # 顶部 import

# ...existing layer1_keyword_match...


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """计算两个向量的余弦相似度. 0 向量返回 0.0。"""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


BORDERLINE_BAND = 0.05  # 阈值下 0.05 内算 borderline


def layer2_icp_similarity(
    *, session, text: str, icp_embedding: Optional[list[float]], threshold: float,
) -> dict:
    """
    Layer 2: 消息 vs 客户 ICP embedding 余弦相似度。

    Returns:
        {"pass": bool, "similarity": float | None,
         "degraded": bool, "borderline": bool}

    pass=True 三种情况:
      - 相似度 >= threshold (正常通过)
      - icp_embedding=None (客户没设画像, 降级跳过该层)
      - 消息 embedding 生成失败 (服务挂, 不阻塞管线)
    """
    if icp_embedding is None:
        return {"pass": True, "similarity": None, "degraded": True, "borderline": False}

    msg_vec = embed_text(session=session, text=text)
    if msg_vec is None:
        return {"pass": True, "similarity": None, "degraded": True, "borderline": False}

    sim = _cosine_similarity(msg_vec, icp_embedding)
    passed = sim >= threshold
    borderline = (not passed) and (sim >= threshold - BORDERLINE_BAND)
    return {
        "pass": passed, "similarity": sim,
        "degraded": False, "borderline": borderline,
    }
```

- [ ] **Step 3.4: 跑测试**

```bash
pytest backend/tests/test_icp_embedding_match.py -v
```
Expected: 5 PASS。

- [ ] **Step 3.5: 提交**

```bash
git add backend/app/services/lead_detector.py backend/tests/test_icp_embedding_match.py
git commit -m "feat(group-ai/phase2a): Layer 2 ICP embedding cosine similarity"
```

---

## Task 4: Layer 3 `score_lead_message` LLM 评分

**Files:**
- Modify: `backend/app/services/llm.py` (加 `score_lead_message` method)
- Create: `backend/tests/test_llm_score_lead_message.py`

- [ ] **Step 4.1: 写测试**

`backend/tests/test_llm_score_lead_message.py`:

```python
"""LLMService.score_lead_message — 结构化 JSON 输出"""
import pytest
import json
from unittest.mock import patch, MagicMock, AsyncMock

from app.services.llm import LLMService


@pytest.mark.asyncio
async def test_score_lead_returns_full_schema():
    fake_json = {
        "score": 85,
        "intent_type": "buy",
        "extracted_needs": ["100k USDT 一次性买", "海外汇款"],
        "suggested_solution_topic": "USDT 大额场外结算",
        "confidence": 0.92,
        "reason": "明确询问 100k 量级 USDT 渠道",
    }
    fake_session = MagicMock()
    svc = LLMService(fake_session)
    with patch.object(svc, "generate", new=AsyncMock(return_value=json.dumps(fake_json))):
        result = await svc.score_lead_message(
            text="想买 100k USDT 一次", icp_text="找 USDT 大额买家",
            kb_top3=[{"text": "USDT 场外结算"}], recent_context=[],
        )
    assert result["score"] == 85
    assert result["intent_type"] == "buy"
    assert "100k USDT" in result["extracted_needs"][0]
    assert result["suggested_solution_topic"] == "USDT 大额场外结算"
    assert result["confidence"] == 0.92


@pytest.mark.asyncio
async def test_score_lead_handles_llm_failure():
    fake_session = MagicMock()
    svc = LLMService(fake_session)
    with patch.object(svc, "generate", new=AsyncMock(return_value=None)):
        result = await svc.score_lead_message(
            text="x", icp_text=None, kb_top3=[], recent_context=[],
        )
    assert result["score"] == 0
    assert result["confidence"] == 0.0
    assert result["intent_type"] == "other"


@pytest.mark.asyncio
async def test_score_lead_handles_malformed_json():
    """LLM 输出不是合法 JSON → 兜底返回 score=0"""
    fake_session = MagicMock()
    svc = LLMService(fake_session)
    with patch.object(
        svc, "generate", new=AsyncMock(return_value="not a json at all"),
    ):
        result = await svc.score_lead_message(
            text="x", icp_text=None, kb_top3=[], recent_context=[],
        )
    assert result["score"] == 0


@pytest.mark.asyncio
async def test_score_lead_extracts_json_from_markdown_fence():
    """有时 LLM 会把 JSON 包在 ```json...``` 里, 应能 parse"""
    fake_json = {"score": 70, "intent_type": "ask", "extracted_needs": [],
                 "suggested_solution_topic": "x", "confidence": 0.8, "reason": "x"}
    wrapped = f"```json\n{json.dumps(fake_json)}\n```"
    fake_session = MagicMock()
    svc = LLMService(fake_session)
    with patch.object(svc, "generate", new=AsyncMock(return_value=wrapped)):
        result = await svc.score_lead_message(
            text="x", icp_text=None, kb_top3=[], recent_context=[],
        )
    assert result["score"] == 70


@pytest.mark.asyncio
async def test_score_lead_clamps_invalid_values():
    """LLM 返回 score=150 → clamp 到 100"""
    fake_json = {"score": 150, "intent_type": "buy", "extracted_needs": [],
                 "suggested_solution_topic": "x", "confidence": 1.5, "reason": "x"}
    fake_session = MagicMock()
    svc = LLMService(fake_session)
    with patch.object(
        svc, "generate", new=AsyncMock(return_value=json.dumps(fake_json)),
    ):
        result = await svc.score_lead_message(
            text="x", icp_text=None, kb_top3=[], recent_context=[],
        )
    assert result["score"] == 100
    assert result["confidence"] == 1.0
```

- [ ] **Step 4.2: 跑 → fail (方法不存在)**

- [ ] **Step 4.3: 加 method 到 llm.py**

在 `backend/app/services/llm.py` 的 `LLMService` 类内（紧挨 `analyze_intent` 之后）加：

```python
    async def score_lead_message(
        self,
        text: str,
        icp_text: Optional[str],
        kb_top3: list[dict],
        recent_context: list[dict],
    ) -> dict:
        """
        Layer 3: 评分 + 需求提取 + 方案话题建议。

        Args:
            text: 当前群消息
            icp_text: 客户 ICP 自由文本 (None 则不喂)
            kb_top3: KB 检索 top 3, [{"text": ..., "score": ...}, ...]
            recent_context: 最近群上下文, [{"text": ..., "sender": ...}, ...]

        Returns 一致 schema (失败/解析错都返回 zero score):
            {
              "score": 0-100,
              "intent_type": "buy|sell|ask|chat|spam|other",
              "extracted_needs": [str],
              "suggested_solution_topic": str,
              "confidence": 0.0-1.0,
              "reason": str,
            }
        """
        default_fail = {
            "score": 0, "intent_type": "other", "extracted_needs": [],
            "suggested_solution_topic": "", "confidence": 0.0, "reason": "llm_failed",
        }
        if not self.is_configured():
            return default_fail

        icp_block = f"客户 ICP 画像:\n{icp_text}\n" if icp_text else ""
        kb_block = "\n".join(f"- {h.get('text', '')}" for h in kb_top3) if kb_top3 else "(无)"
        ctx_block = "\n".join(
            f"  {m.get('sender', '?')}: {m.get('text', '')}"
            for m in (recent_context or [])[-5:]
        ) or "(无)"

        prompt = f"""你在做 TG 群消息的业务线索评分. 客户是一个销售方, 收到群里陌生人的消息, 要判断这条消息是不是真实业务需求。

{icp_block}你的业务知识 (KB 检索 top 3):
{kb_block}

群最近 5 条上下文:
{ctx_block}

当前评分的消息:「{text}」

输出 JSON, 不要 markdown 包装:
{{
  "score": 0-100 整数 (业务需求强度: 90+ 强需求, 60-89 中等, 30-59 弱, <30 闲聊或无关),
  "intent_type": "buy" | "sell" | "ask" | "chat" | "spam" | "other",
  "extracted_needs": [字符串数组, 提取的具体需求点; 无则 []],
  "suggested_solution_topic": 一句话方案主题 (用来后续 KB/案例检索),
  "confidence": 0.0-1.0 浮点 (你对评分的把握),
  "reason": 一句话理由
}}
"""
        raw = await self.generate(prompt, source="score_lead_message")
        if not raw:
            return default_fail

        # 容忍 ```json 包装
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            # 去掉首尾 fence
            lines = cleaned.split("\n")
            if len(lines) >= 3:
                cleaned = "\n".join(lines[1:-1])
            else:
                cleaned = cleaned.strip("`").strip()

        try:
            parsed = json.loads(cleaned)
        except (json.JSONDecodeError, TypeError):
            logger.warning("score_lead_message: failed to parse JSON: %r", raw[:200])
            return default_fail

        # clamp + 默认填充
        score = int(parsed.get("score", 0))
        score = max(0, min(100, score))
        confidence = float(parsed.get("confidence", 0.0))
        confidence = max(0.0, min(1.0, confidence))
        intent_type = parsed.get("intent_type", "other")
        if intent_type not in ("buy", "sell", "ask", "chat", "spam", "other"):
            intent_type = "other"

        return {
            "score": score,
            "intent_type": intent_type,
            "extracted_needs": parsed.get("extracted_needs", []) or [],
            "suggested_solution_topic": parsed.get("suggested_solution_topic", "") or "",
            "confidence": confidence,
            "reason": parsed.get("reason", "") or "",
        }
```

确保文件顶部已有 `import json`、`logger = logging.getLogger(__name__)`、`from typing import Optional`。

- [ ] **Step 4.4: 跑测试**

```bash
pytest backend/tests/test_llm_score_lead_message.py -v
```
Expected: 5 PASS。

- [ ] **Step 4.5: 提交**

```bash
git add backend/app/services/llm.py backend/tests/test_llm_score_lead_message.py
git commit -m "feat(group-ai/phase2a): LLMService.score_lead_message Layer 3"
```

---

## Task 5: Lead detector 三层 orchestrator

**Files:**
- Modify: `backend/app/services/lead_detector.py` (加 `run_all_layers` 函数)
- Create: `backend/tests/test_lead_detector_layers123.py`

- [ ] **Step 5.1: 写测试**

`backend/tests/test_lead_detector_layers123.py`:

```python
"""Lead detector 三层串联 + 早返 + borderline 处理"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.lead_detector import run_all_layers


@pytest.mark.asyncio
async def test_run_all_pass():
    """三层都通过"""
    fake_session = MagicMock()
    customer = MagicMock(
        icp_profile_embedding=[0.5]*768,
        lead_detector_thresholds={"layer2_sim": 0.55, "layer3_score": 60, "layer3_confidence": 0.7},
    )
    monitor = MagicMock(
        keyword_filters={"include": ["USDT"], "exclude": [], "mode": "any"},
        keyword=None,
    )
    fake_llm_result = {
        "score": 80, "intent_type": "buy", "extracted_needs": ["100k"],
        "suggested_solution_topic": "USDT 大额", "confidence": 0.9, "reason": "x",
    }
    with patch(
        "app.services.lead_detector.layer2_icp_similarity",
        return_value={"pass": True, "similarity": 0.7, "degraded": False, "borderline": False},
    ), patch(
        "app.services.lead_detector._score_lead",
        new=AsyncMock(return_value=fake_llm_result),
    ), patch(
        "app.services.lead_detector._fetch_kb_top3",
        new=AsyncMock(return_value=[]),
    ), patch(
        "app.services.lead_detector._fetch_recent_context",
        new=AsyncMock(return_value=[]),
    ):
        result = await run_all_layers(
            session=fake_session, customer=customer, monitor=monitor,
            text="求 USDT 100k", chat_id=-100,
        )
    assert result["pass"] is True
    assert result["layer1_matched"] == ["USDT"]
    assert result["layer2_similarity"] == 0.7
    assert result["layer3"]["score"] == 80
    assert result.get("borderline") is False


@pytest.mark.asyncio
async def test_run_layer1_miss_short_circuits():
    fake_session = MagicMock()
    customer = MagicMock(icp_profile_embedding=None, lead_detector_thresholds={"layer2_sim": 0.55, "layer3_score": 60, "layer3_confidence": 0.7})
    monitor = MagicMock(keyword_filters={"include": ["USDT"], "exclude": [], "mode": "any"}, keyword=None)
    with patch(
        "app.services.lead_detector._score_lead", new=AsyncMock(),
    ) as mocked_score:
        result = await run_all_layers(
            session=fake_session, customer=customer, monitor=monitor,
            text="今天天气好", chat_id=-100,
        )
    assert result["pass"] is False
    assert result["skip_reason"] == "layer1_miss"
    mocked_score.assert_not_called()


@pytest.mark.asyncio
async def test_run_layer2_miss():
    fake_session = MagicMock()
    customer = MagicMock(
        icp_profile_embedding=[0.5]*768,
        lead_detector_thresholds={"layer2_sim": 0.55, "layer3_score": 60, "layer3_confidence": 0.7},
    )
    monitor = MagicMock(
        keyword_filters={"include": ["USDT"], "exclude": [], "mode": "any"}, keyword=None,
    )
    with patch(
        "app.services.lead_detector.layer2_icp_similarity",
        return_value={"pass": False, "similarity": 0.3, "degraded": False, "borderline": False},
    ), patch(
        "app.services.lead_detector._score_lead", new=AsyncMock(),
    ) as mocked_score:
        result = await run_all_layers(
            session=fake_session, customer=customer, monitor=monitor,
            text="求 USDT 但其实不相关", chat_id=-100,
        )
    assert result["pass"] is False
    assert result["skip_reason"] == "layer2_miss"
    mocked_score.assert_not_called()


@pytest.mark.asyncio
async def test_run_layer3_borderline_reported():
    """Layer 3 score=58 落在 [55, 60) → pass=False + borderline=True"""
    fake_session = MagicMock()
    customer = MagicMock(
        icp_profile_embedding=[0.5]*768,
        lead_detector_thresholds={"layer2_sim": 0.55, "layer3_score": 60, "layer3_confidence": 0.7},
    )
    monitor = MagicMock(keyword_filters={"include": ["USDT"], "exclude": [], "mode": "any"}, keyword=None)
    with patch(
        "app.services.lead_detector.layer2_icp_similarity",
        return_value={"pass": True, "similarity": 0.7, "degraded": False, "borderline": False},
    ), patch(
        "app.services.lead_detector._score_lead",
        new=AsyncMock(return_value={
            "score": 58, "intent_type": "ask", "extracted_needs": [],
            "suggested_solution_topic": "x", "confidence": 0.8, "reason": "x",
        }),
    ), patch(
        "app.services.lead_detector._fetch_kb_top3", new=AsyncMock(return_value=[]),
    ), patch(
        "app.services.lead_detector._fetch_recent_context", new=AsyncMock(return_value=[]),
    ):
        result = await run_all_layers(
            session=fake_session, customer=customer, monitor=monitor,
            text="USDT 一般问问", chat_id=-100,
        )
    assert result["pass"] is False
    assert result["skip_reason"] == "layer3_miss"
    assert result.get("borderline") is True


@pytest.mark.asyncio
async def test_run_layer2_degraded_skips_to_layer3():
    """customer.icp_embedding=None → Layer 2 降级 → 直接跑 Layer 3"""
    fake_session = MagicMock()
    customer = MagicMock(
        icp_profile_embedding=None,
        lead_detector_thresholds={"layer2_sim": 0.55, "layer3_score": 60, "layer3_confidence": 0.7},
    )
    monitor = MagicMock(keyword_filters={"include": ["USDT"], "exclude": [], "mode": "any"}, keyword=None)
    fake_llm = {
        "score": 85, "intent_type": "buy", "extracted_needs": ["x"],
        "suggested_solution_topic": "x", "confidence": 0.9, "reason": "x",
    }
    with patch(
        "app.services.lead_detector._score_lead", new=AsyncMock(return_value=fake_llm),
    ), patch(
        "app.services.lead_detector._fetch_kb_top3", new=AsyncMock(return_value=[]),
    ), patch(
        "app.services.lead_detector._fetch_recent_context", new=AsyncMock(return_value=[]),
    ):
        result = await run_all_layers(
            session=fake_session, customer=customer, monitor=monitor,
            text="求 USDT", chat_id=-100,
        )
    assert result["pass"] is True
    assert result["layer2_similarity"] is None  # degraded
```

- [ ] **Step 5.2: 跑 → fail**

- [ ] **Step 5.3: 实装 run_all_layers**

在 `backend/app/services/lead_detector.py` 末尾加：

```python
from typing import Any

from app.services.llm import LLMService
from app.services.kb_retrieval import retrieve_relevant_kb


async def _score_lead(*, session, text, icp_text, kb_top3, recent_context) -> dict:
    """薄包装 LLMService.score_lead_message, 方便 mock。"""
    svc = LLMService(session)
    return await svc.score_lead_message(
        text=text, icp_text=icp_text, kb_top3=kb_top3, recent_context=recent_context,
    )


async def _fetch_kb_top3(*, session, customer_id, query) -> list[dict]:
    """从 KB 取 top 3, 返回 [{text, score}, ...]"""
    if not query:
        return []
    try:
        rows = retrieve_relevant_kb(
            session, query, top_k=3, customer_id_filter=customer_id,
        )
        return [{"text": r.content, "score": 1.0} for r in (rows or [])]
    except Exception:
        logger.exception("kb_top3 fetch failed")
        return []


async def _fetch_recent_context(*, session, chat_id, before_message_id=None) -> list[dict]:
    """从 group_message 表取最近 5 条群上下文 (不含当前消息)。

    Phase 2a: 简化为空返回, Phase 3 再接入 group_message 查询。
    """
    return []


async def run_all_layers(
    *, session, customer, monitor, text: str, chat_id: int,
) -> dict:
    """
    跑 Layer 1 → 2 → 3, 早返 + borderline 标记。

    Returns:
        pass=True 时: {
          "pass": True, "layer1_matched": [...],
          "layer2_similarity": float|None, "layer3": {...full dict},
          "borderline": False,
        }
        pass=False 时: {
          "pass": False, "skip_reason": "layer1_miss"|"layer2_miss"|"layer3_miss",
          "layer1_matched": [...], "layer2_similarity": float|None,
          "layer3": {...}|None, "borderline": bool,
        }
    """
    thresholds = customer.lead_detector_thresholds or {
        "layer2_sim": 0.55, "layer3_score": 60, "layer3_confidence": 0.7,
    }

    # Layer 1
    l1 = layer1_keyword_match(
        text,
        filters=getattr(monitor, "keyword_filters", None),
        legacy_keyword=getattr(monitor, "keyword", None),
    )
    if not l1["pass"]:
        return {
            "pass": False, "skip_reason": "layer1_miss",
            "layer1_matched": [], "layer2_similarity": None,
            "layer3": None, "borderline": False,
        }

    # Layer 2
    l2 = layer2_icp_similarity(
        session=session, text=text,
        icp_embedding=customer.icp_profile_embedding,
        threshold=thresholds.get("layer2_sim", 0.55),
    )
    if not l2["pass"]:
        return {
            "pass": False, "skip_reason": "layer2_miss",
            "layer1_matched": l1["matched"], "layer2_similarity": l2["similarity"],
            "layer3": None, "borderline": l2.get("borderline", False),
        }

    # Layer 3
    kb_top3 = await _fetch_kb_top3(
        session=session, customer_id=customer.id, query=text,
    )
    recent_ctx = await _fetch_recent_context(session=session, chat_id=chat_id)
    l3 = await _score_lead(
        session=session, text=text,
        icp_text=customer.icp_profile_text,
        kb_top3=kb_top3, recent_context=recent_ctx,
    )

    score_thr = thresholds.get("layer3_score", 60)
    conf_thr = thresholds.get("layer3_confidence", 0.7)
    score = l3["score"]
    conf = l3["confidence"]

    passed = score >= score_thr and conf >= conf_thr
    borderline = False
    if not passed:
        # score 落在 [score_thr-5, score_thr) 或 confidence 落在 [conf_thr-0.1, conf_thr)
        borderline = (
            (score_thr - 5 <= score < score_thr) or
            (conf_thr - 0.1 <= conf < conf_thr)
        )

    if not passed:
        return {
            "pass": False, "skip_reason": "layer3_miss",
            "layer1_matched": l1["matched"], "layer2_similarity": l2["similarity"],
            "layer3": l3, "borderline": borderline,
        }

    return {
        "pass": True, "layer1_matched": l1["matched"],
        "layer2_similarity": l2["similarity"], "layer3": l3,
        "borderline": False,
    }
```

- [ ] **Step 5.4: 跑测试**

```bash
pytest backend/tests/test_lead_detector_layers123.py -v
```
Expected: 5 PASS。

也跑一下原 Layer 1 单测确保没回归：
```bash
pytest backend/tests/test_lead_detector_layer1.py -v
```

- [ ] **Step 5.5: 提交**

```bash
git add backend/app/services/lead_detector.py backend/tests/test_lead_detector_layers123.py
git commit -m "feat(group-ai/phase2a): lead detector run_all_layers orchestrator"
```

---

## Task 6: pipeline.entrypoint 接入三层

**Files:**
- Modify: `backend/app/services/group_reply_pipeline.py`
- Modify: `backend/tests/test_group_reply_pipeline.py` (扩展现有测试)

- [ ] **Step 6.1: 修改 entrypoint 调 run_all_layers**

修改 `backend/app/services/group_reply_pipeline.py` 的 `entrypoint`：

```python
import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlmodel import Session

from app.core.database import engine
from app.core.group_reply_config import DEFAULT_PERSONA, GROUP_AI_REPLY_ENABLED
from app.models.customer import Customer
from app.models.pending_reply import PendingReply, PendingReplyStatus
from app.services.lead_detector import run_all_layers

logger = logging.getLogger(__name__)


async def entrypoint(msg, account, monitor) -> dict:
    if not GROUP_AI_REPLY_ENABLED:
        return {"skipped": "feature_off"}
    if getattr(account, "role", None) == "collector":
        return {"skipped": "collector_role"}

    customer_id = getattr(account, "customer_id", None)
    if customer_id is None:
        return {"skipped": "no_customer"}
    if getattr(monitor, "customer_id", None) is None:
        return {"skipped": "monitor_no_customer"}

    text = getattr(msg, "text", None) or ""
    if not text:
        return {"skipped": "empty_text"}

    # 走 run_all_layers (Phase 2a 三层)
    with Session(engine) as session:
        customer = session.get(Customer, customer_id)
        if customer is None:
            return {"skipped": "customer_not_found"}

        result = await run_all_layers(
            session=session, customer=customer, monitor=monitor,
            text=text, chat_id=msg.chat_id,
        )

        if not result["pass"]:
            # borderline 也写一行 pending_replies, 但 status=skipped_borderline
            # 非 borderline 直接 return, 不写库
            if result.get("borderline"):
                pr = _insert_borderline(
                    session=session,
                    customer_id=customer_id, monitor_id=monitor.id,
                    chat_id=msg.chat_id, message_id=msg.id,
                    source_user_id=msg.sender_id, source_text=text,
                    layer1_matched=result["layer1_matched"],
                    layer2_similarity=result["layer2_similarity"],
                    layer3=result.get("layer3"),
                    skip_reason=result["skip_reason"],
                )
                return {"skipped": "borderline", "pending_reply_id": pr.id}
            return {"skipped": result["skip_reason"]}

        # Layer 1+2+3 全 pass → 排队入 observing
        obs_min, obs_max = DEFAULT_PERSONA["observation_window_seconds_range"]
        obs_seconds = random.randint(obs_min, obs_max)
        pr = _insert_observing(
            session=session,
            customer_id=customer_id, monitor_id=monitor.id,
            chat_id=msg.chat_id, message_id=msg.id,
            source_user_id=msg.sender_id, source_text=text,
            layer1_matched=result["layer1_matched"],
            layer2_similarity=result["layer2_similarity"],
            layer3=result["layer3"],
            observation_window_seconds=obs_seconds,
        )
        logger.info(
            "pipeline: pending_reply id=%s queued (window=%ss, score=%s)",
            pr.id, obs_seconds, result["layer3"]["score"],
        )
        return {"pending_reply_id": pr.id}


def _insert_observing(
    *, session, customer_id, monitor_id, chat_id, message_id, source_user_id,
    source_text, layer1_matched, layer2_similarity, layer3, observation_window_seconds,
) -> PendingReply:
    now = datetime.now(timezone.utc)
    pr = PendingReply(
        customer_id=customer_id, monitor_id=monitor_id,
        chat_id=chat_id, message_id=message_id, source_user_id=source_user_id,
        source_text=source_text,
        layer1_matched={"matched": layer1_matched},
        layer2_similarity=layer2_similarity,
        layer3_score=layer3["score"],
        layer3_needs=layer3.get("extracted_needs", []),
        layer3_solution_topic=layer3.get("suggested_solution_topic", ""),
        layer3_confidence=layer3["confidence"],
        status=PendingReplyStatus.OBSERVING.value,
        fire_at=now + timedelta(seconds=observation_window_seconds),
        created_at=now,
    )
    session.add(pr)
    session.commit()
    session.refresh(pr)
    return pr


def _insert_borderline(
    *, session, customer_id, monitor_id, chat_id, message_id, source_user_id,
    source_text, layer1_matched, layer2_similarity, layer3, skip_reason,
) -> PendingReply:
    """borderline 写库供后续训练阈值, 不走 observing 流程。"""
    now = datetime.now(timezone.utc)
    pr = PendingReply(
        customer_id=customer_id, monitor_id=monitor_id,
        chat_id=chat_id, message_id=message_id, source_user_id=source_user_id,
        source_text=source_text,
        layer1_matched={"matched": layer1_matched},
        layer2_similarity=layer2_similarity,
        layer3_score=layer3.get("score") if layer3 else None,
        layer3_needs=layer3.get("extracted_needs", []) if layer3 else None,
        layer3_solution_topic=layer3.get("suggested_solution_topic", "") if layer3 else None,
        layer3_confidence=layer3.get("confidence") if layer3 else None,
        status=PendingReplyStatus.SKIPPED_BORDERLINE.value,
        skip_reason=skip_reason,
        created_at=now,
        decided_at=now,
    )
    session.add(pr)
    session.commit()
    session.refresh(pr)
    return pr
```

- [ ] **Step 6.2: 扩展现有测试**

在 `backend/tests/test_group_reply_pipeline.py` 末尾追加：

```python
@pytest.mark.asyncio
async def test_entrypoint_full_three_layers_passes_to_observing():
    """Layer 1+2+3 全 pass → 入 observing, layer3 字段已写入"""
    msg = FakeMsg(text="求 USDT 100k", chat_id=-100, id=42, sender_id=999)
    acc = FakeAcc()
    monitor = FakeMonitor(keyword_filters={"include": ["USDT"], "exclude": [], "mode": "any"})

    mock_pr = MagicMock(id=777)
    mock_customer = MagicMock(id=1)
    fake_result = {
        "pass": True,
        "layer1_matched": ["USDT"],
        "layer2_similarity": 0.7,
        "layer3": {
            "score": 85, "intent_type": "buy",
            "extracted_needs": ["100k USDT"],
            "suggested_solution_topic": "USDT 大额", "confidence": 0.9, "reason": "x",
        },
        "borderline": False,
    }
    fake_session = MagicMock()
    fake_session.get.return_value = mock_customer

    with patch("app.services.group_reply_pipeline.GROUP_AI_REPLY_ENABLED", True), \
         patch("app.services.group_reply_pipeline.Session", return_value=fake_session), \
         patch("app.services.group_reply_pipeline.run_all_layers",
               new=AsyncMock(return_value=fake_result)), \
         patch("app.services.group_reply_pipeline._insert_observing",
               return_value=mock_pr):
        # Session(engine) 的 context manager
        fake_session.__enter__ = MagicMock(return_value=fake_session)
        fake_session.__exit__ = MagicMock(return_value=None)
        result = await entrypoint(msg, acc, monitor)
    assert result == {"pending_reply_id": 777}


@pytest.mark.asyncio
async def test_entrypoint_borderline_inserts_skipped_row():
    """layer3 borderline → 写一行 status=skipped_borderline, return skipped"""
    msg = FakeMsg(text="求 USDT 一般问", chat_id=-100, id=43, sender_id=999)
    acc = FakeAcc()
    monitor = FakeMonitor(keyword_filters={"include": ["USDT"], "exclude": [], "mode": "any"})

    mock_pr = MagicMock(id=778)
    mock_customer = MagicMock(id=1)
    fake_result = {
        "pass": False, "skip_reason": "layer3_miss",
        "layer1_matched": ["USDT"], "layer2_similarity": 0.6,
        "layer3": {"score": 58, "intent_type": "ask", "extracted_needs": [],
                   "suggested_solution_topic": "x", "confidence": 0.8, "reason": "x"},
        "borderline": True,
    }
    fake_session = MagicMock()
    fake_session.get.return_value = mock_customer

    with patch("app.services.group_reply_pipeline.GROUP_AI_REPLY_ENABLED", True), \
         patch("app.services.group_reply_pipeline.Session", return_value=fake_session), \
         patch("app.services.group_reply_pipeline.run_all_layers",
               new=AsyncMock(return_value=fake_result)), \
         patch("app.services.group_reply_pipeline._insert_borderline",
               return_value=mock_pr):
        fake_session.__enter__ = MagicMock(return_value=fake_session)
        fake_session.__exit__ = MagicMock(return_value=None)
        result = await entrypoint(msg, acc, monitor)
    assert result["skipped"] == "borderline"
    assert result["pending_reply_id"] == 778


@pytest.mark.asyncio
async def test_entrypoint_non_borderline_skip_no_db_write():
    """layer1_miss / 非 borderline 不写库"""
    msg = FakeMsg(text="天气好", chat_id=-100, id=44, sender_id=999)
    acc = FakeAcc()
    monitor = FakeMonitor(keyword_filters={"include": ["USDT"], "exclude": [], "mode": "any"})

    fake_result = {
        "pass": False, "skip_reason": "layer1_miss",
        "layer1_matched": [], "layer2_similarity": None,
        "layer3": None, "borderline": False,
    }
    mock_customer = MagicMock(id=1)
    fake_session = MagicMock()
    fake_session.get.return_value = mock_customer

    with patch("app.services.group_reply_pipeline.GROUP_AI_REPLY_ENABLED", True), \
         patch("app.services.group_reply_pipeline.Session", return_value=fake_session), \
         patch("app.services.group_reply_pipeline.run_all_layers",
               new=AsyncMock(return_value=fake_result)), \
         patch("app.services.group_reply_pipeline._insert_borderline") as mocked_b, \
         patch("app.services.group_reply_pipeline._insert_observing") as mocked_o:
        fake_session.__enter__ = MagicMock(return_value=fake_session)
        fake_session.__exit__ = MagicMock(return_value=None)
        result = await entrypoint(msg, acc, monitor)
    assert result == {"skipped": "layer1_miss"}
    mocked_b.assert_not_called()
    mocked_o.assert_not_called()
```

- [ ] **Step 6.3: 跑 — 旧测试可能要修**

```bash
pytest backend/tests/test_group_reply_pipeline.py -v
```

老的 Phase 1 测试用了旧的 `_insert_pending_reply` mock，会失败。要么改 mock 名改成 `_insert_observing`，要么删除老 mock 路径的 test，因为现在签名变了。

如果老测试无法兼容（因为入口逻辑变了，老的"Layer 1 单层 mock"语义不对了），把它们改写成新的三层 mock 格式。**不要删测试覆盖。** 删之前确认每条都有等价新测试。

- [ ] **Step 6.4: 提交**

```bash
git add backend/app/services/group_reply_pipeline.py backend/tests/test_group_reply_pipeline.py
git commit -m "feat(group-ai/phase2a): pipeline.entrypoint runs all 3 layers + borderline"
```

---

## Task 7: CaseStudy CRUD service + admin endpoints

**Files:**
- Create: `backend/app/services/case_study_service.py`
- Create: `backend/app/routers/admin_group_ai.py`
- Modify: `backend/app/main.py` (注册 router)
- Create: `backend/tests/test_case_study_service.py`
- Create: `backend/tests/test_admin_group_ai_endpoints.py`

- [ ] **Step 7.1: 写 service 测试**

`backend/tests/test_case_study_service.py`:

```python
"""CaseStudy service: 录入 + 自动 embedding + 查询 top_k by similarity"""
from unittest.mock import patch, MagicMock

from app.services.case_study_service import (
    create_case_study, update_case_study, delete_case_study,
    list_case_studies, find_top_k_for_topic,
)


def test_create_case_study_with_embedding():
    fake_session = MagicMock()
    fake_session.add = MagicMock()
    fake_session.commit = MagicMock()
    fake_session.refresh = MagicMock()
    fake_vec = [0.5] * 768

    with patch(
        "app.services.case_study_service.embed_text", return_value=fake_vec,
    ):
        case = create_case_study(
            session=fake_session, customer_id=1,
            industry="OTC", deal_size="100k USDT", period="3 days",
            problem="需要海外汇款", solution="USDT 场外", outcome="3天到账",
            tags=["OTC", "USDT"], source="manual_portal",
        )
    assert case.customer_id == 1
    assert case.industry == "OTC"
    assert case.embedding == fake_vec
    assert case.source == "manual_portal"
    fake_session.add.assert_called_once()
    fake_session.commit.assert_called_once()


def test_create_case_study_embedding_failure_still_saves():
    """embedding 失败不阻塞 case 录入"""
    fake_session = MagicMock()
    with patch(
        "app.services.case_study_service.embed_text", return_value=None,
    ):
        case = create_case_study(
            session=fake_session, customer_id=1,
            industry="x", deal_size="x", period="x",
            problem="x", solution="x", outcome="x",
            tags=[], source="manual_portal",
        )
    assert case.embedding is None


def test_find_top_k_for_topic_returns_ordered_by_similarity():
    """简易测试: 验证调用了 with embedding ORDER BY <=>"""
    fake_session = MagicMock()
    fake_rows = [MagicMock(id=1), MagicMock(id=2)]
    fake_query = MagicMock()
    fake_query.all.return_value = fake_rows
    fake_session.exec.return_value = fake_query
    with patch(
        "app.services.case_study_service.embed_text", return_value=[0.5]*768,
    ):
        result = find_top_k_for_topic(
            session=fake_session, customer_id=1, topic="USDT 大额", k=2,
        )
    assert len(result) == 2
    # 验证 session.exec 被调用一次（即查询执行了）
    fake_session.exec.assert_called_once()


def test_find_top_k_empty_topic_returns_empty():
    fake_session = MagicMock()
    result = find_top_k_for_topic(
        session=fake_session, customer_id=1, topic="", k=2,
    )
    assert result == []


def test_find_top_k_embed_failure_falls_back_to_recent():
    """embedding 失败 → 退回到按 last_used_at desc 取最近的 k 条"""
    fake_session = MagicMock()
    fake_rows = [MagicMock(id=1), MagicMock(id=2)]
    fake_query = MagicMock()
    fake_query.all.return_value = fake_rows
    fake_session.exec.return_value = fake_query
    with patch(
        "app.services.case_study_service.embed_text", return_value=None,
    ):
        result = find_top_k_for_topic(
            session=fake_session, customer_id=1, topic="x", k=2,
        )
    assert len(result) == 2


def test_update_case_study_re_embeds_when_solution_changed():
    fake_session = MagicMock()
    fake_case = MagicMock(id=1, customer_id=1, problem="old", solution="old s", outcome="old o", embedding=[0.0]*768)
    fake_session.get.return_value = fake_case
    new_vec = [0.99] * 768
    with patch(
        "app.services.case_study_service.embed_text", return_value=new_vec,
    ):
        ok = update_case_study(
            session=fake_session, case_id=1, customer_id=1,
            problem="new", solution="new s", outcome="new o",
        )
    assert ok is True
    assert fake_case.solution == "new s"
    assert fake_case.embedding == new_vec


def test_delete_case_study_soft_disables():
    fake_session = MagicMock()
    fake_case = MagicMock(id=1, customer_id=1, active=True)
    fake_session.get.return_value = fake_case
    ok = delete_case_study(session=fake_session, case_id=1, customer_id=1)
    assert ok is True
    assert fake_case.active is False  # soft delete
    fake_session.commit.assert_called_once()


def test_list_case_studies_filters_by_customer():
    fake_session = MagicMock()
    fake_query = MagicMock()
    fake_query.all.return_value = [MagicMock(), MagicMock()]
    fake_session.exec.return_value = fake_query
    rows = list_case_studies(session=fake_session, customer_id=1, include_inactive=False)
    assert len(rows) == 2
```

- [ ] **Step 7.2: 跑 → fail**

- [ ] **Step 7.3: 实装 service**

`backend/app/services/case_study_service.py`:

```python
"""
case_study_service — CaseStudy CRUD + 按 solution_topic 查 top-k。

录入 / 更新时自动重算 embedding (problem + solution + outcome 拼接)。
查询走 pgvector cosine。
"""
import logging
from typing import Optional

from sqlmodel import select

from app.models.case_study import CaseStudy
from app.services.embedding_service import embed_text

logger = logging.getLogger(__name__)


def _build_embed_payload(problem: str, solution: str, outcome: str) -> str:
    parts = [p.strip() for p in [problem, solution, outcome] if p and p.strip()]
    return " | ".join(parts)


def create_case_study(
    *, session, customer_id: int, industry: Optional[str],
    deal_size: Optional[str], period: Optional[str],
    problem: str, solution: str, outcome: str,
    tags: Optional[list] = None, source: str = "manual_portal",
) -> CaseStudy:
    payload = _build_embed_payload(problem, solution, outcome)
    vec = embed_text(session=session, text=payload)
    case = CaseStudy(
        customer_id=customer_id,
        industry=industry, deal_size=deal_size, period=period,
        problem=problem, solution=solution, outcome=outcome,
        tags=tags or [],
        embedding=vec,
        source=source, active=True,
    )
    session.add(case)
    session.commit()
    session.refresh(case)
    return case


def update_case_study(
    *, session, case_id: int, customer_id: int,
    industry: Optional[str] = None, deal_size: Optional[str] = None,
    period: Optional[str] = None,
    problem: Optional[str] = None, solution: Optional[str] = None,
    outcome: Optional[str] = None, tags: Optional[list] = None,
) -> bool:
    case = session.get(CaseStudy, case_id)
    if case is None or case.customer_id != customer_id:
        return False

    content_changed = False
    for fname, val in [
        ("industry", industry), ("deal_size", deal_size), ("period", period),
        ("problem", problem), ("solution", solution), ("outcome", outcome),
    ]:
        if val is not None and getattr(case, fname) != val:
            setattr(case, fname, val)
            if fname in ("problem", "solution", "outcome"):
                content_changed = True
    if tags is not None:
        case.tags = tags

    if content_changed:
        payload = _build_embed_payload(case.problem, case.solution, case.outcome)
        case.embedding = embed_text(session=session, text=payload)

    session.add(case)
    session.commit()
    return True


def delete_case_study(*, session, case_id: int, customer_id: int) -> bool:
    """soft delete: active=False"""
    case = session.get(CaseStudy, case_id)
    if case is None or case.customer_id != customer_id:
        return False
    case.active = False
    session.add(case)
    session.commit()
    return True


def list_case_studies(
    *, session, customer_id: int, include_inactive: bool = False,
) -> list:
    stmt = select(CaseStudy).where(CaseStudy.customer_id == customer_id)
    if not include_inactive:
        stmt = stmt.where(CaseStudy.active == True)
    stmt = stmt.order_by(CaseStudy.created_at.desc())
    return list(session.exec(stmt).all())


# pgvector cosine threshold: 候选案例与 topic 的最小相似度
MIN_CASE_MATCH_SIMILARITY = 0.4


def find_top_k_for_topic(
    *, session, customer_id: int, topic: str, k: int = 2,
) -> list:
    """
    按 layer3.suggested_solution_topic 找 top-k 相关案例。

    pgvector 余弦距离 (embedding <=> :vec)。embedding 失败时降级到
    按 last_used_at desc 取 k 条。
    """
    if not topic or not topic.strip():
        return []

    topic_vec = embed_text(session=session, text=topic)
    if topic_vec is None:
        # 降级: 取最近用过的 k 条
        stmt = (
            select(CaseStudy)
            .where(CaseStudy.customer_id == customer_id, CaseStudy.active == True)
            .order_by(CaseStudy.last_used_at.desc().nullslast(),
                      CaseStudy.created_at.desc())
            .limit(k)
        )
        return list(session.exec(stmt).all())

    # pgvector cosine: 距离 (1 - similarity), 越小越相似
    # SQLAlchemy via pgvector.sqlalchemy: cosine_distance method
    stmt = (
        select(CaseStudy)
        .where(
            CaseStudy.customer_id == customer_id,
            CaseStudy.active == True,
            CaseStudy.embedding.isnot(None),
        )
        .order_by(CaseStudy.embedding.cosine_distance(topic_vec))
        .limit(k)
    )
    rows = list(session.exec(stmt).all())
    return rows
```

> **NOTE:** `CaseStudy.embedding.cosine_distance(topic_vec)` 依赖 `pgvector.sqlalchemy.Vector` 的 ORM 扩展。如果 import 时报 `cosine_distance` 不可用，使用原生 SQL: `stmt.order_by(sa.text("embedding <=> :vec").bindparams(vec=topic_vec))`。

- [ ] **Step 7.4: 跑测试**

```bash
pytest backend/tests/test_case_study_service.py -v
```
Expected: 8 PASS。

- [ ] **Step 7.5: 实装 admin router**

`backend/app/routers/admin_group_ai.py`:

```python
"""
admin Group AI Sales endpoints — Phase 2a 仅有 admin 视角。
客户视角的 endpoint (Portal UI) 由 Phase 2b 接。
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from pydantic import BaseModel

from app.core.database import get_session
from app.services.case_study_service import (
    create_case_study, update_case_study, delete_case_study,
    list_case_studies,
)
from app.services.customer_icp_service import set_customer_icp_text_and_embed
# TODO: 替换成现有 admin 权限依赖, 例如 get_current_admin
# from app.core.security import get_current_admin

router = APIRouter(prefix="/admin/group-ai", tags=["admin-group-ai"])


# === Schemas ===

class ICPUpdate(BaseModel):
    icp_text: Optional[str] = None


class ThresholdsUpdate(BaseModel):
    layer2_sim: Optional[float] = None
    layer3_score: Optional[int] = None
    layer3_confidence: Optional[float] = None


class CaseStudyCreate(BaseModel):
    industry: Optional[str] = None
    deal_size: Optional[str] = None
    period: Optional[str] = None
    problem: str
    solution: str
    outcome: str
    tags: list[str] = []


class CaseStudyUpdate(BaseModel):
    industry: Optional[str] = None
    deal_size: Optional[str] = None
    period: Optional[str] = None
    problem: Optional[str] = None
    solution: Optional[str] = None
    outcome: Optional[str] = None
    tags: Optional[list[str]] = None


# === Endpoints ===

@router.put("/customers/{customer_id}/icp")
async def update_customer_icp(
    customer_id: int, body: ICPUpdate, session: Session = Depends(get_session),
):
    ok = set_customer_icp_text_and_embed(
        session=session, customer_id=customer_id, new_text=body.icp_text,
    )
    if not ok:
        raise HTTPException(404, "customer not found")
    return {"ok": True}


@router.put("/customers/{customer_id}/thresholds")
async def update_customer_thresholds(
    customer_id: int, body: ThresholdsUpdate,
    session: Session = Depends(get_session),
):
    from app.models.customer import Customer
    customer = session.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(404, "customer not found")
    thresholds = dict(customer.lead_detector_thresholds or {})
    if body.layer2_sim is not None:
        if not 0.0 <= body.layer2_sim <= 1.0:
            raise HTTPException(400, "layer2_sim out of range")
        thresholds["layer2_sim"] = body.layer2_sim
    if body.layer3_score is not None:
        if not 0 <= body.layer3_score <= 100:
            raise HTTPException(400, "layer3_score out of range")
        thresholds["layer3_score"] = body.layer3_score
    if body.layer3_confidence is not None:
        if not 0.0 <= body.layer3_confidence <= 1.0:
            raise HTTPException(400, "layer3_confidence out of range")
        thresholds["layer3_confidence"] = body.layer3_confidence

    customer.lead_detector_thresholds = thresholds
    session.add(customer)
    session.commit()
    return {"ok": True, "thresholds": thresholds}


@router.post("/customers/{customer_id}/case-studies")
async def create_case(
    customer_id: int, body: CaseStudyCreate,
    session: Session = Depends(get_session),
):
    case = create_case_study(
        session=session, customer_id=customer_id,
        industry=body.industry, deal_size=body.deal_size, period=body.period,
        problem=body.problem, solution=body.solution, outcome=body.outcome,
        tags=body.tags, source="manual_portal",
    )
    return {"id": case.id}


@router.get("/customers/{customer_id}/case-studies")
async def list_cases(
    customer_id: int, include_inactive: bool = False,
    session: Session = Depends(get_session),
):
    rows = list_case_studies(
        session=session, customer_id=customer_id, include_inactive=include_inactive,
    )
    return [
        {
            "id": c.id, "industry": c.industry, "deal_size": c.deal_size,
            "period": c.period, "problem": c.problem, "solution": c.solution,
            "outcome": c.outcome, "tags": c.tags, "active": c.active,
            "source": c.source, "created_at": c.created_at,
        }
        for c in rows
    ]


@router.put("/customers/{customer_id}/case-studies/{case_id}")
async def update_case(
    customer_id: int, case_id: int, body: CaseStudyUpdate,
    session: Session = Depends(get_session),
):
    ok = update_case_study(
        session=session, case_id=case_id, customer_id=customer_id,
        industry=body.industry, deal_size=body.deal_size, period=body.period,
        problem=body.problem, solution=body.solution, outcome=body.outcome,
        tags=body.tags,
    )
    if not ok:
        raise HTTPException(404, "case not found")
    return {"ok": True}


@router.delete("/customers/{customer_id}/case-studies/{case_id}")
async def delete_case(
    customer_id: int, case_id: int,
    session: Session = Depends(get_session),
):
    ok = delete_case_study(
        session=session, case_id=case_id, customer_id=customer_id,
    )
    if not ok:
        raise HTTPException(404, "case not found")
    return {"ok": True}
```

> **TODO 实施者:** 加上现有 admin 权限依赖 (`Depends(get_current_admin)` 或 `Depends(require_admin)`)。grep `backend/app/routers/admin*.py` 看现有 admin endpoint 怎么写权限。

注册 router 到 `backend/app/main.py`:

```python
from app.routers import admin_group_ai
# 在 app.include_router 调用区域加:
app.include_router(admin_group_ai.router)
```

- [ ] **Step 7.6: 写 endpoint smoke 测试**

`backend/tests/test_admin_group_ai_endpoints.py`:

```python
"""admin Group AI endpoints smoke (FastAPI TestClient)"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def test_update_icp_endpoint_404_unknown_customer(client):
    with patch(
        "app.routers.admin_group_ai.set_customer_icp_text_and_embed",
        return_value=False,
    ):
        r = client.put("/admin/group-ai/customers/9999/icp", json={"icp_text": "x"})
    assert r.status_code == 404


def test_update_thresholds_validates_range(client):
    # layer2_sim=2.0 越界
    fake_customer = MagicMock(lead_detector_thresholds={})
    with patch(
        "app.routers.admin_group_ai.Customer", create=True,
    ) as mocked_customer_cls:
        # session.get(Customer, ...) returns mock
        with patch("app.routers.admin_group_ai.get_session") as ms:
            fake_session = MagicMock()
            fake_session.get.return_value = fake_customer
            ms.return_value.__next__ = MagicMock(return_value=fake_session)
            r = client.put(
                "/admin/group-ai/customers/1/thresholds",
                json={"layer2_sim": 2.0},
            )
    assert r.status_code == 400


def test_create_case_returns_id(client):
    fake_case = MagicMock(id=42)
    with patch(
        "app.routers.admin_group_ai.create_case_study", return_value=fake_case,
    ):
        r = client.post(
            "/admin/group-ai/customers/1/case-studies",
            json={
                "industry": "OTC", "deal_size": "100k", "period": "3d",
                "problem": "x", "solution": "y", "outcome": "z", "tags": [],
            },
        )
    assert r.status_code == 200
    assert r.json() == {"id": 42}
```

> **TODO 实施者:** 如果 endpoints 有 admin auth dependency, 上面的 TestClient 调用要 mock auth。具体看现有 admin endpoint 测试怎么处理 auth (e.g., conftest 里有 admin_token fixture)。

- [ ] **Step 7.7: 跑测试**

```bash
pytest backend/tests/test_admin_group_ai_endpoints.py -v
```

- [ ] **Step 7.8: 提交**

```bash
git add backend/app/services/case_study_service.py \
        backend/app/routers/admin_group_ai.py \
        backend/app/main.py \
        backend/tests/test_case_study_service.py \
        backend/tests/test_admin_group_ai_endpoints.py
git commit -m "feat(group-ai/phase2a): case_study service + admin endpoints (ICP/thresholds/cases)"
```

---

## Task 8: Reply composer 接入 case_studies + 数字一致性反幻觉

**Files:**
- Modify: `backend/app/services/reply_composer.py`
- Create: `backend/tests/test_reply_composer_phase2a.py`

- [ ] **Step 8.1: 写测试**

`backend/tests/test_reply_composer_phase2a.py`:

```python
"""ReplyComposer Phase 2a: 接入 case_studies + 数字一致性反幻觉"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from app.services.reply_composer import (
    compose_reply_phase2a, _extract_numbers, _numeric_consistency_ok,
)


def test_extract_numbers_simple():
    assert _extract_numbers("100k USDT") == {"100k"}
    assert _extract_numbers("3 天到账, 30 万美金") == {"3", "30", "30万"}
    assert _extract_numbers("无数字") == set()


def test_extract_numbers_multiple_formats():
    # 整数 / 浮点 / 量级单位
    text = "上周帮客户 5 笔, 总额 30 万 USDT, 单笔 50k"
    nums = _extract_numbers(text)
    assert "5" in nums
    assert "30" in nums or "30万" in nums
    assert "50k" in nums


def test_numeric_consistency_ok_when_all_numbers_in_sources():
    reply = "USDT 大额 T+0 直接到账, 上周帮客户跑了 100k 单笔"
    sources = ["案例: 100k USDT 单笔, 3 天到账", "KB: T+0 结算"]
    assert _numeric_consistency_ok(reply, sources) is True


def test_numeric_consistency_blocks_hallucinated_number():
    reply = "USDT 大额. 上周帮客户跑了 999k"
    sources = ["案例: 100k USDT, 3 天"]
    assert _numeric_consistency_ok(reply, sources) is False


def test_numeric_consistency_ok_when_no_numbers():
    reply = "USDT 私聊详谈"
    sources = ["案例"]
    assert _numeric_consistency_ok(reply, sources) is True


@pytest.mark.asyncio
async def test_compose_phase2a_uses_case_top1_in_prompt():
    """compose 时 case_top1 应被拼进 prompt"""
    fake_case = MagicMock(
        problem="海外汇款", solution="USDT 场外", outcome="3 天到账",
        deal_size="100k USDT",
    )
    captured_prompt = {}

    async def fake_llm_generate(prompt):
        captured_prompt["v"] = prompt
        return "USDT 大额 T+0 100k 案例已成 私聊"

    with patch(
        "app.services.reply_composer.kb_retrieve_top_k",
        new=AsyncMock(return_value=[{"text": "USDT T+0", "score": 0.9}]),
    ), patch(
        "app.services.reply_composer.find_case_top_k",
        return_value=[fake_case],
    ), patch(
        "app.services.reply_composer.llm_generate_reply",
        new=AsyncMock(side_effect=fake_llm_generate),
    ):
        result = await compose_reply_phase2a(
            customer_id=1,
            source_text="想买 100k USDT",
            solution_topic="USDT 大额场外",
            session=MagicMock(),
        )
    assert result is not None
    prompt = captured_prompt["v"]
    assert "100k USDT" in prompt  # case deal_size
    assert "海外汇款" in prompt  # case problem
    assert "3 天到账" in prompt  # case outcome


@pytest.mark.asyncio
async def test_compose_phase2a_numeric_filter_rejects_hallucinated_reply():
    """LLM 吐出 case 没有的数字 → 反幻觉拒, 重试"""
    fake_case = MagicMock(
        problem="x", solution="x", outcome="x", deal_size="100k USDT",
    )
    bad_reply = "USDT 大额. 帮客户跑了 999k"  # 999k 不在源数据里
    good_reply = "USDT 大额 100k 案例已成 私聊"

    call_count = {"n": 0}
    async def fake_llm(prompt):
        call_count["n"] += 1
        return bad_reply if call_count["n"] == 1 else good_reply

    with patch(
        "app.services.reply_composer.kb_retrieve_top_k",
        new=AsyncMock(return_value=[]),
    ), patch(
        "app.services.reply_composer.find_case_top_k",
        return_value=[fake_case],
    ), patch(
        "app.services.reply_composer.llm_generate_reply",
        new=AsyncMock(side_effect=fake_llm),
    ):
        result = await compose_reply_phase2a(
            customer_id=1, source_text="x", solution_topic="USDT 大额",
            session=MagicMock(),
        )
    assert result == good_reply or "100k" in result
    assert call_count["n"] >= 2  # 第一次被拒, 重试


@pytest.mark.asyncio
async def test_compose_phase2a_no_case_fallback_to_kb_only():
    """无案例匹配 → 用 KB 兜底, 不要因为案例缺失就失败"""
    with patch(
        "app.services.reply_composer.kb_retrieve_top_k",
        new=AsyncMock(return_value=[{"text": "USDT T+0", "score": 0.9}]),
    ), patch(
        "app.services.reply_composer.find_case_top_k", return_value=[],
    ), patch(
        "app.services.reply_composer.llm_generate_reply",
        new=AsyncMock(return_value="USDT T+0 直接到账 私聊"),
    ):
        result = await compose_reply_phase2a(
            customer_id=1, source_text="x", solution_topic="USDT",
            session=MagicMock(),
        )
    assert result is not None
```

- [ ] **Step 8.2: 跑 → fail**

- [ ] **Step 8.3: 实装 compose_reply_phase2a**

修改 `backend/app/services/reply_composer.py`。**保留** 现有 `compose_reply_phase1`（向后兼容），**新增** `compose_reply_phase2a`：

```python
import re
from typing import Optional

from app.services.case_study_service import find_top_k_for_topic

# ... existing imports ...


# 数字 + 量级单位 + 单位 的提取正则
# 匹配: 100k, 30万, 3 天, 50%, 1.5 亿, T+0
_NUMBER_PATTERNS = [
    r"\d+(?:\.\d+)?[kKmMbB万亿百千]?",       # 100k / 30万 / 1.5亿
    r"T\+\d+",                                 # T+0 / T+1
    r"\d+(?:\.\d+)?%",                         # 50%
]


def _extract_numbers(text: str) -> set[str]:
    if not text:
        return set()
    found = set()
    for pat in _NUMBER_PATTERNS:
        found.update(m.group(0) for m in re.finditer(pat, text))
    # 归一化: 100K -> 100k
    return {n.replace("K", "k").replace("M", "m").replace("B", "b") for n in found}


def _numeric_consistency_ok(reply_text: str, sources: list[str]) -> bool:
    """回复里的所有数字都必须能在 sources 任一条里找到 (大小写归一)。"""
    reply_nums = _extract_numbers(reply_text)
    if not reply_nums:
        return True
    source_nums = set()
    for s in sources:
        source_nums.update(_extract_numbers(s))
    hallucinated = reply_nums - source_nums
    return len(hallucinated) == 0


def find_case_top_k(*, session, customer_id, topic, k=2) -> list:
    """薄包装方便 mock"""
    return find_top_k_for_topic(
        session=session, customer_id=customer_id, topic=topic, k=k,
    )


def _build_prompt_phase2a(
    source_text: str, solution_topic: str,
    kb_hits: list[dict], case_top1,
) -> str:
    kb_block = "\n".join(f"- {h['text']}" for h in kb_hits) if kb_hits else "(无)"
    if case_top1 is not None:
        case_block = (
            f"问题: {case_top1.problem}\n"
            f"方案: {case_top1.solution}\n"
            f"效果: {case_top1.outcome}\n"
            f"金额/规模: {case_top1.deal_size or '未填'}"
        )
    else:
        case_block = "(无匹配案例, 仅用 KB 概述)"

    return f"""你扮演 TG 群里的真人销售。看到陌生人发: 「{source_text}」

你建议的方案主题: {solution_topic}

业务知识 (KB top 3):
{kb_block}

你最近的真实成交案例 (必须使用其中的具体数字, 不要编):
{case_block}

请回复 3 句话, 不超 {MAX_REPLY_LENGTH} 中文字:
1. 一句话方案: 针对对方需求点提出做法
2. 一句话案例: 引用上面真实案例 + 具体数字 (没案例时用一句话效果泛述)
3. 一句话引导: 自然提议私聊深聊

禁止:
- "作为 AI" / "我是助手" / "作为大模型"
- "+V" / "加我 V" / "扫码" / "微信"
- 编造任何未在案例 / KB 出现的数字
- 超过 {MAX_REPLY_LENGTH} 字
- 模板化套话
- 超过 1 个 emoji
"""


async def compose_reply_phase2a(
    *, customer_id: int, source_text: str, solution_topic: str, session,
) -> Optional[str]:
    """
    Phase 2a 三段式: KB + 案例 + 数字一致性反幻觉。

    Args:
        session: SQLModel Session (用于 case_studies + KB 查询)

    Returns:
        str: 最终回复
        None: 失败 (status=failed 由调用方写; Phase 4 改 suggested)
    """
    kb_hits = await kb_retrieve_top_k(customer_id, solution_topic, k=3)
    cases = find_case_top_k(
        session=session, customer_id=customer_id, topic=solution_topic, k=2,
    )
    case_top1 = cases[0] if cases else None

    prompt = _build_prompt_phase2a(source_text, solution_topic, kb_hits, case_top1)

    # 构造 sources 列表供数字一致性检查
    sources = [h.get("text", "") for h in kb_hits]
    if case_top1:
        sources.extend([
            case_top1.problem or "", case_top1.solution or "",
            case_top1.outcome or "", case_top1.deal_size or "",
        ])

    for attempt in range(MAX_RETRIES + 1):
        raw = await llm_generate_reply(prompt)
        filtered = _anti_hallucination_filter(raw)
        if filtered and _passes_filter(filtered) and _numeric_consistency_ok(filtered, sources):
            # 更新 case.last_used_at (best effort, 不阻塞)
            if case_top1:
                try:
                    from datetime import datetime, timezone
                    case_top1.last_used_at = datetime.now(timezone.utc)
                    session.add(case_top1)
                    session.commit()
                except Exception:
                    logger.warning("failed to update case.last_used_at, ignoring")
            return filtered
        logger.info(
            "phase2a compose attempt %d/%d failed (exposure/length/numeric)",
            attempt + 1, MAX_RETRIES + 1,
        )

    return None
```

- [ ] **Step 8.4: 跑测试**

```bash
pytest backend/tests/test_reply_composer_phase2a.py -v
```
Expected: 8 PASS。

也跑现有 Phase 1 测试确保没回归:
```bash
pytest backend/tests/test_reply_composer_phase1.py -v
```

- [ ] **Step 8.5: 提交**

```bash
git add backend/app/services/reply_composer.py backend/tests/test_reply_composer_phase2a.py
git commit -m "feat(group-ai/phase2a): reply_composer w/ case_studies + numeric anti-hallucination"
```

---

## Task 9: scanner 用 layer3.solution_topic + compose_reply_phase2a

**Files:**
- Modify: `backend/app/workers/group_reply_scanner.py`
- Modify: `backend/tests/test_group_reply_scanner.py`

- [ ] **Step 9.1: 改 scanner._process_one**

修改 `_process_one`：把 `compose_reply_phase1` 调用换成 `compose_reply_phase2a`，并使用 `pr.layer3_solution_topic`：

```python
# 旧:
# reply = await compose_reply_phase1(
#     customer_id=pr.customer_id,
#     source_text=pr.source_text,
#     solution_topic=pr.source_text,  # Phase 1 兜底
# )

# 新:
from app.services.reply_composer import compose_reply_phase2a
from sqlmodel import Session
from app.core.database import engine

topic = pr.layer3_solution_topic or pr.source_text  # Phase 2a 用 layer3, 兜底 source_text
with Session(engine) as session:
    reply = await compose_reply_phase2a(
        customer_id=pr.customer_id,
        source_text=pr.source_text,
        solution_topic=topic,
        session=session,
    )
```

注意：现有 scanner 是 mock 友好的（用 `compose_reply_phase1` import 路径），改成新调用后，**现有测试的 mock 路径需要改**：

`backend/tests/test_group_reply_scanner.py` 把：
```python
"app.workers.group_reply_scanner.compose_reply_phase1"
```
全部替换成：
```python
"app.workers.group_reply_scanner.compose_reply_phase2a"
```

- [ ] **Step 9.2: 跑现有 scanner 测试 + 改 mock**

```bash
pytest backend/tests/test_group_reply_scanner.py -v
```

预期老测试 mock 路径不对会失败。改 mock 名后应重新通过 4/4。

- [ ] **Step 9.3: 提交**

```bash
git add backend/app/workers/group_reply_scanner.py backend/tests/test_group_reply_scanner.py
git commit -m "feat(group-ai/phase2a): scanner uses compose_reply_phase2a + layer3 topic"
```

---

## Task 10: Case study 历史抽取脚本（admin 触发）

**Files:**
- Create: `backend/app/services/case_study_extractor.py`
- Create: `backend/scripts/extract_case_studies_from_history.py`
- Modify: `backend/app/routers/admin_group_ai.py` (加 trigger endpoint)
- Create: `backend/tests/test_case_study_extractor.py`

- [ ] **Step 10.1: 写测试**

`backend/tests/test_case_study_extractor.py`:

```python
"""Case study extractor: 从客户主号聊天历史 LLM 抽取成交事件"""
import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.case_study_extractor import extract_cases_for_customer


@pytest.mark.asyncio
async def test_extract_returns_list_of_cases():
    """LLM 返回数组 → service 解析成 case_studies 候选"""
    fake_session = MagicMock()
    fake_history = [
        MagicMock(text="客户 A 要买 100k USDT", sender_id=1),
        MagicMock(text="我们用场外结算 3 天到账", sender_id=2),
        MagicMock(text="已完成, 谢谢", sender_id=1),
    ]
    fake_llm_out = json.dumps([{
        "industry": "OTC", "deal_size": "100k USDT", "period": "3 days",
        "problem": "客户 A 需要 USDT 买入", "solution": "场外结算",
        "outcome": "3 天到账, 客户满意", "tags": ["OTC", "USDT"],
    }])

    with patch(
        "app.services.case_study_extractor._fetch_chat_history",
        return_value=fake_history,
    ), patch(
        "app.services.case_study_extractor._llm_extract",
        new=AsyncMock(return_value=fake_llm_out),
    ):
        cases = await extract_cases_for_customer(
            session=fake_session, customer_id=1, max_history=100,
        )
    assert isinstance(cases, list)
    assert len(cases) == 1
    assert cases[0]["industry"] == "OTC"
    assert cases[0]["deal_size"] == "100k USDT"


@pytest.mark.asyncio
async def test_extract_no_history_returns_empty():
    fake_session = MagicMock()
    with patch(
        "app.services.case_study_extractor._fetch_chat_history", return_value=[],
    ):
        cases = await extract_cases_for_customer(
            session=fake_session, customer_id=1, max_history=100,
        )
    assert cases == []


@pytest.mark.asyncio
async def test_extract_llm_failure_returns_empty():
    fake_session = MagicMock()
    fake_history = [MagicMock(text="x", sender_id=1)]
    with patch(
        "app.services.case_study_extractor._fetch_chat_history",
        return_value=fake_history,
    ), patch(
        "app.services.case_study_extractor._llm_extract",
        new=AsyncMock(return_value=None),
    ):
        cases = await extract_cases_for_customer(
            session=fake_session, customer_id=1, max_history=100,
        )
    assert cases == []


@pytest.mark.asyncio
async def test_extract_malformed_json_returns_empty():
    fake_session = MagicMock()
    fake_history = [MagicMock(text="x", sender_id=1)]
    with patch(
        "app.services.case_study_extractor._fetch_chat_history",
        return_value=fake_history,
    ), patch(
        "app.services.case_study_extractor._llm_extract",
        new=AsyncMock(return_value="not a json"),
    ):
        cases = await extract_cases_for_customer(
            session=fake_session, customer_id=1, max_history=100,
        )
    assert cases == []
```

- [ ] **Step 10.2: 实装 extractor**

`backend/app/services/case_study_extractor.py`:

```python
"""
case_study_extractor — 从客户主号聊天历史中 LLM 抽取成交案例。

复用 qa_extractor 思路, 但目标是"成交事件"而不是"Q&A 对":
  - 输入: customer.id, 主号 chat_history 表最近 N 条对话
  - 处理: 让 LLM 识别"完成的成交事件", 输出结构化案例数组
  - 输出: [{industry, deal_size, period, problem, solution, outcome, tags}, ...]
  - 不直接写库. 调用方 (admin endpoint) 决定是否 confirm 入库。
"""
import json
import logging
from typing import Optional

from app.models.chat_history import ChatHistory
from app.services.llm import LLMService

logger = logging.getLogger(__name__)


def _fetch_chat_history(*, session, customer_id: int, max_history: int = 100) -> list:
    """取该客户主号最近 max_history 条聊天历史。

    Phase 2a: 直接拉 chat_history 表 (按 customer_id 过滤,
              按 created_at desc 取 max_history 条)。
    """
    from sqlmodel import select
    stmt = (
        select(ChatHistory)
        .where(ChatHistory.customer_id == customer_id)
        .order_by(ChatHistory.created_at.desc())
        .limit(max_history)
    )
    rows = list(session.exec(stmt).all())
    # 还原成时间顺序 (asc)
    rows.reverse()
    return rows


async def _llm_extract(*, session, history: list) -> Optional[str]:
    """LLM 分析对话, 输出 JSON 数组字符串。"""
    if not history:
        return None
    dialogue = "\n".join(
        f"{getattr(h, 'sender_id', '?')}: {getattr(h, 'text', '')}" for h in history
    )
    prompt = f"""从下面这段聊天对话里找出所有"已完成成交"的案例 (双方达成合作, 有具体金额或规模, 客户表示完成 / 满意)。

聊天:
{dialogue}

为每个识别出的成交输出一个对象, 格式如下 (JSON 数组, 不要 markdown 包装):
[
  {{
    "industry": 一句话行业 (如 "OTC" / "教培" / "SaaS") 或 "",
    "deal_size": 成交规模 (如 "100k USDT" / "30 万人民币") 或 "",
    "period": 成交周期 (如 "3 天" / "1 周") 或 "",
    "problem": 客户的问题需求,
    "solution": 我方提出的方案,
    "outcome": 实际效果 (含数字),
    "tags": [标签字符串数组]
  }},
  ...
]

如果整段聊天没有任何完成成交, 返回空数组 [].
"""
    svc = LLMService(session)
    return await svc.generate(prompt, source="case_extract")


async def extract_cases_for_customer(
    *, session, customer_id: int, max_history: int = 100,
) -> list[dict]:
    """
    返回 LLM 抽取的案例候选列表 (尚未入库)。调用方决定 confirm / discard。
    失败 / 无数据 → 空列表 (调用方不 raise)。
    """
    history = _fetch_chat_history(
        session=session, customer_id=customer_id, max_history=max_history,
    )
    if not history:
        return []

    raw = await _llm_extract(session=session, history=history)
    if not raw:
        return []

    # 容忍 markdown 包装
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        if len(lines) >= 3:
            cleaned = "\n".join(lines[1:-1])
        else:
            cleaned = cleaned.strip("`").strip()

    try:
        parsed = json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        logger.warning("case extract: bad JSON: %r", raw[:200])
        return []

    if not isinstance(parsed, list):
        return []

    # 过滤掉 problem/solution/outcome 任一为空的
    result = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        if not (item.get("problem") and item.get("solution") and item.get("outcome")):
            continue
        result.append({
            "industry": item.get("industry", "") or "",
            "deal_size": item.get("deal_size", "") or "",
            "period": item.get("period", "") or "",
            "problem": item["problem"], "solution": item["solution"],
            "outcome": item["outcome"],
            "tags": item.get("tags", []) or [],
        })
    return result
```

- [ ] **Step 10.3: 加 admin endpoint**

在 `backend/app/routers/admin_group_ai.py` 加：

```python
from app.services.case_study_extractor import extract_cases_for_customer


@router.post("/customers/{customer_id}/case-studies/extract")
async def extract_cases_endpoint(
    customer_id: int, max_history: int = 100,
    session: Session = Depends(get_session),
):
    """从主号历史抽取案例候选 (不直接入库, 返回供 admin review)"""
    cases = await extract_cases_for_customer(
        session=session, customer_id=customer_id, max_history=max_history,
    )
    return {"candidates": cases}


class CasesBatchCreate(BaseModel):
    cases: list[CaseStudyCreate]


@router.post("/customers/{customer_id}/case-studies/batch")
async def batch_create_cases(
    customer_id: int, body: CasesBatchCreate,
    session: Session = Depends(get_session),
):
    """admin review 后批量入库 (source='ai_confirmed')"""
    ids = []
    for c in body.cases:
        case = create_case_study(
            session=session, customer_id=customer_id,
            industry=c.industry, deal_size=c.deal_size, period=c.period,
            problem=c.problem, solution=c.solution, outcome=c.outcome,
            tags=c.tags, source="ai_confirmed",
        )
        ids.append(case.id)
    return {"ids": ids}
```

- [ ] **Step 10.4: 写命令行脚本（备用，方便客户端 CLI 抽取）**

`backend/scripts/extract_case_studies_from_history.py`:

```python
"""CLI: 从客户主号历史抽取案例并打印候选 JSON。

用法:
  cd backend && python scripts/extract_case_studies_from_history.py --customer-id 1

输出 JSON 数组到 stdout, admin 可手动 review 后用 curl 批量 POST。
"""
import argparse
import asyncio
import json
import sys

from sqlmodel import Session
from app.core.database import engine
from app.services.case_study_extractor import extract_cases_for_customer


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--customer-id", type=int, required=True)
    parser.add_argument("--max-history", type=int, default=100)
    args = parser.parse_args()

    with Session(engine) as session:
        cases = await extract_cases_for_customer(
            session=session,
            customer_id=args.customer_id,
            max_history=args.max_history,
        )
    print(json.dumps(cases, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 10.5: 跑测试**

```bash
pytest backend/tests/test_case_study_extractor.py -v
```
Expected: 4 PASS。

- [ ] **Step 10.6: 提交**

```bash
git add backend/app/services/case_study_extractor.py \
        backend/app/routers/admin_group_ai.py \
        backend/scripts/extract_case_studies_from_history.py \
        backend/tests/test_case_study_extractor.py
git commit -m "feat(group-ai/phase2a): case_study extractor + admin extract/batch endpoints"
```

---

## Task 11: E2E smoke 升级到三层

**Files:**
- Modify: `backend/tests/test_group_reply_e2e.py`

- [ ] **Step 11.1: 改 e2e 测试**

原 Phase 1 e2e 只跑 Layer 1。改成跑全三层并 mock LLM + embedding：

在 fixture 里给 fake_customer 加 `icp_profile_text` 和 `icp_profile_embedding`：

```python
customer = Customer(
    name="e2e_smoke", email="e2e@tg1.ai", hashed_password="x",
    icp_profile_text="想找 USDT 大额买家",
    icp_profile_embedding=[0.5]*768,
    lead_detector_thresholds={"layer2_sim": 0.3, "layer3_score": 50, "layer3_confidence": 0.5},
)
```

阈值放低以便 mock 数据能通过。

在 test body 里 mock `score_lead_message`：

```python
fake_score = {
    "score": 80, "intent_type": "buy",
    "extracted_needs": ["100k USDT"],
    "suggested_solution_topic": "USDT 大额场外",
    "confidence": 0.9, "reason": "x",
}
with patch(
    "app.services.lead_detector.embed_text", return_value=[0.5]*768,
), patch(
    "app.services.lead_detector._score_lead", new=AsyncMock(return_value=fake_score),
), patch(
    "app.services.lead_detector._fetch_kb_top3", new=AsyncMock(return_value=[]),
), patch(
    "app.services.lead_detector._fetch_recent_context", new=AsyncMock(return_value=[]),
), patch(
    "app.services.reply_composer.kb_retrieve_top_k",
    new=AsyncMock(return_value=[{"text": "USDT T+0", "score": 0.9}]),
), patch(
    "app.services.reply_composer.find_case_top_k", return_value=[],
), patch(
    "app.services.reply_composer.llm_generate_reply",
    new=AsyncMock(return_value="USDT 大额 T+0 100k 直达 私聊"),
), patch(
    "app.services.group_dispatcher._telethon_send_to_group",
    new=AsyncMock(return_value=True),
), patch(
    "app.services.group_dispatcher._charge_customer",
    new=AsyncMock(return_value=True),
), patch(
    "app.services.group_dispatcher.asyncio.sleep", new=AsyncMock(),
):
    # ... call entrypoint + scanner ...
```

- [ ] **Step 11.2: 跑 e2e**

```bash
pytest backend/tests/test_group_reply_e2e.py -v
```
Expected: 在 Postgres 环境 PASS（含 layer3_score=80, layer3_solution_topic 填充）。

- [ ] **Step 11.3: 提交**

```bash
git add backend/tests/test_group_reply_e2e.py
git commit -m "test(group-ai/phase2a): e2e covers all 3 layers + case_studies path"
```

---

## Task 12: PR 与 release

- [ ] **Step 12.1: 跑全 Phase 1+2a 测试**

```bash
cd /var/tgsc/.claude/worktrees/feature+group-ai-sales-phase2a
pytest backend/tests/ -k "phase1 or phase2a or group_reply or pending_reply or risk_controller or reply_composer or lead_detector or migration or worker_persona or chitchat or icp or case_study or admin_group_ai or embedding_service" --ignore=backend/tests/test_opentele.py --ignore=backend/tests/test_pyrogram_login.py -v 2>&1 | tail -25
```

Expected: 全部 PASS（含 Phase 1 + Phase 2a）。

- [ ] **Step 12.2: 推分支 + 开 PR**

```bash
git push -u origin feature/group-ai-sales-phase2a
gh pr create --title "feat(group-ai): Phase 2a — 3-layer detection + case studies + numeric anti-hallucination" --base main --body "$(cat <<'EOF'
## Summary

Phase 2a of 群内 AI 销售员: 把识别从只用 Layer 1 关键词升级到三层 (关键词 + ICP embedding + LLM 评分), reply composer 接入真实成交案例 + 数字一致性反幻觉。

- LeadDetector: 新增 `layer2_icp_similarity` + `LLMService.score_lead_message` Layer 3 + `run_all_layers` orchestrator
- ReplyComposer: 新增 `compose_reply_phase2a` 引用 case_studies + 数字一致性检测
- CaseStudy CRUD: admin endpoints (ICP/thresholds/cases/batch) + 历史抽取 (extract endpoint + CLI 脚本)
- pipeline.entrypoint: 三层串联 + borderline 单独入库 (status='skipped_borderline') 用于训练阈值
- scanner._process_one: 用 layer3.solution_topic 而非 source_text 兜底

明确不含 (留给 2b + Phase 3):
- Portal UI (2b)
- worker_persona 实际使用 (Phase 3)
- ChitchatScheduler / 真人接话检测 (Phase 3)

## Test plan

- [ ] alembic head 未变 (Phase 1 一次性建好)
- [ ] 全部 Phase 1 + 2a 测试 PASS
- [ ] 在 staging Postgres + Vertex 凭证下:
  - [ ] 给 customer #1 设 icp_profile_text → 查 DB 看 embedding 768 维
  - [ ] POST /admin/group-ai/customers/1/case-studies 录入 1-2 条案例
  - [ ] 群里发 USDT 高意向消息 → 看 pending_replies 行的 layer1_matched / layer2_similarity / layer3_score / layer3_solution_topic 都填了
  - [ ] reply_text 引用了案例 deal_size, 数字一致性反幻觉没误杀
- [ ] borderline 阈值附近的样本会写 skipped_borderline 行

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Phase 2a 完成判据

- [ ] PR merged
- [ ] 灰度客户跑 24h: layer3_score 分布 / borderline 比例 / 数字反幻觉拒绝率统计回流
- [ ] 至少 1 条 status='sent' 包含真实案例 deal_size 引用
- [ ] 写 memory: 灰度数据 / 阈值实际调整 / 案例库自动抽取效果

---

## 不在 Phase 2a 范围（已分配）

| 给 Phase 2b（portal UI） | 给 Phase 3（拟人化） |
|---|---|
| Portal ICP 编辑器 | worker_personas 实际使用 |
| Portal threshold 滑块 | persona_rewriter 实装 |
| Portal case_studies CRUD UI | ChitchatScheduler + chitchat_pool |
| Portal "扫描历史" 按钮 + review modal | 真人接话检测 (RiskController 升级) |
| 实时统计页 (skip_reason 分布) | active_hours 排程 |
| 客户自助 endpoint (vs admin endpoint) | 加权随机选号 |
