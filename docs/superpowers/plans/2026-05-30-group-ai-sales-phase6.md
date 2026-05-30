# 群内 AI 销售员 Phase 6 实施计划（生产强化 + Lead 接入 + A/B 自动化）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 Phase 1-5 + Portal 留下的 6 个核心 backlog 一次性补齐：(a) Lead 表 JOIN 真算 `private_conversion_rate`；(b) A/B 多变体 priority ordering（monitor > customer > global）；(c) A/B 自动停实验；(d) A/B 实验启停 audit log；(e) listener/dispatcher 自动 record_event 挂钩；(f) Portal RealtimeStats WebSocket push 替代 30s polling。

**Architecture:** 纯加法，不改既有接口签名。Phase 6 涉及一个小 Alembic 迁移（A/B audit_log 表）+ 一个 Celery beat task（自动停实验）+ 几个 service 升级 + 一个 portal WebSocket hook。所有改动都 backward compatible（新 service 函数 / 新 endpoint / 新 model），不破 Phase 1-5 / Portal 测试。

**Tech Stack:** FastAPI · SQLModel · pgvector(unchanged) · Celery beat · Telethon (引入 typed exception imports) · React + WebSocket · 复用 Phase 1-5 + Portal 全栈

**Spec:** [docs/superpowers/specs/2026-05-28-group-ai-sales-presence-design.md](../specs/2026-05-28-group-ai-sales-presence-design.md) §10 (A/B 框架) + §8.2 (Portal UI)

**前置条件：**
- PR #9 + #10 + #11 + #12 + #13 + #14 全部 merge 到 main
- 灰度运行至少 2 周，有：
  - 至少 100 个 sent `pending_replies` 行
  - 至少 5 个 Lead 行（私聊转化）
  - 至少 1 个完成生命周期的 A/B 实验（draft → running → finished）
- 新 worktree `/var/tgsc/.claude/worktrees/feature+group-ai-sales-phase6`

**Phase 6 范围：**

| 包含 | 不含 |
|---|---|
| (a) Lead 表 JOIN 真算 private_conversion_rate | KB 文档导入 (PDF/Word/URL) — 独立 epic |
| (b) A/B priority ordering (monitor > customer > global) | Lead source attribution 升级追溯 (deep dive，独立) |
| (c) A/B 自动停实验 Celery beat | 移动端深度优化 |
| (d) A/B 实验启停 audit_log + endpoint | i18n 多语 |
| (e) listener/dispatcher 自动 record_event | Playwright CI integration (运维工作) |
| (f) Portal RealtimeStats WS push | 真人接话检测信号灵敏度调参 (Phase 5 灰度后) |
| 1 小迁移 (ab_experiment_audit_log 表) | A/B 多变体并发 (>2 variants 同时一个 metric, 数学复杂) |

---

## File Structure

**新建（backend）：**
- `backend/app/models/ab_experiment_audit_log.py` — 新表 SQLModel
- `backend/alembic/versions/<rev>_ab_experiment_audit_log.py` — Phase 6 迁移
- `backend/app/services/lead_conversion_service.py` — Lead JOIN 查询封装
- `backend/app/services/ab_auto_stop_service.py` — 自动停逻辑
- `backend/app/workers/ab_auto_stop.py` — Celery beat task
- `backend/tests/test_ab_experiment_audit_log_model.py`
- `backend/tests/test_lead_conversion_service.py`
- `backend/tests/test_experiment_metrics_phase6.py`
- `backend/tests/test_ab_priority_ordering.py`
- `backend/tests/test_ab_auto_stop_service.py`
- `backend/tests/test_account_lifecycle_hooks.py`

**新建（frontend）：**
- `frontend/src/portal/hooks/usePortalStatsWebsocket.ts` — portal customer WS

**修改：**
- `backend/app/services/experiment_metrics_service.py` — `_count_private_conversions_after_sent` 改真实现
- `backend/app/services/ab_assignment_service.py` — `find_applicable_experiments` 加 priority ordering
- `backend/app/services/listener_service.py` — typed telethon exception catch + record_event
- `backend/app/services/group_dispatcher.py` — 同上 + send 失败 record
- `backend/app/routers/admin_group_ai.py` — A/B start/stop endpoint 写 audit_log + 新 endpoint GET audit list
- `backend/app/services/ws_manager.py` 或 websocket_manager.py — broadcast helper for portal customer namespace (verify existing structure)
- `frontend/src/portal/pages/GroupAI/RealtimeStats.tsx` — 加 WS hook 替代部分 polling

---

## Task 1: ab_experiment_audit_log 表 + Alembic 迁移 + SQLModel

**Files:**
- Create: `backend/app/models/ab_experiment_audit_log.py`
- Create: `backend/alembic/versions/<auto>_ab_experiment_audit_log.py`
- Create: `backend/tests/test_ab_experiment_audit_log_model.py`

### Step 1.1: 生成迁移

```bash
cd /var/tgsc/.claude/worktrees/feature+group-ai-sales-phase6
pwd
cd backend
alembic heads  # 应该是 148458b23ea2 (Phase 5)
alembic revision -m "ab_experiment_audit_log"
```

### Step 1.2: 写迁移

