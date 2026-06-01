# LLM Safety Stack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a 5-layer defense stack around every LLM call so that group-message content cannot trigger another Google Vertex account ban. Layers: L0 keyword blacklist → L1 local toxic-bert moderation → L2 routing (Vertex for clean, DeepSeek-V3 for grey, refuse for red) → L3 sales handover → L4 monitoring.

**Architecture:** A single chokepoint (`SafetyGate.evaluate`) sits in front of `LLMService.get_response` / `LLMService.analyze_intent`. Callers no longer pick a provider — they call `LLMRouter.generate(prompt, ...)` which runs L0 → L1, computes a score, picks a provider (Vertex / DeepSeek / refuse) based on thresholds, then dispatches via the existing `LLMService` provider switch (already supports both via OpenAI-compatible + Vertex paths). All filter decisions and provider choices are recorded as new columns on `llm_usage` (`moderation_score`, `block_layer`, `routed_provider`) for monitoring + retro analysis.

**Tech Stack:** Python 3.10, FastAPI, SQLModel/SQLAlchemy, Alembic, pytest, asyncio. New deps: `onnxruntime` (already pulled by fastembed in [[project-reranker-state]]) — reused for toxic-bert. DeepSeek reached via the existing OpenAI-compatible client path in `llm.py:118-133`. No new infra services.

**Spec reference:** Memory entry `project_llm_safety_architecture` (2026-06-01 decision).

**Branches:** All work goes on a single feature branch `feat/llm-safety-stack`. Each Task closes with one commit; each Phase ends with a PR-ready checkpoint.

---

## File Structure

```
backend/
├── app/
│   ├── services/
│   │   ├── safety/                    # NEW package
│   │   │   ├── __init__.py
│   │   │   ├── blacklist.py           # L0 keyword + regex match
│   │   │   ├── moderation.py          # L1 toxic-bert ONNX wrapper
│   │   │   ├── gate.py                # L0+L1 combined, returns SafetyVerdict
│   │   │   └── router.py              # L2 routing + provider selection
│   │   ├── llm.py                     # MODIFY: get_response wrapped in router
│   │   ├── qa_extractor.py            # MODIFY: route through DeepSeek explicitly
│   │   ├── conversation_director.py   # MODIFY: route via LLMRouter
│   │   └── ai_reply_service.py        # MODIFY: route via LLMRouter
│   ├── core/
│   │   └── config.py                  # MODIFY: add moderation thresholds + DeepSeek config keys
│   ├── models/
│   │   └── llm_usage.py               # MODIFY: add moderation_score / block_layer / routed_provider
│   ├── api/
│   │   └── v1/
│   │       └── endpoints/
│   │           └── admin_safety.py    # NEW: thresholds + stats endpoints
│   ├── data/
│   │   └── blacklist/                 # NEW: versioned blacklists
│   │       ├── google_aup_critical.txt
│   │       ├── csam_zh.txt
│   │       ├── csam_en.txt
│   │       └── political_zh.txt
│   ├── tasks/
│   │   └── knowledge_tasks.py         # MODIFY: extract_qa_from_messages uses DeepSeek AIConfig
│   └── alembic/versions/
│       └── c7d8e9f0a1b2_llm_usage_safety_columns.py  # NEW
├── tests/
│   ├── test_safety_blacklist.py       # NEW
│   ├── test_safety_moderation.py      # NEW
│   ├── test_safety_gate.py            # NEW
│   ├── test_llm_router.py             # NEW
│   └── test_qa_extract_uses_deepseek.py  # NEW
└── requirements.txt                   # MODIFY: pin model id, no new pip deps (reuse onnxruntime)

```

**Decomposition rationale:** `safety/` is a sealed package — every public LLM call must pass through `gate.py`. `router.py` is the only place that picks a provider. The existing `llm.py` provider-switch code is unchanged; routing happens *before* `LLMService` is even instantiated (router picks `config_id`).

---

## Pre-flight

- [ ] **Step 0.1: Confirm baseline branch state**

```bash
cd /var/tgsc
git status
git log main --oneline | head -5
```

Expected: working tree clean (or only the already-merged b6c7d8e9f0a1 account-cascade migration), `main` includes commit `3975323 docs(plan): group-AI-sales Phase 1 implementation plan`.

If working tree is dirty with unrelated changes, stash them. If `main` is missing recent commits, `git fetch origin && git pull --ff-only`.

- [ ] **Step 0.2: Create feature branch**

```bash
cd /var/tgsc
git checkout main
git pull --ff-only
git checkout -b feat/llm-safety-stack
```

- [ ] **Step 0.3: Baseline test run**

```bash
docker exec -w /app tgsc-backend-1 pytest tests/ -x --tb=short 2>&1 | tail -20
```

Expected: existing suite passes. Record any pre-existing failures and skip them; don't fix unrelated red tests in this plan.

- [ ] **Step 0.4: Confirm DeepSeek API access exists**

Ask the user to obtain a DeepSeek API key from <https://platform.deepseek.com> if not already in `1Password` / project secrets. Set in `.env` as `DEEPSEEK_API_KEY=...`. STOP and prompt user before continuing if the key is not available — Phase 1 cannot proceed without it.

---

# Phase 1 (P0) — L0 Blacklist + DeepSeek Provider + qa_extract Switch

**Goal:** Stop the largest bleed within 1 day. After this phase: qa_extract no longer touches Vertex, and the most explicit red-line keywords are blocked before any LLM call.

## Task 1.1: L0 Keyword Blacklist Module

**Files:**
- Create: `backend/app/services/safety/__init__.py`
- Create: `backend/app/services/safety/blacklist.py`
- Create: `backend/app/data/blacklist/google_aup_critical.txt`
- Create: `backend/app/data/blacklist/csam_zh.txt`
- Create: `backend/app/data/blacklist/csam_en.txt`
- Create: `backend/app/data/blacklist/political_zh.txt`
- Create: `backend/tests/test_safety_blacklist.py`

- [ ] **Step 1.1.1: Seed blacklist files**

Create `/var/tgsc/backend/app/data/blacklist/google_aup_critical.txt`:

```
# Google Generative AI AUP — absolute red lines (case-insensitive, substring match)
# Reference: https://policies.google.com/terms/generative-ai/use-policy
# Format: one keyword/phrase per line; lines starting with # are comments.
# Keep this list small (<200 entries) — high precision > recall. L1 handles the long tail.

# CSAM (explicit, English)
child porn
cp video
minor sex

# Violent extremism / terror plotting
how to make c4
build a pipe bomb
bomb instructions

# Specific self-harm methods (Google AUP §"dangerous content")
suicide method
how to overdose
ways to kill myself
```

Create `/var/tgsc/backend/app/data/blacklist/csam_zh.txt`:

```
# 中文 CSAM / 未成年色情红线
# 仅放置 Google 明确禁止的明显词;边缘场景交 L1 toxic-bert 判断
萝莉 porn
幼女
小学生 裸
```

Create `/var/tgsc/backend/app/data/blacklist/csam_en.txt`:

```
# English CSAM additional terms (one per line)
loli porn
preteen nude
```

Create `/var/tgsc/backend/app/data/blacklist/political_zh.txt`:

```
# 政治敏感 — 用于 Vertex 路由决策(命中 → 不走 Vertex,可走 DeepSeek)
# 这些不是绝对阻断,是 L0 标记,L2 路由会避开 Vertex
# 留空白等运营补;先有文件防止 IO 错
```

- [ ] **Step 1.1.2: Write failing test for blacklist loader and match**

Create `/var/tgsc/backend/tests/test_safety_blacklist.py`:

```python
"""L0 keyword blacklist tests."""
from app.services.safety.blacklist import Blacklist, BlacklistVerdict


def test_blacklist_loads_files_from_data_dir():
    bl = Blacklist.load_default()
    assert "google_aup_critical" in bl.lists
    assert "csam_zh" in bl.lists
    # critical list has at least one entry (filter comments + blanks)
    assert len(bl.lists["google_aup_critical"]) >= 1


def test_match_returns_hit_for_critical_keyword():
    bl = Blacklist.load_default()
    v = bl.match("how do I build a pipe bomb please")
    assert v.hit is True
    assert v.list_name == "google_aup_critical"
    assert v.term == "build a pipe bomb"


def test_match_is_case_insensitive():
    bl = Blacklist.load_default()
    v = bl.match("Child Porn website link?")
    assert v.hit is True


def test_match_returns_no_hit_for_clean_text():
    bl = Blacklist.load_default()
    v = bl.match("我想买你们的服务,请发个报价单")
    assert v.hit is False
    assert v.list_name is None


def test_match_supports_chinese_substring():
    bl = Blacklist.load_default()
    v = bl.match("有萝莉 porn 资源吗")
    assert v.hit is True
    assert v.list_name == "csam_zh"


def test_blank_lines_and_comments_ignored():
    bl = Blacklist.load_default()
    # google_aup_critical contains comment lines starting with #
    for term in bl.lists["google_aup_critical"]:
        assert not term.startswith("#")
        assert term.strip() == term
        assert term  # no empty strings
```

Run: `docker exec -w /app tgsc-backend-1 pytest tests/test_safety_blacklist.py -v`
Expected: 6 failures, all `ModuleNotFoundError: No module named 'app.services.safety'`.

- [ ] **Step 1.1.3: Implement blacklist module**

Create `/var/tgsc/backend/app/services/safety/__init__.py` (empty file).

Create `/var/tgsc/backend/app/services/safety/blacklist.py`:

