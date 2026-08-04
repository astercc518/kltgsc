# Phase 0 Stabilization Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Produce a reproducible release candidate that fails closed in production, confines platform administration to admins, settles wallet payments atomically, and passes automated backend, frontend, Landing, Compose, migration, and secret-hygiene gates.

**Architecture:** Keep the three existing identity surfaces (`User`, `Customer`, and `SalesContext`) separate and make authorization explicit at router boundaries. Put wallet-invoice settlement behind one transaction-owning service. Make environment mode the switch for production-only validation and startup behavior. Treat Alembic and locked package manifests as release inputs, then enforce them in CI and a local preflight script.

**Tech Stack:** Python 3.10, FastAPI, SQLModel/SQLAlchemy, Alembic, PostgreSQL/pgvector, Redis, Pytest, React 18, TypeScript, Vite, Vitest, Docker Compose, Nginx, GitHub Actions.

---

## Verified baseline

- Branch: `codex/phase0-stabilization`, based on `release/merge-main-into-safety` at `80e7d06`.
- Backend: `pytest --collect-only -q` finds 220 automated tests but also imports four root-level manual/network scripts and exits with four collection errors.
- Business frontend: `npm run typecheck` exits 2 with unused imports plus real API/type mismatches in Inbox, Marketing, Scraping, Script, Warmup, and AccountUploader.
- Landing: `npm run build` succeeds and emits `landing/dist`.
- Group AI Phase 1-12 remains outside this branch.

## Task 1: Make backend test discovery deterministic

**Files:**

- Create: `backend/pytest.ini`
- Create: `backend/tests/test_test_layout.py`

**Step 1: Write the failing test**

Add a repository-layout test that reads `backend/pytest.ini` and requires `testpaths = tests` plus `python_files = test_*.py`. This prevents the manual scripts in `backend/` from silently re-entering CI collection.

```python
from pathlib import Path


def test_pytest_collects_only_automated_test_directory() -> None:
    config = (Path(__file__).parents[1] / "pytest.ini").read_text()
    assert "testpaths = tests" in config
    assert "python_files = test_*.py" in config
```

**Step 2: Run the test to verify it fails**

Run: `cd backend && pytest tests/test_test_layout.py -q`

Expected: FAIL because `backend/pytest.ini` does not exist.

**Step 3: Add the minimal pytest configuration**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
addopts = --strict-markers
```

**Step 4: Verify collection**

Run: `cd backend && pytest tests/test_test_layout.py -q && pytest --collect-only -q`

Expected: layout test PASS; collection reports 220 automated tests and no root-script errors.

**Step 5: Commit**

```bash
git add backend/pytest.ini backend/tests/test_test_layout.py
git commit -m "test: isolate automated backend suite"
```

## Task 2: Fail closed on production configuration and startup

**Files:**

- Modify: `backend/app/core/config.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_config_environment.py`
- Create: `backend/tests/test_app_startup_policy.py`
- Create: `backend/.env.example`

**Step 1: Write failing settings tests**

Instantiate `Settings(_env_file=None, ...)` directly and cover:

- `ENVIRONMENT` accepts only `development`, `test`, or `production`.
- Production rejects absent/short `SECRET_KEY` and `SESSION_ENCRYPTION_KEY`.
- Production rejects absent, short, or known-default `ADMIN_PASSWORD`.
- Production requires a PostgreSQL `DATABASE_URL`.
- Production requires non-empty `REDIS_URL`; when `COMPOSE_DEPLOYMENT=true`, the URL must include a password.
- Development generates missing secrets without writing the generated values to stdout/stderr.
- Test mode remains deterministic when explicit test values are supplied.

Use a helper that supplies valid production defaults and overrides one field per test:

```python
def production_settings(**overrides: object) -> Settings:
    values = {
        "ENVIRONMENT": "production",
        "SECRET_KEY": "s" * 32,
        "SESSION_ENCRYPTION_KEY": "e" * 32,
        "ADMIN_PASSWORD": "StrongAdminPassword1",
        "DATABASE_URL": "postgresql://tgsc:password@db/tgsc",
        "REDIS_URL": "redis://:password@redis:6379/0",
        "COMPOSE_DEPLOYMENT": True,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)
