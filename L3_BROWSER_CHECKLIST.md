# L3 浏览器验证清单

> 配套 Sprint 1 (commit `d2ec873`) + Sprint 2 (commit `74999e7`)
> 推荐 ~25 分钟一次走完。逐项打勾 ☐ → ☑。
> 跑过 L1/L2 已通过的前提下，本清单只验**浏览器视图 / UI 行为**。

---

## 前置准备（2 分钟）

### 测试 URL
- 前端：[http://localhost:3000](http://localhost:3000)
- 后端 API（看请求时用）：`http://localhost:3000/api/v1/...`

### 准备一个干净的测试客户

```bash
PW=$(docker exec tgsc-backend-1 printenv ADMIN_PASSWORD)
EMAIL="ui-test-$(date +%s)@x.tg1.ai"
PASS="UiTest1234!"
echo "EMAIL=$EMAIL  PASS=$PASS"

docker exec -e PW="$PW" tgsc-backend-1 python3 -c "
import os, httpx
c = httpx.Client(base_url='http://localhost:8000/api/v1', timeout=10)
r = c.post('/login/access-token',
    data={'username':'admin','password':os.environ['PW']},
    headers={'Content-Type':'application/x-www-form-urlencoded'})
admin = r.json()['access_token']
r = c.post('/admin/billing/quick-provision',
    json={'new_customer_email':'$EMAIL','new_customer_password':'$PASS',
          'plan':'growth','wallet_credit_cents':50000,'note':'L3 ui test'},
    headers={'Authorization': f'Bearer {admin}'})
print('  customer_id =', r.json()['customer_id'])
"
```

记下 `EMAIL` / `PASS` / `customer_id` 三件套，整个清单都会用到。

### 浏览器准备
- 用一个全新的隐身窗口（或 logout 之前的会话），避免缓存 token 串台
- 开发者工具 → Network tab 打开（验证步骤需要看请求体）

---

## A. 登录 + Portal Layout

| ☐ | 步骤 | 预期 |
|---|---|---|
| A1 | 打开 [/login](http://localhost:3000/login)，输入 `EMAIL` + `PASS` 提交 | 自动跳 `/portal/dashboard` |
| A2 | Header 右上 | 看到 `Growth Plan` 绿色 tag + `Active` 绿色 tag + 邮箱 |
| A3 | 左侧 Sider 菜单 | 应**有**这一项：**`AI 监听`**（紫色闪电图标）。如果没看到，去 §E 排查 feature gate |
| A4 | 三套 token 验证（DevTools → Application → Local Storage） | 看到 `tg1_customer_token` 有值；`token` 和 `tg1_sales_token` 可能为空 |

---

## B. Wallet 月度报表（S1.3）

| ☐ | 步骤 | 预期 |
|---|---|---|
| B1 | 进 [/portal/wallet](http://localhost:3000/portal/wallet) | 顶部 3 张 Statistic 卡片：Balance / Total Topup / Total Spent。Balance = `$500.00`（quick-provision 充的） |
| B2 | 中间 "月度报表" card | 看到 `<BarChartOutlined>` 图标 + 标题 "月度报表"，右上有 DatePicker（默认本月）+ "导出 CSV" 按钮 |
| B3 | 4 张 Statistic 卡片 | 本月充值 `$500.00`（admin credit 入账被记为 adjust，不算 topup），消费 `$0.00`，净现金流 `$500.00`，交易笔数 `1` |
| B4 | BarChart 区域 | 因为还没扣过钱，显示 **"本月暂无消费"** Empty 状态 |
| B5 | 点 "导出 CSV" | 浏览器下载 `wallet-{月份}.csv`。打开看到 header 行 `id,created_at_utc,type,source,...` + 1 行 adjust 类型记录 |
| B6 | DatePicker 切到上月 | 报表数据变 `txn_count: 0`（这个新客户上月不存在），by_source 全 0 |

---

## C. 低余额 Banner（S1.2）

### C-pre：先把余额改低
**关键**——L2 验证完之后这个新客户余额是 $500，不会触发。在控制台手动改：

```bash
docker exec tgsc-backend-1 python3 -c "
from sqlmodel import Session, select
from app.core.db import engine
from app.models.customer import Customer
from app.models.wallet import CustomerWallet
with Session(engine) as s:
    cust = s.exec(select(Customer).where(Customer.email == '$EMAIL')).first()
    w = s.get(CustomerWallet, cust.id)
    w.balance_cents = 500  # \$5  ← 触发警告（<\$20）
    s.add(w); s.commit()
    print('  cust_id =', cust.id, ' balance now = \$', w.balance_cents/100)
"
```

| ☐ | 步骤 | 预期 |
|---|---|---|
| C1 | 刷新 [/portal/dashboard](http://localhost:3000/portal/dashboard) | **页顶横幅 banner**（黄色 warning 色）："钱包余额仅剩 $5.00 — 低于 $20 阈值..." + 右侧 "立即充值" 蓝色按钮 |
| C2 | 进 [/portal/scrape](http://localhost:3000/portal/scrape) | 同样的 banner，挂在 Layout 级 |
| C3 | 进 [/portal/bulk](http://localhost:3000/portal/bulk) | 同上 |
| C4 | 进 [/portal/wallet](http://localhost:3000/portal/wallet) | banner **不出现**（避免和页内卡片重复警告） |
| C5 | 点 banner 上的 "立即充值" 按钮 | 跳 `/portal/wallet`，banner 自动消失 |

### C-second：余额归零 → 红色 error 色

```bash
docker exec tgsc-backend-1 python3 -c "
from sqlmodel import Session, select
from app.core.db import engine
from app.models.customer import Customer
from app.models.wallet import CustomerWallet
with Session(engine) as s:
    cust = s.exec(select(Customer).where(Customer.email == '$EMAIL')).first()
    w = s.get(CustomerWallet, cust.id)
    w.balance_cents = 0
    s.add(w); s.commit()
"
```

| ☐ | 步骤 | 预期 |
|---|---|---|
| C6 | 刷新 dashboard | banner 变**红色 error 色**，文案变："钱包余额已归零 — 进行中的群发 / 群拉 / 采集会自动暂停 (paused_no_funds)" |

### C-cleanup：恢复余额（给后续步骤用）

```bash
docker exec tgsc-backend-1 python3 -c "
from sqlmodel import Session, select
from app.core.db import engine
from app.models.customer import Customer
from app.models.wallet import CustomerWallet
with Session(engine) as s:
    cust = s.exec(select(Customer).where(Customer.email == '$EMAIL')).first()
    w = s.get(CustomerWallet, cust.id)
    w.balance_cents = 50000
    s.add(w); s.commit()
"
```

---

## D. AI 监听 — 配置 + 半自动约束（S2.6）

| ☐ | 步骤 | 预期 |
|---|---|---|
| D1 | 点左侧 menu **"AI 监听"** → 进 [/portal/monitors](http://localhost:3000/portal/monitors) | 标题 "AI 营销助手 — 监听规则"，下方蓝色 Alert 提示计费规则，列表 Empty（无规则） |
| D2 | 点 "新建规则" 按钮 | Modal 弹出，标题 "新建监听规则" |
| D3 | **检查表单字段** | 看到：关键词 / 匹配方式 / 目标群组 / 工作模式 / 行业（可选）/ AI 人设 / 冷却/上限/延迟 4 个 InputNumber / 备注 / 启用 |
| D4 | **关键检查**：工作模式下拉 | 只有两个选项 — `被动监听` + `主动 AI 群内回话（半自动，群内回应）`。**没有任何选项含 "私聊" 字样** ✅（这是产品决策的物理保障） |
| D5 | 关键词留空提交 | Form 校验失败，提示 "关键词必填" |
| D6 | 关键词填 `crypto`，目标群组留空 | 提交后服务端返回 400，错误 message "目标群组必须填" toast 弹出 |
| D7 | 填完整：keyword=`crypto`，target_groups=`@test_g`，模式=主动 | 提交 → 201 Created，列表出现一行；状态列绿色 Switch ON |
| D8 | 列表行的 "主动群内回话" 列 | 显示紫色闪电 tag |
| D9 | 列表行点 "近 50 命中" | 右侧抽屉打开，因为没真触发过，显示 Empty "尚无命中记录" |
| D10 | 列表行点 "编辑" | 同样的 Modal，所有字段被预填 |
| D11 | 编辑里把 max_replies_per_day 改成 500 提交 | 服务端 cap 到 20，列表刷新后该 monitor 详情显示 20 |
| D12 | 列表行启用 Switch 拨到 OFF | 后端 PUT 成功，列变灰，启用列变红/灰色 |
| D13 | 删除按钮（红色，Popconfirm "删除该规则？"） | 确认后行消失 |

---

## E. Feature Gate 行为（S2.3）

### E-pre：先关掉 ai_marketing_assistant feature

```bash
docker exec tgsc-backend-1 python3 -c "
import os, httpx
c = httpx.Client(base_url='http://localhost:8000/api/v1', timeout=10)
r = c.post('/login/access-token',
    data={'username':'admin','password':os.environ['PW']},
    headers={'Content-Type':'application/x-www-form-urlencoded'})
admin = r.json()['access_token']
# 查 cust_id
from sqlmodel import Session, select
from app.core.db import engine
from app.models.customer import Customer
with Session(engine) as s:
    cust = s.exec(select(Customer).where(Customer.email == '$EMAIL')).first()
    cid = cust.id
r = c.put(f'/admin/customers/{cid}/features/ai_marketing_assistant',
    json={'enabled': False},
    headers={'Authorization': f'Bearer {admin}'})
print('  disabled:', r.status_code)
" -e PW="$(docker exec tgsc-backend-1 printenv ADMIN_PASSWORD)"
```

⚠️ 上面命令有 env var 顺序问题，正确写法在末尾：

```bash
PW=$(docker exec tgsc-backend-1 printenv ADMIN_PASSWORD)
docker exec -e PW="$PW" -e EMAIL="$EMAIL" tgsc-backend-1 python3 -c "
import os, httpx
from sqlmodel import Session, select
from app.core.db import engine
from app.models.customer import Customer
c = httpx.Client(base_url='http://localhost:8000/api/v1', timeout=10)
admin = c.post('/login/access-token',
    data={'username':'admin','password':os.environ['PW']},
    headers={'Content-Type':'application/x-www-form-urlencoded'}).json()['access_token']
with Session(engine) as s:
    cid = s.exec(select(Customer).where(Customer.email==os.environ['EMAIL'])).first().id
r = c.put(f'/admin/customers/{cid}/features/ai_marketing_assistant',
    json={'enabled': False}, headers={'Authorization': f'Bearer {admin}'})
print('  disabled feature for cust', cid, ':', r.status_code)
"
```

| ☐ | 步骤 | 预期 |
|---|---|---|
| E1 | 浏览器刷新任意 portal 页 | 左侧 menu 中 **"AI 监听" 项消失**（gate 关闭） |
| E2 | 直接 URL 访问 [/portal/monitors](http://localhost:3000/portal/monitors)（仍能路由进入） | 列表 Empty。点 "新建规则" → 填好提交 → 服务端 **402** Payment Required，toast 提示 "AI 营销助手未开通：Feature ... is not enabled on your account..." |
| E3 | 重新打开 feature | 重跑上面脚本，把 `'enabled': False` 改成 `True`。刷新 portal，menu "AI 监听" 重新出现 |

---

## F. Leads 接管 → Sales 工作台（S2.6）

| ☐ | 步骤 | 预期 |
|---|---|---|
| F1 | 进 [/portal/leads](http://localhost:3000/portal/leads) | 标题 Leads，右上角**蓝色 primary 按钮 "打开销售工作台"**（含客服图标） |
| F2 | 标题下方 | 蓝色 Alert："销售坐席接管 — 要私聊回复某个 lead，请到「销售工作台 → Inbox」..." |
| F3 | 点 "打开销售工作台" | **新 tab** 打开 `/sales/inbox`（不是 portal 内嵌） |
| F4 | 新 tab 里 | 如果当前客户有 CustomerUser 坐席 + 已登录过 sales SPA，会直接看到 inbox；否则跳 `/login` 要求登录 |

---

## G. Admin Feature 定价 UI（S1.1，已存在）

### G-prereq：用 admin 账号登录

```
admin email: 看 docker exec tgsc-backend-1 printenv ADMIN_USERNAME（默认 admin）
admin password: docker exec tgsc-backend-1 printenv ADMIN_PASSWORD
```

| ☐ | 步骤 | 预期 |
|---|---|---|
| G1 | logout 当前 customer，admin 登录 [/login](http://localhost:3000/login) | 跳 `/dashboard`（admin SPA） |
| G2 | 左侧菜单找 "功能包"（admin only） | 看到，点击 → `/feature-pack` |
| G3 | 顶部 tab "全局定价" | Table 列出所有 feature_registry，含 `ai_marketing_*` 三行：assistant (0c/enabled), group_reply (5c/reply), lead_created (50c/lead) |
| G4 | 点某行 "编辑" 改 `ai_marketing_group_reply` default_price_cents 从 5 → 10 | 提交成功，列表刷新显示 10c |
| G5 | tab "客户专属定价" → 选 customer | 列出该客户全部 feature 解析后的 enabled + price（含 override） |
| G6 | 把改的价格改回 5 | 恢复默认 |

---

## H. 跨 SPA 跳转 + token 隔离

| ☐ | 步骤 | 预期 |
|---|---|---|
| H1 | admin 还登录着，**同一浏览器** 打开 [/portal/login](http://localhost:3000/portal/login) | 自动跳 `/login`（unified login） |
| H2 | 用 customer `EMAIL/PASS` 登录 | 跳 `/portal/dashboard` |
| H3 | DevTools → Application → Local Storage | **两个 token 共存**：`token`（admin）+ `tg1_customer_token`（customer） |
| H4 | 直接访问 `/dashboard`（admin 路径） | 看到 admin dashboard（用 `token`） |
| H5 | 直接访问 `/portal/dashboard` | 看到 portal（用 `tg1_customer_token`） |

---

## 完成后清理

```bash
# 删除测试 customer + 全部相关数据（可选）
docker exec -e EMAIL="$EMAIL" tgsc-backend-1 python3 -c "
import os
from sqlmodel import Session, select
from app.core.db import engine
from app.models.customer import Customer
with Session(engine) as s:
    cust = s.exec(select(Customer).where(Customer.email == os.environ['EMAIL'])).first()
    if cust:
        # 留着不删也行——下次走查可复用；若要清理：
        print(f'  to drop: customer_id={cust.id}, run SQL DELETE manually if desired')
"
```

实际多数情况**不删**——保留作为 fixture，后续手动测试也能用。

---

## 发现问题怎么报

发现一个 bug，列以下信息发给我：

```
检查项编号：A3 / B5 / D11 / ...
实际看到：[尽量贴截图或文字描述]
预期看到：[checklist 里那一栏]
浏览器 / 控制台：[F12 Console 报错？]
Network 请求：[相关 HTTP 调用的 path + 状态码 + 响应体前 200 字]
```

我会按 ID 排队定位 + 修。

---

## 评分

- ☑ 全部 50 项：production-ready 体验
- ☐ 1-3 项标红：可上但有小坑，写到 follow-up
- ☐ 5+ 项标红：需要补一轮 UI 修复 sprint
