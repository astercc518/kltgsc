# Services Map

54 service modules — group them by domain before reading individual files.

## TG account lifecycle

| File | Role |
|---|---|
| `account_assignment.py` | Sticky DM↔account pairing for keyword monitors |
| `allocation_service.py` | Epic 3 — pool→customer auto-assign on plan activation |
| `auto_register.py` | New-account SMS registration via `sms_activate` |
| `device_generator.py` | Spoof Android/iOS device fingerprints for fresh accounts |
| `profile_generator.py` | Bio/avatar/name generation for warmup |
| `warmup_service.py` | Day-N safe-action plan (read groups, send to self, etc.) |
| `permission_service.py` | RBAC checks (admin / sales / customer JWT scopes) |
| `score_service.py` | Account health score (flood waits, ban events) |

## TG session I/O — read-only vs read-write

These two pairs look duplicated but are **different layers**:

| File | Reads/Writes | Job |
|---|---|---|
| `session_parser.py` | Read-only | Extract phone + metadata from session filename / file header |
| `session_converter.py` | Read-write | Detect format (Telethon vs Pyrogram), convert, backup, migrate schema |
| `tdata_converter.py` | Wrapper | Spawn subprocess, parse output → return path |
| `tdata_converter_script.py` | Subprocess worker | Actual opentele/PyQt5 conversion (must run isolated to avoid Qt blowing up async) |
| `session_encryption_service.py` | Crypto | Encrypt/decrypt session files at rest |

## Mass-send dispatchers — three different flows, NOT duplicates

| File | Trigger | Quota model |
|---|---|---|
| `shill_dispatcher.py` | Keyword-monitor hit in a group | Static script OR Director-Actor AI persona pair |
| `safe_send_dispatcher.py` | Marketing campaign (manual / scheduled) | Per-account daily quota tiered by account age + flood-wait cooldown |
| `bulk_dispatch_service.py` | Customer-initiated Bulk Send batch | Wallet-charged, variant-weighted, target sharded across pool |

Decision flow: keyword-driven → `shill_dispatcher`. Marketing → `safe_send_dispatcher`. Customer batch (Portal /bulk) → `bulk_dispatch_service`.

## Reply / conversation

| File | Job |
|---|---|
| `ai_reply_service.py` | LLM-generated reply with KB injection + intent + handover trigger |
| `bulk_reply_service.py` | Inbound DM tracker for Bulk Send batches (mark target replied, create Lead) |
| `conversation_director.py` | Director-Actor 2-account chat planning for shill flows |
| `intercept_service.py` | Pre-send filter (banned phrases, length, dedup) |
| `keyword_monitor_service.py` | Match incoming message against monitor rules |

## Lead / CRM / handover

| File | Job |
|---|---|
| `main_account_notifier.py` | Saved-Messages alerts to the customer's main TG account |
| `safe_send_dispatcher.py` | (see above) |

## Billing & wallet

| File | Job |
|---|---|
| `billing_service.py` | Subscription create/renew, invoice CRUD |
| `wallet_service.py` | Bulk-Send wallet topup, debit, low-balance flag |
| `pricing.py` | Plan pricing tables + Bulk-Send tiered cost |
| `feature_billing.py` | Per-feature usage charging |
| `usage_tracker.py` | Quota counters (account_used, group_used, etc.) |

## Knowledge base / AI

| File | Job |
|---|---|
| `embedding_service.py` | Vertex Gemini embedding (768-dim) |
| `industry_kb_service.py` | LLM auto-generate KB on plan activation |
| `kb_retrieval.py` | pgvector search + rerank |
| `kb_upload_service.py` | Customer file → chunks → embeddings |
| `qa_extractor.py` | Pull Q-A pairs from chat history into KB |
| `llm.py` | Vertex LLM client (kltgsc project) |
| `ai_engine.py` | High-level orchestrator: retrieve KB → call LLM → format reply |
| `persona_profile.py` | AI persona config (tone, language, system prompt) |
| `qr_login_service.py` | Epic 5 main-account QR login |

## Scraping / proxies / infra

| File | Job |
|---|---|
| `scraper.py` | Group member / message scraping |
| `mega_importer.py` | Bulk import accounts from tdata folder |
| `proxy_assigner.py` | Sticky account↔proxy binding |
| `proxy_checker.py` | Liveness + geo check |
| `proxy_fetcher.py` | Pull proxies from upstream provider |
| `client_pool.py` | Pyrogram client connection pool |
| `telegram_client.py` | Pyrogram client factory + helpers |
| `listener_service.py` | Long-running event listener (one process per account) |
| `sms_activate.py` | SMS-Activate.org client |
| `websocket_manager.py` | Portal/admin WS connections |
| `dashboard_service.py` | Epic 6 admin business-ops queries |
| `script_executor.py`, `script_service.py` | Custom auto-task scripts (deprecated path, see `workflow_*`) |
| `workflow_engine.py` | New DSL-based workflow runner |
| `system_config_service.py` | Key-value system config CRUD |
| `invite_service.py` | Group invite link rotation |