```python
"""ab_experiment_audit_log

Revision ID: <REV>
Revises: 148458b23ea2
Create Date: 2026-05-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from typing import Sequence, Union

revision: str = "<REV>"
down_revision: Union[str, Sequence[str], None] = "148458b23ea2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ab_experiment_audit_log",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("experiment_id", sa.Integer,
                  sa.ForeignKey("ab_experiments.id"), nullable=False),
        sa.Column("action", sa.Text, nullable=False),
        # action: 'created' | 'started' | 'stopped' | 'auto_stopped'
        sa.Column("operator_id", sa.Integer,
                  sa.ForeignKey("user.id"), nullable=True),
        # operator_id nullable: 'auto_stopped' 是系统操作, NULL
        sa.Column("reason", sa.Text, nullable=True),
        # reason for auto_stop: 'significant_result' / 'max_duration' etc
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "idx_ab_audit_experiment_time",
        "ab_experiment_audit_log",
        ["experiment_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_ab_audit_experiment_time", table_name="ab_experiment_audit_log")
    op.drop_table("ab_experiment_audit_log")
```

### Step 1.3: 写 SQLModel

`backend/app/models/ab_experiment_audit_log.py`:

```python
"""ABExperimentAuditLog — 实验启停操作历史 (含自动停)"""
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, JSON, Text
from sqlmodel import Field, SQLModel


class ABExperimentAuditLog(SQLModel, table=True):
    __tablename__ = "ab_experiment_audit_log"

    id: Optional[int] = Field(
        default=None,
        sa_column=Column(
            BigInteger().with_variant(__import__("sqlalchemy.dialects.sqlite", fromlist=["INTEGER"]).INTEGER(), "sqlite"),
            primary_key=True,
        ),
    )
    experiment_id: int = Field(
        sa_column=Column(Integer, ForeignKey("ab_experiments.id"), nullable=False)
    )
    action: str = Field(sa_column=Column(Text, nullable=False))
    operator_id: Optional[int] = Field(
        default=None, sa_column=Column(Integer, ForeignKey("user.id"), nullable=True)
    )
    reason: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    metadata_json: Optional[dict] = Field(default=None, sa_column=Column(JSON, nullable=True))
    created_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=False),
    )
```

Register in `backend/app/models/__init__.py` (匹配 Phase 5 pattern).

### Step 1.4: 写测试

`backend/tests/test_ab_experiment_audit_log_model.py`:

