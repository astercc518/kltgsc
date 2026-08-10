# 群内 AI 销售员 Phase 1 实施计划（骨架打通）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 打通"群消息 → 关键词命中 → 60s 观望 → 三段式 LLM 回复 → 发出"的端到端最小可用闭环；其它高阶能力（Layer 2/3、案例库、人设、闲聊、A/B）由后续 Phase 计划承接。

**Architecture:** 责任链 + Postgres 状态机（`pending_replies` 表）+ Celery beat 延时扫描。`listener_service` 收群消息时调 `group_reply_pipeline.entrypoint`，内部跑 `LeadDetector(Layer 1)` → 入 `pending_replies(status=observing, fire_at=now+random 60-900s)`；Celery beat 每 30s 扫到期行 → `RiskController` 基础检查 → `ReplyComposer`（仅 KB，无案例库）→ `GroupDispatcher`（随机 30-120s typing 后通过 Telethon 发群）→ `billing_service` 扣 $0.50。

**Tech Stack:** FastAPI · SQLModel · Alembic · PostgreSQL + pgvector · Celery (Redis broker) · Telethon · Vertex Gemini (LLM 复用)

**Spec:** [2026-05-28-group-ai-sales-presence-design.md](../specs/2026-05-28-group-ai-sales-presence-design.md)

**Phase 1 范围（明确包含 / 不含）：**

| 包含 | 不含（留给后续 Phase） |
|---|---|
| 5 张新表 + 4 个字段 一次性建好 | Layer 2 ICP embedding · Layer 3 LLM 评分 |
| `LeadDetector` 仅 Layer 1（keyword_filters） | case_studies 真实匹配（表建好但 ReplyComposer 不查） |
| `pending_replies` 状态机 | worker_personas 真实使用（用兜底 default） |
| Celery beat 每 30s 扫 | persona_rewriter（透传不变） |
| `RiskController` 仅 ①账号日额 ②同线索 48h 去重 ③cooldown | 真人接话检测（Phase 3） |
| `ReplyComposer` 仅 KB + 三段式 LLM | 数字一致性反幻觉（Phase 2）· 副驾驶兜底（Phase 4） |
| 沿用 `shill_dispatcher._anti_hallucination_filter` | ChitchatScheduler · A/B 框架 |
| billing $0.50 扣费 | Portal 配置 UI（除最小阈值开关） |

**实施前提条件：**
- 必须在新分支 `feature/group-ai-sales-phase1` 开始
- 数据库要先升级到包含 Epic 6 的 head（`a3b4c5d6e7f8` 之后）
- `.env` 要有 `GROUP_AI_REPLY_ENABLED=true` 开关（默认 false，灰度时再开）

---

## File Structure

**新建文件：**
- `backend/alembic/versions/<rev>_group_ai_sales_phase1.py` —— 迁移
- `backend/app/models/pending_reply.py` —— PendingReply model
- `backend/app/models/case_study.py` —— CaseStudy model（Phase 1 只建表，不查询）
- `backend/app/models/worker_persona.py` —— WorkerPersona model
- `backend/app/models/chitchat.py` —— ChitchatPool + ChitchatLog models
- `backend/app/models/ab_experiment.py` —— ABExperiment model
- `backend/app/services/group_reply_pipeline.py` —— 编排入口
- `backend/app/services/lead_detector.py` —— Layer 1 keyword filter
- `backend/app/services/risk_controller.py` —— 基础规则
- `backend/app/services/reply_composer.py` —— KB-only 三段式
- `backend/app/services/group_dispatcher.py` —— typing 时延 + 发送
- `backend/app/workers/group_reply_scanner.py` —— Celery beat 扫描器
- `backend/app/core/group_reply_config.py` —— 兜底 persona / 配置常量
- `backend/tests/test_group_reply_pipeline.py`
- `backend/tests/test_lead_detector_layer1.py`
- `backend/tests/test_risk_controller_phase1.py`
- `backend/tests/test_reply_composer_phase1.py`
- `backend/tests/test_group_dispatcher.py`
- `backend/tests/test_group_reply_e2e.py`

**修改文件：**
- `backend/app/models/customer.py` —— 加 4 字段
- `backend/app/models/keyword_monitor.py` —— 加 `keyword_filters` 字段
- `backend/app/services/listener_service.py:70` —— `_handle_message` 内加 1 行
- `backend/app/core/celery_app.py:60` —— `beat_schedule` 注册新 task

每个 service 文件保持 < 250 行，单一职责。models 文件每个一张表（与现有代码风格一致）。

---

## Task 1: Alembic 迁移 —— 5 张新表 + 4 个字段

**Files:**
- Create: `backend/alembic/versions/<auto-gen-rev>_group_ai_sales_phase1.py`
- Test: `backend/tests/test_group_ai_phase1_migration.py`

- [ ] **Step 1.1: 生成迁移文件骨架**

```bash
cd /var/tgsc/backend
alembic revision -m "group_ai_sales_phase1"
```

记下生成的 revision id（下文记作 `<REV>`），用于 down_revision 链接。检查上一个 head 是 `a3b4c5d6e7f8` 或更新的 epic 6 head。如果 head 不一致，先停下来排查。

- [ ] **Step 1.2: 编辑迁移文件 upgrade()**

打开新生成的 `backend/alembic/versions/<REV>_group_ai_sales_phase1.py`，写入：

```python
"""group_ai_sales_phase1

Revision ID: <REV>
Revises: a3b4c5d6e7f8
Create Date: 2026-05-28

新增 5 张表 + 4 个字段, 用于群内 AI 销售员 Phase 1-5 全功能落地。
Phase 1 实际只用 pending_replies + monitor.keyword_filters；
其余表/字段预先建好, 后续 Phase 直接填充逻辑无需再迁移。
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
import pgvector.sqlalchemy

revision = "<REV>"
down_revision = "a3b4c5d6e7f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # === 现有表扩展 ===
    op.add_column("customers", sa.Column("icp_profile_text", sa.Text(), nullable=True))
    op.add_column("customers", sa.Column(
        "icp_profile_embedding",
        pgvector.sqlalchemy.Vector(768),
        nullable=True,
    ))
    op.add_column("customers", sa.Column(
        "lead_detector_thresholds", JSONB(),
        nullable=False,
        server_default=sa.text(
            "'{\"layer2_sim\":0.55,\"layer3_score\":60,\"layer3_confidence\":0.7}'::jsonb"
        ),
    ))
    op.add_column("customers", sa.Column(
        "param_version", sa.Text(), nullable=False, server_default="v1"
    ))

    op.add_column("keywordmonitor", sa.Column("keyword_filters", JSONB(), nullable=True))

    # === pending_replies 全管线状态机 ===
    op.create_table(
        "pending_replies",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("customer_id", sa.Integer, sa.ForeignKey("customer.id"), nullable=False),
        sa.Column("monitor_id", sa.Integer, sa.ForeignKey("keywordmonitor.id"), nullable=False),
        sa.Column("responder_account_id", sa.Integer, sa.ForeignKey("account.id"), nullable=True),
        sa.Column("chat_id", sa.BigInteger, nullable=False),
        sa.Column("message_id", sa.BigInteger, nullable=False),
        sa.Column("source_user_id", sa.BigInteger, nullable=False),
        sa.Column("source_text", sa.Text, nullable=False),
        sa.Column("layer1_matched", JSONB(), nullable=True),
        sa.Column("layer2_similarity", sa.Float, nullable=True),
        sa.Column("layer3_score", sa.Integer, nullable=True),
        sa.Column("layer3_needs", JSONB(), nullable=True),
        sa.Column("layer3_solution_topic", sa.Text, nullable=True),
        sa.Column("layer3_confidence", sa.Float, nullable=True),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("fire_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("skip_reason", sa.Text, nullable=True),
        sa.Column("reply_text", sa.Text, nullable=True),
        sa.Column("lead_id", sa.Integer, sa.ForeignKey("lead.id"), nullable=True),
        sa.Column("experiment_tag", sa.Text, nullable=True),
    )
    op.create_index("idx_pending_replies_scan", "pending_replies", ["status", "fire_at"])
    op.create_index(
        "idx_pending_replies_dedup",
        "pending_replies",
        ["customer_id", "chat_id", "source_user_id", "created_at"],
    )

    # === case_studies ===
    op.create_table(
        "case_studies",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("customer_id", sa.Integer, sa.ForeignKey("customer.id"), nullable=False),
        sa.Column("industry", sa.Text, nullable=True),
        sa.Column("deal_size", sa.Text, nullable=True),
        sa.Column("period", sa.Text, nullable=True),
        sa.Column("problem", sa.Text, nullable=True),
        sa.Column("solution", sa.Text, nullable=True),
        sa.Column("outcome", sa.Text, nullable=True),
        sa.Column("tags", JSONB(), nullable=True),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(768), nullable=True),
        sa.Column("source", sa.Text, nullable=False),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        "CREATE INDEX idx_case_studies_emb ON case_studies "
        "USING hnsw (embedding vector_cosine_ops)"
    )
    op.create_index(
        "idx_case_studies_customer", "case_studies", ["customer_id"],
        postgresql_where=sa.text("active = true"),
    )

    # === worker_personas ===
    op.create_table(
        "worker_personas",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("account_id", sa.Integer, sa.ForeignKey("account.id"), unique=True, nullable=False),
        sa.Column("customer_id", sa.Integer, sa.ForeignKey("customer.id"), nullable=False),
        sa.Column("display_name", sa.Text, nullable=True),
        sa.Column("age_range", sa.Text, nullable=True),
        sa.Column("region", sa.Text, nullable=True),
        sa.Column("occupation", sa.Text, nullable=True),
        sa.Column("speaking_style", sa.Text, nullable=True),
        sa.Column("catchphrases", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("active_hours", JSONB(), nullable=False, server_default=sa.text(
            "'{\"mon\":[[9,18]],\"tue\":[[9,18]],\"wed\":[[9,18]],\"thu\":[[9,18]],"
            "\"fri\":[[9,18]],\"sat\":[],\"sun\":[]}'::jsonb"
        )),
        sa.Column("daily_reply_quota", sa.Integer, nullable=False, server_default="5"),
        sa.Column("per_chat_daily_quota", sa.Integer, nullable=False, server_default="2"),
        sa.Column("per_chat_cooldown_minutes", sa.Integer, nullable=False, server_default="120"),
        sa.Column("daily_chitchat_quota", sa.Integer, nullable=False, server_default="7"),
        sa.Column("observation_window_seconds_range", JSONB(), nullable=False,
                  server_default=sa.text("'[60,900]'::jsonb")),
        sa.Column("typing_delay_seconds_range", JSONB(), nullable=False,
                  server_default=sa.text("'[30,120]'::jsonb")),
        sa.Column("param_version", sa.Text, nullable=False, server_default="v1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # === chitchat_pool ===
    op.create_table(
        "chitchat_pool",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("customer_id", sa.Integer, sa.ForeignKey("customer.id"), nullable=True),
        sa.Column("topic_category", sa.Text, nullable=True),
        sa.Column("prompt_template", sa.Text, nullable=False),
        sa.Column("tags", JSONB(), nullable=True),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # === chitchat_log ===
    op.create_table(
        "chitchat_log",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("account_id", sa.Integer, sa.ForeignKey("account.id"), nullable=False),
        sa.Column("chat_id", sa.BigInteger, nullable=False),
        sa.Column("topic_id", sa.Integer, sa.ForeignKey("chitchat_pool.id"), nullable=True),
        sa.Column("sent_text", sa.Text, nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_chitchat_log_day ON chitchat_log "
        "(account_id, topic_id, chat_id, (sent_at::date))"
    )

    # === ab_experiments ===
    op.create_table(
        "ab_experiments",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.Text, unique=True, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("scope", sa.Text, nullable=False),
        sa.Column("scope_value", sa.Integer, nullable=True),
        sa.Column("variants", JSONB(), nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="draft"),
        sa.Column("primary_metric", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("ab_experiments")
    op.drop_index("uq_chitchat_log_day", table_name="chitchat_log")
    op.drop_table("chitchat_log")
    op.drop_table("chitchat_pool")
    op.drop_table("worker_personas")
    op.drop_index("idx_case_studies_customer", table_name="case_studies")
    op.drop_index("idx_case_studies_emb", table_name="case_studies")
    op.drop_table("case_studies")
    op.drop_index("idx_pending_replies_dedup", table_name="pending_replies")
    op.drop_index("idx_pending_replies_scan", table_name="pending_replies")
    op.drop_table("pending_replies")
    op.drop_column("keywordmonitor", "keyword_filters")
    op.drop_column("customers", "param_version")
    op.drop_column("customers", "lead_detector_thresholds")
    op.drop_column("customers", "icp_profile_embedding")
    op.drop_column("customers", "icp_profile_text")
```

