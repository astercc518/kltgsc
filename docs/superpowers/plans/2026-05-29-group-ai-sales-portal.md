# 群内 AI 销售员 Portal Phase 实施计划（统一前端 UI）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 Phase 2a/3a/4a/5 累积的所有 admin/customer UI 一次性做完。客户能在 portal 自助配置 ICP、案例、人设、闲聊；销售能在 Inbox 看到群内回复 + 副驾驶 suggested 操作；运营能在 admin 后台管 A/B 实验 + 看报告。

**Architecture:** 不改 backend 接口（Phase 2a/3a/4a/5 endpoints 已经齐全）。新加 React 页面 + 组件 + WebSocket 集成。客户端走 `frontend/src/portal/`，admin 走 `frontend/src/pages/`。每个 page 用现有约定的 Ant Design + `@tanstack/react-query` + 各自 axios 实例（portal `api.ts` 用 customer token，admin `services/api.ts` 用 admin token）。

**Tech Stack:** React 18 · TypeScript · Vite · Ant Design 5 · @tanstack/react-query · react-router-dom · axios · WebSocket (existing ws_manager)

**Spec:** [docs/superpowers/specs/2026-05-28-group-ai-sales-presence-design.md](../specs/2026-05-28-group-ai-sales-presence-design.md) §8.2 Portal UI + §10.5 admin A/B UI

