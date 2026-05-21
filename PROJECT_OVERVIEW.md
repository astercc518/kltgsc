# TG1.AI / TGSC — 项目全景梳理

> 落盘日期：2026-05-21
> 仓库：`/var/tgsc` · 主分支：`main` · 最近提交：`a6741c1` (Phase G)
> 本文为对仓库的全面审计，覆盖 业务/产品 · 技术架构 · 代码结构 · 进度与债务 四个维度。

---

## 1. 一句话总览

**TG1.AI** 是一个"账号即服务"（AaaS）SaaS：把养好的 Telegram 账号 + AI 客服 + 行业知识库 + 目标群库打包成月度订阅，客户从 $199/月起即可在 500–3000 个目标群里自动捕获并初谈线索，由客户自己的销售坐席（或平台销售）在内置工作台里接管成单。

- **公开品牌**：TG1.AI（Telegram Growth Intelligence），域名 `tg1.ai`
- **代码库名**：TGSC（Telegram Smart Control），仓库路径、镜像、内部脚本仍用此名
- **目标客户**：Crypto/Web3、跨境电商、B2B 外贸、游戏出海；年营销预算 ¥500K–¥2M、TG 已有活跃使用的项目
- **价值主张**：替代 6 个月 + ¥30K 的自养号成本、规避自建 Telegram bot/账号池的工程投入

---

## 2. 商业模式与定价

三档订阅，全部 USDT 计价（不接 Stripe，决策见 [memory](/.claude/projects/-var-tgsc/memory/project_payment_decision.md)）。

| 档位 | 月费 | TG 账号 | AI 目标群 | LLM Token | 销售坐席 |
|---|---:|---:|---:|---:|---:|
| Starter | $199 | 3 | 500 | 2M | 1 |
| Growth ⭐ | $299 | 5 | 1,000 | 5M | 2–3 |
| Pro | $599 | 10 | 3,000 | 15M | 5–10 |

- 加权 ARPU：**$308/月**，毛利率 **84%**，LTV/CAC ≈ 12×，回本期 < 1 个月（[memory](/.claude/projects/-var-tgsc/memory/project_business_model_aas.md)）
- 支付鏈：USDT TRC20/ERC20/BEP20，唯一识别 = `amount_crypto` 加随机尾数（避免冲突）
- 网关：[NowPayments](backend/app/api/v1/endpoints/webhooks.py) IPN webhook；为空时回退到 admin 手动激活
- 变量计费（W1–W5）：bulk 抓取/邀请/群发按条扣钱包余额，线索 view 也扣钱包

---

## 3. 三个用户角色 × 三套门户

| 角色 | 路由前缀 | localStorage token | 主要工作 |
|---|---|---|---|
| **Admin / 运营** | `/` （根） | `token` | 账号池/LLM 配置/客户审批/订阅手动激活/运营看板 |
| **Customer / 客户** | `/portal/*` | `tg1_customer_token` | 选档/绑主号/上传 KB/查看分配的账号与 AI 跑出的线索 |
| **Sales / 销售** | `/sales/*` | `tg1_sales_token` | 看 Inbox、按行业过滤认领线索、接管 AI 会话、用钱包扣 view 费 |

**统一登录**（commit `f1f87c2`，2026-05-20）：单一 `/api/v1/auth/login`，按 identifier 类型分叉返回不同 JWT；前端 `/login` 根据 token 类型重定向到对应 SPA 根。

