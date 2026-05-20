# TG1 Business Plan (Angel Round)

> **TG1 (Telegram Growth Intelligence)**
> **Multi-Account TG Orchestration + AI Lead Generation Platform**
> Business Model: **System Account Licensing** — Monthly subscription for customized TG accounts + AI personas + industry knowledge base + massive group coverage
>
> Document Version: v3.0 ｜ Date: 2026-05-18 ｜ Round: Angel

---

## 1. Executive Summary

### 1.1 One-Liner

**TG1 sells the right to use "customized TG accounts + AI personas + industry knowledge bases + thousands of target groups" as a monthly subscription. Starting at $199/month, customers log in and start acquiring leads.**

### 1.2 Business Model at a Glance

```
            ┌──────────────────────────────────────────────┐
            │           TG1 Platform (Seller)             │
            │  • Pool of 1000+ pre-warmed TG accounts      │
            │  • Massive industry group library (5000+)    │
            │  • AI persona customization + auto-KB        │
            │  • AI lead-gen (KB+RAG+Intent+Copilot)       │
            │  • Sales Workbench (CRM + Inbox)             │
            └──────────────────┬───────────────────────────┘
                               │ Monthly Subscription
                               │ $199 / $299 / $599
                ┌──────────────▼──────────────┐
                │      Customer (Buyer)       │
                │  • Crypto / Web3 projects   │
                │  • Cross-border e-commerce  │
                │  • B2B exporters            │
                │  • Global SaaS / gaming     │
                └─────────────────────────────┘
```

**Customers don't buy a tool — they buy a 7×24 AI-driven lead-gen team.**

### 1.3 Three Subscription Tiers (Core Pricing)

| Plan | Monthly | TG Accounts | AI Target Groups | Target Customer |
|---|---|---|---|---|
| **Starter** | **$199 / mo** | 3 custom accounts | 500 | Solo / small teams |
| **Growth** | **$299 / mo** | 5 custom accounts | 1,000 | Mid-size export / e-com |
| **Pro** | **$599 / mo** | 10 custom accounts | 3,000 | Crypto projects / large clients |

**Every tier includes**:
- ✅ **Industry-customized TG accounts** (username / avatar / bio / language matched)
- ✅ **AI persona customization** (Pro Sales / Technical Analyst / Active Member, etc.)
- ✅ **Auto-generated industry knowledge base** (scraping + Vertex AI Embedding)
- ✅ **AI precision lead-gen** (group monitoring + intent detection + opener generation + multi-turn negotiation)
- ✅ **Sales takeover workbench** (CRM + Inbox Copilot mode)
- ✅ **Auto-replacement for banned accounts**

### 1.4 Why This Model Works

| Build It Yourself | Use TG1 |
|---|---|
| Register accounts (SMS + proxies + device fingerprints) | ✅ Platform supplies pre-warmed accounts |
| Buy proxies (IP2World / 911s5) | ✅ Platform's proxy pool already bound |
| Warm up accounts for 30+ days | ✅ Accounts already past warm-up |
| Find industry groups (manual search + join rate limits) | ✅ **500-3000 industry groups instantly covered** |
| Curate industry knowledge base | ✅ **AI auto-scrapes + embeds** |
| Develop control scripts (6+ months) | ✅ 50+ services ready to use |
| Integrate AI (GPT/Gemini) | ✅ Vertex AI Gemini integrated |
| Banned = start over | ✅ Auto-replacement + role-based risk control |
| **Cost**: ¥300k upfront + 6 months + ongoing ops | **Cost**: $199/mo, 5-minute setup |

### 1.5 Key Achievements (Already Built)

- **All 9 development stages completed**: account lifecycle, AI marketing, CRM, dashboard, monitoring
- **1000+ account capacity already implemented**: Listener sharding, multi-replica workers, PG/Redis tuning
- **Complete AI pipeline**: pgvector (HNSW 768d) + Vertex AI Gemini + Copilot mode
- **Code assets**: 50+ backend services, 25+ frontend pages, Alembic migration framework
- **Production-ready deployment**: Docker Compose + Nginx + Cloudflare + multi-replica

### 1.6 Funding Request

| Item | Detail |
|---|---|
| Round | Angel |
| Amount | **¥ 500,000 CNY (~$ 71,000 USD)** |
| Valuation | Pre-money ¥4M / Post-money ¥4.5M |
| Equity offered | ~**11.1%** (negotiable 10-15%) |
| Runway | **12 months** |
| Use of funds | Account pool 30% / Team 25% / Infra 25% / Marketing 15% / Reserve 5% |

