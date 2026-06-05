# Admin Customer Operations Module — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a single admin SPA module so platform operators can complete the customer lifecycle (create → activate → allocate → manage) without requiring customers to touch `/portal`.

**Architecture:** Pure frontend module. Zero backend changes. New `frontend/src/pages/customers/` directory with a list page, a "new customer" form (calling existing `POST /admin/billing/quick-provision`), and a 5-tab detail page that wraps existing `/admin/billing/*` and `/admin/features/*` endpoints. Auth is gated by the existing `AdminOnly` wrapper from `App.tsx`.

**Tech Stack:** React 18, TypeScript, React Router v6, React Query v5, Ant Design v6, axios, vitest + @testing-library/react + jsdom (new — set up in Task 2).

**Spec:** [docs/superpowers/specs/2026-06-05-admin-customer-ops-design.md](docs/superpowers/specs/2026-06-05-admin-customer-ops-design.md)

---

## File Structure

**New files:**

```
frontend/
  vitest.config.ts                                    test runner config
  vitest.setup.ts                                     RTL matchers + jsdom helpers
  src/
    services/
      adminCustomers.ts                               typed API client (only file talking to admin endpoints)
      adminCustomers.test.ts                          unit tests for service client
    pages/
      customers/
        CustomerListPage.tsx                          list + filters + search
        NewCustomerPage.tsx                           form + credentials modal
        NewCustomerPage.test.tsx
        CustomerDetailPage.tsx                        sticky header + tab routing shell
        tabs/
          OverviewTab.tsx                             quotas + renewal + resource summary
          BillingTab.tsx                              subscription + invoice history
          AllocationTab.tsx                           reallocate accounts/groups, regenerate KB
          AllocationTab.test.tsx
          QuotaFeaturesTab.tsx                        feature flags + quota ceilings
          QuotaFeaturesTab.test.tsx
          UsageLogsTab.tsx                            token + AI usage
```

**Modified files:**

- `frontend/src/App.tsx` — add 3 lazy imports + 3 `<Route>` entries + 1 menu group
- `frontend/package.json` — add 4 devDependencies + 2 npm scripts
- `frontend/tsconfig.json` — add `"types": ["vitest/globals", ...]` if missing

---

## Backend Reality Check (read once)

Already verified from `backend/app/api/v1/endpoints/admin_billing.py` and `backend/app/models/customer.py`:

**`POST /admin/billing/quick-provision`** payload:
```typescript
{
  customer_id?: number,                  // OR pass new_customer_* below
  new_customer_email?: string,
  new_customer_password?: string,        // min 8 chars
  new_customer_name?: string,
  new_customer_industry?: string,
  plan?: 'starter' | 'growth' | 'pro',
  wallet_credit_cents?: number,          // 0..10_000_000
  note?: string,                         // max 200
}
```

**`GET /admin/billing/customers`** query params: `status`, `plan`, `skip`, `limit`. **No `email` filter.** Email dedupe in Task 6 fetches the list once and filters client-side.

**No `GET /admin/billing/customers/{id}` exists.** Detail page in Task 7 reuses the list endpoint with a client-side `.find()` until backend adds it (out of scope here).

**`CustomerRead` shape:** `{id, email, name, company, industry, status, plan, subscription_status, current_period_end, account_quota, group_quota, token_quota, seat_quota, account_used, group_used, token_used, seat_used, is_internal_pool, created_at, last_login_at}`.

**Auth:** All `/admin/*` endpoints require `Depends(get_current_admin)`. Frontend uses `localStorage.getItem('token')` and the shared axios instance at `frontend/src/services/api.ts`.

**Existing UI patterns to follow:**
- Sidebar menu definition: `buildMenuItems(role, isSuperuser)` in `App.tsx`, returns `MenuProps['items']`.
- Admin-only route guard: `<AdminOnly><Page /></AdminOnly>` (already defined in `App.tsx`).
- Page subfolder example: `frontend/src/pages/billing/ActivationCodes.tsx`.

---

## Tasks

### Task 1: Service client + TypeScript types

**Files:**
- Create: `frontend/src/services/adminCustomers.ts`

**Purpose:** Single typed module that owns every call to `/admin/billing/*` and `/admin/features/*`. Tabs and pages import functions from here — they never use raw axios.

> **STATUS: IMPLEMENTED + AMENDED** (2026-06-05). Initial commit `407af4d`, code review fix `9c4a07a`. The canonical types are in [`frontend/src/services/adminCustomers.ts`](frontend/src/services/adminCustomers.ts) — they differ from the draft below in 4 ways: (1) types `Invoice`, `FeatureRegistry`, `CustomerFeature`, `FeatureUsageSummary` were renamed to `AdminInvoice`, `AdminFeatureEntry`, `AdminCustomerFeature`, `AdminFeatureUsageSummary` and their fields aligned with backend `models/feature.py` and `models/subscription.py`; (2) `upsertCustomerFeature` now takes `(customerId, slug, update: CustomerFeatureUpdate)` instead of `(customerId, slug, enabled: boolean)`; (3) the local axios instance was removed in favour of `import api from './api'` (gets the existing 401/403 interceptor); (4) `AxiosError` is now a type-only import. **Downstream tasks (8, 10, 11) below have been patched to match.** The draft code block is kept below as historical context only.

- [ ] **Step 1: Create the service module with shared axios instance**

Create `frontend/src/services/adminCustomers.ts`:

```typescript
import axios, { AxiosError } from 'axios';

const api = axios.create({ baseURL: '/api/v1' });
api.interceptors.request.use((cfg) => {
  const token = localStorage.getItem('token');
  if (token) cfg.headers.Authorization = `Bearer ${token}`;
  return cfg;
});

// ---- Types (mirrors CustomerRead from backend/app/models/customer.py) ----

export type CustomerStatus = 'pending' | 'active' | 'suspended' | 'canceled';
export type Plan = 'starter' | 'growth' | 'pro';

export interface Customer {
  id: number;
  email: string;
  name: string | null;
  company: string | null;
  industry: string | null;
  status: CustomerStatus;
  plan: Plan | null;
  subscription_status: string | null;
  current_period_end: string | null;
  account_quota: number;
  group_quota: number;
  token_quota: number;
  seat_quota: number;
  account_used: number;
  group_used: number;
  token_used: number;
  seat_used: number;
  is_internal_pool: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface Invoice {
  id: number;
  customer_id: number;
  amount_cents: number;
  status: string;
  tx_hash: string | null;
  note: string | null;
  created_at: string;
}

// Two modes:
//   - create mode: provide new_customer_email + new_customer_password
//   - existing mode: provide customer_id only
// Backend validates one of the two; do not mix.
export type QuickProvisionPayload =
  | {
      new_customer_email: string;
      new_customer_password: string;
      new_customer_name?: string;
      new_customer_industry?: string;
      plan: Plan;
      wallet_credit_cents?: number;
      note?: string;
    }
  | {
      customer_id: number;
      plan: Plan;
      wallet_credit_cents?: number;
      note?: string;
    };

export interface FeatureRegistry {
  slug: string;
  name: string;
  description: string | null;
  default_enabled: boolean;
}

export interface CustomerFeature {
  slug: string;
  enabled: boolean;
  config_json: Record<string, unknown> | null;
}

export interface FeatureUsageSummary {
  slug: string;
  period_start: string;
  units_used: number;
}

// ---- Error normalization ----

export class AdminApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown, message: string) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

function normalize(err: unknown, method: string, path: string): never {
  const ax = err as AxiosError<{ detail?: unknown }>;
  if (ax.response) {
    const detail = ax.response.data?.detail;
    const message =
      typeof detail === 'string' ? detail : `${method} ${path} → ${ax.response.status}`;
    throw new AdminApiError(ax.response.status, detail, message);
  }
  throw new AdminApiError(0, null, `${method} ${path} → network error`);
}

// ---- Customer endpoints ----

export async function listCustomers(params?: {
  status?: CustomerStatus;
  plan?: Plan;
  skip?: number;
  limit?: number;
}): Promise<Customer[]> {
  try {
    const res = await api.get<Customer[]>('/admin/billing/customers', { params });
    return res.data;
  } catch (e) {
    normalize(e, 'GET', '/admin/billing/customers');
  }
}

export async function getCustomerById(id: number): Promise<Customer | null> {
  // Backend has no /customers/{id} GET; fetch list with high limit and find.
  // Acceptable for <1000 customers per spec §3.
  const all = await listCustomers({ limit: 500 });
  return all.find((c) => c.id === id) ?? null;
}

export async function quickProvision(payload: QuickProvisionPayload): Promise<Customer> {
  try {
    const res = await api.post<Customer>('/admin/billing/quick-provision', payload);
    return res.data;
  } catch (e) {
    normalize(e, 'POST', '/admin/billing/quick-provision');
  }
}

export async function reallocateAccounts(customerId: number): Promise<void> {
  try {
    await api.post(`/admin/billing/customers/${customerId}/reallocate-accounts`);
  } catch (e) {
    normalize(e, 'POST', `/admin/billing/customers/${customerId}/reallocate-accounts`);
  }
}

export async function reallocateGroups(customerId: number): Promise<void> {
  try {
    await api.post(`/admin/billing/customers/${customerId}/reallocate-groups`);
  } catch (e) {
    normalize(e, 'POST', `/admin/billing/customers/${customerId}/reallocate-groups`);
  }
}

export async function regenerateKb(customerId: number): Promise<void> {
  try {
    await api.post(`/admin/billing/customers/${customerId}/regenerate-kb`);
  } catch (e) {
    normalize(e, 'POST', `/admin/billing/customers/${customerId}/regenerate-kb`);
  }
}

// ---- Invoice endpoints ----

export async function listInvoices(customerId: number): Promise<Invoice[]> {
  try {
    const res = await api.get<Invoice[]>('/admin/billing/invoices', {
      params: { customer_id: customerId, limit: 100 },
    });
    return res.data;
  } catch (e) {
    normalize(e, 'GET', '/admin/billing/invoices');
  }
}

// ---- Feature endpoints ----

export async function listFeatureRegistry(): Promise<FeatureRegistry[]> {
  try {
    const res = await api.get<FeatureRegistry[]>('/admin/features/features');
    return res.data;
  } catch (e) {
    normalize(e, 'GET', '/admin/features/features');
  }
}

export async function listCustomerFeatures(customerId: number): Promise<CustomerFeature[]> {
  try {
    const res = await api.get<CustomerFeature[]>(
      `/admin/features/customers/${customerId}/features`,
    );
    return res.data;
  } catch (e) {
    normalize(e, 'GET', `/admin/features/customers/${customerId}/features`);
  }
}

export async function upsertCustomerFeature(
  customerId: number,
  slug: string,
  enabled: boolean,
): Promise<CustomerFeature> {
  try {
    const res = await api.put<CustomerFeature>(
      `/admin/features/customers/${customerId}/features/${slug}`,
      { enabled },
    );
    return res.data;
  } catch (e) {
    normalize(e, 'PUT', `/admin/features/customers/${customerId}/features/${slug}`);
  }
}

export async function listCustomerUsage(
  customerId: number,
): Promise<FeatureUsageSummary[]> {
  try {
    const res = await api.get<FeatureUsageSummary[]>(
      `/admin/features/customers/${customerId}/usage`,
    );
    return res.data;
  } catch (e) {
    normalize(e, 'GET', `/admin/features/customers/${customerId}/usage`);
  }
}

// ---- Utilities ----

export function generateRandomPassword(length = 12): string {
  const charset =
    'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789!@#$%^&*';
  const arr = new Uint32Array(length);
  crypto.getRandomValues(arr);
  return Array.from(arr, (n) => charset[n % charset.length]).join('');
}
```