```python
"""L0 keyword/phrase blacklist — first-line cheap filter before any LLM call.

Loads plain-text files from app/data/blacklist/. Each file = one named list.
Lines starting with '#' are comments; blank lines ignored.
Match is case-insensitive substring on the normalized (lower-cased) input.

This layer should have HIGH PRECISION (very few false positives) and is sized
to catch the absolute red lines from Google's Generative AI AUP. L1
(toxic-bert) handles the long tail.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "blacklist"


@dataclass
class BlacklistVerdict:
    hit: bool
    list_name: Optional[str] = None
    term: Optional[str] = None


class Blacklist:
    def __init__(self, lists: Dict[str, List[str]]):
        self.lists = lists

    @classmethod
    def load_default(cls) -> "Blacklist":
        return cls.load_from_dir(DEFAULT_DATA_DIR)

    @classmethod
    def load_from_dir(cls, data_dir: Path) -> "Blacklist":
        lists: Dict[str, List[str]] = {}
        if not data_dir.exists():
            return cls(lists)
        for path in sorted(data_dir.glob("*.txt")):
            terms: List[str] = []
            for raw in path.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                terms.append(line.lower())
            lists[path.stem] = terms
        return cls(lists)

    def match(self, text: str) -> BlacklistVerdict:
        if not text:
            return BlacklistVerdict(hit=False)
        haystack = text.lower()
        for list_name, terms in self.lists.items():
            for term in terms:
                if term in haystack:
                    return BlacklistVerdict(hit=True, list_name=list_name, term=term)
        return BlacklistVerdict(hit=False)
```

Run: `docker exec -w /app tgsc-backend-1 pytest tests/test_safety_blacklist.py -v`
Expected: all 6 tests pass.

- [ ] **Step 1.1.4: Commit**

```bash
cd /var/tgsc
git add backend/app/services/safety/__init__.py \
        backend/app/services/safety/blacklist.py \
        backend/app/data/blacklist/ \
        backend/tests/test_safety_blacklist.py
git commit -m "feat(safety): add L0 keyword blacklist module + seed lists"
```

---

## Task 1.2: DeepSeek AIConfig Row + Smoke Test

DeepSeek is OpenAI-compatible — already supported by `LLMService._init_openai` (`llm.py:118-133`). We just need an `AIConfig` row pointing at it. We seed via a small script (not a migration — config is per-environment) and verify with a unit test.

**Files:**
- Create: `backend/scripts/seed_deepseek_config.py`
- Create: `backend/tests/test_qa_extract_uses_deepseek.py`

- [ ] **Step 1.2.1: Write seed script**

Create `/var/tgsc/backend/scripts/seed_deepseek_config.py`:

```python
"""Seed an AIConfig row for DeepSeek-V3.

Idempotent — running twice updates the existing row by name.
Reads DEEPSEEK_API_KEY from environment (must be set).

Usage:
    docker exec -e DEEPSEEK_API_KEY=sk-... tgsc-backend-1 python scripts/seed_deepseek_config.py
"""
import os
import sys
from sqlmodel import Session, select

from app.core.db import engine
from app.models.ai_config import AIConfig


CONFIG_NAME = "DeepSeek-V3 (safety fallback)"
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
DEEPSEEK_MODEL = "deepseek-chat"


def main() -> int:
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("ERROR: DEEPSEEK_API_KEY env var not set", file=sys.stderr)
        return 1

    with Session(engine) as session:
        existing = session.exec(
            select(AIConfig).where(AIConfig.name == CONFIG_NAME)
        ).first()

        if existing:
            existing.api_key = api_key
            existing.provider = "deepseek"
            existing.model = DEEPSEEK_MODEL
            existing.base_url = DEEPSEEK_BASE_URL
            existing.is_active = True
            session.add(existing)
            print(f"Updated AIConfig id={existing.id} '{CONFIG_NAME}'")
        else:
            cfg = AIConfig(
                name=CONFIG_NAME,
                provider="deepseek",
                model=DEEPSEEK_MODEL,
                api_key=api_key,
                base_url=DEEPSEEK_BASE_URL,
                is_active=True,
                is_default=False,
            )
            session.add(cfg)
            session.commit()
            session.refresh(cfg)
            print(f"Created AIConfig id={cfg.id} '{CONFIG_NAME}'")

        session.commit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 1.2.2: Run seed script**

```bash
docker exec -e DEEPSEEK_API_KEY=$(grep ^DEEPSEEK_API_KEY /var/tgsc/.env | cut -d= -f2-) \
  -w /app tgsc-backend-1 python scripts/seed_deepseek_config.py
```

Expected: `Created AIConfig id=N 'DeepSeek-V3 (safety fallback)'`. Note the `id` value — call it `DEEPSEEK_CONFIG_ID` in subsequent steps.

- [ ] **Step 1.2.3: Smoke test DeepSeek round-trip**

```bash
docker exec -w /app tgsc-backend-1 python -c "
import asyncio
from sqlmodel import Session
from app.core.db import engine
from app.services.llm import LLMService

async def main():
    with Session(engine) as s:
        # Use config_id from previous step; substitute the printed id
        from sqlmodel import select
        from app.models.ai_config import AIConfig
        cfg = s.exec(select(AIConfig).where(AIConfig.name == 'DeepSeek-V3 (safety fallback)')).first()
        assert cfg, 'config not found'
        llm = LLMService(s, config_id=cfg.id)
        out = await llm.get_response('Reply with the single word OK.', source='smoke_test_deepseek')
        print('Response:', repr(out))
        assert out and 'OK' in out.upper(), f'unexpected response: {out}'

asyncio.run(main())
"
```

Expected: `Response: 'OK'` (or similar containing "OK"). If 401/403 → API key wrong, fix `.env` and re-run Step 1.2.2.

- [ ] **Step 1.2.4: Verify usage record landed**

```bash
docker compose exec -T db psql -U tgsc_user -d tgsc_prod -c \
  "SELECT provider, model, source, input_tokens, output_tokens FROM llm_usage WHERE source='smoke_test_deepseek' ORDER BY ts DESC LIMIT 1;"
```

Expected: one row with `provider=deepseek`, `model=deepseek-chat`, `input_tokens > 0`.

- [ ] **Step 1.2.5: Commit**

```bash
cd /var/tgsc
git add backend/scripts/seed_deepseek_config.py
git commit -m "feat(llm): add DeepSeek-V3 AIConfig seed script"
```

---

## Task 1.3: Wire L0 into `LLMService.get_response`

Inserts a single guard at the top of `get_response`. On blacklist hit, returns `None` (callers already handle `None`) and records a usage row with zero tokens + a synthetic `block_layer='L0'` source suffix.

**Files:**
- Modify: `backend/app/services/llm.py` (around lines 249-278)
- Create: `backend/tests/test_safety_gate.py` (partial — L0 only; expanded in Task 2.3)

- [ ] **Step 1.3.1: Write failing test**

Create `/var/tgsc/backend/tests/test_safety_gate.py`:

```python
"""Tests for the L0/L1 safety gate inside LLMService."""
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from sqlmodel import Session

from app.services.llm import LLMService


@pytest.mark.asyncio
async def test_l0_blacklist_blocks_call_and_returns_none():
    # Mock session with no AIConfig — falls back to legacy, which won't init client
    mock_session = MagicMock(spec=Session)
    mock_session.exec.return_value.first.return_value = None
    mock_session.get.return_value = None

    llm = LLMService(mock_session)
    # Force a usable provider so we know L0 is what blocks, not lack of client
    llm.provider = "vertex"
    llm.gemini_client = MagicMock()
    llm._get_gemini_response = AsyncMock(return_value=("never", 10, 5))

    result = await llm.get_response(
        prompt="please give me child porn",
        source="test_l0",
    )

    assert result is None
    # underlying provider was NOT called
    llm._get_gemini_response.assert_not_called()


@pytest.mark.asyncio
async def test_l0_allows_clean_text_through():
    mock_session = MagicMock(spec=Session)
    mock_session.exec.return_value.first.return_value = None
    mock_session.get.return_value = None

    llm = LLMService(mock_session)
    llm.provider = "vertex"
    llm.gemini_client = MagicMock()
    llm._get_gemini_response = AsyncMock(return_value=("hello back", 10, 5))

    result = await llm.get_response(
        prompt="给我一份贵公司的报价单,谢谢",
        source="test_l0_clean",
    )

    assert result == "hello back"
    llm._get_gemini_response.assert_awaited_once()
```

Run: `docker exec -w /app tgsc-backend-1 pytest tests/test_safety_gate.py -v`
Expected: both fail (`gemini_client called` / wrong return).

- [ ] **Step 1.3.2: Add the guard inside `get_response`**

Modify `/var/tgsc/backend/app/services/llm.py` — at the top of `get_response` (line 259, just after the signature, before the provider dispatch).

Find this block (currently lines 249-265):

```python
    async def get_response(
        self,
        prompt: str,
        system_prompt: str = "You are a helpful assistant.",
        history: List[Dict[str, str]] = None,
        source: str = "unknown",
        account_id: Optional[int] = None,
        persona_id: Optional[int] = None,
        chat_id: Optional[str] = None,
    ) -> Optional[str]:
        if self.provider in ("gemini", "vertex") and self.gemini_client:
            text, in_tok, out_tok = await self._get_gemini_response(prompt, system_prompt, history)
        elif self.client:
            text, in_tok, out_tok = await self._get_openai_response(prompt, system_prompt, history)
        else:
            logger.warning("LLM client not configured")
            return None