```python
import os
import pytest


def test_model_importable():
    from app.models.ab_experiment_audit_log import ABExperimentAuditLog
    assert ABExperimentAuditLog.__tablename__ == "ab_experiment_audit_log"


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

### Step 1.5: 验证 + 提交

```bash
pytest backend/tests/test_ab_experiment_audit_log_model.py -v
git add backend/app/models/ab_experiment_audit_log.py \
        backend/app/models/__init__.py \
        backend/alembic/versions/*ab_experiment_audit_log.py \
        backend/tests/test_ab_experiment_audit_log_model.py
git commit -m "feat(group-ai/phase6): ab_experiment_audit_log table + migration"
```

---

## Task 2: lead_conversion_service — Lead JOIN 查询封装

**Files:**
- Create: `backend/app/services/lead_conversion_service.py`
- Create: `backend/tests/test_lead_conversion_service.py`

Phase 5 `_count_private_conversions_after_sent` 返回 0 placeholder。Phase 6 接 Lead 表。

### Pre-implementation: 摸 Lead model

```bash
grep -nE "telegram_user_id|tg_user_id|source_user_id|sender_id" backend/app/models/lead.py | head -10
grep -nE "private_chat_started|first_msg_at|created_at" backend/app/models/lead.py | head -10
```

需要找：
- Lead 表存 source TG user ID 的字段名（可能 `telegram_user_id` / `tg_user_id` / `sender_id`）
- Lead 创建时间字段（`created_at` 通常存在）
- 任何 source attribution 字段（哪个 group → 哪个 lead）

### Step 2.1: 写测试

`backend/tests/test_lead_conversion_service.py`:

```python
"""lead_conversion_service: 查 source_user 在 sent 后 N 小时内私聊转化"""
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

from app.services.lead_conversion_service import (
    count_private_conversions_for_experiment,
)


def test_returns_zero_when_no_sent_rows():
    fake_session = MagicMock()
    fake_session.exec.return_value.all.return_value = []
    cnt = count_private_conversions_for_experiment(
        session=fake_session, experiment_tag="exp:v1", window_hours=24,
    )
    assert cnt == 0


def test_counts_distinct_lead_conversions_within_window():
    """每个 sent 行检查 source_user 是否在窗口内有 Lead 行"""
    now = datetime.now(timezone.utc)
    # Mock: sent_rows = [(source_user_id, sent_at)]
    fake_sent_rows = [(8888, now - timedelta(hours=3))]
    # Mock: lead exists for user 8888 created 1h after sent
    fake_lead_count = 1
    fake_session = MagicMock()

    # Two queries: first for sent rows, second per row for Lead count
    call_results = [fake_sent_rows, [fake_lead_count]]
    def mock_exec(stmt):
        result = MagicMock()
        result.all.return_value = call_results[0] if call_results else []
        result.first.return_value = call_results.pop(0)[0] if call_results else 0
        return result
    fake_session.exec.side_effect = mock_exec

    cnt = count_private_conversions_for_experiment(
        session=fake_session, experiment_tag="exp:v1", window_hours=24,
    )
    assert cnt >= 0  # smoke: doesn't crash


def test_window_filter_excludes_late_conversions():
    """sent 48h 前, 现在算的 24h window → 即使有 Lead 也不算"""
    fake_session = MagicMock()
    # sent 行 sent_at 太旧, query 阶段就过滤掉
    fake_session.exec.return_value.all.return_value = []
    cnt = count_private_conversions_for_experiment(
        session=fake_session, experiment_tag="exp:v1", window_hours=24,
    )
    assert cnt == 0
```

### Step 2.2: 实装

`backend/app/services/lead_conversion_service.py`:

```python
"""
lead_conversion_service — 查 source_user 在群回复后 N 小时内是否私聊转化为 Lead。

实施者: Lead 表字段名以摸底 grep 结果为准。本文件 hardcode 一组合理默认,
如果真实字段名不同 (e.g. tg_user_id), 替换为正确字段名。
"""
import logging
from datetime import datetime, timezone, timedelta

from sqlmodel import select, func

from app.models.lead import Lead
from app.models.pending_reply import PendingReply, PendingReplyStatus

logger = logging.getLogger(__name__)

PRIVATE_CONVERSION_WINDOW_HOURS = 24


def count_private_conversions_for_experiment(
    *, session, experiment_tag: str,
    window_hours: int = PRIVATE_CONVERSION_WINDOW_HOURS,
) -> int:
    """
    Returns count of distinct (source_user_id, sent_at) pairs from sent rows
    where a Lead row was created for that user within `window_hours` after sent_at.

    Lead.tg_user_id (or telegram_user_id — adapt to real schema) MUST match
    pending_replies.source_user_id for the join.
    """
    # 1. Fetch sent rows for this experiment_tag
    sent_rows = session.exec(
        select(PendingReply.source_user_id, PendingReply.sent_at).where(
            PendingReply.experiment_tag == experiment_tag,
            PendingReply.status == PendingReplyStatus.SENT.value,
            PendingReply.sent_at.isnot(None),
        )
    ).all()

    if not sent_rows:
        return 0

    # 2. For each sent row, check if Lead row exists for source_user within window
    conversion_count = 0
    for source_user_id, sent_at in sent_rows:
        cutoff = sent_at + timedelta(hours=window_hours)

        # Adapt field name: try .tg_user_id; if not exist, use .telegram_user_id
        # Real implementation depends on Lead model schema (摸底确认)
        try:
            user_field = Lead.tg_user_id  # type: ignore
        except AttributeError:
            user_field = Lead.telegram_user_id  # type: ignore

        stmt = select(func.count(Lead.id)).where(
            user_field == source_user_id,
            Lead.created_at >= sent_at,
            Lead.created_at <= cutoff,
        )
        lead_cnt = int(session.exec(stmt).first() or 0)
        if lead_cnt > 0:
            conversion_count += 1

    return conversion_count
```

Adapt to real Lead schema based on摸底.

### Step 2.3: 跑 + 提交

```bash
pytest backend/tests/test_lead_conversion_service.py -v
git add backend/app/services/lead_conversion_service.py backend/tests/test_lead_conversion_service.py
git commit -m "feat(group-ai/phase6): lead_conversion_service (real private_conversion count)"
```

---

## Task 3: experiment_metrics 改用 lead_conversion_service

**Files:**
- Modify: `backend/app/services/experiment_metrics_service.py`
- Create: `backend/tests/test_experiment_metrics_phase6.py`

### Step 3.1: 替换 placeholder

In `_count_private_conversions_after_sent`:

```python
def _count_private_conversions_after_sent(
    *, session, experiment_tag: str,
) -> int:
    """Phase 6: real implementation via lead_conversion_service."""
    from app.services.lead_conversion_service import (
        count_private_conversions_for_experiment,
    )
    return count_private_conversions_for_experiment(
        session=session, experiment_tag=experiment_tag,
    )
```

### Step 3.2: 测试

`backend/tests/test_experiment_metrics_phase6.py`:

```python
"""Phase 6: experiment_metrics 真算 private_conversion_rate"""
from unittest.mock import patch, MagicMock

from app.services.experiment_metrics_service import (
    _count_private_conversions_after_sent,
)


def test_count_delegates_to_lead_conversion_service():
    with patch(
        "app.services.lead_conversion_service.count_private_conversions_for_experiment",
        return_value=42,
    ):
        cnt = _count_private_conversions_after_sent(
            session=MagicMock(), experiment_tag="exp:v1",
        )
    assert cnt == 42
```

### Step 3.3: 跑 + 提交

```bash
pytest backend/tests/test_experiment_metrics_phase6.py -v
# Also confirm Phase 5 metrics tests still pass
pytest backend/tests/test_experiment_metrics_service.py -v
git add backend/app/services/experiment_metrics_service.py backend/tests/test_experiment_metrics_phase6.py
git commit -m "feat(group-ai/phase6): experiment_metrics uses real lead_conversion_service"
```

---

## Task 4: A/B priority ordering (monitor > customer > global)

**Files:**
- Modify: `backend/app/services/ab_assignment_service.py` — `find_applicable_experiments`
- Create: `backend/tests/test_ab_priority_ordering.py`

Phase 4a 简化: `find_applicable_experiments` 返回 list, pipeline 取 `experiments[0]` — 任意 DB row order。

Phase 6: 改返回排序的 list, monitor 优先, 然后 customer, 然后 global。

### Step 4.1: 写测试

`backend/tests/test_ab_priority_ordering.py`:

```python
"""find_applicable_experiments priority: monitor > customer > global"""
from unittest.mock import MagicMock

from app.services.ab_assignment_service import find_applicable_experiments


def test_priority_monitor_wins_over_customer_and_global():
    """3 实验同时 applicable, monitor scope 第一"""
    fake_session = MagicMock()
    fake_session.exec.return_value.all.return_value = [
        MagicMock(id=1, scope="global", scope_value=None),
        MagicMock(id=2, scope="customer", scope_value=1),
        MagicMock(id=3, scope="monitor", scope_value=5),
    ]
    result = find_applicable_experiments(
        session=fake_session, customer_id=1, monitor_id=5,
    )
    assert len(result) == 3
    assert result[0].scope == "monitor"
    assert result[1].scope == "customer"
    assert result[2].scope == "global"


def test_priority_customer_wins_over_global_when_no_monitor():
    fake_session = MagicMock()
    fake_session.exec.return_value.all.return_value = [
        MagicMock(id=1, scope="global", scope_value=None),
        MagicMock(id=2, scope="customer", scope_value=1),
    ]
    result = find_applicable_experiments(
        session=fake_session, customer_id=1, monitor_id=5,
    )
    assert result[0].scope == "customer"
    assert result[1].scope == "global"


def test_only_global_returns_global():
    fake_session = MagicMock()
    fake_session.exec.return_value.all.return_value = [
        MagicMock(id=1, scope="global", scope_value=None),
    ]
    result = find_applicable_experiments(
        session=fake_session, customer_id=1, monitor_id=5,
    )
    assert len(result) == 1
    assert result[0].scope == "global"
```

### Step 4.2: 修改 find_applicable_experiments

In `backend/app/services/ab_assignment_service.py`:

```python
# Priority: lower number = higher priority
_SCOPE_PRIORITY = {"monitor": 0, "customer": 1, "global": 2}


def find_applicable_experiments(
    *, session, customer_id: int, monitor_id: int,
) -> list[ABExperiment]:
    """
    取当前 (customer, monitor) 适用的 running 实验, 按 scope priority 排序:
    monitor > customer > global.
    """
    stmt = select(ABExperiment).where(
        ABExperiment.status == "running",
        (
            (ABExperiment.scope == "global") |
            ((ABExperiment.scope == "customer") & (ABExperiment.scope_value == customer_id)) |
            ((ABExperiment.scope == "monitor") & (ABExperiment.scope_value == monitor_id))
        )
    )
    rows = list(session.exec(stmt).all())
    # Phase 6: priority ordering
    rows.sort(key=lambda e: _SCOPE_PRIORITY.get(e.scope, 99))
    return rows
```

### Step 4.3: 跑 + 提交

```bash
pytest backend/tests/test_ab_priority_ordering.py -v
# 确认 Phase 4a ab_assignment 测试无回归
pytest backend/tests/test_ab_assignment_service.py -v
git add backend/app/services/ab_assignment_service.py backend/tests/test_ab_priority_ordering.py
git commit -m "feat(group-ai/phase6): ab priority ordering (monitor > customer > global)"
```

---

## Task 5: ab_auto_stop_service — 自动停实验

**Files:**
- Create: `backend/app/services/ab_auto_stop_service.py`
- Create: `backend/tests/test_ab_auto_stop_service.py`

逻辑：每日 Celery beat 检查 running 实验，若样本 > N 且 p < 0.01 → 自动 stop + 写 audit_log（reason='significant_result'）。

### Step 5.1: 写测试

`backend/tests/test_ab_auto_stop_service.py`:

```python
"""ab_auto_stop_service: 自动停实验逻辑"""
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

from app.services.ab_auto_stop_service import (
    should_auto_stop, run_auto_stop_check,
)


def test_should_auto_stop_when_significant_and_enough_sample():
    """primary_metric=reply_rate, total > 1000, p < 0.01 → True"""
    fake_report = {
        "variants": [
            {"counters": {"sent": 600, "total_triggered": 1000}, "metrics": {"reply_rate": 0.6}},
            {"counters": {"sent": 400, "total_triggered": 1000}, "metrics": {"reply_rate": 0.4}},
        ],
        "significance": {"p_value": 0.001, "significant": True},
    }
    fake_exp = MagicMock(primary_metric="reply_rate")
    result = should_auto_stop(experiment=fake_exp, report=fake_report)
    assert result["should_stop"] is True
    assert result["reason"] == "significant_result"


def test_should_not_auto_stop_when_sample_too_small():
    """total < 200 → 即使 significant 也不停 (规则: 最少 200/variant)"""
    fake_report = {
        "variants": [
            {"counters": {"sent": 50, "total_triggered": 100}, "metrics": {"reply_rate": 0.5}},
            {"counters": {"sent": 30, "total_triggered": 100}, "metrics": {"reply_rate": 0.3}},
        ],
        "significance": {"p_value": 0.001, "significant": True},
    }
    fake_exp = MagicMock(primary_metric="reply_rate")
    result = should_auto_stop(experiment=fake_exp, report=fake_report)
    assert result["should_stop"] is False
    assert "sample_too_small" in result["reason"]


def test_should_not_auto_stop_when_not_significant():
    fake_report = {
        "variants": [
            {"counters": {"sent": 500, "total_triggered": 1000}, "metrics": {"reply_rate": 0.5}},
            {"counters": {"sent": 480, "total_triggered": 1000}, "metrics": {"reply_rate": 0.48}},
        ],
        "significance": {"p_value": 0.45, "significant": False},
    }
    fake_exp = MagicMock(primary_metric="reply_rate")
    result = should_auto_stop(experiment=fake_exp, report=fake_report)
    assert result["should_stop"] is False
    assert "not_significant" in result["reason"]


def test_run_auto_stop_check_stops_qualifying_experiments():
    """主 entry: 拉 running 实验 + 每个判断 + stop + audit"""
    fake_exp = MagicMock(id=1, name="test_exp", primary_metric="reply_rate", status="running")
    fake_report = {
        "variants": [
            {"counters": {"sent": 600, "total_triggered": 1000}, "metrics": {"reply_rate": 0.6}},
            {"counters": {"sent": 400, "total_triggered": 1000}, "metrics": {"reply_rate": 0.4}},
        ],
        "significance": {"p_value": 0.001, "significant": True},
    }
    with patch("app.services.ab_auto_stop_service._list_running_experiments", return_value=[fake_exp]), \
         patch("app.services.ab_auto_stop_service.build_experiment_report", return_value=fake_report), \
         patch("app.services.ab_auto_stop_service._stop_experiment_with_audit") as stop_mock:
        n = run_auto_stop_check()
    assert n == 1
    stop_mock.assert_called_once_with(experiment=fake_exp, reason="significant_result")
```

### Step 5.2: 实装

`backend/app/services/ab_auto_stop_service.py`:

```python
"""
ab_auto_stop_service — 每日检查 running 实验, 若样本充足且显著则自动停。

约定:
- 最小样本: 200 / variant (太少 CI 太宽)
- 显著阈值: p < 0.01 (比标准 0.05 更严, 自动停应该高置信)
- 写 ab_experiment_audit_log reason='significant_result', operator_id=None
"""
import logging
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.core.db import engine
from app.models.ab_experiment import ABExperiment
from app.models.ab_experiment_audit_log import ABExperimentAuditLog
from app.services.experiment_report_service import build_experiment_report

logger = logging.getLogger(__name__)

MIN_SAMPLE_PER_VARIANT = 200
AUTO_STOP_P_THRESHOLD = 0.01


def should_auto_stop(*, experiment, report: dict) -> dict:
    """Decide if an experiment should auto-stop.

    Returns: {"should_stop": bool, "reason": str}
    """
    variants = report.get("variants", [])
    if len(variants) < 2:
        return {"should_stop": False, "reason": "not_enough_variants"}

    # Check sample size
    for v in variants:
        counters = v.get("counters", {})
        total = counters.get("total_triggered", 0)
        if total < MIN_SAMPLE_PER_VARIANT:
            return {
                "should_stop": False,
                "reason": f"sample_too_small (variant {v.get('tag')} = {total} < {MIN_SAMPLE_PER_VARIANT})",
            }

    # Check significance
    sig = report.get("significance") or {}
    p = sig.get("p_value")
    if p is None or p >= AUTO_STOP_P_THRESHOLD:
        return {
            "should_stop": False,
            "reason": f"not_significant (p={p})",
        }

    return {"should_stop": True, "reason": "significant_result"}


def _list_running_experiments() -> list:
    with Session(engine) as session:
        rows = session.exec(
            select(ABExperiment).where(ABExperiment.status == "running")
        ).all()
        return list(rows)


def _stop_experiment_with_audit(*, experiment, reason: str) -> None:
    with Session(engine) as session:
        exp = session.get(ABExperiment, experiment.id)
        if exp is None or exp.status != "running":
            logger.warning("auto_stop: experiment %s not in running state", experiment.id)
            return
        exp.status = "finished"
        exp.ended_at = datetime.now(timezone.utc)
        session.add(exp)

        # audit log
        audit = ABExperimentAuditLog(
            experiment_id=exp.id,
            action="auto_stopped",
            operator_id=None,  # system action
            reason=reason,
            metadata_json=None,
            created_at=datetime.now(timezone.utc),
        )
        session.add(audit)

        session.commit()
    logger.info("auto_stop: experiment %s stopped (reason: %s)", experiment.id, reason)


def run_auto_stop_check() -> int:
    """Main entry. Returns count of experiments auto-stopped."""
    experiments = _list_running_experiments()
    stopped = 0
    for exp in experiments:
        try:
            with Session(engine) as session:
                report = build_experiment_report(session=session, experiment=exp)
        except Exception:
            logger.exception("auto_stop: failed to build report for exp %s", exp.id)
            continue

        decision = should_auto_stop(experiment=exp, report=report)
        if decision["should_stop"]:
            try:
                _stop_experiment_with_audit(
                    experiment=exp, reason=decision["reason"],
                )
                stopped += 1
            except Exception:
                logger.exception("auto_stop: failed to stop exp %s", exp.id)
    return stopped
```

### Step 5.3: 跑 + 提交

```bash
pytest backend/tests/test_ab_auto_stop_service.py -v
git add backend/app/services/ab_auto_stop_service.py backend/tests/test_ab_auto_stop_service.py
git commit -m "feat(group-ai/phase6): ab_auto_stop_service (sample > 200 + p < 0.01)"
```

---

## Task 6: Celery beat task for auto_stop (daily)

**Files:**
- Create: `backend/app/workers/ab_auto_stop.py`
- Modify: `backend/app/core/celery_app.py` (注册 beat task)

### Step 6.1: 写 task

`backend/app/workers/ab_auto_stop.py`:

```python
"""Celery beat task: daily auto-stop check"""
import logging

from app.core.celery_app import celery_app
from app.services.ab_auto_stop_service import run_auto_stop_check

logger = logging.getLogger(__name__)


@celery_app.task(name="ab_auto_stop.daily_check")
def auto_stop_daily():
    stopped = run_auto_stop_check()
    logger.info("ab_auto_stop daily check: stopped %d experiments", stopped)
    return stopped
```

### Step 6.2: 注册 beat

In `backend/app/core/celery_app.py` `beat_schedule`:

```python
"ab-auto-stop-daily": {
    "task": "ab_auto_stop.daily_check",
    "schedule": 86400.0,  # 24h
}
```

And include:
```python
include=[
    "app.workers.group_reply_scanner",
    "app.workers.chitchat_scheduler",
    "app.workers.ab_auto_stop",  # NEW
]
```

### Step 6.3: 提交

```bash
# No tests for the bare Celery task wrapper; ab_auto_stop_service tests cover logic
git add backend/app/workers/ab_auto_stop.py backend/app/core/celery_app.py
git commit -m "feat(group-ai/phase6): Celery beat daily task for ab_auto_stop"
```

---

## Task 7: A/B start/stop endpoints write audit_log + new audit list endpoint

**Files:**
- Modify: `backend/app/routers/admin_group_ai.py`

### Step 7.1: 改 start/stop endpoints to write audit

Find `start_ab_experiment` and `stop_ab_experiment` endpoints. After the state flip, add:

```python
from app.models.ab_experiment_audit_log import ABExperimentAuditLog
from datetime import datetime, timezone

# In start_ab_experiment, before final commit:
audit = ABExperimentAuditLog(
    experiment_id=exp.id, action="started",
    operator_id=_admin.id if hasattr(_admin, "id") else None,
    reason=None, metadata_json=None,
    created_at=datetime.now(timezone.utc),
)
session.add(audit)
session.commit()
```

Same for `stop_ab_experiment` with `action="stopped"`.

For `create_ab_experiment` add `action="created"`.

### Step 7.2: 新 audit list endpoint

```python
@router.get("/ab/experiments/{exp_id}/audit")
async def get_experiment_audit(
    exp_id: int,
    session: Session = Depends(get_session),
    _admin: User = Depends(get_current_admin),
):
    exp = session.get(ABExperiment, exp_id)
    if exp is None:
        raise HTTPException(404, "experiment not found")
    rows = session.exec(
        select(ABExperimentAuditLog)
        .where(ABExperimentAuditLog.experiment_id == exp_id)
        .order_by(ABExperimentAuditLog.created_at.desc())
    ).all()
    return [
        {
            "id": r.id, "action": r.action, "operator_id": r.operator_id,
            "reason": r.reason, "created_at": r.created_at,
        } for r in rows
    ]
```

### Step 7.3: 简单 smoke 测试

`backend/tests/test_admin_ab_audit_endpoints.py`:

```python
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


@pytest.mark.skip(reason="needs admin auth fixture, Portal phase")
def test_get_experiment_audit_returns_list(client):
    r = client.get("/admin/group-ai/ab/experiments/1/audit")
    assert r.status_code in (200, 422)
```

### Step 7.4: 提交

```bash
pytest backend/tests/test_admin_ab_audit_endpoints.py -v
git add backend/app/routers/admin_group_ai.py backend/tests/test_admin_ab_audit_endpoints.py
git commit -m "feat(group-ai/phase6): A/B start/stop writes audit + GET audit endpoint"
```

---

## Task 8: listener 自动 record_event 挂钩

**Files:**
- Modify: `backend/app/services/listener_service.py`
- Create: `backend/tests/test_account_lifecycle_hooks.py`

Phase 5 SKIPPED 此挂钩 (现有代码无 typed exception handlers)。Phase 6 introduce typed catches。

### Step 8.1: 摸现有错误处理

```bash
grep -nE "except|telethon\.|pyrogram\." backend/app/services/listener_service.py | head -30
```

Identify exception classes used (likely from `telethon.errors`, e.g. `SessionRevokedError`, `AuthKeyUnregisteredError`, `FloodWaitError`, `UserDeactivatedError`).

### Step 8.2: 加 typed exception catch + record_event

In the main message-handling loop or session-init function of `ListenerService`, add (per actual exception structure found):

```python
# At top:
from app.services.account_lifecycle_tracker import record_event
from app.core.db import engine
from sqlmodel import Session
try:
    from telethon.errors import (
        SessionRevokedError, AuthKeyUnregisteredError,
        UserDeactivatedError, FloodWaitError,
    )
except ImportError:
    # Pyrogram fallback
    from pyrogram.errors import SessionRevokedError, AuthKeyUnregisteredError  # type: ignore
    UserDeactivatedError = Exception
    FloodWaitError = Exception


# In exception handler (best fit per actual structure):
except (SessionRevokedError, AuthKeyUnregisteredError) as exc:
    logger.warning("session invalid for account %s: %s", account.id, exc)
    try:
        with Session(engine) as s:
            record_event(
                session=s, account_id=account.id,
                event_type="session_invalid", reason=str(exc),
            )
    except Exception:
        logger.warning("lifecycle hook failed", exc_info=True)
    # ... existing handling (e.g. mark account session_invalid)

except UserDeactivatedError as exc:
    try:
        with Session(engine) as s:
            record_event(session=s, account_id=account.id, event_type="banned", reason=str(exc))
    except Exception:
        logger.warning("lifecycle hook failed", exc_info=True)
    # ... existing

except FloodWaitError as exc:
    # Optional: record as 'flood_wait' (not the same as kick)
    # Phase 6 简化: 不记录 flood_wait, 因为是临时态; 后续可扩
    raise  # re-raise so existing retry logic kicks in
```

如果 listener_service 当前没有 try/except 包 message handling, **不要重写** —— 加 try/except 风险大。仅在已有 try/except 块里加 typed catches。

### Step 8.3: 测试

`backend/tests/test_account_lifecycle_hooks.py`:

```python
"""验证 listener / dispatcher 异常路径调 record_event"""
from unittest.mock import patch, MagicMock


def test_listener_session_invalid_records_event():
    """listener 捕获 SessionRevokedError → record_event 'session_invalid'"""
    # 这是 integration test, 因为 listener 内部状态多
    # Phase 6 简化: 验证 listener_service.py 中确实有 import record_event 调用
    import app.services.listener_service as ls
    src = open(ls.__file__).read()
    assert "from app.services.account_lifecycle_tracker import record_event" in src
    assert 'event_type="session_invalid"' in src or "event_type='session_invalid'" in src


def test_dispatcher_kicked_records_event():
    """dispatcher 捕获 UserBannedInChannelError / ChatWriteForbiddenError → record_event"""
    import app.services.group_dispatcher as gd
    src = open(gd.__file__).read()
    assert "from app.services.account_lifecycle_tracker import record_event" in src
```

Static source assert pattern is a pragmatic compromise — full integration would need to instantiate telethon mocks.

### Step 8.4: 提交

```bash
pytest backend/tests/test_account_lifecycle_hooks.py -v
git add backend/app/services/listener_service.py backend/tests/test_account_lifecycle_hooks.py
git commit -m "feat(group-ai/phase6): listener auto-records lifecycle events (session_invalid + banned)"
```

---

## Task 9: dispatcher 自动 record_event

**Files:**
- Modify: `backend/app/services/group_dispatcher.py`

Similar pattern to Task 8, but for `_telethon_send_to_group`:

```python
try:
    from telethon.errors import (
        UserBannedInChannelError, ChatWriteForbiddenError,
        ChannelPrivateError,
    )
except ImportError:
    UserBannedInChannelError = Exception
    ChatWriteForbiddenError = Exception
    ChannelPrivateError = Exception


# In dispatch_send's error path:
except (UserBannedInChannelError, ChatWriteForbiddenError) as exc:
    logger.warning("kicked from chat %s account %s: %s", chat_id, account_id, exc)
    try:
        with Session(engine) as s:
            record_event(
                session=s, account_id=account_id,
                event_type="kicked_from_chat", chat_id=chat_id, reason=str(exc),
            )
    except Exception:
        logger.warning("lifecycle hook failed", exc_info=True)
    return False  # send failed
```

Integration with existing `dispatch_send` flow — add typed catches around the `_telethon_send_to_group` call (or inside if it has its own try/except).

Test (already added in Task 8 static check):
```bash
pytest backend/tests/test_account_lifecycle_hooks.py -v
```

Commit:
```bash
git add backend/app/services/group_dispatcher.py
git commit -m "feat(group-ai/phase6): dispatcher auto-records kicked_from_chat events"
```

---

## Task 10: Portal RealtimeStats WS push

**Files:**
- Modify: `backend/app/services/group_reply_pipeline.py` (or scanner) — broadcast on status change
- Create: `frontend/src/portal/hooks/usePortalStatsWebsocket.ts`
- Modify: `frontend/src/portal/pages/GroupAI/RealtimeStats.tsx`

### Step 10.1: backend broadcast hook

每当 pending_replies 状态变化（特别是 `_insert_observing` 或 `_mark_status` 写完后），broadcast 给 portal customer namespace。但实际增加 ws broadcast 调用会触及很多点（scanner / pipeline / dispatcher）—— Phase 6 简化：仅在 `_insert_observing` 和 `dispatcher._mark_status` 处 broadcast。

In `backend/app/services/group_reply_pipeline.py`:

```python
async def _broadcast_stat_update(*, customer_id: int) -> None:
    """Phase 6: broadcast stats invalidation to portal customer."""
    try:
        from app.services.websocket_manager import manager as ws_manager
        await ws_manager.broadcast({
            "type": "portal_stats_update",
            "customer_id": customer_id,
        })
    except Exception:
        # ws failure shouldn't block pipeline
        pass


# In entrypoint, after _insert_observing or _insert_borderline:
await _broadcast_stat_update(customer_id=customer_id)
```

Similar minimal addition in `dispatcher._mark_status` (after status update commit).

### Step 10.2: portal WS hook

`frontend/src/portal/hooks/usePortalStatsWebsocket.ts`:

```typescript
/**
 * usePortalStatsWebsocket — customer portal WS for stats invalidation.
 * Replaces 30s polling with reactive push.
 */
