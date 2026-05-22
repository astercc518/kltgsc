# Epic 1 — TG 号导入等级化 UI + 激活码体系 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Epic 1 of the business-flow rework: (a) let admin choose "使用等级 1/2/3" when importing TG accounts (UI-only, maps to existing `Account.role`); (b) ship an end-to-end activation-code subscription path (admin generates codes → customer redeems in portal → Subscription becomes active).

**Architecture:** Add a small bidirectional mapping (`account_roles.py`) so "等级 1/2/3" is purely UI sugar over the existing `role` field — no schema change, no business-logic drift. For activation codes, add a new `activation_code` table plus two columns on `subscription`, then refactor `activate_invoice` to extract a shared `_apply_subscription_activation` helper so both USDT and code paths reuse the same activation side effects (quota, denormalized fields, AI marketing features, provision_customer). Customer redeems via a new `/customer/redeem-code` endpoint that calls the shared helper.

**Tech Stack:**
- Backend: FastAPI + SQLModel + Alembic + pytest + pytest-asyncio (existing)
- Frontend: React + TypeScript + Ant Design + existing portal/admin SPAs
- DB: PostgreSQL (prod) / SQLite in-memory (tests)

---

## Decision Log

### 1. Mapping, not new column

`Account.role` is referenced by 10+ business modules ([account_roles.py:18](backend/app/core/account_roles.py#L18) is the only authoritative VALID_ROLES set). Adding a parallel `usage_level int` column would create two sources of truth that drift. We add a pure-functional bidirectional map in `account_roles.py`:

```
USAGE_LEVEL_TO_ROLE = {1: "worker", 2: "listener", 3: "support"}
ROLE_TO_USAGE_LEVEL = {"worker": 1, "listener": 2, "support": 3}
USAGE_LEVEL_LABEL_ZH = {1: "高危操作（群发/采集/拉群）", 2: "监听引流", 3: "客服交流"}
```

Other roles (`master`, `sales`, `collector`, `main`) have no usage-level concept — they return `None`. Endpoints accepting `usage_level: int | None` translate to `role: str` server-side; old callers passing `role` directly continue to work.

### 2. Activation code = second payment method for Subscription

Activation codes are NOT a parallel subscription mechanism — they are a non-USDT redemption path that reaches the same end state (`Subscription.status='active'` + customer denormalized fields + AI features + `provision_customer`). To avoid drift:

- Add column `subscription.activated_via VARCHAR(20) DEFAULT 'usdt'` (values: `usdt` / `code` / `admin_manual`).
- Add column `subscription.activation_code_id INTEGER NULL REFERENCES activation_code(id)`.
- Refactor [billing_service.activate_invoice](backend/app/services/billing_service.py#L173) to extract `_apply_subscription_activation(session, customer, subscription)` containing everything after the invoice-specific status flip (cancel-priors / set-active / refresh-customer / enable-features / provision). Both USDT and code paths call this helper.

**Hard constraint:** `activate_invoice` behavior must not change for existing USDT callers. Tests will pin existing behavior before the refactor.

### 3. Code format

12-character `secrets.token_urlsafe`-derived string, stored UPPERCASE, displayed grouped as `XXXX-XXXX-XXXX`. The grouping is presentation-only; redemption strips dashes case-insensitively. Format check: `^[A-Z0-9]{12}$` after normalization.

### 4. Code state machine

```
unused ──redeem──> redeemed     (terminal, sets redeemed_by_customer_id + redeemed_subscription_id + redeemed_at)
unused ──revoke──> revoked      (admin only, terminal)
redeemed/revoked → (no transitions)
```

Concurrent redeem race is closed by `UPDATE ... WHERE status='unused'` returning row count = 1 (or `SELECT ... FOR UPDATE` if running on SQLite for tests we use the same SQL guard which works because of single-writer semantics).

### 5. Code → Customer assignment

Codes have NO `customer_id` at generation time. They are bearer instruments. Whoever submits an unused code first via `POST /customer/redeem-code` claims it under their account. This matches user requirement ("admin 授权订阅激活码 用于激活营销账号" — bearer, no pre-binding).

### 6. What this Epic does NOT do

- Per-IP / per-customer redeem rate limiting (TODO comment only — recorded as future hardening).
- Email/notify customer when their code is generated (out of scope).
- Bulk CSV export UI in admin (the endpoint returns codes plainly; CSV button can be added later).

---

## File Structure

**Create:**
- `backend/alembic/versions/a4b5c6d7e8f9_epic1_activation_codes.py` — migration: new table + 2 columns
- `backend/app/models/activation_code.py` — ActivationCode SQLModel + Create/Read schemas
- `backend/app/services/activation_code_service.py` — generate / redeem / revoke
- `backend/tests/test_account_roles_usage_level.py` — mapping function tests
- `backend/tests/test_account_read_usage_level.py` — schema derivation test
- `backend/tests/test_import_endpoints_usage_level.py` — 4 import endpoints accept usage_level
- `backend/tests/test_billing_service_refactor.py` — pin existing activate_invoice behavior + verify helper
- `backend/tests/test_activation_code_service.py` — generate / redeem / revoke unit tests
- `backend/tests/test_admin_activation_codes_api.py` — admin endpoints
- `backend/tests/test_customer_redeem_api.py` — customer redeem endpoint
- `frontend/src/pages/billing/ActivationCodes.tsx` — admin list/generate/revoke page

**Modify:**
- `backend/app/core/account_roles.py` — add USAGE_LEVEL_TO_ROLE / ROLE_TO_USAGE_LEVEL / USAGE_LEVEL_LABEL_ZH / role_for_usage_level / usage_level_for_role
- `backend/app/models/account.py` — AccountRead.usage_level computed field
- `backend/app/models/subscription.py` — Subscription adds `activated_via` and `activation_code_id`
- `backend/app/api/v1/endpoints/accounts.py` — 4 import endpoints accept `usage_level` query/body
- `backend/app/tasks/account_tasks.py` — MegaImportRequest add usage_level + propagate to import_mega_accounts
- `backend/app/services/billing_service.py` — extract `_apply_subscription_activation`
- `backend/app/api/v1/endpoints/admin_billing.py` — 4 admin endpoints for codes
- `backend/app/api/v1/endpoints/customer_billing.py` — `POST /customer/redeem-code`
- `frontend/src/pages/accounts/AccountUploader.tsx` — defaultRole → defaultUsageLevel selector (4 tabs)
- `frontend/src/pages/accounts/AccountTable.tsx` — add "等级" column
- `frontend/src/portal/pages/Billing.tsx` — redeem-code card

---

## Task 1: Add usage-level mapping helpers

**Files:**
- Modify: `backend/app/core/account_roles.py`
- Create: `backend/tests/test_account_roles_usage_level.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_account_roles_usage_level.py`:

```python
"""usage_level <-> role bidirectional mapping for Epic 1 UI sugar."""
import pytest

from app.core.account_roles import (
    USAGE_LEVEL_TO_ROLE,
    ROLE_TO_USAGE_LEVEL,
    USAGE_LEVEL_LABEL_ZH,
    role_for_usage_level,
    usage_level_for_role,
)


def test_forward_map_covers_levels_1_2_3():
    assert USAGE_LEVEL_TO_ROLE == {1: "worker", 2: "listener", 3: "support"}


def test_reverse_map_is_consistent():
    for lvl, role in USAGE_LEVEL_TO_ROLE.items():
        assert ROLE_TO_USAGE_LEVEL[role] == lvl


def test_labels_present_for_each_level():
    for lvl in (1, 2, 3):
        assert lvl in USAGE_LEVEL_LABEL_ZH
        assert USAGE_LEVEL_LABEL_ZH[lvl]


def test_role_for_usage_level_valid():
    assert role_for_usage_level(1) == "worker"
    assert role_for_usage_level(2) == "listener"
    assert role_for_usage_level(3) == "support"


def test_role_for_usage_level_none_or_invalid_returns_none():
    assert role_for_usage_level(None) is None
    assert role_for_usage_level(0) is None
    assert role_for_usage_level(4) is None
    assert role_for_usage_level(99) is None


def test_usage_level_for_role_known():
    assert usage_level_for_role("worker") == 1
    assert usage_level_for_role("listener") == 2
    assert usage_level_for_role("support") == 3


def test_usage_level_for_role_unmapped_returns_none():
    # master / sales / collector / main have no usage-level concept
    assert usage_level_for_role("master") is None
    assert usage_level_for_role("collector") is None
    assert usage_level_for_role("main") is None
    assert usage_level_for_role(None) is None
    assert usage_level_for_role("nonsense") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_account_roles_usage_level.py -v`
Expected: ImportError on `USAGE_LEVEL_TO_ROLE` (not yet defined).

- [ ] **Step 3: Add mapping + helpers to `account_roles.py`**

Append to [backend/app/core/account_roles.py](backend/app/core/account_roles.py), after the existing `tier_for_role` function:

```python
# ── Epic 1 — usage-level UI sugar ─────────────────────────────────────
# Admin's "使用等级 1/2/3" is a UX label over a subset of role values.
# DB still stores `role`; this map is purely for translating between
# admin UI selectors and the underlying role string. Roles outside this
# subset (master / sales / collector / main) have no usage_level — those
# are reserved for admin/system flows and never appear in the import
# picker.
USAGE_LEVEL_TO_ROLE: dict[int, str] = {
    1: "worker",     # 高危操作（群发/采集/拉群）
    2: "listener",   # 监听引流
    3: "support",    # 客服交流
}

ROLE_TO_USAGE_LEVEL: dict[str, int] = {
    role: level for level, role in USAGE_LEVEL_TO_ROLE.items()
}

USAGE_LEVEL_LABEL_ZH: dict[int, str] = {
    1: "高危操作（群发/采集/拉群）",
    2: "监听引流",
    3: "客服交流",
}


def role_for_usage_level(level: Optional[int]) -> Optional[str]:
    """Translate UI 等级 1/2/3 to DB role. Returns None for invalid input."""
    if level is None:
        return None
    return USAGE_LEVEL_TO_ROLE.get(level)


def usage_level_for_role(role: Optional[str]) -> Optional[int]:
    """Inverse of role_for_usage_level. Returns None for roles outside the picker subset."""
    if not role:
        return None
    return ROLE_TO_USAGE_LEVEL.get(role)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_account_roles_usage_level.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/account_roles.py backend/tests/test_account_roles_usage_level.py
git commit -m "feat(epic1): usage_level <-> role mapping helpers"
```

---

## Task 2: AccountRead exposes `usage_level` derived field

**Files:**
- Modify: `backend/app/models/account.py` (AccountRead class)
- Create: `backend/tests/test_account_read_usage_level.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_account_read_usage_level.py`:

```python
"""AccountRead serializes a derived `usage_level` field from role."""
from datetime import datetime

from app.models.account import Account, AccountRead


def _make_account(role: str | None) -> Account:
    return Account(
        id=1,
        phone_number="+10000000000",
        role=role,
        created_at=datetime.utcnow(),
    )


def test_account_read_usage_level_worker():
    ar = AccountRead.model_validate(_make_account("worker"))
    assert ar.usage_level == 1


def test_account_read_usage_level_listener():
    ar = AccountRead.model_validate(_make_account("listener"))
    assert ar.usage_level == 2


def test_account_read_usage_level_support():
    ar = AccountRead.model_validate(_make_account("support"))
    assert ar.usage_level == 3


def test_account_read_usage_level_other_role_is_none():
    for role in ("master", "sales", "collector", "main"):
        ar = AccountRead.model_validate(_make_account(role))
        assert ar.usage_level is None, f"role={role} should yield None"


def test_account_read_usage_level_no_role_is_none():
    ar = AccountRead.model_validate(_make_account(None))
    assert ar.usage_level is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_account_read_usage_level.py -v`
Expected: AttributeError or validation error — `usage_level` not defined.

- [ ] **Step 3: Add the computed field to AccountRead**

Edit [backend/app/models/account.py](backend/app/models/account.py). Find the existing `AccountRead` class (line ~79) and modify it:

```python
class AccountRead(AccountBase):
    id: int
    created_at: datetime
    proxy: Optional[Proxy] = None
    usage_level: Optional[int] = None  # derived from role; UI display only

    @classmethod
    def model_validate(cls, obj, **kwargs):
        # Compute usage_level from role when serializing an Account instance.
        from app.core.account_roles import usage_level_for_role
        instance = super().model_validate(obj, **kwargs)
        if instance.usage_level is None and getattr(obj, "role", None):
            instance.usage_level = usage_level_for_role(obj.role)
        return instance
```

If `AccountRead` is already a `SQLModel` subclass, the cleaner Pydantic v2 idiom is a `model_validator` — use this alternative implementation instead:

```python
from pydantic import model_validator


class AccountRead(AccountBase):
    id: int
    created_at: datetime
    proxy: Optional[Proxy] = None
    usage_level: Optional[int] = None

    @model_validator(mode="after")
    def _set_usage_level(self):
        if self.usage_level is None and self.role:
            from app.core.account_roles import usage_level_for_role
            self.usage_level = usage_level_for_role(self.role)
        return self
```

Use whichever pattern matches the existing codebase style (read [backend/app/models/customer.py](backend/app/models/customer.py) for the convention; if customer.py uses `model_validator`, use that. If it uses `__init__`-style overrides, use the first pattern).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_account_read_usage_level.py -v`
Expected: 5 passed.

- [ ] **Step 5: Sanity-check unchanged callers**

Run: `cd backend && pytest tests/ -v -k "account" --timeout=60`
Expected: no regressions. `AccountRead` is constructed in many places; the field is additive (Optional[int] default None) so existing JSON consumers won't break.

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/account.py backend/tests/test_account_read_usage_level.py
git commit -m "feat(epic1): AccountRead exposes derived usage_level"
```

---

## Task 3: 4 import endpoints accept `usage_level`

**Files:**
- Modify: `backend/app/api/v1/endpoints/accounts.py` (`upload_session`, `upload_sessions_batch`, `upload_tdata_batch`, `MegaImportRequest`)
- Modify: `backend/app/tasks/account_tasks.py` (`_apply_role_to_account` already exists, but call sites need to handle usage_level translation)
- Create: `backend/tests/test_import_endpoints_usage_level.py`

This task touches 4 import paths but the change is the same shape on each: accept optional `usage_level: int`, translate to `role` via `role_for_usage_level`, then pass to existing logic. If both `role` and `usage_level` are passed, `usage_level` wins (UI sends it).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_import_endpoints_usage_level.py`:

```python
"""4 admin import endpoints honor usage_level parameter (1=worker, 2=listener, 3=support)."""
import io
import pytest
from unittest.mock import patch

from sqlmodel import select
from app.models.account import Account


@pytest.fixture
def admin_client(client, session):
    """A TestClient pre-authenticated as admin. Assumes existing admin fixture
    machinery in conftest. If no such fixture exists, this test will need
    an admin JWT token header added manually — see CONVENTIONS.md."""
    from app.core.security import create_access_token
    token = create_access_token({"sub": "admin", "type": "user", "user_id": 1})
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


def test_upload_session_usage_level_1_sets_role_worker(admin_client, session, monkeypatch):
    # Mock the actual Telethon session parse so we don't need a real .session file
    from app.api.v1.endpoints import accounts as accounts_mod
    fake_phone = "+19999990001"

    def fake_parse(filepath, **kwargs):
        return {"phone_number": fake_phone, "api_id": 1, "api_hash": "x"}

    monkeypatch.setattr(accounts_mod, "_parse_session_metadata", fake_parse, raising=False)

    files = {"file": ("test.session", io.BytesIO(b"\x00" * 64), "application/octet-stream")}
    resp = admin_client.post("/api/v1/accounts/upload?usage_level=1", files=files)
    assert resp.status_code in (200, 201), resp.text

    acc = session.exec(select(Account).where(Account.phone_number == fake_phone)).first()
    assert acc is not None
    assert acc.role == "worker"


def test_upload_session_usage_level_2_sets_role_listener(admin_client, session, monkeypatch):
    from app.api.v1.endpoints import accounts as accounts_mod
    fake_phone = "+19999990002"
    monkeypatch.setattr(
        accounts_mod, "_parse_session_metadata",
        lambda *a, **k: {"phone_number": fake_phone, "api_id": 1, "api_hash": "x"},
        raising=False,
    )

    files = {"file": ("test.session", io.BytesIO(b"\x00" * 64), "application/octet-stream")}
    resp = admin_client.post("/api/v1/accounts/upload?usage_level=2", files=files)
    assert resp.status_code in (200, 201), resp.text

    acc = session.exec(select(Account).where(Account.phone_number == fake_phone)).first()
    assert acc.role == "listener"


def test_upload_session_usage_level_overrides_role_param(admin_client, session, monkeypatch):
    """When both role= and usage_level= are passed, usage_level wins."""
    from app.api.v1.endpoints import accounts as accounts_mod
    fake_phone = "+19999990003"
    monkeypatch.setattr(
        accounts_mod, "_parse_session_metadata",
        lambda *a, **k: {"phone_number": fake_phone, "api_id": 1, "api_hash": "x"},
        raising=False,
    )

    files = {"file": ("test.session", io.BytesIO(b"\x00" * 64), "application/octet-stream")}
    resp = admin_client.post(
        "/api/v1/accounts/upload?role=collector&usage_level=3",
        files=files,
    )
    assert resp.status_code in (200, 201), resp.text

    acc = session.exec(select(Account).where(Account.phone_number == fake_phone)).first()
    assert acc.role == "support"  # usage_level=3 wins over role=collector


def test_upload_session_usage_level_invalid_returns_400(admin_client):
    files = {"file": ("test.session", io.BytesIO(b"\x00" * 64), "application/octet-stream")}
    resp = admin_client.post("/api/v1/accounts/upload?usage_level=99", files=files)
    assert resp.status_code == 400


def test_mega_import_request_accepts_usage_level():
    """MegaImportRequest body model accepts usage_level."""
    from app.api.v1.endpoints.accounts import MegaImportRequest
    req = MegaImportRequest(mega_url="https://mega.nz/x", usage_level=2)
    assert req.usage_level == 2
    # Existing field still works:
    req2 = MegaImportRequest(mega_url="https://mega.nz/x", role="worker")
    assert req2.role == "worker"
```

Note: if `_parse_session_metadata` doesn't exist in `accounts.py` (the actual parser might have a different name), inspect [backend/app/api/v1/endpoints/accounts.py:322-395](backend/app/api/v1/endpoints/accounts.py#L322) to find the actual session-parse call and monkeypatch that instead. The test fixtures must mock the Telethon parse so we don't need a real session file.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_import_endpoints_usage_level.py -v`
Expected: failures on usage_level not recognized, or 422 (FastAPI rejects unknown query param).

- [ ] **Step 3: Add `usage_level` param to upload_session**

In [backend/app/api/v1/endpoints/accounts.py](backend/app/api/v1/endpoints/accounts.py) at line ~322:

Find the signature (currently):
```python
async def upload_session(
    file: UploadFile = File(...),
    role: Optional[str] = Query(None),
    ...
):
```

Change to:
```python
async def upload_session(
    file: UploadFile = File(...),
    role: Optional[str] = Query(None),
    usage_level: Optional[int] = Query(None, description="UI 等级 1/2/3, overrides role"),
    ...
):
    from app.core.account_roles import role_for_usage_level
    if usage_level is not None:
        translated = role_for_usage_level(usage_level)
        if translated is None:
            raise HTTPException(status_code=400, detail=f"Invalid usage_level: {usage_level}")
        role = translated  # usage_level wins over role
```

Do the same in:
- `upload_sessions_batch` (line ~398)
- `upload_tdata_batch` (line ~545)

For the Mega import path, find `MegaImportRequest` (line ~63) and add the field:

```python
class MegaImportRequest(BaseModel):
    mega_url: str
    target_channels: Optional[str] = "kltgsc"
    role: Optional[str] = None  # 导入后默认角色（worker/master/support/sales/listener/collector）
    usage_level: Optional[int] = None  # UI 等级 1/2/3, overrides role when present
```

Find the endpoint that consumes this model (search for `MegaImportRequest` usage in the same file) and add the same translation block at the top:

```python
from app.core.account_roles import role_for_usage_level
if request.usage_level is not None:
    translated = role_for_usage_level(request.usage_level)
    if translated is None:
        raise HTTPException(status_code=400, detail=f"Invalid usage_level: {request.usage_level}")
    request.role = translated
```

- [ ] **Step 4: Run tests**

Run: `cd backend && pytest tests/test_import_endpoints_usage_level.py -v`
Expected: 5 passed.

- [ ] **Step 5: Smoke-check existing role-only callers still work**

Run: `cd backend && pytest tests/test_api_accounts.py tests/test_mega_importer.py -v`
Expected: no regressions in existing import tests.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/v1/endpoints/accounts.py backend/tests/test_import_endpoints_usage_level.py
git commit -m "feat(epic1): 4 import endpoints accept usage_level (UI 1/2/3 → role)"
```

---

## Task 4: Frontend — AccountUploader picker switches to 使用等级

**Files:**
- Modify: `frontend/src/pages/accounts/AccountUploader.tsx`
- Modify: `frontend/src/pages/accounts/AccountTable.tsx`
- Modify: `frontend/src/pages/accounts/AccountDetailDrawer.tsx`

Frontend has no Jest setup that we've confirmed; this task is verified by manual UI inspection. **If a test runner exists in `frontend/`, add a single render test per touched component asserting the new label appears.** Otherwise commit and verify via the running dev server.

- [ ] **Step 1: Inspect existing role usage in AccountUploader**

Read [frontend/src/pages/accounts/AccountUploader.tsx](frontend/src/pages/accounts/AccountUploader.tsx). Find where `defaultRole` (or whatever the role state is called) is declared and where it's submitted in each of the 4 Tab forms.

- [ ] **Step 2: Add UsageLevel constant + replace role state**

Create or modify `frontend/src/pages/accounts/usageLevel.ts` (new file, helper module):

```typescript
// Mirrors backend/app/core/account_roles.py — keep both in sync.
export const USAGE_LEVELS = [
  { value: 1, label: "等级 1 — 高危操作（群发/采集/拉群）", color: "red" },
  { value: 2, label: "等级 2 — 监听引流", color: "blue" },
  { value: 3, label: "等级 3 — 客服交流", color: "green" },
] as const;

export type UsageLevel = 1 | 2 | 3;

export const labelForUsageLevel = (level: number | null | undefined): string => {
  const entry = USAGE_LEVELS.find(u => u.value === level);
  return entry ? entry.label : "未指定";
};

export const colorForUsageLevel = (level: number | null | undefined): string => {
  const entry = USAGE_LEVELS.find(u => u.value === level);
  return entry ? entry.color : "default";
};
```

- [ ] **Step 3: Modify AccountUploader to use usage_level picker**

In `AccountUploader.tsx`:

1. Add import: `import { USAGE_LEVELS, UsageLevel } from "./usageLevel";`
2. Replace `defaultRole` state with `defaultUsageLevel: UsageLevel = 1`
3. Replace the role `<Select>` (in all 4 tabs) with:

```tsx
<Form.Item label="使用等级" name="usage_level" initialValue={1}>
  <Select>
    {USAGE_LEVELS.map(u => (
      <Select.Option key={u.value} value={u.value}>
        {u.label}
      </Select.Option>
    ))}
  </Select>
</Form.Item>
```

4. In the submit handlers, replace `role: defaultRole` (or the equivalent) with `usage_level: values.usage_level` in the request payload / query string.

- [ ] **Step 4: Add "等级" column to AccountTable**

In `AccountTable.tsx`, add a new column between existing role/status columns:

```tsx
{
  title: "等级",
  dataIndex: "usage_level",
  key: "usage_level",
  width: 130,
  render: (level: number | null) => {
    if (level == null) return <Tag>未指定</Tag>;
    const entry = USAGE_LEVELS.find(u => u.value === level);
    return entry ? <Tag color={entry.color}>{entry.label.split("—")[0].trim()}</Tag> : <Tag>未指定</Tag>;
  },
},
```

Import `USAGE_LEVELS` and `Tag` from Ant Design at the top.

- [ ] **Step 5: Update AccountDetailDrawer**

In `AccountDetailDrawer.tsx`, find the line showing `account.role` and add (above or instead) a display of `usage_level`:

```tsx
{account.usage_level != null && (
  <Descriptions.Item label="使用等级">
    <Tag color={colorForUsageLevel(account.usage_level)}>
      {labelForUsageLevel(account.usage_level)}
    </Tag>
  </Descriptions.Item>
)}
```

- [ ] **Step 6: Run dev server and smoke-test manually**

Run: `cd /var/tgsc && docker compose up -d frontend && curl -s http://localhost:3000/ > /dev/null`

Open browser, navigate to `/accounts`. Verify:
- AccountUploader 4 tabs all show "使用等级" picker with 3 options.
- After importing one account in each level, AccountTable shows the matching color tag in the new "等级" column.
- Detail drawer shows the level.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/accounts/
git commit -m "feat(epic1): admin AccountUploader/Table/Drawer show usage_level"
```

---

## Task 5: DB migration — activation_code table + subscription columns

**Files:**
- Create: `backend/alembic/versions/a4b5c6d7e8f9_epic1_activation_codes.py`

- [ ] **Step 1: Write the migration**

Create `backend/alembic/versions/a4b5c6d7e8f9_epic1_activation_codes.py`:

```python
"""add activation_code table + subscription activated_via columns for Epic 1

Revision ID: a4b5c6d7e8f9
Revises: e4f5a6b7c8d9
Create Date: 2026-05-22

Epic 1 — bearer activation codes for subscription redemption.
Codes are admin-batch-generated, customer-redeemed in portal.
The activated_via column distinguishes USDT vs code vs admin_manual
activation sources sharing the same Subscription pipeline.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'a4b5c6d7e8f9'
down_revision: Union[str, Sequence[str], None] = 'e4f5a6b7c8d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # New table: activation_code
    op.execute("""
        CREATE TABLE IF NOT EXISTS activation_code (
            id SERIAL PRIMARY KEY,
            code VARCHAR(32) NOT NULL UNIQUE,
            plan VARCHAR(20) NOT NULL,
            duration_days INTEGER NOT NULL DEFAULT 30,
            batch_id VARCHAR(36) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'unused',
            created_by_admin_id INTEGER REFERENCES "user"(id) ON DELETE SET NULL,
            redeemed_by_customer_id INTEGER REFERENCES customer(id) ON DELETE SET NULL,
            redeemed_subscription_id INTEGER REFERENCES subscription(id) ON DELETE SET NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            redeemed_at TIMESTAMP,
            notes VARCHAR(200)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_activation_code_status ON activation_code(status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_activation_code_batch_id ON activation_code(batch_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_activation_code_plan ON activation_code(plan)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_activation_code_redeemed_by_customer_id ON activation_code(redeemed_by_customer_id)")

    # Subscription gets two new columns
    op.execute("""
        ALTER TABLE subscription
        ADD COLUMN IF NOT EXISTS activated_via VARCHAR(20) NOT NULL DEFAULT 'usdt'
    """)
    op.execute("""
        ALTER TABLE subscription
        ADD COLUMN IF NOT EXISTS activation_code_id INTEGER
            REFERENCES activation_code(id) ON DELETE SET NULL
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE subscription DROP COLUMN IF EXISTS activation_code_id")
    op.execute("ALTER TABLE subscription DROP COLUMN IF EXISTS activated_via")
    op.execute("DROP TABLE IF EXISTS activation_code")
```

**Important:** The `Revises:` line must point to the most recent existing migration. Check with:

```bash
cd /var/tgsc/backend && ls -1 alembic/versions/*.py | sort | tail -3
```

If `e4f5a6b7c8d9_seed_ai_marketing_features.py` is not the latest, update `down_revision` to whichever is.

- [ ] **Step 2: Apply the migration locally**

Run:
```bash
cd /var/tgsc && docker compose exec backend alembic upgrade head 2>&1 | tail -10
```

Expected: `INFO  [alembic.runtime.migration] Running upgrade ... -> a4b5c6d7e8f9, add activation_code table ...`

- [ ] **Step 3: Verify schema in DB**

```bash
docker exec tgsc_postgres psql -U tgsc_user -d tgsc_prod -c "\d activation_code"
docker exec tgsc_postgres psql -U tgsc_user -d tgsc_prod -c "SELECT column_name, data_type, column_default FROM information_schema.columns WHERE table_name='subscription' AND column_name IN ('activated_via', 'activation_code_id')"
```

Expected: activation_code table listed with all columns; subscription shows `activated_via VARCHAR(20) DEFAULT 'usdt'::character varying` and `activation_code_id INTEGER`.

- [ ] **Step 4: Test downgrade works (then re-upgrade)**

```bash
docker compose exec backend alembic downgrade -1 2>&1 | tail -5
docker compose exec backend alembic upgrade head 2>&1 | tail -5
```

Expected: both succeed without error.

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/a4b5c6d7e8f9_epic1_activation_codes.py
git commit -m "feat(epic1): migration — activation_code table + subscription columns"
```

---

## Task 6: ActivationCode SQLModel + schemas

**Files:**
- Create: `backend/app/models/activation_code.py`
- Modify: `backend/app/models/subscription.py` (add 2 fields to Subscription class)

- [ ] **Step 1: Write the model file**

Create `backend/app/models/activation_code.py`:

```python
"""
ActivationCode — bearer redemption code for subscription activation.

Epic 1 — admin generates a batch of codes for a given plan, distributes
them out-of-band (email/IM/etc.), and any customer who submits an unused
code via /customer/redeem-code claims an active Subscription on that
plan. See docs/superpowers/plans/2026-05-22-epic1-levels-and-activation-codes.md
"""
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


# ── State machine ──────────────────────────────────────────────────────
CODE_UNUSED = "unused"
CODE_REDEEMED = "redeemed"
CODE_REVOKED = "revoked"
CODE_STATUSES = {CODE_UNUSED, CODE_REDEEMED, CODE_REVOKED}


class ActivationCode(SQLModel, table=True):
    __tablename__ = "activation_code"

    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(unique=True, index=True, max_length=32)
    plan: str = Field(index=True, max_length=20)  # starter / growth / pro
    duration_days: int = Field(default=30)
    batch_id: str = Field(index=True, max_length=36)  # UUID4 hex, groups codes from one generate call
    status: str = Field(default=CODE_UNUSED, index=True, max_length=20)

    created_by_admin_id: Optional[int] = Field(default=None, foreign_key="user.id")
    redeemed_by_customer_id: Optional[int] = Field(
        default=None, foreign_key="customer.id", index=True
    )
    redeemed_subscription_id: Optional[int] = Field(
        default=None, foreign_key="subscription.id"
    )

    created_at: datetime = Field(default_factory=datetime.utcnow)
    redeemed_at: Optional[datetime] = None
    notes: Optional[str] = Field(default=None, max_length=200)


# ── Request / response schemas ─────────────────────────────────────────

class ActivationCodeGenerateRequest(SQLModel):
    plan: str
    count: int = Field(default=1, ge=1, le=500)
    duration_days: int = Field(default=30, ge=1, le=365)
    notes: Optional[str] = None


class ActivationCodeRead(SQLModel):
    id: int
    code: str
    plan: str
    duration_days: int
    batch_id: str
    status: str
    created_by_admin_id: Optional[int]
    redeemed_by_customer_id: Optional[int]
    redeemed_subscription_id: Optional[int]
    created_at: datetime
    redeemed_at: Optional[datetime]
    notes: Optional[str]


class ActivationCodeGenerateResponse(SQLModel):
    batch_id: str
    codes: list[ActivationCodeRead]


class ActivationCodeRedeemRequest(SQLModel):
    code: str
```

- [ ] **Step 2: Update Subscription with new fields**

In [backend/app/models/subscription.py](backend/app/models/subscription.py), modify the `Subscription` class to add the two new fields:

```python
class Subscription(SQLModel, table=True):
    __tablename__ = "subscription"

    id: Optional[int] = Field(default=None, primary_key=True)
    customer_id: int = Field(foreign_key="customer.id", index=True)

    plan: str = Field(index=True, max_length=20)
    status: str = Field(default=SUB_PENDING, index=True, max_length=20)

    period_start: datetime
    period_end: datetime
    auto_renew: bool = Field(default=False)

    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    activated_at: Optional[datetime] = None
    canceled_at: Optional[datetime] = None

    # Epic 1 — activation provenance
    activated_via: str = Field(default="usdt", max_length=20)  # usdt / code / admin_manual
    activation_code_id: Optional[int] = Field(default=None, foreign_key="activation_code.id")
```

Also update `SubscriptionRead` to expose `activated_via`:

```python
class SubscriptionRead(SQLModel):
    id: int
    customer_id: int
    plan: str
    status: str
    period_start: datetime
    period_end: datetime
    auto_renew: bool
    activated_at: Optional[datetime]
    created_at: datetime
    activated_via: str = "usdt"  # default for back-compat with old DB rows
```

- [ ] **Step 3: Register the model in `app/models/__init__.py`**

In [backend/app/models/__init__.py](backend/app/models/__init__.py), add:

```python
from app.models.activation_code import ActivationCode  # noqa: F401
```

This ensures SQLModel sees the table when conftest does `import app.models`.

- [ ] **Step 4: Verify conftest in-memory tests still build the schema**

Run: `cd backend && pytest tests/test_account_roles_usage_level.py -v`

Expected: still passes. (This indirectly verifies model registration didn't break import.)

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/activation_code.py backend/app/models/subscription.py backend/app/models/__init__.py
git commit -m "feat(epic1): ActivationCode model + Subscription.activated_via"
```

---

## Task 7: Pin existing `activate_invoice` behavior (regression test)

Before refactoring `activate_invoice` to extract the shared helper (next task), we lock in current behavior so the refactor cannot drift.

**Files:**
- Create: `backend/tests/test_billing_service_refactor.py`

- [ ] **Step 1: Write the pinning tests**

Create `backend/tests/test_billing_service_refactor.py`:

```python
"""Lock in activate_invoice behavior before extracting _apply_subscription_activation.

These tests must pass against the CURRENT activate_invoice (pre-refactor)
and continue to pass after the refactor in Task 8. Any drift = regression.
"""
from datetime import datetime, timedelta

import pytest
from sqlmodel import select

from app.models.customer import Customer, STATUS_ACTIVE
from app.models.subscription import (
    Invoice,
    INV_PENDING,
    INV_PAID,
    SUB_ACTIVE,
    SUB_PENDING,
    SUB_CANCELED,
    Subscription,
)
from app.services.billing_service import activate_invoice


@pytest.fixture
def customer(session):
    c = Customer(
        email="t@t.t",
        password_hash="x",
        status="pending",
        plan=None,
        account_quota=0, group_quota=0, token_quota=0, seat_quota=0,
    )
    session.add(c); session.commit(); session.refresh(c)
    return c


def _make_pending(session, customer, plan="starter"):
    now = datetime.utcnow()
    sub = Subscription(
        customer_id=customer.id, plan=plan, status=SUB_PENDING,
        period_start=now, period_end=now + timedelta(days=30),
    )
    session.add(sub); session.flush()
    inv = Invoice(
        customer_id=customer.id, subscription_id=sub.id,
        plan=plan, amount_usd=199.0, amount_crypto=199.5, currency="USDT",
        network="TRC20", payment_address="addr",
        status=INV_PENDING, description="test",
        expires_at=now + timedelta(minutes=30),
    )
    session.add(inv); session.commit(); session.refresh(inv)
    return inv, sub


def test_activate_invoice_marks_invoice_paid(session, customer, monkeypatch):
    monkeypatch.setattr(
        "app.services.allocation_service.provision_customer",
        lambda s, c: None, raising=False,
    )
    inv, sub = _make_pending(session, customer)
    result_sub = activate_invoice(session, inv, tx_hash="0xabc", admin_user_id=1)
    session.refresh(inv)
    assert inv.status == INV_PAID
    assert inv.tx_hash == "0xabc"
    assert inv.paid_at is not None
    assert inv.paid_by_admin == 1


def test_activate_invoice_activates_subscription(session, customer, monkeypatch):
    monkeypatch.setattr(
        "app.services.allocation_service.provision_customer",
        lambda s, c: None, raising=False,
    )
    inv, sub = _make_pending(session, customer)
    result_sub = activate_invoice(session, inv, tx_hash="0xabc")
    assert result_sub.status == SUB_ACTIVE
    assert result_sub.activated_at is not None


def test_activate_invoice_cancels_prior_active(session, customer, monkeypatch):
    monkeypatch.setattr(
        "app.services.allocation_service.provision_customer",
        lambda s, c: None, raising=False,
    )
    # Pre-existing active subscription on a different plan
    now = datetime.utcnow()
    prior = Subscription(
        customer_id=customer.id, plan="starter", status=SUB_ACTIVE,
        period_start=now - timedelta(days=10), period_end=now + timedelta(days=20),
        activated_at=now - timedelta(days=10),
    )
    session.add(prior); session.commit(); session.refresh(prior)

    inv, new_sub = _make_pending(session, customer, plan="growth")
    activate_invoice(session, inv, tx_hash="0xdef")

    session.refresh(prior)
    assert prior.status == SUB_CANCELED
    assert prior.canceled_at is not None


def test_activate_invoice_refreshes_customer_denormalized(session, customer, monkeypatch):
    monkeypatch.setattr(
        "app.services.allocation_service.provision_customer",
        lambda s, c: None, raising=False,
    )
    inv, sub = _make_pending(session, customer, plan="growth")
    activate_invoice(session, inv, tx_hash="0xghi")
    session.refresh(customer)
    assert customer.status == STATUS_ACTIVE
    assert customer.plan == "growth"
    assert customer.subscription_status == SUB_ACTIVE
    # quota fields should be set to plan defaults
    assert customer.account_quota > 0
    assert customer.group_quota > 0


def test_activate_invoice_is_idempotent_on_paid_invoice(session, customer, monkeypatch):
    monkeypatch.setattr(
        "app.services.allocation_service.provision_customer",
        lambda s, c: None, raising=False,
    )
    inv, sub = _make_pending(session, customer)
    activate_invoice(session, inv, tx_hash="0xabc")
    # Second call must not raise / must not double-activate
    result = activate_invoice(session, inv, tx_hash="0xabc")
    assert result.id == sub.id
    assert result.status == SUB_ACTIVE


def test_activate_invoice_sets_activated_via_usdt(session, customer, monkeypatch):
    """Pin Epic 1: USDT path leaves activated_via at default 'usdt'."""
    monkeypatch.setattr(
        "app.services.allocation_service.provision_customer",
        lambda s, c: None, raising=False,
    )
    inv, sub = _make_pending(session, customer)
    result = activate_invoice(session, inv, tx_hash="0xabc")
    assert result.activated_via == "usdt"
    assert result.activation_code_id is None
```

- [ ] **Step 2: Run tests to verify all pass (against current activate_invoice)**

Run: `cd backend && pytest tests/test_billing_service_refactor.py -v`
Expected: 6 passed (these test current behavior, which already works).

If the last test (`activated_via_usdt`) fails because the field default isn't loaded from DB on SQLite, ensure conftest's `engine` fixture re-runs `SQLModel.metadata.create_all` after the model changes in Task 6. If still failing, that's a Task 6 issue — revisit.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_billing_service_refactor.py
git commit -m "test(epic1): pin activate_invoice behavior before extraction"
```

---

## Task 8: Extract `_apply_subscription_activation` helper

Refactor `activate_invoice` to extract a private helper containing the post-invoice-flip side effects (cancel-priors, set-active, refresh-customer, enable-features, provision). This helper will also be called by `redeem_code` in Task 9.

**Files:**
- Modify: `backend/app/services/billing_service.py`

- [ ] **Step 1: Refactor activate_invoice**

In [backend/app/services/billing_service.py](backend/app/services/billing_service.py), replace `activate_invoice` and add the helper. Final state of the file should have:

```python
def _apply_subscription_activation(
    session: Session,
    customer: Customer,
    subscription: Subscription,
) -> Subscription:
    """Side effects shared by USDT-invoice and activation-code paths.

    Idempotent on `subscription.status == SUB_ACTIVE` (returns without changes).
    Caller MUST have already set subscription.activated_via and (if applicable)
    activation_code_id before invoking this helper.

    Side effects (all in one commit):
      - Cancel any other active Subscription for this customer
      - Mark `subscription` active + activated_at = now
      - Refresh Customer denormalized fields + quota
      - Auto-enable AI marketing feature slugs
      - Trigger provision_customer (account/group/KB allocation)
    """
    if subscription.status == SUB_ACTIVE:
        return subscription

    now = datetime.utcnow()

    # Cancel any other active subscription for this customer
    prior_active = session.exec(
        select(Subscription).where(
            Subscription.customer_id == customer.id,
            Subscription.status == SUB_ACTIVE,
            Subscription.id != subscription.id,
        )
    ).all()
    for prev in prior_active:
        prev.status = SUB_CANCELED
        prev.canceled_at = now
        session.add(prev)

    subscription.status = SUB_ACTIVE
    subscription.activated_at = now
    session.add(subscription)

    quota = PLAN_QUOTA[subscription.plan]
    customer.status = STATUS_ACTIVE
    customer.plan = subscription.plan
    customer.subscription_status = SUB_ACTIVE
    customer.current_period_end = subscription.period_end
    customer.account_quota = quota["account"]
    customer.group_quota = quota["group"]
    customer.token_quota = quota["token"]
    customer.seat_quota = quota["seat"]
    customer.updated_at = now
    session.add(customer)

    session.commit()
    session.refresh(subscription)

    # Auto-enable AI marketing features (best-effort)
    try:
        from app.services import feature_billing as fb
        for slug in (
            "ai_marketing_assistant",
            "ai_marketing_group_reply",
            "ai_marketing_lead_created",
        ):
            fb.upsert_customer_feature(
                session, customer.id, slug,
                enabled=True,
                notes=f"auto-enabled on activation of {subscription.plan} plan",
            )
    except Exception as e:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).warning(
            "Failed to auto-enable AI marketing features for customer %s: %s",
            customer.id, e,
        )

    # Auto-provision accounts + groups (best-effort, never blocks payment confirmation)
    subscription_id = subscription.id
    try:
        from app.services.allocation_service import provision_customer
        provision_customer(session, customer)
    except Exception as e:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).exception(
            "Provisioning failed for customer %s after activation: %s",
            customer.id, e,
        )

    # Re-fetch — provision_customer issued multiple commits that expired
    # this Session's identity-map entry for `subscription`.
    return session.get(Subscription, subscription_id)


def activate_invoice(
    session: Session,
    invoice: Invoice,
    tx_hash: str,
    admin_user_id: Optional[int] = None,
) -> Subscription:
    """Mark an invoice as paid and activate its subscription (USDT path)."""
    if invoice.status == INV_PAID:
        return session.get(Subscription, invoice.subscription_id)
    if invoice.status != INV_PENDING:
        raise BillingError(
            f"Invoice {invoice.id} is in status '{invoice.status}', cannot activate"
        )
    if invoice.expires_at < datetime.utcnow():
        raise BillingError(f"Invoice {invoice.id} has expired")

    customer = session.get(Customer, invoice.customer_id)
    if not customer:
        raise BillingError(f"Customer {invoice.customer_id} not found")

    subscription = session.get(Subscription, invoice.subscription_id)
    if not subscription:
        raise BillingError(f"Subscription {invoice.subscription_id} not found")

    now = datetime.utcnow()

    # Mark invoice paid (USDT-specific)
    invoice.status = INV_PAID
    invoice.tx_hash = tx_hash
    invoice.paid_at = now
    invoice.paid_by_admin = admin_user_id
    session.add(invoice)

    # Pin activation provenance
    subscription.activated_via = "usdt"
    session.add(subscription)
    session.commit()
    session.refresh(subscription)

    return _apply_subscription_activation(session, customer, subscription)
```

- [ ] **Step 2: Re-run the regression suite**

Run: `cd backend && pytest tests/test_billing_service_refactor.py -v`
Expected: all 6 still pass (the refactor must not change behavior).

- [ ] **Step 3: Smoke-check the wider billing test suite**

Run: `cd backend && pytest tests/ -v -k "billing or subscription or activate" --timeout=60`
Expected: no regressions.

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/billing_service.py
git commit -m "refactor(epic1): extract _apply_subscription_activation helper"
```

---

## Task 9: `activation_code_service.generate_codes`

**Files:**
- Create: `backend/app/services/activation_code_service.py`
- Create: `backend/tests/test_activation_code_service.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_activation_code_service.py`:

```python
"""ActivationCodeService — generate/redeem/revoke unit tests."""
import re
from datetime import datetime, timedelta

import pytest
from sqlmodel import select

from app.models.activation_code import (
    ActivationCode,
    CODE_UNUSED,
    CODE_REDEEMED,
    CODE_REVOKED,
)
from app.models.customer import Customer, STATUS_ACTIVE
from app.models.subscription import Subscription, SUB_ACTIVE
from app.services.activation_code_service import (
    ActivationCodeError,
    generate_codes,
    redeem_code,
    revoke_code,
)


# ── generate_codes ─────────────────────────────────────────────────────

def test_generate_codes_returns_requested_count(session):
    codes = generate_codes(session, admin_user_id=1, plan="starter", count=5)
    assert len(codes) == 5
    for c in codes:
        assert c.status == CODE_UNUSED
        assert c.plan == "starter"
        assert c.duration_days == 30
        assert re.fullmatch(r"[A-Z0-9]{12}", c.code), f"bad code format: {c.code}"


def test_generate_codes_assigns_same_batch_id(session):
    codes = generate_codes(session, admin_user_id=1, plan="growth", count=3)
    batch_ids = {c.batch_id for c in codes}
    assert len(batch_ids) == 1


def test_generate_codes_different_calls_get_different_batches(session):
    a = generate_codes(session, admin_user_id=1, plan="starter", count=2)
    b = generate_codes(session, admin_user_id=1, plan="starter", count=2)
    assert a[0].batch_id != b[0].batch_id


def test_generate_codes_rejects_invalid_plan(session):
    with pytest.raises(ActivationCodeError):
        generate_codes(session, admin_user_id=1, plan="freemium", count=1)


def test_generate_codes_persists_to_db(session):
    generate_codes(session, admin_user_id=1, plan="pro", count=4)
    rows = session.exec(select(ActivationCode).where(ActivationCode.plan == "pro")).all()
    assert len(rows) == 4


def test_generate_codes_codes_are_unique(session):
    codes = generate_codes(session, admin_user_id=1, plan="starter", count=20)
    seen = {c.code for c in codes}
    assert len(seen) == 20


def test_generate_codes_respects_duration_days(session):
    codes = generate_codes(session, admin_user_id=1, plan="starter", count=1, duration_days=90)
    assert codes[0].duration_days == 90
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_activation_code_service.py::test_generate_codes_returns_requested_count -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement `generate_codes`**

Create `backend/app/services/activation_code_service.py`:

```python
"""
ActivationCode service — generate / redeem / revoke.

Epic 1 — see docs/superpowers/plans/2026-05-22-epic1-levels-and-activation-codes.md
"""
from __future__ import annotations

import logging
import secrets
import string
import uuid
from datetime import datetime, timedelta
from typing import Optional

from sqlmodel import Session, select

from app.models.activation_code import (
    ActivationCode,
    CODE_UNUSED,
    CODE_REDEEMED,
    CODE_REVOKED,
)
from app.models.customer import PLAN_CODES, Customer
from app.models.subscription import (
    Subscription,
    SUB_PENDING,
)

logger = logging.getLogger(__name__)


class ActivationCodeError(Exception):
    """Validation / state errors. Mapped to 400/404/409 at the API layer."""


_CODE_ALPHABET = string.ascii_uppercase + string.digits  # 36 chars
_CODE_LENGTH = 12


def _generate_code_string() -> str:
    """12-char [A-Z0-9] random code. Caller checks DB collision."""
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))


def generate_codes(
    session: Session,
    admin_user_id: int,
    plan: str,
    count: int = 1,
    duration_days: int = 30,
    notes: Optional[str] = None,
) -> list[ActivationCode]:
    """Generate `count` unused codes for `plan`, all sharing one batch_id."""
    if plan not in PLAN_CODES:
        raise ActivationCodeError(f"Unknown plan: {plan}")
    if not (1 <= count <= 500):
        raise ActivationCodeError(f"count must be 1..500, got {count}")
    if not (1 <= duration_days <= 365):
        raise ActivationCodeError(f"duration_days must be 1..365, got {duration_days}")

    batch_id = uuid.uuid4().hex
    created: list[ActivationCode] = []

    for _ in range(count):
        # Retry on collision (vanishingly rare with 36^12 space)
        for _attempt in range(5):
            code_str = _generate_code_string()
            existing = session.exec(
                select(ActivationCode).where(ActivationCode.code == code_str)
            ).first()
            if not existing:
                break
        else:
            raise ActivationCodeError("Failed to generate unique code after 5 retries")

        ac = ActivationCode(
            code=code_str,
            plan=plan,
            duration_days=duration_days,
            batch_id=batch_id,
            status=CODE_UNUSED,
            created_by_admin_id=admin_user_id,
            notes=notes,
        )
        session.add(ac)
        created.append(ac)

    session.commit()
    for ac in created:
        session.refresh(ac)
    logger.info(
        "Generated %d activation codes for plan=%s batch=%s by admin=%d",
        count, plan, batch_id, admin_user_id,
    )
    return created


def redeem_code(session: Session, customer: Customer, code_str: str) -> Subscription:
    raise NotImplementedError("Implemented in Task 10")


def revoke_code(session: Session, code_id: int, admin_user_id: int) -> ActivationCode:
    raise NotImplementedError("Implemented in Task 11")
```

- [ ] **Step 4: Run tests**

Run: `cd backend && pytest tests/test_activation_code_service.py -v -k generate`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/activation_code_service.py backend/tests/test_activation_code_service.py
git commit -m "feat(epic1): activation_code_service.generate_codes"
```

---

## Task 10: `activation_code_service.redeem_code`

Reuses `_apply_subscription_activation` from Task 8. Creates a new Subscription with `activated_via='code'` then applies the shared activation pipeline.

**Files:**
- Modify: `backend/app/services/activation_code_service.py`
- Modify: `backend/tests/test_activation_code_service.py` (append redeem tests)

- [ ] **Step 1: Append the failing tests**

Append to `backend/tests/test_activation_code_service.py`:

```python
# ── redeem_code ────────────────────────────────────────────────────────

@pytest.fixture
def fresh_customer(session):
    c = Customer(
        email="redeem@t.t", password_hash="x", status="pending",
        plan=None, account_quota=0, group_quota=0, token_quota=0, seat_quota=0,
    )
    session.add(c); session.commit(); session.refresh(c)
    return c


def test_redeem_unused_code_creates_active_subscription(session, fresh_customer, monkeypatch):
    monkeypatch.setattr(
        "app.services.allocation_service.provision_customer",
        lambda s, c: None, raising=False,
    )
    [code] = generate_codes(session, admin_user_id=1, plan="growth", count=1)
    sub = redeem_code(session, fresh_customer, code.code)
    assert sub.status == SUB_ACTIVE
    assert sub.plan == "growth"
    assert sub.activated_via == "code"
    assert sub.activation_code_id == code.id


def test_redeem_marks_code_redeemed(session, fresh_customer, monkeypatch):
    monkeypatch.setattr(
        "app.services.allocation_service.provision_customer",
        lambda s, c: None, raising=False,
    )
    [code] = generate_codes(session, admin_user_id=1, plan="starter", count=1)
    redeem_code(session, fresh_customer, code.code)
    session.refresh(code)
    assert code.status == CODE_REDEEMED
    assert code.redeemed_by_customer_id == fresh_customer.id
    assert code.redeemed_subscription_id is not None
    assert code.redeemed_at is not None


def test_redeem_unknown_code_raises(session, fresh_customer):
    with pytest.raises(ActivationCodeError, match="not found"):
        redeem_code(session, fresh_customer, "NOTEXIST0001")


def test_redeem_already_redeemed_raises(session, fresh_customer, monkeypatch):
    monkeypatch.setattr(
        "app.services.allocation_service.provision_customer",
        lambda s, c: None, raising=False,
    )
    [code] = generate_codes(session, admin_user_id=1, plan="starter", count=1)
    redeem_code(session, fresh_customer, code.code)
    with pytest.raises(ActivationCodeError, match="already redeemed"):
        redeem_code(session, fresh_customer, code.code)


def test_redeem_revoked_code_raises(session, fresh_customer):
    [code] = generate_codes(session, admin_user_id=1, plan="starter", count=1)
    code.status = CODE_REVOKED
    session.add(code); session.commit()
    with pytest.raises(ActivationCodeError, match="revoked"):
        redeem_code(session, fresh_customer, code.code)


def test_redeem_case_insensitive_and_strips_dashes(session, fresh_customer, monkeypatch):
    monkeypatch.setattr(
        "app.services.allocation_service.provision_customer",
        lambda s, c: None, raising=False,
    )
    [code] = generate_codes(session, admin_user_id=1, plan="starter", count=1)
    # Convert to display form: "XXXX-XXXX-XXXX" with random casing
    formatted = f"{code.code[:4]}-{code.code[4:8]}-{code.code[8:]}".lower()
    sub = redeem_code(session, fresh_customer, formatted)
    assert sub.status == SUB_ACTIVE


def test_redeem_refreshes_customer_denormalized(session, fresh_customer, monkeypatch):
    monkeypatch.setattr(
        "app.services.allocation_service.provision_customer",
        lambda s, c: None, raising=False,
    )
    [code] = generate_codes(session, admin_user_id=1, plan="pro", count=1)
    redeem_code(session, fresh_customer, code.code)
    session.refresh(fresh_customer)
    assert fresh_customer.plan == "pro"
    assert fresh_customer.subscription_status == SUB_ACTIVE
    assert fresh_customer.status == STATUS_ACTIVE
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_activation_code_service.py -v -k redeem`
Expected: 7 fail with `NotImplementedError`.

- [ ] **Step 3: Implement `redeem_code`**

Replace the `redeem_code` stub in `backend/app/services/activation_code_service.py`:

```python
def redeem_code(session: Session, customer: Customer, code_str: str) -> Subscription:
    """Redeem a bearer activation code → create active Subscription.

    Normalization:
      - Strip dashes and whitespace
      - Uppercase
      - Must match ^[A-Z0-9]{12}$ after normalization

    Race-safety: row is fetched, status checked, status flipped + relations
    set, then committed. On SQLite single-writer there is no race. On
    Postgres, an UPDATE ... WHERE status='unused' guard could be added if
    we see contention (TODO comment, not implemented in this Epic).
    """
    from app.services.billing_service import _apply_subscription_activation, BillingError

    normalized = code_str.replace("-", "").replace(" ", "").upper()
    if len(normalized) != _CODE_LENGTH or not all(c in _CODE_ALPHABET for c in normalized):
        raise ActivationCodeError(f"Invalid code format")

    code = session.exec(
        select(ActivationCode).where(ActivationCode.code == normalized)
    ).first()
    if not code:
        raise ActivationCodeError("Code not found")
    if code.status == CODE_REDEEMED:
        raise ActivationCodeError("Code already redeemed")
    if code.status == CODE_REVOKED:
        raise ActivationCodeError("Code has been revoked")

    # Create Subscription tagged with activation provenance
    now = datetime.utcnow()
    sub = Subscription(
        customer_id=customer.id,
        plan=code.plan,
        status=SUB_PENDING,
        period_start=now,
        period_end=now + timedelta(days=code.duration_days),
        activated_via="code",
        activation_code_id=code.id,
    )
    session.add(sub)
    session.flush()  # need sub.id

    # Mark code redeemed BEFORE applying activation, so the helper's
    # commit-batch includes the code transition.
    code.status = CODE_REDEEMED
    code.redeemed_by_customer_id = customer.id
    code.redeemed_subscription_id = sub.id
    code.redeemed_at = now
    session.add(code)
    session.commit()
    session.refresh(sub)

    # Apply shared activation pipeline (cancel-priors, set-active,
    # refresh-customer, enable-features, provision_customer)
    return _apply_subscription_activation(session, customer, sub)
```

- [ ] **Step 4: Run tests**

Run: `cd backend && pytest tests/test_activation_code_service.py -v`
Expected: all 14 pass (7 generate + 7 redeem).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/activation_code_service.py backend/tests/test_activation_code_service.py
git commit -m "feat(epic1): redeem_code reuses _apply_subscription_activation"
```

---

## Task 11: `activation_code_service.revoke_code`

**Files:**
- Modify: `backend/app/services/activation_code_service.py`
- Modify: `backend/tests/test_activation_code_service.py` (append revoke tests)

- [ ] **Step 1: Append the failing tests**

Append to `backend/tests/test_activation_code_service.py`:

```python
# ── revoke_code ────────────────────────────────────────────────────────

def test_revoke_unused_code_succeeds(session):
    [code] = generate_codes(session, admin_user_id=1, plan="starter", count=1)
    result = revoke_code(session, code.id, admin_user_id=1)
    assert result.status == CODE_REVOKED


def test_revoke_unknown_code_raises(session):
    with pytest.raises(ActivationCodeError, match="not found"):
        revoke_code(session, code_id=999999, admin_user_id=1)


def test_revoke_already_redeemed_raises(session, fresh_customer, monkeypatch):
    monkeypatch.setattr(
        "app.services.allocation_service.provision_customer",
        lambda s, c: None, raising=False,
    )
    [code] = generate_codes(session, admin_user_id=1, plan="starter", count=1)
    redeem_code(session, fresh_customer, code.code)
    with pytest.raises(ActivationCodeError, match="already redeemed"):
        revoke_code(session, code.id, admin_user_id=1)


def test_revoke_already_revoked_is_idempotent(session):
    [code] = generate_codes(session, admin_user_id=1, plan="starter", count=1)
    revoke_code(session, code.id, admin_user_id=1)
    # Second revoke succeeds silently (idempotent)
    result = revoke_code(session, code.id, admin_user_id=1)
    assert result.status == CODE_REVOKED
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_activation_code_service.py -v -k revoke`
Expected: 4 fail with NotImplementedError.

- [ ] **Step 3: Implement `revoke_code`**

Replace the `revoke_code` stub:

```python
def revoke_code(session: Session, code_id: int, admin_user_id: int) -> ActivationCode:
    """Revoke an unused code. Idempotent on already-revoked codes.
    Rejects (409) if code is already redeemed (terminal state)."""
    code = session.get(ActivationCode, code_id)
    if not code:
        raise ActivationCodeError("Code not found")
    if code.status == CODE_REDEEMED:
        raise ActivationCodeError("Code already redeemed; cannot revoke")
    if code.status == CODE_REVOKED:
        return code  # idempotent
    code.status = CODE_REVOKED
    session.add(code)
    session.commit()
    session.refresh(code)
    logger.info("Revoked code %s by admin=%d", code.code, admin_user_id)
    return code
```

- [ ] **Step 4: Run all activation_code_service tests**

Run: `cd backend && pytest tests/test_activation_code_service.py -v`
Expected: 18 passed (7 generate + 7 redeem + 4 revoke).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/activation_code_service.py backend/tests/test_activation_code_service.py
git commit -m "feat(epic1): revoke_code"
```

---

## Task 12: Admin endpoints — generate / list / revoke / detail

**Files:**
- Modify: `backend/app/api/v1/endpoints/admin_billing.py`
- Create: `backend/tests/test_admin_activation_codes_api.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_admin_activation_codes_api.py`:

```python
"""Admin activation code API endpoints."""
import pytest
from sqlmodel import select

from app.models.activation_code import ActivationCode, CODE_UNUSED, CODE_REVOKED


@pytest.fixture
def admin_token(session):
    from app.core.security import create_access_token
    from app.models.user import User
    u = User(username="admin", password_hash="x", is_superuser=True)
    session.add(u); session.commit(); session.refresh(u)
    return create_access_token({"sub": u.username, "type": "user", "user_id": u.id})


@pytest.fixture
def admin_client(client, admin_token):
    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    return client


def test_generate_codes_endpoint(admin_client, session):
    resp = admin_client.post(
        "/api/v1/admin/billing/activation-codes/generate",
        json={"plan": "starter", "count": 5, "duration_days": 30, "notes": "test batch"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "batch_id" in body
    assert len(body["codes"]) == 5
    for c in body["codes"]:
        assert c["plan"] == "starter"
        assert c["status"] == "unused"
        assert len(c["code"]) == 12


def test_generate_codes_invalid_plan_returns_400(admin_client):
    resp = admin_client.post(
        "/api/v1/admin/billing/activation-codes/generate",
        json={"plan": "freemium", "count": 1},
    )
    assert resp.status_code == 400


def test_generate_codes_invalid_count_returns_422(admin_client):
    resp = admin_client.post(
        "/api/v1/admin/billing/activation-codes/generate",
        json={"plan": "starter", "count": 1000},  # > max 500
    )
    assert resp.status_code in (400, 422)


def test_list_codes(admin_client, session):
    # Seed some codes directly
    from app.services.activation_code_service import generate_codes
    generate_codes(session, admin_user_id=1, plan="starter", count=3)
    generate_codes(session, admin_user_id=1, plan="growth", count=2)

    resp = admin_client.get("/api/v1/admin/billing/activation-codes")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body, list) or "items" in body
    items = body if isinstance(body, list) else body["items"]
    assert len(items) >= 5


def test_list_codes_filter_by_plan(admin_client, session):
    from app.services.activation_code_service import generate_codes
    generate_codes(session, admin_user_id=1, plan="starter", count=2)
    generate_codes(session, admin_user_id=1, plan="growth", count=3)
    resp = admin_client.get("/api/v1/admin/billing/activation-codes?plan=growth")
    assert resp.status_code == 200
    items = resp.json() if isinstance(resp.json(), list) else resp.json()["items"]
    assert all(c["plan"] == "growth" for c in items)


def test_get_code_detail(admin_client, session):
    from app.services.activation_code_service import generate_codes
    [code] = generate_codes(session, admin_user_id=1, plan="pro", count=1)
    resp = admin_client.get(f"/api/v1/admin/billing/activation-codes/{code.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == code.id
    assert body["code"] == code.code


def test_revoke_code_endpoint(admin_client, session):
    from app.services.activation_code_service import generate_codes
    [code] = generate_codes(session, admin_user_id=1, plan="starter", count=1)
    resp = admin_client.post(f"/api/v1/admin/billing/activation-codes/{code.id}/revoke")
    assert resp.status_code == 200
    session.refresh(code)
    assert code.status == CODE_REVOKED
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_admin_activation_codes_api.py -v`
Expected: 404 on all endpoints (not yet registered).

- [ ] **Step 3: Implement the endpoints**

Append to [backend/app/api/v1/endpoints/admin_billing.py](backend/app/api/v1/endpoints/admin_billing.py) (assumes the file already has `router = APIRouter(...)` and admin auth dependency named `get_current_user_admin` or similar; inspect the file for the exact dep name):

```python
# ── Epic 1 — Activation codes ─────────────────────────────────────────
from app.models.activation_code import (
    ActivationCode,
    ActivationCodeGenerateRequest,
    ActivationCodeGenerateResponse,
    ActivationCodeRead,
)
from app.services.activation_code_service import (
    ActivationCodeError,
    generate_codes as ac_generate,
    revoke_code as ac_revoke,
)


@router.post(
    "/billing/activation-codes/generate",
    response_model=ActivationCodeGenerateResponse,
)
def admin_generate_activation_codes(
    request: ActivationCodeGenerateRequest,
    session: Session = Depends(get_session),
    admin = Depends(get_current_admin_user),  # adjust to actual dep name
):
    try:
        codes = ac_generate(
            session,
            admin_user_id=admin.id,
            plan=request.plan,
            count=request.count,
            duration_days=request.duration_days,
            notes=request.notes,
        )
    except ActivationCodeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ActivationCodeGenerateResponse(
        batch_id=codes[0].batch_id,
        codes=[ActivationCodeRead.model_validate(c) for c in codes],
    )


@router.get(
    "/billing/activation-codes",
    response_model=list[ActivationCodeRead],
)
def admin_list_activation_codes(
    status: Optional[str] = Query(None),
    plan: Optional[str] = Query(None),
    batch_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    admin = Depends(get_current_admin_user),
):
    stmt = select(ActivationCode)
    if status:
        stmt = stmt.where(ActivationCode.status == status)
    if plan:
        stmt = stmt.where(ActivationCode.plan == plan)
    if batch_id:
        stmt = stmt.where(ActivationCode.batch_id == batch_id)
    stmt = stmt.order_by(ActivationCode.created_at.desc()).offset(offset).limit(limit)
    rows = session.exec(stmt).all()
    return [ActivationCodeRead.model_validate(r) for r in rows]


@router.get(
    "/billing/activation-codes/{code_id}",
    response_model=ActivationCodeRead,
)
def admin_get_activation_code(
    code_id: int,
    session: Session = Depends(get_session),
    admin = Depends(get_current_admin_user),
):
    code = session.get(ActivationCode, code_id)
    if not code:
        raise HTTPException(status_code=404, detail="Code not found")
    return ActivationCodeRead.model_validate(code)


@router.post(
    "/billing/activation-codes/{code_id}/revoke",
    response_model=ActivationCodeRead,
)
def admin_revoke_activation_code(
    code_id: int,
    session: Session = Depends(get_session),
    admin = Depends(get_current_admin_user),
):
    try:
        code = ac_revoke(session, code_id, admin_user_id=admin.id)
    except ActivationCodeError as e:
        msg = str(e)
        if "not found" in msg.lower():
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=409, detail=msg)
    return ActivationCodeRead.model_validate(code)
```

**Important**: The actual dependency name for admin auth might be different (`require_admin`, `get_current_user`, etc.). Inspect [backend/app/api/v1/endpoints/admin_billing.py](backend/app/api/v1/endpoints/admin_billing.py) top imports to find the exact name and use it consistently.

- [ ] **Step 4: Run tests**

Run: `cd backend && pytest tests/test_admin_activation_codes_api.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v1/endpoints/admin_billing.py backend/tests/test_admin_activation_codes_api.py
git commit -m "feat(epic1): admin endpoints for activation codes"
```

---

## Task 13: Customer endpoint — `POST /customer/redeem-code`

**Files:**
- Modify: `backend/app/api/v1/endpoints/customer_billing.py`
- Create: `backend/tests/test_customer_redeem_api.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_customer_redeem_api.py`:

```python
"""Customer-facing redeem-code endpoint."""
import pytest
from sqlmodel import select

from app.models.activation_code import CODE_REDEEMED
from app.models.subscription import Subscription, SUB_ACTIVE


@pytest.fixture
def customer_token(session):
    from app.core.security import create_access_token
    from app.models.customer import Customer
    c = Customer(
        email="cust@t.t", password_hash="x", status="pending",
        plan=None, account_quota=0, group_quota=0, token_quota=0, seat_quota=0,
    )
    session.add(c); session.commit(); session.refresh(c)
    return create_access_token({"type": "customer", "customer_id": c.id}), c


@pytest.fixture
def customer_client(client, customer_token):
    token, _ = customer_token
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


def test_redeem_endpoint_creates_active_subscription(
    customer_client, session, customer_token, monkeypatch,
):
    monkeypatch.setattr(
        "app.services.allocation_service.provision_customer",
        lambda s, c: None, raising=False,
    )
    _, customer = customer_token
    from app.services.activation_code_service import generate_codes
    [code] = generate_codes(session, admin_user_id=1, plan="growth", count=1)

    resp = customer_client.post(
        "/api/v1/customer/redeem-code",
        json={"code": code.code},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "active"
    assert body["plan"] == "growth"
    assert body["activated_via"] == "code"


def test_redeem_endpoint_unknown_code_returns_404(customer_client):
    resp = customer_client.post(
        "/api/v1/customer/redeem-code",
        json={"code": "NOTEXIST0001"},
    )
    assert resp.status_code == 404


def test_redeem_endpoint_already_used_returns_409(
    customer_client, session, customer_token, monkeypatch,
):
    monkeypatch.setattr(
        "app.services.allocation_service.provision_customer",
        lambda s, c: None, raising=False,
    )
    from app.services.activation_code_service import generate_codes
    [code] = generate_codes(session, admin_user_id=1, plan="starter", count=1)
    customer_client.post("/api/v1/customer/redeem-code", json={"code": code.code})
    resp = customer_client.post("/api/v1/customer/redeem-code", json={"code": code.code})
    assert resp.status_code == 409


def test_redeem_endpoint_invalid_format_returns_400(customer_client):
    resp = customer_client.post(
        "/api/v1/customer/redeem-code",
        json={"code": "tooshort"},
    )
    assert resp.status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_customer_redeem_api.py -v`
Expected: 404 on the endpoint URL.

- [ ] **Step 3: Implement the endpoint**

Append to [backend/app/api/v1/endpoints/customer_billing.py](backend/app/api/v1/endpoints/customer_billing.py). Inspect the file's existing imports and dependency for `get_current_customer` (or whatever the customer auth dep is called) and use the same.

```python
from app.models.activation_code import ActivationCodeRedeemRequest
from app.models.subscription import SubscriptionRead
from app.services.activation_code_service import (
    ActivationCodeError,
    redeem_code,
)


@router.post("/redeem-code", response_model=SubscriptionRead)
def customer_redeem_code(
    request: ActivationCodeRedeemRequest,
    session: Session = Depends(get_session),
    customer = Depends(get_current_customer),  # adjust to actual dep
):
    try:
        sub = redeem_code(session, customer, request.code)
    except ActivationCodeError as e:
        msg = str(e)
        if "not found" in msg.lower():
            raise HTTPException(status_code=404, detail=msg)
        if "already redeemed" in msg.lower() or "revoked" in msg.lower():
            raise HTTPException(status_code=409, detail=msg)
        raise HTTPException(status_code=400, detail=msg)
    return SubscriptionRead.model_validate(sub)
```

- [ ] **Step 4: Run tests**

Run: `cd backend && pytest tests/test_customer_redeem_api.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v1/endpoints/customer_billing.py backend/tests/test_customer_redeem_api.py
git commit -m "feat(epic1): POST /customer/redeem-code"
```

---

## Task 14: Frontend — admin ActivationCodes page + portal redeem card

**Files:**
- Create: `frontend/src/pages/billing/ActivationCodes.tsx`
- Modify: `frontend/src/portal/pages/Billing.tsx`

- [ ] **Step 1: Create admin ActivationCodes page**

Create `frontend/src/pages/billing/ActivationCodes.tsx`:

```tsx
import React, { useState, useEffect } from "react";
import {
  Table, Button, Modal, Form, Input, InputNumber, Select,
  Tag, message, Space, Popconfirm, Card, Typography,
} from "antd";
import { api } from "../../lib/api"; // adjust to project's actual api util import path

const { Title } = Typography;

interface ActivationCode {
  id: number;
  code: string;
  plan: string;
  duration_days: number;
  batch_id: string;
  status: "unused" | "redeemed" | "revoked";
  redeemed_by_customer_id: number | null;
  created_at: string;
  redeemed_at: string | null;
  notes: string | null;
}

const STATUS_COLOR: Record<string, string> = {
  unused: "blue",
  redeemed: "green",
  revoked: "red",
};

export const ActivationCodes: React.FC = () => {
  const [codes, setCodes] = useState<ActivationCode[]>([]);
  const [loading, setLoading] = useState(false);
  const [filterStatus, setFilterStatus] = useState<string | undefined>();
  const [filterPlan, setFilterPlan] = useState<string | undefined>();
  const [genModalOpen, setGenModalOpen] = useState(false);
  const [genForm] = Form.useForm();

  const fetchCodes = async () => {
    setLoading(true);
    const params: any = {};
    if (filterStatus) params.status = filterStatus;
    if (filterPlan) params.plan = filterPlan;
    const resp = await api.get("/admin/billing/activation-codes", { params });
    setCodes(resp.data);
    setLoading(false);
  };

  useEffect(() => { fetchCodes(); }, [filterStatus, filterPlan]);

  const handleGenerate = async (values: any) => {
    try {
      const resp = await api.post("/admin/billing/activation-codes/generate", values);
      message.success(`已生成 ${resp.data.codes.length} 个激活码，批次 ${resp.data.batch_id}`);
      setGenModalOpen(false);
      genForm.resetFields();
      fetchCodes();
    } catch (err: any) {
      message.error(err.response?.data?.detail || "生成失败");
    }
  };

  const handleRevoke = async (id: number) => {
    try {
      await api.post(`/admin/billing/activation-codes/${id}/revoke`);
      message.success("已撤销");
      fetchCodes();
    } catch (err: any) {
      message.error(err.response?.data?.detail || "撤销失败");
    }
  };

  const columns = [
    {
      title: "激活码",
      dataIndex: "code",
      key: "code",
      render: (v: string) =>
        <code style={{ fontFamily: "monospace" }}>
          {`${v.slice(0,4)}-${v.slice(4,8)}-${v.slice(8)}`}
        </code>,
    },
    {
      title: "套餐", dataIndex: "plan", key: "plan",
      render: (v: string) => <Tag>{v}</Tag>,
    },
    { title: "有效期(天)", dataIndex: "duration_days", key: "duration_days" },
    {
      title: "状态", dataIndex: "status", key: "status",
      render: (v: string) =>
        <Tag color={STATUS_COLOR[v] || "default"}>{v}</Tag>,
    },
    { title: "批次", dataIndex: "batch_id", key: "batch_id",
      render: (v: string) => <code>{v.slice(0,8)}</code> },
    { title: "已兑换客户", dataIndex: "redeemed_by_customer_id", key: "redeemed_by_customer_id" },
    { title: "创建时间", dataIndex: "created_at", key: "created_at" },
    { title: "备注", dataIndex: "notes", key: "notes" },
    {
      title: "操作", key: "action",
      render: (_: any, record: ActivationCode) =>
        record.status === "unused" ? (
          <Popconfirm
            title="确定撤销？"
            onConfirm={() => handleRevoke(record.id)}
          >
            <Button type="link" danger>撤销</Button>
          </Popconfirm>
        ) : null,
    },
  ];

  return (
    <Card>
      <Space style={{ marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>激活码管理</Title>
        <Select
          placeholder="状态筛选"
          allowClear
          style={{ width: 120 }}
          onChange={setFilterStatus}
          options={[
            { value: "unused", label: "未兑换" },
            { value: "redeemed", label: "已兑换" },
            { value: "revoked", label: "已撤销" },
          ]}
        />
        <Select
          placeholder="套餐筛选"
          allowClear
          style={{ width: 120 }}
          onChange={setFilterPlan}
          options={[
            { value: "starter", label: "Starter" },
            { value: "growth", label: "Growth" },
            { value: "pro", label: "Pro" },
          ]}
        />
        <Button type="primary" onClick={() => setGenModalOpen(true)}>
          批量生成
        </Button>
      </Space>

      <Table
        dataSource={codes}
        columns={columns}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 20 }}
      />

      <Modal
        title="批量生成激活码"
        open={genModalOpen}
        onCancel={() => setGenModalOpen(false)}
        onOk={() => genForm.submit()}
      >
        <Form form={genForm} onFinish={handleGenerate} layout="vertical">
          <Form.Item name="plan" label="套餐" rules={[{ required: true }]}>
            <Select options={[
              { value: "starter", label: "Starter" },
              { value: "growth", label: "Growth" },
              { value: "pro", label: "Pro" },
            ]} />
          </Form.Item>
          <Form.Item
            name="count" label="数量" initialValue={10}
            rules={[{ required: true, type: "number", min: 1, max: 500 }]}
          >
            <InputNumber min={1} max={500} />
          </Form.Item>
          <Form.Item name="duration_days" label="有效期(天)" initialValue={30}>
            <InputNumber min={1} max={365} />
          </Form.Item>
          <Form.Item name="notes" label="备注">
            <Input placeholder="可选" />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
};

export default ActivationCodes;
```

- [ ] **Step 2: Add the route**

Find the admin router file (likely `frontend/src/App.tsx` or a routes file). Add:

```tsx
import ActivationCodes from "./pages/billing/ActivationCodes";

// inside the admin routes block:
<Route path="/admin/billing/activation-codes" element={<ActivationCodes />} />
```

Also add a sidebar/menu entry (if there's a menu config file like `frontend/src/menu.ts`).

- [ ] **Step 3: Add redeem card to portal Billing page**

In [frontend/src/portal/pages/Billing.tsx](frontend/src/portal/pages/Billing.tsx), add a new Card section above or beside the existing subscription info:

```tsx
import { Card, Input, Button, message } from "antd";
import { portalApi } from "../api"; // or wherever the portal axios instance lives

// ... inside the component:
const [redeemCode, setRedeemCode] = useState("");

const handleRedeem = async () => {
  if (!redeemCode.trim()) return;
  try {
    const resp = await portalApi.post("/customer/redeem-code", {
      code: redeemCode.trim(),
    });
    message.success(`激活成功，套餐：${resp.data.plan}`);
    setRedeemCode("");
    refetchSubscription(); // refresh the displayed sub
  } catch (err: any) {
    const status = err.response?.status;
    const detail = err.response?.data?.detail;
    if (status === 404) message.error("激活码不存在");
    else if (status === 409) message.error(detail || "激活码已使用或已撤销");
    else message.error(detail || "兑换失败");
  }
};

// ... in the JSX:
<Card title="激活码兑换" style={{ marginBottom: 16 }}>
  <Input.Group compact>
    <Input
      style={{ width: "calc(100% - 100px)" }}
      placeholder="输入激活码，例如 XXXX-XXXX-XXXX"
      value={redeemCode}
      onChange={(e) => setRedeemCode(e.target.value)}
      onPressEnter={handleRedeem}
    />
    <Button type="primary" onClick={handleRedeem}>兑换</Button>
  </Input.Group>
</Card>
```

- [ ] **Step 4: Smoke-test in browser**

Run: `cd /var/tgsc && docker compose up -d frontend && docker compose restart backend`

Then:
1. Log into admin at `https://your-host/admin` → 侧栏 → 激活码 → 生成 5 个 starter → 看列表出现 5 行 unused
2. 复制一个 code
3. 登出 → 登入 portal as a customer (pending plan) → Billing 页面 → 兑换框输入 code → 看到"激活成功"
4. 回 admin 激活码列表 → 那行变 redeemed + 显示客户 id

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/billing/ActivationCodes.tsx frontend/src/portal/pages/Billing.tsx
# Plus any route/menu file edits:
git add frontend/src/App.tsx  # or routes/menu file
git commit -m "feat(epic1): admin ActivationCodes page + portal redeem card"
```

---

## Done Criteria

- [ ] All test files pass: `cd backend && pytest tests/test_account_roles_usage_level.py tests/test_account_read_usage_level.py tests/test_import_endpoints_usage_level.py tests/test_billing_service_refactor.py tests/test_activation_code_service.py tests/test_admin_activation_codes_api.py tests/test_customer_redeem_api.py -v` shows **all passed** with no skips.
- [ ] `cd backend && pytest tests/ -v --timeout=120` shows no new regressions vs main.
- [ ] `docker compose exec backend alembic upgrade head` completes cleanly; downgrade -1 + upgrade head also works.
- [ ] Admin imports a TG account via Mega URL with `usage_level=2` → DB row has `role='listener'`; AccountRead returns `usage_level=2`.
- [ ] Admin generates 10 starter codes → portal customer redeems one → Subscription is `active`, customer's `plan=starter`, code is `redeemed`, `subscription.activated_via='code'`, `subscription.activation_code_id` points to the code.
- [ ] Admin revokes an unused code → status becomes `revoked`. Attempting to redeem it returns 409.
- [ ] **USDT activate_invoice path unchanged**: pre-existing customer billing flow still works (verified by the regression suite in Task 7 still passing after Task 8 refactor).