```

Replace with:

```python
    async def get_response(
        self,
        prompt: str,
        system_prompt: str = "You are a helpful assistant.",
        history: List[Dict[str, str]] = None,
        source: str = "unknown",
        account_id: Optional[int] = None,
        persona_id: Optional[int] = None,
        chat_id: Optional[str] = None,
    ) -> Optional[str]:
        # L0: keyword blacklist guard — must run before any provider dispatch.
        # See [[project-llm-safety-architecture]] for the layered design.
        from app.services.safety.blacklist import Blacklist
        verdict = _BLACKLIST.match(prompt)
        if verdict.hit:
            logger.warning(
                f"L0 blacklist hit: list={verdict.list_name} term={verdict.term!r} "
                f"source={source} account_id={account_id} provider={self.provider}"
            )
            record_usage(
                provider=self.provider,
                model=self.model,
                source=f"{source}:blocked_L0",
                input_tokens=0,
                output_tokens=0,
                account_id=account_id,
                persona_id=persona_id,
                chat_id=chat_id,
            )
            return None

        if self.provider in ("gemini", "vertex") and self.gemini_client:
            text, in_tok, out_tok = await self._get_gemini_response(prompt, system_prompt, history)
        elif self.client:
            text, in_tok, out_tok = await self._get_openai_response(prompt, system_prompt, history)
        else:
            logger.warning("LLM client not configured")
            return None
```

Then add a module-level cached blacklist instance at the top of `llm.py`, just below the existing imports (around line 30):

```python
# Module-level cached L0 blacklist (loaded once per process).
from app.services.safety.blacklist import Blacklist as _Blacklist
_BLACKLIST = _Blacklist.load_default()
```

Run: `docker exec -w /app tgsc-backend-1 pytest tests/test_safety_gate.py tests/test_safety_blacklist.py -v`
Expected: all tests pass.

- [ ] **Step 1.3.3: Also guard `analyze_intent`**

Find `analyze_intent` in `llm.py` (search for `async def analyze_intent`). At its start, add the same L0 check (use `message` as the prompt input). Use a helper to avoid duplication.

Add this helper just below the `_BLACKLIST` line:

```python
def _l0_check(prompt: str, source: str, model: str, provider: str,
              account_id, persona_id, chat_id) -> bool:
    """Returns True if L0 blocks; logs + records usage row when blocked."""
    verdict = _BLACKLIST.match(prompt)
    if not verdict.hit:
        return False
    logger.warning(
        f"L0 blacklist hit: list={verdict.list_name} term={verdict.term!r} "
        f"source={source} account_id={account_id} provider={provider}"
    )
    record_usage(
        provider=provider, model=model, source=f"{source}:blocked_L0",
        input_tokens=0, output_tokens=0,
        account_id=account_id, persona_id=persona_id, chat_id=chat_id,
    )
    return True
```

Replace the inline L0 block from Step 1.3.2 with a call to this helper:

```python
        if _l0_check(prompt, source, self.model, self.provider,
                     account_id, persona_id, chat_id):
            return None
```

Then at the top of `analyze_intent`, after its signature, before the provider dispatch:

```python
        if _l0_check(message, source, self.model, self.provider,
                     account_id, None, chat_id):
            return None
```

Run: `docker exec -w /app tgsc-backend-1 pytest tests/test_safety_gate.py -v`
Expected: still passing.

- [ ] **Step 1.3.4: Commit**

```bash
cd /var/tgsc
git add backend/app/services/llm.py backend/tests/test_safety_gate.py
git commit -m "feat(safety): wire L0 blacklist guard into LLMService.get_response + analyze_intent"
```

---

## Task 1.4: Switch `qa_extract` to DeepSeek (force, ignore default config)

**Files:**
- Modify: `backend/app/tasks/knowledge_tasks.py` (around line 344)
- Modify: `backend/app/services/qa_extractor.py` (no logic change — just verify it doesn't pin a provider)
- Create: `backend/tests/test_qa_extract_uses_deepseek.py`

- [ ] **Step 1.4.1: Write failing test**

Create `/var/tgsc/backend/tests/test_qa_extract_uses_deepseek.py`:

```python
"""qa_extract must always run via DeepSeek to avoid Vertex policy bans.

See: memory feedback-qa-extraction-vertex-ban + project-llm-safety-architecture.
"""
from unittest.mock import patch, MagicMock

import pytest
from sqlmodel import Session

from app.tasks.knowledge_tasks import _resolve_qa_extract_config_id


def test_resolves_to_deepseek_config_id_when_present():
    mock_session = MagicMock(spec=Session)
    fake_cfg = MagicMock()
    fake_cfg.id = 42
    fake_cfg.name = "DeepSeek-V3 (safety fallback)"
    mock_session.exec.return_value.first.return_value = fake_cfg

    cfg_id = _resolve_qa_extract_config_id(mock_session)
    assert cfg_id == 42


def test_raises_when_deepseek_config_missing():
    mock_session = MagicMock(spec=Session)
    mock_session.exec.return_value.first.return_value = None
    with pytest.raises(RuntimeError, match="DeepSeek"):
        _resolve_qa_extract_config_id(mock_session)
```

Run: `docker exec -w /app tgsc-backend-1 pytest tests/test_qa_extract_uses_deepseek.py -v`
Expected: 2 failures, `ImportError: cannot import name '_resolve_qa_extract_config_id'`.

- [ ] **Step 1.4.2: Add resolver + wire it into `extract_qa_from_messages`**

In `/var/tgsc/backend/app/tasks/knowledge_tasks.py`, find line ~344 where `LLMService(db_session=db)` is instantiated (inside `extract_qa_from_messages`).

Add this helper near the top of the file (after the imports):

```python
from app.models.ai_config import AIConfig

QA_EXTRACT_CONFIG_NAME = "DeepSeek-V3 (safety fallback)"


def _resolve_qa_extract_config_id(session) -> int:
    """qa_extract MUST run on DeepSeek — Vertex was banned over group content.

    Raises RuntimeError if the DeepSeek config row is missing (operator must
    run scripts/seed_deepseek_config.py before any qa_extract run).
    """
    cfg = session.exec(
        select(AIConfig).where(AIConfig.name == QA_EXTRACT_CONFIG_NAME)
    ).first()
    if cfg is None:
        raise RuntimeError(
            f"DeepSeek AIConfig '{QA_EXTRACT_CONFIG_NAME}' missing — "
            f"run scripts/seed_deepseek_config.py before qa_extract."
        )
    return cfg.id
```

If `select` is not already imported in this file, ensure `from sqlmodel import select` is present (it should be already — check around line 19).

Then change the instantiation. Find:

```python
                llm = LLMService(db_session=db)
```

Replace with:

```python
                config_id = _resolve_qa_extract_config_id(db)
                llm = LLMService(db_session=db, config_id=config_id)
                logger.info(f"qa_extract using AIConfig id={config_id} (DeepSeek, anti-Vertex-ban)")
```

Run: `docker exec -w /app tgsc-backend-1 pytest tests/test_qa_extract_uses_deepseek.py -v`
Expected: both pass.

- [ ] **Step 1.4.3: End-to-end smoke**

Run a tiny QA extraction over 2 clean messages to verify the integration end-to-end:

```bash
docker exec -w /app tgsc-backend-1 python -c "
from sqlmodel import Session, select
from app.core.db import engine
from app.models.group_message import GroupMessage
from app.services.qa_extractor import extract_qa_from_window
from app.services.llm import LLMService
from app.tasks.knowledge_tasks import _resolve_qa_extract_config_id

with Session(engine) as s:
    cfg_id = _resolve_qa_extract_config_id(s)
    llm = LLMService(s, config_id=cfg_id)
    msgs = s.exec(select(GroupMessage).where(GroupMessage.qa_extracted==True).limit(5)).all()
    if not msgs:
        print('No qa_extracted messages available — skipping smoke')
    else:
        import asyncio
        out = asyncio.run(extract_qa_from_window(llm, 'smoke', 'supergroup', msgs))
        print(f'Got {len(out)} Q&A pairs via DeepSeek')
"
```

Expected: prints `Got N Q&A pairs via DeepSeek` (or "No qa_extracted messages" — also OK). Then verify in DB:

```bash
docker compose exec -T db psql -U tgsc_user -d tgsc_prod -c \
  "SELECT provider, source, COUNT(*) FROM llm_usage WHERE ts > NOW() - INTERVAL '5 minutes' AND source='qa_extract' GROUP BY provider, source;"
```

Expected: `provider=deepseek` (NOT vertex).

- [ ] **Step 1.4.4: Commit**

```bash
cd /var/tgsc
git add backend/app/tasks/knowledge_tasks.py backend/tests/test_qa_extract_uses_deepseek.py
git commit -m "feat(safety): force qa_extract through DeepSeek (anti-Vertex-ban)"
```

> **Note for Phase 3:** After this task, `qa_extract` pipeline is `L0 → DeepSeek`. L1 (toxic-bert) and the explicit router decision land in Phase 2/3; `LLMService.get_response` already enforces L0 from Task 1.3, so red-line content is rejected before reaching DeepSeek. This means a portion of the 632k unprocessed group_messages will silently return `None` from extraction — that's by design. Do not re-run historical QA backfill until Phase 3 ships routing visibility.

---

## Task 1.5: Phase 1 checkpoint

- [ ] **Step 1.5.1: Run full test suite**

```bash
docker exec -w /app tgsc-backend-1 pytest tests/ -x --tb=short 2>&1 | tail -20
```

Expected: all pass (or the pre-existing baseline failures from Step 0.3, no new ones).

- [ ] **Step 1.5.2: Manual integration check on dev**

In Postgres:

```bash
docker compose exec -T db psql -U tgsc_user -d tgsc_prod -c \
  "SELECT source, COUNT(*) FROM llm_usage WHERE ts > NOW() - INTERVAL '1 hour' GROUP BY source ORDER BY 2 DESC;"
```

Confirm no `vertex` rows show up under `qa_extract` after the cutover (only `deepseek`).

- [ ] **Step 1.5.3: Push branch + open draft PR**

```bash
cd /var/tgsc
git push -u origin feat/llm-safety-stack
gh pr create --draft --title "feat(safety): LLM safety stack — Phase 1 (L0 + DeepSeek + qa_extract switch)" \
  --body "$(cat <<'EOF'