> **注意：** 表名大小写要与现有迁移一致。`customer`/`account`/`keywordmonitor`/`lead` 的实际表名以 `\dt` 查到的为准。如查到的是 `customers` 复数则相应调整 `ForeignKey` 引用。

- [ ] **Step 1.3: 应用迁移到 dev DB 验证 upgrade**

```bash
cd /var/tgsc/backend
alembic upgrade head
```

Expected: 无 error，最后输出 `INFO  [alembic.runtime.migration] Running upgrade a3b4c5d6e7f8 -> <REV>, group_ai_sales_phase1`。

随后验证：
```bash
psql $DATABASE_URL -c "\d pending_replies" | head -30
psql $DATABASE_URL -c "\d worker_personas" | head -10
psql $DATABASE_URL -c "SELECT column_name FROM information_schema.columns WHERE table_name='customers' AND column_name IN ('icp_profile_text','icp_profile_embedding','lead_detector_thresholds','param_version');"
```

Expected: pending_replies 各字段齐, customers 4 个新字段都列出。

- [ ] **Step 1.4: 写迁移可逆测试**

`backend/tests/test_group_ai_phase1_migration.py`:

```python
"""验证 group_ai_sales_phase1 迁移可正反两向跑通"""
import subprocess
import os


def _alembic(*args):
    cwd = os.path.join(os.path.dirname(__file__), "..")
    return subprocess.run(
        ["alembic", *args], cwd=cwd,
        env={**os.environ}, capture_output=True, text=True, check=True,
    )


def test_migration_round_trip():
    """upgrade head -> downgrade -1 -> upgrade head 不报错"""
    _alembic("upgrade", "head")
    _alembic("downgrade", "-1")
    _alembic("upgrade", "head")
```

- [ ] **Step 1.5: 跑测试**

```bash
cd /var/tgsc/backend
pytest tests/test_group_ai_phase1_migration.py -v
```

Expected: PASS。如果 down 失败排查约束顺序。

- [ ] **Step 1.6: 提交**

```bash
git add backend/alembic/versions/<REV>_group_ai_sales_phase1.py \
        backend/tests/test_group_ai_phase1_migration.py
git commit -m "feat(group-ai/phase1): alembic migration for 5 tables + 4 columns"
```

---

## Task 2: SQLModel — Customer / Monitor 扩展字段

**Files:**
- Modify: `backend/app/models/customer.py`
- Modify: `backend/app/models/keyword_monitor.py`
- Test: `backend/tests/test_models_phase1_extension.py`

- [ ] **Step 2.1: 写测试 —— customer 新字段读写**

`backend/tests/test_models_phase1_extension.py`:

```python
"""验证 Phase 1 model 扩展字段读写"""
import pytest
from sqlmodel import Session, select
from app.core.database import engine
from app.models.customer import Customer


def test_customer_icp_fields_readable(db_session: Session):
    c = db_session.exec(select(Customer).limit(1)).first()
    if c is None:
        pytest.skip("no customer rows in test DB")
    # 新字段访问不抛
    assert c.icp_profile_text is None or isinstance(c.icp_profile_text, str)
    assert isinstance(c.lead_detector_thresholds, dict)
    assert "layer2_sim" in c.lead_detector_thresholds
    assert c.param_version == "v1" or isinstance(c.param_version, str)


def test_customer_icp_write_roundtrip(db_session: Session):
    c = db_session.exec(select(Customer).limit(1)).first()
    if c is None:
        pytest.skip("no customer rows")
    c.icp_profile_text = "test ICP"
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    assert c.icp_profile_text == "test ICP"
    # cleanup
    c.icp_profile_text = None
    db_session.add(c)
    db_session.commit()
```

- [ ] **Step 2.2: 跑测试 —— 应失败**

```bash
pytest backend/tests/test_models_phase1_extension.py::test_customer_icp_fields_readable -v
```

Expected: FAIL with `AttributeError: 'Customer' object has no attribute 'icp_profile_text'`。

- [ ] **Step 2.3: 扩展 Customer SQLModel**

修改 `backend/app/models/customer.py`，在 `class Customer(...)` 字段定义末尾、`Config` 之前加：

```python
from typing import Any
from sqlalchemy import Column, Text
from sqlalchemy.dialects.postgresql import JSONB

# 在合适的 import 区块上方加（如果已有 import 跳过）
try:
    from pgvector.sqlalchemy import Vector as _PGVector
except ImportError:
    _PGVector = None
```

在 Customer 类字段区域加：

```python
    # === Phase 1 群内 AI 销售员 ===
    icp_profile_text: Optional[str] = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    # icp_profile_embedding 用 vector(768); SQLModel 不直接支持 → 用原生 Column
    if _PGVector is not None:
        icp_profile_embedding: Optional[Any] = Field(
            default=None, sa_column=Column(_PGVector(768), nullable=True)
        )
    lead_detector_thresholds: dict = Field(
        default_factory=lambda: {"layer2_sim": 0.55, "layer3_score": 60, "layer3_confidence": 0.7},
        sa_column=Column(JSONB, nullable=False, server_default=(
            '{"layer2_sim":0.55,"layer3_score":60,"layer3_confidence":0.7}'
        )),
    )
    param_version: str = Field(
        default="v1", sa_column=Column(Text, nullable=False, server_default="v1")
    )
```

> 现有 `customer.py` 是 SQLModel 风格但用 `Field()` 表达字段。`vector` 类型不能用纯 Field —— 必须用 `sa_column=Column(...)`。如果 PR import 找不到 `Any`，把它加到 typing import 里。

- [ ] **Step 2.4: 扩展 KeywordMonitor SQLModel**

修改 `backend/app/models/keyword_monitor.py`，在 `KeywordMonitorBase` 类合适位置加：

```python
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB

# 类字段区域：
    # Phase 1 新增 - 结构化关键词过滤 (include/exclude/mode)
    # mode: 'any' = include 任一命中即通过; 'all' = include 全部命中
    keyword_filters: Optional[dict] = Field(
        default=None, sa_column=Column(JSONB, nullable=True)
    )
```

- [ ] **Step 2.5: 跑测试 —— 应通过**

```bash
pytest backend/tests/test_models_phase1_extension.py -v
```

Expected: PASS。

- [ ] **Step 2.6: 提交**

```bash
git add backend/app/models/customer.py \
        backend/app/models/keyword_monitor.py \
        backend/tests/test_models_phase1_extension.py
git commit -m "feat(group-ai/phase1): SQLModel extensions for ICP + keyword_filters"
```

---

## Task 3: 新建 SQLModel —— PendingReply

**Files:**
- Create: `backend/app/models/pending_reply.py`
- Test: `backend/tests/test_pending_reply_model.py`

- [ ] **Step 3.1: 写测试**

`backend/tests/test_pending_reply_model.py`:

```python
"""PendingReply CRUD + status 状态机字段验证"""
from datetime import datetime, timezone, timedelta
from sqlmodel import Session, select
from app.models.pending_reply import PendingReply, PendingReplyStatus


def test_pending_reply_create_with_observing_status(db_session: Session):
    pr = PendingReply(
        customer_id=1, monitor_id=1,
        chat_id=-100123456, message_id=42, source_user_id=9999,
        source_text="想买 100k USDT",
        layer1_matched={"matched": ["USDT", "100k"]},
        status=PendingReplyStatus.OBSERVING,
        fire_at=datetime.now(timezone.utc) + timedelta(seconds=120),
    )
    db_session.add(pr)
    db_session.commit()
    db_session.refresh(pr)
    assert pr.id is not None
    assert pr.status == PendingReplyStatus.OBSERVING
    assert pr.layer1_matched == {"matched": ["USDT", "100k"]}


def test_pending_reply_status_enum_values():
    # 必须包含所有 spec §4.2 定义的状态
    expected = {
        "observing", "risk_check", "composing", "sent",
        "skipped_human_replied", "skipped_throttled", "skipped_dup",
        "skipped_borderline", "skipped_no_account", "failed", "suggested",
    }
    actual = {s.value for s in PendingReplyStatus}
    assert expected == actual
```

- [ ] **Step 3.2: 跑测试 —— 应失败**

```bash
pytest backend/tests/test_pending_reply_model.py -v
```

Expected: ImportError on `app.models.pending_reply`。

- [ ] **Step 3.3: 实装 PendingReply 模型**

`backend/app/models/pending_reply.py`:

```python
"""
PendingReply — 群内 AI 销售员管线的状态机表。

每条群消息命中 LeadDetector 后入一行, Celery beat 按 fire_at 扫描推进:
observing -> risk_check -> composing -> sent (或 skipped_*/failed/suggested)
"""
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from sqlalchemy import BigInteger, Column, DateTime, Float, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class PendingReplyStatus(str, Enum):
    OBSERVING = "observing"
    RISK_CHECK = "risk_check"
    COMPOSING = "composing"
    SENT = "sent"
    SKIPPED_HUMAN_REPLIED = "skipped_human_replied"
    SKIPPED_THROTTLED = "skipped_throttled"
    SKIPPED_DUP = "skipped_dup"
    SKIPPED_BORDERLINE = "skipped_borderline"
    SKIPPED_NO_ACCOUNT = "skipped_no_account"
    FAILED = "failed"
    SUGGESTED = "suggested"


class PendingReply(SQLModel, table=True):
    __tablename__ = "pending_replies"

    id: Optional[int] = Field(
        default=None, sa_column=Column(BigInteger, primary_key=True)
    )

    customer_id: int = Field(
        sa_column=Column(Integer, ForeignKey("customer.id"), nullable=False)
    )
    monitor_id: int = Field(
        sa_column=Column(Integer, ForeignKey("keywordmonitor.id"), nullable=False)
    )
    responder_account_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("account.id"), nullable=True),
    )

    chat_id: int = Field(sa_column=Column(BigInteger, nullable=False))
    message_id: int = Field(sa_column=Column(BigInteger, nullable=False))
    source_user_id: int = Field(sa_column=Column(BigInteger, nullable=False))
    source_text: str = Field(sa_column=Column(Text, nullable=False))

    layer1_matched: Optional[dict] = Field(
        default=None, sa_column=Column(JSONB, nullable=True)
    )
    layer2_similarity: Optional[float] = Field(
        default=None, sa_column=Column(Float, nullable=True)
    )
    layer3_score: Optional[int] = Field(
        default=None, sa_column=Column(Integer, nullable=True)
    )
    layer3_needs: Optional[list] = Field(
        default=None, sa_column=Column(JSONB, nullable=True)
    )
    layer3_solution_topic: Optional[str] = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    layer3_confidence: Optional[float] = Field(
        default=None, sa_column=Column(Float, nullable=True)
    )

    status: str = Field(sa_column=Column(Text, nullable=False))
    fire_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    decided_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    sent_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    skip_reason: Optional[str] = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )

    reply_text: Optional[str] = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    lead_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("lead.id"), nullable=True),
    )
    experiment_tag: Optional[str] = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
```

