# API Endpoints Map

37 endpoint modules. The naming convention is **`{role}_{domain}.py`** where role is `admin_` (internal team), `customer_` (paying tenant), or unprefixed (shared / admin-default).

## Auth — single file post-merge

| Router (in `auth.py`) | Mount prefix | URLs |
|---|---|---|
| `admin_router` | (none) | `/login/access-token` (OAuth2 + 2FA), `/logout`, `/auth/setup-2fa`, `/auth/verify-2fa` |
| `customer_router` | `/customer` | `/customer/register`, `/customer/login` (deprecated), `/customer/me` |
| `unified_router` | `/auth` | `/auth/login` (SPA entry — identifier email → customer, username → admin) |

> Why three routers in one file: OAuth2 bearer schemes in `deps.py` / `deps_customer.py` are bound to specific tokenUrls. Moving URLs would break token validation. The file split was historical; one file is now enough.

## Admin (internal team) endpoints

| File | Mount prefix | What |
|---|---|---|
| `admin_billing.py` | `/admin/billing` | Subscriptions, invoices, manual activate |
| `admin_bulk.py` | `/admin/bulk` | Cross-customer bulk batch list, force pause/cancel, metrics |
| `admin_dashboard.py` | `/admin/dashboard` | Epic 6 — MRR/funnel/pool/LLM/handover/health panels |
| `admin_features.py` | `/admin/features` | Feature registry CRUD |
| `users.py` | `/users` | Admin user CRUD |
| `system.py` | `/system` | System config + health |
| `logs.py` | `/logs` | Audit log query |

## Customer (paying-tenant) endpoints

| File | Mount prefix | What |
|---|---|---|
| `customer_billing.py` | `/customer` | Self-serve subscribe, NowPayments webhook redirect |
| `customer_bulk.py` | `/customer/bulk` | Bulk Send: preview-cost, batches CRUD, variants CRUD |
| `customer_features.py` | `/customer/features` | Feature pack usage view |
| `customer_kb.py` | `/customer` | Knowledge-base CRUD + upload |
| `customer_main_account.py` | `/customer` | Epic 5 main-account QR login |
| `customer_resources.py` | `/customer` | Read-only resource lists (accounts, leads, quota) |
| `customer_wallet.py` | `/customer/wallet` | Topup, balance, transactions |

## TG/Account endpoints (admin-default)

| File | What |
|---|---|
| `accounts.py` | Account CRUD, session import, bulk ops |
| `proxies.py` | Proxy CRUD + assign |
| `registration.py` | New-account SMS registration flow |
| `warmup.py` | Warmup task queue |

## Marketing / monitoring — NOT duplicates, separate concerns

These two are easy to confuse — they have different jobs:

| File | What |
|---|---|
| `monitor.py` | **Keyword monitor management** — CRUD monitors, AI keyword suggestion, semantic match, hit tracking, live-chat groups |
| `monitoring.py` | **Real-time dashboard snapshot** — account status, proxy health, warmup counts, alerts |
| `marketing.py` | Marketing campaign CRUD, safe-send dispatch |
| `campaigns.py` | Campaign templates + scheduling |

## CRM / scraping

| File | What |
|---|---|
| `crm.py` | Lead Inbox: list/filter/takeover/reply |
| `scraping.py` | Group member + message scraping |
| `source_groups.py` | Traffic-source group catalog |
| `funnel_groups.py` | Funnel/destination group catalog |

## AI / KB

| File | What |
|---|---|
| `ai.py` | LLM completion + intent + persona test |
| `ai_usage.py` | LLM usage stats |
| `personas.py` | Persona CRUD |
| `knowledge_bases.py` | Admin-side KB CRUD (vs `customer_kb.py`) |

## Misc

| File | What |
|---|---|
| `invite.py` | Invite-link automation |
| `script.py` | Legacy script runner |
| `tasks.py` | Generic task queue introspection |
| `workflow.py` | DSL-based workflow runner |
| `webhooks.py` | Inbound webhooks (NowPayments, etc.) |
| `ws.py` | WebSocket gateway |
