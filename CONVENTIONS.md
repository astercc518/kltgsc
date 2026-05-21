# TG1.AI 项目约定（Conventions）

> 落盘日期：2026-05-21
> 用途：把"语言"统一了，再动代码。
> 配合 [DIAGNOSIS.md](DIAGNOSIS.md) 阅读——这份是"治"，那份是"诊"。
>
> 本文包含三张表：
> 1. **模块字典**：6 个稳定模块名替代 5 套混乱编号
> 2. **角色能力矩阵**：5 个 `role` 字段说清每个值的含义和消费方
> 3. **扣费路径图**：所有钱包/配额扣减点的统一对账视图
>
> ⚠️ 这只是「**约定**」，不是「**完成**」——表格里所有"应该"代表目标态，"现状"代表当下代码态。差异即技术债。

---

## 一、模块字典（Module Dictionary）

**约定**：以后讨论功能、写 commit message、写文档、起 issue 都用模块名（`[Tenancy]`、`[Billing]` 这种 prefix）。旧的 Epic 1-6/A-G/F1-5/W1-5 编号只在历史归档里出现。

### 6 个稳定模块

| Code | 模块名 | 职责一句话 | 覆盖旧编号 | 主要后端文件 | 主要前端入口 |
|---|---|---|---|---|---|
| `TEN` | **Tenancy** 多租户 | 客户/子用户/JWT/隔离 | Epic 1, 1.5, C1 | `models/customer.py`, `customer_user.py`, `auth.py` | `/portal/*` 登录注册 |
| `BIL` | **Billing** 计费 | 订阅 + 钱包 + 发票 + USDT + 配额 | Epic 2, 2.5, C2, W1-5 | `services/{billing,wallet,sales_wallet,feature_billing}_service.py`, `webhooks.py` | `/portal/billing`, `/portal/wallet`, `/sales/wallet` |
| `ALC` | **Allocation** 资源分配 | 账号/群组/AI persona 分配，role/tier/combat_role | Epic 3, 4.0, G | `services/{allocation,account_assignment,proxy_assigner}_service.py` | `/accounts`, `/portal/accounts`, `/sales/accounts` |
| `KBA` | **KnowledgeBase** 知识库 | 行业 KB + 客户 KB + 聊天历史 KB + 上传 + embedding + RAG | Epic 4.1, 5.1 | `services/{embedding,kb_retrieval,industry_kb,kb_upload}_service.py` | `/knowledge-bases`, `/portal/knowledge-bases` |
| `LED` | **LeadFlow** 线索流转 | Monitor 命中 / Bulk 回复 → Lead → claim → AI 接管 → Sales 接管 | Epic 5.2, A, B, D, E, F1-F5 | `services/{listener,bulk_reply,ai_reply,conversation_director}_service.py` | `/inbox`, `/sales/inbox`, `/sales/leads`, `/portal/leads` |
| `OPS` | **Ops** 运营看板 | Admin BusinessOps, 监控, impersonate | Epic 6, 主号 QR | `services/dashboard_service.py`, `admin_dashboard.py` | `/business-ops`, `/monitoring` |

### 编号映射回溯表