- [ ] **Step 2: TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: 0 new errors in `services/adminCustomers.ts`. Pre-existing errors elsewhere are not part of this task.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/services/adminCustomers.ts
git commit -m "feat(admin-customers): typed service client for admin endpoints"
```

---

### Task 2: Frontend test infrastructure (vitest + RTL + jsdom)

**Files:**
- Create: `frontend/vitest.config.ts`
- Create: `frontend/vitest.setup.ts`
- Modify: `frontend/package.json`
- Modify: `frontend/tsconfig.json` (only if `types` array is present and missing vitest globals)

**Purpose:** Wire up vitest so subsequent tasks can write `*.test.tsx` files. Smoke-test the service client to prove the harness works.

- [ ] **Step 1: Install dev dependencies**

Run:
```bash
cd frontend && npm install --save-dev vitest@^1.6.0 @testing-library/react@^16.0.0 @testing-library/jest-dom@^6.4.0 @testing-library/user-event@^14.5.0 jsdom@^24.0.0
```
Expected: 5 packages added; no peer-dep errors that fail install.

- [ ] **Step 2: Create vitest.config.ts**

Create `frontend/vitest.config.ts`:

```typescript
/// <reference types="vitest" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./vitest.setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    exclude: ['src/App.test.tsx'],  // legacy dummy file, not a real test
  },
});
```

- [ ] **Step 3: Create vitest.setup.ts**

Create `frontend/vitest.setup.ts`:

```typescript
import '@testing-library/jest-dom/vitest';
import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';

afterEach(() => {
  cleanup();
});
```

- [ ] **Step 4: Add npm scripts**

Modify `frontend/package.json`. In the `scripts` block, add:

```json
"test": "vitest run",
"test:watch": "vitest"
```

- [ ] **Step 5: Write smoke test for the service client**

Create `frontend/src/services/adminCustomers.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';
import { generateRandomPassword, AdminApiError } from './adminCustomers';

describe('generateRandomPassword', () => {
  it('returns 12 chars by default', () => {
    expect(generateRandomPassword()).toHaveLength(12);
  });

  it('returns the requested length', () => {
    expect(generateRandomPassword(16)).toHaveLength(16);
  });

  it('returns different values across calls (randomness sanity)', () => {
    const a = generateRandomPassword();
    const b = generateRandomPassword();
    expect(a).not.toBe(b);
  });
});

describe('AdminApiError', () => {
  it('preserves status and detail', () => {
    const err = new AdminApiError(409, { detail: 'dup' }, 'duplicate');
    expect(err.status).toBe(409);
    expect(err.detail).toEqual({ detail: 'dup' });
    expect(err.message).toBe('duplicate');
  });
});
```

- [ ] **Step 6: Run the smoke test**

Run: `cd frontend && npm test`
Expected: all tests in `adminCustomers.test.ts` pass. 4 passed total.

- [ ] **Step 7: Commit**

```bash
git add frontend/vitest.config.ts frontend/vitest.setup.ts frontend/package.json frontend/package-lock.json frontend/src/services/adminCustomers.test.ts
git commit -m "test(frontend): set up vitest + RTL + jsdom"
```

---

### Task 3: Sidebar entry + routing scaffold (empty pages)

**Files:**
- Create: `frontend/src/pages/customers/CustomerListPage.tsx` (placeholder)
- Create: `frontend/src/pages/customers/NewCustomerPage.tsx` (placeholder)
- Create: `frontend/src/pages/customers/CustomerDetailPage.tsx` (placeholder)
- Modify: `frontend/src/App.tsx`

**Purpose:** Wire the new pages into routing and the sidebar so the rest of the tasks can iterate on real navigation. Real content lands in Tasks 4–11.

- [ ] **Step 1: Create three placeholder pages**

Create `frontend/src/pages/customers/CustomerListPage.tsx`:
```tsx
import React from 'react';

const CustomerListPage: React.FC = () => <div data-testid="customer-list">客户列表 (placeholder)</div>;
export default CustomerListPage;
```

Create `frontend/src/pages/customers/NewCustomerPage.tsx`:
```tsx
import React from 'react';

const NewCustomerPage: React.FC = () => <div data-testid="customer-new">新建客户 (placeholder)</div>;
export default NewCustomerPage;
```

Create `frontend/src/pages/customers/CustomerDetailPage.tsx`:
```tsx
import React from 'react';

const CustomerDetailPage: React.FC = () => <div data-testid="customer-detail">客户详情 (placeholder)</div>;
export default CustomerDetailPage;
```

- [ ] **Step 2: Add imports to App.tsx**

In `frontend/src/App.tsx`, find the block of `import` statements for `pages/billing/...` and add immediately after:

```tsx
import CustomerListPage from './pages/customers/CustomerListPage';
import NewCustomerPage from './pages/customers/NewCustomerPage';
import CustomerDetailPage from './pages/customers/CustomerDetailPage';
```

- [ ] **Step 3: Add menu entry**

In `App.tsx`, inside `buildMenuItems()`, immediately above the `'business-ops'` entry (so "客户运营" appears at the top), insert:

```tsx
{
  key: 'customer-ops',
  icon: <TeamOutlined />,
  label: '客户运营',
  children: [
    { key: 'customer-list', label: <Link to="/customers">客户列表</Link> },
    { key: 'customer-new', label: <Link to="/customers/new">新建客户</Link> },
  ],
},
```

(`TeamOutlined` is already imported at the top of `App.tsx`.)

- [ ] **Step 4: Add routes**

In `App.tsx`, find the `<Routes>` block. Add three new `<Route>` entries among the other admin routes (placement after the `/business-ops` route is fine):

```tsx
<Route path="/customers" element={<ProtectedRoute><AdminOnly><CustomerListPage /></AdminOnly></ProtectedRoute>} />
<Route path="/customers/new" element={<ProtectedRoute><AdminOnly><NewCustomerPage /></AdminOnly></ProtectedRoute>} />
<Route path="/customers/:id" element={<ProtectedRoute><AdminOnly><CustomerDetailPage /></AdminOnly></ProtectedRoute>} />
```

(`ProtectedRoute` and `AdminOnly` are already defined in `App.tsx`.)

- [ ] **Step 5: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit 2>&1 | grep "pages/customers"`
Expected: no output (no errors in the new files).