- [ ] **Step 3.4: 跑测试**

```bash
pytest backend/tests/test_pending_reply_model.py -v
```

Expected: PASS。

- [ ] **Step 3.5: 提交**

```bash
git add backend/app/models/pending_reply.py \
        backend/tests/test_pending_reply_model.py
git commit -m "feat(group-ai/phase1): PendingReply SQLModel with status enum"
```

---

## Task 4: 占位模型 —— CaseStudy / WorkerPersona / Chitchat / ABExperiment

> Phase 1 不查询这些表，但模型类要建好以便后续 Phase 直接用。每个文件只放 SQLModel 类，不写业务逻辑。

**Files:**
- Create: `backend/app/models/case_study.py`
- Create: `backend/app/models/worker_persona.py`
- Create: `backend/app/models/chitchat.py`
- Create: `backend/app/models/ab_experiment.py`
- Test: `backend/tests/test_phase1_placeholder_models.py`

- [ ] **Step 4.1: 写测试 —— import 成功 + 表存在**

`backend/tests/test_phase1_placeholder_models.py`:

```python
"""验证 Phase 1 占位模型 import 成功且对应 DB 表存在"""
from sqlmodel import Session, text


def test_models_importable():
    from app.models.case_study import CaseStudy
    from app.models.worker_persona import WorkerPersona
    from app.models.chitchat import ChitchatPool, ChitchatLog
    from app.models.ab_experiment import ABExperiment
    assert CaseStudy.__tablename__ == "case_studies"
    assert WorkerPersona.__tablename__ == "worker_personas"
    assert ChitchatPool.__tablename__ == "chitchat_pool"
    assert ChitchatLog.__tablename__ == "chitchat_log"
    assert ABExperiment.__tablename__ == "ab_experiments"


def test_tables_exist_in_db(db_session: Session):
    rows = db_session.exec(text(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_name IN ('case_studies','worker_personas','chitchat_pool',"
        "'chitchat_log','ab_experiments')"
    )).all()
    names = {r[0] for r in rows}
    assert names == {
        "case_studies", "worker_personas", "chitchat_pool",
        "chitchat_log", "ab_experiments"
    }
```

- [ ] **Step 4.2: 跑 —— 应 ImportError**

```bash
pytest backend/tests/test_phase1_placeholder_models.py -v
```

Expected: FAIL。

- [ ] **Step 4.3: 实装 case_study.py**

`backend/app/models/case_study.py`:

```python
"""CaseStudy — 客户成交案例库（Phase 2 启用查询）。"""
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

try:
    from pgvector.sqlalchemy import Vector as _PGVector
except ImportError:
    _PGVector = None


class CaseStudy(SQLModel, table=True):
    __tablename__ = "case_studies"

    id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, primary_key=True))
    customer_id: int = Field(
        sa_column=Column(Integer, ForeignKey("customer.id"), nullable=False)
    )
    industry: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    deal_size: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    period: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    problem: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    solution: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    outcome: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    tags: Optional[list] = Field(default=None, sa_column=Column(JSONB, nullable=True))

    if _PGVector is not None:
        embedding: Optional[Any] = Field(
            default=None, sa_column=Column(_PGVector(768), nullable=True)
        )

    source: str = Field(sa_column=Column(Text, nullable=False))
    active: bool = Field(default=True, sa_column=Column(Boolean, nullable=False))
    created_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    last_used_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
```

- [ ] **Step 4.4: 实装 worker_persona.py**

`backend/app/models/worker_persona.py`:

```python
"""WorkerPersona — worker 账号的"真人画像"配置（Phase 3 启用读取）。

NOTE: 与 ai_persona.py 中的 AIPersona 是不同概念。
AIPersona = LLM system_prompt 模板（"金牌销售"/"技术分析师"）。
WorkerPersona = 单个 TG 账号的拟真身份（地区/职业/口头禅/活跃时段）。
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


_DEFAULT_ACTIVE_HOURS = {
    "mon": [[9, 18]], "tue": [[9, 18]], "wed": [[9, 18]],
    "thu": [[9, 18]], "fri": [[9, 18]], "sat": [], "sun": [],
}


class WorkerPersona(SQLModel, table=True):
    __tablename__ = "worker_personas"

    id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, primary_key=True))
    account_id: int = Field(
        sa_column=Column(Integer, ForeignKey("account.id"), unique=True, nullable=False)
    )
    customer_id: int = Field(
        sa_column=Column(Integer, ForeignKey("customer.id"), nullable=False)
    )

    display_name: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    age_range: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    region: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    occupation: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    speaking_style: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))

    catchphrases: list = Field(
        default_factory=list, sa_column=Column(JSONB, nullable=False)
    )
    active_hours: dict = Field(
        default_factory=lambda: dict(_DEFAULT_ACTIVE_HOURS),
        sa_column=Column(JSONB, nullable=False),
    )

    daily_reply_quota: int = Field(default=5, sa_column=Column(Integer, nullable=False))
    per_chat_daily_quota: int = Field(default=2, sa_column=Column(Integer, nullable=False))
    per_chat_cooldown_minutes: int = Field(default=120, sa_column=Column(Integer, nullable=False))
    daily_chitchat_quota: int = Field(default=7, sa_column=Column(Integer, nullable=False))

    observation_window_seconds_range: list = Field(
        default_factory=lambda: [60, 900], sa_column=Column(JSONB, nullable=False)
    )
    typing_delay_seconds_range: list = Field(
        default_factory=lambda: [30, 120], sa_column=Column(JSONB, nullable=False)
    )

    param_version: str = Field(default="v1", sa_column=Column(Text, nullable=False))
    created_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=False),
    )
```

- [ ] **Step 4.5: 实装 chitchat.py**

`backend/app/models/chitchat.py`:

```python
"""ChitchatPool / ChitchatLog — 闲聊话题库与发送记录（Phase 3 启用）。"""
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class ChitchatPool(SQLModel, table=True):
    __tablename__ = "chitchat_pool"

    id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, primary_key=True))
    customer_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("customer.id"), nullable=True),
    )
    topic_category: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    prompt_template: str = Field(sa_column=Column(Text, nullable=False))
    tags: Optional[list] = Field(default=None, sa_column=Column(JSONB, nullable=True))
    active: bool = Field(default=True, sa_column=Column(Boolean, nullable=False))
    created_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class ChitchatLog(SQLModel, table=True):
    __tablename__ = "chitchat_log"

    id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, primary_key=True))
    account_id: int = Field(
        sa_column=Column(Integer, ForeignKey("account.id"), nullable=False)
    )
    chat_id: int = Field(sa_column=Column(BigInteger, nullable=False))
    topic_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("chitchat_pool.id"), nullable=True),
    )
    sent_text: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    sent_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=False),
    )
```

- [ ] **Step 4.6: 实装 ab_experiment.py**

`backend/app/models/ab_experiment.py`:

```python
"""ABExperiment — A/B 实验定义（Phase 5 启用）。"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class ABExperiment(SQLModel, table=True):
    __tablename__ = "ab_experiments"

    id: Optional[int] = Field(default=None, sa_column=Column(Integer, primary_key=True))
    name: str = Field(sa_column=Column(Text, unique=True, nullable=False))
    description: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    scope: str = Field(sa_column=Column(Text, nullable=False))
    scope_value: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
    variants: list = Field(default_factory=list, sa_column=Column(JSONB, nullable=False))
    status: str = Field(default="draft", sa_column=Column(Text, nullable=False))
    primary_metric: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    started_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    ended_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
```

- [ ] **Step 4.7: 跑测试**

```bash
pytest backend/tests/test_phase1_placeholder_models.py -v
```

Expected: PASS。

- [ ] **Step 4.8: 提交**

```bash
git add backend/app/models/case_study.py \
        backend/app/models/worker_persona.py \
        backend/app/models/chitchat.py \
        backend/app/models/ab_experiment.py \
        backend/tests/test_phase1_placeholder_models.py
git commit -m "feat(group-ai/phase1): placeholder SQLModels for cases/persona/chitchat/ab"
```

---

## Task 5: 配置常量 + 兜底 Persona

**Files:**
- Create: `backend/app/core/group_reply_config.py`
- Test: `backend/tests/test_group_reply_config.py`

- [ ] **Step 5.1: 写测试**

`backend/tests/test_group_reply_config.py`:

```python
from app.core.group_reply_config import (
    DEFAULT_PERSONA, OBSERVATION_WINDOW_SECONDS, TYPING_DELAY_SECONDS,
    GROUP_AI_REPLY_ENABLED, BILLING_PER_REPLY_USD,
)


def test_default_persona_has_required_fields():
    required = {
        "display_name", "speaking_style", "daily_reply_quota",
        "per_chat_daily_quota", "per_chat_cooldown_minutes",
        "daily_chitchat_quota",
        "observation_window_seconds_range", "typing_delay_seconds_range",
    }
    assert required.issubset(DEFAULT_PERSONA.keys())


def test_default_persona_conservative_values():
    """未配置 persona 时使用保守 default"""
    assert DEFAULT_PERSONA["daily_reply_quota"] == 3
    assert DEFAULT_PERSONA["per_chat_daily_quota"] == 1
    assert DEFAULT_PERSONA["per_chat_cooldown_minutes"] == 240
    assert DEFAULT_PERSONA["daily_chitchat_quota"] == 0


def test_billing_amount():
    assert BILLING_PER_REPLY_USD == 0.50


def test_observation_window_default_range():
    assert OBSERVATION_WINDOW_SECONDS == (60, 900)


def test_typing_delay_default_range():
    assert TYPING_DELAY_SECONDS == (30, 120)
```

- [ ] **Step 5.2: 跑测试 —— 应失败**

```bash
pytest backend/tests/test_group_reply_config.py -v
```

Expected: ImportError。

- [ ] **Step 5.3: 实装 config**

`backend/app/core/group_reply_config.py`:

```python
"""群内 AI 销售员管线 Phase 1 共享配置 + 兜底 persona。

参考: docs/superpowers/specs/2026-05-28-group-ai-sales-presence-design.md §6.3
"""
import os


# ENV 主开关 (灰度阶段全局 off)
GROUP_AI_REPLY_ENABLED = os.getenv("GROUP_AI_REPLY_ENABLED", "false").lower() == "true"

# 计费 (per sent reply, USD)
BILLING_PER_REPLY_USD = 0.50

# 兜底范围 (未配置 worker_persona 时用)
OBSERVATION_WINDOW_SECONDS = (60, 900)    # spec §1.3
TYPING_DELAY_SECONDS = (30, 120)          # spec §1.3

# 兜底 persona — 保守值, 比 spec §4.2 表 DDL 默认更保守 (未配置即降级)
DEFAULT_PERSONA = {
    "display_name": "用户",
    "region": None,
    "occupation": None,
    "speaking_style": "casual",
    "catchphrases": [],
    "active_hours": {
        "mon": [[9, 22]], "tue": [[9, 22]], "wed": [[9, 22]],
        "thu": [[9, 22]], "fri": [[9, 22]], "sat": [[10, 20]], "sun": [[10, 20]],
    },
    "daily_reply_quota": 3,                    # 保守
    "per_chat_daily_quota": 1,                 # 保守
    "per_chat_cooldown_minutes": 240,          # 保守
    "daily_chitchat_quota": 0,                 # Phase 1 不闲聊
    "observation_window_seconds_range": [120, 900],
    "typing_delay_seconds_range": [45, 120],
}

# Celery beat 扫描频率
SCAN_INTERVAL_SECONDS = 30
```