## Summary

Phase 1 of the 5-layer LLM safety stack. See memory entry
`project-llm-safety-architecture` for full design.

- L0 keyword blacklist module + 4 seed lists
- `LLMService.get_response` and `.analyze_intent` guarded by L0
- DeepSeek-V3 AIConfig seeder script
- `qa_extract` task now forced through DeepSeek (anti-Vertex-ban)

## Test plan
- [ ] L0 blacklist hit → returns None, no provider call
- [ ] L0 clean text → reaches provider normally
- [ ] qa_extract resolver returns DeepSeek config id; raises if missing
- [ ] Smoke: DeepSeek round-trip via LLMService.get_response works
- [ ] llm_usage rows for qa_extract show provider=deepseek

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Phase 1 ends here. **Do not merge to main yet** — wait until Phase 2/3 also land so the full stack ships together.

---

# Phase 2 (P1a) — L1 Local toxic-bert Moderation

**Goal:** Add a local ONNX-based toxic content scorer. Output is a multi-dim score dict (sexual/violence/hate/self-harm/political), feeding the L2 router.

## Task 2.1: Add toxic-bert ONNX wrapper

We use HuggingFace `unitary/multilingual-toxic-xlm-roberta` exported to ONNX, served via `onnxruntime` (already installed transitively by fastembed in [[project-reranker-state]]). Loading is lazy and cached at module level.

**Files:**
- Create: `backend/app/services/safety/moderation.py`
- Create: `backend/tests/test_safety_moderation.py`
- Modify: `backend/requirements.txt` (pin model)

- [ ] **Step 2.1.1: Confirm onnxruntime is available**

```bash
docker exec -w /app tgsc-backend-1 python -c "import onnxruntime; print(onnxruntime.__version__)"
```

Expected: a version string (e.g., `1.17.0`). If `ModuleNotFoundError`, add `onnxruntime>=1.17` to `requirements.txt` and rebuild backend image. (Likely already present.)

- [ ] **Step 2.1.2: Write failing test (mocked model)**

Create `/var/tgsc/backend/tests/test_safety_moderation.py`:

```python
"""Tests for the L1 toxic-bert moderation wrapper.

Model inference is mocked — these tests verify the wrapper logic, not
the model accuracy. Accuracy is validated separately via a sample-set
calibration step in operations docs.
"""
from unittest.mock import patch, MagicMock
import numpy as np
import pytest

from app.services.safety.moderation import (
    Moderator, ModerationScore, ModerationVerdict, DEFAULT_THRESHOLDS,
)


def test_score_dict_has_expected_dims():
    s = ModerationScore(sexual=0.1, violence=0.0, hate=0.2,
                        self_harm=0.0, political=0.05)
    d = s.to_dict()
    assert set(d.keys()) == {"sexual", "violence", "hate", "self_harm", "political"}


def test_max_dim_returns_strongest_signal():
    s = ModerationScore(sexual=0.1, violence=0.8, hate=0.2,
                        self_harm=0.0, political=0.05)
    name, val = s.max_dim()
    assert name == "violence"
    assert val == 0.8


def test_classify_clean_text_returns_clean():
    mod = Moderator()
    with patch.object(mod, "_score", return_value=ModerationScore(
        sexual=0.05, violence=0.02, hate=0.01, self_harm=0.0, political=0.0
    )):
        v = mod.evaluate("买点啥都行,给我个报价")
    assert v.tier == "clean"
    assert v.blocked is False


def test_classify_grey_routes_away_from_vertex():
    mod = Moderator()
    with patch.object(mod, "_score", return_value=ModerationScore(
        sexual=0.45, violence=0.0, hate=0.0, self_harm=0.0, political=0.0
    )):
        v = mod.evaluate("borderline sexual content")
    assert v.tier == "grey"
    assert v.blocked is False
    assert v.avoid_vertex is True


def test_classify_red_blocks():
    mod = Moderator()
    with patch.object(mod, "_score", return_value=ModerationScore(
        sexual=0.95, violence=0.0, hate=0.0, self_harm=0.0, political=0.0
    )):
        v = mod.evaluate("very explicit")
    assert v.tier == "red"
    assert v.blocked is True


def test_thresholds_overridable():
    custom = {"sexual_grey": 0.3, "sexual_red": 0.5}
    mod = Moderator(thresholds={**DEFAULT_THRESHOLDS, **custom})
    with patch.object(mod, "_score", return_value=ModerationScore(
        sexual=0.4, violence=0.0, hate=0.0, self_harm=0.0, political=0.0
    )):
        v = mod.evaluate("borderline")
    assert v.tier == "grey"
```

Run: `docker exec -w /app tgsc-backend-1 pytest tests/test_safety_moderation.py -v`
Expected: 5 failures, `ImportError: cannot import name 'Moderator'`.

- [ ] **Step 2.1.3: Implement moderation wrapper**

Create `/var/tgsc/backend/app/services/safety/moderation.py`:

```python
"""L1 local moderation — multi-dim toxic content scoring via ONNX.

Model: `unitary/multilingual-toxic-xlm-roberta` (XLM-R based, covers EN/ZH/RU).
Inference: onnxruntime, CPU. Latency target <20ms per call on a 4-core host.

The wrapper is lazy-loading and cached at module level — first call does the
download + warmup; subsequent calls reuse the session.

Public surface:
    Moderator()                       # default thresholds
    Moderator(thresholds=overrides)   # operator-tuned
    moderator.evaluate(text) -> ModerationVerdict
"""
from __future__ import annotations
import logging
import os
import threading
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Tunable thresholds. Each dimension has _grey (route away from Vertex) and
# _red (refuse entirely). Operator can override via SystemConfig — see Task 4.2.
DEFAULT_THRESHOLDS: Dict[str, float] = {
    "sexual_grey": 0.40,
    "sexual_red": 0.85,
    "violence_grey": 0.50,
    "violence_red": 0.85,
    "hate_grey": 0.40,
    "hate_red": 0.80,
    "self_harm_grey": 0.30,
    "self_harm_red": 0.70,
    "political_grey": 0.50,  # political content: only route away from Vertex, no red tier
    "political_red": 1.01,   # effectively disabled
}

MODEL_NAME = os.environ.get("TOXIC_MODEL_NAME", "unitary/multilingual-toxic-xlm-roberta")
MODEL_CACHE_DIR = Path(os.environ.get("TOXIC_MODEL_CACHE", "/app/.cache/toxic"))


@dataclass
class ModerationScore:
    sexual: float
    violence: float
    hate: float
    self_harm: float
    political: float

    def to_dict(self) -> Dict[str, float]:
        return asdict(self)

    def max_dim(self) -> Tuple[str, float]:
        d = self.to_dict()
        name = max(d, key=d.get)
        return name, d[name]


@dataclass
class ModerationVerdict:
    score: ModerationScore
    tier: str           # "clean" | "grey" | "red"
    blocked: bool       # True iff tier == "red"
    avoid_vertex: bool  # True iff tier in {"grey", "red"} OR political_grey breached
    dim_triggered: Optional[str] = None  # which dim pushed it past threshold


_MODEL_LOCK = threading.Lock()
_MODEL_SESSION = None
_MODEL_TOKENIZER = None


def _get_session():
    """Lazy-load onnxruntime session + tokenizer. Thread-safe singleton."""
    global _MODEL_SESSION, _MODEL_TOKENIZER
    if _MODEL_SESSION is not None:
        return _MODEL_SESSION, _MODEL_TOKENIZER
    with _MODEL_LOCK:
        if _MODEL_SESSION is not None:
            return _MODEL_SESSION, _MODEL_TOKENIZER
        import onnxruntime as ort
        from transformers import AutoTokenizer
        from huggingface_hub import snapshot_download

        MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        local_path = snapshot_download(
            repo_id=MODEL_NAME, cache_dir=str(MODEL_CACHE_DIR),
            allow_patterns=["*.onnx", "tokenizer*", "*.json"],
        )
        onnx_files = list(Path(local_path).rglob("*.onnx"))
        if not onnx_files:
            raise RuntimeError(f"No .onnx file found under {local_path}")
        sess = ort.InferenceSession(
            str(onnx_files[0]),
            providers=["CPUExecutionProvider"],
        )
        tok = AutoTokenizer.from_pretrained(local_path)
        _MODEL_SESSION, _MODEL_TOKENIZER = sess, tok
        logger.info(f"Toxic-bert loaded from {local_path}, onnx={onnx_files[0].name}")
    return _MODEL_SESSION, _MODEL_TOKENIZER


class Moderator:
    def __init__(self, thresholds: Optional[Dict[str, float]] = None):
        self.thresholds = dict(DEFAULT_THRESHOLDS)
        if thresholds:
            self.thresholds.update(thresholds)

    def _score(self, text: str) -> ModerationScore:
        """Run inference; map model output dims → our 5-dim schema.

        unitary/multilingual-toxic-xlm-roberta outputs 6 labels:
        ['toxic', 'severe_toxic', 'obscene', 'threat', 'insult', 'identity_hate']
        We map:
            sexual    ← obscene
            violence  ← threat
            hate      ← max(insult, identity_hate)
            self_harm ← severe_toxic   (proxy; full model not separated)
            political ← 0.0            (toxic-bert has no political dim; use blacklist for now)
        """
        import numpy as np
        sess, tok = _get_session()
        encoded = tok(text, padding=True, truncation=True, max_length=256,
                      return_tensors="np")
        feeds = {k: encoded[k] for k in encoded if k in {"input_ids", "attention_mask"}}
        outputs = sess.run(None, feeds)
        logits = outputs[0][0]  # shape (6,)
        probs = 1.0 / (1.0 + np.exp(-logits))  # sigmoid
        return ModerationScore(
            sexual=float(probs[2]),
            violence=float(probs[3]),
            hate=float(max(probs[4], probs[5])),
            self_harm=float(probs[1]),
            political=0.0,
        )

    def evaluate(self, text: str) -> ModerationVerdict:
        if not text:
            return ModerationVerdict(
                score=ModerationScore(0.0, 0.0, 0.0, 0.0, 0.0),
                tier="clean", blocked=False, avoid_vertex=False,
            )
        score = self._score(text)
        tier = "clean"
        dim = None
        avoid_vertex = False

        for dim_name in ("sexual", "violence", "hate", "self_harm", "political"):
            val = getattr(score, dim_name)
            red_th = self.thresholds[f"{dim_name}_red"]
            grey_th = self.thresholds[f"{dim_name}_grey"]
            if val >= red_th:
                tier = "red"
                dim = dim_name
                avoid_vertex = True
                break
            if val >= grey_th and tier != "grey":
                tier = "grey"
                dim = dim_name
                avoid_vertex = True

        return ModerationVerdict(
            score=score, tier=tier,
            blocked=(tier == "red"),
            avoid_vertex=avoid_vertex,
            dim_triggered=dim,
        )
```