**前置条件：**
- Phase 2a / 3a / 4a / 5 后端已全部实施（admin_group_ai router 完整、inbox_group_ai router 完整、A/B endpoints 完整、WebSocket 推送已上）
- 客户视角的 API endpoints **未在 Phase 2a/3a/4a/5 写**（这几期只写了 admin/{customer_id}/* 路径）。本期 Task 1 必须先在 backend 加一组客户视角 endpoint（不带 customer_id 参数，从 customer token 推断）
- worktree `/var/tgsc/.claude/worktrees/feature+group-ai-sales-portal`

**Portal phase 范围：**

| 包含 | 不含（后续 / 不在范围） |
|---|---|
| Backend：客户视角 endpoints（/portal/group-ai/*） | 移动端原生 App |
| 客户端 portal UI：ICP / 阈值 / 案例 / 人设 / 闲聊 / 统计 | A/B 实验后端逻辑变更（Phase 5 已定） |
| Admin UI：Inbox 群内 AI 互动 + 副驾驶操作 | i18n 多语（英文文案占位即可，国际化 Phase 后续） |
| Admin UI：A/B 实验列表 / 创建 / 报告 | 移动端深度优化（响应式即可，复杂手势不上） |
| WebSocket 集成 ai_suggestion_pending 通知 | 复杂数据可视化（饼图/趋势线，Phase 后续） |
| E2E（Playwright）核心 happy path | — |

---

## File Structure

**新建（backend，客户视角端点）：**
- `backend/app/routers/portal_group_ai.py` —— 复用 admin 的 service 层，只换 customer_id 来源（从 token）

**新建（frontend 客户端 portal）：**
- `frontend/src/portal/pages/GroupAI/` (新目录)
  - `index.tsx` —— 主页，nav 进来落点 + sub-route 容器
  - `IcpEditor.tsx`
  - `Thresholds.tsx`
  - `CaseStudies.tsx`
  - `CaseExtractModal.tsx`
  - `WorkerPersonas.tsx`
  - `ChitchatTopics.tsx`
  - `RealtimeStats.tsx`
- `frontend/src/portal/api/groupAi.ts` —— typed API wrappers

**新建（frontend admin 端）：**
- `frontend/src/pages/inbox/GroupAIInteractions.tsx` —— Inbox 内 tab，或独立路由
- `frontend/src/pages/ab/` (新目录)
  - `ExperimentList.tsx`
  - `ExperimentCreate.tsx`
  - `ExperimentReport.tsx`
- `frontend/src/services/groupAi.ts` —— admin typed API wrappers
- `frontend/src/hooks/useGroupAiWebsocket.ts` —— 复用现有 ws hook 模式

**修改：**
- `frontend/src/portal/Layout.tsx` —— Menu 加 "群内 AI 销售员" 项
- `frontend/src/App.tsx` —— Routes 加 admin 端 group-ai routes
- `frontend/src/pages/Inbox.tsx` —— 加 "群内 AI 互动" tab 或 link

---

## Task 1: Backend — 客户视角 portal endpoints

> Phase 2a/3a/4a 写的全是 `/admin/group-ai/customers/{customer_id}/*`，需要管理员权限。客户用 portal 时 customer_id 应从 JWT token 推断。新增 router 复用 service。

**Files:**
- Create: `backend/app/routers/portal_group_ai.py`
- Create: `backend/tests/test_portal_group_ai_endpoints.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1.1: 摸现有客户 JWT 依赖**

```bash
grep -rn "get_current_customer\|customer_user\|customer_token" backend/app/routers/ | head -10
```

确定客户 JWT 怎么解（应该有类似 `Depends(get_current_customer)` 返回 Customer 对象）。

- [ ] **Step 1.2: 写 portal router 桩**

`backend/app/routers/portal_group_ai.py`:

```python
"""
portal_group_ai — 客户视角端点。复用 admin 的 service, 但 customer_id 来自 JWT。
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.core.database import get_session
# 复用 admin router 的 schemas + services
from app.routers.admin_group_ai import (
    ICPUpdate, ThresholdsUpdate, CaseStudyCreate, CaseStudyUpdate,
    PersonaUpsert, ChitchatTopicCreate, CasesBatchCreate,
)
from app.services.case_study_service import (
    create_case_study, update_case_study, delete_case_study, list_case_studies,
)
from app.services.customer_icp_service import set_customer_icp_text_and_embed
from app.services.case_study_extractor import extract_cases_for_customer

# TODO 实施者: 找到现有 portal endpoints 用的 customer JWT dependency,
# 比如 `get_current_customer` 返回 Customer 对象
from app.core.security import get_current_customer  # 桩, 实际 import 以现有为准

router = APIRouter(prefix="/portal/group-ai", tags=["portal-group-ai"])


@router.put("/icp")
async def update_icp(
    body: ICPUpdate,
    customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
):
    ok = set_customer_icp_text_and_embed(
        session=session, customer_id=customer.id, new_text=body.icp_text,
    )
    if not ok:
        raise HTTPException(404, "customer not found (auth ok)")
    return {"ok": True}


@router.get("/icp")
async def get_icp(
    customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
):
    return {
        "icp_text": customer.icp_profile_text,
        "has_embedding": customer.icp_profile_embedding is not None,
        "thresholds": customer.lead_detector_thresholds,
    }


@router.put("/thresholds")
async def update_thresholds(
    body: ThresholdsUpdate,
    customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
):
    from app.models.customer import Customer
    c = session.get(Customer, customer.id)
    thresholds = dict(c.lead_detector_thresholds or {})
    if body.layer2_sim is not None:
        thresholds["layer2_sim"] = body.layer2_sim
    if body.layer3_score is not None:
        thresholds["layer3_score"] = body.layer3_score
    if body.layer3_confidence is not None:
        thresholds["layer3_confidence"] = body.layer3_confidence
    c.lead_detector_thresholds = thresholds
    session.commit()
    return {"ok": True, "thresholds": thresholds}


# === case_studies ===

@router.get("/case-studies")
async def list_my_cases(
    include_inactive: bool = False,
    customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
):
    return list_case_studies(
        session=session, customer_id=customer.id, include_inactive=include_inactive,
    )


@router.post("/case-studies")
async def create_my_case(
    body: CaseStudyCreate,
    customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
):
    case = create_case_study(
        session=session, customer_id=customer.id,
        industry=body.industry, deal_size=body.deal_size, period=body.period,
        problem=body.problem, solution=body.solution, outcome=body.outcome,
        tags=body.tags, source="manual_portal",
    )
    return {"id": case.id}


@router.put("/case-studies/{case_id}")
async def update_my_case(
    case_id: int, body: CaseStudyUpdate,
    customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
):
    ok = update_case_study(
        session=session, case_id=case_id, customer_id=customer.id,
        industry=body.industry, deal_size=body.deal_size, period=body.period,
        problem=body.problem, solution=body.solution, outcome=body.outcome,
        tags=body.tags,
    )
    if not ok:
        raise HTTPException(404, "case not found")
    return {"ok": True}


@router.delete("/case-studies/{case_id}")
async def delete_my_case(
    case_id: int,
    customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
):
    ok = delete_case_study(
        session=session, case_id=case_id, customer_id=customer.id,
    )
    if not ok:
        raise HTTPException(404, "case not found")
    return {"ok": True}


@router.post("/case-studies/extract")
async def extract_my_cases(
    max_history: int = 100,
    customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
):
    return {
        "candidates": await extract_cases_for_customer(
            session=session, customer_id=customer.id, max_history=max_history,
        )
    }


@router.post("/case-studies/batch")
async def batch_save_my_cases(
    body: CasesBatchCreate,
    customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
):
    ids = []
    for c in body.cases:
        case = create_case_study(
            session=session, customer_id=customer.id,
            industry=c.industry, deal_size=c.deal_size, period=c.period,
            problem=c.problem, solution=c.solution, outcome=c.outcome,
            tags=c.tags, source="ai_confirmed",
        )
        ids.append(case.id)
    return {"ids": ids}


# === worker_personas (客户自己看的 own accounts) ===

@router.get("/accounts")
async def list_my_accounts(
    customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
):
    """列出客户名下的 worker 账号 (供 persona 编辑入口)"""
    from app.models.account import Account
    from sqlmodel import select
    rows = session.exec(
        select(Account).where(
            Account.customer_id == customer.id,
            Account.role == "worker",
        )
    ).all()
    return [{"id": a.id, "phone": a.phone_number, "status": a.status} for a in rows]


@router.put("/accounts/{account_id}/persona")
async def upsert_my_persona(
    account_id: int, body: PersonaUpsert,
    customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
):
    """客户只能改自己账号的 persona"""
    from app.models.account import Account
    acc = session.get(Account, account_id)
    if acc is None or acc.customer_id != customer.id:
        raise HTTPException(404, "account not yours")
    # 复用 admin 同名 endpoint 逻辑 (内联简版)
    from app.models.worker_persona import WorkerPersona
    from sqlmodel import select
    existing = session.exec(
        select(WorkerPersona).where(WorkerPersona.account_id == account_id)
    ).first()
    if existing is None:
        existing = WorkerPersona(account_id=account_id, customer_id=customer.id)
        session.add(existing)
    for fname in [
        "display_name", "region", "occupation", "speaking_style",
        "catchphrases", "active_hours",
        "daily_reply_quota", "per_chat_daily_quota",
        "per_chat_cooldown_minutes", "daily_chitchat_quota",
        "observation_window_seconds_range", "typing_delay_seconds_range",
    ]:
        val = getattr(body, fname)
        if val is not None:
            setattr(existing, fname, val)
    session.commit()
    return {"ok": True}


@router.get("/accounts/{account_id}/persona")
async def get_my_persona(
    account_id: int,
    customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
):
    from app.models.account import Account
    from app.models.worker_persona import WorkerPersona
    from sqlmodel import select
    acc = session.get(Account, account_id)
    if acc is None or acc.customer_id != customer.id:
        raise HTTPException(404, "account not yours")
    row = session.exec(
        select(WorkerPersona).where(WorkerPersona.account_id == account_id)
    ).first()
    if row is None:
        return None  # fallback default 由 service 层处理
    return {
        "display_name": row.display_name, "region": row.region,
        "occupation": row.occupation, "speaking_style": row.speaking_style,
        "catchphrases": row.catchphrases, "active_hours": row.active_hours,
        "daily_reply_quota": row.daily_reply_quota,
        "per_chat_daily_quota": row.per_chat_daily_quota,
        "per_chat_cooldown_minutes": row.per_chat_cooldown_minutes,
        "daily_chitchat_quota": row.daily_chitchat_quota,
        "observation_window_seconds_range": row.observation_window_seconds_range,
        "typing_delay_seconds_range": row.typing_delay_seconds_range,
    }


# === chitchat_topics ===

@router.get("/chitchat-topics")
async def list_my_chitchat_topics(
    customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
):
    from app.models.chitchat import ChitchatPool
    from sqlmodel import select
    rows = session.exec(
        select(ChitchatPool).where(
            ((ChitchatPool.customer_id == customer.id) | (ChitchatPool.customer_id.is_(None))),
            ChitchatPool.active == True,
        )
    ).all()
    return [
        {"id": r.id, "topic_category": r.topic_category,
         "prompt_template": r.prompt_template, "tags": r.tags,
         "scope": "global" if r.customer_id is None else "customer"}
        for r in rows
    ]


@router.post("/chitchat-topics")
async def create_my_chitchat_topic(
    body: ChitchatTopicCreate,
    customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
):
    from app.models.chitchat import ChitchatPool
    row = ChitchatPool(
        customer_id=customer.id,
        topic_category=body.topic_category,
        prompt_template=body.prompt_template,
        tags=body.tags, active=True,
    )
    session.add(row); session.commit(); session.refresh(row)
    return {"id": row.id}


# === 实时统计 ===

@router.get("/stats/recent")
async def get_my_recent_stats(
    customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
):
    """精简版: 命中 / 发出 / 转化 + skip_reason 分布"""
    from sqlmodel import select, func
    from datetime import datetime, timezone, timedelta
    from app.models.pending_reply import PendingReply, PendingReplyStatus

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    base = select(func.count(PendingReply.id)).where(
        PendingReply.customer_id == customer.id,
        PendingReply.created_at >= today_start,
    )

    def cnt(*statuses):
        stmt = base.where(PendingReply.status.in_(statuses))
        return int(session.exec(stmt).first() or 0)

    triggered = cnt(*[s.value for s in PendingReplyStatus])
    sent = cnt(PendingReplyStatus.SENT.value)
    skipped_human = cnt(PendingReplyStatus.SKIPPED_HUMAN_REPLIED.value)
    skipped_dup = cnt(PendingReplyStatus.SKIPPED_DUP.value)
    skipped_throttled = cnt(PendingReplyStatus.SKIPPED_THROTTLED.value)
    skipped_borderline = cnt(PendingReplyStatus.SKIPPED_BORDERLINE.value)
    suggested = cnt(PendingReplyStatus.SUGGESTED.value)
    failed = cnt(PendingReplyStatus.FAILED.value)
    return {
        "triggered_today": triggered,
        "sent_today": sent,
        "suggested_today": suggested,
        "failed_today": failed,
        "skipped": {
            "human_replied": skipped_human, "dup": skipped_dup,
            "throttled": skipped_throttled, "borderline": skipped_borderline,
        },
    }
```

注册到 `backend/app/main.py`:
```python
from app.routers import portal_group_ai
app.include_router(portal_group_ai.router)
```

- [ ] **Step 1.3: 写 smoke 测试**

`backend/tests/test_portal_group_ai_endpoints.py` —— 类似 admin endpoint 测试，mock customer dep。

- [ ] **Step 1.4: 跑测试 + 提交**

```bash
pytest backend/tests/test_portal_group_ai_endpoints.py -v
git add backend/app/routers/portal_group_ai.py backend/app/main.py backend/tests/test_portal_group_ai_endpoints.py
git commit -m "feat(group-ai/portal): customer-perspective endpoints (/portal/group-ai/*)"
```

---

## Task 2: Frontend portal API client + nav 入口

**Files:**
- Create: `frontend/src/portal/api/groupAi.ts`
- Modify: `frontend/src/portal/Layout.tsx`
- Modify: `frontend/src/portal/App.tsx` (or main router config — 找现有 portal 路由文件)

- [ ] **Step 2.1: 写 typed API wrapper**

`frontend/src/portal/api/groupAi.ts`:

```typescript
/**
 * Customer-portal API wrappers for "群内 AI 销售员" features.
 * Backend: /portal/group-ai/*
 */