---

## 2. Market Opportunity

### 2.1 Industry Trends

- **Telegram MAU passed 900M (2025)**, fastest-growing private-traffic channel for global teams
- **WeChat increasingly bans export accounts**, driving export businesses to TG
- **Web3 / Crypto**: 90% of projects use TG as their primary community channel
- **TG account price rising**: high-quality aged accounts ¥100-500 each on black market, with supply heavily reliant on grey-market chains

### 2.2 Target Customers (ICP)

| Type | Profile | Pain Point | Monthly Budget |
|---|---|---|---|
| **Crypto / Web3 Projects** | Exchanges, DeFi, NFT projects | Community + high-ticket conversion | **Pro $599+** (multi-seat) |
| **Cross-border E-commerce** | Shopify sellers, DTC brands | Funnel from TG to conversion | **Growth $299** |
| **B2B Exporters** | SMB exporters, freelance traders | Continuous overseas client acquisition | **Starter $199** |
| **Global Gaming / SaaS** | Cross-border startups | User acquisition + retention | **Growth/Pro $299-599** |
| **MCN / KOL Operators** | TG channel matrix operators | Multi-account matrix management | **Pro $599+** |

### 2.3 Market Sizing

| Tier | Scope | Estimate |
|---|---|---|
| **TAM** | Global TG private-traffic marketing tools | USD 3B/year |
| **SAM** | Chinese cross-border teams + Web3 projects | USD 600M/year |
| **SOM** (3-year achievable) | Top 5-10% of Chinese export teams | ¥50M ARR (~$7M) |

**A single city or vertical can support the angel-round target**: Shenzhen cross-border e-commerce alone has 10,000+ willing-to-pay customers.

---

## 3. Product Architecture

### 3.1 System Overview

```
┌────────────────────────────────────────────────────────────────┐
│                Customer Web Frontend (React 18)                │
│  Account Pool │ Campaign │ KB │ CRM │ Inbox │ Dashboard       │
└────────────────────────┬───────────────────────────────────────┘
                         │ REST + WebSocket
┌────────────────────────▼───────────────────────────────────────┐
│              FastAPI Backend (Python 3.10+ / asyncio)          │
│   ┌──────────────────────────────────────────────────────┐     │
│   │  API Layer  /api/v1/*  (25+ endpoints)               │     │
│   └──────────────────────────────────────────────────────┘     │
│   ┌──────────────────────────────────────────────────────┐     │
│   │  Service Layer (50+ services)                        │     │
│   │  • TG Client Pool (Pyrogram)                         │     │
│   │  • Task Scheduling (Celery + Redis)                  │     │
│   │  • AI Engine (Vertex AI / Gemini)                    │     │
│   │  • Knowledge Base (pgvector HNSW 768d)               │     │
│   │  • Proxy Pool (IP2World / 911s5)                     │     │
│   │  • SMS (SMS-Activate)                                │     │
│   └──────────────────────────────────────────────────────┘     │
└──┬───────────┬──────────────┬────────────────┬────────────────┘
   │           │              │                │
   ▼           ▼              ▼                ▼
┌──────┐  ┌────────┐    ┌─────────┐      ┌──────────┐
│ PG16 │  │ Redis  │    │   TG    │      │Vertex AI │
│pgvect│  │ Celery │    │ Servers │      │ Gemini   │
└──────┘  └────────┘    └─────────┘      └──────────┘
```

### 3.2 Tech Stack

| Layer | Technology | Rationale |
|---|---|---|
| Backend | FastAPI + SQLModel + Pyrogram | Async-friendly, native fit for TG protocol |
| Task Queue | Celery + Redis | Thousand-account concurrency, sharded scaling |
| Database | PostgreSQL 16 + pgvector + Alembic | Single DB for business data + vector search |
| AI | Vertex AI (Gemini) + `gemini-embedding-001` 768d | Enterprise SLA, no free-tier RPM limits |
| Frontend | React 18 + Vite + Ant Design | Rapid admin UI iteration |
| Deployment | Docker Compose + Nginx + Cloudflare | Single-host launch, no cloud lock-in |

### 3.3 Account-as-a-Service (AaaS) — Three Asset Layers