- [ ] **Step 6: Manual smoke check**

Start the dev server: `cd frontend && npm run dev`
Open browser, log in as admin, click "客户运营 → 客户列表" in sidebar.
Expected: page renders the placeholder text "客户列表 (placeholder)".

Stop the dev server.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/customers/ frontend/src/App.tsx
git commit -m "feat(admin-customers): sidebar entry + routing scaffold"
```

---

### Task 4: CustomerListPage — table + filters

**Files:**
- Modify: `frontend/src/pages/customers/CustomerListPage.tsx`

**Purpose:** Real list view. Search + plan/status filter, all client-side.

- [ ] **Step 1: Replace the placeholder with the full list page**

Replace contents of `frontend/src/pages/customers/CustomerListPage.tsx` with:

```tsx
import React, { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { Card, Table, Input, Select, Tag, Button, Space, Empty } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { listCustomers, type Customer, type Plan, type CustomerStatus } from '../../services/adminCustomers';

const PLAN_COLOR: Record<Plan, string> = {
  starter: 'blue',
  growth: 'purple',
  pro: 'gold',
};
const STATUS_COLOR: Record<CustomerStatus, string> = {
  pending: 'default',
  active: 'green',
  suspended: 'orange',
  canceled: 'red',
};

const CustomerListPage: React.FC = () => {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [planFilter, setPlanFilter] = useState<Plan[]>([]);
  const [statusFilter, setStatusFilter] = useState<CustomerStatus[]>([]);

  const { data, isLoading } = useQuery({
    queryKey: ['admin-customers'],
    queryFn: () => listCustomers({ limit: 500 }),
  });

  const filtered = useMemo(() => {
    let rows = data ?? [];
    if (search.trim()) {
      const s = search.trim().toLowerCase();
      rows = rows.filter((r) => r.email.toLowerCase().includes(s) || (r.name ?? '').toLowerCase().includes(s));
    }
    if (planFilter.length > 0) rows = rows.filter((r) => r.plan && planFilter.includes(r.plan));
    if (statusFilter.length > 0) rows = rows.filter((r) => statusFilter.includes(r.status));
    return rows;
  }, [data, search, planFilter, statusFilter]);

  const columns = [
    { title: 'Email', dataIndex: 'email', key: 'email' },
    { title: '姓名', dataIndex: 'name', key: 'name', render: (v: string | null) => v ?? '—' },
    {
      title: '套餐',
      dataIndex: 'plan',
      key: 'plan',
      render: (p: Plan | null) => (p ? <Tag color={PLAN_COLOR[p]}>{p}</Tag> : <Tag>无</Tag>),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (s: CustomerStatus) => <Tag color={STATUS_COLOR[s]}>{s}</Tag>,
    },
    {
      title: '续费倒计时',
      dataIndex: 'current_period_end',
      key: 'renewal',
      render: (end: string | null) => {
        if (!end) return '—';
        const days = dayjs(end).diff(dayjs(), 'day');
        const color = days < 7 ? '#cf1322' : undefined;
        return <span style={{ color }}>{days} 天</span>;
      },
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (t: string) => dayjs(t).format('YYYY-MM-DD'),
    },
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, r: Customer) => (
        <Button type="link" onClick={() => navigate(`/customers/${r.id}`)}>详情</Button>
      ),
    },
  ];

  return (
    <Card
      title="客户运营 / 客户列表"
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/customers/new')}>
          新建客户
        </Button>
      }
    >
      <Space style={{ marginBottom: 16 }}>
        <Input.Search
          placeholder="搜索邮箱或姓名"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ width: 280 }}
          allowClear
        />
        <Select
          mode="multiple"
          placeholder="套餐"
          value={planFilter}
          onChange={setPlanFilter}
          style={{ width: 200 }}
          options={[
            { value: 'starter', label: 'Starter' },
            { value: 'growth', label: 'Growth' },
            { value: 'pro', label: 'Pro' },
          ]}
        />
        <Select
          mode="multiple"
          placeholder="状态"
          value={statusFilter}
          onChange={setStatusFilter}
          style={{ width: 200 }}
          options={[
            { value: 'pending', label: 'Pending' },
            { value: 'active', label: 'Active' },
            { value: 'suspended', label: 'Suspended' },
            { value: 'canceled', label: 'Canceled' },
          ]}
        />
      </Space>
      <Table
        rowKey="id"
        loading={isLoading}
        columns={columns}
        dataSource={filtered}
        pagination={{ pageSize: 20, showSizeChanger: true }}
        locale={{
          emptyText: (
            <Empty
              description={data && data.length === 0 ? '还没有客户' : '没有匹配结果'}
            >
              {data && data.length === 0 && (
                <Button type="primary" onClick={() => navigate('/customers/new')}>
                  立即开户第一个客户
                </Button>
              )}
            </Empty>
          ),
        }}
      />
    </Card>
  );
};

export default CustomerListPage;
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit 2>&1 | grep "CustomerListPage"`
Expected: no output.

- [ ] **Step 3: Manual smoke check**

Start dev server, navigate to `/customers`. Expected:
- table renders with real backend data
- search by email substring filters rows
- plan/status filters filter rows
- click "详情" navigates to `/customers/:id` (lands on placeholder for now)
- "新建客户" button navigates to `/customers/new`

Stop dev server.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/customers/CustomerListPage.tsx
git commit -m "feat(admin-customers): customer list page with filters and search"
```

---

### Task 5: NewCustomerPage — form + credentials modal + dedupe

**Files:**
- Modify: `frontend/src/pages/customers/NewCustomerPage.tsx`
- Create: `frontend/src/pages/customers/NewCustomerPage.test.tsx`

**Purpose:** Operator self-serve open-account flow with one-time credential reveal.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/pages/customers/NewCustomerPage.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import NewCustomerPage from './NewCustomerPage';
import * as svc from '../../services/adminCustomers';