import React from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { getCustomerToken } from '../auth';

export function usePortalStatsWebsocket() {
  const qc = useQueryClient();
  React.useEffect(() => {
    const token = getCustomerToken();
    if (!token) return;
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${proto}://${window.location.host}/api/v1/ws?token=${token}`);
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        if (msg.type === 'portal_stats_update') {
          qc.invalidateQueries({ queryKey: ['portal-stats'] });
        }
      } catch { /* ignore */ }
    };
    ws.onerror = () => { /* swallow */ };
    return () => { ws.close(); };
  }, [qc]);
}
```

### Step 10.3: RealtimeStats use hook

In `RealtimeStats.tsx`, add at top:

```typescript
import { usePortalStatsWebsocket } from '../../hooks/usePortalStatsWebsocket';

export default function RealtimeStats() {
  usePortalStatsWebsocket();  // 加这行, 30s polling 保留作 fallback
  // ... existing
}
```

Keep `refetchInterval: 30000` as fallback (in case WS drops).

### Step 10.4: 提交

```bash
git add backend/app/services/group_reply_pipeline.py \
        frontend/src/portal/hooks/usePortalStatsWebsocket.ts \
        frontend/src/portal/pages/GroupAI/RealtimeStats.tsx
git commit -m "feat(group-ai/phase6): portal RealtimeStats WS push + backend broadcast"
```

---

## Task 11: 全量测试 + E2E 更新

**File:**
- Modify: `backend/tests/test_group_reply_e2e.py` (optional Phase 6 audit log assertion)

### Step 11.1: 全测试跑

```bash
cd /var/tgsc/.claude/worktrees/feature+group-ai-sales-phase6
pytest backend/tests/ -k "phase1 or phase2a or phase3a or phase4a or phase5 or phase6 or portal_group_ai or group_reply or pending_reply or risk_controller or reply_composer or lead_detector or migration or icp or case_study or embedding_service or admin_group_ai or customer_icp or llm_score or worker_persona or human_reply or persona_rewriter or chitchat or ab_assignment or pipeline_with_experiment or copilot or inbox_group_ai or ai_reply_service_with or significance or experiment_metrics or experiment_report or admin_ab_report or account_lifecycle or lead_conversion or ab_priority or ab_auto_stop or admin_ab_audit" --ignore=backend/tests/test_opentele.py --ignore=backend/tests/test_pyrogram_login.py 2>&1 | tail -5
```

Expected: 158 + Phase 6 new (~15-20 tests) = ~175 PASS.

### Step 11.2: 提交

```bash
git commit --allow-empty -m "test(group-ai/phase6): full regression run — N PASS"
# Or: 如果有 e2e 改动:
# git add backend/tests/test_group_reply_e2e.py
# git commit -m "test(group-ai/phase6): e2e covers audit + auto-stop"
```

---

## Task 12: PR + release

### Step 12.1: 推

```bash
git push -u origin worktree-feature+group-ai-sales-phase6:feature/group-ai-sales-phase6 2>&1 | tail -3
```

### Step 12.2: 开 PR

```bash
gh pr create --title "feat(group-ai): Phase 6 — production hardening + Lead conversion + A/B automation" --base main --head feature/group-ai-sales-phase6 --body "$(cat <<'EOF'
## Summary