import portalApi from '../api';

// === Types ===

export interface ICPState {
  icp_text: string | null;
  has_embedding: boolean;
  thresholds: {
    layer2_sim: number;
    layer3_score: number;
    layer3_confidence: number;
  };
}

export interface CaseStudy {
  id: number;
  industry: string | null;
  deal_size: string | null;
  period: string | null;
  problem: string;
  solution: string;
  outcome: string;
  tags: string[];
  active: boolean;
  source: string;
  created_at: string;
}

export interface CaseStudyExtractedCandidate {
  industry: string;
  deal_size: string;
  period: string;
  problem: string;
  solution: string;
  outcome: string;
  tags: string[];
}

export interface WorkerPersona {
  display_name: string | null;
  region: string | null;
  occupation: string | null;
  speaking_style: string | null;
  catchphrases: string[];
  active_hours: Record<string, [number, number][]>;
  daily_reply_quota: number;
  per_chat_daily_quota: number;
  per_chat_cooldown_minutes: number;
  daily_chitchat_quota: number;
  observation_window_seconds_range: [number, number];
  typing_delay_seconds_range: [number, number];
}

export interface ChitchatTopic {
  id: number;
  topic_category: string | null;
  prompt_template: string;
  tags: string[];
  scope: 'global' | 'customer';
}

export interface RecentStats {
  triggered_today: number;
  sent_today: number;
  suggested_today: number;
  failed_today: number;
  skipped: {
    human_replied: number;
    dup: number;
    throttled: number;
    borderline: number;
  };
}

// === API ===

export const groupAiApi = {
  // ICP
  getIcp: () => portalApi.get<ICPState>('/portal/group-ai/icp').then(r => r.data),
  updateIcp: (icp_text: string | null) =>
    portalApi.put('/portal/group-ai/icp', { icp_text }),

  // Thresholds
  updateThresholds: (body: Partial<ICPState['thresholds']>) =>
    portalApi.put('/portal/group-ai/thresholds', body),

  // Cases
  listCases: (include_inactive = false) =>
    portalApi.get<CaseStudy[]>('/portal/group-ai/case-studies', { params: { include_inactive } })
      .then(r => r.data),
  createCase: (body: Omit<CaseStudy, 'id' | 'active' | 'source' | 'created_at'>) =>
    portalApi.post<{ id: number }>('/portal/group-ai/case-studies', body),
  updateCase: (id: number, body: Partial<CaseStudy>) =>
    portalApi.put(`/portal/group-ai/case-studies/${id}`, body),
  deleteCase: (id: number) =>
    portalApi.delete(`/portal/group-ai/case-studies/${id}`),
  extractCases: (max_history = 100) =>
    portalApi.post<{ candidates: CaseStudyExtractedCandidate[] }>(
      '/portal/group-ai/case-studies/extract', null, { params: { max_history } },
    ).then(r => r.data),
  batchCreateCases: (cases: CaseStudyExtractedCandidate[]) =>
    portalApi.post<{ ids: number[] }>('/portal/group-ai/case-studies/batch', { cases }),

  // Accounts + persona
  listAccounts: () =>
    portalApi.get<{ id: number; phone: string; status: string }[]>('/portal/group-ai/accounts')
      .then(r => r.data),
  getPersona: (account_id: number) =>
    portalApi.get<WorkerPersona | null>(`/portal/group-ai/accounts/${account_id}/persona`)
      .then(r => r.data),
  upsertPersona: (account_id: number, body: Partial<WorkerPersona> & { customer_id: number }) =>
    portalApi.put(`/portal/group-ai/accounts/${account_id}/persona`, body),

  // Chitchat
  listChitchatTopics: () =>
    portalApi.get<ChitchatTopic[]>('/portal/group-ai/chitchat-topics').then(r => r.data),
  createChitchatTopic: (body: Omit<ChitchatTopic, 'id' | 'scope'>) =>
    portalApi.post<{ id: number }>('/portal/group-ai/chitchat-topics', body),

  // Stats
  getRecentStats: () =>
    portalApi.get<RecentStats>('/portal/group-ai/stats/recent').then(r => r.data),
};
```

- [ ] **Step 2.2: Layout.tsx 加 menu 项**

修改 `frontend/src/portal/Layout.tsx`：在 menu items 数组里加：

```typescript
{
  key: '/portal/group-ai',
  icon: <RobotOutlined />,  // 从 @ant-design/icons import
  label: <Link to="/portal/group-ai">群内 AI 销售员</Link>,
},
```

并在 import 区域加 `RobotOutlined`。

- [ ] **Step 2.3: 加 sub-routes**

在 portal 路由配置里 (找 `<Routes>` 配置文件，可能在 App.tsx 或 portal/index.tsx)，加：

```typescript
<Route path="group-ai" element={<GroupAiLayout />}>
  <Route index element={<Navigate to="icp" replace />} />
  <Route path="icp" element={<IcpEditor />} />
  <Route path="thresholds" element={<Thresholds />} />
  <Route path="cases" element={<CaseStudies />} />
  <Route path="personas" element={<WorkerPersonas />} />
  <Route path="chitchat" element={<ChitchatTopics />} />
  <Route path="stats" element={<RealtimeStats />} />
</Route>
```

`GroupAiLayout.tsx` 是子 sidebar + Outlet 容器（参考 portal 现有 sub-route 模式）。

- [ ] **Step 2.4: 提交**

```bash
cd /var/tgsc/.claude/worktrees/feature+group-ai-sales-portal
git add frontend/src/portal/api/groupAi.ts frontend/src/portal/Layout.tsx \
        frontend/src/portal/App.tsx frontend/src/portal/pages/GroupAI/index.tsx
git commit -m "feat(group-ai/portal): nav entry + sub-route scaffold + typed API client"
```

---

## Task 3: ICP 编辑器页

**Files:**
- Create: `frontend/src/portal/pages/GroupAI/IcpEditor.tsx`

- [ ] **Step 3.1: 组件骨架**

```typescript
/**
 * IcpEditor — ICP 画像自由文本编辑器 (200-500 字).
 *
 * 保存后自动 re-embed (backend 自动). 前端只显示 has_embedding 状态。
 */
import React from 'react';
import { Form, Input, Button, Alert, Space, Typography } from 'antd';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { groupAiApi } from '../../api/groupAi';

const { TextArea } = Input;
const { Title, Paragraph } = Typography;

const EXAMPLE_PLACEHOLDER = `示例:
想找 BTC/USDT 大额场外买家, 单笔 100k USDT 以上, 海外华人优先.
不要小白和倒卖中间人, 不要询价不付钱的.
理想行业: 矿企 / 海外贸易 / 跨境支付.`;

export default function IcpEditor() {
  const [form] = Form.useForm();
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ['portal-icp'],
    queryFn: () => groupAiApi.getIcp(),
  });
  const mutation = useMutation({
    mutationFn: (icp_text: string | null) => groupAiApi.updateIcp(icp_text),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['portal-icp'] }),
  });

  React.useEffect(() => {
    if (data) form.setFieldsValue({ icp_text: data.icp_text || '' });
  }, [data, form]);

  return (
    <div style={{ maxWidth: 800 }}>
      <Title level={3}>ICP 客户画像</Title>
      <Paragraph type="secondary">
        用 200-500 字自由文本描述你的理想客户. 保存后系统会自动生成 embedding,
        用于群消息的 Layer 2 智能过滤 (与你描述相似的消息才会触发 AI 回复).
      </Paragraph>

      {data && !data.has_embedding && data.icp_text && (
        <Alert
          type="warning"
          message="ICP 文本已保存但 embedding 生成失败"
          description="Layer 2 暂时关闭. 系统会在后台重试 embedding. 你也可以点'保存'重新触发."
          style={{ marginBottom: 16 }}
        />
      )}

      <Form
        form={form}
        layout="vertical"
        onFinish={(values) => mutation.mutate(values.icp_text || null)}
      >
        <Form.Item
          name="icp_text"
          rules={[
            { max: 500, message: '不要超过 500 字' },
          ]}
        >
          <TextArea
            rows={10}
            placeholder={EXAMPLE_PLACEHOLDER}
            showCount
            maxLength={500}
          />
        </Form.Item>

        <Form.Item>
          <Space>
            <Button
              type="primary" htmlType="submit"
              loading={mutation.isPending}
            >
              保存并重新生成 embedding
            </Button>
            <Button onClick={() => form.setFieldsValue({ icp_text: '' })}>
              清空
            </Button>
          </Space>
        </Form.Item>
      </Form>
    </div>
  );
}
```

- [ ] **Step 3.2: 提交**

```bash
git add frontend/src/portal/pages/GroupAI/IcpEditor.tsx
git commit -m "feat(group-ai/portal): ICP editor page with auto re-embedding"
```

---

## Task 4: Thresholds 滑块页

**Files:**
- Create: `frontend/src/portal/pages/GroupAI/Thresholds.tsx`

- [ ] **Step 4.1: 组件骨架**

```typescript
/**
 * Thresholds — 三层过滤灵敏度滑块.
 *
 * - Layer 2 ICP 相似度 (0.3 - 0.8)
 * - Layer 3 LLM 评分 (40 - 90)
 * - Layer 3 置信度 (0.5 - 0.95)
 */