| 旧编号 | 模块 | 备注 |
|---|---|---|
| Epic 1 多租户 | `TEN` | Customer 表 + 6 表 customer_id FK |
| Epic 1.5 客户门户 | `TEN` + 各业务模块的 portal 视图 | `/portal/*` SPA |
| Epic 2 USDT 计费 | `BIL` | Subscription + Invoice |
| Epic 2.5 计费自动化 | `BIL` | 3 条 beat + NowPayments webhook |
| Epic 3.0 账号分配 | `ALC` | 套餐激活时自动分配 |
| Epic 4.0 行业 KB | `KBA` | LLM 生成 4 条行业 KB |
| Epic 4.1 客户 KB CRUD | `KBA` | portal UI |
| Epic 5.0 主号 QR 登录 | `ALC` + `LED` | 绑定主号；可选 MOCK |
| Epic 5.1 聊天历史 KB | `KBA` | 主号导入聊天 → 专属 KB |
| Epic 5.2 接管超时升级 | `LED` | Saved Messages 通知 |
| Epic 6 BusinessOps | `OPS` | 6 panels |
| Epic A 客户自助 Scrape | `LED`（产物是 BulkTarget，进而 Lead） + `BIL` | 钱包计费 |
| Epic B 客户邀请任务 | `LED` + `BIL` | `paused_no_funds` |
| Epic C1 销售坐席 | `TEN` | CustomerUser 模型 |
| Epic C2 SalesWallet | `BIL` | per-view 扣费 |
| Epic D 线索行业过滤 | `LED` | `Lead.industry/category` |
| Epic E 销售 SPA | `LED`（前端视图） | `/sales/*` |
| F1-F5 内部线索池 | `LED` | `is_internal_pool` + 原子 claim + industry filter + 快通道 |
| Phase G 销售自助 | `ALC`（账号分配给销售） + `LED`（Monitor） | `Account.assigned_to_sales_user_id` |
| W1-W5 Bulk Send | `BIL` + `LED` | 钱包驱动的群发 |

### Commit message 约定（建议）

```
[BIL] add idempotency to charge_wallet
[LED] write Lead.source='bulk' from bulk_reply_service
[ALC] retire combat_role 'bulk_sender' (use role='worker' + flag)
[TEN] CustomerUser support multi-role expansion (closes C1.next)
```

---

## 二、角色能力矩阵（Roles Matrix）

**约定**：5 个独立的 `role` 字段在 codebase 里互相不冲突，但**叙述时必须带表前缀**。比如说 "sales 用户" 是错的，必须说 "`User.role='sales'`（平台员工）" 或 "`CustomerUser.role='sales'`（客户坐席）"。

### 2.1 五个 role 字段一览

| 表 | 字段 | 类型 | 取值（实际） | 决定什么 |
|---|---|---|---|---|
| `user` | `role` | 平台员工岗位 | `admin` / `sales` / *（其他）* | API 入口权限（admin_*、sales_wallet 等） |
| `user` | `is_superuser` | bool | true/false | 与 role='admin' 并列，crm.py 同时检查两者——**冗余字段** |
| `customer_user` | `role` | 客户子用户类型 | `sales`（仅此一种） | 客户内部子账号身份；预留扩展 |
| `account` | `role` | TG 账号功能位置 | `worker` / `master` / `support` / `sales` / `listener` / `collector` / `main` | allocation / listener / proxy / 统计 |
| `account` | `combat_role` | TG 账号战斗角色 | `cannon` / `scout` / `actor` / `sniper` / **`bulk_sender`** | invite / workflow / AI reply / 对话调度 / intercept / bulk |
| `account` | `tier`（派生） | 阶级 | `tier1` / `tier2` / `tier3` | shill_dispatcher / permission_service |
| `sales_wallet` | `owner_type` | 钱包归属 | `customer_sales` / `platform_sales` | 决定钱包余额扣给谁 |

### 2.2 `Account.role` 完整含义（功能角色，**系统位置**）