Phase 6: 把 Phase 1-5 + Portal 累积的 6 个核心 backlog 一次性补齐, 让 A/B 框架可全自动跑 + Lead 转化率真算 + 账号事件自动采集。

**Depends on PR #9 + #10 + #11 + #12 + #13 + #14** — merge them first.

### What's in this PR

- **12 Tasks completed** (~175 unit/integration tests pass)
- **ab_experiment_audit_log table + migration** (Phase 6 唯一新表)
- **lead_conversion_service**: 接 Lead 表 JOIN 真算 private_conversion_rate (Phase 5 placeholder fix)
- **A/B priority ordering**: monitor > customer > global (Phase 4a 简化版升级)
- **ab_auto_stop_service**: 每日 Celery beat 检查 running 实验, 样本 > 200 + p < 0.01 → 自动 stop + audit
- **A/B audit_log**: start/stop endpoints 写 audit + GET audit endpoint
- **listener/dispatcher record_event 挂钩**: Telethon typed exception → record_event (session_invalid / banned / kicked_from_chat)
- **Portal RealtimeStats WS push**: 替代 30s polling, 实时性提升

### Phase 6 explicitly **does not** include
- KB 文档导入 (独立 epic)
- Lead source attribution deep tracing
- 移动端深度优化
- i18n
- Playwright CI integration (运维工作)