- [ ] **Step 5.4: 跑测试**

```bash
pytest backend/tests/test_group_reply_config.py -v
```

Expected: PASS。

- [ ] **Step 5.5: 提交**

```bash
git add backend/app/core/group_reply_config.py \
        backend/tests/test_group_reply_config.py
git commit -m "feat(group-ai/phase1): config + fallback persona constants"
```

---

## Task 6: LeadDetector Layer 1（keyword_filters）

**Files:**
- Create: `backend/app/services/lead_detector.py`
- Test: `backend/tests/test_lead_detector_layer1.py`

- [ ] **Step 6.1: 写测试**

`backend/tests/test_lead_detector_layer1.py`:

```python
"""LeadDetector Layer 1 (keyword filter) 单元测试"""
from app.services.lead_detector import layer1_keyword_match


def test_layer1_include_any_hits():
    filters = {"include": ["USDT", "比特币"], "exclude": [], "mode": "any"}
    result = layer1_keyword_match("想买 100k USDT 一次", filters)
    assert result["pass"] is True
    assert result["matched"] == ["USDT"]


def test_layer1_include_any_misses():
    filters = {"include": ["USDT"], "exclude": [], "mode": "any"}
    result = layer1_keyword_match("今天天气真不错", filters)
    assert result["pass"] is False
    assert result["matched"] == []


def test_layer1_exclude_blocks():
    filters = {"include": ["USDT"], "exclude": ["免费"], "mode": "any"}
    result = layer1_keyword_match("USDT 免费教学", filters)
    assert result["pass"] is False
    assert "免费" in result.get("excluded", [])


def test_layer1_mode_all():
    filters = {"include": ["USDT", "求"], "exclude": [], "mode": "all"}
    assert layer1_keyword_match("求 USDT 渠道", filters)["pass"] is True
    assert layer1_keyword_match("有 USDT 卖", filters)["pass"] is False


def test_layer1_case_insensitive():
    filters = {"include": ["usdt"], "exclude": [], "mode": "any"}
    assert layer1_keyword_match("找 USDT 大户", filters)["pass"] is True


def test_layer1_fallback_to_legacy_keyword_field():
    """keyword_filters=None 时降级用旧 keyword 字段"""
    result = layer1_keyword_match(
        "找 USDT 大户", filters=None, legacy_keyword="USDT"
    )
    assert result["pass"] is True
    assert result["matched"] == ["USDT"]


def test_layer1_empty_filters_and_no_legacy():
    """全空 → 不通过 (不能默认全过)"""
    assert layer1_keyword_match("任何消息", filters=None, legacy_keyword=None)["pass"] is False
```

- [ ] **Step 6.2: 跑 —— 应 ImportError**

```bash
pytest backend/tests/test_lead_detector_layer1.py -v
```

Expected: FAIL。

- [ ] **Step 6.3: 实装 lead_detector.py（仅 Layer 1）**

`backend/app/services/lead_detector.py`:

```python
"""
LeadDetector — 群消息业务线索三层过滤。

Phase 1: 仅实现 Layer 1 (keyword_filters)
Phase 2: 加 Layer 2 (ICP embedding) + Layer 3 (LLM scoring)

参考: spec §3
"""
from typing import Optional


def layer1_keyword_match(
    text: str,
    filters: Optional[dict],
    legacy_keyword: Optional[str] = None,
) -> dict:
    """
    Layer 1: include/exclude 关键词过滤 (大小写不敏感)。

    Args:
        text: 群消息原文
        filters: {"include": [...], "exclude": [...], "mode": "any"|"all"}
                 None → 降级用 legacy_keyword
        legacy_keyword: monitor.keyword 旧字段, 兼容路径

    Returns:
        {"pass": bool, "matched": [str], "excluded": [str]}
    """
    text_lower = text.lower()

    if filters is None:
        # 降级路径: 旧 keyword 字段
        if not legacy_keyword:
            return {"pass": False, "matched": [], "excluded": []}
        kw_lower = legacy_keyword.lower()
        hit = kw_lower in text_lower
        return {
            "pass": hit,
            "matched": [legacy_keyword] if hit else [],
            "excluded": [],
        }

    include = filters.get("include", []) or []
    exclude = filters.get("exclude", []) or []
    mode = filters.get("mode", "any")

    # exclude 优先
    excluded_hits = [w for w in exclude if w.lower() in text_lower]
    if excluded_hits:
        return {"pass": False, "matched": [], "excluded": excluded_hits}

    if not include:
        return {"pass": False, "matched": [], "excluded": []}

    matched = [w for w in include if w.lower() in text_lower]

    if mode == "all":
        passed = len(matched) == len(include)
    else:  # any
        passed = len(matched) > 0

    return {"pass": passed, "matched": matched, "excluded": []}
```

- [ ] **Step 6.4: 跑测试**

```bash
pytest backend/tests/test_lead_detector_layer1.py -v
```

Expected: 全部 PASS（7 个测试）。

- [ ] **Step 6.5: 提交**

```bash
git add backend/app/services/lead_detector.py \
        backend/tests/test_lead_detector_layer1.py
git commit -m "feat(group-ai/phase1): LeadDetector Layer 1 keyword filter"
```

---

## Task 7: group_reply_pipeline 入口

**Files:**
- Create: `backend/app/services/group_reply_pipeline.py`
- Test: `backend/tests/test_group_reply_pipeline.py`

- [ ] **Step 7.1: 写测试 —— 早返路径**

`backend/tests/test_group_reply_pipeline.py`:

```python
"""group_reply_pipeline.entrypoint 早返路径 + 命中入库"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from app.services.group_reply_pipeline import entrypoint


class FakeMsg:
    def __init__(self, text="测试", chat_id=-100, id=1, sender_id=999):
        self.text = text
        self.chat_id = chat_id
        self.id = id
        self.sender_id = sender_id


class FakeAcc:
    def __init__(self, customer_id=1, role="worker"):
        self.id = 10
        self.customer_id = customer_id
        self.role = role


class FakeMonitor:
    def __init__(self, customer_id=1, keyword_filters=None, keyword=None):
        self.id = 5
        self.customer_id = customer_id
        self.keyword_filters = keyword_filters
        self.keyword = keyword


@pytest.mark.asyncio
async def test_entrypoint_skips_collector_role():
    """role=='collector' → 立即返回, 不写 DB"""
    msg = FakeMsg()
    acc = FakeAcc(role="collector")
    monitor = FakeMonitor()
    with patch("app.services.group_reply_pipeline._insert_pending_reply") as mocked:
        result = await entrypoint(msg, acc, monitor)
    assert result == {"skipped": "collector_role"}
    mocked.assert_not_called()


@pytest.mark.asyncio
async def test_entrypoint_skips_no_customer():
    msg = FakeMsg()
    acc = FakeAcc(customer_id=None)
    monitor = FakeMonitor()
    with patch("app.services.group_reply_pipeline._insert_pending_reply") as mocked:
        result = await entrypoint(msg, acc, monitor)
    assert result == {"skipped": "no_customer"}
    mocked.assert_not_called()


@pytest.mark.asyncio
async def test_entrypoint_skips_feature_off():
    msg = FakeMsg()
    acc = FakeAcc()
    monitor = FakeMonitor()
    with patch("app.services.group_reply_pipeline.GROUP_AI_REPLY_ENABLED", False), \
         patch("app.services.group_reply_pipeline._insert_pending_reply") as mocked:
        result = await entrypoint(msg, acc, monitor)
    assert result == {"skipped": "feature_off"}
    mocked.assert_not_called()


@pytest.mark.asyncio
async def test_entrypoint_skips_layer1_miss():
    msg = FakeMsg(text="今天天气真好")
    acc = FakeAcc()
    monitor = FakeMonitor(keyword_filters={"include": ["USDT"], "exclude": [], "mode": "any"})
    with patch("app.services.group_reply_pipeline.GROUP_AI_REPLY_ENABLED", True), \
         patch("app.services.group_reply_pipeline._insert_pending_reply") as mocked:
        result = await entrypoint(msg, acc, monitor)
    assert result == {"skipped": "layer1_miss"}
    mocked.assert_not_called()


@pytest.mark.asyncio
async def test_entrypoint_layer1_hit_inserts_pending_reply():
    msg = FakeMsg(text="求 USDT 100k", chat_id=-100, id=42, sender_id=999)
    acc = FakeAcc()
    monitor = FakeMonitor(keyword_filters={"include": ["USDT"], "exclude": [], "mode": "any"})
    mock_pr = MagicMock(id=777)
    with patch("app.services.group_reply_pipeline.GROUP_AI_REPLY_ENABLED", True), \
         patch("app.services.group_reply_pipeline._insert_pending_reply",
               new=AsyncMock(return_value=mock_pr)) as mocked:
        result = await entrypoint(msg, acc, monitor)
    assert result == {"pending_reply_id": 777}
    assert mocked.call_count == 1
    kwargs = mocked.call_args.kwargs
    assert kwargs["chat_id"] == -100
    assert kwargs["message_id"] == 42
    assert kwargs["source_user_id"] == 999
    assert kwargs["source_text"] == "求 USDT 100k"
    assert kwargs["layer1_matched"] == {"matched": ["USDT"]}
    # observation window 在 (60, 900) 之间
    assert 60 <= kwargs["observation_window_seconds"] <= 900
```

- [ ] **Step 7.2: 跑 —— 应 ImportError**

```bash
pytest backend/tests/test_group_reply_pipeline.py -v
```

Expected: FAIL。

- [ ] **Step 7.3: 实装 pipeline.entrypoint**

`backend/app/services/group_reply_pipeline.py`:

```python
"""
group_reply_pipeline — 群内 AI 销售员管线入口。

每条群消息从 listener_service._handle_message 调一次本入口。
本模块只做编排：早返 → Layer 1 → 入 pending_replies。Layer 2/3 在 Phase 2 加。

Phase 1 流程:
  msg → entrypoint(msg, account, monitor) →
    (skip collector / no_customer / feature_off) →
    layer1_keyword_match → (skip if miss) →
    INSERT pending_replies(status='observing', fire_at=now+random(60..900))

参考: spec §2.1, §3.1
"""
import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.core.database import get_session
from app.core.group_reply_config import (
    DEFAULT_PERSONA, GROUP_AI_REPLY_ENABLED,
)
from app.models.pending_reply import PendingReply, PendingReplyStatus
from app.services.lead_detector import layer1_keyword_match

logger = logging.getLogger(__name__)


async def entrypoint(msg, account, monitor) -> dict:
    """
    Args:
        msg: Telethon Message 对象 (须含 text, chat_id, id, sender_id)
        account: app.models.account.Account (含 customer_id, role)
        monitor: app.models.keyword_monitor.KeywordMonitor (含 keyword_filters, keyword)

    Returns:
        {"skipped": <reason>} 或 {"pending_reply_id": <id>}
    """
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

    # Layer 1
    layer1 = layer1_keyword_match(
        text,
        filters=getattr(monitor, "keyword_filters", None),
        legacy_keyword=getattr(monitor, "keyword", None),
    )
    if not layer1["pass"]:
        return {"skipped": "layer1_miss"}

    # 选 observation window (用 customer 默认; persona 维度在 Phase 3 接入)
    obs_min, obs_max = DEFAULT_PERSONA["observation_window_seconds_range"]
    obs_seconds = random.randint(obs_min, obs_max)

    pr = await _insert_pending_reply(
        customer_id=customer_id,
        monitor_id=monitor.id,
        chat_id=msg.chat_id,
        message_id=msg.id,
        source_user_id=msg.sender_id,
        source_text=text,
        layer1_matched={"matched": layer1["matched"]},
        observation_window_seconds=obs_seconds,
    )
    logger.info(
        "group_reply_pipeline: pending_reply id=%s queued (window=%ss)",
        pr.id, obs_seconds,
    )
    return {"pending_reply_id": pr.id}


async def _insert_pending_reply(
    *,
    customer_id: int,
    monitor_id: int,
    chat_id: int,
    message_id: int,
    source_user_id: int,
    source_text: str,
    layer1_matched: dict,
    observation_window_seconds: int,
) -> PendingReply:
    now = datetime.now(timezone.utc)
    pr = PendingReply(
        customer_id=customer_id,
        monitor_id=monitor_id,
        chat_id=chat_id,
        message_id=message_id,
        source_user_id=source_user_id,
        source_text=source_text,
        layer1_matched=layer1_matched,
        status=PendingReplyStatus.OBSERVING.value,
        fire_at=now + timedelta(seconds=observation_window_seconds),
        created_at=now,
    )
    async with get_session() as session:
        session.add(pr)
        await session.commit()
        await session.refresh(pr)
    return pr
```

