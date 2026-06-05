# Admin Customer Operations Module — Design

**Date**: 2026-06-05
**Status**: Spec ready for plan
**Scope**: Frontend-only admin module that lets platform operators run the full customer lifecycle (register → activate → allocate → manage) without requiring customers to touch `/portal`.

---

## 1. Problem & Motivation

Today the customer-side flows (register, choose plan, pay USDT, manage subscription) live exclusively in the customer portal at `/portal/*`. For early-stage operations the team needs to onboard customers manually:

- Trial / seed customers who pay offline (wire, OTC USDT, internal favor)
- Sales-assisted onboarding where the customer is on a call and the operator drives the screen
- Internal QA and migrated accounts that should bypass payment
- Hand-holding the first 5–10 paying customers until the portal UX is polished ([[project-priority-polish-first]])

The backend already supports every action via `/admin/billing/*` and `/admin/features/*` endpoints — most importantly `POST /admin/billing/quick-provision`, which atomically creates the customer, activates the subscription (marked `tx_hash='admin_manual'`), credits the wallet, and triggers Epic 3 allocation + Epic 4 KB generation.

What's missing is a coherent admin UI that stitches these endpoints into one operator workflow. Today an operator has to either call the API by hand or jump between unrelated admin pages.

## 2. Goals

1. A single admin module where one operator can complete: create customer → activate subscription → confirm allocation → manage quotas/features → view usage.
2. Reuse 100% of existing backend endpoints. **No backend code or migrations.**
3. Customers onboarded this way can still log into `/portal/*` with the credentials the operator sets — admin onboarding is additive, not exclusive.
4. All destructive or hard-to-reverse actions require explicit confirmation with the impact preview.
5. Operator can always recover a customer's portal URL and (within the same session window) the initial password.

## 3. Non-Goals

- No customer-facing email sending. Credentials are handed off out-of-band (the operator screenshots / copies them from the post-create modal).
- No password reset flow built in this module. If the customer loses their password, the operator re-provisions or uses the existing customer-side reset path (out of scope; build when needed).
- No backend pagination. Customer count is well under 1,000 for the foreseeable future; if it crosses that threshold we add backend pagination later.
- No e2e (Playwright) coverage. Playwright scaffold already exists from Portal phase; admin e2e is deferred to the broader polish pass.
- No new role / permission model. Existing admin auth (`get_current_admin`) gates everything.
- No replacement of existing admin pages (BusinessOps, Inbox, billing/ActivationCodes, etc.). This module sits alongside them.

## 4. Architecture

### 4.1 Backend
Zero changes. Endpoints consumed:

| Action | Endpoint |
|---|---|
| Create customer + activate + allocate + KB | `POST /admin/billing/quick-provision` |
| List customers | `GET /admin/billing/customers` |
| Get customer (single) | `GET /admin/billing/customers/{id}` (via existing list filter or detail endpoint) |
| List invoices | `GET /admin/billing/invoices` |
| Reallocate accounts | `POST /admin/billing/customers/{id}/reallocate-accounts` |
| Reallocate groups | `POST /admin/billing/customers/{id}/reallocate-groups` |
| Regenerate KB | `POST /admin/billing/customers/{id}/regenerate-kb` |
| List feature registry | `GET /admin/features` |
| List customer features | `GET /admin/features/customers/{cid}/features` |
| Upsert customer feature | `PUT /admin/features/customers/{cid}/features/{slug}` |
| Remove customer feature | `DELETE /admin/features/customers/{cid}/features/{slug}` |
| Customer usage summary | `GET /admin/features/customers/{cid}/usage` |

If during plan execution a needed read endpoint turns out to be missing (e.g. fetching a single customer by id), the plan must call it out and prefer extending an existing endpoint over a new one.

### 4.2 Frontend layout

```
frontend/src/pages/customers/                  ← new
  CustomerListPage.tsx                          list + filters
  NewCustomerPage.tsx                           create form + credentials modal
  CustomerDetailPage.tsx                        tabs container
  tabs/
    OverviewTab.tsx                             quotas + renewal + resource summary
    BillingTab.tsx                              subscription + invoices + renew
    AllocationTab.tsx                           reallocate accounts/groups, regenerate KB
    QuotaFeaturesTab.tsx                        feature flags + quota ceilings
    UsageLogsTab.tsx                            token usage + AI calls

frontend/src/services/adminCustomers.ts        ← new typed API client (thin)
```

Routing additions in [App.tsx](frontend/src/App.tsx):

```
/customers                       → CustomerListPage (lazy)
/customers/new                   → NewCustomerPage (lazy)
/customers/:id                   → CustomerDetailPage (lazy, tab routing via search param)
```

Sidebar: new top-level menu item **"客户运营"** with `UserOutlined` icon, placed above existing items in [MainLayout.tsx](frontend/src/components/Layout/MainLayout.tsx) (or equivalent). Decision per user 2026-06-05.

### 4.3 Module boundaries