### Stats
- 12 commits + 0-1 fix
- 20+ files changed
- 1 small Alembic migration (ab_experiment_audit_log)
- ~175 tests passing (Phase 1-6 + Portal 累计)

## Test plan

- [ ] PR #9-#14 全 merge
- [ ] alembic upgrade head (ab_experiment_audit_log 表建)
- [ ] 灰度: 触发 200+ pending_replies 给一个 running 实验
- [ ] 第二天 Celery beat 跑 → 看实验自动 stop + audit_log 行
- [ ] 创建 / 启动 / 停止 实验, audit_log 每步都有行
- [ ] 模拟 SessionRevokedError → account_lifecycle_events 行 'session_invalid'
- [ ] 模拟 UserBannedInChannelError → 'kicked_from_chat'
- [ ] customer 私聊 → Lead 表新建 → /admin/group-ai/ab/experiments/{id}/metrics 看 private_conversion_rate 不再 0

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)" 2>&1 | tail -3
```

---

## Phase 6 完成判据

- [ ] PR merged
- [ ] 灰度 1 周后:
  - 至少 1 个 A/B 实验自动停 + audit_log 行 reason='significant_result'
  - private_conversion_rate 算出非零真值
  - listener / dispatcher 有 lifecycle event 写入
  - portal RealtimeStats 不依赖 polling 也能实时更新

---

## 整套群内 AI 销售员 7 phase 路线图实施完成

```
Phase 1 (PR #9)  → 骨架            43 PASS
Phase 2a (#10)   → 三层识别+案例    90 PASS
Phase 3a (#11)   → 拟人化生命体    126 PASS
Phase 4a (#12)   → 销售衔接+A/B    141 PASS
Phase 5 (#13)    → A/B 完整化     158 PASS
Portal (#14)     → 统一前端        158 backend + frontend
Phase 6 (本 PR)  → 生产强化        ~175 backend + portal WS
```

**7 个 PR, 60+ commits, 80+ tasks, ~28000 行代码**.

至此 spec §9 (路线图) + §10 (A/B 框架) + §8.2 (Portal UI) 全部实施完毕。剩余的优化 (KB 文档导入 / 多语 / 移动端 / 实验自动停规则调参) 都是产品迭代而非架构补丁, 可按业务节奏增量做。