Run: `docker exec -w /app tgsc-backend-1 pytest tests/test_safety_moderation.py -v`
Expected: all 5 pass (the model itself is mocked, so no download is triggered).

- [ ] **Step 2.1.4: One-time model warmup**

Pre-download and cache the model so first prod request isn't slow:

```bash
docker exec -w /app tgsc-backend-1 python -c "
from app.services.safety.moderation import _get_session, Moderator
sess, tok = _get_session()
print('Model loaded.')
m = Moderator()
v = m.evaluate('hello world')
print('Verdict:', v.tier, v.score.to_dict())
"
```

Expected: `Model loaded.` (may take 30-60s on first run for download), then a `clean` verdict with low scores. If the model id needs Hugging Face auth, set `HF_TOKEN` env var.

If the `unitary/multilingual-toxic-xlm-roberta` repo doesn't ship ONNX directly, fall back: download safetensors and convert via:

```bash
docker exec -w /app tgsc-backend-1 python -m transformers.onnx --model=unitary/multilingual-toxic-xlm-roberta --feature=sequence-classification /tmp/toxic_onnx
```

Then set `TOXIC_MODEL_CACHE=/tmp/toxic_onnx` and re-run the warmup. Document the chosen path in commit message.

- [ ] **Step 2.1.5: Commit**

```bash
cd /var/tgsc
git add backend/app/services/safety/moderation.py backend/tests/test_safety_moderation.py
git commit -m "feat(safety): add L1 toxic-bert moderation wrapper (ONNX, lazy-loaded)"
```

---

## Task 2.2: Combined SafetyGate (L0 + L1)

Replace the inline L0-only check in `llm.py` with a unified `SafetyGate` that runs L0 first, then L1, and returns a `SafetyVerdict` covering both layers.

**Files:**
- Create: `backend/app/services/safety/gate.py`
- Modify: `backend/app/services/llm.py` (replace `_l0_check` with `_safety_check`)
- Modify: `backend/tests/test_safety_gate.py` (add L1 cases)

- [ ] **Step 2.2.1: Implement SafetyGate**

Create `/var/tgsc/backend/app/services/safety/gate.py`:

```python
"""Combined L0 + L1 gate. Single chokepoint in front of every LLM call."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from app.services.safety.blacklist import Blacklist
from app.services.safety.moderation import Moderator, ModerationVerdict


@dataclass
class SafetyVerdict:
    blocked: bool
    block_layer: Optional[str]      # "L0" | "L1" | None
    blacklist_list: Optional[str]   # only set when block_layer == "L0"
    blacklist_term: Optional[str]
    moderation: Optional[ModerationVerdict]  # set whenever L1 ran
    avoid_vertex: bool              # True iff L0 hit OR L1 grey/red

    @property
    def moderation_score(self) -> Optional[float]:
        if self.moderation is None:
            return None
        _, val = self.moderation.score.max_dim()
        return val

    @property
    def max_dim(self) -> Optional[str]:
        if self.moderation is None:
            return None
        name, _ = self.moderation.score.max_dim()
        return name


class SafetyGate:
    def __init__(self, blacklist: Optional[Blacklist] = None,
                 moderator: Optional[Moderator] = None):
        self.blacklist = blacklist or Blacklist.load_default()
        self.moderator = moderator or Moderator()

    def evaluate(self, text: str) -> SafetyVerdict:
        bl = self.blacklist.match(text)
        if bl.hit:
            return SafetyVerdict(
                blocked=True, block_layer="L0",
                blacklist_list=bl.list_name, blacklist_term=bl.term,
                moderation=None, avoid_vertex=True,
            )
        mv = self.moderator.evaluate(text)
        return SafetyVerdict(
            blocked=mv.blocked,
            block_layer=("L1" if mv.blocked else None),
            blacklist_list=None, blacklist_term=None,
            moderation=mv,
            avoid_vertex=mv.avoid_vertex,
        )
```

- [ ] **Step 2.2.2: Replace `_l0_check` in `llm.py`**

In `/var/tgsc/backend/app/services/llm.py`, remove the `_BLACKLIST` import and `_l0_check` helper (added in Task 1.3). Replace with:

```python
from app.services.safety.gate import SafetyGate as _SafetyGate

_GATE = _SafetyGate()


def _safety_check(prompt: str, source: str, model: str, provider: str,
                  account_id, persona_id, chat_id) -> bool:
    """Returns True iff the gate blocked the call. Records usage with metadata."""
    verdict = _GATE.evaluate(prompt)
    if not verdict.blocked:
        return False
    logger.warning(
        f"Safety gate blocked: layer={verdict.block_layer} "
        f"list={verdict.blacklist_list} term={verdict.blacklist_term!r} "
        f"dim={verdict.max_dim} score={verdict.moderation_score} "
        f"source={source} account_id={account_id} provider={provider}"
    )
    record_usage(
        provider=provider, model=model,
        source=f"{source}:blocked_{verdict.block_layer}",
        input_tokens=0, output_tokens=0,
        account_id=account_id, persona_id=persona_id, chat_id=chat_id,
    )
    return True
```

Replace both call sites (`_l0_check(...)`) with `_safety_check(...)`.

- [ ] **Step 2.2.3: Add L1 test cases to `test_safety_gate.py`**

Append to `/var/tgsc/backend/tests/test_safety_gate.py`:

```python
from unittest.mock import patch
from app.services.safety.moderation import ModerationVerdict, ModerationScore


@pytest.mark.asyncio
async def test_l1_red_blocks_call():
    mock_session = MagicMock(spec=Session)
    mock_session.exec.return_value.first.return_value = None
    mock_session.get.return_value = None

    llm = LLMService(mock_session)
    llm.provider = "vertex"
    llm.gemini_client = MagicMock()
    llm._get_gemini_response = AsyncMock(return_value=("never", 10, 5))

    # Patch the module-level gate's moderator to force red
    from app.services.llm import _GATE
    red_score = ModerationScore(sexual=0.99, violence=0.0, hate=0.0,
                                self_harm=0.0, political=0.0)
    red_verdict = ModerationVerdict(
        score=red_score, tier="red",
        blocked=True, avoid_vertex=True, dim_triggered="sexual",
    )
    with patch.object(_GATE.moderator, "evaluate", return_value=red_verdict):
        result = await llm.get_response(prompt="ambiguous text", source="test_l1_red")

    assert result is None
    llm._get_gemini_response.assert_not_called()


@pytest.mark.asyncio
async def test_l1_grey_still_allows_call():
    """Grey tier does NOT block at the gate — it's L2 routing's job to reroute.
    The gate only blocks on red."""
    mock_session = MagicMock(spec=Session)
    mock_session.exec.return_value.first.return_value = None
    mock_session.get.return_value = None

    llm = LLMService(mock_session)
    llm.provider = "vertex"
    llm.gemini_client = MagicMock()
    llm._get_gemini_response = AsyncMock(return_value=("ok", 10, 5))

    from app.services.llm import _GATE
    grey_score = ModerationScore(sexual=0.5, violence=0.0, hate=0.0,
                                 self_harm=0.0, political=0.0)
    grey_verdict = ModerationVerdict(
        score=grey_score, tier="grey",
        blocked=False, avoid_vertex=True, dim_triggered="sexual",
    )
    with patch.object(_GATE.moderator, "evaluate", return_value=grey_verdict):
        result = await llm.get_response(prompt="borderline", source="test_l1_grey")

    assert result == "ok"
    llm._get_gemini_response.assert_awaited_once()
```

Run: `docker exec -w /app tgsc-backend-1 pytest tests/test_safety_gate.py -v`
Expected: all 4 tests pass.

- [ ] **Step 2.2.4: Commit**

```bash
cd /var/tgsc
git add backend/app/services/safety/gate.py backend/app/services/llm.py \
        backend/tests/test_safety_gate.py
git commit -m "feat(safety): unify L0+L1 into SafetyGate chokepoint"
```

---

# Phase 3 (P1b) — L2 Router + Integrate Reply Paths

**Goal:** Make routing decisions explicit. Callers ask `LLMRouter.generate(...)`; the router runs the SafetyGate, picks a provider based on `avoid_vertex`, and dispatches via `LLMService` with the right `config_id`.

## Task 3.1: LLMRouter class

**Files:**
- Create: `backend/app/services/safety/router.py`
- Create: `backend/tests/test_llm_router.py`

- [ ] **Step 3.1.1: Write failing tests**

Create `/var/tgsc/backend/tests/test_llm_router.py`:

```python
"""LLMRouter selects Vertex for clean text, DeepSeek for grey, refuses on red."""
from unittest.mock import patch, MagicMock, AsyncMock
import pytest
from sqlmodel import Session

from app.services.safety.router import LLMRouter, RouteDecision
from app.services.safety.gate import SafetyVerdict
from app.services.safety.moderation import ModerationVerdict, ModerationScore


def _clean_verdict():
    return SafetyVerdict(
        blocked=False, block_layer=None,
        blacklist_list=None, blacklist_term=None,
        moderation=ModerationVerdict(
            score=ModerationScore(0.01, 0.0, 0.0, 0.0, 0.0),
            tier="clean", blocked=False, avoid_vertex=False, dim_triggered=None,
        ),
        avoid_vertex=False,
    )


def _grey_verdict():
    return SafetyVerdict(
        blocked=False, block_layer=None,
        blacklist_list=None, blacklist_term=None,
        moderation=ModerationVerdict(
            score=ModerationScore(0.5, 0.0, 0.0, 0.0, 0.0),
            tier="grey", blocked=False, avoid_vertex=True, dim_triggered="sexual",
        ),
        avoid_vertex=True,
    )


def _red_verdict():
    return SafetyVerdict(
        blocked=True, block_layer="L1",
        blacklist_list=None, blacklist_term=None,
        moderation=ModerationVerdict(
            score=ModerationScore(0.95, 0.0, 0.0, 0.0, 0.0),
            tier="red", blocked=True, avoid_vertex=True, dim_triggered="sexual",
        ),
        avoid_vertex=True,
    )


def test_decide_clean_picks_vertex():
    router = LLMRouter(vertex_config_id=1, deepseek_config_id=2)
    d = router.decide(_clean_verdict())
    assert d.routed_to == "vertex"
    assert d.config_id == 1
    assert d.refuse is False


def test_decide_grey_picks_deepseek():
    router = LLMRouter(vertex_config_id=1, deepseek_config_id=2)
    d = router.decide(_grey_verdict())
    assert d.routed_to == "deepseek"
    assert d.config_id == 2
    assert d.refuse is False


def test_decide_red_refuses():
    router = LLMRouter(vertex_config_id=1, deepseek_config_id=2)
    d = router.decide(_red_verdict())
    assert d.refuse is True
    assert d.routed_to is None
    assert d.config_id is None


@pytest.mark.asyncio
async def test_generate_clean_text_calls_vertex_llmservice():
    mock_session = MagicMock(spec=Session)
    router = LLMRouter(vertex_config_id=1, deepseek_config_id=2)
    with patch("app.services.safety.router._GATE.evaluate",
               return_value=_clean_verdict()), \
         patch("app.services.safety.router.LLMService") as mock_llm_cls:
        mock_llm = mock_llm_cls.return_value
        mock_llm.get_response = AsyncMock(return_value="ok")

        out = await router.generate(mock_session, "hello", source="t1")

        assert out == "ok"
        mock_llm_cls.assert_called_once()
        # config_id arg present
        _, kwargs = mock_llm_cls.call_args
        assert kwargs.get("config_id") == 1


@pytest.mark.asyncio
async def test_generate_red_refuses_without_calling_provider():
    mock_session = MagicMock(spec=Session)
    router = LLMRouter(vertex_config_id=1, deepseek_config_id=2)
    with patch("app.services.safety.router._GATE.evaluate",
               return_value=_red_verdict()), \
         patch("app.services.safety.router.LLMService") as mock_llm_cls:
        out = await router.generate(mock_session, "explicit", source="t2")
    assert out is None
    mock_llm_cls.assert_not_called()
```

Run: `docker exec -w /app tgsc-backend-1 pytest tests/test_llm_router.py -v`
Expected: 5 failures, import errors for `LLMRouter` / `RouteDecision`.

- [ ] **Step 3.1.2: Implement router**

Create `/var/tgsc/backend/app/services/safety/router.py`:

```python
"""L2 routing — given a SafetyVerdict, pick a provider and dispatch.

Public surface:
    router = LLMRouter(vertex_config_id=..., deepseek_config_id=...)
    out = await router.generate(session, prompt, source="...", ...)

The router owns the SafetyGate evaluation step. Callers stop instantiating
LLMService directly — they go through the router. This guarantees the gate
runs and the right config_id is selected.
"""
from __future__ import annotations
import logging
from dataclasses import dataclass
from typing import Optional, List, Dict

from sqlmodel import Session, select

from app.models.ai_config import AIConfig
from app.services.llm import LLMService
from app.services.safety.gate import SafetyGate

logger = logging.getLogger(__name__)

# Shared gate instance (cheap to instantiate; reuses the same blacklist+model).
_GATE = SafetyGate()

VERTEX_CONFIG_NAME = "Vertex (default)"  # whatever name your AIConfig row uses for Vertex
DEEPSEEK_CONFIG_NAME = "DeepSeek-V3 (safety fallback)"


@dataclass
class RouteDecision:
    refuse: bool
    routed_to: Optional[str]   # "vertex" | "deepseek" | None
    config_id: Optional[int]
    reason: str                # human-readable diagnostic


class LLMRouter:
    def __init__(self, vertex_config_id: Optional[int] = None,
                 deepseek_config_id: Optional[int] = None):
        self.vertex_config_id = vertex_config_id
        self.deepseek_config_id = deepseek_config_id

    @classmethod
    def from_session(cls, session: Session) -> "LLMRouter":
        """Build a router by resolving config IDs from AIConfig table."""
        def _find(name: str) -> Optional[int]:
            row = session.exec(select(AIConfig).where(AIConfig.name == name)).first()
            return row.id if row else None
        return cls(
            vertex_config_id=_find(VERTEX_CONFIG_NAME),
            deepseek_config_id=_find(DEEPSEEK_CONFIG_NAME),
        )

    def decide(self, verdict) -> RouteDecision:
        if verdict.blocked:
            return RouteDecision(
                refuse=True, routed_to=None, config_id=None,
                reason=f"L2 refuse: gate.blocked layer={verdict.block_layer}",
            )
        if verdict.avoid_vertex:
            if self.deepseek_config_id is None:
                # Fail-closed: better to refuse than risk Vertex
                return RouteDecision(
                    refuse=True, routed_to=None, config_id=None,
                    reason="L2 refuse: avoid_vertex but no DeepSeek config",
                )
            return RouteDecision(
                refuse=False, routed_to="deepseek",
                config_id=self.deepseek_config_id,
                reason=f"L2 deepseek: avoid_vertex (dim={verdict.max_dim} score={verdict.moderation_score:.2f})",
            )
        return RouteDecision(
            refuse=False, routed_to="vertex",
            config_id=self.vertex_config_id,
            reason="L2 vertex: clean",
        )

    async def generate(
        self, session: Session, prompt: str, *,
        system_prompt: str = "You are a helpful assistant.",
        history: Optional[List[Dict[str, str]]] = None,
        source: str = "router",
        account_id: Optional[int] = None,
        persona_id: Optional[int] = None,
        chat_id: Optional[str] = None,
    ) -> Optional[str]:
        verdict = _GATE.evaluate(prompt)
        decision = self.decide(verdict)
        logger.info(f"LLMRouter: {decision.reason} source={source}")

        if decision.refuse:
            # Still record a usage row so we can monitor block rate
            from app.services.pricing import record_usage
            record_usage(
                provider="router", model="refuse",
                source=f"{source}:routed_refuse",
                input_tokens=0, output_tokens=0,
                account_id=account_id, persona_id=persona_id, chat_id=chat_id,
            )
            return None

        llm = LLMService(db_session=session, config_id=decision.config_id)
        return await llm.get_response(
            prompt=prompt, system_prompt=system_prompt, history=history,
            source=f"{source}:routed_{decision.routed_to}",
            account_id=account_id, persona_id=persona_id, chat_id=chat_id,
        )
```

Run: `docker exec -w /app tgsc-backend-1 pytest tests/test_llm_router.py -v`
Expected: all 5 pass.

- [ ] **Step 3.1.3: Commit**

```bash
cd /var/tgsc
git add backend/app/services/safety/router.py backend/tests/test_llm_router.py
git commit -m "feat(safety): add L2 LLMRouter (Vertex/DeepSeek/refuse)"
```

---

## Task 3.2: Seed Vertex AIConfig (if not already present)

We need a named Vertex AIConfig row so the router can resolve it. If one already exists with a different name, rename or seed a new one.

**Files:**
- Modify: `backend/scripts/seed_deepseek_config.py` → extend to also seed Vertex row, OR
- Create: `backend/scripts/seed_vertex_config.py` (new file, cleaner)

- [ ] **Step 3.2.1: Check current Vertex config row**

```bash
docker compose exec -T db psql -U tgsc_user -d tgsc_prod -c \
  "SELECT id, name, provider, model, is_default, is_active FROM ai_config WHERE provider IN ('vertex','gemini') ORDER BY id;"
```

If a row already exists with `provider=vertex` and is active, note its name. If it's not `"Vertex (default)"`, update the name to match:

```bash
docker compose exec -T db psql -U tgsc_user -d tgsc_prod -c \
  "UPDATE ai_config SET name='Vertex (default)' WHERE id=<NN>;"
```

Where `<NN>` is the row id from the SELECT.

- [ ] **Step 3.2.2: Verify router resolves both configs**

```bash
docker exec -w /app tgsc-backend-1 python -c "
from sqlmodel import Session
from app.core.db import engine
from app.services.safety.router import LLMRouter
with Session(engine) as s:
    r = LLMRouter.from_session(s)
    print('vertex:', r.vertex_config_id, 'deepseek:', r.deepseek_config_id)
    assert r.vertex_config_id is not None, 'missing Vertex AIConfig row'
    assert r.deepseek_config_id is not None, 'missing DeepSeek AIConfig row'
print('OK')
"
```

Expected: prints both ids + `OK`. If either is `None`, fix the AIConfig table and re-run.