由 [accounts.py:76](backend/app/api/v1/endpoints/accounts.py#L76) 定义，由代码各处消费：

| role 取值 | 含义 | 派生 tier | 谁会用它（消费点） |
|---|---|---|---|
| `master` | 主控号，特殊代理 | tier1 | [proxy_assigner.py:37](backend/app/services/proxy_assigner.py#L37) 单独代理；分配时排除大池 |
| `main` | 客户主号（QR 登录绑定） | tier1 | [allocation_service.py:103](backend/app/services/allocation_service.py#L103) 不参与分配；[dashboard_service.py:234](backend/app/services/dashboard_service.py#L234) 不算账号池容量；接管会话 |
| `support` | 辅助账号 | tier2 | [listener_service.py:677](backend/app/services/listener_service.py#L677) 与 listener 一起跑监听 |
| `sales` | 销售人设账号 | tier2 | 暂无独有消费点（仅供 UI 分类） |
| `collector` | KB 采集专用号 | tier2 | [allocation_service.py:102](backend/app/services/allocation_service.py#L102), [account_assignment.py:99](backend/app/services/account_assignment.py#L99) 全链排除；只采群消息进 KB |
| `listener` | 监听号 | tier3 | [listener_service.py:677](backend/app/services/listener_service.py#L677) 跑监听 |
| `worker` | 通用工作号（默认） | tier3 | 分配池里参与各种任务 |

**派生规则**（[accounts.py `_tier_for_role`](backend/app/api/v1/endpoints/accounts.py)）：
```
{master, main}              → tier1
{support, sales, collector} → tier2
其他                         → tier3
```

### 2.3 `Account.combat_role` 完整含义（战斗角色，**行为权限**）

`combat_role` 决定账号在 TG 上能"做什么动作"——和 role 是正交维度。

| combat_role 取值 | 含义 | 消费点 |
|---|---|---|
| `cannon` | 炮灰（默认） | qr_login_service 新建主号默认；conversation_director 概率最低 |
| `scout` | 侦察 | 一般用于探群 |
| `actor` | 演员 | [ai_reply_service.py:226-231](backend/app/services/ai_reply_service.py#L226) AI 回复匹配；[conversation_director.py:257-364](backend/app/services/conversation_director.py#L257) 对话优先；[intercept_service.py:163](backend/app/services/intercept_service.py#L163) 拦截 |
| `sniper` | 狙击 | [conversation_director.py:243](backend/app/services/conversation_director.py#L243); [intercept_service.py:155](backend/app/services/intercept_service.py#L155) 拦截 |
| **`bulk_sender`** | 群发专用号 | [bulk_dispatch_service.py:190](backend/app/services/bulk_dispatch_service.py#L190) **— 但 [account.py:32](backend/app/models/account.py#L32) 模型注释没列这个值，这是漂出来的** |

**workflow_engine.py 还有一个独立的 `COMBAT_ROLE_PERMISSIONS` 字典**控制哪些 combat_role 能跑哪些动作 ([workflow_engine.py:126-133](backend/app/services/workflow_engine.py#L126))。这是**第三套**关于 combat_role 的真相来源。

### 2.4 三个 sales 的语义区分（最容易踩坑）

| 出现位置 | "sales" 真正意思 | 谁会有这个值 |
|---|---|---|
| `User.role='sales'` | 平台公司的销售员工 | 平台招聘的销售（admin 在 User 表创建） |
| `CustomerUser.role='sales'` | 客户公司的销售坐席 | 客户在 `/portal/sales-users` 自己创建 |
| `Account.role='sales'` | 账号在群里扮演"销售人设" | 任何 TG 账号都可以被标记 |
| `SalesWallet.owner_type='customer_sales'` | 客户销售个人钱包 | 与 `CustomerUser.id` 关联 |
| `SalesWallet.owner_type='platform_sales'` | 平台销售个人钱包 | 与 `User.id` 关联 |

**叙述规范**：
- ✅ "平台销售"、"客户坐席"（带定语）
- ✅ "`User.role='sales'`"（带表名）
- ❌ "sales 用户"、"销售"（不指明）

### 2.5 当前矩阵的 4 个不一致点（技术债登记）

1. **`bulk_sender` 漂移**：实际使用了第 5 种 combat_role，但模型注释 + 模型字段都不知道
2. **`tier` 是派生但被持久化**：[account_tasks.py:180](backend/app/tasks/account_tasks.py#L180) 用 `account.tier = _tier_for_role(role)` 写库。如果 role 变了 tier 不会自动更新——**有真相分裂风险**
3. **`User.role` vs `User.is_superuser` 同时被检查**：[crm.py:153-235](backend/app/api/v1/endpoints/crm.py#L153) 等多处用 `or` 检查两者——应统一为单一 source of truth
4. **`COMBAT_ROLE_PERMISSIONS`、`COMBAT_ROLE_CONFIG`、模型注释**三处都在描述 combat_role 的元数据——三方不同步是迟早的事

---

## 三、扣费路径图（Billing Flow Map）

**约定**：每一个"花客户钱/扣额度"的动作必须找到自己在这张表里的位置。新功能开发前先填表。

### 3.1 三层结算体系（先看这个）

```
┌─────────────────────────────────────────────────────────┐
│  Layer 1: Subscription Quota（套餐配额，硬上限）          │
│  写入：billing_service.activate_invoice()              │
│  字段：customer.{account,group,token,seat}_quota       │
│  消费：allocation / customer_sales_users               │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  Layer 2: CustomerWallet（客户共享钱包，按条扣）           │
│  入金：客户 topup USDT / admin credit                   │
│  出金：bulk send / scrape / invite / customer_sales view │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  Layer 3: SalesWallet（销售个人钱包，按 view 扣）          │
│  入金：customer_sales 自己 USDT topup / admin credit    │
│  出金：sales 看线索 view 费                              │
└─────────────────────────────────────────────────────────┘
```

### 3.2 配额（Quota）侧

| 配额字段 | 上限来源 | 实际消费点 | 超额行为 | 现状评估 |
|---|---|---|---|---|
| `customer.account_quota` | [billing_service.py:239](backend/app/services/billing_service.py#L239) 订阅激活写入 | [allocation_service.py:184](backend/app/services/allocation_service.py#L184) 分配 top-up 时检查 | 停止分配新账号 | ✅ 闭环 |
| `customer.group_quota` | 同上 | [allocation_service.py:261](backend/app/services/allocation_service.py#L261) | 停止分配新群 | ✅ 闭环 |
| `customer.seat_quota` | 同上 | [customer_sales_users.py:48,70,124](backend/app/api/v1/endpoints/customer_sales_users.py#L48) 创建/删除坐席时增减 | 拒绝创建新坐席 | ✅ 闭环 |
| `customer.token_quota` | 同上 | **无消费点**（grep 全空） | **无超额行为** | ⚠️ **空头支票**——quota 写入但没人扣 |
| `feature_registry.usage_limit` | feature_billing 单独表 | [feature_billing.py:117 check_can_afford](backend/app/services/feature_billing.py#L117) | 拒绝执行 | ⚠️ 与上面 quota 系统并行存在，**两套体系** |

### 3.3 CustomerWallet（客户共享钱包）

入口在 `wallet_service.py`：

| 动作 | 入口 | 写入 | 类型(`WalletTransaction.type`) |
|---|---|---|---|
| 客户充值（USDT） | `create_topup_invoice` → NowPayments webhook → `credit_wallet_from_invoice` | balance + amount | `topup` |
| Admin 手动 credit | `admin_credit_wallet` | balance + amount | `admin_credit` |
| 扣费 | `charge_wallet` | balance − amount | (由调用方传入，常见: `bulk_send`, `scrape`, `invite`) |

**charge_wallet 的调用者**（每个动作都应该带 `idempotency_key`）：

| 调用方 | 触发场景 | 单价来源 |
|---|---|---|
| Bulk Send（W2） | 每条群发消息 | feature_registry `bulk_send` 单价 |
| Scrape Batch（A） | 每个抓取到的成员 | feature_registry `scrape` 单价 |
| Invite Task（B） | 每次邀请尝试 | feature_registry `invite` 单价 |
| Customer-sales view lead | 客户的销售看自己客户的线索 | feature_registry `lead_view` 单价 |

> ⚠️ **不一致**：客户的销售（`CustomerUser`）看 lead 时，扣的是**客户共享钱包**还是**销售个人钱包**？
> - DIAGNOSIS §2-3 的结论：扣客户共享钱包
> - 但 [sales_wallet_service.py:71 `create_topup_invoice_for_customer_sales`](backend/app/services/sales_wallet_service.py#L71) 确实存在，意味着 `customer_sales` 钱包**会有余额**
> - **真相**：两条路径都存在，要么是客户为坐席预付（坐席自充），要么是客户共享钱包代付。**当前代码到底走哪条没看清，待沿 charge_sales 调用链确认**。

### 3.4 SalesWallet（销售个人钱包）

入口在 `sales_wallet_service.py`：

| 动作 | 入口 | owner_type | 谁触发 |
|---|---|---|---|
| 客户销售充值 USDT | `create_topup_invoice_for_customer_sales` | `customer_sales` | CustomerUser 自己 |
| Admin 给平台销售充值 | `admin_credit_platform_sales` | `platform_sales` | admin 操作 |
| 扣费（per-view） | `charge_sales` | 任一 | sales 在 `/sales/leads/:id` 点开 |

> ⚠️ **不对称**：客户销售（customer_sales）有 USDT topup 路径，但**平台销售（platform_sales）没有 topup 路径**，只能 admin credit。这是设计选择还是漏做？需要明确。

### 3.5 一个动作可能触发多层扣费的场景

| 动作 | Quota 影响 | CustomerWallet 影响 | SalesWallet 影响 | 备注 |
|---|---|---|---|---|
| 客户激活订阅 | 写入 4 个 _quota 字段 | 不动 | 不动 | 升级套餐会覆盖原配额 |
| 客户上传 KB 文件 | 不动 | 不动 | 不动 | 走 KB 路径，未扣费——**或许应该按文件大小扣？** |
| 客户的销售看一个 Lead | 不动 | -X¢（lead_view 单价）？ | 或 -X¢（customer_sales 钱包）？ | **二义性，待确认** |
| 平台销售看一个 Lead（内部池） | 不动 | 不动 | -X¢（platform_sales 钱包） | ✅ 清晰 |
| 客户起一个 Bulk Send 批次 | 不动 | -Σ（每条消息单价） | 不动 | 余额不足 → `paused_no_funds` |
| 客户起一个 Scrape 批次 | 不动 | -Σ（每个成员单价） | 不动 | 同上 |
| AI 自动回复一条消息 | **应消费 token_quota 但实际不消费** | 不动 | 不动 | ⚠️ Token 黑洞 |
| 接管会话超时升级 | 不动 | 不动 | 不动 | LeadFlow 内部，无钱涉及 |

### 3.6 当前 Billing 体系的 5 个不一致点

1. **`token_quota` 是空头支票**：订阅激活写了但全代码没人消费，LLM 调用走 `LLMUsage` 表只统计不限额 ⚠️
2. **`feature_registry.usage_limit` vs `customer.*_quota`**：两套配额体系并行，未来某个功能同时被两边定义不一致就乱
3. **customer_sales 钱包归属二义**：能 topup 又能被共享钱包代付，调用链未画清
4. **NowPayments webhook 不验签**（[project_epic25_45_state.md](/root/.claude/projects/-var-tgsc/memory/project_epic25_45_state.md)）+ admin 手动激活 = 双入账路径
5. **idempotency_key 不统一**：`wallet_service.charge_wallet` 和 `sales_wallet_service.charge_sales` 都收 idempotency_key 但调用方是否每次都传值未审计

---

## 四、给后续工作的三条铁律

读完这份约定，要落地的"以后这么做"规则：

### 铁律 1：所有新功能 PR 必须填**模块字典 + 角色矩阵 + 扣费表**

PR 模板（建议）：
```markdown
**模块**：[BIL] / [LED] / ...
**影响 role 字段**：account.role={} / combat_role={} / ...
**扣费动作**：消费 quota={} / wallet={} / 单价来源={}
```

### 铁律 2：新枚举值必须先写到模型，再在 service 里用

- `combat_role='bulk_sender'` 这种漂移**不许再发生**
- 强制做法：所有 `Field()` 带 `# values:` 注释 + 同目录写 `models/enums.py` 集中常量

### 铁律 3："sales" 这个词不许独立出现

- 永远写：`User.role='sales'` / `CustomerUser.role='sales'` / `Account.role='sales'` / `SalesWallet[platform_sales]` / `SalesWallet[customer_sales]`
- 文档、commit、对话、issue 全部照此规范

---

## 五、配合阅读

- [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) — 项目全景（业务/技术/进度）
- [DIAGNOSIS.md](DIAGNOSIS.md) — 混乱点诊断（问题清单）
- 本文 — 治理约定（语言统一）