import React from 'react';
import { Slider, Card, Button, Space, Typography, Tag } from 'antd';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { groupAiApi } from '../../api/groupAi';

const { Title, Text } = Typography;

const DEFAULTS = { layer2_sim: 0.55, layer3_score: 60, layer3_confidence: 0.7 };

export default function Thresholds() {
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ['portal-icp'],
    queryFn: () => groupAiApi.getIcp(),
  });
  const [values, setValues] = React.useState(DEFAULTS);

  React.useEffect(() => {
    if (data?.thresholds) setValues(data.thresholds);
  }, [data]);

  const mutation = useMutation({
    mutationFn: (body: typeof DEFAULTS) => groupAiApi.updateThresholds(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['portal-icp'] }),
  });

  return (
    <div style={{ maxWidth: 700 }}>
      <Title level={3}>识别灵敏度</Title>

      <Card title="Layer 2: ICP 画像相似度阈值" style={{ marginBottom: 16 }}>
        <Text type="secondary">
          消息与你 ICP 画像的余弦相似度 ≥ 此值才进入 Layer 3.
          阈值越低识别越宽松 (更多消息进入下一层), 越高越严.
        </Text>
        <Slider
          min={0.3} max={0.8} step={0.05}
          value={values.layer2_sim}
          onChange={(v) => setValues({ ...values, layer2_sim: v as number })}
          marks={{ 0.3: '0.3 宽松', 0.55: '默认', 0.8: '0.8 严格' }}
          style={{ marginTop: 24 }}
        />
      </Card>

      <Card title="Layer 3: LLM 评分阈值" style={{ marginBottom: 16 }}>
        <Text type="secondary">
          LLM 给消息打 0-100 分 (业务需求强度). 此值以上才生成回复.
        </Text>
        <Slider
          min={40} max={90} step={5}
          value={values.layer3_score}
          onChange={(v) => setValues({ ...values, layer3_score: v as number })}
          marks={{ 40: '40 宽', 60: '默认', 90: '90 严' }}
          style={{ marginTop: 24 }}
        />
      </Card>

      <Card title="Layer 3: LLM 置信度阈值" style={{ marginBottom: 16 }}>
        <Slider
          min={0.5} max={0.95} step={0.05}
          value={values.layer3_confidence}
          onChange={(v) => setValues({ ...values, layer3_confidence: v as number })}
          marks={{ 0.5: '0.5', 0.7: '默认', 0.95: '0.95' }}
          style={{ marginTop: 24 }}
        />
      </Card>

      <Space>
        <Button
          type="primary" loading={mutation.isPending}
          onClick={() => mutation.mutate(values)}
        >
          保存
        </Button>
        <Button onClick={() => setValues(DEFAULTS)}>恢复默认</Button>
        <Tag>当前生效: L2={data?.thresholds.layer2_sim} L3-S={data?.thresholds.layer3_score} L3-C={data?.thresholds.layer3_confidence}</Tag>
      </Space>
    </div>
  );
}
```

- [ ] **Step 4.2: 提交**

```bash
git add frontend/src/portal/pages/GroupAI/Thresholds.tsx
git commit -m "feat(group-ai/portal): thresholds page (3 sliders + presets)"
```

---

## Task 5: 案例库 CRUD 页 + 历史抽取 modal

**Files:**
- Create: `frontend/src/portal/pages/GroupAI/CaseStudies.tsx`
- Create: `frontend/src/portal/pages/GroupAI/CaseExtractModal.tsx`

- [ ] **Step 5.1: 主页**

`CaseStudies.tsx` 骨架（Ant Design Table + Drawer 编辑表单 + "扫描历史"按钮）：

```typescript
import React from 'react';
import { Table, Button, Space, Drawer, Form, Input, Tag, Popconfirm, Typography } from 'antd';
import { PlusOutlined, ScanOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { groupAiApi, CaseStudy } from '../../api/groupAi';
import CaseExtractModal from './CaseExtractModal';

const { Title, Paragraph } = Typography;

export default function CaseStudies() {
  const [drawerOpen, setDrawerOpen] = React.useState(false);
  const [editing, setEditing] = React.useState<CaseStudy | null>(null);
  const [extractOpen, setExtractOpen] = React.useState(false);
  const [form] = Form.useForm();
  const qc = useQueryClient();

  const { data: cases = [] } = useQuery({
    queryKey: ['portal-cases'],
    queryFn: () => groupAiApi.listCases(),
  });

  const createMut = useMutation({
    mutationFn: (body: any) => groupAiApi.createCase(body),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['portal-cases'] }); setDrawerOpen(false); form.resetFields(); },
  });
  const updateMut = useMutation({
    mutationFn: ({ id, body }: { id: number; body: any }) => groupAiApi.updateCase(id, body),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['portal-cases'] }); setDrawerOpen(false); setEditing(null); form.resetFields(); },
  });
  const deleteMut = useMutation({
    mutationFn: (id: number) => groupAiApi.deleteCase(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['portal-cases'] }),
  });

  const columns = [
    { title: '行业', dataIndex: 'industry' },
    { title: '规模', dataIndex: 'deal_size' },
    { title: '周期', dataIndex: 'period' },
    { title: '问题', dataIndex: 'problem', ellipsis: true },
    { title: '方案', dataIndex: 'solution', ellipsis: true },
    { title: '效果', dataIndex: 'outcome', ellipsis: true },
    { title: '标签', dataIndex: 'tags',
      render: (t: string[]) => t?.map(x => <Tag key={x}>{x}</Tag>) },
    { title: '来源', dataIndex: 'source',
      render: (s: string) => <Tag color={s === 'manual_portal' ? 'blue' : 'green'}>{s}</Tag> },
    { title: '操作', render: (_: any, r: CaseStudy) => (
      <Space>
        <Button size="small" onClick={() => { setEditing(r); form.setFieldsValue(r); setDrawerOpen(true); }}>编辑</Button>
        <Popconfirm title="确认禁用?" onConfirm={() => deleteMut.mutate(r.id)}>
          <Button size="small" danger>禁用</Button>
        </Popconfirm>
      </Space>
    ) },
  ];

  return (
    <div>
      <Title level={3}>成交案例库</Title>
      <Paragraph type="secondary">
        AI 回复时会引用真实案例 + 具体数字, 避免空泛套话. 案例越多, 数字反幻觉越精准.
      </Paragraph>

      <Space style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />}
                onClick={() => { setEditing(null); form.resetFields(); setDrawerOpen(true); }}>
          手动录入
        </Button>
        <Button icon={<ScanOutlined />} onClick={() => setExtractOpen(true)}>
          从历史会话扫描
        </Button>
      </Space>

      <Table columns={columns} dataSource={cases} rowKey="id" />

      <Drawer
        title={editing ? '编辑案例' : '新增案例'}
        open={drawerOpen} onClose={() => { setDrawerOpen(false); setEditing(null); }}
        width={600}
      >
        <Form form={form} layout="vertical"
              onFinish={(values) => {
                if (editing) updateMut.mutate({ id: editing.id, body: values });
                else createMut.mutate(values);
              }}>
          <Form.Item name="industry" label="行业"><Input /></Form.Item>
          <Form.Item name="deal_size" label="规模"><Input placeholder="100k USDT" /></Form.Item>
          <Form.Item name="period" label="周期"><Input placeholder="3 天" /></Form.Item>
          <Form.Item name="problem" label="问题" rules={[{ required: true }]}><Input.TextArea rows={3} /></Form.Item>
          <Form.Item name="solution" label="方案" rules={[{ required: true }]}><Input.TextArea rows={3} /></Form.Item>
          <Form.Item name="outcome" label="效果" rules={[{ required: true }]}><Input.TextArea rows={3} /></Form.Item>
          <Form.Item name="tags" label="标签">
            <Input placeholder="逗号分隔, e.g. OTC,USDT" />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={createMut.isPending || updateMut.isPending}>
            保存
          </Button>
        </Form>
      </Drawer>

      <CaseExtractModal open={extractOpen} onClose={() => setExtractOpen(false)} />
    </div>
  );
}
```

`CaseExtractModal.tsx` 骨架：

```typescript
import React from 'react';
import { Modal, Button, List, Checkbox, message, Spin, Typography } from 'antd';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { groupAiApi, CaseStudyExtractedCandidate } from '../../api/groupAi';