> **注意：** 如果项目使用同步 SQLModel session 而非 `async with get_session()`，把 `_insert_pending_reply` 改成同步形式或用 `run_in_executor`。先在仓库 grep `get_session` 与同步/异步用法对齐。

- [ ] **Step 7.4: 跑测试**

```bash
pytest backend/tests/test_group_reply_pipeline.py -v
```

Expected: 5 个测试全 PASS。

- [ ] **Step 7.5: 提交**

```bash
git add backend/app/services/group_reply_pipeline.py \
        backend/tests/test_group_reply_pipeline.py
git commit -m "feat(group-ai/phase1): pipeline entrypoint with early-return + Layer1 + queue"
```

---

## Task 8: listener_service 一行 hook

**Files:**
- Modify: `backend/app/services/listener_service.py:70` (`_handle_message`)
- Test: `backend/tests/test_listener_pipeline_hook.py`

- [ ] **Step 8.1: 读取上下文确定 hook 位置**

```bash
sed -n '60,130p' /var/tgsc/backend/app/services/listener_service.py
```

记下 `_handle_message` 中"群消息已通过 keyword/intercept 等现有处理后"的合适插入点（通常在结束 return 之前、或在 keyword_monitor 命中分支后）。如果现有逻辑里 monitor 命中已经触发了 intercept_service / keyword_monitor，**不要重复**——group_reply_pipeline 应在监控命中分支处与 intercept 并行触发，且仅当 chat 是群（不是私聊）时触发。

- [ ] **Step 8.2: 写测试**

`backend/tests/test_listener_pipeline_hook.py`:

```python
"""listener._handle_message 调 group_reply_pipeline.entrypoint"""
import pytest
from unittest.mock import AsyncMock, patch

from app.services.listener_service import ListenerService


class FakeGroupMsg:
    def __init__(self):
        self.text = "求 USDT"
        self.chat_id = -100123
        self.id = 1
        self.sender_id = 999
        self.is_group = True  # 假设有此属性; 否则用 chat_id < 0 区分


@pytest.mark.asyncio
async def test_handle_message_calls_pipeline_for_group():
    """收到群消息且有 monitor 命中时, 应调 group_reply_pipeline.entrypoint"""
    svc = ListenerService()
    msg = FakeGroupMsg()
    with patch(
        "app.services.listener_service.group_reply_pipeline.entrypoint",
        new=AsyncMock(return_value={"pending_reply_id": 1}),
    ) as mocked:
        # 调用方式视 _handle_message 签名而定; 示例:
        await svc._handle_message(client=None, message=msg)
    # 至少调一次 (可能匹配多个 monitor)
    assert mocked.call_count >= 1
```

> 实测前先看 `_handle_message` 的真实签名和它内部如何枚举 monitors。如果它不接受 `client=None`，调整调用。如果它只针对私聊有逻辑，这个测试需要 mock 出群消息上下文（如 `MessageContext`）。

- [ ] **Step 8.3: 跑 —— 应失败（hook 还未加）**

```bash
pytest backend/tests/test_listener_pipeline_hook.py -v
```

Expected: FAIL，mocked 调用次数 0。

- [ ] **Step 8.4: 在 listener_service 加 hook**

修改 `backend/app/services/listener_service.py`，在文件顶部 import 区域加：

```python
from app.services import group_reply_pipeline
```

在 `_handle_message` 内找到"对每个匹配的 monitor 做处理"的循环（通常类似 `for monitor in matched_monitors:` 或 `if keyword_hit:`），在该循环内、与 intercept/keyword 自动回复**并行**插入一行：

```python
# === Phase 1 群内 AI 销售员管线触发 ===
# 与现有 intercept / keyword auto_reply 并行, 不互斥 (两者目标不同)
try:
    await group_reply_pipeline.entrypoint(message, account, monitor)
except Exception:
    logger.exception("group_reply_pipeline failed (non-blocking)")
```

> **关键：** 用 try/except 包住，不让新管线异常影响现有 listener 路径。日志 warn 即可。

- [ ] **Step 8.5: 跑测试**

```bash
pytest backend/tests/test_listener_pipeline_hook.py -v
```

Expected: PASS。

- [ ] **Step 8.6: 跑 listener 现有回归**

```bash
pytest backend/tests/ -k listener -v
```

Expected: 既有 listener 测试无回归。

- [ ] **Step 8.7: 提交**

```bash
git add backend/app/services/listener_service.py \
        backend/tests/test_listener_pipeline_hook.py
git commit -m "feat(group-ai/phase1): listener hook into group_reply_pipeline"
```

---

## Task 9: RiskController 基础规则

**Files:**
- Create: `backend/app/services/risk_controller.py`
- Test: `backend/tests/test_risk_controller_phase1.py`

> Phase 1 只做 3 条规则：①同线索 48h 去重；②账号日额；③同账号同群 cooldown。**不做**真人接话检测（Phase 3）、active_hours（Phase 3）、加权选号（Phase 3 改进；P1 用兜底「同 customer 的第一个 worker」）。

- [ ] **Step 9.1: 写测试**

`backend/tests/test_risk_controller_phase1.py`:

```python
"""RiskController Phase 1 单元测试 — 3 条规则"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

from app.services.risk_controller import RiskDecision, decide_phase1
from app.models.pending_reply import PendingReplyStatus


def _pr(**overrides):
    base = dict(
        id=1, customer_id=1, monitor_id=1, chat_id=-100,
        source_user_id=9999, source_text="求 USDT",
        status=PendingReplyStatus.OBSERVING.value,
        created_at=datetime.now(timezone.utc) - timedelta(minutes=2),
    )
    base.update(overrides)
    return MagicMock(**base)


def _candidate_acc(id=10, customer_id=1):
    return MagicMock(id=id, customer_id=customer_id, role="worker", status="active")


def test_decide_skip_dup_within_48h():
    pr = _pr()
    sent_recently = [_pr(status=PendingReplyStatus.SENT.value, sent_at=datetime.now(timezone.utc) - timedelta(hours=20))]
    decision = decide_phase1(
        pending=pr,
        candidate_accounts=[_candidate_acc()],
        same_lead_sent_within_48h=sent_recently,
        account_daily_sent_count={10: 0},
        account_last_sent_in_chat={(10, -100): None},
        cooldown_minutes=120,
        daily_quota=5,
    )
    assert decision.action == "skip"
    assert decision.skip_reason == "skipped_dup"


def test_decide_skip_throttled_when_no_candidate():
    pr = _pr()
    decision = decide_phase1(
        pending=pr,
        candidate_accounts=[],  # 无可用账号
        same_lead_sent_within_48h=[],
        account_daily_sent_count={},
        account_last_sent_in_chat={},
        cooldown_minutes=120, daily_quota=5,
    )
    assert decision.action == "skip"
    assert decision.skip_reason == "skipped_no_account"


def test_decide_skip_throttled_all_over_quota():
    pr = _pr()
    decision = decide_phase1(
        pending=pr,
        candidate_accounts=[_candidate_acc()],
        same_lead_sent_within_48h=[],
        account_daily_sent_count={10: 5},  # 已满
        account_last_sent_in_chat={(10, -100): None},
        cooldown_minutes=120, daily_quota=5,
    )
    assert decision.action == "skip"
    assert decision.skip_reason == "skipped_throttled"


def test_decide_skip_cooldown():
    pr = _pr()
    last_sent = datetime.now(timezone.utc) - timedelta(minutes=30)  # 不足 cooldown
    decision = decide_phase1(
        pending=pr,
        candidate_accounts=[_candidate_acc()],
        same_lead_sent_within_48h=[],
        account_daily_sent_count={10: 0},
        account_last_sent_in_chat={(10, -100): last_sent},
        cooldown_minutes=120, daily_quota=5,
    )
    assert decision.action == "skip"
    assert decision.skip_reason == "skipped_throttled"


def test_decide_compose_when_all_pass():
    pr = _pr()
    decision = decide_phase1(
        pending=pr,
        candidate_accounts=[_candidate_acc()],
        same_lead_sent_within_48h=[],
        account_daily_sent_count={10: 0},
        account_last_sent_in_chat={(10, -100): None},
        cooldown_minutes=120, daily_quota=5,
    )
    assert decision.action == "compose"
    assert decision.responder_account_id == 10


def test_decide_compose_picks_first_eligible_when_multiple():
    """Phase 1: 候选多于 1 时, 取第一个 eligible (Phase 3 升级为加权随机)"""
    pr = _pr()
    accs = [_candidate_acc(id=10), _candidate_acc(id=11)]
    decision = decide_phase1(
        pending=pr, candidate_accounts=accs,
        same_lead_sent_within_48h=[],
        account_daily_sent_count={10: 0, 11: 0},
        account_last_sent_in_chat={(10, -100): None, (11, -100): None},
        cooldown_minutes=120, daily_quota=5,
    )
    assert decision.action == "compose"
    assert decision.responder_account_id == 10
```

- [ ] **Step 9.2: 跑 —— 应 ImportError**

```bash
pytest backend/tests/test_risk_controller_phase1.py -v
```

Expected: FAIL。

- [ ] **Step 9.3: 实装 risk_controller.py**

`backend/app/services/risk_controller.py`:

```python
"""
RiskController — pending_reply 决策中央。

Phase 1: 3 条规则
  ① 同线索 48h 去重
  ② 账号日额配额
  ③ 同账号同群 cooldown

Phase 2/3 升级: 真人接话检测 (Phase 3) + active_hours (Phase 3)
              + 加权随机选号 (Phase 3) + Layer 2/3 边界值 (Phase 2)

参考: spec §5
"""
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional

from app.models.pending_reply import PendingReplyStatus


@dataclass
class RiskDecision:
    action: str                              # 'compose' | 'skip'
    skip_reason: Optional[str] = None        # PendingReplyStatus value (skipped_*)
    responder_account_id: Optional[int] = None


def decide_phase1(
    *,
    pending,                                 # PendingReply 实例
    candidate_accounts: list,                # list[Account] 同 customer 的 worker
    same_lead_sent_within_48h: list,         # list[PendingReply] (status=sent, 同 chat+user)
    account_daily_sent_count: dict,          # {account_id: count_today}
    account_last_sent_in_chat: dict,         # {(account_id, chat_id): Optional[datetime]}
    cooldown_minutes: int,
    daily_quota: int,
) -> RiskDecision:
    """Phase 1 决策序列。返回 RiskDecision。"""

    # 规则 ①: 同线索 48h 去重
    if same_lead_sent_within_48h:
        return RiskDecision(
            action="skip",
            skip_reason=PendingReplyStatus.SKIPPED_DUP.value,
        )

    # 规则 ②/③: 筛符合配额 + cooldown 的候选
    now = datetime.now(timezone.utc)
    eligible = []
    for acc in candidate_accounts:
        sent_today = account_daily_sent_count.get(acc.id, 0)
        if sent_today >= daily_quota:
            continue

        last_sent = account_last_sent_in_chat.get((acc.id, pending.chat_id))
        if last_sent is not None:
            elapsed = now - last_sent
            if elapsed < timedelta(minutes=cooldown_minutes):
                continue

        eligible.append(acc)

    if not candidate_accounts:
        return RiskDecision(
            action="skip",
            skip_reason=PendingReplyStatus.SKIPPED_NO_ACCOUNT.value,
        )

    if not eligible:
        return RiskDecision(
            action="skip",
            skip_reason=PendingReplyStatus.SKIPPED_THROTTLED.value,
        )

    # Phase 1: 取第一个 (Phase 3 升级为加权随机)
    chosen = eligible[0]
    return RiskDecision(action="compose", responder_account_id=chosen.id)
```

