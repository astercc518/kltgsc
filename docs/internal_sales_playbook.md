# 内部销售获客运营手册（TG 营销助手）

> 目标：公司自营的销售团队用平台采集的 TG 线索做获客转化。
> 落地 Phase F1–F4 后该手册可执行。

---

## 1. Day-1 配置（admin 跑一次）

### 1.1 建一个内部线索池
```
POST /api/v1/admin/billing/provision-internal-pool
{
  "email": "internal-crypto@platform.local",
  "name": "Internal · Crypto",
  "industry": "crypto"
}
```
- 每个**业务组**一个池子（crypto / forex / gambling / saas / 等）—— `industry` 不同
- 返回的 `customer_id` 后续都用得上（这里假设 38）

### 1.2 把 TG 监听账号划归到池子
方式 A（API 一并完成）：
```
POST .../provision-internal-pool
{
  "email": "...",
  "account_ids": [79, 80, 81]   # 这些账号 customer_id 会被设为 38
}
```
方式 B（admin 后台 /accounts 改）。
- 一个池子建议 **5-10 个监听账号**，避免被风控集中触发
- 这些账号必须 `role='listener'` 且 `is_active=true`

### 1.3 让监听账号加入采集群（admin 后台 /scraping/join 批量）
- 每个内部池建议覆盖 **30-100 个目标群**，按 `industry` 严格匹配
- 控制每账号加群速度：默认每群 2-5 秒延迟（[scraping_tasks.py](../backend/app/tasks/scraping_tasks.py) 已自带）
- 加群后等 6 小时再开 monitor — 给账号"暖身"避免 spam 风险

### 1.4 配置 KeywordMonitor 规则
- admin /monitor 后台或 `POST /api/v1/monitors`
- **关键**：给每条规则填 `industry`（与池子 industry 对齐）
- 推荐参数：
  - `match_type: 'partial'`（或 `'semantic'` 配 `scenario_description` 更准）
  - `marketing_mode: 'passive'`（**绝对不要 active** — 内部池禁止自动 DM）
  - `auto_capture_lead: true`（已无所谓，F4 fast path 不依赖它）
  - `cooldown_seconds: 300`（5 分钟一群内不重复）
- 改 industry 用 `PUT /monitors/{id}` 带 `{"industry": "..."}`

### 1.5 创建销售账号 + 分配 industry_filter
```
# 1. admin 后台 /users 建 10 个 User，role='sales'
# 2. 给每个销售设 industry 过滤：
PATCH /api/v1/users/{user_id}/industry-filter
{ "industry_filter": ["crypto", "forex"] }
```
- industry_filter 决定该销售看到哪些行业的 lead
- 空数组 = 看所有内部池的 lead（不推荐，会争抢）

### 1.6 给所有销售充月度预算
```
POST /api/v1/admin/sales-wallet/bulk-monthly-credit
{ "amount_usd": 50, "period_tag": "2026-05", "description": "monthly budget" }
```
- `period_tag` 用 `YYYY-MM` 格式；同 tag 重跑幂等，不会重复充
- 每月 1 日定时跑（或人工触发）

---

## 2. 每日运营 — 销售（platform_sales）

1. 登录 → 自动跳 `/sales/inbox`
2. 上面看到自己 industry 内**未 claim** 的 lead 卡片（联系方式打码）
3. 选一条 **未被别人 claim** 的点 **View ($0.50)** —— 同时扣 50¢ 并自动 claim
   - 若已被别人 claim：会显示 409 提示，换一条
4. 详情页：复制 username 或 phone，去自己的 Telegram 私聊
5. 写 notes → PATCH 改 status（`contacted` / `replied` / `interested`）
6. 成交 → 点 **Convert**（保留 claim 用于业绩归属）
7. 跟进不下去 → 点 **Release** 归还公池

**自己已 claim 的 lead 可以无限 free re-open**（不重复扣费）。

---

## 3. 每周/每月运营

### 销售组长
- 看 `/business-ops` 的 **Platform Sales Performance** 卡片
  - 每人当月 spend / claimed / converted / conversion%
  - 余额低于 $10 提醒充值
- 调 `/users/{id}/industry-filter` 平衡组内分工

### 平台 admin
- 月度跑 `POST /admin/sales-wallet/bulk-monthly-credit` 续杯
- 每周看 `/business-ops`：
  - **Customer Health** 卡片：观察外部客户 lead 流量
  - **Sales Performance** 卡片：内部销售 ROI
- 监控调优：
  - `GET /monitors/{id}/recent-hits?hours=24` 看每条规则真实命中量
  - 命中 0 → 规则太严或目标群不活；命中多但 conversion% 低 → 规则太松
  - 内部池每日新增 lead 数 = `select count(*) from lead where customer_id IN (internal_pool_ids) and created_at::date = today`

---

## 4. 关键约束与坑

| 约束 | 影响 | 缓解 |
|---|---|---|
| platform_sales 看不到外部客户 lead | by design (F1)，避免越权 | 不要把外部客户的 customer 误设 `is_internal_pool=true` |
| `KeywordMonitor.marketing_mode='active'` 在内部池下也**被 F4 跳过** | 不会发 DM | 想发批量 DM 走客户侧 `/portal/bulk` 体系 |
| 销售 claim 后离职 → lead 锁死 | 历史 lead 无法被新销售 view | admin 跑 SQL `UPDATE lead SET assigned_to_user_id=NULL, claimed_at=NULL WHERE assigned_to_user_id=<离职id>` |
| listener 容器网络异常 | hit 数据 0，lead 不增长 | `docker compose logs listener` 看 SOCKS 代理报错；换代理或调 [proxy_assigner.py](../backend/app/services/proxy_assigner.py) |
| 监听账号一旦封号 | 当前账号下所有未 claim lead 丢失（无人接管） | 一池多账号；定期检查 `/account-pool` 健康 |

---

## 5. 不要做的事

- **不要把内部池和真实客户混用**（一个 Customer 不能同时 paying & is_internal_pool）
- **不要让 platform_sales 用 `industry_filter=[]`** —— 会引起多人争抢同一条
- **不要在内部池的 monitor 上开 `marketing_mode='active'` 期待 DM 群发** —— F4 已禁止
- **不要手动改 lead.assigned_to_user_id 跳过 claim** —— 计费 + 报表会错乱

---

## 6. 紧急回滚

如发现 F1-F4 任一改动有问题：
```
docker compose exec backend alembic downgrade 9c0d1e2f3a4b   # 回到 Epic D 末
git revert 6ef53f3 17cfb71 107ff91                            # F3 F2 F1
docker compose restart backend listener
```
仅会丢失 internal_pool 标志 + sales claim 记录，客户侧功能不影响。
