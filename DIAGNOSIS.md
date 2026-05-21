# TG1.AI 项目混乱点诊断

> 落盘日期：2026-05-21
> 这是一份"脸谱图"：只指出问题、不提交修改方案。
> 与 [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) 配合阅读。
>
> 用户反馈："目前项目需求和功能都很混乱"。我把混乱点全数排出，按四个层面分组。

---

## 根因总览（先看这个）

| # | 根因 | 受影响范围 |
|---|---|---|
| **R1** | **没有统一的"模块字典"**——5 套并行的编号体系（Epic 数字 / Epic 字母 / F系列 / G / W系列） | 文档、对话、git log |
| **R2** | **"角色"语义被复用到 5 张表上**——同名字段不同含义 | account / customer_user / user / wallet / 账号导入 |
| **R3** | **计费三层叠加**——订阅配额硬上限 + CustomerWallet 按条扣 + SalesWallet 按 view 扣，无统一对账视图 | 客户结算、销售扣费、运营对账 |
| **R4** | **进行中的重构没收尾**——role→tier 改了一半，前端 UI 与权限校验留尾巴 | 账号管理、权限判定 |
| **R5** | **入口多但出口不收口**——Monitor / Bulk 回复 / 主号 DM / Scrape 都能"产生信息"，但只有 Monitor 明确写入 `Lead`，其它路径模糊 | 销售工作台、漏斗看板 |

---

## 1. 需求/Epic 命名体系混乱

**现状**：5 套并行的编号体系散落在 commit message、memory、docs：

| 编号风格 | 实例 | 用在哪 |
|---|---|---|
| **整数+小数** | Epic 1 / 1.5 / 2 / 2.5 / 3 / 4 / 4.1 / 5 / 6 | 基础平台 |
| **大写字母** | Epic A / B / C1 / C2 / D / E | 营销助手 + 销售坐席 |
| **F 系列** | F1 / F2 / F3 / F4+F5 | 内部线索池 |
| **单字母** | Phase G | 销售自助 |
| **W 系列** | W1 / W2 / W3 / W4 / W5 | Bulk Send 子任务 |

**具体冲突点**：
- "Epic 2" 和 "W2" 完全无关，但乍看像同一序列
- "Epic 4" 和 "Epic 4.1" 是父子关系，但 "Epic A" 和 "Epic A.1" 没出现过——风格不统一
- "F4+F5" 是合并 commit，但 memory 还是当两个独立 Epic 描述
- C1/C2 用了 .1/.2 分裂，D 又不分——分裂规则不一致
- 销售工作台 SPA 路由 = Epic E，但销售自助 Monitor + 账号操作 = Phase G——同样是"销售能力"被分到两个不同编号系统

**外部能看到的影响**：
- 投资人材料 / DEV_PLAN / TASKS 里 Epic 编号需要逐句校对
- 跟新人介绍要花 5 分钟解释编号风格
- git log 看不出来"这个 commit 在产品地图的哪一格"

---

## 2. 角色 / 租户层级混乱（最严重）

**现状**：codebase 里有 **5 个独立的 "role" 字段**，名字相同但含义全不一样：

| 表 | 字段 | 取值 | 实际含义 |
|---|---|---|---|
| `user` | `role` | `admin` / `sales` / 其他 | 平台员工的岗位 |
| `customer_user` | `role` | `sales`（注释："only role for now; reserved for future expansion"） | 客户的子用户类型 |
| `account` | `role` | `worker` / `master` / `support` / `sales` / `listener` / `collector` / `main` | TG 账号的功能角色（7 种） |
| `account` | `combat_role` | `cannon` / `scout` / `actor` / `sniper` | TG 账号的战斗角色（4 种） |
| `account` | （派生 tier） | `tier1` / `tier2` / `tier3` | 由 `role` 派生出的"阶级"（in-progress 重构） |

**重叠/冲突点**：