| Layer | Asset | Customer View |
|---|---|---|
| **Account Layer** | 1000+ pre-warmed TG accounts, grouped by cannon/scout/actor/sniper | Ready to use, auto-replaced on ban |
| **Capability Layer** | Full software stack: orchestration + AI lead-gen + sales handoff | No coding, UI config |
| **Service Layer** | Customer success + risk advisor + script optimization | Guided, never stranded |

---

## 4. Core Business Flows

### 4.1 Customer Purchase & Onboarding Flow

```
Customer visits site → selects plan (by accounts + groups) → pays monthly fee
    ↓
Platform allocates dedicated account pool (tenant-isolated)
    ↓
Customer logs in → uploads KB (PDF/Word/web) → configures AI persona → sets script
    ↓
Customer configures hunting grounds (competitor / industry group links)
    ↓
Platform launches Scout monitoring + AI scoring + Sniper outreach
    ↓
High-intent leads → sales takes over in Inbox → Copilot-assisted closing
```

### 4.2 Three Core Lead-Gen Pipelines

**A. Competitor Interception (Real-Time)**
```
Scout joins competitor group → listens for new members → AI scoring
  → Sniper DMs within 5 minutes → user replies → AI multi-turn negotiation
  → high-intent alert → sales takes over → closes deal
```

**B. Bulk Group Washing (Weekly)**
```
Scout bulk-scrapes public groups (500-1000 members each) → AI batch scoring
  → Tier-A direct DM / Tier-B funnel into nurture group / Tier-C discard
  → Actors run hype scripts in nurture group → engaged users harvested by Sniper
```

**C. AI Service + Sales Takeover (Core Commercialization Loop)**
```
Inbound TG DM → KB retrieval (pgvector) → intent analysis → AI reply
  → intent=purchase + is_high_value → WebSocket high-intent alert
  → Sales clicks "Take Over" → Lead.ai_enabled=false
  → AI switches to Copilot (no auto-send, generates drafts + live negotiation summary)
  → Sales one-click send / edit-and-send → deal closed
```

---

## 5. Module Functionality Matrix

### 5.1 Backend Services (50+)

| Module Group | Key Services | Function |
|---|---|---|
| **Account Lifecycle** | `auto_register` `device_generator` `session_*` `warmup_service` | Registration, device fingerprint, session, warm-up |
| **Proxy Network** | `proxy_fetcher` `proxy_checker` `proxy_assigner` | API fetch, connectivity check, ISP binding |
| **TG Communication** | `telegram_client` `client_pool` `listener_service` | Pyrogram pool, 5-shard listener |
| **Task Scheduling** | `safe_send_dispatcher` `shill_dispatcher` `script_executor` `workflow_engine` | Rate-limited send, hype, script, workflow |
| **AI Engine** | `ai_engine` `llm` `ai_reply_service` `conversation_director` | LLM routing, reply generation, dialog state |
| **Knowledge Base** | `embedding_service` `kb_retrieval` `qa_extractor` | Vertex Embedding, vector recall, Q&A extraction |
| **Acquisition & Marketing** | `scraper` `intercept_service` `keyword_monitor_service` `invite_service` | Group scraping, interception, keywords, invites |
| **CRM & Profiling** | `score_service` `persona_profile` | User scoring, persona profile |
| **Billing & Quota** | `pricing` `usage_tracker` `permission_service` | LLM billing, tenant quota (core monetization) |
| **Infrastructure** | `websocket_manager` `system_config_service` `mega_importer` | Realtime push, dynamic config, bulk import |

### 5.2 Frontend Pages (25+)

| Module | Page | Value |
|---|---|---|
| Account Pool | AccountList / AutoRegister / ProxyList / Warmup | Customer sees rented account status |
| Campaign | CampaignPage / TasksPage / Marketing / ScriptPage | Customer configures campaigns |
| Hunting Ground | SourceGroupPage / FunnelGroupPage / Scraping / InvitePage | Customer configures target groups |
| AI Center | AIPage / KnowledgeBasePage / PersonaPage / `ai/*` | Customer trains own AI |
| Sales Workbench | CRM / Inbox (Copilot) | Sales execution |
| Data | Dashboard / MonitoringDashboard / MonitorPage / LogsPage | Customer views ROI |
| System | Login / SystemConfigPage | Customer admin |

---

## 6. Business Model (Core Chapter)

### 6.1 Pricing Model: System Account Licensing