- **`services/adminCustomers.ts`** is the only file that talks to admin endpoints. Tabs and pages call typed functions, not raw axios.
- **Each tab is independently mounted** with its own `useQuery` keys. No tab assumes another tab has loaded. Tab order is presentation; data dependency is not.
- **No new state management** (no Zustand store, no Context). React Query cache is the source of truth, invalidated on mutation success.
- **No business logic in the frontend.** Every mutation is a thin wrapper around one backend endpoint. If something needs orchestration (e.g. "deactivate then reallocate"), do it as a backend endpoint in a separate effort.

## 5. UX Decisions

### 5.1 Sidebar entry
New top-level menu **"客户运营"** above existing items, with a child group:
```
👥 客户运营
   ├─ 客户列表           → /customers
   └─ 新建客户           → /customers/new
```

### 5.2 Customer list
- Columns: email, name, plan badge (Starter/Growth/Pro color-coded), status (active/expired/suspended), 续费倒计时 (days, red if <7), 钱包余额, 创建时间, 操作 (查看详情).
- Search box filters by email substring (client-side; we have <1000 rows).
- Plan filter, status filter (multi-select).
- Sort default: 创建时间 desc.
- Empty state: button "立即开户第一个客户" → `/customers/new`.

### 5.3 New customer form
Fields:
- email (required, validated; on blur calls list with email filter — if exists, inline error linking to existing customer detail)
- 初始密码 (required, min 8 chars). Button "🎲 生成随机 12 位密码" auto-fills.
- 姓名 (optional, defaults to email local-part server-side)
- 行业 (dropdown: crypto/ecommerce/b2b/gaming/mcn — same options as portal Register)
- 套餐 (radio: Starter $199 / Growth $299 / Pro $599, each card shows quotas)
- 备注 (textarea, optional, written as note on the manual transaction)
- 提交按钮: "开户并激活"

On submit:
1. POST `/admin/billing/quick-provision`
2. Success → modal popup:
   ```
   ✅ 客户已创建并激活

   email:       alice@acme.io
   初始密码:    Xk9!mPq2bRtY      [复制]
   portal 链接: https://tg1.ai/portal/login   [复制]

   ⚠ 此密码仅在本次显示。关闭后请通过其他途径联系客户。

   [前往客户详情]   [关闭]
   ```
3. Failure → inline form errors for 4xx, global notification for 5xx.

### 5.4 Customer detail tabs

All tabs share a sticky header with: customer name, email, plan badge, status, 续费倒计时, 钱包余额.

**Overview tab**
- 4 `QuotaMeter` cards (账号 used/total, 群组 used/total, Token used/total, 线索 used/total)
- 续费倒计时
- 资源摘要: 已分配账号 N 个 / 已加入群组 M 个 / KB 条目 K 条 (with links to existing admin pages filtered by `customer_id`)
- 自动 polling 5s × 6 attempts after create/reallocate, to surface async allocation progress; stop polling once stable.

**Billing tab**
- Current subscription card (plan / period / 续费倒计时 / auto-renew off because manual)
- Invoice history table (date, amount, status, tx_hash, note)
- Action: "手动续期" → modal: choose plan (or keep) + duration months + note → calls existing extend endpoint (if not present, plan task explicitly notes this gap)

**Allocation tab**
Three large action buttons with descriptive text:
- 🔄 重新分配账号 — current N accounts → modal confirm "将释放 N 个账号回池，并按当前套餐配额重新分配。此操作影响客户群控运行，建议提前通知。" → POST reallocate-accounts → success toast + invalidate Overview
- 🔄 重新分配群组 — same pattern
- 🧠 重生成行业 KB — modal confirm "将删除当前 K 条行业 KB 并按客户行业重新生成。约耗时 30s。"

Below the buttons: list of currently allocated accounts and groups (table with `account.id`, role, health, last_active; link to existing AccountDetail).

**Quota & features tab**
- Top section "配额上限"
  - Editable numbers for account_quota / group_quota / token_quota / seat_quota
  - On save: if any new ceiling < current used, show confirm dialog "当前已用 X > 新上限 Y，确定降配？" with yes/no
  - Otherwise save directly
- Bottom section "功能开关"
  - Table of all features from `/admin/features` with current enable/disable per customer
  - Switch toggles call PUT or DELETE on `customers/{cid}/features/{slug}`

**Usage & logs tab**
- Token consumption chart (last 30 days)
- AI call count by source
- Recent leads (last 50, link to existing CRM page filtered by customer_id)
- Read-only; no mutations

## 6. Data Flow

### 6.1 Create flow
```
operator fills form
   ↓
POST /admin/billing/quick-provision
   {email, password, name?, industry, plan, note}
   ↓ (backend synchronously creates customer + subscription + invoice + allocation + KB)
returns {customer_id, email, plan, ...}
   ↓
frontend: credentials modal
   ↓ (operator clicks "前往客户详情")
navigate to /customers/:id
   ↓
OverviewTab mounts → useQuery starts polling allocation state
   (refetchInterval=5000, stopAfter=6 attempts or stable)
```

### 6.2 Reallocate flow (example: accounts)
```
operator clicks button in AllocationTab
   ↓
Modal.confirm shows "将释放 N 个账号..." (N pulled from current cache)
   ↓ confirm
POST /admin/billing/customers/{id}/reallocate-accounts
   ↓
success: notification.success + queryClient.invalidateQueries(['customer', id])
                                + queryClient.invalidateQueries(['customer', id, 'accounts'])
failure: notification.error with status + endpoint
```