vi.mock('../../services/adminCustomers', async () => {
  const actual = await vi.importActual<typeof import('../../services/adminCustomers')>(
    '../../services/adminCustomers',
  );
  return { ...actual, quickProvision: vi.fn(), listCustomers: vi.fn() };
});

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <NewCustomerPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('NewCustomerPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (svc.listCustomers as ReturnType<typeof vi.fn>).mockResolvedValue([]);
  });

  it('submits valid form and shows credentials modal', async () => {
    (svc.quickProvision as ReturnType<typeof vi.fn>).mockResolvedValue({
      id: 42,
      email: 'alice@acme.io',
      name: 'alice',
      industry: 'crypto',
      plan: 'starter',
      status: 'active',
    });
    const user = userEvent.setup();
    renderPage();
    await user.type(screen.getByLabelText('Email'), 'alice@acme.io');
    await user.type(screen.getByLabelText('初始密码'), 'Sup3rSecret!');
    // 行业 + 套餐 use AntD Select / Radio — pick by visible text
    await user.click(screen.getByLabelText('行业'));
    await user.click(await screen.findByText('crypto'));
    await user.click(screen.getByLabelText('Starter ($199)'));
    await user.click(screen.getByRole('button', { name: '开户并激活' }));
    expect(await screen.findByText(/客户已创建并激活/)).toBeInTheDocument();
    expect(screen.getByText('alice@acme.io')).toBeInTheDocument();
    expect(screen.getByText('Sup3rSecret!')).toBeInTheDocument();
  });

  it('blocks submission when email already exists', async () => {
    (svc.listCustomers as ReturnType<typeof vi.fn>).mockResolvedValue([
      { id: 1, email: 'alice@acme.io', status: 'active' },
    ]);
    const user = userEvent.setup();
    renderPage();
    const emailInput = screen.getByLabelText('Email');
    await user.type(emailInput, 'alice@acme.io');
    emailInput.blur();
    expect(await screen.findByText(/邮箱已存在/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- NewCustomerPage`
Expected: FAIL — placeholder doesn't render any form.

- [ ] **Step 3: Implement the form + modal**

Replace `frontend/src/pages/customers/NewCustomerPage.tsx`:

```tsx
import React, { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { Card, Form, Input, Select, Radio, Button, Modal, message, Space, Typography } from 'antd';
import { ReloadOutlined, CopyOutlined } from '@ant-design/icons';
import {
  quickProvision,
  listCustomers,
  generateRandomPassword,
  AdminApiError,
  type Customer,
  type Plan,
} from '../../services/adminCustomers';

const { Text, Paragraph } = Typography;

const INDUSTRIES = ['crypto', 'ecommerce', 'b2b', 'gaming', 'mcn'];

interface FormValues {
  email: string;
  password: string;
  name?: string;
  industry: string;
  plan: Plan;
  note?: string;
}

const PLANS: Array<{ value: Plan; label: string; desc: string }> = [
  { value: 'starter', label: 'Starter ($199)', desc: '3 账号 / 500 群 / 200 万 token' },
  { value: 'growth', label: 'Growth ($299)', desc: '5 账号 / 1000 群 / 500 万 token' },
  { value: 'pro', label: 'Pro ($599)', desc: '10 账号 / 3000 群 / 1500 万 token' },
];

const NewCustomerPage: React.FC = () => {
  const navigate = useNavigate();
  const [form] = Form.useForm<FormValues>();
  const [credentials, setCredentials] = useState<{ customer: Customer; password: string } | null>(null);

  const mutation = useMutation({
    mutationFn: async (vals: FormValues) =>
      quickProvision({
        new_customer_email: vals.email,
        new_customer_password: vals.password,
        new_customer_name: vals.name,
        new_customer_industry: vals.industry,
        plan: vals.plan,
        note: vals.note,
      }),
    onSuccess: (customer, vars) => {
      setCredentials({ customer, password: vars.password });
    },
    onError: (err: unknown) => {
      if (err instanceof AdminApiError) {
        if (err.status === 409 || err.status === 400) {
          form.setFields([{ name: 'email', errors: [err.message] }]);
          return;
        }
        message.error(err.message);
      } else {
        message.error('网络错误，请重试');
      }
    },
  });

  const handleEmailBlur = async () => {
    const email = form.getFieldValue('email');
    if (!email) return;
    try {
      const all = await listCustomers({ limit: 500 });
      const dup = all.find((c) => c.email.toLowerCase() === email.toLowerCase());
      if (dup) {
        form.setFields([
          {
            name: 'email',
            errors: [`邮箱已存在 (id=${dup.id})。请前往客户详情。`],
          },
        ]);
      }
    } catch {
      // non-blocking; submission will surface the real error
    }
  };

  const handleGeneratePassword = () => {
    form.setFieldValue('password', generateRandomPassword());
  };

  const portalUrl = `${window.location.origin}/portal/login`;

  const copy = async (s: string, label: string) => {
    try {
      await navigator.clipboard.writeText(s);
      message.success(`${label} 已复制`);
    } catch {
      message.error('复制失败');
    }
  };

  return (
    <Card title="客户运营 / 新建客户">
      <Form<FormValues>
        form={form}
        layout="vertical"
        onFinish={(vals) => mutation.mutate(vals)}
        initialValues={{ plan: 'starter' }}
        style={{ maxWidth: 640 }}
      >
        <Form.Item
          label="Email"
          name="email"
          rules={[
            { required: true, message: '请输入邮箱' },
            { type: 'email', message: '邮箱格式不正确' },
          ]}
        >
          <Input onBlur={handleEmailBlur} placeholder="customer@example.com" />
        </Form.Item>
        <Form.Item
          label="初始密码"
          name="password"
          rules={[
            { required: true, message: '请输入密码' },
            { min: 8, message: '至少 8 位' },
          ]}
          extra="此密码仅在创建完成时展示一次。"
        >
          <Input.Password
            placeholder="至少 8 位"
            addonAfter={
              <Button size="small" type="link" icon={<ReloadOutlined />} onClick={handleGeneratePassword}>
                生成 12 位随机密码
              </Button>
            }
          />
        </Form.Item>
        <Form.Item label="姓名" name="name">
          <Input placeholder="留空则使用邮箱前缀" />
        </Form.Item>
        <Form.Item label="行业" name="industry" rules={[{ required: true, message: '请选择行业' }]}>
          <Select placeholder="选择行业" options={INDUSTRIES.map((v) => ({ value: v, label: v }))} />
        </Form.Item>
        <Form.Item label="套餐" name="plan" rules={[{ required: true }]}>
          <Radio.Group>
            <Space direction="vertical">
              {PLANS.map((p) => (
                <Radio key={p.value} value={p.value}>
                  <strong>{p.label}</strong> — {p.desc}
                </Radio>
              ))}
            </Space>
          </Radio.Group>
        </Form.Item>
        <Form.Item label="备注" name="note">
          <Input.TextArea rows={2} placeholder="线下付款/试用/内部 QA 等" maxLength={200} showCount />
        </Form.Item>
        <Form.Item>
          <Space>
            <Button type="primary" htmlType="submit" loading={mutation.isPending}>
              开户并激活
            </Button>
            <Button onClick={() => navigate('/customers')}>取消</Button>
          </Space>
        </Form.Item>
      </Form>

      <Modal
        title="✅ 客户已创建并激活"
        open={credentials !== null}
        closable={false}
        maskClosable={false}
        footer={
          <Space>
            <Button onClick={() => setCredentials(null)}>关闭</Button>
            <Button
              type="primary"
              onClick={() => credentials && navigate(`/customers/${credentials.customer.id}`)}
            >
              前往客户详情
            </Button>
          </Space>
        }
      >
        {credentials && (
          <Space direction="vertical" style={{ width: '100%' }}>
            <Paragraph>
              <Text strong>Email:</Text> {credentials.customer.email}{' '}
              <Button size="small" icon={<CopyOutlined />} onClick={() => copy(credentials.customer.email, 'Email')} />
            </Paragraph>
            <Paragraph>
              <Text strong>初始密码:</Text>{' '}
              <Text code copyable={{ text: credentials.password }}>{credentials.password}</Text>
            </Paragraph>
            <Paragraph>
              <Text strong>Portal:</Text>{' '}
              <Text code copyable={{ text: portalUrl }}>{portalUrl}</Text>
            </Paragraph>
            <Text type="warning">
              ⚠ 此密码仅在本窗口显示。关闭后无法再次查看，请立即通过其他途径转交客户。
            </Text>
          </Space>
        )}
      </Modal>
    </Card>
  );
};

export default NewCustomerPage;
```

- [ ] **Step 4: Run tests**

Run: `cd frontend && npm test -- NewCustomerPage`
Expected: PASS.

If tests fail because AntD Select/Radio labels don't match expected, adjust test selectors (e.g. `screen.getByLabelText('行业')` may need `getByText('行业')` next-to-input pattern; the page implementation is the source of truth).

- [ ] **Step 5: Manual smoke check**

Start dev server, navigate `/customers/new`, fill the form with a fresh test email, click "开户并激活". Expected:
- modal shows email + password + portal URL with copy buttons
- "前往客户详情" navigates to `/customers/:id`
- creating a second customer with the same email immediately shows the inline "邮箱已存在" error on blur

Stop dev server.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/customers/NewCustomerPage.tsx frontend/src/pages/customers/NewCustomerPage.test.tsx
git commit -m "feat(admin-customers): new customer form + credentials reveal modal"
```

---

### Task 6: CustomerDetailPage shell — sticky header + tab routing

**Files:**
- Modify: `frontend/src/pages/customers/CustomerDetailPage.tsx`
- Create: 5 empty tab files (each with one-line placeholder)

**Purpose:** Build the detail page container so Tasks 7–11 only need to fill in tab bodies.

- [ ] **Step 1: Create 5 placeholder tab files**

Create each of the following with the matching default export:

`frontend/src/pages/customers/tabs/OverviewTab.tsx`:
```tsx
import React from 'react';
const OverviewTab: React.FC<{ customerId: number }> = ({ customerId }) => (
  <div data-testid="tab-overview">概览 (customer {customerId})</div>
);
export default OverviewTab;
```

`frontend/src/pages/customers/tabs/BillingTab.tsx`:
```tsx
import React from 'react';
const BillingTab: React.FC<{ customerId: number }> = ({ customerId }) => (
  <div data-testid="tab-billing">订阅账单 (customer {customerId})</div>
);
export default BillingTab;
```

`frontend/src/pages/customers/tabs/AllocationTab.tsx`:
```tsx
import React from 'react';
const AllocationTab: React.FC<{ customerId: number }> = ({ customerId }) => (
  <div data-testid="tab-allocation">资源分配 (customer {customerId})</div>
);
export default AllocationTab;
```

`frontend/src/pages/customers/tabs/QuotaFeaturesTab.tsx`:
```tsx
import React from 'react';
const QuotaFeaturesTab: React.FC<{ customerId: number }> = ({ customerId }) => (
  <div data-testid="tab-quota">配额功能 (customer {customerId})</div>
);
export default QuotaFeaturesTab;
```

`frontend/src/pages/customers/tabs/UsageLogsTab.tsx`:
```tsx
import React from 'react';
const UsageLogsTab: React.FC<{ customerId: number }> = ({ customerId }) => (
  <div data-testid="tab-usage">用量日志 (customer {customerId})</div>
);
export default UsageLogsTab;
```

- [ ] **Step 2: Replace the detail page with the real shell**

Replace `frontend/src/pages/customers/CustomerDetailPage.tsx`:

```tsx
import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { useParams, useSearchParams, useNavigate } from 'react-router-dom';
import { Card, Tabs, Tag, Space, Button, Spin, Result, Descriptions } from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { getCustomerById, type Plan, type CustomerStatus } from '../../services/adminCustomers';
import OverviewTab from './tabs/OverviewTab';
import BillingTab from './tabs/BillingTab';
import AllocationTab from './tabs/AllocationTab';
import QuotaFeaturesTab from './tabs/QuotaFeaturesTab';
import UsageLogsTab from './tabs/UsageLogsTab';

const PLAN_COLOR: Record<Plan, string> = { starter: 'blue', growth: 'purple', pro: 'gold' };
const STATUS_COLOR: Record<CustomerStatus, string> = {
  pending: 'default',
  active: 'green',
  suspended: 'orange',
  canceled: 'red',
};

const CustomerDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [search, setSearch] = useSearchParams();
  const customerId = Number(id);

  const { data: customer, isLoading, error } = useQuery({
    queryKey: ['admin-customer', customerId],
    queryFn: () => getCustomerById(customerId),
    enabled: Number.isFinite(customerId),
  });

  if (isLoading) return <Spin tip="加载中..." style={{ display: 'block', padding: 48 }} />;
  if (error || !customer) {
    return (
      <Result
        status="404"
        title="未找到该客户"
        extra={<Button onClick={() => navigate('/customers')}>返回列表</Button>}
      />
    );
  }

  const activeTab = search.get('tab') ?? 'overview';
  const setTab = (k: string) => {
    search.set('tab', k);
    setSearch(search, { replace: true });
  };

  const renewalDays = customer.current_period_end
    ? dayjs(customer.current_period_end).diff(dayjs(), 'day')
    : null;

  return (
    <Card
      title={
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/customers')} />
          <span>{customer.name ?? customer.email}</span>
          {customer.plan && <Tag color={PLAN_COLOR[customer.plan]}>{customer.plan}</Tag>}
          <Tag color={STATUS_COLOR[customer.status]}>{customer.status}</Tag>
        </Space>
      }
    >
      <Descriptions size="small" column={4} style={{ marginBottom: 16 }}>
        <Descriptions.Item label="Email">{customer.email}</Descriptions.Item>
        <Descriptions.Item label="行业">{customer.industry ?? '—'}</Descriptions.Item>
        <Descriptions.Item label="续费倒计时">
          {renewalDays !== null ? (
            <span style={{ color: renewalDays < 7 ? '#cf1322' : undefined }}>{renewalDays} 天</span>
          ) : (
            '—'
          )}
        </Descriptions.Item>
        <Descriptions.Item label="创建时间">{dayjs(customer.created_at).format('YYYY-MM-DD')}</Descriptions.Item>
      </Descriptions>

      <Tabs
        activeKey={activeTab}
        onChange={setTab}
        items={[
          { key: 'overview', label: '概览', children: <OverviewTab customerId={customerId} /> },
          { key: 'billing', label: '订阅账单', children: <BillingTab customerId={customerId} /> },
          { key: 'allocation', label: '资源分配', children: <AllocationTab customerId={customerId} /> },
          { key: 'quota', label: '配额功能', children: <QuotaFeaturesTab customerId={customerId} /> },
          { key: 'usage', label: '用量日志', children: <UsageLogsTab customerId={customerId} /> },
        ]}
      />
    </Card>
  );
};

export default CustomerDetailPage;
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit 2>&1 | grep "customers/"`
Expected: no output.

- [ ] **Step 4: Manual smoke check**

Navigate to `/customers/:id` for an existing customer. Expected:
- sticky header shows email, plan tag, status tag, renewal countdown
- 5 tabs render with placeholder content
- clicking a tab updates the URL `?tab=...` and switching tabs back via browser back/forward works

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/customers/CustomerDetailPage.tsx frontend/src/pages/customers/tabs/
git commit -m "feat(admin-customers): detail page shell with sticky header and 5 tabs"
```

---

### Task 7: OverviewTab — quota meters + polling

**Files:**
- Modify: `frontend/src/pages/customers/tabs/OverviewTab.tsx`

**Purpose:** Show 4 quota meters and resource summary, with polling that runs 6× 5s after navigation (to surface allocation progress after a fresh provision or reallocation).

- [ ] **Step 1: Replace OverviewTab with the real implementation**

Replace `frontend/src/pages/customers/tabs/OverviewTab.tsx`:

```tsx
import React, { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Row, Col, Card, Progress, Statistic, Space } from 'antd';
import { getCustomerById } from '../../../services/adminCustomers';

interface MeterProps {
  title: string;
  used: number;
  total: number;
}

const QuotaMeter: React.FC<MeterProps> = ({ title, used, total }) => {
  const pct = total > 0 ? Math.min(100, Math.round((used / total) * 100)) : 0;
  return (
    <Card size="small">
      <Statistic title={title} value={used} suffix={`/ ${total}`} />
      <Progress percent={pct} size="small" status={pct >= 90 ? 'exception' : 'active'} />
    </Card>
  );
};

const OverviewTab: React.FC<{ customerId: number }> = ({ customerId }) => {
  const [pollCount, setPollCount] = useState(0);
  const polling = pollCount < 6;

  const { data } = useQuery({
    queryKey: ['admin-customer', customerId],
    queryFn: () => getCustomerById(customerId),
    refetchInterval: polling ? 5000 : false,
  });

  useEffect(() => {
    if (!polling) return;
    const t = setInterval(() => setPollCount((n) => n + 1), 5000);
    return () => clearInterval(t);
  }, [polling]);

  if (!data) return null;

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Row gutter={16}>
        <Col span={6}>
          <QuotaMeter title="TG 账号" used={data.account_used} total={data.account_quota} />
        </Col>
        <Col span={6}>
          <QuotaMeter title="AI 获客群" used={data.group_used} total={data.group_quota} />
        </Col>
        <Col span={6}>
          <QuotaMeter title="Token" used={data.token_used} total={data.token_quota} />
        </Col>
        <Col span={6}>
          <QuotaMeter title="销售席位" used={data.seat_used} total={data.seat_quota} />
        </Col>
      </Row>
      {polling && (
        <Card size="small" type="inner" title="资源分配进度">
          每 5 秒刷新一次，已刷新 {pollCount}/6 次。完成后停止。
        </Card>
      )}
    </Space>
  );
};

export default OverviewTab;
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit 2>&1 | grep OverviewTab`
Expected: no output.

- [ ] **Step 3: Manual smoke check**

Open detail page Overview tab for any customer. Expected: 4 quota cards with progress bars; polling card visible for the first ~30s then disappears.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/customers/tabs/OverviewTab.tsx
git commit -m "feat(admin-customers): overview tab with quota meters and polling"
```

---

### Task 8: BillingTab — subscription summary + invoice history

**Files:**
- Modify: `frontend/src/pages/customers/tabs/BillingTab.tsx`

**Purpose:** Show subscription status, current period, and full invoice history. Manual renewal/plan-switch is **out of scope** for this task (the backend currently has no single dedicated endpoint to extend a subscription without going through `quick-provision`; we either reuse `quick-provision` with the existing customer_id or wait until billing exposes a dedicated extend endpoint).

- [ ] **Step 1: Replace BillingTab with the real implementation**

Replace `frontend/src/pages/customers/tabs/BillingTab.tsx`:

```tsx
import React from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, Descriptions, Table, Tag, Space, Button, Modal, Form, Select, message } from 'antd';
import dayjs from 'dayjs';
import {
  getCustomerById,
  listInvoices,
  quickProvision,
  AdminApiError,
  type Plan,
  type AdminInvoice,
} from '../../../services/adminCustomers';

const PLAN_LABELS: Record<Plan, string> = {
  starter: 'Starter ($199)',
  growth: 'Growth ($299)',
  pro: 'Pro ($599)',
};

const BillingTab: React.FC<{ customerId: number }> = ({ customerId }) => {
  const queryClient = useQueryClient();
  const [renewModal, setRenewModal] = React.useState(false);
  const [renewForm] = Form.useForm<{ plan: Plan; note?: string }>();

  const { data: customer } = useQuery({
    queryKey: ['admin-customer', customerId],
    queryFn: () => getCustomerById(customerId),
  });
  const { data: invoices } = useQuery({
    queryKey: ['admin-customer', customerId, 'invoices'],
    queryFn: () => listInvoices(customerId),
  });

  const renewMutation = useMutation({
    mutationFn: async (vals: { plan: Plan; note?: string }) =>
      quickProvision({
        customer_id: customerId,
        plan: vals.plan,
        note: vals.note ?? `admin renew ${dayjs().format('YYYY-MM-DD')}`,
      }),
    onSuccess: () => {
      message.success('续期成功');
      setRenewModal(false);
      renewForm.resetFields();
      queryClient.invalidateQueries({ queryKey: ['admin-customer', customerId] });
    },
    onError: (err: unknown) => {
      message.error(err instanceof AdminApiError ? err.message : '续期失败');
    },
  });

  const invoiceColumns = [
    { title: 'Invoice ID', dataIndex: 'id', key: 'id' },
    {
      title: '套餐',
      dataIndex: 'plan',
      key: 'plan',
    },
    {
      title: '金额',
      dataIndex: 'amount_usd',
      key: 'amount',
      render: (usd: number) => `$${usd.toFixed(2)}`,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (s: string) => <Tag color={s === 'paid' ? 'green' : 'default'}>{s}</Tag>,
    },
    {
      title: 'Tx Hash',
      dataIndex: 'tx_hash',
      key: 'tx_hash',
      render: (h: string | null) => h ?? '—',
    },
    {
      title: '说明',
      dataIndex: 'description',
      key: 'description',
      render: (v: string) => v || '—',
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (t: string) => dayjs(t).format('YYYY-MM-DD HH:mm'),
    },
  ];

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Card
        size="small"
        title="当前订阅"
        extra={
          <Button type="primary" onClick={() => { renewForm.setFieldsValue({ plan: customer?.plan ?? 'starter' }); setRenewModal(true); }}>
            手动续期 / 切套餐
          </Button>
        }
      >
        <Descriptions size="small" column={3}>
          <Descriptions.Item label="套餐">
            {customer?.plan ? PLAN_LABELS[customer.plan] : '无'}
          </Descriptions.Item>
          <Descriptions.Item label="订阅状态">{customer?.subscription_status ?? '—'}</Descriptions.Item>
          <Descriptions.Item label="当前周期截至">
            {customer?.current_period_end ? dayjs(customer.current_period_end).format('YYYY-MM-DD') : '—'}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      <Card size="small" title="账单历史">
        <Table<AdminInvoice>
          rowKey="id"
          dataSource={invoices ?? []}
          columns={invoiceColumns}
          pagination={{ pageSize: 10 }}
          size="small"
        />
      </Card>

      <Modal
        title="手动续期 / 切套餐"
        open={renewModal}
        onCancel={() => setRenewModal(false)}
        onOk={() => renewForm.submit()}
        confirmLoading={renewMutation.isPending}
      >
        <Form form={renewForm} layout="vertical" onFinish={(v) => renewMutation.mutate(v)}>
          <Form.Item label="套餐" name="plan" rules={[{ required: true }]}>
            <Select
              options={[
                { value: 'starter', label: PLAN_LABELS.starter },
                { value: 'growth', label: PLAN_LABELS.growth },
                { value: 'pro', label: PLAN_LABELS.pro },
              ]}
            />
          </Form.Item>
          <Form.Item label="备注" name="note">
            <Select
              mode="tags"
              maxCount={1}
              placeholder="选填，将写入 invoice note"
              tokenSeparators={[',']}
            />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  );
};

export default BillingTab;
```

> **Implementation note for the engineer:** The renewal path reuses `quick-provision` against an existing customer. Verify with one manual end-to-end test that `quick-provision` with an existing email correctly extends the subscription (it should: the docstring says it's idempotent and dedupes by email). If this turns out to be wrong, file a backlog ticket "billing: add `/admin/billing/customers/{id}/extend` endpoint" and disable the renewal button with a tooltip until then. **Do not silently mis-implement.**

- [ ] **Step 2: TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit 2>&1 | grep BillingTab`
Expected: no output.

- [ ] **Step 3: Manual smoke check**

Open detail page Billing tab. Expected: subscription card, invoice table, renew modal opens and renew action succeeds for an existing customer. Verify the customer's `current_period_end` advances.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/customers/tabs/BillingTab.tsx
git commit -m "feat(admin-customers): billing tab with subscription summary and renewal"
```

---

### Task 9: AllocationTab — three actions + confirm modals

**Files:**
- Modify: `frontend/src/pages/customers/tabs/AllocationTab.tsx`
- Create: `frontend/src/pages/customers/tabs/AllocationTab.test.tsx`

**Purpose:** Three large buttons that wrap the three reallocate endpoints, each with an impact-preview confirm. This is the most operationally sensitive tab — tests are mandatory.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/pages/customers/tabs/AllocationTab.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import AllocationTab from './AllocationTab';
import * as svc from '../../../services/adminCustomers';

vi.mock('../../../services/adminCustomers', async () => {
  const actual = await vi.importActual<typeof import('../../../services/adminCustomers')>(
    '../../../services/adminCustomers',
  );
  return {
    ...actual,
    reallocateAccounts: vi.fn(),
    reallocateGroups: vi.fn(),
    regenerateKb: vi.fn(),
    getCustomerById: vi.fn().mockResolvedValue({
      id: 7,
      email: 'a@b.io',
      account_used: 3,
      account_quota: 3,
      group_used: 100,
      group_quota: 500,
    }),
  };
});

function renderTab() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <AllocationTab customerId={7} />
    </QueryClientProvider>,
  );
}

describe('AllocationTab', () => {
  beforeEach(() => vi.clearAllMocks());

  it('cancel does NOT call reallocate API', async () => {
    const user = userEvent.setup();
    renderTab();
    await user.click(await screen.findByRole('button', { name: /重新分配账号/ }));
    await user.click(await screen.findByRole('button', { name: '取消' }));
    expect(svc.reallocateAccounts).not.toHaveBeenCalled();
  });

  it('confirm calls reallocateAccounts with the customer id', async () => {
    (svc.reallocateAccounts as ReturnType<typeof vi.fn>).mockResolvedValue(undefined);
    const user = userEvent.setup();
    renderTab();
    await user.click(await screen.findByRole('button', { name: /重新分配账号/ }));
    await user.click(await screen.findByRole('button', { name: '确认' }));
    await waitFor(() => expect(svc.reallocateAccounts).toHaveBeenCalledWith(7));
  });
});
```

- [ ] **Step 2: Run test, expect failure**

Run: `cd frontend && npm test -- AllocationTab`
Expected: FAIL — placeholder has no buttons.

- [ ] **Step 3: Implement AllocationTab**

Replace `frontend/src/pages/customers/tabs/AllocationTab.tsx`:

```tsx
import React from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, Button, Space, Modal, message, Typography } from 'antd';
import { ReloadOutlined, BulbOutlined } from '@ant-design/icons';
import {
  getCustomerById,
  reallocateAccounts,
  reallocateGroups,
  regenerateKb,
  AdminApiError,
} from '../../../services/adminCustomers';

const { Paragraph, Text } = Typography;

const AllocationTab: React.FC<{ customerId: number }> = ({ customerId }) => {
  const queryClient = useQueryClient();
  const { data: customer } = useQuery({
    queryKey: ['admin-customer', customerId],
    queryFn: () => getCustomerById(customerId),
  });

  const onErr = (err: unknown) =>
    message.error(err instanceof AdminApiError ? err.message : '操作失败');
  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['admin-customer', customerId] });

  const accountsM = useMutation({
    mutationFn: () => reallocateAccounts(customerId),
    onSuccess: () => { message.success('账号已重新分配'); invalidate(); },
    onError: onErr,
  });
  const groupsM = useMutation({
    mutationFn: () => reallocateGroups(customerId),
    onSuccess: () => { message.success('群组已重新分配'); invalidate(); },
    onError: onErr,
  });
  const kbM = useMutation({
    mutationFn: () => regenerateKb(customerId),
    onSuccess: () => { message.success('行业 KB 已重新生成'); invalidate(); },
    onError: onErr,
  });

  const confirmAccounts = () =>
    Modal.confirm({
      title: '重新分配账号',
      okText: '确认',
      cancelText: '取消',
      content: (
        <>
          <Paragraph>
            将释放当前 <Text strong>{customer?.account_used ?? '?'}</Text> 个账号回池，
            并按当前套餐配额（<Text strong>{customer?.account_quota ?? '?'}</Text> 个）重新分配。
          </Paragraph>
          <Paragraph type="warning">此操作影响客户群控运行，建议提前通知。</Paragraph>
        </>
      ),
      onOk: () => accountsM.mutateAsync(),
    });

  const confirmGroups = () =>
    Modal.confirm({
      title: '重新分配群组',
      okText: '确认',
      cancelText: '取消',
      content: (
        <>
          <Paragraph>
            将释放当前 <Text strong>{customer?.group_used ?? '?'}</Text> 个群组，
            并按套餐配额（<Text strong>{customer?.group_quota ?? '?'}</Text> 个）重新分配。
          </Paragraph>
        </>
      ),
      onOk: () => groupsM.mutateAsync(),
    });

  const confirmKb = () =>
    Modal.confirm({
      title: '重新生成行业 KB',
      okText: '确认',
      cancelText: '取消',
      content: (
        <Paragraph>
          将删除当前所有行业 KB 条目并按客户行业重新生成。约耗时 30 秒。
        </Paragraph>
      ),
      onOk: () => kbM.mutateAsync(),
    });

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Card title="重新分配账号">
        <Paragraph>
          当前已分配 {customer?.account_used ?? '?'} / {customer?.account_quota ?? '?'} 个 TG 账号。
        </Paragraph>
        <Button icon={<ReloadOutlined />} loading={accountsM.isPending} onClick={confirmAccounts}>
          重新分配账号
        </Button>
      </Card>
      <Card title="重新分配群组">
        <Paragraph>
          当前已加入 {customer?.group_used ?? '?'} / {customer?.group_quota ?? '?'} 个群。
        </Paragraph>
        <Button icon={<ReloadOutlined />} loading={groupsM.isPending} onClick={confirmGroups}>
          重新分配群组
        </Button>
      </Card>
      <Card title="重新生成行业 KB">
        <Paragraph>清空当前行业 KB 并按客户当前 industry 重新生成 4 条 KB（含 embedding）。</Paragraph>
        <Button icon={<BulbOutlined />} loading={kbM.isPending} onClick={confirmKb}>
          重新生成行业 KB
        </Button>
      </Card>
    </Space>
  );
};