const { Title, Paragraph } = Typography;

export default function CaseExtractModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [candidates, setCandidates] = React.useState<CaseStudyExtractedCandidate[]>([]);
  const [selected, setSelected] = React.useState<Set<number>>(new Set());
  const qc = useQueryClient();

  const extractMut = useMutation({
    mutationFn: () => groupAiApi.extractCases(100),
    onSuccess: (data) => setCandidates(data.candidates),
  });
  const batchMut = useMutation({
    mutationFn: () => {
      const items = candidates.filter((_, i) => selected.has(i));
      return groupAiApi.batchCreateCases(items);
    },
    onSuccess: () => {
      message.success(`已录入 ${selected.size} 条`);
      qc.invalidateQueries({ queryKey: ['portal-cases'] });
      setSelected(new Set());
      setCandidates([]);
      onClose();
    },
  });

  React.useEffect(() => {
    if (open && candidates.length === 0) extractMut.mutate();
  }, [open]);

  return (
    <Modal title="从主号历史会话扫描案例" open={open} onCancel={onClose} width={800}
           footer={[
             <Button key="cancel" onClick={onClose}>取消</Button>,
             <Button key="save" type="primary"
                     disabled={selected.size === 0}
                     loading={batchMut.isPending}
                     onClick={() => batchMut.mutate()}>
               录入选中 {selected.size} 条
             </Button>,
           ]}>
      {extractMut.isPending ? <Spin tip="AI 扫描中..." /> : (
        <>
          <Paragraph type="secondary">
            勾选要录入的案例。AI 自动从主号历史聊天里识别出的"已完成成交"事件，需要你审一遍。
          </Paragraph>
          <List
            dataSource={candidates}
            renderItem={(item, i) => (
              <List.Item>
                <Checkbox
                  checked={selected.has(i)}
                  onChange={(e) => {
                    const next = new Set(selected);
                    if (e.target.checked) next.add(i); else next.delete(i);
                    setSelected(next);
                  }}
                >
                  <strong>{item.industry || '未填'} | {item.deal_size}</strong> | {item.period}
                  <br />
                  问题: {item.problem}<br />
                  方案: {item.solution}<br />
                  效果: {item.outcome}
                </Checkbox>
              </List.Item>
            )}
          />
        </>
      )}
    </Modal>
  );
}
```

- [ ] **Step 5.2: 提交**

```bash
git add frontend/src/portal/pages/GroupAI/CaseStudies.tsx \
        frontend/src/portal/pages/GroupAI/CaseExtractModal.tsx
git commit -m "feat(group-ai/portal): case_studies CRUD + auto-extract review modal"
```

---

## Task 6: 人设管理页（per worker account 卡片）

**Files:**
- Create: `frontend/src/portal/pages/GroupAI/WorkerPersonas.tsx`

- [ ] **Step 6.1: 组件骨架**

```typescript
/**
 * WorkerPersonas — 每个 worker 账号一张人设卡, 可编辑/重置.
 *
 * 数据流: list accounts → click → 拉 persona → drawer 编辑 → upsert.
 */
import React from 'react';
import { Card, Avatar, Button, Drawer, Form, Input, Select, Slider, InputNumber, Space, Tag, Typography, Row, Col } from 'antd';
import { UserOutlined, EditOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { groupAiApi, WorkerPersona } from '../../api/groupAi';

const { Title, Paragraph } = Typography;

const SPEAKING_STYLES = [
  { value: 'formal', label: 'formal 正式' },
  { value: 'casual', label: 'casual 随意 (默认)' },
  { value: 'techy', label: 'techy 技术风' },
  { value: 'northeastern_dialect', label: '东北话' },
  { value: 'cantonese_flavor', label: '广东话' },
];

export default function WorkerPersonas() {
  const [editingAcc, setEditingAcc] = React.useState<number | null>(null);
  const [form] = Form.useForm();
  const qc = useQueryClient();

  const { data: accounts = [] } = useQuery({
    queryKey: ['portal-accounts'],
    queryFn: () => groupAiApi.listAccounts(),
  });
  const { data: persona } = useQuery({
    queryKey: ['portal-persona', editingAcc],
    queryFn: () => editingAcc ? groupAiApi.getPersona(editingAcc) : Promise.resolve(null),
    enabled: !!editingAcc,
  });

  React.useEffect(() => {
    if (persona) form.setFieldsValue(persona);
  }, [persona, form]);

  const upsertMut = useMutation({
    mutationFn: (body: any) => groupAiApi.upsertPersona(editingAcc!, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['portal-persona', editingAcc] });
      setEditingAcc(null);
    },
  });

  return (
    <div>
      <Title level={3}>账号人设</Title>
      <Paragraph type="secondary">
        每个 worker 账号可独立配置语言风格 / 口头禅 / 活跃时段. 没配的账号用兜底默认 (保守模式).
      </Paragraph>

      <Row gutter={[16, 16]}>
        {accounts.map((acc) => (
          <Col span={8} key={acc.id}>
            <Card
              title={<Space><Avatar icon={<UserOutlined />} />{acc.phone}</Space>}
              extra={<Tag color={acc.status === 'active' ? 'green' : 'orange'}>{acc.status}</Tag>}
              actions={[
                <Button type="link" icon={<EditOutlined />} onClick={() => setEditingAcc(acc.id)}>
                  编辑人设
                </Button>,
              ]}
            >
              <Paragraph type="secondary">点击右下编辑</Paragraph>
            </Card>
          </Col>
        ))}
      </Row>

      <Drawer
        title={`人设: account #${editingAcc}`}
        open={!!editingAcc} onClose={() => setEditingAcc(null)} width={600}
      >
        <Form form={form} layout="vertical" initialValues={{
          customer_id: 0, // 占位; backend 实际从 token 推断
        }} onFinish={(values) => upsertMut.mutate({
          ...values, customer_id: 0,  // backend 会忽略, 用 customer auth
        })}>
          <Form.Item name="display_name" label="显示名"><Input /></Form.Item>
          <Form.Item name="region" label="地区"><Input placeholder="香港 / 上海" /></Form.Item>
          <Form.Item name="occupation" label="职业"><Input placeholder="OTC 中介 / SaaS 销售" /></Form.Item>
          <Form.Item name="speaking_style" label="语言风格"><Select options={SPEAKING_STYLES} /></Form.Item>
          <Form.Item name="catchphrases" label="口头禅 (一行一个)">
            <Select mode="tags" placeholder="搞不好 / 我跟你说" tokenSeparators={[',']} />
          </Form.Item>

          <Form.Item label="日回复上限">
            <Form.Item name="daily_reply_quota" noStyle><InputNumber min={1} max={50} /></Form.Item> 条/天
          </Form.Item>
          <Form.Item label="单群日限">
            <Form.Item name="per_chat_daily_quota" noStyle><InputNumber min={1} max={20} /></Form.Item> 条/群/天
          </Form.Item>
          <Form.Item label="单群冷却">
            <Form.Item name="per_chat_cooldown_minutes" noStyle><InputNumber min={0} max={1440} /></Form.Item> 分钟
          </Form.Item>
          <Form.Item label="日闲聊上限">
            <Form.Item name="daily_chitchat_quota" noStyle><InputNumber min={0} max={50} /></Form.Item> 条/天
          </Form.Item>

          {/* 活跃时段编辑器 — 简化版: 用 dynamic JSON; Phase 后续做时段网格 */}
          <Form.Item name="active_hours" label="活跃时段 (JSON)">
            <Input.TextArea rows={4} placeholder='{"mon": [[9, 18]], ...}' />
          </Form.Item>

          <Button type="primary" htmlType="submit" loading={upsertMut.isPending}>
            保存
          </Button>
        </Form>
      </Drawer>
    </div>
  );
}
```

- [ ] **Step 6.2: 提交**

```bash
git add frontend/src/portal/pages/GroupAI/WorkerPersonas.tsx
git commit -m "feat(group-ai/portal): worker_persona editor (per-account cards)"
```

---

## Task 7: 闲聊话题库页

**Files:**
- Create: `frontend/src/portal/pages/GroupAI/ChitchatTopics.tsx`

- [ ] **Step 7.1: 组件骨架**

```typescript
import React from 'react';
import { List, Card, Tag, Button, Form, Input, Select, Modal, Typography } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { groupAiApi } from '../../api/groupAi';

