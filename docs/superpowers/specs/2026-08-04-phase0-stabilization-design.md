# Phase 0 Stabilization Design

**Date:** 2026-08-04

**Status:** Approved for implementation planning

## Objective

Create one reproducible release baseline and close the highest-risk security,
payment, configuration, and deployment gaps before any Group AI phase is
merged. The result must be safe to build from a clean checkout and must fail
closed when production secrets are missing.

## Baseline and Delivery Boundary

- Implementation starts from `release/merge-main-into-safety` at `80e7d06`.
- Work is isolated on `codex/phase0-stabilization`.
- The Group AI Phase 1-12 stack remains quarantined and is not merged.
- This phase changes repository code, tests, configuration templates, and
  operational documentation only.
- It does not rotate live credentials, restart production containers, mutate
  the production database, rewrite Git history, or deploy a release.

## Workstreams

### 1. Authorization Boundary

The public API remains divided into three explicit identity surfaces:

- `/admin` and legacy platform-management routes: admin or superuser only.
- `/customer`: customer JWT scoped to exactly one `customer_id`.
- `/sales`: platform-sales or customer-sales JWT resolved through
  `SalesContext` and scoped by kind and tenant.

Legacy management routers such as accounts, proxies, system configuration,
AI configuration, scraping, marketing, and operational logs must use an admin
dependency at the router boundary. Endpoints intentionally needed by platform
sales must be exposed through `/sales` rather than inheriting broad platform
access. `/users/me` remains available to the authenticated platform identity;
user administration remains admin-only.

System configuration responses must not expose secret values. A redacted
response reports whether a sensitive key is configured, while write operations
remain admin-only.

### 2. WebSocket Containment

The legacy `/api/v1/ws` channel is an admin operational channel during Phase
0. Its handshake must:

1. Decode the JWT with the configured algorithm.
2. Require a platform access token rather than customer or customer-sales
   token types.
3. Require `jti` to be unrevoked.
4. Resolve an active `User` from the database.
5. Require admin or superuser role before accepting the socket.

Customer- and sales-scoped real-time channels are deferred to the Redis
fan-out workstream because the current connection manager is process-local.
Until then, non-admin sockets are rejected instead of receiving global
broadcasts. Existing in-process admin notifications continue as best effort.

### 3. Atomic Wallet Settlement

Wallet and sales-wallet top-up settlement becomes one database transaction.
The service owns the full state transition:

1. Lock the invoice row.
2. Validate terminal payment status and invoice plan.
3. Return the existing transaction when its invoice idempotency key already
   exists.
4. Lock or create the target wallet without committing.
5. Mark the invoice paid and attach the payment hash.
6. Credit the wallet and create the transaction row.
7. Commit once after all mutations succeed.

On any exception the service rolls back the session. The invoice therefore
remains pending and a webhook retry can settle it. Subscription activation
keeps its existing path but receives regression coverage for idempotency.

No network call is made while database locks are held.

### 4. Production Configuration

Add an explicit environment mode with `development`, `test`, and `production`
values. Production startup validates these required values:

- `SECRET_KEY`, minimum 32 characters.
- `SESSION_ENCRYPTION_KEY`, minimum 32 characters.
- `ADMIN_PASSWORD`, minimum 12 characters and not a known default.
- `DATABASE_URL`, PostgreSQL in production.
- `REDIS_URL`, non-empty and authenticated when the Compose deployment is
  used.

Development may generate ephemeral values, but generated values are never
printed. Production never generates replacements and exits with a validation
error before serving traffic.

Backend, worker, beat, and listener services read the same ignored
`backend/.env` file, while Compose-provided database, Redis, and shard values
override it. The example environment file documents every required setting
without containing usable credentials.

### 5. Schema and Deployment Reproducibility

Alembic is the sole production schema authority. FastAPI startup may call
`SQLModel.metadata.create_all` only outside production so existing local SQLite
development remains convenient. Production startup requires `alembic upgrade
head` to complete before Gunicorn starts.

The release baseline already tracks the load-bearing migration
`41f948211e5f` and `frontend/src/lib/queryClient.ts`; CI verifies both remain
present.