```

**Step 2: Verify red**

Run: `cd backend && pytest tests/test_config_environment.py tests/test_app_startup_policy.py -q`

Expected: FAIL because environment fields and startup-policy helpers do not exist.

**Step 3: Implement settings validation**

In `config.py`:

- Add `Environment(str, Enum)` with the three allowed values.
- Add `ENVIRONMENT`, `COMPOSE_DEPLOYMENT`, and `LLM_SAFETY_WARMUP` settings.
- Replace printing validators with a single `model_validator(mode="after")`.
- Generate ephemeral development/test secrets with `secrets.token_hex(32)` without logging values.
- Raise `ValueError` for every invalid production requirement.
- Parse `REDIS_URL` with `urllib.parse.urlparse`; require `parsed.password` for Compose production.
- Keep `settings = Settings()` so every process validates on import.

In `main.py`, extract startup decisions into testable helpers:

```python
def should_create_tables() -> bool:
    return settings.ENVIRONMENT != Environment.PRODUCTION


def should_warmup_moderator() -> bool:
    return settings.LLM_SAFETY_WARMUP
```

Call `init_tables()` only when `should_create_tables()` is true, and skip model warmup when the setting is false. Configuration import/validation remains before DB seeding or model warmup.

**Step 4: Add a complete non-secret example**

`backend/.env.example` documents all required runtime variables using non-usable placeholders, including `ENVIRONMENT=production`, `COMPOSE_DEPLOYMENT=true`, PostgreSQL/Redis URLs, app keys, payment keys, LLM keys, and Telegram settings. It must not contain a value accepted as a real secret.

**Step 5: Verify green**

Run: `cd backend && pytest tests/test_config_environment.py tests/test_app_startup_policy.py -q`

Expected: PASS.

**Step 6: Commit**

```bash
git add backend/app/core/config.py backend/app/main.py backend/tests/test_config_environment.py backend/tests/test_app_startup_policy.py backend/.env.example
git commit -m "fix: enforce production configuration policy"
```

## Task 3: Enforce the platform-admin boundary and redact configuration

**Files:**

- Modify: `backend/app/api/v1/__init__.py`
- Modify: `backend/app/api/deps.py`
- Modify: `backend/app/api/v1/endpoints/users.py`
- Modify: `backend/app/api/v1/endpoints/system.py`
- Modify: `backend/app/models/system_config.py`
- Modify: `backend/app/models/token.py`
- Modify: `backend/conftest.py`
- Create: `backend/tests/test_admin_authorization_boundary.py`
- Create: `backend/tests/test_system_config_redaction.py`

**Step 1: Write failing authorization tests**

Inspect router route dependencies rather than booting the whole application. Assert each legacy management prefix uses `get_current_admin`, while `/users/me` and `/users/change-password` retain `get_current_user`. Add endpoint dependency tests showing a sales `User` receives 403 and an admin succeeds.

The admin-only list is:

```python
ADMIN_PREFIXES = {
    "/accounts", "/proxies", "/registration", "/system", "/tasks",
    "/scraping", "/marketing", "/warmup", "/ai", "/scripts", "/crm",
    "/logs", "/monitors", "/invites", "/campaigns", "/source-groups",
    "/funnel-groups", "/personas", "/knowledge-bases", "/workflow",
    "/monitoring",
}
```

**Step 2: Write failing redaction tests**

Seed `SystemConfig` rows named `NOWPAYMENTS_IPN_SECRET`, `OPENAI_API_KEY`, and a non-sensitive `DEFAULT_TIMEZONE`. Assert list/detail reads return:

```json
{"key":"OPENAI_API_KEY","value":null,"is_sensitive":true,"is_configured":true}
```

and preserve the non-sensitive value. Sensitive detection must be case-insensitive and match names containing `SECRET`, `PASSWORD`, `TOKEN`, `API_KEY`, `PRIVATE_KEY`, or `ENCRYPTION_KEY`.

**Step 3: Verify red**

Run: `cd backend && pytest tests/test_admin_authorization_boundary.py tests/test_system_config_redaction.py -q`

Expected: FAIL because the current legacy dependency accepts every authenticated `User` and config reads expose raw values.

**Step 4: Implement router boundaries**

- Replace the shared `auth_deps` with `admin_deps = [Depends(get_current_admin)]` for the management routers.
- Extend `TokenPayload` with the optional `type` claim and make the platform
  dependency accept only a legacy missing type or `access`; reject `customer`
  and `customer_sales` before resolving a `User`.
- Keep customer/sales/admin-specific routers on their existing dependencies.
- Do not put a router-wide admin dependency on `users.router`; instead change `read_users` to `Depends(get_current_admin)` and keep self-service endpoints authenticated.
- Ensure `/users` create/update/delete/reset routes remain admin-only.

**Step 5: Implement redacted response models**

Add a non-table `SystemConfigRead` model and a `redact_system_config(config)` helper. Use `SystemConfigRead` for GET responses; write responses also use the redacted model so a secret cannot echo back after mutation.

**Step 6: Verify green**

Run: `cd backend && pytest tests/test_admin_authorization_boundary.py tests/test_system_config_redaction.py -q`

Expected: PASS.

**Step 7: Commit**

```bash
git add backend/app/api/v1/__init__.py backend/app/api/deps.py backend/app/api/v1/endpoints/users.py backend/app/api/v1/endpoints/system.py backend/app/models/system_config.py backend/app/models/token.py backend/conftest.py backend/tests/test_admin_authorization_boundary.py backend/tests/test_system_config_redaction.py
git commit -m "fix: restrict management API to admins"
```

## Task 4: Authenticate the global WebSocket as an admin channel

**Files:**

- Modify: `backend/app/api/v1/endpoints/ws.py`
- Create: `backend/tests/test_websocket_auth.py`

**Step 1: Write failing handshake tests**

Test a pure helper `authenticate_websocket_admin(token, session)` and assert rejection for:

- missing or malformed JWT;
- expired JWT;
- token types `customer`, `customer_sales`, or any non-platform type;
- revoked `jti`;
- missing or inactive user;
- active platform-sales user.

Assert an active admin/superuser is returned. Patch `is_token_revoked` at the module boundary. Add one TestClient handshake test that sends `ping` and receives `pong`, with moderation warmup disabled.

**Step 2: Verify red**

Run: `cd backend && pytest tests/test_websocket_auth.py -q`

Expected: FAIL because the helper does not exist and the endpoint only checks `sub`.

**Step 3: Implement before-accept authentication**

- Inject `Session` into the WebSocket endpoint with `Depends(get_session)`.
- Decode with the configured algorithm and validate through `TokenPayload`.
- Accept only missing/`access` token type used by the platform login; explicitly reject customer token types.
- Require non-empty, unrevoked `jti`, an active `User`, and admin/superuser capability.
- Close with 4001 for missing credentials, 4003 for invalid/revoked credentials, and 4004 for insufficient capability; never call `manager.connect()` before authentication succeeds.
- Log user identifiers and rejection class, never the token.

**Step 4: Verify green**

Run: `cd backend && pytest tests/test_websocket_auth.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/api/v1/endpoints/ws.py backend/tests/test_websocket_auth.py
git commit -m "fix: confine global websocket to admins"
```

## Task 5: Settle wallet invoices in one transaction

**Files:**

- Create: `backend/app/services/payment_settlement.py`
- Modify: `backend/app/api/v1/endpoints/webhooks.py`
- Modify: `backend/app/services/wallet_service.py`
- Modify: `backend/app/services/sales_wallet_service.py`
- Create: `backend/tests/test_payment_settlement.py`

**Step 1: Write failing transaction tests**

Using an in-memory SQLite engine with foreign keys enabled, create customer and customer-sales invoices. Cover:

- injected failure after wallet mutation rolls back invoice status, wallet balance, and transaction row;
- retry after failure creates exactly one credit and marks the invoice paid;
- replay returns the original transaction without a second credit;
- both customer-wallet and sales-wallet routes have the same guarantees;
- a paid invoice with no matching transaction raises an invariant error rather than reporting success.

Save the real bound `session.commit`, temporarily replace that one method with
a function that raises `RuntimeError`, call settlement, then restore the real
method before inspecting and retrying. This exercises real SQLModel mutations
and rollback while keeping test-only hooks out of production services.

**Step 2: Verify red**

Run: `cd backend && pytest tests/test_payment_settlement.py -q`

Expected: FAIL because the settlement service does not exist.

**Step 3: Make wallet primitives transaction-neutral**

Add `commit: bool = True` to `get_or_create_wallet` and both invoice-credit helpers, preserving existing callers. When `commit=False`, use `session.flush()` instead of `commit()` and do not refresh until the owning service commits. Do not change direct-credit/charge semantics in this task.

**Step 4: Implement the transaction owner**

`settle_wallet_invoice` must:

1. select `Invoice.id == invoice_id` with `with_for_update()`;
2. select the expected transaction by invoice-derived idempotency key;
3. return it only when the invoice is already paid;
4. reject non-pending status or a paid invoice missing its transaction;
5. mark paid and set hash/time in memory;
6. call the correct credit helper with `commit=False`;
7. `session.commit()` once and refresh the transaction;
8. on every exception, call `session.rollback()` and re-raise.

**Step 5: Route the webhook through settlement**

Remove the pre-credit invoice commit and both direct credit calls from `webhooks.py`. For wallet plans call the settlement service by invoice id. Let duplicate successful notifications return the original receipt. Convert domain errors to HTTP 400 and unexpected DB errors to a retryable HTTP 503 after rollback.

**Step 6: Verify green and subscription regression**

Run: `cd backend && pytest tests/test_payment_settlement.py tests/test_billing_service_refactor.py -q`

Expected: PASS.

**Step 7: Commit**

```bash
git add backend/app/services/payment_settlement.py backend/app/api/v1/endpoints/webhooks.py backend/app/services/wallet_service.py backend/app/services/sales_wallet_service.py backend/tests/test_payment_settlement.py
git commit -m "fix: settle wallet payments atomically"
```

## Task 6: Make Compose, Alembic, and Landing release inputs reproducible

**Files:**

- Modify: `docker-compose.prod.yml`
- Modify: `docker-compose.yml`
- Modify: `nginx.conf`
- Modify: `.env.example`
- Create: `scripts/release_preflight.sh`
- Create: `backend/tests/test_release_contract.py`

**Step 1: Write failing static release-contract tests**

Read repository files and assert:

- every backend/worker/beat/listener service in production Compose has `env_file: ./backend/.env`;
- production service overrides set PostgreSQL, authenticated Redis, and shard-specific values without blank secret interpolation;
- backend command runs `alembic upgrade head` before Gunicorn;
- Nginx mounts `./landing/dist:/usr/share/nginx/landing:ro`;
- the tracked migration `backend/alembic/versions/41f948211e5f_*.py` and `frontend/src/lib/queryClient.ts` exist;
- the preflight checks Landing assets and exactly one Alembic head.

**Step 2: Verify red**

Run: `cd backend && pytest tests/test_release_contract.py -q`

Expected: FAIL because shared env files, Landing mount, and preflight are missing.

**Step 3: Implement Compose and Nginx wiring**

- Add shared backend env files to backend, worker, beat, and listener services.
- Keep DB/Redis and listener shard variables in Compose `environment` so they override `backend/.env`.
- Add `ENVIRONMENT=production` and `COMPOSE_DEPLOYMENT=true` for production services.
- Do not interpolate application secrets to empty strings in YAML.
- Mount Landing output read-only and retain the existing `/usr/share/nginx/landing` Nginx root.
- Update examples to explain `cp backend/.env.example backend/.env` and the Landing build step.

**Step 4: Add executable preflight**

The script uses `set -euo pipefail` and checks:

```bash
test -f landing/dist/index.html
test -f frontend/src/lib/queryClient.ts
test "$(cd backend && alembic heads | rg -c '\(head\)$')" -eq 1
docker compose --env-file .env.example -f docker-compose.yml config -q
docker compose --env-file .env.example -f docker-compose.prod.yml config -q
```

It exits non-zero with a clear message when a prerequisite is absent. Do not build, migrate, or deploy.

**Step 5: Verify green**

Run: `cd backend && pytest tests/test_release_contract.py -q`

Run when Docker CLI exists: `docker compose --env-file .env.example -f docker-compose.prod.yml config -q`

Expected: tests PASS; Compose config PASS or be recorded as unavailable when the runtime is absent.

**Step 6: Commit**

```bash
git add docker-compose.prod.yml docker-compose.yml nginx.conf .env.example scripts/release_preflight.sh backend/tests/test_release_contract.py
git commit -m "build: add reproducible release preflight"
```

## Task 7: Remove tracked credentials and document rotation

**Files:**

- Modify: `docs/architecture/MIGRATION_GUIDE.md`
- Create: `docs/operations/CREDENTIAL_ROTATION.md`
- Create: `scripts/check_tracked_secrets.sh`
- Create: `backend/tests/test_credential_hygiene.py`

**Step 1: Write the failing hygiene test**

Assert the migration guide contains placeholders only, the runbook lists every credential class, and the scanner rejects the known leaked-pattern fixtures while accepting `.env.example` placeholders.

Required runbook classes: PostgreSQL, Redis, admin password, JWT secret, session encryption, NowPayments, LLM providers, Telegram API/session files, and TLS private keys.

**Step 2: Verify red**

Run: `cd backend && pytest tests/test_credential_hygiene.py -q`

Expected: FAIL because tracked live-looking values remain and no runbook/scanner exists.

**Step 3: Redact and add the runbook**

- Replace hosts, passwords, and administrator credentials in the migration guide with `<DB_HOST>`, `<DB_PASSWORD>`, `<REDIS_PASSWORD>`, and `<ADMIN_PASSWORD>`.
- Document rotation order, validation, dependent-service restart, rollback, and audit evidence for every class.
- Put Git-history cleanup after rotation and label it as a separate destructive procedure requiring explicit approval.
- Include read-only permission checks with `find ... -printf '%m %p\n'`; prescribe service-account ownership and mode `0600` without changing live files.

**Step 4: Add a narrow tracked-file scanner**

Use `git grep` over tracked text files for the exact retired credential patterns plus private-key headers and obviously assigned non-placeholder secrets. Exclude lockfiles, fixtures that contain only generated dummy values, and example placeholders. Never print secret values; report file and rule name only.

**Step 5: Verify green**

Run: `cd backend && pytest tests/test_credential_hygiene.py -q`

Run: `bash scripts/check_tracked_secrets.sh`

Expected: PASS and no secret values printed.

**Step 6: Commit**

```bash
git add docs/architecture/MIGRATION_GUIDE.md docs/operations/CREDENTIAL_ROTATION.md scripts/check_tracked_secrets.sh backend/tests/test_credential_hygiene.py
git commit -m "docs: add credential rotation controls"
```

## Task 8: Restore business-frontend type safety without weakening checks

**Files:**

- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/hooks/useAccounts.ts`
- Modify: `frontend/src/pages/BusinessOps.tsx`
- Modify: `frontend/src/pages/CRM.tsx`
- Modify: `frontend/src/pages/CampaignPage.tsx`
- Modify: `frontend/src/pages/Dashboard.tsx`
- Modify: `frontend/src/pages/FunnelGroupPage.tsx`
- Modify: `frontend/src/pages/Inbox.tsx`
- Modify: `frontend/src/pages/InvitePage.tsx`
- Modify: `frontend/src/pages/KnowledgeBasePage.tsx`
- Modify: `frontend/src/pages/Login.tsx`
- Modify: `frontend/src/pages/LogsPage.tsx`
- Modify: `frontend/src/pages/Marketing.tsx`
- Modify: `frontend/src/pages/MonitorPage.tsx`
- Modify: `frontend/src/pages/MonitoringDashboard.tsx`
- Modify: `frontend/src/pages/PersonaPage.tsx`
- Modify: `frontend/src/pages/Scraping.tsx`
- Modify: `frontend/src/pages/ScriptPage.tsx`
- Modify: `frontend/src/pages/SourceGroupPage.tsx`
- Modify: `frontend/src/pages/SystemConfigPage.tsx`
- Modify: `frontend/src/pages/TasksPage.tsx`
- Modify: `frontend/src/pages/Warmup.tsx`
- Modify: `frontend/src/pages/accounts/AccountUploader.tsx`
- Modify: `frontend/src/pages/ai/UsageDashboard.tsx`
- Modify: `frontend/src/portal/pages/BulkDetail.tsx`
- Modify: `frontend/src/portal/pages/BulkInbox.tsx`
- Modify: `frontend/src/portal/pages/BulkNew.tsx`
- Modify: `frontend/src/sales/pages/Wallet.tsx`
- Modify: `frontend/src/services/api.ts`