**Three Standard Tiers (USD-denominated, global customers)**

| Plan | Monthly | TG Accounts | AI Target Groups | Avg Groups/Account | AI Token Included |
|---|---|---|---|---|---|
| **Starter** | **$199 / mo** | 3 | 500 | 167 grp/acc | 2M tokens |
| **Growth** | **$299 / mo** | 5 | 1,000 | 200 grp/acc | 5M tokens |
| **Pro** | **$599 / mo** | 10 | 3,000 | 300 grp/acc | 15M tokens |

> **"AI Target Groups" defined**: max number of TG groups monitored & engaged for the customer, including competitor / industry / general-traffic groups. Customer filters by industry; platform accounts auto-join and run AI lead-gen.

### 6.2 What Each Plan Delivers (Standardized SKU)

| Deliverable | Starter | Growth | Pro |
|---|---|---|---|
| Customized TG accounts (industry-matched username/avatar/bio) | 3 | 5 | 10 |
| AI persona customization (Sales / Analyst / Active Member) | 1 set | 2 sets | 3 sets |
| Auto-generated industry KB (scrape + embed) | 1 | 2 | 5 |
| AI target group coverage | 500 | 1,000 | 3,000 |
| AI auto-reply + Copilot | ✅ | ✅ | ✅ |
| CRM + Inbox sales workbench seats | 1 | 3 | 10 |
| Auto-replacement SLA on ban | 24h | 12h | 4h |
| Customer success | Ticket | Ticket + monthly review | 1-on-1 dedicated CSM |

### 6.3 Add-On Revenue

| Item | Pricing |
|---|---|
| AI token overage | $5 / million tokens |
| Extra accounts | Starter $50/acc, Growth $45/acc, Pro $40/acc (tiered) |
| Extra target groups | $20 / 100 groups / month |
| Custom KB import service | $80 / batch (PDF <100 pages free) |
| Residential proxy upgrade | $5 / account / month |
| Self-hosted deployment | From $12,000 / year |
| Industry template customization (script + KB + persona) | $300 / batch |

### 6.4 Per-Account / Per-Group Cost Structure

**TG account monthly amortized cost** (SMS + warm-up + proxy + infra):

| Item | Cost (¥) |
|---|---|
| Registration (SMS-Activate + one-time proxy) | 15 |
| Warm-up amortization (30 days) | 7 |
| Monthly ops (proxy + server) | 15 |
| Avg lifecycle 4 months → monthly amortized | **¥ 25 ≈ $ 3.6** |

**Per-group monthly cost**:
- Join + message monitoring + Listener shard overhead → ~¥0.05 / group / month (marginal cost near zero)

**Per-customer AI token cost** (Vertex AI Gemini):
- 200-1500M tokens included, avg Vertex price ¥0.7 / M output tokens → ¥10-100/mo cost

### 6.5 Per-Plan Unit Economics (Critical)

| Item | Starter | Growth | Pro |
|---|---|---|---|
| Monthly fee (USD) | $ 199 | $ 299 | $ 599 |
| Monthly fee (¥, @ 7.0) | ¥ 1,393 | ¥ 2,093 | ¥ 4,193 |
| Account cost | ¥ 75 | ¥ 125 | ¥ 250 |
| Group coverage cost | ¥ 25 | ¥ 50 | ¥ 150 |
| AI token cost | ¥ 25 | ¥ 60 | ¥ 180 |
| Customer success amortized | ¥ 30 | ¥ 80 | ¥ 250 |
| **Total direct cost** | **¥ 155** | **¥ 315** | **¥ 830** |
| **Monthly gross profit** | **¥ 1,238** | **¥ 1,778** | **¥ 3,363** |
| **Gross margin** | **89%** | **85%** | **80%** |

**Blended gross margin ≈ 84%** (well above SaaS industry average 70-80%, thanks to near-zero marginal cost on account + group assets + automated ops).

### 6.6 Blended ARPU & LTV/CAC

**Plan mix assumption**: Starter 50% / Growth 30% / Pro 20%

| Metric | Value |
|---|---|
| Blended monthly fee | $199×0.5 + $299×0.3 + $599×0.2 = **$ 308 ≈ ¥ 2,160** |
| Blended monthly gross profit | **¥ 1,790** |
| CAC | ¥ 1,500 / customer |
| Monthly retention | 90% |
| Avg lifecycle | 10 months |
| LTV | ≈ ¥ 2,160 × 10 × 0.84 ≈ **¥ 18,144** |
| **LTV / CAC** | **≈ 12** |
| **Payback period** | **< 1 month** |