const { Title, Paragraph } = Typography;

const CATEGORIES = ['weather', 'food', 'news', 'life', 'tech', 'sports', 'gossip', 'work', 'travel', 'mood'];

export default function ChitchatTopics() {
  const [modalOpen, setModalOpen] = React.useState(false);
  const [form] = Form.useForm();
  const qc = useQueryClient();

  const { data: topics = [] } = useQuery({
    queryKey: ['portal-chitchat-topics'],
    queryFn: () => groupAiApi.listChitchatTopics(),
  });
  const createMut = useMutation({
    mutationFn: (body: any) => groupAiApi.createChitchatTopic(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['portal-chitchat-topics'] });
      setModalOpen(false);
      form.resetFields();
    },
  });

  return (
    <div>
      <Title level={3}>闲聊话题库</Title>
      <Paragraph type="secondary">
        账号在群里偶尔发的"非业务闲聊"模板. 系统内置 30+ 全局话题, 你也可以加自己的.
        闲聊永远会避开你的业务关键词, 不会无意触发自家 AI 回复.
      </Paragraph>

      <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)} style={{ marginBottom: 16 }}>
        添加我的话题
      </Button>

      <List
        grid={{ gutter: 16, column: 3 }}
        dataSource={topics}
        renderItem={(t) => (
          <List.Item>
            <Card
              title={<Tag color={t.scope === 'global' ? 'blue' : 'green'}>{t.scope}</Tag>}
              size="small"
            >
              <p>{t.prompt_template}</p>
              <div>{t.tags?.map(tag => <Tag key={tag}>{tag}</Tag>)}</div>
            </Card>
          </List.Item>
        )}
      />

      <Modal title="添加话题" open={modalOpen} onCancel={() => setModalOpen(false)} footer={null}>
        <Form form={form} layout="vertical" onFinish={(v) => createMut.mutate(v)}>
          <Form.Item name="topic_category" label="分类"><Select options={CATEGORIES.map(c => ({ value: c, label: c }))} /></Form.Item>
          <Form.Item name="prompt_template" label="模板" rules={[{ required: true }]}>
            <Input.TextArea rows={3} placeholder="今天{城市}天气不错, 出门带伞" />
          </Form.Item>
          <Form.Item name="tags" label="标签">
            <Select mode="tags" tokenSeparators={[',']} />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={createMut.isPending}>添加</Button>
        </Form>
      </Modal>
    </div>
  );
}
```

- [ ] **Step 7.2: 提交**

```bash
git add frontend/src/portal/pages/GroupAI/ChitchatTopics.tsx
git commit -m "feat(group-ai/portal): chitchat_topics page (list + customer-scoped add)"
```

---

## Task 8: 实时统计页（精简版 + skip_reason 展开）

**Files:**
- Create: `frontend/src/portal/pages/GroupAI/RealtimeStats.tsx`

- [ ] **Step 8.1: 组件骨架**

```typescript
/**
 * RealtimeStats — 今日 3 核心数字 + 可展开 skip_reason 分布.
 *
 * 数据来自 GET /portal/group-ai/stats/recent. 每 30s refetch.
 */
import React from 'react';
import { Card, Row, Col, Statistic, Collapse, Tag, Typography, Empty } from 'antd';
import { useQuery } from '@tanstack/react-query';
import { groupAiApi } from '../../api/groupAi';

const { Title, Paragraph } = Typography;

export default function RealtimeStats() {
  const { data } = useQuery({
    queryKey: ['portal-stats'],
    queryFn: () => groupAiApi.getRecentStats(),
    refetchInterval: 30000,
  });

  if (!data) return <Empty description="加载中" />;

  const conversion = data.sent_today > 0
    ? `${((data.sent_today / Math.max(1, data.triggered_today)) * 100).toFixed(1)}%`
    : '0%';
  const skippedTotal = Object.values(data.skipped).reduce((a, b) => a + b, 0);

  return (
    <div>
      <Title level={3}>今日数据 (UTC)</Title>
      <Paragraph type="secondary">
        每 30 秒自动刷新. 客户私聊转化率反映"群里被回复后主动私聊主号"的比例.
      </Paragraph>

      <Row gutter={16}>
        <Col span={8}>
          <Card>
            <Statistic title="今日命中" value={data.triggered_today} suffix="条" />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic title="今日发出" value={data.sent_today} suffix="条" />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic title="发出占比" value={conversion} />
          </Card>
        </Col>
      </Row>

      <Collapse style={{ marginTop: 16 }} items={[{
        key: '1',
        label: `跳过明细 (共 ${skippedTotal} 条) + 失败/草稿`,
        children: (
          <div>
            <p><Tag>真人接话</Tag> {data.skipped.human_replied} 条 — 真人或其他号已接, AI 礼貌避让</p>
            <p><Tag>同线索去重</Tag> {data.skipped.dup} 条 — 48h 内已经回过同一客户</p>
            <p><Tag>限流</Tag> {data.skipped.throttled} 条 — 账号日额 / 群冷却保护</p>
            <p><Tag>边界值</Tag> {data.skipped.borderline} 条 — Layer 3 评分边缘, 留存供后续训练阈值</p>
            <p><Tag color="orange">副驾驶草稿</Tag> {data.suggested_today} 条 — 反幻觉拒, 待你在 Inbox 审</p>
            <p><Tag color="red">失败</Tag> {data.failed_today} 条 — LLM / 发送失败</p>
          </div>
        ),
      }]} />
    </div>
  );
}
```

- [ ] **Step 8.2: 提交**

```bash
git add frontend/src/portal/pages/GroupAI/RealtimeStats.tsx
git commit -m "feat(group-ai/portal): realtime stats page (3 core + skip breakdown)"
```

---

## Task 9: Admin Inbox 群内 AI 互动视图

**Files:**
- Create: `frontend/src/pages/inbox/GroupAIInteractions.tsx`
- Modify: `frontend/src/pages/Inbox.tsx`（加 tab 或独立路由）
- Create: `frontend/src/services/groupAi.ts`
- Create: `frontend/src/hooks/useGroupAiWebsocket.ts`

- [ ] **Step 9.1: 写 admin API client**

`frontend/src/services/groupAi.ts`:

```typescript
import api from './api';