**Step 1: Preserve the failing compiler output**

Run: `cd frontend && npm run typecheck`

Expected: exit 2 with the verified diagnostics. Do not disable `noUnusedLocals`, use `skipLibCheck` to hide app errors, add `any`, or remove `typecheck` from CI.

**Step 2: Remove dead imports/state in mechanical batches**

Delete only symbols identified by TS6133. After each group, rerun `npm run typecheck` and ensure the error count decreases without new diagnostics.

**Step 3: Repair real contract mismatches**

- Inbox: either add the backend-supported `interactions` field to the `Lead` read type or use the actual interaction query result; do not assert-cast.
- Marketing: replace invalid Ant Design `orientation="left"` with the supported property/value for the installed version.
- Scraping: wrap the refresh callback as `onClick={() => void fetchBatches()}`.
- Script: align create/run payloads and `Script` response fields with the backend schemas (`roles`/`lines` versus legacy JSON field names) in one typed API adapter.
- Warmup: align `WarmupTask` with the actual endpoint response or update rendering to existing fields.
- AccountUploader: use `ReturnType<typeof setTimeout>` and narrow Ant Design `RcFile` values without an invalid `File` predicate.

**Step 4: Verify frontend**

Run: `cd frontend && npm run typecheck && npm test -- --run && npm run build`