### 6.3 Quota down-adjust flow
```
operator edits ceiling, e.g. account_quota 5 → 2
   ↓ save
client compares new ceiling vs current used
   if new < used:
      Modal.confirm "当前已用 5 > 新上限 2, 确定降配?"
        → confirm → PUT
        → cancel → revert form
   else:
      PUT directly
```

## 7. Error Handling

Implemented once in `services/adminCustomers.ts`:

| Status | UX |
|---|---|
| Network error | `notification.error` with method + path |
| 400 / 422 | Parse `detail`; if validation, attach to form field; else global error toast |
| 401 / 403 | Should not happen (admin already authed); show "权限失效, 请重新登录" + redirect /login |
| 409 (email duplicate on create) | Inline form error: "邮箱已存在 [前往详情]" |
| 5xx | `notification.error` with `trace_id` if header present, else generic |
| Network timeout (>30s on quick-provision) | "操作可能仍在后台进行，请刷新列表查看" |

`quick-provision` is documented as idempotent on invoice/transaction keys, so retrying with the same inputs is safe.

## 8. Testing Strategy

### 8.1 Backend
**Zero new tests.** All consumed endpoints are covered by existing tests (Epic 2 / Epic 3 / Epic 4 test suites and `quick-provision` integration test if present).

If the plan discovers an endpoint with thin coverage, that's a finding to surface — not a license for this module to add tests for someone else's code.

### 8.2 Frontend (vitest + @testing-library/react)
Required:
- **NewCustomerPage**
  - submits valid form → calls quickProvision mutation → renders credentials modal with returned email + password
  - email blur with existing email → renders inline error with link
  - missing required field → form validation prevents submit
- **AllocationTab**
  - "重新分配账号" opens Modal.confirm; cancel does not call API; confirm calls API and invalidates queries
- **QuotaFeaturesTab**
  - lowering account_quota below current used triggers confirm modal; rejecting reverts the form

Optional (nice-to-have if quick):
- CustomerListPage filter + search wires to client-side filter
- OverviewTab polling stops after 6 attempts

### 8.3 e2e
Deferred. Not in scope for this module.

## 9. Security & Permissions

- All routes guard with existing admin auth context.
- The credentials modal does not log the password to console, does not write to any analytics, and is shown only in response to the successful POST. Refresh discards it.
- No password storage on the frontend at any point.
- Reallocation and KB regeneration are admin-only and already enforced at the endpoint level; no client-side bypass possible.

## 10. Open Questions (resolved during brainstorming)

| Question | Decision |
|---|---|
| Payment for admin-created customers | Manual activation only, marked `tx_hash='admin_manual'`. No USDT invoice link path in this module. |
| Sidebar placement | New top-level "客户运营" menu above existing items. |
| Can the customer still log into portal? | Yes. Admin sets initial password and shares it; customer can log in and change password. |
| Are there cases where the operator needs to see the password again later? | No. If lost, re-provision or build a reset flow separately. Out of scope here. |
| Pagination? | Client-side only for <1000 customers. Revisit when crossing threshold. |
| i18n? | Module is admin-internal; Chinese only matches the rest of admin SPA. |

## 11. Estimate

| Area | Est. |
|---|---|
| Service client + types | 1h |
| Sidebar entry + routing | 0.5h |
| CustomerListPage | 1.5h |
| NewCustomerPage + credentials modal | 2h |
| CustomerDetailPage shell + 5 tabs | 5h |
| Frontend tests | 1.5h |
| Polish (loading / empty / a11y / error toasts) | 1.5h |
| **Total** | **~1.5 working days** |

## 12. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| `quick-provision` payload shape may have drifted since memory snapshot | First plan task verifies actual Pydantic model in `admin_billing.py` and produces concrete TypeScript types |
| Single-customer GET endpoint may not exist (only list) | Plan task explicitly verifies; if missing, the simplest mitigation is using the list endpoint with `email=` or `id=` filter, or extending it |
| Operator reads-but-misses the "password shown once" warning | Modal uses prominent warning style + locks for at least 3s before close button is enabled |
| Admin polling on Overview tab leaks if user navigates away mid-poll | React Query auto-cancels on unmount; verified pattern from existing pages |
| Feature flag toggle disables a feature mid-use | Backend already handles this; frontend just respects the response |

## 13. Related Memories

- [[project-core-direction]] — TG group control + AI sales main thread
- [[project-business-model-aas]] — 3-tier subscription plans being provisioned
- [[project-epic1-multitenant-state]] — Customer model + admin JWT
- [[project-epic2-billing-state]] — Subscription/Invoice models the admin endpoints write to
- [[project-epic3-allocation-state]] — Allocation triggered by activation
- [[project-epic4-kb-state]] — KB generation triggered by activation
- [[project-epic15-portal-state]] — Customer-side portal that this module complements (not replaces)
- [[project-priority-polish-first]] — Operator-first onboarding is the polish play that lets us seed paying customers