### 6.7 Three-Year Revenue Forecast

| Year | Paying Customers | Blended ARPU (USD) | MRR (USD) | ARR (USD) | ARR (¥) | Milestone |
|---|---|---|---|---|---|---|
| **Y1 (2026)** | 60 | $ 308 | $ 18.5k | $ 222k | ¥1.55M | PMF validated, account pool 2000 |
| **Y2 (2027)** | 280 | $ 350 | $ 98k | $ 1.18M | ¥8.25M | Crypto + cross-border head customers |
| **Y3 (2028)** | 900 | $ 400 | $ 360k | $ 4.32M | ¥30.24M | Series A / overseas expansion |

---

## 7. Technical Moats & Differentiation

### 7.1 Three Moats

**① Account Supply & Warm-up Engineering (Highest Barrier)**

Hardest part for competitors to replicate:
- Auto-registration: SMS-Activate + IP2World + device fingerprint → ¥15/account cost
- Auto warm-up: `warmup_service` simulates human behavior for 30-60 days
- Risk tiering: cannon/scout/actor/sniper 4 roles + health score + auto-demotion
- Replacement supply: auto-replace banned accounts in customer pool within 1 hour

**② 1000+ Account Real Engineering Capability**

- Listener sharded by `account.id % N`, 5 shards support 1000+ long connections
- Multi-replica Workers + `max-tasks-per-child=200` prevents Pyrogram memory leaks
- PG `max_connections=500`, Redis `maxmemory=4G` `noeviction`
- Most TG control tools stop at 50-200 accounts

**③ AI Copilot + Sales Collaboration Product Form**

- Competitor A (pure orchestration): only "blast tool", no AI, no sales handoff
- Competitor B (AI service SaaS): ChatGPT wrapper, no sales collaboration
- **TG1**: AI handles 80% long-tail traffic + auto-alert sales on high-intent + AI continuously generates drafts/summaries

### 7.2 Network Effect Moat

**Pre-warmed account inventory is a network effect**:
- More customers → faster pool churn → lower marginal cost/account → better pricing
- Different customers have different account requirements → secondary account flow (used Cannons demoted and reused)

---

## 8. Competitive Landscape

### 8.1 Comparison Table

| Dimension | TG1 | Competitor A (Scripts) | Competitor B (AI Service) | Self-Build |
|---|---|---|---|---|
| Account supply | **Platform-supplied, leased** | Customer brings own | – | Customer builds (hardest) |
| Account scale | **1000+ pre-warmed pool** | Customer's own (<200) | – | 6 months to start |
| AI lead-gen | **KB+RAG+Intent+Copilot** | None | ChatGPT wrapper | – |
| Sales handoff | **Copilot mode** | None | Simple human escalation | Manual |
| Risk tiering | **4 roles + health score** | Basic rate limit | – | Experience-dependent |
| Customer onboarding | **$199/mo, 5 min** | ¥5-50k tool fee | ¥500-5000/mo | ¥300k + 6 months |
| Auto-replacement | **Automatic** | Customer bears | – | Customer bears |
| Deployment | SaaS lease + self-hosted | Local only | SaaS only | Self-build |

### 8.2 Positioning

> **TG1 = "The Cloud of TG Marketing"**
>
> Competitors sell "control scripts" = sell physical servers
> TG1 sells "accounts + compute + AI" = sells cloud services

**Don't compete on price with orchestration tools** — we sell "end-to-end lead-gen + ongoing supply"
**Don't compete on models with AI service SaaS** — our value is "account inventory + engineering + sales collaboration"
**Differentiate on onboarding + ongoing operations** — customer math: self-build ¥300k vs lease ¥2,100/mo

---

## 9. Product Roadmap

### Completed (Stage 1-8 + part of Stage 9)

✅ Account full lifecycle / proxy pool / session management
✅ AI marketing / hype / keyword monitoring / interception
✅ CRM customer management / Inbox unified chat
✅ Dashboard / realtime monitoring / alerts
✅ pgvector vector retrieval + Vertex AI unified integration
✅ 1000+ account capacity expansion (code shipped, prod compose pending switch)

### Within 12 Months (Funding Cycle)

