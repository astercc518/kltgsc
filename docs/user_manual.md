# TG1.AI 使用手册

> Telegram Growth Intelligence — TG 群控 + AI 客服 SaaS 平台
> 文档版本：v1.0 · 编制日期：2026-05-19

---

## 目录

- [第一部分：系统总览](#第一部分系统总览)
- [第二部分：客户使用手册（Portal）](#第二部分客户使用手册portal)
- [第三部分：运营管理手册（Admin 后台）](#第三部分运营管理手册admin-后台)
- [第四部分：销售操作手册（Inbox + CRM）](#第四部分销售操作手册inbox--crm)
- [第五部分：集成开发者 API 文档](#第五部分集成开发者-api-文档)
- [附录](#附录)

---

# 第一部分：系统总览

## 1.1 产品定位

TG1.AI 是面向出海企业的 **Telegram 群控 + AI 客服 SaaS** 平台，提供"账号即服务"（AaaS, Accounts-as-a-Service）的订阅模式。客户购买套餐后，系统自动分配预热好的 TG 账号、关联目标群组、配置 AI 人设和行业知识库，全天候捕获群内潜在客户并由 AI 完成初谈，销售只在高意向时介入接管。

**核心能力**

| 能力 | 说明 |
|---|---|
| TG 账号池 | 平台维护 N 个预热账号，按订阅档位分配给客户使用，统一健康监控与代理调度 |
| AI 自动回复 | Gemini/GPT 驱动，结合知识库 RAG 检索，对潜客做 24/7 个性化首轮触达 |
| 销售副驾驶接管 | 销售可在 Inbox 一键接管 AI 会话，AI 切换为草稿建议模式，销售可改写后发出 |
| 客户专属 KB | 客户通过门户上传文档、导入主号聊天历史，自动切块向量化 |
| USDT 自动计费 | 三档订阅，TRC20/ERC20/BEP20 多链支付，NowPayments Webhook 自动激活 |
| 多租户隔离 | 所有业务表均带 `customer_id` 列，客户 JWT 隔离数据视图 |

## 1.2 商业模式（三档订阅）

| 套餐 | 月费（USDT） | TG 账号数 | 目标群配额 | LLM tokens/月 | 销售席位 |
|---|---:|---:|---:|---:|---:|
| **Starter** | $199 | 3 | 5 | 2,000,000 | 1 |
| **Growth** ⭐ | $299 | 5 | 10 | 5,000,000 | 2 |
| **Pro** | $599 | 15 | 30 | 15,000,000 | 5 |

加权 ARPU $308，毛利率 84%。支付仅接受 USDT（不接 Stripe），早期 MVP 可由运营手动开通。

## 1.3 用户角色

```
┌────────────────────────────────────────────────────────┐
│                     运营 (Admin)                       │
│   维护账号池 / 配置 LLM / 审核订阅 / 看 BusinessOps    │
└────────────────────┬───────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        ▼                         ▼
┌──────────────┐         ┌──────────────────┐
│   客户       │         │   销售           │
│   /portal/*  │         │   /inbox + /crm  │
│  9 个页面    │         │  接管 AI 对话    │
└──────────────┘         └──────────────────┘
```

| 角色 | 入口 | 主要工作 |
|---|---|---|
| **运营 / 管理员** | `/login`（Admin 后台 26 页） | 账号池、LLM 配置、订阅审核、整体监控 |
| **客户（订阅者）** | `/portal/login`（Portal 9 页） | 选套餐 / 看线索 / 维护 KB / 连主号 |
| **销售** | `/inbox`、`/crm` | 接管 AI 会话、跟进高意向 lead |
| **集成开发者** | Customer API (`/api/v1/customer/*`) | 通过 API 调用平台能力 |

## 1.4 系统架构总览

```
                ┌─────────────────────────────────────────┐
                │            Nginx (HTTPS)                │
                │   tg1.ai → 80/443 → frontend + backend  │
                └────────────────┬────────────────────────┘
                                 │
        ┌────────────────────────┴─────────────────────┐
        ▼                                              ▼
┌─────────────────┐                          ┌──────────────────┐
│  Frontend       │                          │  Backend (FastAPI│
│  React + Vite   │                          │   + SQLModel)    │
│  Admin + Portal │                          │  30+ endpoint    │
└─────────────────┘                          └────────┬─────────┘
                                                      │
                       ┌──────────────────────────────┼───────────┐
                       ▼                              ▼           ▼
                ┌────────────┐               ┌──────────────┐  ┌──────────┐
                │ PostgreSQL │               │   Redis      │  │ Celery   │
                │  pgvector  │               │  cache + bus │  │ Worker × │
                │  (768 维)  │               │              │  │ Beat     │
                └────────────┘               └──────────────┘  └──────────┘
                                                      │
                                              ┌───────┴─────────┐
                                              ▼                 ▼
                                       ┌──────────────┐  ┌──────────────┐
                                       │  Listener    │  │  Gemini      │
                                       │ (Pyrogram)   │  │  Vertex AI   │
                                       │ 接 TG 消息   │  │  LLM+Embed   │
                                       └──────────────┘  └──────────────┘
```

**容器布局**（`docker-compose.yml`）：`nginx / frontend / backend / worker / beat / listener / redis / db`。

---

# 第二部分：客户使用手册（Portal）

> 入口：`https://<domain>/portal/login`
> 9 个页面 · JWT 7 天有效（localStorage `tg1_customer_token`）

## 2.1 注册账户（Register）

**URL** `/portal/register`

**操作步骤**
1. 填写邮箱、密码（≥ 8 字符）、姓名（选）、公司名（选）、行业
2. 行业下拉支持：`crypto / e-commerce / B2B / gaming / MCN / other`
3. 点击"注册" → 后端 `POST /api/v1/customer/register`
4. 自动获得 JWT 并跳转到 Billing 页选套餐

**初始状态** `customer.status = pending`，未付费前所有业务功能受限。

## 2.2 登录（Login）

**URL** `/portal/login`

- 邮箱 + 密码 → `POST /api/v1/customer/login`
- 返回 JWT 存入 `localStorage.tg1_customer_token`，所有后续请求自动加 `Authorization: Bearer <token>`
- Token 过期或被撤销时返回 401，前端自动清 token 并跳回登录页

## 2.3 仪表盘（Dashboard）

**URL** `/portal/dashboard`

显示：

- 欢迎信息（姓名 + 公司 + 行业）
- 订阅状态横幅
  - 🔴 `pending`：提示去支付
  - 🟢 `active`：显示到期倒计时
- **4 项配额进度条**（数据每 15 秒自动刷新）

| 指标 | 含义 | 数据源 |
|---|---|---|
| TG 账号 | 已分配账号数 / 套餐限额 | `account` 表按 `customer_id` 计 |
| AI 目标群 | 已加入目标群数 / 套餐限额 | `source_group` 表 |
| 已捕获线索 | `lead.customer_id = me` 总数 | `lead` 表 |
| AI tokens | 本月 LLM 消耗 / 套餐配额 | `llm_usage` 月聚合 |

**关键 endpoint**
- `GET /api/v1/customer/quota` —— 实时配额 & 使用量
- `GET /api/v1/customer/me` —— 客户信息

## 2.4 计费与订阅（Billing）

**URL** `/portal/billing`

### 选购套餐

页面显示三张套餐卡片（Starter / Growth ⭐ / Pro），点击进入支付：

1. 选择**支付网络**：`TRC20` / `ERC20` / `BEP20`
2. 点 "Subscribe" → `POST /api/v1/customer/subscribe`
3. 弹出发票弹窗，展示：
   - 精确到 8 位小数的 USDT 金额（含支付转换损耗）
   - 收款地址 + 一键复制按钮
   - 二维码（可手机扫描）
   - 过期时间倒计时（通常 30 分钟）
4. 转账后弹窗每 5 秒轮询 `GET /api/v1/customer/invoices/{id}`
5. 链上确认（TRC20 约 1 分钟、ERC20 约 5 分钟）后 `status: pending → paid`，订阅自动激活

**激活后自动发生（admin 后端）**
- 账号池分配 N 个预热账号（按套餐档位）
- 默认目标群组绑定到 `customer_id`
- AI 配置：默认人设 + 默认 LLM 模型
- 行业 KB 自动生成（LLM 基于客户行业生成 4 条基础知识）

### 历史发票

页面下方显示发票表格（ID / 套餐 / 金额 / 网络 / 状态 / 创建时间）。可点开任意一张回看支付详情。

**关键 endpoints**
- `POST /api/v1/customer/subscribe` —— 创建订单
- `GET /api/v1/customer/invoices` —— 列表
- `GET /api/v1/customer/invoices/{id}` —— 单张
- `GET /api/v1/customer/subscription` —— 当前订阅

## 2.5 我的账号（Accounts）

**URL** `/portal/accounts`

只读列表，显示分配给客户的 TG 账号：

| 字段 | 说明 |
|---|---|
| ID | 账号内部编号 |
| 电话 | 脱敏显示（前 4 + 后 4，中间 ●●） |
| 状态 | `init` / `active` / `banned` / `spam_block` / `flood_wait` |
| 战斗角色 | `cannon`（输出）/ `scout`（侦察）/ `actor`（演员）/ `sniper`（狙击） |
| 健康分 | 0-100，<60 提示运营介入 |
| 最近活跃 | 最后一次操作时间戳 |

如果未分配（订阅未付）会显示提示并引导去 Billing 页。

**Endpoint** `GET /api/v1/customer/accounts`

## 2.6 线索（Leads）

**URL** `/portal/leads`

只读分页表格（每页 20 条）：

| 字段 | 说明 |
|---|---|
| ID | 线索编号 |
| TG 用户 | `@username` 或 first_name |
| 状态 | `new` / `contacted` / `replied` / `interested` / `converted` / `closed` |
| AI 启用 | 是否仍由 AI 处理（销售接管后变 false） |
| 最近互动 | 最后一条消息时间 |

状态颜色按销售漏斗着色，方便客户对当周 KPI 一目了然。

**Endpoint** `GET /api/v1/customer/leads`

## 2.7 知识库（Knowledge Bases）

**URL** `/portal/knowledge-bases`

这是客户**最常用**的页面，决定 AI 回复质量。三种添加方式：

### A. 手动创建 KB 条目

点 "New KB entry"，填表：

| 字段 | 必填 | 说明 |
|---|---|---|
| name | ✅ | 条目标题 |
| category | ✅ | 8 选 1：`custom / industry_overview / pain_points / use_cases / pricing / faq / objection_handling / case_study` |
| language | ✅ | `zh / en / 其他` |
| description | | 简介 |
| content | ✅ | 正文（Markdown 支持）|

提交后端 `POST /api/v1/customer/knowledge-bases/`，content 会被切块 + 调用 Gemini Embedding 入向量索引。

### B. 上传文档

点 "Upload document"，支持的格式：

- `.pdf`（最大 50MB）
- `.docx / .doc`
- `.txt / .md`

后端自动：
1. 文本提取（PyMuPDF / python-docx）
2. 按 512 token chunk 切片
3. 每片调 Gemini Embedding → 768 维向量
4. 入 `ai_knowledge_base.embedding`（pgvector HNSW 索引）

**Endpoint** `POST /api/v1/customer/knowledge-bases/upload`（multipart/form-data）

### C. 从主账号导入聊天历史

最强大的功能：把客户自己 TG 主号的群+私聊历史变成 KB。

**前置条件**：先在 [MainAccount 页](#28-主账号绑定main-account) 完成 QR 登录

操作：

1. 点 "Import from My Telegram"
2. 配置：
   - **Since**：从 N 天前的历史开始（默认 30）
   - **Dialog types**：勾选要拉的对话类型（`private / group / supergroup`）
   - **Max messages per chat**：单 chat 最多拉多少条（默认 500，None=全量）
   - **Cost cap (USD)**：LLM 抽取 Q&A 的预算上限（默认 $5）
3. 启动 → 后台 Celery 任务
4. 弹窗每 3 秒轮询进度，显示 `processed_chats / total_chats` 和 `qa_extracted`

**Endpoints**
- `POST /api/v1/customer/knowledge-bases/import-history`
- `GET /api/v1/customer/knowledge-bases/import-history/{task_id}/status`

> ⚠️ **温馨提示**：单账号短时间内高强度拉历史可能被 TG 风控踢下线。导入完成后建议主号 24h 不要再做密集采集。

### KB 表格视图

|  | 字段 | 说明 |
|---|---|---|
|  | name | 条目名 |
|  | category | 类别（见 A） |
|  | source | 来源：`manual / industry_template / file_import / qa_extracted / scraped` |
|  | updated | 更新时间 |
| 操作 | 👁 查看 / ✏ 编辑 / 🗑 删除 | 删除有二次确认 |

## 2.8 主账号绑定（Main Account）

**URL** `/portal/main-account`

客户绑定**自己的 TG 主号**到平台，仅用于：
- 从主号导入聊天历史→ KB
- 接收高意向客户告警（Saved Messages）
- 超时未接管时由主号代发兜底消息（如客户在 Settings 启用）

### 连接流程（QR 扫码）

1. 进入页面，点 "Connect via QR"
2. 后端 `POST /api/v1/customer/main-account/qr/start` 生成 QR 码
3. 显示 QR 图片 + 状态标签 `pending`
4. 客户用 Telegram 手机端 → 设置 → 设备 → 扫码登录
5. 前端每 2 秒轮询 `GET /qr/status`
6. 三种结果：
   - `success` → 绑定成功，显示连接时间
   - `password_required` → 弹窗输入两步验证密码 → `POST /qr/password`
   - `expired` → QR 过期（60 秒），需重新生成

### 安全保障

- session 文件用 **AES-256-GCM** 在数据库加密存储（[encryption.py](backend/app/core/encryption.py)）
- 客户可随时点 "Disconnect" 解绑，session 删除

**Endpoints**
- `POST /api/v1/customer/main-account/qr/start`
- `GET /api/v1/customer/main-account/qr/status?token=<>`
- `POST /api/v1/customer/main-account/qr/password`
- `GET /api/v1/customer/main-account`
- `DELETE /api/v1/customer/main-account`

## 2.9 设置（Settings）

**URL** `/portal/settings`

3 项关键配置：

| 配置 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `handover_group_link` | TG 群邀请链接 | 空 | AI 兜底时把客户引到这个群 |
| `takeover_timeout_minutes` | 滑块 1-30 | 5 | 销售多久没接管，AI 自动发兜底消息 |
| `notify_main_account` | 开关 | true | 高意向时是否给主号 Saved Messages 发告警 |

**典型场景**：客户设 10 分钟超时。AI 探测到高意向时，给主号发 Saved Messages（"Lead @xxx 高意向，赶紧来 Inbox 接管"）。10 分钟内销售没认领，AI 给潜客发 `handover_group_link`，引导加群继续后续转化。

**Endpoints**
- `GET /api/v1/customer/settings`
- `PATCH /api/v1/customer/settings`

## 2.10 群发服务（Bulk Send）

群发服务是 TG1 的"加量 SKU"：客户上传一份目标号码 / 用户名 CSV，平台用 worker 账号池批量私聊发送 + 监听回复，按条计费。
回复后自动落进 Inbox，AI 副驾驶 / 销售接管完全沿用现有管线。

详尽规格见 [docs/planning/bulk_send_spec.md](planning/bulk_send_spec.md)。

### 2.10.1 钱包（Wallet）

**URL** `/portal/wallet`

群发走预存钱包模型，不与订阅 quota 共享。

- **起充 $100**，最大单次 $50,000
- 充值赠送：$500 +2% / $1,000 +5% / $5,000 +10%
- USDT 链上结算（TRC20 / ERC20 / BEP20），webhook 自动确认后到账
- 余额跌破 **$20** 触发一次告警（WS + 主号 Saved Messages），下次充值后自动重置

**Endpoints**
- `GET /api/v1/customer/wallet` 余额 + 累计统计
- `POST /api/v1/customer/wallet/topup` 创建充值 invoice
- `GET /api/v1/customer/wallet/transactions` 流水分页

### 2.10.2 创建批次（New Batch）

**URL** `/portal/bulk/new`

四步走：

1. **填基本信息**：批次名 + 主消息模板 + 节流（min/max delay 秒数）
2. **上传 CSV**（可粘贴）：自动识别 `phone` / `tg_username` / `tg_user_id` / `name` / `country` 列；无 header 时按内容自动判断
3. **加 5+ 文案变体**：anti-spam 硬要求，发送时按权重随机抽
4. **实时成本预览**：右侧卡片显示当前 tier 单价、跨 tier 总价、余额是否够、不够时一键跳钱包充值

阶梯单价（按累计已花算）：

| 累计已发送量 | 单条价格 |
|---|---|
| 0 – 10,000 | $0.15 |
| 10,001 – 50,000 | $0.10 |
| 50,001 – 200,000 | $0.07 |
| 200,001+ | $0.05 |

创建后状态是 `draft`，未扣款。

### 2.10.3 启动 / 暂停 / 续跑（Lifecycle）

**URL** `/portal/bulk/{id}`

| 状态 | 描述 | 可做的操作 |
|---|---|---|
| `draft` | 草稿，未派发 | Start / Delete / 编辑变体 |
| `pending` | Dispatcher 排队中 | Pause |
| `running` | Worker 正在发送 | Pause |
| `paused` | 暂停（用户手动 / 余额不足 / 失败熔断） | Resume / 编辑变体 |
| `completed` | 全部 target 终态 | 查看历史 |
| `canceled` | 取消 | 查看历史 |

**Start 校验**：必须有 ≥ 5 个变体 + 钱包余额 ≥ 单条单价。
**Pause 是软暂停**：在跑的 worker 在下一条 target 之前退出。
**Resume 续跑** 仍然按当前 tier 单价。

### 2.10.4 收件箱（Inbox）

**URL** `/portal/bulk/inbox`

群发回复进 Inbox 的工作机制：

1. Worker 用账号池里的某个号给目标发 DM → 标记 `bulk_target.status='sent'` + 扣款
2. 对方回复 → Listener 命中 → 自动创建 Lead，`source='bulk'` `bulk_batch_id={id}` `status='replied'`
3. WebSocket 广播 `bulk_reply` 事件 → 前端 Inbox 实时刷新
4. 同一个 Lead 自动出现在 `/portal/leads` 主收件箱，AI 副驾驶 / 销售接管完整继承

按批次过滤（下拉框）可以快速看某次活动的转化率。

### 2.10.5 反 spam / 风控自动化

| 控制点 | 阈值 / 行为 |
|---|---|
| 文案变体最少 5 个 | 创建批次时可少，启动时强校验 |
| 单条最小延迟 | min/max delay 秒，每条 random 抽 |
| 失败熔断 | 单 worker 连续 5 次失败 → 整个 batch 自动 `paused`，pause_reason=`account_X_failure_burst` |
| 跨批次去重 | `UNIQUE(customer_id, tg_user_id)` — 同号 7 天内不会被两个批次重复打 |
| 余额耗尽 | Worker 扣款失败 → batch `paused`，pause_reason=`insufficient_balance` |
| 余额低告警 | < $20 触发，每次 dip 仅一次 |

### 2.10.6 Endpoints 速查

```
# Customer
POST   /api/v1/customer/bulk/preview-cost
POST   /api/v1/customer/bulk/batches
GET    /api/v1/customer/bulk/batches[?status=]
GET    /api/v1/customer/bulk/batches/{id}
DELETE /api/v1/customer/bulk/batches/{id}              # 取消 draft
POST   /api/v1/customer/bulk/batches/{id}/start
POST   /api/v1/customer/bulk/batches/{id}/pause
POST   /api/v1/customer/bulk/batches/{id}/resume
POST   /api/v1/customer/bulk/batches/{id}/variants     # 加变体
PUT    /api/v1/customer/bulk/variants/{vid}            # 改变体
DELETE /api/v1/customer/bulk/variants/{vid}            # 删变体
GET    /api/v1/customer/leads?source=bulk&bulk_batch_id={id}   # 收件箱

# Admin
GET    /api/v1/admin/bulk/batches[?status=&customer_id=]
GET    /api/v1/admin/bulk/metrics[?window_hours=24]    # 健康快照
POST   /api/v1/admin/bulk/batches/{id}/force-pause
POST   /api/v1/admin/bulk/batches/{id}/force-cancel
```

### 2.10.7 端到端 sanity check

部署后或演示前可一键体检：

```bash
docker exec -w /app -e PYTHONPATH=/app tgsc-backend-1 \
  python -m scripts.bulk_send_e2e_smoke
```

会覆盖：登录 → cost preview → 创建 batch → 变体 CRUD → 启动 → 等完成 →
模拟 inbound reply → 验证 Leads filter → admin metrics → 清理。
全过返回退出码 0。

### 2.10.8 当前限制（MVP）

- **真发模式**需要 `BULK_SEND_MOCK=0` + bulk 专属账号池就位；默认 `=1` 仅模拟（90% 成功率随机）
- 仅支持 **tg_user_id** 直发；`@username` / `phone` 真发要 `client.resolve_username` / `import_contacts`，会消耗 ResolveUsername 配额且容易撞 24h FloodWait — phase 4 解决
- 客户自带账号（BYOA）、API 接入、模板变量替换 — Phase 4+

---

# 第三部分：运营管理手册（Admin 后台）

> 入口：`https://<domain>/login`
> 26 个页面 · 角色 admin / sales / ops，JWT 24 小时

按职能分 5 组：账号池 / AI 内容 / 营销触达 / 客服销售 / 多租户运营

## 3.1 账号池管理

### 3.1.1 账号列表 [AccountList](frontend/src/pages/AccountList.tsx)

**URL** `/accounts`

**主要展示**：所有 TG 账号库存，可按 `status` / `role` / `customer_id` / `combat_role` 过滤。表格列：ID / 手机号 / 状态 / 角色 / 健康分 / 战斗角色 / 客户归属 / 最近活跃。

**典型操作**

| 操作 | 行为 |
|---|---|
| 上传账号 | 拖入 `.session` 或 tdata 压缩包，自动解析手机号、设备指纹、API ID/HASH |
| 批量检查 | 选中 N 个 → `POST /accounts/batch/check` 异步派发 |
| 一键删异常 | 删除 `status IN (banned, spam_block, error)` 的全部账号 |
| 绑定 AI 人设 | 在详情抽屉里选 persona，下次回复就用该人设语气 |
| 改战斗角色 | `cannon` / `scout` / `actor` / `sniper`，影响营销策略匹配 |

**关键 endpoints**：`GET /accounts/`、`POST /accounts/batch/upload`、`POST /accounts/{id}/check`、`PUT /accounts/{id}/role`

### 3.1.2 自动注册 [AutoRegister](frontend/src/pages/AutoRegister.tsx)

**URL** `/auto-register`

**场景**：账号池库存不足时，调 SMS Activate API 批量注册新号。

**操作**
1. 在 [SystemConfig](#36-系统配置) 配置 SMS Activate API Key
2. 进入页面，设置：国家、数量、代理类型、API 凭证池
3. 点 "启动" → Celery `register_accounts_task`
4. 任务跑完，新号自动入库 `status='init'`，下一步走 [Warmup](#313-养号-warmup)

**Endpoints**：`POST /registration/start`、`POST /registration/proxies/refresh`

### 3.1.3 养号 [Warmup](frontend/src/pages/Warmup.tsx)

**URL** `/warmup`

**为什么要养号**：刚注册的号活跃度=0，直接发消息会被 TG 风控。需要 7-30 天模拟人类行为：加群、阅读消息、点赞、关注频道。

**操作流程**
1. 创建养号模板（如 "新号 7 日基础"）
2. 配置行为序列：第 1 天加 2 个群、第 2 天打开 1 条历史消息……
3. 创建养号任务 → 选账号 → 选模板 → 启动
4. Worker 按时序执行，每个动作随机延迟 30-180 秒

**典型模板**

| 模板名 | 用途 | 时长 |
|---|---|---|
| 新号 7 日基础 | 注册后立即跑 | 7 天 |
| Spam 解封后回温 | 状态从 spam_block 恢复后 | 3 天 |
| 长期保活 | 已 active 账号每周一次 | 1 天 |

**Endpoints**：`POST /warmup/templates`、`POST /warmup/tasks`、`GET /warmup/tasks`

### 3.1.4 代理池 [ProxyList](frontend/src/pages/ProxyList.tsx)

**URL** `/proxies`

**关键点**：每个 TG 账号必须挂一个独立 IP 代理，否则同 IP 多号会被关联封号。

**操作**

| 操作 | 说明 |
|---|---|
| CSV 批量上传 | 一行一条：`host:port:user:pass:type:country` |
| 同步 IP2World | 一键拉取付费代理服务的最新可用 IP |
| 批量检测 | 并发 ping 所有代理（live / dead） |
| 设置过期 | 给批次设到期日，过期前邮件提醒 |
| 清理过期 | 一键删过期代理（同步解绑账号） |

**Endpoints**：`POST /proxies/batch/upload`、`POST /proxies/batch/check`、`POST /proxies/sync/ip2world`

### 3.1.5 关键词监控 [MonitorPage](frontend/src/pages/MonitorPage.tsx)

**URL** `/monitor`

**功能**：在 TG 群里监听关键词，命中后自动触发响应（发消息 / 拉群 / 通知销售）。

**创建监控器**
1. 选目标群组（必须先在 [SourceGroupPage](#332-源群池) 录入）
2. 配置触发词：精准匹配 / 模糊匹配 / 正则
3. AI 联想关键词（点 "建议"，LLM 帮你拓展同义词）
4. 绑定响应：发指定脚本 / 绑定 AI 人设回 / 自由发言
5. 启用

**Endpoints**：`POST /monitor/`、`POST /monitor/suggest-keywords`、`GET /monitor/hits`

### 3.1.6 任务监控 [TasksPage](frontend/src/pages/TasksPage.tsx)

**URL** `/tasks`

实时展示 Celery 队列状态：

| 类别 | 说明 |
|---|---|
| Active | 正在执行的任务 |
| Reserved | 已被 worker 取走待执行 |
| Scheduled | 定时计划任务 |

可在任意 task 上点 "Revoke" 终止。

**Endpoints**：`GET /tasks/active`、`POST /tasks/{id}/revoke`

### 3.1.7 监控仪表板 [MonitoringDashboard](frontend/src/pages/MonitoringDashboard.tsx)

**URL** `/monitoring`

每 30 秒自动刷新的实时面板：

- 账号状态分布（active / banned / spam_block / stale）
- 高级风险告警（健康分 < 60 的账号）
- 手动触发深度检查按钮（绕过定时 beat）

**Endpoints**：`GET /monitoring/stats`、`POST /monitoring/trigger-check`

### 3.1.8 操作日志 [LogsPage](frontend/src/pages/LogsPage.tsx)

**URL** `/logs`

审计所有管理员动作（用户登录、账号变更、配置修改）。可按 `时间 / 动作 / 执行人 / IP` 过滤。用于事故追责。

**Endpoint**：`GET /logs/`

## 3.2 AI / 知识库 / 内容体系

### 3.2.1 AI 配置 [AIPage](frontend/src/pages/AIPage.tsx)

**URL** `/ai`

**功能**：管理 LLM 配置（支持 Gemini AI Studio / Vertex AI / OpenAI / 任意 OpenAI 兼容 API）。

**配置字段**

| 字段 | 说明 |
|---|---|
| name | 配置名（如 "默认 Vertex 配置"） |
| provider | `gemini` / `vertex` / `openai` |
| api_key | API Key（Vertex 时填项目认证 JSON 路径） |
| base_url | OpenAI 兼容 endpoint，gemini/vertex 留空 |
| model | 模型名（`gemini-2.5-flash` / `gpt-4` 等） |
| is_default | 是否作为系统默认 |
| is_active | 是否启用 |

**操作**

- 添加 / 编辑 / 删除配置
- 点 "测试连接" → 后端调一次小请求验证 key 有效性
- 点 "设为默认" → 全平台调用此配置

**Endpoints**：`GET /ai/configs`、`POST /ai/configs/{id}/test`、`PUT /ai/configs/{id}/default`

> ⚠️ **2026-05-19 现状**：Vertex（kltgsc 项目）+ AI Studio key 双双被 Google Trust & Safety 系统 suspend。当前 AI 客服功能暂停，等待账号申诉或更换 provider。已入库的 134K Q&A 不受影响，关键词召回仍然可用。详见 [附录 D · 已知问题](#d-已知问题)。

### 3.2.2 知识库管理 [KnowledgeBasePage](frontend/src/pages/KnowledgeBasePage.tsx)

**URL** `/knowledge-bases`

**Admin 视角**：可看**所有客户**的 KB（含 `customer_id IS NULL` 的全局 KB）。

**操作能力（比客户 Portal 多）**

- 触发主号采集：`POST /knowledge-bases/scrape/{account_id}`
- 触发 Q&A 抽取：`POST /knowledge-bases/extract-qa`（指定 chat_ids、window_size、concurrency）
- 全文搜索：`GET /knowledge-bases/search/content?q=...`
- 关联 / 解关联 Campaign：让特定 campaign 只检索特定 KB

**Endpoints**：见 [API 文档](#52-管理员-api)

### 3.2.3 AI 人设 [PersonaPage](frontend/src/pages/PersonaPage.tsx)

**URL** `/personas`

**用途**：定义 AI 客服的角色和说话风格。每个 TG 账号可绑一个 persona。

**Persona 字段**

| 字段 | 说明 | 示例 |
|---|---|---|
| name | 人设名 | "热心导师小李" |
| tone | 语气 | "亲和、专业、不急于推销" |
| forbidden_topics | 禁止话题 | ["政治", "宗教", "竞品价格"] |
| required_keywords | 必含关键词 | ["KOL变现", "私域"] |
| sample_dialog | 示例对话 | （供 LLM few-shot 学习）|

**使用统计**：每个 persona 显示对话总数、回复率、用户回复率。

**Endpoints**：`POST /personas/`、`PUT /personas/{id}`

### 3.2.4 营销话术脚本 [ScriptPage](frontend/src/pages/ScriptPage.tsx)

**URL** `/scripts`

**用途**：预写多角色的群发对话脚本，由账号轮流执行（A 号说一句 → B 号附和 → C 号下单），制造"群里有人讨论"的氛围。

**两种生成方式**

1. **手写**：填角色对话表
2. **AI 生成**：从已选 personas + 营销目标 → 一键生成脚本草稿，再人工微调

**Endpoints**：`POST /script/`、`POST /script/{id}/generate`、`POST /script/generate-from-personas`、`POST /script/tasks`

## 3.3 营销与触达

### 3.3.1 战役 [CampaignPage](frontend/src/pages/CampaignPage.tsx)

**URL** `/campaigns`

**Campaign = 一个营销目标的组合体**：关联 persona、目标群池、KB、预算上限。

**字段**

| 字段 | 说明 |
|---|---|
| name | 战役名 |
| persona_id | 用哪个人设回复 |
| daily_budget_usd | 单日 LLM token 预算 |
| max_accounts | 最多用多少账号执行 |
| allowed_roles | 允许执行的战斗角色 |

**Dashboard**：每个 campaign 展示 KPI：发出消息数 / 收到回复数 / 回复率 / 高意向转化数 / LLM 成本。

**Endpoints**：`POST /campaigns/`、`GET /campaigns/{id}/dashboard`

### 3.3.2 源群池 [SourceGroupPage](frontend/src/pages/SourceGroupPage.tsx)

**URL** `/source-groups`

**用途**：维护"目标群组库" —— 我们要去采集成员、监听关键词的群。

**字段**

| 字段 | 说明 |
|---|---|
| group_link | TG 群链接（`https://t.me/xxx` 或邀请链接）|
| chat_id | TG 内部 ID（自动解析） |
| risk_level | 风险等级（low/medium/high） |
| theme | 主题分类（如"出海博彩"、"crypto trading"） |
| member_count | 群成员数 |

**操作**

- 添加 / 批量导入
- 点群进入详情 → 触发"采集成员" → 调 [scraper.py](backend/app/services/scraper.py)
- AI 分析群组：让 LLM 读群名+置顶+最近 50 条消息 → 推断主题、风险、价值

**Endpoints**：`GET /source-groups/`、`POST /source-groups/{id}/scrape`

### 3.3.3 转化漏斗群 [FunnelGroupPage](frontend/src/pages/FunnelGroupPage.tsx)

**URL** `/funnel-groups`

**用途**：自有的"承接群"——已转化客户加进来做后续运营。

**配置**

- 关联 campaign
- 欢迎语模板（新人加群自动私聊）
- 自动踢广告：发链接 / 长串数字立即踢

**Endpoint**：`GET /funnel-groups/`

### 3.3.4 群成员采集 [Scraping](frontend/src/pages/Scraping.tsx)

**URL** `/scraping`

**功能**：用账号加群 + 采集群成员到 `target_user` 表。

| 操作 | 说明 |
|---|---|
| 单加群 | `POST /scraping/join` |
| 批量加群 | `POST /scraping/join/batch`（N 个账号 × M 个群） |
| 单采群成员 | `POST /scraping/scrape` |
| 批量采群成员 | `POST /scraping/scrape/batch`，可设高级过滤（活跃用户、有头像、有 username） |
| 查任务 | `GET /scraping/tasks` |

### 3.3.5 群邀请 [InvitePage](frontend/src/pages/InvitePage.tsx)

**URL** `/invite`

**功能**：把采集到的 `target_user` 邀请到自己的漏斗群。

**配置**
- 选源（哪个 target_user 池）→ 选目标（漏斗群）
- 配置发送策略：每号每小时邀请上限、每邀请间隔秒数
- 启动后实时监控成功 / 拒绝 / 隐私限制 / 风控错误

**Endpoints**：`POST /invite/tasks`、`GET /invite/tasks/{id}/stats`

### 3.3.6 群发任务 [Marketing](frontend/src/pages/Marketing.tsx)

**URL** `/marketing`

**功能**：给采集到的目标用户批量发私聊营销消息。

**安全发送核心配置**

| 参数 | 说明 |
|---|---|
| max_per_account_per_hour | 单号每小时最多发几条 |
| min_delay / max_delay | 每条消息间隔（随机化） |
| rest_after_n | 发 N 条后休息几分钟 |
| working_hours | 只在客户当地 09:00-22:00 内发 |

**计划预览**：填好配置后点 "Plan"，前端展示"总发送条数 / 预计完成时间 / 风险评估"，确认后再启动。

**Endpoints**：`POST /marketing/plan`、`POST /marketing/tasks`、`POST /marketing/tasks/{id}/pause`

## 3.4 客服与销售（Admin 视角）

详见 [第四部分销售操作手册](#第四部分销售操作手册inbox--crm)。Admin 可看所有客户的 Inbox 和 CRM 数据，销售只能看自己客户的。

## 3.5 多租户运营 [BusinessOps](frontend/src/pages/BusinessOps.tsx)

**URL** `/business-ops`

**Epic 6 商务运营 Dashboard 6 面板**：

### Panel 1：KPI 总览
- 活跃客户数
- MRR（月经常性收入）
- 已分配账号数
- 当月新增 leads

### Panel 2：客户健康
表格列每个客户的：
- 订阅状态 + 到期日
- 配额使用率（账号 / 线索 / tokens）
- 最近活跃日
- 健康评分（系统自动算）

### Panel 3：线索漏斗趋势
日序列堆叠面积图：`new → contacted → replied → interested → converted → closed`，看每天每个阶段的 lead 数量。

### Panel 4：账号池构成
按 `status / role / health_score 区间` 切片饼图。

### Panel 5：LLM 成本
按日 + 按 provider 折线图。点开看每个 customer 的成本明细。

### Panel 6：销售接管统计
Epic 5.2 的核心指标：
- 平均接管响应时长
- 接管率（高意向 lead 中销售实际接管的比例）
- 转化率（接管后的 lead 最终 converted 比例）

**Endpoints**：`GET /admin/dashboard/overview`、`/customers`、`/lead-funnel`、`/account-pool`、`/llm-usage`、`/handover-stats`

## 3.6 系统配置 [SystemConfigPage](frontend/src/pages/SystemConfigPage.tsx)

**URL** `/system-config`

集中管理全局敏感配置：

| 配置 key | 用途 |
|---|---|
| `SMS_ACTIVATE_API_KEY` | SMS Activate 接码 |
| `SMTP_*` | 邮件通知 |
| `NOWPAYMENTS_API_KEY` / `IPN_SECRET` | USDT 支付网关 |
| `IP2WORLD_TOKEN` | 代理同步 |
| `TELEGRAM_API_*` | TG API 凭证池 |

修改管理员密码、查看当前登录用户、强制下线其他会话。

**Endpoints**：`GET /system/config`、`POST /system/config`、`POST /auth/change-password`

---

# 第四部分：销售操作手册（Inbox + CRM）

> 销售工作的"主战场"是 Inbox（实时对话）和 CRM（线索管理）。
> 设计哲学：**AI 副驾驶（Copilot）模式**——销售接管后 AI 不再发送，只提供建议草稿。

## 4.1 销售工作流总览

```
   AI 自动回复客户 ───────►  ❶ 检测到高意向
                              │
                              ▼
                ┌──────────── ❷ AI 推送告警到 Inbox ────────┐
                │                                            │
                ▼                                            ▼
        ❸ 销售在 CRM 看到火警标签          ❺ 销售看 Inbox 接收高意向弹窗
                │                                            │
                ▼                                            │
        ❹ 点"接管对话"按钮                                  │
        (ai_enabled=false + assigned_to=me)                  │
                │                                            │
                └─────────────► ❻ 进入 Inbox ◄──────────────┘
                                │
                                ▼
                    ❼ AI 持续生成建议草稿（不发送）
                                │
                                ▼
                ┌───────────────┼────────────────┐
                ▼               ▼                ▼
        "使用"草稿       "改写"重生        手工输入
                │               │                │
                └───────────────┼────────────────┘
                                ▼
                    ❽ 销售点"发送"，消息真正发出
                                │
                                ▼
                    ❾ 客户已成交 → "释放"线索 (ai_enabled=true)
```

## 4.2 AI 自动回复决策

每条客户消息进来，[ai_reply_service.py:74](backend/app/services/ai_reply_service.py#L74) 根据 `lead.ai_enabled` 决定行为：

| `ai_enabled` | 行为 |
|---|---|
| `true`（默认） | AI 直接发送回复，销售只能旁观 |
| `false`（接管中） | AI 生成草稿写入 `lead.ai_draft`，通过 WebSocket 推到销售前端，**不发送** |

## 4.3 Inbox 操作详解 [Inbox.tsx](frontend/src/pages/Inbox.tsx)

**URL** `/inbox`

### 4.3.1 左侧：会话列表

按"最近活跃倒序"排列所有 lead，每条显示：
- TG 头像 + first_name
- 最新消息预览
- 未读红点
- 火警标签（高意向）
- 接管中标签（assigned_to_user_id 非空）

### 4.3.2 中间：对话流

时间序展示历史消息，自己发的消息在右、客户的在左。底部有：

| 元素 | 行为 |
|---|---|
| 输入框 | 手动输入消息 |
| **使用按钮** | 把 AI 草稿 `ai_draft` 填入输入框（[Inbox.tsx:175-178](frontend/src/pages/Inbox.tsx#L175-L178)）|
| **改写按钮** | 调 `POST /crm/leads/{id}/regenerate-draft`，让 AI 重新生成草稿 |
| **发送按钮** | 调 `POST /crm/leads/{id}/message/send` 真正发出 |
| **AI 副驾驶开关** | Switch 控制 `lead.ai_enabled` ([Inbox.tsx:295-299](frontend/src/pages/Inbox.tsx#L295-L299)) |

### 4.3.3 右侧：Lead 详情卡片

- 状态、标签、AI 启用、认领人、首次接触时间
- 关联的 customer / campaign
- 标签编辑（销售可加标签做归类）

### 4.3.4 实时事件（WebSocket）

Inbox 连 `/api/v1/ws/<session>`，监听以下事件：

| 事件 type | 触发 | 前端动作 |
|---|---|---|
| `ai_draft` | AI 生成新草稿 ([ai_reply_service.py:80-84](backend/app/services/ai_reply_service.py#L80-L84)) | 更新右侧"建议草稿"卡片 |
| `high_intent_alert` | LLM 标记高意向 ([ai_reply_service.py:136-146](backend/app/services/ai_reply_service.py#L136-L146)) | 弹 `notification.open()` 火警 ([Inbox.tsx:69-78](frontend/src/pages/Inbox.tsx#L69-L78)) |
| `new_message` | 客户来新消息 | 左侧会话列表上浮 + 红点 |

## 4.4 CRM 操作详解 [CRM.tsx](frontend/src/pages/CRM.tsx)

**URL** `/crm`

**职责定位**：CRM 是 lead 全景视图（适合做归档、统计、批量操作），Inbox 是单对话深耕。

### 4.4.1 列表视图

| 列 | 说明 |
|---|---|
| Lead ID | 内部编号 |
| TG 用户 | first_name / username |
| 当前状态 | `new / contacted / replied / interested / converted / closed` |
| 接管状态 | "AI 中" / "销售认领: @xxx" |
| 标签 | 自定义 tags |
| 最近活动 | 最后一条消息时间 |
| 操作 | "接管对话"按钮 |

### 4.4.2 接管对话流程 ([CRM.tsx:247-249](frontend/src/pages/CRM.tsx#L247-L249))

点 "接管对话"按钮 → 调用 `handleClaimAndOpen()` ([CRM.tsx:269](frontend/src/pages/CRM.tsx#L269))：

1. `POST /crm/leads/{id}/claim` ([crm.py:134](backend/app/api/v1/endpoints/crm.py#L134))
2. 后端原子设置 ([crm.py:164](backend/app/api/v1/endpoints/crm.py#L164))：
   - `lead.assigned_to_user_id = current_user.id`
   - `lead.ai_enabled = false`
3. 如果 lead 已被他人认领且我不是 admin，返回 409 拒绝
4. 成功后前端自动跳转到 Inbox 并定位到该 lead

### 4.4.3 释放对话

如果客户成单或销售离场，可点"释放" → `POST /crm/leads/{id}/release`：
- 清空 `assigned_to_user_id`
- 恢复 `ai_enabled = true`
- AI 重新接管自动回复

## 4.5 高意向告警

### 4.5.1 告警链路

1. 客户消息进入 [ai_reply_service.py](backend/app/services/ai_reply_service.py)
2. 调 `llm.analyze_intent()` ([ai_reply_service.py:123-128](backend/app/services/ai_reply_service.py#L123-L128))
3. 返回结构 `{intent: "purchase", is_high_value: true, confidence: 0.85}`
4. `is_high_value=true` 触发：
   - WebSocket 广播 `high_intent_alert`
   - Celery `notify_high_intent.delay()` → 给主号 Saved Messages 发文字告警（如客户在 Settings 启用）
   - 设置 `takeover_deadline = now + customer.takeover_timeout_minutes`
5. 超时未接管 → Celery beat 触发"超时升级"，AI 给潜客发兜底引导（如 `handover_group_link`）

### 4.5.2 销售应对

收到 Inbox 弹窗后**5-10 分钟内**响应（具体取决于客户 Settings.takeover_timeout）：

1. 立刻 → CRM 找该 lead → 点"接管对话"
2. 进入 Inbox 看历史对话 + AI 建议草稿
3. 评估：
   - 草稿质量 OK → "使用" + 微调 + 发送
   - 草稿不行 → "改写"重生，或自己手写
4. 推动客户进入下一阶段（拉群、发资料、约电话）

## 4.6 AI 副驾驶建议草稿

### 4.6.1 何时生成

| 时机 | 触发 |
|---|---|
| 客户来新消息且 `ai_enabled=false` | 自动生成草稿写入 `lead.ai_draft` |
| 销售手动点"改写" | `POST /crm/leads/{id}/regenerate-draft` 强制重生 |

### 4.6.2 草稿质量影响因素

按权重排序：

1. 该 customer 的 KB 内容（RAG 检索召回 top-K）
2. 该 lead 的历史对话（前 10 条作为 context）
3. AI 人设 prompt（绑定到 account 的 persona）
4. 客户行业模板（注册时选的 industry 字段）

## 4.7 关于"实时摘要"

> ⚠️ **未实现**：[KB & 销售接管决策](memory) 中规划了 `lead.ai_summary` 字段（实时把对话摘要给销售看），但当前代码版本里 Lead 模型**没有这个字段**，[ai_reply_service.py](backend/app/services/ai_reply_service.py) 也没生成摘要的逻辑。预计在后续版本补全。

---

# 第五部分：集成开发者 API 文档

## 5.1 认证

### 5.1.1 客户 API 认证

**获取 Token**

```bash
curl -X POST https://<domain>/api/v1/customer/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "customer@example.com",
    "password": "your_password"
  }'
```

**响应**

```json
{
  "access_token": "eyJ0eXAiOiJKV1Qi...",
  "token_type": "bearer",
  "customer": {
    "id": 12,
    "email": "customer@example.com",
    "plan": "growth",
    "status": "active"
  }
}
```

**使用**

所有受保护接口加 header：

```http
Authorization: Bearer eyJ0eXAiOiJKV1Qi...
```

**有效期**：7 天，无 refresh token。过期需重新登录。

### 5.1.2 管理员 API 认证

```bash
curl -X POST https://<domain>/api/v1/login/access-token \
  -d "username=admin&password=xxx&totp_code=123456"
```

支持 TOTP 2FA（可在 `/auth/setup-2fa` 启用）。

## 5.2 客户 API（28 个端点）

### Auth & Profile ([customer_auth.py](backend/app/api/v1/endpoints/customer_auth.py))

| Method | Path | 说明 |
|---|---|---|
| POST | `/api/v1/customer/register` | 创建客户账号 |
| POST | `/api/v1/customer/login` | 登录换 JWT |
| GET | `/api/v1/customer/me` | 当前客户资料 |

### Billing & Subscription ([customer_billing.py](backend/app/api/v1/endpoints/customer_billing.py))

| Method | Path | 说明 |
|---|---|---|
| POST | `/api/v1/customer/subscribe` | 发起订阅，返回 USDT 发票 |
| GET | `/api/v1/customer/invoices` | 列出发票（分页） |
| GET | `/api/v1/customer/invoices/{id}` | 单张发票（轮询付款状态用） |
| GET | `/api/v1/customer/subscription` | 当前订阅信息 |

### Resources ([customer_resources.py](backend/app/api/v1/endpoints/customer_resources.py))

| Method | Path | 说明 |
|---|---|---|
| GET | `/api/v1/customer/quota` | 实时配额 + 使用量 |
| GET | `/api/v1/customer/accounts` | 已分配的 TG 账号 |
| GET | `/api/v1/customer/leads` | 已捕获的 leads |
| GET | `/api/v1/customer/settings` | 客户可调设置 |
| PATCH | `/api/v1/customer/settings` | 修改设置 |
| GET | `/api/v1/customer/knowledge-bases` | KB 条目列表 |

### Knowledge Base ([customer_kb.py](backend/app/api/v1/endpoints/customer_kb.py))

| Method | Path | 说明 |
|---|---|---|
| POST | `/api/v1/customer/knowledge-bases/` | 创建 KB 条目 |
| GET | `/api/v1/customer/knowledge-bases/{id}` | 获取条目 |
| PATCH | `/api/v1/customer/knowledge-bases/{id}` | 编辑 |
| DELETE | `/api/v1/customer/knowledge-bases/{id}` | 删除 |
| POST | `/api/v1/customer/knowledge-bases/upload` | 上传文件 (multipart) |
| GET | `/api/v1/customer/knowledge-bases/_meta/supported-types` | 支持的文件类型 |
| POST | `/api/v1/customer/knowledge-bases/import-history` | 从主号导入聊天 |
| GET | `/api/v1/customer/knowledge-bases/import-history/{task_id}/status` | 查导入进度 |

### Main Account ([customer_main_account.py](backend/app/api/v1/endpoints/customer_main_account.py))

| Method | Path | 说明 |
|---|---|---|
| POST | `/api/v1/customer/main-account/qr/start` | 生成 QR |
| GET | `/api/v1/customer/main-account/qr/status?token=` | 轮询 QR 状态 |
| POST | `/api/v1/customer/main-account/qr/password` | 提交 2FA 密码 |
| GET | `/api/v1/customer/main-account` | 主号绑定状态 |
| DELETE | `/api/v1/customer/main-account` | 解绑 |

### 调用示例：订阅 + 等待支付

```bash
# 1. 发起订阅
RESP=$(curl -X POST https://<domain>/api/v1/customer/subscribe \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"plan": "growth", "network": "TRC20"}')

INVOICE_ID=$(echo "$RESP" | jq -r '.id')
PAY_ADDR=$(echo "$RESP" | jq -r '.pay_address')
PAY_AMOUNT=$(echo "$RESP" | jq -r '.pay_amount')

echo "Send $PAY_AMOUNT USDT to $PAY_ADDR"

# 2. 客户转账后轮询确认
while true; do
  STATUS=$(curl -s -H "Authorization: Bearer $TOKEN" \
    https://<domain>/api/v1/customer/invoices/$INVOICE_ID | jq -r '.status')
  echo "Invoice status: $STATUS"
  [ "$STATUS" = "paid" ] && break
  sleep 30
done

echo "Subscription activated!"
```

## 5.3 管理员 API（190+ 端点）

完整清单见 [/api/v1/openapi.json](backend/app/api/v1/__init__.py)，关键模块：

### Auth & Users
- `POST /api/v1/login/access-token` — OAuth2 + TOTP 登录
- `POST /api/v1/logout` — 撤销 token
- `GET /api/v1/users/me`, `POST /api/v1/users/`, `POST /api/v1/users/change-password`

### Admin Billing
- `GET /api/v1/admin/customers` — 客户列表
- `GET /api/v1/admin/invoices` — 发票列表
- `POST /api/v1/admin/customers/{id}/activate-subscription` — 手动激活（链上 txn）
- `POST /api/v1/admin/customers/{id}/reallocate-accounts` — 重新分配账号配额
- `POST /api/v1/admin/customers/{id}/regenerate-kb` — 行业 KB 重生成

### Admin Dashboard
- `GET /api/v1/admin/dashboard/overview` — 总览
- `GET /api/v1/admin/dashboard/customers` — 客户健康
- `GET /api/v1/admin/dashboard/lead-funnel` — Lead 漏斗
- `GET /api/v1/admin/dashboard/account-pool` — 账号池
- `GET /api/v1/admin/dashboard/llm-usage` — LLM 成本
- `GET /api/v1/admin/dashboard/handover-stats` — 接管统计

### Accounts（账号池，~40 个端点）
覆盖增删改查、批量上传 session/tdata、状态检查、角色变更、人设绑定、批量任务派发。

### Knowledge Bases（admin 视角）
- `POST /api/v1/knowledge-bases/scrape/{account_id}` — 用账号采集群历史
- `POST /api/v1/knowledge-bases/extract-qa` — Q&A 抽取
- `GET /api/v1/knowledge-bases/search/content?q=` — 全文搜索
- `POST /api/v1/knowledge-bases/{kb_id}/link-campaign/{campaign_id}` — 关联

### CRM (销售)
- `GET /api/v1/crm/leads` — 列表
- `POST /api/v1/crm/leads/{id}/claim` — 接管
- `POST /api/v1/crm/leads/{id}/release` — 释放
- `POST /api/v1/crm/leads/{id}/send` — 发消息
- `POST /api/v1/crm/leads/{id}/regenerate-draft` — 重生草稿
- `PUT /api/v1/crm/leads/{id}/ai-config` — AI 开关

### AI Engine
- `POST /api/v1/ai/engine/generate-opener` — 开场白
- `POST /api/v1/ai/engine/generate-reply` — 回复
- `POST /api/v1/ai/engine/analyze-user` — 用户画像
- `POST /api/v1/ai/engine/analyze-group` — 群组画像
- `POST /api/v1/ai/engine/rewrite` — 改写

### Marketing / Scraping / Invite / Warmup / Campaign / Persona / Script / Source-Group / Funnel-Group / Monitor / Proxies
每个模块 5-15 个端点，涵盖完整 CRUD + 任务派发。

## 5.4 Webhooks（受信回调）

### NowPayments IPN ([webhooks.py](backend/app/api/v1/endpoints/webhooks.py))

**URL** `POST /api/v1/webhooks/nowpayments`

**签名验证**：请求头 `x-nowpayments-sig` = HMAC-SHA512(body, IPN_SECRET)

**流程**
1. NowPayments 检测到链上 USDT 到账
2. 调用此 webhook POST 订单 ID + 状态
3. 后端验证签名，找到对应 invoice
4. 若 `payment_status=finished`：
   - 把 invoice 标 `paid`
   - 找到 customer，激活其 subscription
   - 触发账号分配 + KB 生成

```bash
# 测试 webhook（开发环境）
curl -X POST https://<domain>/api/v1/webhooks/nowpayments \
  -H "Content-Type: application/json" \
  -H "x-nowpayments-sig: <hmac-sha512 of body>" \
  -d '{
    "payment_id": "...",
    "payment_status": "finished",
    "order_id": "invoice_42",
    "actually_paid": "299.00"
  }'
```

## 5.5 错误码

| HTTP | 含义 | 处理 |
|---|---|---|
| 200 | 成功 | - |
| 201 | 创建成功 | - |
| 400 | 请求参数错误 | 检查 body 格式 |
| 401 | Token 失效 | 重新登录获取 token |
| 403 | 权限不足 | 角色不对（如客户调 admin API） |
| 404 | 资源不存在 | 检查 ID |
| 409 | 冲突（如 lead 已被他人认领） | 提示用户或换策略 |
| 422 | 请求体 schema 校验失败 | 看 detail 字段 |
| 429 | 限流 | 退避重试 |
| 500 | 服务器错误 | 看 backend 日志 + 上报 |

## 5.6 WebSocket（实时事件）

**Connect**：`wss://<domain>/api/v1/ws/<session-id>`

**事件类型**

| type | payload |
|---|---|
| `new_message` | `{account_id, lead_id, message}` |
| `ai_draft` | `{lead_id, draft}` |
| `high_intent_alert` | `{account_id, lead_id, lead_name, intent, message}` |
| `task_update` | `{task_id, status, progress}` |
| `account_status_change` | `{account_id, old_status, new_status}` |

**前端示例**

```javascript
const ws = new WebSocket(`wss://${host}/api/v1/ws/${session}`);
ws.onmessage = (e) => {
  const data = JSON.parse(e.data);
  if (data.type === 'ai_draft') {
    setDraft(data.draft);
  } else if (data.type === 'high_intent_alert') {
    notification.open({
      message: '🔥 高意向客户',
      description: `${data.lead_name}: ${data.message}`
    });
  }
};
```

---

# 附录

## A. 名词表

| 术语 | 解释 |
|---|---|
| **AaaS** | Accounts-as-a-Service，账号即服务，TG1.AI 的核心商业模式 |
| **主号 / Main Account** | 客户自己的 TG 账号，QR 扫码绑定后用于历史导入和告警 |
| **Worker 号** | 平台预热好分配给客户的 TG 账号，做营销执行 |
| **战斗角色** | `cannon`（输出/发消息） `scout`（侦察/采集） `actor`（演员/对话） `sniper`（狙击/精准） |
| **副驾驶 / Copilot** | AI 接管后只生成草稿不发送，由销售确认发出 |
| **认领 / Claim** | 销售独占某 lead 的对话，自动关闭 AI 自动回复 |
| **释放 / Release** | 销售放弃 lead，AI 恢复自动回复 |
| **高意向告警** | LLM 标记 `is_high_value=true` 触发的 WebSocket 通知 |
| **handover_group_link** | 客户设置的承接群链接，AI 兜底时引导潜客加入 |
| **takeover_deadline** | 销售接管最后期限，超时后 AI 发兜底消息 |
| **KB / Knowledge Base** | 知识库，AI 回复时 RAG 检索的内容源 |
| **pgvector** | PostgreSQL 向量扩展，存 768 维 Gemini embedding |
| **HNSW** | 向量索引算法，pgvector 用它做近似最近邻搜索 |
| **Persona** | AI 人设，定义回复语气和风格 |
| **Campaign** | 营销战役，绑定 persona / KB / 预算 |
| **Source Group** | 源群池，要去采集成员的目标群 |
| **Funnel Group** | 漏斗群，承接转化后的客户 |
| **target_user** | 采集到的目标用户表 |
| **session_invalid** | TG 把 session 踢下线，账号需要重新登录 |
| **spam_block** | TG 因检测异常行为给账号的临时禁言（24h-7d 自动恢复） |
| **FloodWait** | TG 服务端限流，要求客户端等 N 秒 |
| **NowPayments** | USDT 收款网关，链上确认后回调激活订阅 |
| **JTI** | JWT 的唯一 ID，登出时存入黑名单 |

## B. 常见问题 FAQ

### B.1 客户常见问

**Q: 套餐买了多久能用？**
A: USDT 链上确认后（TRC20 约 1 分钟），系统自动分配账号 + 生成 KB，5 分钟内可用。

**Q: 账号被分配了能换吗？**
A: 不能自助换。如果分配的账号被封或不可用，联系运营，会自动从池子里补一个同档位的健康号。

**Q: KB 上传支持哪些格式？**
A: PDF / DOCX / TXT / MD，单文件 50MB 内。Excel/PPT 暂不支持，建议先转 PDF。

**Q: 我的主号会被封吗？**
A: 平台只读取你授权的对话，做历史导入和告警通知，不会用主号发营销消息。但**短时间高频导入大量历史**可能被 TG 风控暂时踢下线，建议导入完成后 24h 不要再做大量操作。

**Q: 销售看不到 leads 怎么办？**
A: 检查：①订阅是否激活；②你的账号是否真有加群在跑 AI 监听；③在 Settings 是否禁用了主号通知。

### B.2 销售常见问

**Q: 怎么知道哪条 lead 该我接管？**
A: ① Inbox 火警弹窗（最及时）；② CRM 列表里"高意向"标签的 lead；③ 主号 Saved Messages（如客户启用）。

**Q: AI 草稿不能用怎么办？**
A: 点"改写"重生（前提：客户对应的 KB 已配置好）。如果改写多次仍不行，说明 KB 内容不足，去客户的 KB 页补充语料后再让 AI 重新生成。

**Q: 接管后我能反悔吗？**
A: 可以。在 Inbox 把 AI 开关打开，或在 CRM 点"释放"，AI 恢复自动回复。

**Q: 一个 lead 我和同事都想接管怎么办？**
A: 谁先点谁拿到。后点的会得到 409 冲突错误。Admin 可强制夺权。

### B.3 运营常见问

**Q: 账号怎么批量进群？**
A: `/scraping` 页面 → "批量加群" → 选 N 个账号 × M 个群链接。后端单号每加 1 群间隔 2-5 秒，每群间 3-8 秒。预估时间 = N × M × 5s。

**Q: 一个号一次能采多少历史？**
A: 经验数据：约 100,000-300,000 条后 TG 会暂时 session 失效。建议单号一次任务 limit_per_chat=500，分批跑。

**Q: LLM 成本怎么控制？**
A: ①每个 customer 设 token 配额（Pro 档 1500万/月）；②BusinessOps Dashboard 看 LLM 成本面板；③在 AIPage 切换更便宜的模型（gemini-2.5-flash 比 gpt-4 便宜 10 倍）。

**Q: 客户付款没自动激活？**
A: 检查 NowPayments webhook 是否能正常打到 `/api/v1/webhooks/nowpayments`。如果 webhook 失败，可手动调 `POST /api/v1/admin/customers/{id}/activate-subscription` 传 txn hash 验证激活。

### B.4 集成开发者常见问

**Q: API 限流吗？**
A: 当前没有显式 rate limit，但 backend 单实例并发 ~50 QPS。如要更高，需要部署多 backend instance + 共享 Redis。

**Q: 能拿到 webhook 列表自己定义吗？**
A: 当前仅 NowPayments webhook 是 inbound。outbound webhook（让我们告诉你 lead 状态变化）暂未实现。可以通过 WebSocket 订阅事件流。

**Q: 怎么本地调试？**
A: `docker-compose up`，前端 `http://localhost:80/portal`，admin `http://localhost:80/login`。API 在 `http://localhost:80/api/v1/`。

## C. 数据流与状态机

### C.1 客户订阅状态机

```
        register
            │
            ▼
       ┌─────────┐
       │ pending │
       └────┬────┘
            │ subscribe + pay
            ▼
       ┌─────────┐    subscription expires    ┌───────────┐
       │ active  │ ─────────────────────────► │ suspended │
       └────┬────┘                            └─────┬─────┘
            │                                       │
            │  cancel / refund                      │  renew
            ▼                                       ▼
       ┌─────────┐                            ┌─────────┐
       │ cancelled│                            │ active  │
       └─────────┘                            └─────────┘
```

### C.2 TG 账号状态机

```
                    register / import
                          │
                          ▼
                     ┌─────────┐
                     │  init   │
                     └────┬────┘
                          │ check_account_status
                          ▼
                ┌─────────────────┐
                │  active (健康)  │
                └────┬──────┬─────┘
                     │      │
                     │      │ FloodWait > N
                     │      ▼
                     │ ┌────────────┐
                     │ │ flood_wait │
                     │ └─────┬──────┘
                     │       │ wait expires
                     │       ▼
                     │  (回到 active)
                     │
                     │ TG 检测异常
                     ▼
                ┌──────────────┐
                │ spam_block   │ ──── 7 天自动恢复 ────► active
                └──────────────┘
                     │
                     │ AUTH_KEY_UNREGISTERED
                     ▼
              ┌──────────────────┐
              │ session_invalid  │ ── 重新登录 ──► active
              └──────────────────┘
                     │
                     │ TG 永久封号
                     ▼
                ┌─────────┐
                │ banned  │
                └─────────┘
```

### C.3 Lead 状态机

```
   AI 首次回复
        │
        ▼
   ┌────────┐
   │  new   │
   └───┬────┘
       │  AI 发首条消息
       ▼
   ┌────────────┐
   │ contacted  │
   └─────┬──────┘
         │ 客户回复
         ▼
   ┌──────────┐
   │ replied  │
   └────┬─────┘
        │ LLM 判定高意向 / 销售认领
        ▼
   ┌────────────┐
   │ interested │
   └─────┬──────┘
         │
         │  成交                    流失
         ▼                            ▼
   ┌────────────┐              ┌─────────┐
   │ converted  │              │ closed  │
   └────────────┘              └─────────┘
```

## D. 已知问题（2026-05-19 快照）

### D.1 Google AI 账号 suspend（P0）

**现象**
- Vertex AI（kltgsc 项目）所有调用返回 `access_denied: Account Restricted`
- AI Studio API key 也被 suspend (`Consumer ... has been suspended`)
- 整条 Google AI 链路不可用

**影响**
- AI 自动回复 ❌
- AI 副驾驶建议草稿 ❌
- Embedding 生成 ❌（新 KB 入库会失败）
- 行业 KB 自动生成 ❌

**仍然可用**
- 已入库的 134K Q&A 通过关键词召回（中文 2-gram + ILIKE）✅
- 销售在 Inbox 手动回复（不依赖 AI）✅
- 所有 TG 操作（账号管理、群发、采集、加群、邀请）✅
- Portal 看线索 / 看配额 ✅

**处理状态**：等待 Google 账号申诉 + 评估更换 LLM provider（备选：DeepSeek / Anthropic / 本地 vLLM）。

### D.2 lead.ai_summary 未实现

[KB & 销售接管决策](memory) 中规划的"实时摘要"字段在当前代码版本不存在。销售接管时只能看到完整对话历史，没有 AI 生成的快速摘要。预计后续版本补全。

### D.3 主账号 QR 登录 Mock 模式

当前环境 `MOCK_QR_AUTOACCEPT=true`（开发模式），客户在 Portal 上发起 QR 登录会**自动 success** 而不需要真正扫码。生产部署前需设为 `false` 启用真实 QR 流程。

---

## E. 部署速查表

```bash
# 服务启停
docker compose up -d
docker compose down
docker compose restart <service>  # backend / worker / beat / listener

# 看日志
docker compose logs -f <service>

# 数据库连接
docker compose exec db psql -U tgsc_user -d tgsc_prod

# Celery 任务监控
docker compose exec backend python -c "
from app.core.celery_app import celery_app
print(celery_app.control.inspect().active())
"

# 数据库迁移
docker compose exec backend alembic upgrade head
docker compose exec backend alembic revision --autogenerate -m "msg"

# 重新激活 AI 配置
docker compose exec db psql -U tgsc_user -d tgsc_prod -c \
  "UPDATE ai_config SET is_active=true WHERE id IN (1, 2);"
```

## F. 联系与支持

- 内部 IM：在 Slack `#tg1-ops` 频道
- Issue Tracker：内部 Linear 工作区
- 紧急 P0 事故：电话直拨运营负责人

---

**文档版本历史**

| 版本 | 日期 | 修订 |
|---|---|---|
| v1.0 | 2026-05-19 | 初版发布，覆盖 Portal/Admin/Sales/API 全模块 |