Expected: all commands PASS.

**Step 5: Commit**

```bash
git add frontend/src
git commit -m "fix: restore frontend type safety"
```

## Task 9: Add CI for the release contract

**Files:**

- Create: `.github/workflows/ci.yml`
- Modify: `frontend/package.json`
- Modify: `landing/package.json`
- Create: `backend/tests/test_ci_contract.py`

**Step 1: Write a failing CI contract test**

Parse the workflow as text and require jobs/steps for:

- backend collection and tests;
- one Alembic head check;
- tracked-secret scan;
- frontend locked install, typecheck, test, and build;
- Landing locked install, typecheck/test/build;
- Compose config validation;
- release-contract file existence.

**Step 2: Verify red**

Run: `cd backend && pytest tests/test_ci_contract.py -q`

Expected: FAIL because `.github/workflows/ci.yml` does not exist.

**Step 3: Implement the workflow**

Use Python 3.10 and Node 20. Cache pip/npm by lockfile. Set deterministic test environment values through job-level environment variables. Run `npm ci`; never run `npm audit fix` or mutate lockfiles in CI. Upload no secret-bearing `.env` files. Keep backend, frontend, Landing, and release-contract checks in separate jobs so failures are attributable.

Keep `build` and `typecheck` as distinct scripts in the business frontend. Add a Landing `typecheck` script if absent so CI can report it separately from `build`.