- [ ] **Step 9.4: 跑测试**

```bash
pytest backend/tests/test_risk_controller_phase1.py -v
```

Expected: 6 个测试全 PASS。

- [ ] **Step 9.5: 提交**

```bash
git add backend/app/services/risk_controller.py \
        backend/tests/test_risk_controller_phase1.py
git commit -m "feat(group-ai/phase1): RiskController with 3 basic rules"
```

---

## Task 10: ReplyComposer KB-only 三段式

**Files:**
- Create: `backend/app/services/reply_composer.py`
- Test: `backend/tests/test_reply_composer_phase1.py`

> Phase 1 不查 case_studies、不做数字一致性检测。Step C 用 KB 检索 + LLM 出三段式，Step D 沿用 `shill_dispatcher._anti_hallucination_filter`。

- [ ] **Step 10.1: 写测试**

`backend/tests/test_reply_composer_phase1.py`:

```python
"""ReplyComposer Phase 1 — KB-only 三段式生成"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from app.services.reply_composer import compose_reply_phase1


@pytest.mark.asyncio
async def test_compose_returns_str_within_length():
    fake_kb_hits = [
        {"text": "USDT 大额场外结算通常 T+0 到账", "score": 0.9},
        {"text": "汇率优于交易所现价 0.3%", "score": 0.85},
    ]
    fake_llm_output = "USDT 大额 T+0 直接到账, 汇率优交易所 0.3%. 私聊我"
    with patch(
        "app.services.reply_composer.kb_retrieve_top_k",
        new=AsyncMock(return_value=fake_kb_hits),
    ), patch(
        "app.services.reply_composer.llm_generate_reply",
        new=AsyncMock(return_value=fake_llm_output),
    ):
        result = await compose_reply_phase1(
            customer_id=1,
            source_text="想买 100k USDT",
            solution_topic="USDT 大额场外",
        )
    assert isinstance(result, str)
    assert 5 <= len(result) <= 80
    assert "USDT" in result


@pytest.mark.asyncio
async def test_compose_anti_hallucination_filters_exposure():
    fake_kb_hits = [{"text": "USDT 渠道", "score": 0.9}]
    # LLM 不慎吐 "+V"  → filter 应去掉
    fake_llm_output = "USDT 直供, 我有真实案例, 加我 +V 详谈"
    with patch(
        "app.services.reply_composer.kb_retrieve_top_k",
        new=AsyncMock(return_value=fake_kb_hits),
    ), patch(
        "app.services.reply_composer.llm_generate_reply",
        new=AsyncMock(return_value=fake_llm_output),
    ):
        result = await compose_reply_phase1(
            customer_id=1, source_text="USDT", solution_topic="USDT",
        )
    assert "+V" not in result
    assert "加我" not in result or "加我 +V" not in result


@pytest.mark.asyncio
async def test_compose_retries_then_returns_suggested_on_persistent_fail():
    """LLM 一直吐暴露词 → 2 次失败后返回 None (Phase 4 接管转 suggested)"""
    fake_kb_hits = [{"text": "USDT", "score": 0.9}]
    bad_output = "作为 AI 助手, 我是大模型"
    with patch(
        "app.services.reply_composer.kb_retrieve_top_k",
        new=AsyncMock(return_value=fake_kb_hits),
    ), patch(
        "app.services.reply_composer.llm_generate_reply",
        new=AsyncMock(return_value=bad_output),
    ):
        result = await compose_reply_phase1(
            customer_id=1, source_text="x", solution_topic="x",
        )
    # Phase 1: 失败返回 None, 上层置 status=failed (Phase 4 改成 suggested)
    assert result is None


@pytest.mark.asyncio
async def test_compose_empty_kb_still_attempts():
    """KB 无召回也尝试生成 (Phase 1 容错; Phase 2 会用 case_studies 兜底)"""
    with patch(
        "app.services.reply_composer.kb_retrieve_top_k",
        new=AsyncMock(return_value=[]),
    ), patch(
        "app.services.reply_composer.llm_generate_reply",
        new=AsyncMock(return_value="一句话方案 一句话效果 私聊我"),
    ):
        result = await compose_reply_phase1(
            customer_id=1, source_text="x", solution_topic="x",
        )
    assert result is not None
```

- [ ] **Step 10.2: 跑 —— 应 ImportError**

```bash
pytest backend/tests/test_reply_composer_phase1.py -v
```

Expected: FAIL。

- [ ] **Step 10.3: 实装 reply_composer.py**

`backend/app/services/reply_composer.py`:

```python
"""
ReplyComposer — 三段式回复生成 (Phase 1: KB-only, 无案例库, 无数字一致性)。

Phase 2 升级: 接入 case_studies + 数字一致性反幻觉
Phase 4 升级: 失败转副驾驶 Inbox

参考: spec §6
"""
import logging
from typing import Optional

from app.services.kb_retrieval import search as kb_search
from app.services.llm import generate_reply as llm_generate
from app.services.shill_dispatcher import _anti_hallucination_filter

logger = logging.getLogger(__name__)

MAX_REPLY_LENGTH = 80
MAX_RETRIES = 2

# 暴露词 (Phase 1 简单检测; Phase 2 用 shill_dispatcher filter + 数字一致性)
EXPOSURE_PATTERNS = [
    "作为 AI", "我是助手", "作为大模型", "+V", "加我 V", "加微信",
    "扫码", "扫一扫",
]


async def kb_retrieve_top_k(customer_id: int, query: str, k: int = 3) -> list[dict]:
    """薄包装, 方便 mock。"""
    return await kb_search(customer_id=customer_id, query=query, top_k=k)


async def llm_generate_reply(prompt: str) -> str:
    """薄包装。"""
    return await llm_generate(prompt)


def _build_prompt(source_text: str, solution_topic: str, kb_hits: list[dict]) -> str:
    kb_block = "\n".join(f"- {h['text']}" for h in kb_hits) if kb_hits else "(无)"
    return f"""你扮演一个 TG 群里的真人销售。看到陌生人发: 「{source_text}」

你建议谈论的方案主题: {solution_topic}

你的业务知识 (来自 KB):
{kb_block}

请回复 3 句话, 不超 {MAX_REPLY_LENGTH} 中文字:
1. 一句话方案: 针对对方需求点提出做法
2. 一句话效果: 提及业务效果 (Phase 1 可泛说, Phase 2 接入真实案例)
3. 一句话引导: 自然提议私聊深聊

禁止:
- 出现"作为 AI"/"我是助手"/"作为大模型"等暴露词
- 出现"+V"/"加我 V"/"扫码"/"微信"
- 超过 {MAX_REPLY_LENGTH} 字
- 模板化套话
- 超过 1 个 emoji
"""


def _has_exposure_words(text: str) -> bool:
    return any(p in text for p in EXPOSURE_PATTERNS)


def _passes_filter(text: str) -> bool:
    if _has_exposure_words(text):
        return False
    if len(text) > MAX_REPLY_LENGTH:
        return False
    return True


async def compose_reply_phase1(
    *,
    customer_id: int,
    source_text: str,
    solution_topic: str,
) -> Optional[str]:
    """
    生成三段式回复; 反幻觉 2 次失败返回 None。

    Returns:
        str: 最终回复
        None: 失败 (上层置 status=failed, Phase 4 改为 status=suggested)
    """
    kb_hits = await kb_retrieve_top_k(customer_id, solution_topic, k=3)
    prompt = _build_prompt(source_text, solution_topic, kb_hits)

    for attempt in range(MAX_RETRIES + 1):
        raw = await llm_generate_reply(prompt)
        filtered = _anti_hallucination_filter(raw)
        if filtered and _passes_filter(filtered):
            return filtered
        logger.info(
            "reply_composer attempt %d/%d failed filter for customer %s",
            attempt + 1, MAX_RETRIES + 1, customer_id,
        )

    return None
```

> **TODO 给实施者：** `kb_retrieval.search` 和 `llm.generate_reply` 的实际签名必须先确认。grep 查后调整 wrapper 参数。如果没有 `generate_reply` 而是 `gemini_call` 之类，wrapper 名字保持，内部桥接到实际函数。

- [ ] **Step 10.4: 校验依赖签名**

```bash
grep -nE "^(async )?def (search|generate_reply|generate_text|chat_completion)" \
  /var/tgsc/backend/app/services/kb_retrieval.py \
  /var/tgsc/backend/app/services/llm.py
```

按实际签名调整 `kb_retrieve_top_k` / `llm_generate_reply` wrapper 内部调用。

- [ ] **Step 10.5: 跑测试**

```bash
pytest backend/tests/test_reply_composer_phase1.py -v
```

Expected: 4 个测试 PASS。

- [ ] **Step 10.6: 提交**

```bash
git add backend/app/services/reply_composer.py \
        backend/tests/test_reply_composer_phase1.py
git commit -m "feat(group-ai/phase1): ReplyComposer KB-only 3-segment with anti-hallucination"
```

---

## Task 11: GroupDispatcher (typing delay + Telethon send + billing)

**Files:**
- Create: `backend/app/services/group_dispatcher.py`
- Test: `backend/tests/test_group_dispatcher.py`

- [ ] **Step 11.1: 写测试**

`backend/tests/test_group_dispatcher.py`:

```python
"""GroupDispatcher 单元测试 — typing 时延 + Telethon send + 扣费"""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.group_dispatcher import dispatch_send


@pytest.mark.asyncio
async def test_dispatch_picks_delay_in_range():
    """时延在 (30, 120) 内"""
    pr = MagicMock(
        id=1, responder_account_id=10, chat_id=-100, reply_text="hi"
    )
    with patch(
        "app.services.group_dispatcher._telethon_send_to_group",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.services.group_dispatcher._charge_customer",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.services.group_dispatcher.asyncio.sleep", new=AsyncMock()
    ) as sleep_mock:
        await dispatch_send(pr)
    delay_called = sleep_mock.call_args[0][0]
    assert 30 <= delay_called <= 120


@pytest.mark.asyncio
async def test_dispatch_calls_telethon_with_correct_args():
    pr = MagicMock(
        id=1, responder_account_id=10,
        chat_id=-100, reply_text="测试回复",
    )
    with patch(
        "app.services.group_dispatcher._telethon_send_to_group",
        new=AsyncMock(return_value=True),
    ) as send_mock, patch(
        "app.services.group_dispatcher._charge_customer",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.services.group_dispatcher.asyncio.sleep", new=AsyncMock()
    ):
        await dispatch_send(pr)
    send_mock.assert_awaited_once()
    kwargs = send_mock.call_args.kwargs
    assert kwargs["account_id"] == 10
    assert kwargs["chat_id"] == -100
    assert kwargs["text"] == "测试回复"


@pytest.mark.asyncio
async def test_dispatch_charges_after_send():
    pr = MagicMock(id=1, responder_account_id=10, chat_id=-100, reply_text="x")
    with patch(
        "app.services.group_dispatcher._telethon_send_to_group",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.services.group_dispatcher._charge_customer",
        new=AsyncMock(return_value=True),
    ) as charge, patch(
        "app.services.group_dispatcher.asyncio.sleep", new=AsyncMock()
    ):
        await dispatch_send(pr)
    charge.assert_awaited_once_with(pending_reply=pr, amount_usd=0.50)


@pytest.mark.asyncio
async def test_dispatch_send_failure_skips_charge():
    pr = MagicMock(id=1, responder_account_id=10, chat_id=-100, reply_text="x")
    with patch(
        "app.services.group_dispatcher._telethon_send_to_group",
        new=AsyncMock(return_value=False),
    ), patch(
        "app.services.group_dispatcher._charge_customer",
        new=AsyncMock(return_value=True),
    ) as charge, patch(
        "app.services.group_dispatcher.asyncio.sleep", new=AsyncMock()
    ):
        await dispatch_send(pr)
    charge.assert_not_called()
```