**Q1 (M1-M3) — PMF Validation**
- 🚧 Multi-tenant isolation (account pool per customer, quota management)
- 🚧 Self-service signup + billing (per account + usage)
- 🚧 Sales Copilot UI polish (AI on/off + draft suggestions + live summary)
- 🚧 Onboard 3-5 seed customers in private beta

**Q2 (M4-M6) — Commercial Launch**
- 📅 Multi-source KB import (PDF/Word/web/chat-history extraction)
- 📅 Negotiation stage modeling (need discovery → quote → bargain → close)
- 📅 Public launch + price-list rollout
- 📅 Target: 20+ paying customers, MRR > ¥100k

**Q3 (M7-M9) — Scaling**
- 📅 Auto-replacement mechanism (auto-replace banned accounts)
- 📅 Customer success system
- 📅 Target: 40+ paying customers, MRR > ¥200k

**Q4 (M10-M12) — Series A Prep**
- 📅 Multi-language expansion (RU/EN/AR)
- 📅 Multi-channel planning (WhatsApp / Discord)
- 📅 Target: 60+ paying customers, MRR > ¥300k, initiate Series A

---

## 10. Team

> *Placeholder — please fill with actual details*

### Current Team (Recommended Size: 3-4)

| Role | Responsibility | Background | Status |
|---|---|---|---|
| **Founder / CEO** | Strategy, commercialization, sales | 5+ yrs TG private-traffic / export | – |
| **CTO / Full-stack** | Architecture, platform engineering | 5+ yrs Python + distributed | – |
| **AI / Backend** | AI pipeline, RAG, risk control | 2+ yrs LLM application | – |
| **Ops / CS** | Account supply, customer support | TG marketing operations | – |

### Post-Funding Expansion (12 months)

Hire 2-3: 1 sales + 1 CS + 1 senior backend

---

## 11. Financial Projection

### 11.1 12-Month MRR Forecast (USD / CNY dual)

Exchange rate: 1 USD = 7.0 CNY; blended ARPU uses 50%/30%/20% plan mix.

| Month | Cumulative Customers | Blended ARPU (USD) | MRR (USD) | MRR (¥) | Cumulative ARR (¥) |
|---|---|---|---|---|---|
| M1-M3 | 3-5 (seed, half-price/free) | – | < $1k | < ¥7k | – |
| M4 | 10 | $ 250 | $ 2.5k | ¥17.5k | ¥210k |
| M6 | 25 | $ 280 | $ 7.0k | ¥49k | ¥590k |
| M9 | 45 | $ 300 | $ 13.5k | ¥95k | ¥1.13M |
| **M12** | **60** | **$ 308** | **$ 18.5k** | **¥130k** | **¥1.56M** |

### 11.2 12-Month P&L Forecast (¥ ten thousands / 万)

| Item | M1-M3 | M4-M6 | M7-M9 | M10-M12 | Full Year |
|---|---|---|---|---|---|
| Revenue | 0.5 | 7 | 20 | 35 | **62.5** |
| Direct cost (accounts + proxy + AI + CS) | 1 | 2 | 3.5 | 5.5 | 12 |
| **Gross profit** | -0.5 | 5 | 16.5 | 29.5 | **50.5** |
| People cost | 8 | 10 | 12 | 14 | 44 |
| Server & infra | 2 | 2 | 3 | 4 | 11 |
| Marketing acquisition | 1 | 4 | 6 | 8 | 19 |
| Other | 1 | 2 | 2 | 3 | 8 |
| **EBITDA** | -12.5 | -13 | -6.5 | 0.5 | **-31.5** |

**Key Milestones**:
- **M10-M12** approaching monthly EBITDA breakeven
- **Y2 Q1** sustained profitability, Series A prep
- **3-year blended gross margin 84%** is top-decile SaaS, thanks to ultra-low marginal cost on accounts + groups

> Note: Y1 EBITDA loss is normal for angel-stage PMF validation. ¥315k loss is within ¥500k raise.

---

## 12. Investment Plan

### 12.1 Round Terms

| Item | Detail |
|---|---|
| Round | Angel |
| Amount | **¥ 500,000 CNY (~$ 71,000 USD)** |
| Pre-money valuation | ¥ 4,000,000 |
| Post-money valuation | ¥ 4,500,000 |
| Equity offered | **11.1%** (negotiable 10-15%) |
| Runway | **12 months** |
| Board seat | Observer seat (non-controlling, no day-to-day decisions) |
| Anti-dilution | Weighted-average anti-dilution |