export interface InboxRow {
  id: number; status: string; reply_text: string | null;
  chat_id: number; source_user_id: number; source_text: string;
  sent_at: string | null; created_at: string;
  solution_topic: string | null; extracted_needs: string[] | null;
}

export const groupAiAdminApi = {
  listInbox: (customer_id: number) =>
    api.get<InboxRow[]>(`/inbox/group-ai/customers/${customer_id}/recent`).then(r => r.data),
  approveSuggested: (pr_id: number) =>
    api.post(`/inbox/group-ai/suggested/${pr_id}/approve`),
  editSuggested: (pr_id: number, reply_text: string) =>
    api.put(`/inbox/group-ai/suggested/${pr_id}`, { reply_text }),
};
```

- [ ] **Step 9.2: 写 WebSocket hook**

`frontend/src/hooks/useGroupAiWebsocket.ts`:

```typescript
/**
 * Listen for `ai_suggestion_pending` events. Refresh inbox + show toast.
 */
import React from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { notification } from 'antd';

export function useGroupAiWebsocket(customerId?: number) {
  const qc = useQueryClient();
  React.useEffect(() => {
    // 复用现有 ws connection: grep src/hooks for useWebSocket / WsContext
    // 简化版: 直接 new WebSocket
    const ws = new WebSocket(`${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws`);
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        if (msg.type === 'ai_suggestion_pending') {
          if (customerId && msg.customer_id !== customerId) return;
          qc.invalidateQueries({ queryKey: ['admin-inbox-group-ai', msg.customer_id] });
          notification.info({
            message: 'AI 草稿待审',
            description: `#${msg.pending_reply_id}: ${msg.suggested_text?.slice(0, 50)}...`,
          });
        }
      } catch {}
    };
    return () => ws.close();
  }, [customerId, qc]);
}
```

- [ ] **Step 9.3: 写 GroupAIInteractions.tsx**

```typescript
import React from 'react';
import { Table, Tag, Button, Modal, Input, Space, Typography } from 'antd';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { groupAiAdminApi, InboxRow } from '../../services/groupAi';
import { useGroupAiWebsocket } from '../../hooks/useGroupAiWebsocket';

const { Title } = Typography;

export default function GroupAIInteractions({ customerId }: { customerId: number }) {
  useGroupAiWebsocket(customerId);
  const qc = useQueryClient();
  const [editing, setEditing] = React.useState<InboxRow | null>(null);
  const [editText, setEditText] = React.useState('');

  const { data: rows = [] } = useQuery({
    queryKey: ['admin-inbox-group-ai', customerId],
    queryFn: () => groupAiAdminApi.listInbox(customerId),
    refetchInterval: 15000,
  });

  const approveMut = useMutation({
    mutationFn: (pr_id: number) => groupAiAdminApi.approveSuggested(pr_id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-inbox-group-ai', customerId] }),
  });
  const editMut = useMutation({
    mutationFn: ({ pr_id, text }: { pr_id: number; text: string }) =>
      groupAiAdminApi.editSuggested(pr_id, text),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-inbox-group-ai', customerId] });
      setEditing(null);
    },
  });

  const columns = [
    { title: '状态', dataIndex: 'status',
      render: (s: string) => <Tag color={s === 'sent' ? 'green' : 'orange'}>{s}</Tag> },
    { title: '客户消息', dataIndex: 'source_text', ellipsis: true },
    { title: '主题', dataIndex: 'solution_topic' },
    { title: '需求点', dataIndex: 'extracted_needs',
      render: (n: string[]) => n?.map(x => <Tag key={x}>{x}</Tag>) },
    { title: 'AI 回复', dataIndex: 'reply_text', ellipsis: true },
    { title: '操作', render: (_: any, r: InboxRow) => (
      r.status === 'suggested' ? (
        <Space>
          <Button size="small" onClick={() => { setEditing(r); setEditText(r.reply_text || ''); }}>编辑</Button>
          <Button size="small" type="primary" loading={approveMut.isPending}
                  onClick={() => approveMut.mutate(r.id)}>批准发送</Button>
        </Space>
      ) : null
    ) },
  ];

  return (
    <div>
      <Title level={4}>群内 AI 互动</Title>
      <Table dataSource={rows} columns={columns} rowKey="id" pagination={{ pageSize: 20 }} />

      <Modal title={`编辑 #${editing?.id}`} open={!!editing} onCancel={() => setEditing(null)}
             onOk={() => editing && editMut.mutate({ pr_id: editing.id, text: editText })}
             confirmLoading={editMut.isPending}>
        <Input.TextArea rows={4} value={editText} onChange={(e) => setEditText(e.target.value)} />
      </Modal>
    </div>
  );
}
```

- [ ] **Step 9.4: Inbox.tsx 加 link 或 tab**

修改现有 Inbox.tsx，在合适位置（如顶部 nav）加：

```typescript
<Button type="link" onClick={() => navigate('/admin/group-ai-interactions')}>群内 AI 互动</Button>
```

或加 Tab，按 Inbox.tsx 现有结构决定。

- [ ] **Step 9.5: 提交**

```bash
git add frontend/src/services/groupAi.ts frontend/src/hooks/useGroupAiWebsocket.ts \
        frontend/src/pages/inbox/GroupAIInteractions.tsx frontend/src/pages/Inbox.tsx
git commit -m "feat(group-ai/portal): admin Inbox group-AI interactions + WS notifications"
```

---

## Task 10-12: Admin A/B 实验 UI

> 路由建议：`/admin/ab/experiments` (list)、`/admin/ab/experiments/new`、`/admin/ab/experiments/:id` (report)

**Files:**
- Create: `frontend/src/pages/ab/ExperimentList.tsx`
- Create: `frontend/src/pages/ab/ExperimentCreate.tsx`
- Create: `frontend/src/pages/ab/ExperimentReport.tsx`
- Extend: `frontend/src/services/groupAi.ts` 加 A/B endpoints

- [ ] **Step 10.1: 扩展 admin API client**

```typescript
// frontend/src/services/groupAi.ts 追加

export interface ABExperiment {
  id: number; name: string; description: string | null;
  scope: 'global' | 'customer' | 'monitor';
  scope_value: number | null;
  variants: { tag: string; weight: number; params: Record<string, any> }[];
  status: 'draft' | 'running' | 'finished' | 'paused';
  primary_metric: string | null;
  started_at: string | null; ended_at: string | null;
}

export const abApi = {
  list: () =>
    api.get<ABExperiment[]>('/admin/group-ai/ab/experiments').then(r => r.data),
  create: (body: Partial<ABExperiment>) =>
    api.post<{ id: number }>('/admin/group-ai/ab/experiments', body),
  start: (id: number) =>
    api.put(`/admin/group-ai/ab/experiments/${id}/start`),
  stop: (id: number) =>
    api.put(`/admin/group-ai/ab/experiments/${id}/stop`),
  metrics: (id: number) =>
    api.get(`/admin/group-ai/ab/experiments/${id}/metrics`).then(r => r.data),
  report: (id: number) =>
    api.get(`/admin/group-ai/ab/experiments/${id}/report`).then(r => r.data),
  csvUrl: (id: number) => `/api/v1/admin/group-ai/ab/experiments/${id}/report.csv`,
};
```

- [ ] **Step 10.2: ExperimentList.tsx**

简单 Table + 状态切换按钮 + "创建实验" 入口 + 行点击进 report 页。

```typescript
import React from 'react';
import { Table, Button, Tag, Space, Popconfirm, Typography } from 'antd';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { abApi, ABExperiment } from '../../services/groupAi';

const { Title } = Typography;
const COLORS = { draft: 'default', running: 'green', finished: 'blue', paused: 'orange' };