- [ ] **Step 11.2: 跑 —— 应 ImportError**

```bash
pytest backend/tests/test_group_dispatcher.py -v
```

Expected: FAIL。

- [ ] **Step 11.3: 实装 group_dispatcher.py**

`backend/app/services/group_dispatcher.py`:

```python
"""
GroupDispatcher — 随机 typing 时延 + Telethon 发群 + billing 扣费。

参考: spec §2.1 + §8.1 集成点 3
"""
import asyncio
import logging
import random
from datetime import datetime, timezone

from app.core.group_reply_config import BILLING_PER_REPLY_USD, DEFAULT_PERSONA
from app.models.pending_reply import PendingReplyStatus

logger = logging.getLogger(__name__)


async def dispatch_send(pending_reply) -> None:
    """
    主入口: 等 typing 时延 → Telethon 发群 → 扣费 → 落 sent。

    失败时只 warn, status 由调用方在异常路径写。
    """
    delay = _pick_typing_delay()
    logger.info(
        "dispatch pending_reply id=%s: delaying %ss before send",
        pending_reply.id, delay,
    )
    await asyncio.sleep(delay)

    sent_ok = await _telethon_send_to_group(
        account_id=pending_reply.responder_account_id,
        chat_id=pending_reply.chat_id,
        text=pending_reply.reply_text,
    )

    if not sent_ok:
        logger.warning("dispatch send failed pending_reply id=%s", pending_reply.id)
        await _mark_status(pending_reply, PendingReplyStatus.FAILED, skip_reason="send_failed")
        return

    charged = await _charge_customer(pending_reply=pending_reply, amount_usd=BILLING_PER_REPLY_USD)
    if not charged:
        logger.warning("billing charge failed pending_reply id=%s (kept as sent)", pending_reply.id)

    await _mark_status(pending_reply, PendingReplyStatus.SENT, sent_at=datetime.now(timezone.utc))


def _pick_typing_delay() -> int:
    lo, hi = DEFAULT_PERSONA["typing_delay_seconds_range"]
    return random.randint(lo, hi)


async def _telethon_send_to_group(*, account_id: int, chat_id: int, text: str) -> bool:
    """通过 account_id 拿 Telethon client 发到 chat_id。

    TODO 实施者: 复用 shill_dispatcher.send_message_with_client_reply
                 或 listener_service 的 client 管理。具体桥接以实际仓库为准。
    """
    from app.services import shill_dispatcher
    # 占位调用; 实施者按现有 API 调整
    try:
        return await shill_dispatcher.send_message_with_client_reply(
            account_id=account_id, chat_id=chat_id, text=text,
        )
    except Exception:
        logger.exception("telethon send failed")
        return False


async def _charge_customer(*, pending_reply, amount_usd: float) -> bool:
    """复用 billing_service。

    TODO 实施者: 调用现有 billing_service.deduct(customer_id, amount, idempotency_key)
                 idempotency_key = f"group_reply:{pending_reply.id}"
    """
    from app.services import billing_service
    try:
        return await billing_service.deduct(
            customer_id=pending_reply.customer_id,
            amount_usd=amount_usd,
            idempotency_key=f"group_reply:{pending_reply.id}",
            reason="group_ai_reply",
        )
    except AttributeError:
        # billing_service.deduct 不存在 → 临时空跑, 等 Phase 1 后补
        logger.warning("billing_service.deduct missing; skipping charge")
        return True
    except Exception:
        logger.exception("billing charge failed")
        return False


async def _mark_status(pending_reply, status, **fields) -> None:
    """更新 pending_reply 行的 status + 其它字段, 持久化。"""
    from app.core.database import get_session
    pending_reply.status = status.value
    for k, v in fields.items():
        setattr(pending_reply, k, v)
    async with get_session() as session:
        session.add(pending_reply)
        await session.commit()
```

- [ ] **Step 11.4: 跑测试**

```bash
pytest backend/tests/test_group_dispatcher.py -v
```

Expected: 4 个测试 PASS。

- [ ] **Step 11.5: 提交**

```bash
git add backend/app/services/group_dispatcher.py \
        backend/tests/test_group_dispatcher.py
git commit -m "feat(group-ai/phase1): GroupDispatcher with typing delay + billing"
```

---

## Task 12: Celery beat 扫描器

**Files:**
- Create: `backend/app/workers/group_reply_scanner.py`
- Modify: `backend/app/core/celery_app.py:60` (`beat_schedule`)
- Test: `backend/tests/test_group_reply_scanner.py`

- [ ] **Step 12.1: 写测试**

`backend/tests/test_group_reply_scanner.py`:

```python
"""Celery beat 扫描器: 拉到期 pending_replies + RiskController + ReplyComposer + Dispatch"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

from app.workers.group_reply_scanner import scan_and_process_due_replies


@pytest.mark.asyncio
async def test_scanner_no_due_returns_zero():
    with patch(
        "app.workers.group_reply_scanner._fetch_due_pending_replies",
        new=AsyncMock(return_value=[]),
    ):
        processed = await scan_and_process_due_replies()
    assert processed == 0


@pytest.mark.asyncio
async def test_scanner_processes_one_compose_path():
    pr = MagicMock(
        id=1, customer_id=1, chat_id=-100, source_user_id=999,
        source_text="求 USDT", responder_account_id=None,
    )
    decision = MagicMock(action="compose", responder_account_id=10, skip_reason=None)

    with patch(
        "app.workers.group_reply_scanner._fetch_due_pending_replies",
        new=AsyncMock(return_value=[pr]),
    ), patch(
        "app.workers.group_reply_scanner._gather_risk_inputs",
        new=AsyncMock(return_value={}),
    ), patch(
        "app.workers.group_reply_scanner.decide_phase1", return_value=decision,
    ), patch(
        "app.workers.group_reply_scanner.compose_reply_phase1",
        new=AsyncMock(return_value="测试回复"),
    ), patch(
        "app.workers.group_reply_scanner.dispatch_send", new=AsyncMock()
    ) as dispatch:
        processed = await scan_and_process_due_replies()
    assert processed == 1
    dispatch.assert_awaited_once()
    assert pr.responder_account_id == 10
    assert pr.reply_text == "测试回复"


@pytest.mark.asyncio
async def test_scanner_skip_path_marks_status():
    pr = MagicMock(id=1, customer_id=1, chat_id=-100, source_user_id=999, source_text="x")
    decision = MagicMock(
        action="skip", skip_reason="skipped_dup", responder_account_id=None,
    )
    with patch(
        "app.workers.group_reply_scanner._fetch_due_pending_replies",
        new=AsyncMock(return_value=[pr]),
    ), patch(
        "app.workers.group_reply_scanner._gather_risk_inputs",
        new=AsyncMock(return_value={}),
    ), patch(
        "app.workers.group_reply_scanner.decide_phase1", return_value=decision,
    ), patch(
        "app.workers.group_reply_scanner._mark_status", new=AsyncMock()
    ) as mark:
        processed = await scan_and_process_due_replies()
    assert processed == 1
    mark.assert_awaited_once()
    assert mark.call_args.args[1] == "skipped_dup"


@pytest.mark.asyncio
async def test_scanner_compose_failure_marks_failed():
    pr = MagicMock(id=1, customer_id=1, chat_id=-100, source_user_id=999, source_text="x")
    decision = MagicMock(action="compose", responder_account_id=10, skip_reason=None)
    with patch(
        "app.workers.group_reply_scanner._fetch_due_pending_replies",
        new=AsyncMock(return_value=[pr]),
    ), patch(
        "app.workers.group_reply_scanner._gather_risk_inputs",
        new=AsyncMock(return_value={}),
    ), patch(
        "app.workers.group_reply_scanner.decide_phase1", return_value=decision,
    ), patch(
        "app.workers.group_reply_scanner.compose_reply_phase1",
        new=AsyncMock(return_value=None),  # 失败
    ), patch(
        "app.workers.group_reply_scanner._mark_status", new=AsyncMock()
    ) as mark:
        processed = await scan_and_process_due_replies()
    assert processed == 1
    # Phase 1 失败 → status=failed (Phase 4 改 suggested)
    assert mark.call_args.args[1] == "failed"
```

- [ ] **Step 12.2: 跑 —— 应 ImportError**

```bash
pytest backend/tests/test_group_reply_scanner.py -v
```

Expected: FAIL。

- [ ] **Step 12.3: 实装 scanner**

`backend/app/workers/group_reply_scanner.py`:

```python
"""
Celery beat 任务: 每 30s 扫到期 pending_replies → RiskController → Composer → Dispatch。

参考: spec §2.1
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta

from sqlmodel import select

from app.core.celery_app import celery_app
from app.core.database import get_session
from app.core.group_reply_config import DEFAULT_PERSONA, SCAN_INTERVAL_SECONDS
from app.models.account import Account
from app.models.pending_reply import PendingReply, PendingReplyStatus
from app.services.reply_composer import compose_reply_phase1
from app.services.risk_controller import decide_phase1
from app.services.group_dispatcher import dispatch_send

logger = logging.getLogger(__name__)


async def scan_and_process_due_replies() -> int:
    """主入口。返回处理条数。"""
    due = await _fetch_due_pending_replies()
    if not due:
        return 0

    processed = 0
    for pr in due:
        try:
            await _process_one(pr)
            processed += 1
        except Exception:
            logger.exception("scanner failed to process pending_reply id=%s", pr.id)
    return processed


async def _process_one(pr: PendingReply) -> None:
    inputs = await _gather_risk_inputs(pr)
    decision = decide_phase1(
        pending=pr,
        candidate_accounts=inputs["candidate_accounts"],
        same_lead_sent_within_48h=inputs["same_lead_sent_within_48h"],
        account_daily_sent_count=inputs["account_daily_sent_count"],
        account_last_sent_in_chat=inputs["account_last_sent_in_chat"],
        cooldown_minutes=DEFAULT_PERSONA["per_chat_cooldown_minutes"],
        daily_quota=DEFAULT_PERSONA["daily_reply_quota"],
    )

    if decision.action == "skip":
        await _mark_status(pr, decision.skip_reason)
        return

    # compose 路径
    pr.responder_account_id = decision.responder_account_id
    reply = await compose_reply_phase1(
        customer_id=pr.customer_id,
        source_text=pr.source_text,
        solution_topic=pr.source_text,  # Phase 1 无 Layer 3, 用 source_text 兜底
    )
    if reply is None:
        # Phase 1: 失败 → status=failed (Phase 4 改 suggested)
        await _mark_status(pr, PendingReplyStatus.FAILED.value, skip_reason="compose_failed")
        return

    pr.reply_text = reply
    await dispatch_send(pr)


async def _fetch_due_pending_replies() -> list[PendingReply]:
    now = datetime.now(timezone.utc)
    async with get_session() as session:
        result = await session.exec(
            select(PendingReply)
            .where(
                PendingReply.status == PendingReplyStatus.OBSERVING.value,
                PendingReply.fire_at <= now,
            )
            .order_by(PendingReply.fire_at)
            .limit(50)
        )
        return list(result.all())


async def _gather_risk_inputs(pr: PendingReply) -> dict:
    """聚合 RiskController 决策所需 DB 上下文。"""
    now = datetime.now(timezone.utc)
    window_48h = now - timedelta(hours=48)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    async with get_session() as session:
        # 候选 worker 账号 (同 customer + role=worker + active)
        candidates_result = await session.exec(
            select(Account).where(
                Account.customer_id == pr.customer_id,
                Account.role == "worker",
                Account.status == "active",
            )
        )
        candidate_accounts = list(candidates_result.all())

        # 同 (chat, source_user) 48h 内已发过的
        dup_result = await session.exec(
            select(PendingReply).where(
                PendingReply.chat_id == pr.chat_id,
                PendingReply.source_user_id == pr.source_user_id,
                PendingReply.status == PendingReplyStatus.SENT.value,
                PendingReply.sent_at >= window_48h,
                PendingReply.id != pr.id,
            )
        )
        same_lead_sent = list(dup_result.all())

        # 每个候选账号今日已发计数
        sent_today = await session.exec(
            select(PendingReply).where(
                PendingReply.status == PendingReplyStatus.SENT.value,
                PendingReply.sent_at >= today_start,
                PendingReply.responder_account_id.in_(
                    [a.id for a in candidate_accounts]
                ) if candidate_accounts else False,
            )
        )
        daily_count = {}
        for row in sent_today.all():
            daily_count[row.responder_account_id] = daily_count.get(row.responder_account_id, 0) + 1

        # 每个候选账号在本 chat 的最近发送时间
        last_sent_in_chat = {}
        for acc in candidate_accounts:
            last = await session.exec(
                select(PendingReply.sent_at).where(
                    PendingReply.responder_account_id == acc.id,
                    PendingReply.chat_id == pr.chat_id,
                    PendingReply.status == PendingReplyStatus.SENT.value,
                ).order_by(PendingReply.sent_at.desc()).limit(1)
            )
            row = last.first()
            last_sent_in_chat[(acc.id, pr.chat_id)] = row if row else None

    return {
        "candidate_accounts": candidate_accounts,
        "same_lead_sent_within_48h": same_lead_sent,
        "account_daily_sent_count": daily_count,
        "account_last_sent_in_chat": last_sent_in_chat,
    }


async def _mark_status(pr: PendingReply, status_value: str, skip_reason: str | None = None) -> None:
    pr.status = status_value
    if skip_reason and not pr.skip_reason:
        pr.skip_reason = skip_reason
    pr.decided_at = datetime.now(timezone.utc)
    async with get_session() as session:
        session.add(pr)
        await session.commit()


# === Celery task 包装 ===

@celery_app.task(name="group_reply_scanner.tick")
def scan_tick():
    """beat 调用入口。同步包装 async 主逻辑。"""
    return asyncio.run(scan_and_process_due_replies())
```

- [ ] **Step 12.4: 注册到 Celery beat**

修改 `backend/app/core/celery_app.py:60` 附近的 `beat_schedule` dict，加：

```python
beat_schedule={
    # ... 现有任务 ...
    "group_reply_scanner": {
        "task": "group_reply_scanner.tick",
        "schedule": 30.0,  # 30 秒
    },
}
```

并在文件顶部 / `include` 列表加 `"app.workers.group_reply_scanner"`，让 Celery 能发现 task。

- [ ] **Step 12.5: 跑测试**

```bash
pytest backend/tests/test_group_reply_scanner.py -v
```

Expected: 4 个测试 PASS。

- [ ] **Step 12.6: 启动 beat 烟测**

```bash
# 一个 terminal:
celery -A app.core.celery_app beat -l info
# 另一个 terminal:
celery -A app.core.celery_app worker -l info -Q celery
```

Expected: beat 每 30s 打印 `Scheduler: Sending due task group_reply_scanner`；worker 收到 task 执行，无 error。

- [ ] **Step 12.7: 提交**

```bash
git add backend/app/workers/group_reply_scanner.py \
        backend/app/core/celery_app.py \
        backend/tests/test_group_reply_scanner.py
git commit -m "feat(group-ai/phase1): Celery beat scanner wires risk + composer + dispatch"
```

---

## Task 13: 端到端 smoke 测试

**Files:**
- Create: `backend/tests/test_group_reply_e2e.py`

> 此测试在真实 DB 上跑全管线：插一条 fake 群消息 → 调 pipeline → fast-forward fire_at → 调 scanner → 验证 status=sent。

- [ ] **Step 13.1: 写 e2e 测试**

`backend/tests/test_group_reply_e2e.py`:

```python
"""端到端: msg → pipeline → scanner → sent (mock Telethon + LLM)"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch
from sqlmodel import select

from app.models.pending_reply import PendingReply, PendingReplyStatus
from app.services import group_reply_pipeline
from app.workers.group_reply_scanner import scan_and_process_due_replies


class FakeMsg:
    text = "求 USDT 100k 渠道"
    chat_id = -100999888
    id = 99999
    sender_id = 8888888


class FakeAcc:
    id = 9999  # 须为真实 DB 中存在的 worker account, 否则 set 一个 fixture-created id
    customer_id = 1  # 同上
    role = "worker"


class FakeMonitor:
    id = None  # 取 DB 中一个真实 monitor 的 id
    customer_id = 1
    keyword_filters = {"include": ["USDT"], "exclude": [], "mode": "any"}
    keyword = None


@pytest.mark.asyncio
async def test_e2e_happy_path(db_session):
    """
    前置: DB 中存在 customer_id=1 + 1 个 worker account + 1 个 monitor。
    用 fixture 准备; 这里只演示骨架。
    """
    # === Arrange ===
    # TODO: 用 fixture 创建临时 customer + account + monitor, 测试后回滚

    # === Act 1: pipeline entrypoint ===
    with patch(
        "app.services.group_reply_pipeline.GROUP_AI_REPLY_ENABLED", True
    ):
        result = await group_reply_pipeline.entrypoint(
            FakeMsg(), FakeAcc(), FakeMonitor()
        )
    assert "pending_reply_id" in result
    pr_id = result["pending_reply_id"]

    # === fast-forward fire_at ===
    pr = (db_session.exec(select(PendingReply).where(PendingReply.id == pr_id))).first()
    pr.fire_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.add(pr)
    db_session.commit()

    # === Act 2: scanner ===
    with patch(
        "app.services.reply_composer.kb_retrieve_top_k",
        new=AsyncMock(return_value=[{"text": "USDT 大额场外", "score": 0.9}]),
    ), patch(
        "app.services.reply_composer.llm_generate_reply",
        new=AsyncMock(return_value="USDT 大额 T+0 直接到账 私聊我"),
    ), patch(
        "app.services.group_dispatcher._telethon_send_to_group",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.services.group_dispatcher._charge_customer",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.services.group_dispatcher.asyncio.sleep", new=AsyncMock()
    ):
        n = await scan_and_process_due_replies()
    assert n == 1

    # === Assert: status=sent ===
    db_session.refresh(pr)
    assert pr.status == PendingReplyStatus.SENT.value
    assert pr.reply_text is not None
    assert "USDT" in pr.reply_text
```

> **TODO 实施者：** 写 pytest fixture 创建 customer/account/monitor 临时行，测试结束 rollback。如果项目用 `transaction` rollback pattern 已有 `db_session` fixture，参考 backend/tests/test_billing_service_refactor.py 看现有 fixture 风格。

- [ ] **Step 13.2: 跑 e2e**

```bash
pytest backend/tests/test_group_reply_e2e.py -v
```

Expected: PASS。如失败，逐段排查（先看 pending_reply 是否写入；再看 scanner 是否抓到；再看 reply_text 是否填）。

- [ ] **Step 13.3: 提交**

```bash
git add backend/tests/test_group_reply_e2e.py
git commit -m "test(group-ai/phase1): e2e smoke from msg to sent"
```

---

## Task 14: PR 与 release

- [ ] **Step 14.1: 跑全量测试**

```bash
cd /var/tgsc/backend
pytest tests/ -v -k "phase1 or group or pending_reply or risk_controller or reply_composer or lead_detector or migration"
```

Expected: 全部 PASS。

- [ ] **Step 14.2: 跑现有 listener 回归**

```bash
pytest tests/ -k "listener or intercept or shill"
```

Expected: 无回归。

- [ ] **Step 14.3: 推分支 + 开 PR**

```bash
git push -u origin feature/group-ai-sales-phase1
gh pr create --title "feat(group-ai): Phase 1 — skeleton end-to-end" --body "$(cat <<'EOF'
## Summary

群内 AI 销售员 Phase 1 实施 —— 骨架打通。

- 一次性 Alembic 迁移建 5 张新表 + 4 个扩展字段 (后续 Phase 不再迁)
- `group_reply_pipeline.entrypoint` listener hook + Layer 1 keyword filter
- `pending_replies` 状态机 + Celery beat 每 30s 扫描
- `RiskController` 3 条基础规则 (48h dedup / daily quota / cooldown)
- `ReplyComposer` KB-only 三段式 + 复用 shill_dispatcher 反幻觉 filter
- `GroupDispatcher` typing 时延 + Telethon 发送 + billing 扣 \$0.50
- 14+ 单元 + 1 e2e smoke 测试

明确不含 (留给后续 Phase):
- Layer 2 ICP embedding / Layer 3 LLM 评分 (Phase 2)
- case_studies 实际查询 (Phase 2)
- worker_persona 实际读取 (Phase 3 — Phase 1 用兜底)
- ChitchatScheduler (Phase 3)
- 副驾驶兜底 / 群→私聊上下文 (Phase 4)
- 完整 A/B 框架 (Phase 5)

## Test plan

- [ ] alembic upgrade head 在 dev DB 成功
- [ ] alembic downgrade -1 → upgrade head round-trip 成功
- [ ] 全部 Phase 1 单元 + e2e PASS
- [ ] 现有 listener / intercept / shill 测试无回归
- [ ] GROUP_AI_REPLY_ENABLED=true 灰度跑 1 个客户 1 个监控群 24h 观察

## 相关

- Spec: docs/superpowers/specs/2026-05-28-group-ai-sales-presence-design.md
- 决策: \`feature/group-ai-sales-phase1\` 分支

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 14.4: PR review + merge**

等 reviewer 通过后 squash merge 到 main。

---

## Phase 1 完成判据

- [ ] PR merged 到 main
- [ ] 灰度客户 GROUP_AI_REPLY_ENABLED=true 跑 24h 无报错
- [ ] 至少 1 条 pending_reply 走到 status='sent' 且实际看到群里发出
- [ ] 写 memory: `feedback_group_ai_phase1_learnings.md` 记录灰度阶段实际遇到的问题, 给 Phase 2 plan 当输入

---

## 写 Phase 2 plan 触发条件

Phase 1 完成判据全部满足后, 启动 Phase 2 plan 撰写。Phase 2 包含 (详见 spec §9.2):
- Layer 2 ICP embedding + portal ICP 编辑器
- Layer 3 LLM 评分 (`llm.score_lead_message`)
- case_studies 表实际查询 + portal 录入 UI
- 案例库自动抽取脚本 + portal "扫描历史" 按钮
- ReplyComposer 接入 case_studies + 数字一致性反幻觉