The production Nginx service receives the built Landing assets at
`/usr/share/nginx/landing`. A documented build step produces `landing/dist`
before Compose startup. Missing Landing assets must be detected by the release
preflight rather than producing a root-path 404.

### 6. Credential Incident Hygiene

Tracked documentation must replace live-looking credentials, host addresses,
and administrator passwords with placeholders. Add a rotation runbook covering
database, Redis, administrator, JWT, session encryption, payment, LLM,
Telegram, and TLS credentials.

The runbook explicitly requires rotation before optional Git-history cleanup.
History rewriting is a separate destructive operation and is not performed by
this phase.

Local secret files, TLS private keys, and Telegram session files should be
owned by the service account and mode `0600`; the runbook contains the exact
verification commands. Repository code does not chmod arbitrary deployment
paths automatically.

## Error Handling

- Authentication and authorization failures return 401 for missing or revoked
  credentials and 403 for authenticated identities lacking capability.
- Sensitive resources use 404 when tenant existence itself must not be leaked.
- Configuration validation fails during process startup, before database seed
  or model warmup.
- Wallet settlement rolls back all state and returns a retryable webhook error;
  duplicate successful notifications return the existing receipt.
- Best-effort provisioning remains outside the payment transaction. Improving
  its repair workflow is a follow-up and does not reverse a settled payment.

## Test Strategy

All behavior changes follow red-green-refactor.

### Authorization

- A platform-sales token cannot list, create, update, or delete accounts.
- A platform-sales token cannot read or write raw system configuration.
- An admin token retains access.
- Customer and customer-sales tokens remain rejected by platform dependencies.

### WebSocket

- Missing, malformed, expired, revoked, customer, customer-sales, inactive-user,
  and platform-sales tokens are rejected before `accept()`.
- An active admin token can connect and exchange a ping/pong heartbeat.

### Payment

- Injecting a wallet mutation failure leaves the invoice pending, balance
  unchanged, and no transaction row.
- Retrying after the failure produces exactly one transaction and one balance
  increase.
- Replaying a successful webhook returns the original transaction without a
  second credit.
- Customer-wallet and customer-sales-wallet paths share the same guarantees.

### Configuration and Release

- Production settings reject each missing or weak required secret.
- Development settings do not log generated values.
- `alembic heads` returns one head and a clean database upgrades to it.
- Backend tests collect only automated tests; manual/network scripts are
  excluded.
- Business frontend and Landing typecheck, test, and build commands run in CI.
- Both Compose files pass configuration validation without missing-variable
  warnings when supplied with the example test environment.

## Rollout Order

1. Land tests and fixes on the isolated branch.
2. Run the full repository verification matrix from a clean worktree.
3. Review the diff and create a release-candidate artifact.
4. Rotate credentials using the runbook outside this code change.
5. Restore a production backup into staging and run migrations.
6. Deploy to staging and exercise admin, customer, sales, payment, and
   WebSocket smoke tests.
7. Deploy production with a recorded image digest and rollback image.

## Acceptance Criteria

- Non-admin platform users receive 403 from every management mutation and
  secret-bearing read endpoint.
- Non-admin WebSocket identities cannot connect to the global channel.
- A wallet settlement failure never leaves a paid invoice without its wallet
  transaction.
- Production processes cannot start with missing or generated security keys.
- A clean checkout contains the full migration chain and QueryClient module.
- A clean PostgreSQL database upgrades to one Alembic head.
- Backend, frontend, Landing, Compose, and secret-scan gates pass before a
  release artifact is built.
- Tracked documentation contains no usable production credential.

## Follow-up Projects

After Phase 0, independent designs and plans cover:

1. Redis-backed tenant-aware real-time fan-out.
2. CI completion, frontend type debt, and test-suite classification.
3. Unified role/capability and tenant-query policy.
4. Unified subscription, quota, wallet, and feature-billing ledger.
5. Controlled Group AI Phase 1-12 integration.
6. 100/300/1000-account capacity and recovery testing.