### 12.2 Use of Funds (¥500k / 12 months)

```
┌─────────────────────────────────────────────────────────┐
│  30%  Account Pool (¥ 150k)                             │
│       • Cumulative 2000 accounts purchased (SMS ¥30k)   │
│       • Warm-up period proxy + servers (¥80k)           │
│       • Reserve pool (¥40k)                             │
├─────────────────────────────────────────────────────────┤
│  25%  Team (¥ 125k)                                     │
│       • Founder + 1 co-founder 12-month sub-stipend     │
│       • Part-time AI / frontend engineer                │
├─────────────────────────────────────────────────────────┤
│  25%  Infrastructure (¥ 125k)                           │
│       • Servers (PG + Redis + Worker cluster) ¥50k      │
│       • Vertex AI Token (Embedding + LLM) ¥50k          │
│       • Premium residential proxies (IP2World) ¥25k     │
├─────────────────────────────────────────────────────────┤
│  15%  Marketing Cold Start (¥ 75k)                      │
│       • Industry-group placement / KOL ¥30k             │
│       • Content marketing / case studies ¥20k           │
│       • Crypto / cross-border events ¥25k               │
├─────────────────────────────────────────────────────────┤
│   5%  Reserve (¥ 25k)                                   │
└─────────────────────────────────────────────────────────┘
```

### 12.3 Exit Strategy

| Path | Timeframe | Notes |
|---|---|---|
| **Series A** | 12-15 months | Target raise ¥5-10M, valuation ¥30-50M |
| **Strategic M&A** | 3-5 years | Potential acquirers: CRM giants, Web3 infra, cross-border SaaS |
| **Continued dividend** | – | Early dividend possible (84% gross margin, fast payback) |

---

## 13. Risk & Mitigation

| Risk | Severity | Mitigation |
|---|---|---|
| **TG policy change / mass bans** | High | 4-role tiering + health score + ISP binding + auto-replacement; plan multi-channel (WhatsApp/Discord) |
| **Account supply source cut off** | Medium | Multi-platform SMS backup (SMS-Activate / 5sim / smshub); build small in-house registration |
| **AI cost increase** | Low | Already on Vertex optimal tier; plan self-hosted Qwen/Llama as fallback |
| **Compliance risk (data/marketing)** | Medium | Reject illegal customers; ToS prohibits gambling/scam use |
| **Competitor copies business model** | Medium | Account supply chain + warm-up engineering is high barrier; first-mover advantage locks head customers |
| **Customer willingness below expectation** | Medium | M1-M3 beta validates PMF; flexible pricing (Starter $199 lowers barrier) |
| **Founding team stability** | High | 4-year vesting + 1-year cliff; raise covers 12 months |

---

## 14. Appendix

### A. Technical Documentation Index

- [ARCHITECTURE.md](./ARCHITECTURE.md) — Technical architecture
- [STRATEGIC_PLAN.md](./STRATEGIC_PLAN.md) — 3D Matrix + AI Strategy
- [DEV_PLAN.md](./DEV_PLAN.md) — 9-stage development plan
- [TASKS.md](./TASKS.md) — Task list and acceptance criteria
- [REQUIREMENTS.md](./REQUIREMENTS.md) — Functional requirements
- [WEB_ACCEPTANCE_REPORT.md](./WEB_ACCEPTANCE_REPORT.md) — Web acceptance report

### B. Core Code Assets (for due diligence)

- Backend services: [backend/app/services/](./backend/app/services/) (50+ modules)
- API endpoints: [backend/app/api/v1/endpoints/](./backend/app/api/v1/endpoints/) (25+)
- DB migrations: [backend/alembic/versions/](./backend/alembic/versions/)
- Frontend pages: [frontend/src/pages/](./frontend/src/pages/) (25+)
- Deployment: [docker-compose.prod.yml](./docker-compose.prod.yml)

### C. Operating Data (to be filled)

- Current account pool size: [TBD]
- Current paying customers: [TBD]
- Current MRR: [TBD]
- Avg account lifecycle: [TBD]

### D. Contact

- Project Lead: [TBD]
- Email: [TBD]
- Telegram: [TBD]
- WeChat: [TBD]

---

> *This document is confidential and intended solely for qualified investors conducting due diligence. Unauthorized copying or distribution is prohibited.*