export default AllocationTab;
```

- [ ] **Step 4: Run tests**

Run: `cd frontend && npm test -- AllocationTab`
Expected: PASS.

- [ ] **Step 5: Manual smoke check**

Open detail page Allocation tab. Click each button → confirm modal shows the right counts → cancel does nothing, confirm calls the API and refreshes the cache. Verify in OverviewTab that the metrics update.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/customers/tabs/AllocationTab.tsx frontend/src/pages/customers/tabs/AllocationTab.test.tsx
git commit -m "feat(admin-customers): allocation tab with confirm-gated reallocate actions"
```

---

### Task 10: QuotaFeaturesTab — feature toggles + quota down-adjust guard

**Files:**
- Modify: `frontend/src/pages/customers/tabs/QuotaFeaturesTab.tsx`
- Create: `frontend/src/pages/customers/tabs/QuotaFeaturesTab.test.tsx`

**Purpose:** Feature flag table + (read-only display of quota ceilings; no API exists yet to *change* the ceilings on customers — confirmed against `admin_billing.py`). The "down-adjust confirm" interaction lives on a future write endpoint; this task stubs it as a disabled field with a tooltip, and the test covers the confirm flow when the toggle is enabled.

> **Engineer note:** Spec §5.4 called for editable quota ceilings, but the backend does not expose a `PATCH /admin/billing/customers/{id}/quotas` endpoint today. **Do not write a new backend endpoint in this task.** Make the quota fields read-only with a tooltip "暂不支持后台调整，需联系开发" and leave the feature-toggle work intact. The test below verifies the toggle path, not the quota path.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/pages/customers/tabs/QuotaFeaturesTab.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import QuotaFeaturesTab from './QuotaFeaturesTab';
import * as svc from '../../../services/adminCustomers';