**管理员 impersonate**（commit `9d2c8a5`）：admin 在用户列表点"登录该账号"打开新 tab，URL hash 形如 `#impersonate=<jwt>&role=<role>&to=<path>`，模块加载阶段（[App.tsx:85-103](frontend/src/App.tsx#L85-L103)）把 token 写到正确 key，再清掉 hash、挂载 React。

---

## 4. 已交付功能全景（Epic 1-6 + A-E + F1-F5 + G）

按 git 提交顺序追溯：

### 4.1 基础平台（Epic 1–6，commit `ef2e22b` 一次性合入，已稳定）

| Epic | 内容 | 关键证据 |
|---|---|---|
| **1** | 多租户（Customer 表 + 6 业务表 `customer_id` FK + 客户 JWT） | 迁移 `e1a2b3c4d5f6` |
| **1.5** | 客户门户 `/portal/*`（登录、注册、Dashboard、Billing、Accounts、Leads、KB 共 7 页） | [frontend/src/portal/](frontend/src/portal/) |
| **2** | USDT 订阅与发票（Subscription/Invoice 模型 + admin 手动激活） | 迁移 `f2b3c4d5e6a7` |
| **2.5** | 计费自动化（beat × 3：发票过期、订阅过期、续费提醒 + NowPayments IPN） | [billing_tasks.py](backend/app/tasks/billing_tasks.py)、[webhooks.py](backend/app/api/v1/endpoints/webhooks.py) |
| **3.0** | 账号自动分配（套餐激活时分配账号+群组+AI metadata 改造） | 迁移 `a3b4c5d6e7f8` |
| **4.0** | 行业 KB 自动生成（激活时 LLM 生成 4 条行业 KB + 768 维 embedding） | [embedding_service.py](backend/app/services/embedding_service.py) |
| **4.1** | 客户 KB CRUD/上传（portal UI 全量重写） | [customer_kb.py](backend/app/api/v1/endpoints/customer_kb.py)、[portal/pages/KnowledgeBases.tsx](frontend/src/portal/pages/KnowledgeBases.tsx) |
| **5** | 主号 QR 登录 + 聊天历史→专属 KB（P0 tenant filter）+ Saved Messages 通知 + 对接群超时升级 | 迁移 `d5e6f7a8b9c0`、[qr_login_service.py](backend/app/services/qr_login_service.py)（`MOCK_QR_AUTOACCEPT` 是可选 mock，**不在生产路径**） |
| **6** | Admin BusinessOps Dashboard 6 面板（MRR/funnel/pool/LLM/handover/customer health） | [admin_dashboard.py](backend/app/api/v1/endpoints/admin_dashboard.py)、[pages/BusinessOps.tsx](frontend/src/pages/BusinessOps.tsx) |

### 4.2 营销助手模块（Epic A–E，commit `bd1a17a`–`3589410`）

| 编号 | 名称 | 关键产物 |
|---|---|---|
| **A** | 客户自助抓取批次 + 钱包计费 | `ScrapeBatch` + `CustomerWallet` |
| **B** | 客户邀请任务 + `paused_no_funds` 自暂停 | [invite_tasks.py](backend/app/tasks/invite_tasks.py) |
| **C1** | 客户子用户/销售坐席 + 统一登录分叉 | `CustomerUser` 模型，迁移 `7a8b9c0d1e2f` |
| **C2** | 销售个人钱包（topup + 按 view 扣费 + admin credit） | `SalesWallet`（`owner_type=customer_sales\|platform_sales`） |
| **D** | 线索行业/品类 + 销售 view 扣费 | `Lead.industry/category` + [sales_leads.py](backend/app/api/v1/endpoints/sales_leads.py) |
| **E** | 销售工作台 `/sales/*`（第三套 SPA 路由树） | [frontend/src/sales/](frontend/src/sales/) |

### 4.3 内部线索池 + 自助化（F1–F5 + G，commit `107ff91`–`a6741c1`）

| 编号 | 名称 | 要点 |
|---|---|---|
| **F1** | 内部线索池边界 | `Customer.is_internal_pool` 标记；平台销售仅看池内线索 |
| **F2** | 原子 view+claim | `lead.claimed_at` 单条 SQL，防止双抢 |
| **F3** | 销售按行业过滤 + 月度批量充值 | `CustomerUser.industry_filter_json`、admin 批量 credit |
| **F4 + F5** | 内部池命中→Lead 快通道 + 运营 playbook | Monitor → Account assign → Lead capture → Sales claim 全链 |
| **G** | 销售自助 Monitor + 在被分配账号上做操作 | `Account.assigned_to_sales_user_id`，[sales_monitors.py](backend/app/api/v1/endpoints/sales_monitors.py)、[sales_accounts.py](backend/app/api/v1/endpoints/sales_accounts.py) |

---

## 5. 核心业务闭环

### 闭环 A：客户开通 → 线索回流

1. 客户在 `/portal/register` 注册（status=pending）
2. 在 `/portal/billing` 选档 → `Invoice(status=pending)` 生成 USDT 收款金额
3. 客户付款 / admin 手动 confirm → `Subscription.active` + `CustomerWallet` 初始化
4. 系统自动 `quick-provision` 分配 3/5/10 个账号、推送 customized profile（[admin_features.py](backend/app/api/v1/endpoints/admin_features.py)）
5. 客户上传 KB / 配置 Monitor → 监听服务持续抓取 → Lead 入池
6. AI 自动回复 → 超时未结束 → 移交给销售坐席

### 闭环 B：销售接管

- **平台销售（内部池）**：在 `/sales/leads` 看池内线索 → 点击进详情触发 view 扣费 → claim → 在 Inbox 接管会话（AI 转 draft 模式）
- **客户自己的销售**：登录后只看 parent customer 的线索；view 费扣的是客户共享钱包，不是个人钱包
- 接管超时升级：Customer 的主号会被 Saved Messages 通知（[main_account_notifier.py](backend/app/services/main_account_notifier.py)）

### 闭环 C：Bulk Send（W2 已完成，W3–W5 仍在演进）

1. 客户在 `/portal/bulk` 起批 → 估算成本 vs `CustomerWallet.balance`
2. 余额足 → Celery 抓取群成员到 `BulkTarget`，扣钱包
3. 客户筛 target → 创建 `SendTask` → 每条消息扣钱包
4. 余额 < 阈值 → `low_balance_notified_at` 写入 → 前端弹窗

---

## 6. 技术架构

### 6.1 进程拓扑

| 容器 | dev (`docker-compose.yml`) | prod (`docker-compose.prod.yml`) |
|---|---|---|
| nginx | alpine，反代前后端 | 同 dev |
| backend | uvicorn 单进程，热重载 | gunicorn 4 workers，无 reload |
| frontend | Vite 3000 | Vite build → nginx 静态 |
| worker (Celery) | 1 副本 | **3 副本 × concurrency=8 = 24 并发** |
| beat | 1（单例） | 1（单例） |
| listener | 1 shard（`LISTENER_SHARD_TOTAL=1`） | **5 shards**（按 `account.id % 5` 分片，每分片 ≤ ~200 Pyrogram 客户端） |
| redis | alpine，4GB maxmemory，noeviction | 同 dev（单实例，⚠️ 见风险） |
| db | SQLite 文件 | **pgvector/pg16，max_connections=500，shared_buffers=2GB** |

> Prod compose 已配齐，但目前线上仍跑 dev 形态。容量规划详见 [memory](/.claude/projects/-var-tgsc/memory/project_capacity_plan.md)。

### 6.2 后端代码结构（`backend/app/`，165 个 `.py`）

```
app/
├── main.py                  FastAPI app 工厂 + lifespan + 中间件
├── core/
│   ├── config.py            Pydantic Settings（DB/Redis/USDT/JWT/NowPayments）
│   ├── celery_app.py        16 条 beat schedule + 3 队列（default/high/low）
│   ├── db.py                pool_size=10 + max_overflow=10，pre_ping，1h recycle
│   ├── security.py          JWT + bcrypt + Redis JTI blocklist + 2FA (pyotp)
│   └── encryption.py        AES-256 加密 session_string 落盘
├── api/v1/
│   ├── __init__.py          挂载 ~45 个 router
│   ├── deps.py              get_current_user/admin/sales 依赖
│   └── endpoints/           按域分组：auth · customer_* · sales_* · admin_* · 共享
├── models/                  35+ SQLModel 表
├── services/                54 个 service 模块
├── tasks/                   13 个 Celery 任务模块
├── db/init_db.py            启动时 seed admin
└── sessions/                Telegram session 文件
```

**Router 分组**（详见 [api/v1/__init__.py](backend/app/api/v1/__init__.py)）：

- **Auth（3 路由）**：admin 登录、customer 注册/登录、unified `/auth/login`
- **Customer Portal（11 文件）**：`customer_resources/billing/kb/main_account/wallet/features/bulk/scrape/invite/sales_users` 等
- **Sales（4 文件）**：`sales_wallet/leads/monitors/accounts`
- **Admin Ops（7 文件）**：`admin_bulk/sales_wallet/dashboard/billing/features`
- **共享 / 编排（18 文件）**：`accounts/proxies/registration/tasks/marketing/warmup/ai/crm/logs/monitor/monitoring/invite/campaigns/source_groups/funnel_groups/personas/knowledge_bases/workflow/ws/webhooks`

### 6.3 前端代码结构（`frontend/src/`，76 个 `.ts/.tsx`）

```
src/
├── App.tsx                  统一路由树 + 3 个 SPA 子树挂载
├── main.tsx                 React 入口
├── pages/                   26 个 admin 页（AccountList/CRM/Dashboard/...）
├── portal/                  17 个 customer 页 + 独立 Layout/auth/api
├── sales/                   6 个 sales 页 + i18n（zh-CN/en）+ 独立 Layout/auth/api
├── components/              共享组件
├── services/api.ts          admin API 客户端（1621 行，单 axios 实例）
├── hooks/                   领域 hooks（useAccounts 等）
└── lib/queryClient.ts       React Query 配置
```

**栈**：React 18.2 + Vite 5 + AntD 6.2 + TypeScript 5.2 + Zustand 4.4 + React Query 5.17 + Axios + Recharts。

**三套独立 API 客户端**（[services/api.ts](frontend/src/services/api.ts) / [sales/api.ts](frontend/src/sales/api.ts) / [portal/api.ts](frontend/src/portal/api.ts)），各自从 localStorage 读对应 token，相互独立可共存。

**i18n**：目前仅 `/sales/*` 有 zh-CN/en 切换（自建 Context + STRINGS 表，未引第三方库），admin 与 portal 是中文硬编码。

### 6.4 数据模型

35+ 表，按域分：

- **核心**：`user / account / proxy`
- **租户**：`customer / customer_user / customer_wallet`
- **计费**：`subscription / invoice / sales_wallet / wallet_transaction`
- **业务**：`bulk_batch / bulk_target / scrape_batch / keyword_monitor / keyword_hit / lead / lead_interaction`
- **特性**：`feature_registry / customer_feature`
- **AI/KB**：`knowledge_base`（含 pgvector 768 维）、`group_message`、`ai_config`、`ai_persona`、`llm_usage`

**多租户**：`customer_id` FK 在 6 张核心业务表上（account、bulk_batch、scrape_batch、keyword_monitor、lead、knowledge_base），`NULL` 表示系统级（pre-multi-tenant 数据，仅 admin 可见）。

### 6.5 后台任务与调度（16 条 beat）

| 任务 | 频次 | 队列 | 作用 |
|---|---|---|---|
| `batch_heartbeat_check` | 5 min | default | 账号最近上线时间扫描 |
| `batch_deep_check` | 6 h | low | 真连 Pyrogram 校验账号 |
| `check_all_proxies_fast` | 30 s | high | TCP ping 全量代理 |
| `check_proxies_batch_task` | 1 h | low | 完整 geo + liveness |
| `rebalance_proxy_accounts` | 5 min | default | 代理粘性分配 + 溢出均衡 |
| `expire_pending_invoices` | 5 min | default | 30 min 未付发票自动过期 |
| `sweep_expired_subscriptions` | 1 h | default | 订阅过期处理 |
| `send_renewal_reminders` | 1 d | low | 续费 3 天前通知 |
| `scan_low_balance` | 10 min | low | 钱包低额报警 |

### 6.6 外部集成

| 服务 | 用途 | 文件 |
|---|---|---|
| Pyrogram | TG 协议 | `telegram_client.py`、`listener_service.py` |
| OpenTele | Telethon ↔ Pyrogram session 转换 | `session_converter.py` |
| Vertex AI Gemini | LLM + 768 维 embedding（统一走 Vertex，不走 AI Studio） | `llm.py`、`embedding_service.py` |
| OpenAI（fallback） | 多 provider 切换 | `llm.py`（通过 `AIConfig` 表） |
| NowPayments | USDT 收款 + IPN webhook | `webhooks.py` |
| MEGA / rarfile | tdata 批量导入 | `mega_importer.py` |
| IP2World | 代理地理校验 | `proxy_checker.py` |
| SMS-Activate | 新账号注册 SMS | `auto_register.py` |

### 6.7 迁移

23 条 Alembic 迁移，链式无 merge。memory 已引用的关键节点全部验证存在：

- `e1a2b3c4d5f6` — Epic 1 multi-tenant
- `f2b3c4d5e6a7` — Epic 2 USDT billing
- `a3b4c5d6e7f8` — Epic 3 allocation
- `d5e6f7a8b9c0` — Epic 5 main account
- `2b3c4d5e6f7a` — feature registry（链尾，2026-05-19）

`backend/legacy_migrations/`（7 个 .py 文件，Jan–Feb）是 pre-Alembic 时代的手写脚本，已废。
`migration_backup/`（pg14 dump 118 MB + 数据卷 151 MB，2026-05-17）是 pg14→pg16 升级前的安全快照，可归档。

---

## 7. 当前进行中工作（未提交）

`git status` 显示 9 个文件未提交，主题统一：**"role → tier 自动派生"重构**。

- 后端 [accounts.py](backend/app/api/v1/endpoints/accounts.py) 加入 `_tier_for_role()`：`{master, main} → tier1`、`{support, sales, collector} → tier2`、其他 → tier3；从 `RoleTagsUpdate` 与批量更新中删除手动 tier 参数；`VALID_ROLES` 加入 `"main"`
- 后端 [account_tasks.py](backend/app/tasks/account_tasks.py)：tdata 导入时账号先用 `imported_<uuid>` 占位手机号，状态检查时根据 device fingerprint 解析为真实 `+<phone>`
- 前端 [services/api.ts](frontend/src/services/api.ts)：`updateAccountsRoleBatch()` 去掉 tier 参数；上传相关方法补 `role` 参数
- 前端 `AccountList / AccountActions / AccountTable / AccountUploader / CombatRoleManager`：UI 去 tier 选择、改为 role 选择

**风险**：tier 仍被下游使用（shill_dispatcher / 权限服务）。如果 tier 在 phone 解析前就写入，权限判断可能错位（[account_tasks.py:92-95](backend/app/tasks/account_tasks.py#L92-L95) 有部分缓解逻辑）。**未补任何测试**。

---

## 8. 技术债与风险清单（按 impact/effort 排序）

| # | 项目 | 影响 | 工作量 | 建议时机 |
|---|---|---|---|---|
| 1 | **完成 role→tier 重构** — 前端 UI 收尾 + 验证所有权限点 + 至少补一个 e2e | 高（阻塞账号分配） | 中（1–2d） | 立刻 |
| 2 | **零前端测试** — `App.test.tsx` 只是一个 stub，三套 SPA 完全无回归保护 | 中 | 中（3–5d） | 下个 sprint |
| 3 | **无 CI** — 无 `.github/workflows/`，smoke 测试不在 PR 门 | 中 | 低（1d） | 本周 |
| 4 | **品牌名混用** — 根 `README.md` 仍叫"TGSC"，三份 doc 也是；公开品牌已切 TG1.AI | 低 | 低（1h） | 本周 |
| 5 | **Redis 单实例（prod）** — 1000+ 规模下 Celery 队列与 session 都压在一个实例上 | 中 | 中（2–3d） | 下个 sprint |
| 6 | **Listener 仍是单进程 in dev** — prod 已配 5 shard 但未切；目前实际跑的还是 dev 形态 | 中 | — | 与切 prod 同步 |
| 7 | **3 套独立 API client** — `services/api.ts` / `sales/api.ts` / `portal/api.ts` 各自维护 token 与 interceptor，分歧风险 | 低 | 中（2–3d） | 有空时 |
| 8 | **未用的 Zustand 依赖** — package.json 里有，代码里没引；React Query + localStorage 已够用 | 低 | 低（10min） | 立刻删 |
| 9 | **scratch 文件污染 backend/ 根** — `add_columns.py`、`reproduce_issue.py`、`test_mega_*.py`、`test_pyrogram_login.py` 等 ~5 个早期一次性脚本；11 个 `smoke_*.py` 是有用集成测试但应移到 `tests/smoke/` | 低 | 低（2h） | 本周 |
| 10 | **legacy_migrations/ + migration_backup/** — 历史归档，可移出 repo | 低 | 低（10min） | 本周 |

**额外观察**：
- 全 codebase 仅 3 个 TODO 注释（[auto_register.py:55](backend/app/services/auto_register.py#L55)、[billing_service.py:17](backend/app/services/billing_service.py#L17)、[dashboard_service.py:13](backend/app/services/dashboard_service.py#L13)），都不阻塞
- 没有 Stripe 残留代码（决策落实彻底）
- 没有重复实现（auth 合并、LLM 单一 provider 框架、KB 单路径都已统一）

---

## 9. 文档导航

- 用户手册（4 视角）：[docs/user_manual.md](docs/user_manual.md)
- 架构：[docs/architecture/](docs/architecture/)（ARCHITECTURE / REQUIREMENTS / MIGRATION_GUIDE）
- 规划：[docs/planning/](docs/planning/)（DEV_PLAN / STRATEGIC_PLAN / TASKS / TESTING / WEB_ACCEPTANCE_REPORT）
- 投资人材料：[docs/investor/](docs/investor/)（FINANCING / PITCH，中英双语 + PDF）
- 内部销售 playbook：[docs/internal_sales_playbook.md](docs/internal_sales_playbook.md)
- 数据资产：[docs/data/](docs/data/)（群清单 / 候选清单 / resolve 结果）

---

## 10. 一页摘要（给新人 / 给未来的自己）

- **是什么**：TG 账号 + AI 客服 + 行业 KB 的 SaaS，月度订阅 $199/$299/$599，USDT 收款
- **怎么跑**：FastAPI + Celery(3×8) + 5 listener shard + pgvector PG16 + Redis；3 套 SPA（admin / portal / sales）共用后端
- **做完了什么**：Epic 1–6（多租户/计费/分配/KB/接管/运营看板）+ Epic A–E（自助抓取/邀请/坐席/钱包/工作台）+ F1–G（内部池/自助 Monitor）
- **正在做**：role→tier 自动派生重构，9 文件未提交
- **最痛**：无 CI、零前端测试、prod compose 配齐了但还没切
- **下一刀切哪**：把进行中重构收尾 + 加最小 CI + 切 prod，三件事都属于"工作量小但解锁很多"