export default function ExperimentList() {
  const nav = useNavigate();
  const qc = useQueryClient();
  const { data: exps = [] } = useQuery({ queryKey: ['admin-ab-list'], queryFn: () => abApi.list() });
  const startMut = useMutation({ mutationFn: (id: number) => abApi.start(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-ab-list'] }) });
  const stopMut = useMutation({ mutationFn: (id: number) => abApi.stop(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-ab-list'] }) });

  const columns = [
    { title: 'ID', dataIndex: 'id' },
    { title: '名称', dataIndex: 'name' },
    { title: '范围', dataIndex: 'scope',
      render: (s: string, r: ABExperiment) => `${s}${r.scope_value ? `:${r.scope_value}` : ''}` },
    { title: '主指标', dataIndex: 'primary_metric' },
    { title: '状态', dataIndex: 'status',
      render: (s: keyof typeof COLORS) => <Tag color={COLORS[s]}>{s}</Tag> },
    { title: '变体', dataIndex: 'variants',
      render: (v: ABExperiment['variants']) => v?.map(x => <Tag key={x.tag}>{x.tag} ({(x.weight * 100).toFixed(0)}%)</Tag>) },
    { title: '操作', render: (_: any, r: ABExperiment) => (
      <Space>
        <Button size="small" onClick={() => nav(`/admin/ab/experiments/${r.id}`)}>报告</Button>
        {r.status === 'draft' && <Button size="small" type="primary" onClick={() => startMut.mutate(r.id)}>启动</Button>}
        {r.status === 'running' && <Popconfirm title="停止后不能再启动" onConfirm={() => stopMut.mutate(r.id)}>
          <Button size="small" danger>停止</Button>
        </Popconfirm>}
      </Space>
    ) },
  ];

  return (
    <div>
      <Title level={3}>A/B 实验</Title>
      <Button type="primary" onClick={() => nav('/admin/ab/experiments/new')} style={{ marginBottom: 16 }}>
        创建实验
      </Button>
      <Table dataSource={exps} columns={columns} rowKey="id" />
    </div>
  );
}
```

- [ ] **Step 10.3: ExperimentCreate.tsx**

表单：name / scope / scope_value / primary_metric / variants (动态行)。提交后跳 list。骨架略，模式同 CaseStudies Drawer。

- [ ] **Step 10.4: ExperimentReport.tsx**

按 id 拉 report，展示：
- 实验元信息
- 每 variant 一卡：sent/suggested/skipped/failed + 4 metrics 数值 + CI95
- 显著性结论卡片：p / z / 是否显著
- CSV 下载按钮 (`window.location.href = abApi.csvUrl(id)`)

骨架略，Ant Design Descriptions + Statistic + Card + Button。

- [ ] **Step 10.5: 提交（3 task 合并 1 commit 也可）**

```bash
git add frontend/src/services/groupAi.ts frontend/src/pages/ab/
git commit -m "feat(group-ai/portal): admin A/B experiment UI (list + create + report)"
```

- [ ] **Step 10.6: App.tsx 加 admin routes**

```typescript
<Route path="/admin/ab/experiments" element={<ExperimentList />} />
<Route path="/admin/ab/experiments/new" element={<ExperimentCreate />} />
<Route path="/admin/ab/experiments/:id" element={<ExperimentReport />} />
<Route path="/admin/group-ai-interactions" element={<GroupAIInteractionsByCustomer />} />
```

`GroupAIInteractionsByCustomer` 是个 wrapper 让 admin 先选客户再看（或用 URL param）。

---

## Task 13: E2E (Playwright) happy path

**Files:**
- Create: `frontend/e2e/group-ai-portal.spec.ts`

- [ ] **Step 13.1: 写 Playwright 测试**

覆盖核心 happy path（grep 现有 `frontend/playwright.config.ts` 看是否已经有 E2E 框架；如无则装）：

```typescript
import { test, expect } from '@playwright/test';

test('客户能保存 ICP 并看到统计页', async ({ page }) => {
  // 假设有 e2e fixture 登录, 略
  await page.goto('/portal/group-ai/icp');
  await page.fill('textarea', '想找 USDT 大额买家');
  await page.click('button:has-text("保存并重新生成 embedding")');
  await expect(page.locator('.ant-message-success')).toBeVisible();

  await page.goto('/portal/group-ai/stats');
  await expect(page.locator('text=今日命中')).toBeVisible();
});

test('admin 能 approve suggested', async ({ page }) => {
  // 略
});
```

- [ ] **Step 13.2: 提交**

```bash
git add frontend/e2e/group-ai-portal.spec.ts
git commit -m "test(group-ai/portal): e2e happy path (Playwright)"
```

---

## Task 14: PR + release

- [ ] **Step 14.1: 全测试**

```bash
cd /var/tgsc/.claude/worktrees/feature+group-ai-sales-portal
npm --prefix frontend run typecheck   # 或 tsc --noEmit
npm --prefix frontend run build       # 验证生产编译
pytest backend/tests/ -k "portal_group_ai" -v
```

- [ ] **Step 14.2: 推 + PR**

```bash
git push -u origin feature/group-ai-sales-portal
gh pr create --title "feat(group-ai): Portal phase — unified UI (customer + admin + A/B)" --base main --body "$(cat <<'EOF'
## Summary

Portal phase 把 Phase 2a/3a/4a/5 累积的所有 UI 一次性做完。

### Backend (1 file)
- portal_group_ai.py: 客户视角端点 (复用 admin service, customer_id 从 JWT)

### Customer portal UI (frontend/src/portal/pages/GroupAI/)
- IcpEditor: ICP 文本编辑器 + 自动 re-embed
- Thresholds: 3 滑块 + 恢复默认
- CaseStudies: CRUD + 扫描历史 modal (review + 批量录入)
- WorkerPersonas: per-account 卡片 + 抽屉编辑
- ChitchatTopics: 列表 (全局/客户标签) + 客户加自定义
- RealtimeStats: 3 核心数 + 可展开 skip_reason 分布

### Admin UI
- Inbox/GroupAIInteractions: 列出 sent + suggested, edit + approve
- useGroupAiWebsocket: WS 推 ai_suggestion_pending → 自动 refetch + toast
- ab/ExperimentList + Create + Report (含 CSV 下载)

### E2E (Playwright)
- 客户 ICP 保存 happy path
- admin approve suggested happy path

## Test plan

- [ ] typecheck + production build OK
- [ ] backend portal_group_ai 测试 PASS
- [ ] 灰度: 用 1 个客户账号登 portal:
  - 录 ICP → DB 里看 embedding 写入
  - 录 1 条案例 → 看 reply_composer 实际引用
  - 改阈值 → DB lead_detector_thresholds 更新
  - 看 stats 页 → 数字与 DB 对得上
- [ ] admin: 故意让 compose 失败 → 看 Inbox 有 suggested 卡 + WS 弹窗 → approve → 状态变 sent

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Portal phase 完成判据

- [ ] PR merged
- [ ] 灰度客户能用 portal 完整自助配置（ICP / 案例 / 人设 / 闲聊 / 阈值）
- [ ] 销售能在 Inbox 完成 suggested 审核闭环
- [ ] 运营能在 admin 看 A/B 实验报告 + CSV 导出
- [ ] WebSocket 通知在真实网络下稳定（断线重连）

---

## 整条 9 周路线完成判据

到此为止，spec §9 的 6 个 Phase 都有了 plan 或落地代码：

| Phase | 状态 |
|---|---|
| Phase 1 骨架 | ✅ 实施完成 (PR #9) |
| Phase 2a 三层 + 案例 | plan 已写 |
| Phase 3a 拟人化 | plan 已写 |
| Phase 4a 销售衔接 + A/B 框架 backend | plan 已写 |
| Phase 5 A/B 完整化（含小迁移 account_lifecycle_events） | plan 已写 |
| Portal phase 统一 UI | plan 已写 |

**真核心需求"业务体感到位"判据**（不在本 plan 内，需要灰度数据验证）：
1. 灰度 1 个月被踢号率 < 5% / 周
2. 群内回复后 24h 私聊转化率 > 15%
3. 反幻觉失败率 < 8%
4. 真人接话检测精确率 > 80%
5. 5 个种子客户中 ≥ 4 个能独立完成 portal 首次配置