vi.mock('../../../services/adminCustomers', async () => {
  const actual = await vi.importActual<typeof import('../../../services/adminCustomers')>(
    '../../../services/adminCustomers',
  );
  return {
    ...actual,
    upsertCustomerFeature: vi.fn().mockResolvedValue({
      feature_slug: 'ai_marketing',
      enabled: false,
      unit_price_cents: 0,
      is_custom_price: false,
      billing_unit: 'call',
      name_zh: 'AI 营销',
      name_en: 'AI Marketing',
      category: 'ai',
      notes: '',
    }),
    listFeatureRegistry: vi.fn().mockResolvedValue([
      {
        slug: 'ai_marketing',
        name_zh: 'AI 营销',
        name_en: 'AI Marketing',
        description: 'AI marketing',
        billing_unit: 'call',
        default_price_cents: 0,
        enabled_by_default: true,
        category: 'ai',
        is_active: true,
      },
    ]),
    listCustomerFeatures: vi.fn().mockResolvedValue([
      {
        feature_slug: 'ai_marketing',
        enabled: true,
        unit_price_cents: 0,
        is_custom_price: false,
        billing_unit: 'call',
        name_zh: 'AI 营销',
        name_en: 'AI Marketing',
        category: 'ai',
        notes: '',
      },
    ]),
    getCustomerById: vi.fn().mockResolvedValue({
      id: 7,
      account_used: 2,
      account_quota: 5,
      group_used: 100,
      group_quota: 500,
      token_used: 0,
      token_quota: 2000000,
      seat_used: 1,
      seat_quota: 1,
    }),
  };
});