1. **同一个 `Account` 行同时挂三个分类系统**：role（功能） + combat_role（战斗） + tier（派生）。
   - 三套分类的边界没说清楚：一个 `master` 战斗角色应该是什么？一个 `sniper` 功能角色应该是什么？
   - 进行中的 role→tier 重构（[accounts.py:76](backend/app/api/v1/endpoints/accounts.py#L76) `_tier_for_role`）只解决了 role↔tier 的派生，没碰 combat_role。

2. **"sales" 这个值被三处复用，含义都不一样**：
   - `User.role='sales'` = 平台内部销售员工
   - `CustomerUser.role='sales'` = 客户公司的销售坐席
   - `Account.role='sales'` = 账号本身在群里扮演"销售人设"
   - 权限判定时容易写错（比如 "用户是 sales" 到底指哪个？）

3. **钱包的 owner_type 又再造了一套角色枚举**（[sales_wallet.py](backend/app/models/sales_wallet.py)）：
   - `owner_type='customer_sales'`, `owner_id=CustomerUser.id`
   - `owner_type='platform_sales'`, `owner_id=User.id`
   - 但 agent 调研发现 README/playbook 里的描述是"客户的销售扣客户共享钱包，不是个人钱包"——而 SalesWallet 又开了 `customer_sales` 这个 owner_type，**是否真的会创建这种钱包记录，行为不清晰**。

4. **`collector` 角色是 memory 里手工补丁**（id=82 +85261894271）。[feedback_main_account_kb_only](/root/.claude/projects/-var-tgsc/memory/feedback_main_account_kb_only.md) 说 allocation/listener/shill/auto_reply 都跳过 collector——这是隐式约束，散落在多个 service 文件里，没有一个统一的"角色能力矩阵"声明。

5. **"impersonate" 让事情更复杂**：admin 通过 URL hash 切到任一角色，三套 token 在同一浏览器并存。哪个 SPA "当前活跃"取决于浏览器历史，权限错位的认知负担转嫁给用户。

---

## 3. 计费维度堆叠

**现状**：一个客户在一个月里同时被三层计费规则覆盖：

```
                       客户做一件事
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
  ① 套餐配额硬上限    ② CustomerWallet     ③ SalesWallet
  (Subscription)        (按条扣)            (按 view 扣)

  account_quota          抓取一条 = X¢       销售看一条 = Y¢
  group_quota            发一条   = Z¢
  token_quota            邀请一次 = W¢
  seat_quota
```

**具体冲突点**：

1. **同一个动作可能被多重计量**：
   - 销售看线索：扣 SalesWallet（per-view）+ 占用 customer 的 token_quota（如果触发 AI rewrite）
   - 客户 bulk send：扣 CustomerWallet（per message）+ 占用 token_quota（如果用 AI 拟稿）
   - 没有一个统一的"成本归集"视图

2. **配额（quota）与钱包（wallet）的语义重叠**：
   - `seat_quota` 限制销售数量——但销售数量本身又通过 SalesWallet 影响 customer 现金流
   - `token_quota` 是 LLM 使用上限——但客户 KB 检索、bulk send AI 写稿、销售辅助回复都会触发，且没有一个"为什么扣这么多 token"的归因
   - 两套上限并行：超 quota 会怎样？降级？拒绝？无明确策略

3. **三种钱包模型，余额来源不同**：
   - `CustomerWallet`（一个客户一份）：客户充值 + admin credit
   - `SalesWallet.owner_type=platform_sales`：admin 充值
   - `SalesWallet.owner_type=customer_sales`：来源不清，可能根本不会被创建
   - 当客户的销售扣费时，到底扣哪个？前面 agent 给的"扣客户共享钱包"和模型里有的 `customer_sales` 类型本身就矛盾。

4. **变量计费 W1–W5 编号穿插在 Bulk Send 内部**，但 W1（钱包基础）和 Epic 2（订阅）的边界没说清——MRR 报表是只算订阅，还是把 wallet topup 也算？

5. **NowPayments webhook 不验签**（[memory](/root/.claude/projects/-var-tgsc/memory/project_epic25_45_state.md)）+ admin 手动激活 = 两条入账路径并存，未来一定会出"发票收两次款"。

---

## 4. 业务入口与"线索"出口不收口

**现状**：能产生"客户信息"的入口有 5 个，但只有一个出口（`Lead` 表）：

| 入口 | 触发条件 | 是否写入 `Lead` 表 | 备注 |
|---|---|---|---|
| Monitor 关键词命中 | listener 抓到匹配 | ✅ 是（[listener_service.py:485,497](backend/app/services/listener_service.py#L485)，`source='monitor'`） | 主路径 |
| Bulk Send 用户回复 | `handle_bulk_reply` task | ❓ 不确定 | 应该但没看到明确写 Lead |
| Scrape 抓到的成员 | scrape_batch | ❌ 否（写 `BulkTarget`） | 是"准客户名单"不是 Lead |
| 客户主号被人主动私聊 | 主号 listener | ❓ 不确定 | Epic 5 接管管线，未必落 Lead |
| 销售自己主动拉的人 | 手动 | ❓ 无入口 | 销售工作台无"新建线索"入口？ |
| 拦截回复（`intercept_reply`） | listener_service.py:615 | 写 `source='intercept_reply'` | 又是新的 source 值 |

**Lead.source 取值**至少有：`monitor` / `intercept_reply` / `keyword_match_judge`——但**没有统一的枚举常量**，每个 service 自己写字符串。

**漏斗看板（Epic 6）的数据**：看的是哪条入口的转化？看 Monitor 还是看全部？一份"funnel"指标背后藏着几个不同业务路径的混合。

**销售视角的混乱**：
- `/sales/leads` 列表是 Lead 表
- `/sales/inbox` 列表是 Conversation 表（推测）
- 这两个表的关系是？一个 Lead 对应一个 Conversation？还是 Lead 有多次 Conversation？
- F2 的"原子 view+claim"只解决 Lead 表层面，Conversation 层面有没有同样的双抢风险未知

**KB 也有同样的"多入口少出口"问题**：
- `KnowledgeBase.source_type`：`manual` / `qa_extracted` / `scraped` / `file_import` / `industry_template` / `chat_reply`——**6 种取值散布在不同 service**，模型里只列了 4 种，industry_template 和 chat_reply 是漂出来的字符串。

---

## 5. 进行中的 role→tier 重构反而凝固了混乱

**未提交工作**目标：把手动 tier 选择替换成 role 派生 tier。但实际效果是：

1. **没解决根本问题**：现在 `Account` 上还是有 role + combat_role 两个独立分类系统，只是少了手动 tier 输入框。
2. **加了新值 `main`**：`VALID_ROLES = {"worker", "master", "support", "sales", "listener", "collector", "main"}`——本来 `Customer.main_account_id` 已经能标记主号，现在 `Account.role='main'` 是另一种标记方式，**两种事实真相**。
3. **派生函数 `_tier_for_role`** 是写死的 if-else 映射（master/main→tier1, support/sales/collector→tier2, 其他→tier3）。这意味着"以后想新增一种 role 类型"得改代码而不是改配置。
4. **下游 tier 用法没动**：shill_dispatcher、permission_service 还是按 tier 判断。如果 tier 在 phone 解析前就写入（tdata 导入场景），权限判断可能错位。
5. **零测试**：9 个文件没有任何对应测试。

---

## 6. 三套 SPA 的"分散与统一并存"

**统一的部分**：
- 同一个 `/api/v1/auth/login` 入口（commit `f1f87c2` 合并）
- 同一套后端 router

**分散的部分**：
- 三套 token key：`token` / `tg1_customer_token` / `tg1_sales_token`
- 三套 axios 实例：[services/api.ts](frontend/src/services/api.ts)（1621 行） / [sales/api.ts](frontend/src/sales/api.ts) / [portal/api.ts](frontend/src/portal/api.ts)
- 三套 auth helper / Layout / 401 处理
- i18n 只在 `/sales/*` 有，且自建（不引第三方），admin 和 portal 是中文硬编码

**真正的痛**不是"三套"本身——而是**三套之间的能力会漂移**：
- 比如未来给 portal 加语言切换，会复制 sales 那套？还是抽公共？
- admin 加了一个错误提示统一格式，portal/sales 用不到，慢慢就行为不一致
- 三套 axios 实例里如果有一套的 token 刷新逻辑变了，另外两套不知道

---

## 7. 其他散点（不到重写门槛，但值得登记）

- **AI provider 既支持 9 种又默认 Vertex Gemini**：[llm.py](backend/app/services/llm.py) 同时支持 OpenAI/Anthropic/DeepSeek/Qwen/Moonshot/Zhipu/Doubao/OpenRouter/Gemini，但 [memory](/root/.claude/projects/-var-tgsc/memory/project_gemini_on_vertex.md) 明确说"统一 Vertex"。多 provider 框架是历史遗留，但删除也有风险——决策不明。
- **`AIConfig` 表 + `.env` 的 LLM 配置并存**：API key 在哪？admin UI 可改 vs `.env` 写死，两条路。
- **Stripe 字段可能残留**：memory 说"决策走 USDT"，agent 确认没找到 Stripe 代码，但 INVOICE 模型字段、网关接口设计有没有"为 Stripe 留白"未验证。
- **`legacy_migrations/`（7 文件）+ `migration_backup/`（269 MB）+ backend 根 5 个一次性脚本**：物理混乱，看着像活的实际是死的。
- **品牌名 TGSC ↔ TG1.AI 混用**：README 是 TGSC，docs 是 TG1.AI；代码里都是 TGSC。

---

## 给你的"先治什么"建议（按 ROI 排序）

我建议**不要现在就动重构**。先做的是「立约定」，不是「改代码」：

| # | 动作 | 工作量 | 收益 |
|---|---|---|---|
| **A** | **建立"模块字典"**：把 Epic 1–6 + A–E + F1–G + W1–5 一次性翻译成 6–8 个稳定模块名（如 Tenancy / Billing / Allocation / KB / Handover / SalesWorkbench / LeadPool / Ops），所有后续 commit/doc/memory 都用模块名，旧编号只作为历史归档 | 0.5d | 高 |
| **B** | **画"能力矩阵"**：5 个 role 字段 × 行为 = 矩阵表，明确每个 role/owner_type 取值的含义、谁能用、谁能改 | 0.5d | 高 |
| **C** | **画"扣费路径图"**：所有钱包/配额扣减点列成一张表（动作 / 触发位置 / 扣什么 / 扣多少 / 失败行为）| 0.5d | 高 |
| **D** | **统一 `Lead.source` / `KnowledgeBase.source_type` 枚举**：写到 `models/enums.py`，service 调用引用常量而非字符串 | 0.5d | 中 |
| **E** | **收尾 role→tier 重构**：但只在已经做完上面 B 之后——先决定要不要保留 combat_role | 1d | 中 |
| **F** | **决定 multi-provider LLM 框架的去留**：留 = 写清切换条件；删 = 把 [llm.py](backend/app/services/llm.py) 砍到只剩 Vertex | 1d | 中 |

**核心建议**：**当前的"混乱感"不是代码不够好，是"语言"不够统一**。先花一两天把命名、角色、扣费这三套语言写清楚（用 6 张表），后续重构就有了对账基准；现在直接动代码反而会再产生新的不一致。