**Step 4: Verify green**

Run: `cd backend && pytest tests/test_ci_contract.py -q`

Run: `cd frontend && npm run typecheck && npm test -- --run && npm run build`

Run: `cd landing && npm run typecheck && npm test -- --run && npm run build`

Expected: PASS.

**Step 5: Commit**

```bash
git add .github/workflows/ci.yml frontend/package.json landing/package.json backend/tests/test_ci_contract.py
git commit -m "ci: enforce phase zero release gates"
```

## Task 10: Full verification and release-candidate handoff

**Files:**

- Modify only files required by verification failures that are within this plan's scope.

**Step 1: Run backend verification**

```bash
cd backend
pytest --collect-only -q
pytest -q
alembic heads
```

Expected: no collection errors, all automated tests PASS, exactly one Alembic head.

**Step 2: Run web verification**

```bash
cd frontend
npm run typecheck
npm test -- --run
npm run build
cd ../landing
npm run typecheck
npm test -- --run
npm run build
```

Expected: all commands PASS.

**Step 3: Run release gates**

```bash
bash scripts/check_tracked_secrets.sh
bash scripts/release_preflight.sh
git diff --check
git status --short
```

Expected: secret scan and preflight PASS; no whitespace errors; only intentional branch changes are present.

**Step 4: Review security invariants**

Use `git diff release/merge-main-into-safety...HEAD` and confirm:

- no generated secret or password is logged;
- no customer/sales router inherited platform-admin dependencies;
- WebSocket authentication completes before `accept()`;
- the wallet settlement path has one commit and rollback on all exceptions;
- production startup does not call `create_all`;
- no live credential, deployment, database mutation, or Group AI merge occurred.

**Step 5: Resolve verification failures within their owning task**

If a command fails, return to the task that owns that file, add a regression
test where behavior changed, make the smallest fix, rerun that task's focused
checks, and then repeat the complete verification matrix. Do not create an
unscoped catch-all commit.

**Step 6: Hand off**

Report exact command results, known environmental skips (for example Docker runtime unavailable), the commit list, and the next safe operational actions: code review, staging restore/migration, credential rotation, staging smoke tests, then release approval. Do not deploy or rotate credentials as part of this plan.