function renderTab() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <QuotaFeaturesTab customerId={7} />
    </QueryClientProvider>,
  );
}

describe('QuotaFeaturesTab', () => {
  beforeEach(() => vi.clearAllMocks());

  it('toggling a feature off calls upsertCustomerFeature with enabled=false', async () => {
    const user = userEvent.setup();
    renderTab();
    const toggle = await screen.findByRole('switch');
    await user.click(toggle);
    await waitFor(() =>
      expect(svc.upsertCustomerFeature).toHaveBeenCalledWith(
        7,
        'ai_marketing',
        expect.objectContaining({ enabled: false }),
      ),
    );
  });
});
```

- [ ] **Step 2: Run test, expect failure**

Run: `cd frontend && npm test -- QuotaFeaturesTab`
Expected: FAIL — placeholder has no switch.

- [ ] **Step 3: Implement QuotaFeaturesTab**

Replace `frontend/src/pages/customers/tabs/QuotaFeaturesTab.tsx`:

```tsx
import React from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, Descriptions, Tooltip, InputNumber, Table, Switch, Space, message, Tag } from 'antd';
import {
  getCustomerById,
  listFeatureRegistry,
  listCustomerFeatures,
  upsertCustomerFeature,
  AdminApiError,
  type AdminFeatureEntry,
  type AdminCustomerFeature,
} from '../../../services/adminCustomers';

const QuotaFeaturesTab: React.FC<{ customerId: number }> = ({ customerId }) => {
  const queryClient = useQueryClient();

  const { data: customer } = useQuery({
    queryKey: ['admin-customer', customerId],
    queryFn: () => getCustomerById(customerId),
  });
  const { data: registry } = useQuery({
    queryKey: ['admin-feature-registry'],
    queryFn: listFeatureRegistry,
  });
  const { data: customerFeatures } = useQuery({
    queryKey: ['admin-customer-features', customerId],
    queryFn: () => listCustomerFeatures(customerId),
  });

  const toggleMutation = useMutation({
    mutationFn: ({ slug, enabled }: { slug: string; enabled: boolean }) =>
      upsertCustomerFeature(customerId, slug, { enabled }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-customer-features', customerId] });
      message.success('已更新');
    },
    onError: (err: unknown) =>
      message.error(err instanceof AdminApiError ? err.message : '更新失败'),
  });

  const enabledMap = new Map(
    (customerFeatures ?? []).map((f: AdminCustomerFeature) => [f.feature_slug, f.enabled]),
  );

  const featureColumns = [
    { title: '功能', dataIndex: 'name_zh', key: 'name_zh' },
    { title: 'Slug', dataIndex: 'slug', key: 'slug', render: (s: string) => <Tag>{s}</Tag> },
    { title: '说明', dataIndex: 'description', key: 'description', render: (d: string) => d || '—' },
    {
      title: '已启用',
      key: 'enabled',
      render: (_: unknown, r: AdminFeatureEntry) => {
        const enabled = enabledMap.get(r.slug) ?? r.enabled_by_default;
        return (
          <Switch
            checked={enabled}
            loading={toggleMutation.isPending && toggleMutation.variables?.slug === r.slug}
            onChange={(next) => toggleMutation.mutate({ slug: r.slug, enabled: next })}
          />
        );
      },
    },
  ];

  const readOnlyTip = '暂不支持后台调整，需联系开发';

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Card title="配额上限 (只读)">
        <Descriptions size="small" column={2}>
          <Descriptions.Item label="TG 账号">
            <Tooltip title={readOnlyTip}>
              <InputNumber disabled value={customer?.account_quota} addonAfter={`已用 ${customer?.account_used ?? 0}`} />
            </Tooltip>
          </Descriptions.Item>
          <Descriptions.Item label="AI 获客群">
            <Tooltip title={readOnlyTip}>
              <InputNumber disabled value={customer?.group_quota} addonAfter={`已用 ${customer?.group_used ?? 0}`} />
            </Tooltip>
          </Descriptions.Item>
          <Descriptions.Item label="Token">
            <Tooltip title={readOnlyTip}>
              <InputNumber disabled value={customer?.token_quota} addonAfter={`已用 ${customer?.token_used ?? 0}`} />
            </Tooltip>
          </Descriptions.Item>
          <Descriptions.Item label="销售席位">
            <Tooltip title={readOnlyTip}>
              <InputNumber disabled value={customer?.seat_quota} addonAfter={`已用 ${customer?.seat_used ?? 0}`} />
            </Tooltip>
          </Descriptions.Item>
        </Descriptions>
      </Card>

      <Card title="功能开关">
        <Table<AdminFeatureEntry>
          rowKey="slug"
          dataSource={registry ?? []}
          columns={featureColumns}
          pagination={false}
          size="small"
        />
      </Card>
    </Space>
  );
};