- [ ] **Step 3.2.3: Commit** (no file changes — just config DB state)

Document the rename / seeding step in the PR description. No git commit needed for this task.

---

## Task 3.3: Route `conversation_director` through `LLMRouter`

`LLMService.generate` is a convenience alias for `get_response` (`llm.py:349-362`), so the L0/L1 gate added in Task 1.3 + 2.2 already runs. But we want **L2 routing** here too — so callers go through `LLMRouter` instead of `ai.llm.generate`. The router decides config_id, the gate decides block/allow, no logic stays in the caller.

**Files:**
- Modify: `backend/app/services/conversation_director.py` (lines 295-310 reactive; 425-439 proactive)

- [ ] **Step 3.3.1: Replace reactive path (lines 295-310)**

In `/var/tgsc/backend/app/services/conversation_director.py`, find this exact block (line 295):

```python
            ai = AIEngine(session)
            try:
                raw = await ai.llm.generate(
                    _REACT_PROMPT.format(
                        persona_prompt=persona_prompt,
                        human_traits=_HUMAN_TRAITS_SHORT,
                        time_str=_get_time_str(),
                        context=context_str,
                        sender_name=sender_name,
                        trigger=trigger[:150],
                    ),
                    source="director_reactive",
                    account_id=account.id,
                    persona_id=account.ai_persona_id,
                    chat_id=str(group_id) if group_id else None,
                )
```

Replace with:

```python
            from app.services.safety.router import LLMRouter
            router = LLMRouter.from_session(session)
            try:
                raw = await router.generate(
                    session,
                    _REACT_PROMPT.format(
                        persona_prompt=persona_prompt,
                        human_traits=_HUMAN_TRAITS_SHORT,
                        time_str=_get_time_str(),
                        context=context_str,
                        sender_name=sender_name,
                        trigger=trigger[:150],
                    ),
                    source="director_reactive",
                    account_id=account.id,
                    persona_id=account.ai_persona_id,
                    chat_id=str(group_id) if group_id else None,
                )
```

(The `AIEngine(session)` instantiation is no longer needed in this code path — `ai_engine` is only used here for its `.llm` attribute, which we've replaced with the router.)

- [ ] **Step 3.3.2: Replace proactive path (lines 425-439)**

In the same file, find this block (line 425):

```python
            ai = AIEngine(session)
            try:
                raw = await ai.llm.generate(
                    _PROACTIVE_PROMPT.format(
                        persona_prompt=persona_prompt,
                        human_traits=_HUMAN_TRAITS_SHORT,
                        time_str=_get_time_str(),
                        context=context_str,
                        topic_hint=topic_hint,
                    ),
                    source="director_proactive",
                    account_id=acc.id,
                    persona_id=acc.ai_persona_id,
                    chat_id=str(group_id) if group_id else None,
                )
```

Replace with:

```python
            from app.services.safety.router import LLMRouter
            router = LLMRouter.from_session(session)
            try:
                raw = await router.generate(
                    session,
                    _PROACTIVE_PROMPT.format(
                        persona_prompt=persona_prompt,
                        human_traits=_HUMAN_TRAITS_SHORT,
                        time_str=_get_time_str(),
                        context=context_str,
                        topic_hint=topic_hint,
                    ),
                    source="director_proactive",
                    account_id=acc.id,
                    persona_id=acc.ai_persona_id,
                    chat_id=str(group_id) if group_id else None,
                )
```

- [ ] **Step 3.3.3: Verify with a smoke test**

```bash
docker exec -w /app tgsc-backend-1 python -c "
# Manually invoke ConversationDirector with a clean trigger and check llm_usage
# Substitute real fixture data based on your dev DB
from sqlmodel import Session
from app.core.db import engine
from app.services.conversation_director import ConversationDirector
# ... build a minimal trigger and assert routing went via router
print('Run a real reactive trigger via the listener if needed')
"
```

Then query `llm_usage` and confirm new rows have `source` like `director_reactive:routed_vertex` (or `:routed_deepseek`). Old `director_reactive` (no suffix) should not be appearing for new traffic.

- [ ] **Step 3.3.4: Commit**

```bash
cd /var/tgsc
git add backend/app/services/conversation_director.py
git commit -m "feat(safety): route director_reactive/proactive through LLMRouter"
```

---

## Task 3.4: Route `ai_reply_service` through `LLMRouter`

**Files:**
- Modify: `backend/app/services/ai_reply_service.py` (lines 148, 266)

- [ ] **Step 3.4.1: Replace `self.llm.get_response(...)` at line 266**

In `process_account_messages`, at the line that currently reads:

```python
reply_text = await self.llm.get_response(
    prompt=prompt, system_prompt=system_prompt, history=history,
    source="chat_reply", account_id=self.account_id, chat_id=chat_id,
)
```

Replace with:

```python
from app.services.safety.router import LLMRouter
router = LLMRouter.from_session(self.session)
reply_text = await router.generate(
    self.session, prompt,
    system_prompt=system_prompt, history=history,
    source="chat_reply",
    account_id=self.account_id, chat_id=chat_id,
)
```

- [ ] **Step 3.4.2: Replace `self.llm.analyze_intent(...)` at line 148**

`analyze_intent` is shorter — the input is just a user message. Route it the same way:

```python
intent = await router.generate(
    self.session, user_msg,
    system_prompt=INTENT_SYSTEM_PROMPT,  # use the existing intent system prompt
    history=history_msgs,
    source="intent_analyze",
    account_id=self.account_id, chat_id=chat_id,
)
# Parse intent the same way `analyze_intent` did downstream
```

Note: this changes the return shape from `analyze_intent`'s structured dict to a plain string. If the caller depends on structured output, keep `analyze_intent` separate and instead add an L0/router check inside `LLMService.analyze_intent` (Task 1.3 step 3 already did the L0 check; here we'd add a routing override via a config_id parameter — discuss with reviewer before committing).

If structured parsing is needed downstream, defer this step and open a follow-up issue. The Phase 3 PR can land with reactive/proactive + chat_reply routed; intent_analyze can wait.

- [ ] **Step 3.4.3: Commit**

```bash
cd /var/tgsc
git add backend/app/services/ai_reply_service.py
git commit -m "feat(safety): route ai_reply_service.chat_reply through LLMRouter"
```

---

# Phase 4 (P1c) — Monitoring + Operator Controls

## Task 4.1: Add `moderation_score`, `block_layer`, `routed_provider` columns to `llm_usage`

**Files:**
- Modify: `backend/app/models/llm_usage.py`
- Create: `backend/alembic/versions/c7d8e9f0a1b2_llm_usage_safety_columns.py`
- Modify: `backend/app/services/pricing.py` — `record_usage` signature

- [ ] **Step 4.1.1: Add columns to model**

Modify `/var/tgsc/backend/app/models/llm_usage.py`. Inside `LLMUsage` (around line 18-29), add:

```python
    moderation_score: Optional[float] = Field(default=None, index=True)
    block_layer: Optional[str] = Field(default=None, max_length=8, index=True)  # "L0" | "L1" | "L2" | None
    routed_provider: Optional[str] = Field(default=None, max_length=32, index=True)
```

- [ ] **Step 4.1.2: Write migration**

Create `/var/tgsc/backend/alembic/versions/c7d8e9f0a1b2_llm_usage_safety_columns.py`:

```python
"""llm_usage safety columns: moderation_score, block_layer, routed_provider

Revision ID: c7d8e9f0a1b2
Revises: b6c7d8e9f0a1
Create Date: 2026-06-01
"""
from alembic import op
import sqlalchemy as sa

revision = "c7d8e9f0a1b2"
down_revision = "b6c7d8e9f0a1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("llm_usage", sa.Column("moderation_score", sa.Float(), nullable=True))
    op.add_column("llm_usage", sa.Column("block_layer", sa.String(length=8), nullable=True))
    op.add_column("llm_usage", sa.Column("routed_provider", sa.String(length=32), nullable=True))
    op.create_index("ix_llm_usage_moderation_score", "llm_usage", ["moderation_score"])
    op.create_index("ix_llm_usage_block_layer", "llm_usage", ["block_layer"])
    op.create_index("ix_llm_usage_routed_provider", "llm_usage", ["routed_provider"])


def downgrade():
    op.drop_index("ix_llm_usage_routed_provider", table_name="llm_usage")
    op.drop_index("ix_llm_usage_block_layer", table_name="llm_usage")
    op.drop_index("ix_llm_usage_moderation_score", table_name="llm_usage")
    op.drop_column("llm_usage", "routed_provider")
    op.drop_column("llm_usage", "block_layer")
    op.drop_column("llm_usage", "moderation_score")
```

- [ ] **Step 4.1.3: Apply migration**

```bash
docker exec -w /app tgsc-backend-1 alembic upgrade head
```

Expected: `Running upgrade b6c7d8e9f0a1 -> c7d8e9f0a1b2, llm_usage safety columns`.

Verify:

```bash
docker compose exec -T db psql -U tgsc_user -d tgsc_prod -c \
  "\d llm_usage" | grep -E "moderation_score|block_layer|routed_provider"
```

Expected: 3 lines, all `nullable`.

- [ ] **Step 4.1.4: Extend `record_usage` signature**

In `/var/tgsc/backend/app/services/pricing.py`, find the `record_usage` function and add the three new kwargs (optional, default None). Persist them into the new columns. Existing call sites continue to work because the kwargs are optional.

- [ ] **Step 4.1.5: Wire the new fields from the router**

In `router.py` `generate(...)`, after computing `decision`, pass through the new metadata when calling `LLMService.get_response`. The cleanest approach: bypass `LLMService.get_response`'s built-in `record_usage` call and have the router write the row itself. Refactor:

In `LLMService.get_response`, add a parameter `_skip_usage_record: bool = False` that, when True, suppresses the inline `record_usage` call. The router will set it to True and then call `record_usage` with full metadata:

```python
# Inside LLMRouter.generate, after llm.get_response returns:
from app.services.pricing import record_usage
record_usage(
    provider=decision.routed_to or "router",
    model="...",   # capture from llm.model
    source=f"{source}:routed_{decision.routed_to}",
    input_tokens=...,   # need to expose tokens from get_response too — or refactor
    output_tokens=...,
    account_id=account_id, persona_id=persona_id, chat_id=chat_id,
    moderation_score=verdict.moderation_score,
    block_layer=None,
    routed_provider=decision.routed_to,
)
```

**Cleaner alternative (recommended):** have `LLMService.get_response` return a tuple `(text, usage_info)` when `_safety_metadata` is passed in. This is a 30-line refactor — discuss in PR. If too invasive, defer to a follow-up; the columns can stay null for now and Phase 1/2 sources (`:blocked_L0`, `:blocked_L1`) already encode the block reason via source-name suffix.

For this plan, take the **deferred** path: land the columns + index, populate them best-effort via source-name parsing in the monitoring endpoint (Task 4.2), and revisit a clean refactor in Phase 5.

- [ ] **Step 4.1.6: Commit**

```bash
cd /var/tgsc
git add backend/app/models/llm_usage.py \
        backend/alembic/versions/c7d8e9f0a1b2_llm_usage_safety_columns.py \
        backend/app/services/pricing.py
git commit -m "feat(safety): add moderation columns to llm_usage + migration"
```

---

## Task 4.2: Monitoring endpoint + alert thresholds

**Files:**
- Create: `backend/app/api/v1/endpoints/admin_safety.py`
- Modify: `backend/app/api/v1/__init__.py` (register router)

- [ ] **Step 4.2.1: Write endpoint**

Create `/var/tgsc/backend/app/api/v1/endpoints/admin_safety.py`:

```python
"""Admin endpoints for the LLM safety stack.

GET /admin/safety/stats — rolling 24h/7d aggregate of block/route decisions
GET /admin/safety/recent-blocks — last N L0/L1 hits for spot-check
GET /admin/safety/by-source — breakdown per source (qa_extract, director_reactive, ...)
"""
from datetime import datetime, timedelta
from typing import List, Dict, Any

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select, func

from app.core.db import get_session
from app.models.llm_usage import LLMUsage

router = APIRouter()


@router.get("/stats")
def safety_stats(
    hours: int = Query(24, ge=1, le=720),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Aggregate counts: total, L0-blocked, L1-blocked, routed-deepseek, routed-vertex."""
    since = datetime.utcnow() - timedelta(hours=hours)

    def _count(suffix: str) -> int:
        return session.exec(
            select(func.count(LLMUsage.id))
            .where(LLMUsage.ts > since)
            .where(LLMUsage.source.like(f"%{suffix}"))
        ).one()

    return {
        "since": since.isoformat(),
        "total_calls": session.exec(
            select(func.count(LLMUsage.id)).where(LLMUsage.ts > since)
        ).one(),
        "blocked_L0": _count(":blocked_L0"),
        "blocked_L1": _count(":blocked_L1"),
        "routed_refuse": _count(":routed_refuse"),
        "routed_deepseek": _count(":routed_deepseek"),
        "routed_vertex": _count(":routed_vertex"),
    }


@router.get("/recent-blocks")
def recent_blocks(
    limit: int = Query(50, ge=1, le=500),
    session: Session = Depends(get_session),
) -> List[Dict[str, Any]]:
    rows = session.exec(
        select(LLMUsage)
        .where(
            (LLMUsage.source.like("%:blocked_L0")) |
            (LLMUsage.source.like("%:blocked_L1"))
        )
        .order_by(LLMUsage.ts.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": r.id, "ts": r.ts.isoformat(),
            "source": r.source, "provider": r.provider,
            "account_id": r.account_id, "chat_id": r.chat_id,
        }
        for r in rows
    ]


@router.get("/by-source")
def stats_by_source(
    hours: int = Query(24, ge=1, le=720),
    session: Session = Depends(get_session),
) -> List[Dict[str, Any]]:
    since = datetime.utcnow() - timedelta(hours=hours)
    rows = session.exec(
        select(LLMUsage.source, func.count(LLMUsage.id))
        .where(LLMUsage.ts > since)
        .group_by(LLMUsage.source)
        .order_by(func.count(LLMUsage.id).desc())
    ).all()
    return [{"source": s, "count": c} for s, c in rows]
```

- [ ] **Step 4.2.2: Register router**

In `/var/tgsc/backend/app/api/v1/__init__.py`, around the other `include_router` calls, add:

```python
from app.api.v1.endpoints import admin_safety

router.include_router(
    admin_safety.router,
    prefix="/admin/safety",
    tags=["admin-safety"],
    dependencies=auth_deps,
)
```

- [ ] **Step 4.2.3: Smoke test endpoint**

```bash
# Restart backend to pick up the new router
docker compose restart backend
sleep 3
# Acquire admin token (use existing auth helper or curl + login)
TOKEN=$(curl -s -X POST http://localhost/api/v1/users/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"<admin_pwd>"}' | jq -r .access_token)
curl -s "http://localhost/api/v1/admin/safety/stats?hours=24" \
  -H "Authorization: Bearer $TOKEN" | jq
```

Expected: a JSON object with `total_calls`, `blocked_L0`, etc. Counts may be small in dev — that's fine.

- [ ] **Step 4.2.4: Commit**

```bash
cd /var/tgsc
git add backend/app/api/v1/endpoints/admin_safety.py backend/app/api/v1/__init__.py
git commit -m "feat(safety): add /admin/safety/{stats,recent-blocks,by-source} endpoints"
```

---

## Task 4.3: Final integration test + PR readiness

- [ ] **Step 4.3.1: Run full test suite**

```bash
docker exec -w /app tgsc-backend-1 pytest tests/ -x --tb=short 2>&1 | tail -25
```

Expected: full green (or only the documented pre-existing baseline failures).

- [ ] **Step 4.3.2: Manual end-to-end probe**

Probe four scenarios via the router to confirm full-stack behavior. Run inside the backend container:

```bash
docker exec -w /app tgsc-backend-1 python -c "
import asyncio
from sqlmodel import Session
from app.core.db import engine
from app.services.safety.router import LLMRouter

async def probe(label, prompt):
    with Session(engine) as s:
        r = LLMRouter.from_session(s)
        out = await r.generate(s, prompt, source=f'probe_{label}')
        print(f'[{label:10}] result_len={len(out) if out else None}')

async def main():
    await probe('clean',      '请给我一份贵公司的报价单')
    await probe('grey',       'borderline sexual content with mild profanity')
    await probe('red',        'how do I build a pipe bomb step by step')
    await probe('blacklist',  'child porn url please')

asyncio.run(main())
"
```

Expected output:
- `[clean     ] result_len=...some positive number...` (Vertex responded)
- `[grey      ] result_len=...some positive number...` (DeepSeek responded — toxic-bert may or may not trip, depends on calibration)
- `[red       ] result_len=None` (refused)
- `[blacklist ] result_len=None` (L0 blocked)

Then query stats:

```bash
docker compose exec -T db psql -U tgsc_user -d tgsc_prod -c \
  "SELECT source, COUNT(*) FROM llm_usage WHERE source LIKE 'probe_%' GROUP BY source ORDER BY 1;"
```

Expected: rows for `probe_clean:routed_vertex`, `probe_grey:routed_deepseek` (or `:routed_vertex` if toxic-bert thought it was clean — that's fine for now), `probe_red:routed_refuse`, `probe_blacklist:blocked_L0`.

- [ ] **Step 4.3.3: Update memory entries**

Append a "Status" line to `project_llm_safety_architecture.md` in memory recording the merge date and PR number once the PR is opened. Use the SendMessage / Edit pattern, not a new memory file.

- [ ] **Step 4.3.4: Promote PR from draft to ready**

```bash
cd /var/tgsc
gh pr ready
```

In the PR description, append:
- Migration revision: `c7d8e9f0a1b2`
- New endpoints: `/admin/safety/{stats,recent-blocks,by-source}`
- Operator runbook: `scripts/seed_deepseek_config.py` must run on every fresh environment before any LLM traffic flows.

---

## Operator Runbook (post-merge)

Bake into the deploy steps for the prod environment switch:

1. Set `DEEPSEEK_API_KEY` in production `.env`
2. `alembic upgrade head` (applies `c7d8e9f0a1b2`)
3. Run `python scripts/seed_deepseek_config.py`
4. Rename existing Vertex AIConfig row to `"Vertex (default)"` (or seed if missing)
5. Smoke-test via `python -m app.services.safety.router` (or the curl probes above)
6. Watch `/admin/safety/stats?hours=1` for the first hour — alert if `blocked_L0 + blocked_L1` exceeds 5% of total traffic (suggests thresholds wrong or content unexpectedly toxic)
7. If Vertex outage / ban happens: temporarily change `LLMRouter.decide` to always return `deepseek` (hot-patch); long-term: lower `*_grey` thresholds to push more grey traffic to DeepSeek

---

## Out of scope (follow-ups)

- **Multi-Vertex hot-spare** (P3 from the memory entry): swap to a secondary Vertex project on outage. Defer to a separate plan.
- **Refactor `record_usage` to accept structured safety metadata** (Task 4.1.5 placeholder): cleaner than parsing source suffixes. Land after this PR.
- **Operator UI for threshold tuning**: portal page calling `/admin/safety/stats` with sliders that PATCH thresholds. Defer.
- **Calibration test set for toxic-bert**: a 100-message labeled sample to tune `DEFAULT_THRESHOLDS`. Operator should build this on real traffic after a week of monitoring.