export default QuotaFeaturesTab;
```

- [ ] **Step 4: Run tests**

Run: `cd frontend && npm test -- QuotaFeaturesTab`
Expected: PASS.

- [ ] **Step 5: Manual smoke check**

Open Quota tab. Quota fields are visible but disabled; feature switches toggle and persist (refresh page → still toggled).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/customers/tabs/QuotaFeaturesTab.tsx frontend/src/pages/customers/tabs/QuotaFeaturesTab.test.tsx
git commit -m "feat(admin-customers): quota readout + feature toggles"
```

---

### Task 11: UsageLogsTab — token usage summary

**Files:**
- Modify: `frontend/src/pages/customers/tabs/UsageLogsTab.tsx`

**Purpose:** Show feature usage summary from the existing endpoint. Charts are out of scope; a sortable table is enough for v1.

- [ ] **Step 1: Replace UsageLogsTab with the real implementation**

Replace `frontend/src/pages/customers/tabs/UsageLogsTab.tsx`:

```tsx
import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, Table, Empty, Tag } from 'antd';
import dayjs from 'dayjs';
import { listCustomerUsage, type AdminFeatureUsageSummary } from '../../../services/adminCustomers';

const UsageLogsTab: React.FC<{ customerId: number }> = ({ customerId }) => {
  const { data, isLoading } = useQuery({
    queryKey: ['admin-customer-usage', customerId],
    queryFn: () => listCustomerUsage(customerId),
  });

  const columns = [
    { title: '功能', dataIndex: 'name_zh', key: 'name_zh' },
    { title: 'Slug', dataIndex: 'feature_slug', key: 'feature_slug', render: (s: string) => <Tag>{s}</Tag> },
    {
      title: '本月用量',
      dataIndex: 'units_consumed',
      key: 'units_consumed',
      sorter: (a: AdminFeatureUsageSummary, b: AdminFeatureUsageSummary) =>
        a.units_consumed - b.units_consumed,
      defaultSortOrder: 'descend' as const,
    },
    {
      title: '本月计费',
      dataIndex: 'total_charged_cents',
      key: 'total_charged_cents',
      render: (cents: number) => `$${(cents / 100).toFixed(2)}`,
    },
    {
      title: '最近一次',
      dataIndex: 'last_charged_at',
      key: 'last_charged_at',
      render: (t: string | null) => (t ? dayjs(t).format('YYYY-MM-DD HH:mm') : '—'),
    },
  ];

  return (
    <Card title="功能用量摘要">
      <Table<AdminFeatureUsageSummary>
        rowKey="feature_slug"
        dataSource={data ?? []}
        columns={columns}
        loading={isLoading}
        pagination={{ pageSize: 20 }}
        size="small"
        locale={{ emptyText: <Empty description="暂无用量数据" /> }}
      />
    </Card>
  );
};

export default UsageLogsTab;
```

- [ ] **Step 2: TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit 2>&1 | grep UsageLogsTab`
Expected: no output.

- [ ] **Step 3: Manual smoke check**

Open Usage tab. Table renders (empty for fresh customers, populated for customers with billed usage).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/customers/tabs/UsageLogsTab.tsx
git commit -m "feat(admin-customers): usage summary tab"
```

---

### Task 12: End-to-end smoke + polish

**Files:**
- Modify (only if needed): any of the files touched above

**Purpose:** Run the full operator workflow once, fix anything that breaks, run all frontend tests, type-check, and lint.

- [ ] **Step 1: Run all frontend tests**

Run: `cd frontend && npm test`
Expected: all tests pass. If any fail, fix and re-commit before continuing.

- [ ] **Step 2: TypeScript check**

Run: `cd frontend && npx tsc --noEmit 2>&1 | grep "src/services/adminCustomers\|src/pages/customers"`
Expected: no output. Pre-existing errors elsewhere are not in scope.

- [ ] **Step 3: Lint**

Run: `cd frontend && npm run lint 2>&1 | grep "src/services/adminCustomers\|src/pages/customers"`
Expected: no errors in the new files. If any, fix and commit.

- [ ] **Step 4: Manual end-to-end smoke (operator workflow)**

Start dev server and complete this script with a real backend:

1. Log in as admin.
2. Sidebar → "客户运营 → 新建客户".
3. Enter a fresh test email (e.g. `smoke+<timestamp>@tg1.ai`), click "生成 12 位随机密码", select industry "crypto", plan "Starter", note "smoke test".
4. Click "开户并激活". Modal must show email + password + portal URL; copy buttons must copy.
5. Click "前往客户详情". Overview shows 4 quota cards with the polling banner.
6. Switch to Billing tab. Subscription is active, invoice has one row.
7. Switch to Allocation tab. Click "重新分配账号", confirm. Refresh Overview — counts may change.
8. Switch to Quota 功能. Toggle a feature off, refresh page, it stays off.
9. Switch to Usage tab. Table either shows the recent feature usage or empty state.
10. Return to list. The new customer appears at the top.
11. Open `/portal/login` in an incognito tab. Log in with the captured email + password. Customer dashboard loads.

If anything in 1–11 fails, fix it as a new commit with `fix(admin-customers): ...` message and re-run the steps it affects.

- [ ] **Step 5: Final commit (only if Step 4 forced fixes)**

```bash
git add frontend/src/pages/customers frontend/src/services/adminCustomers.ts
git commit -m "fix(admin-customers): polish from end-to-end smoke"
```

---

## Spec Coverage Self-Review

| Spec section | Covered by task |
|---|---|
| §4.1 Backend endpoints consumed | Task 1 (service client wraps all) |
| §4.2 Frontend layout | Tasks 3–11 (one file per planned location) |
| §4.3 Module boundaries | Task 1 (service client) + Tasks 7–11 (independent `useQuery` per tab) |
| §5.1 Sidebar entry | Task 3 |
| §5.2 Customer list (columns, filters, empty state) | Task 4 |
| §5.3 New customer form + credentials modal | Task 5 |
| §5.4 Overview tab | Task 7 |
| §5.4 Billing tab | Task 8 |
| §5.4 Allocation tab | Task 9 |
| §5.4 Quota & features tab | Task 10 (with explicit deviation: quota ceilings are read-only — engineer note in task) |
| §5.4 Usage & logs tab | Task 11 |
| §6 Data flow | Tasks 5 (create), 7 (overview polling), 9 (reallocate), 10 (down-adjust → deviation noted) |
| §7 Error handling | Task 1 (`AdminApiError` + `normalize`) + each tab using `instanceof AdminApiError` |
| §8.1 Backend zero tests | Honored — no backend changes |
| §8.2 Frontend tests (NewCustomer, Allocation, QuotaFeatures) | Tasks 5, 9, 10 |
| §8.3 e2e deferred | Honored |
| §9 Security | Task 3 (`<AdminOnly>` wrapper on all routes) + Task 5 (no logging of credentials) |
| §12 Risks | Quick-provision shape verified in pre-plan reality check; single-customer GET handled via list+find in Task 1 |

**Known deviation from spec:** §5.4 said quota ceilings are editable; reality is no backend endpoint exists. Task 10 implements them as read-only with a tooltip explaining the limitation. This is called out in Task 10's engineer note. **Do not silently fix by writing a new backend endpoint — file a follow-up plan first.**
