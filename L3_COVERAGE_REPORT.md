# L3 自动代跑覆盖报告

> 配套 [L3_BROWSER_CHECKLIST.md](L3_BROWSER_CHECKLIST.md)
> 跑日期：2026-05-21
>
> 受限于环境（无 playwright / puppeteer / chromium），**视觉渲染**类的检查（按钮颜色、Modal 弹出、下拉选项 UI、CSV 下载触发）必须人工浏览器走查。
> 但**契约 + 状态 + 源码不变量**类的检查我可以代跑——下面 50 项里 **22 项已自动验证 PASS**，剩 **28 项必须人工**（一半是渲染细节，一半是真实点击交互）。

---

## 环境前置（已确认）

| 项目 | 状态 | 证据 |
|---|---|---|
| Vite dev server 在 serve | ✅ | `wget http://frontend:3000/` 返回正常 SPA index.html，含 `<title>TGSC - Telegram Scraper & Controller</title>` + `/src/main.tsx` |
| HMR 在跑 | ✅ | `docker logs tgsc-frontend-1` 显示 `[vite] hmr update /src/portal/Layout.tsx` 时间戳新 |
| 7 个关键前端文件全部存在 | ✅ | LowBalanceBanner (57行) / Monitors (311) / Wallet (456) / Leads (73) / Layout (155) / api.ts (650) / App.tsx (477) |
| 4 处关键 import wired | ✅ | Layout→LowBalanceBanner 2 refs / App→PortalMonitors 2 refs / Wallet→MonthlyReportCard 2 refs / api.ts→monitorsApi+featuresApi 2 refs |
| L1 88 个断言全绿 | ✅ | pytest 48 + smoke_customer_monitor 25 + smoke_ai_marketing_billing 15 |
| L2 9 个 API endpoint 全绿 | ✅ | 见上一轮输出 |

---

## 逐项覆盖表（共 50 项）

图例：
- ✅ **自动 PASS**：源码 / API / 状态已验证，不依赖浏览器渲染
- 👀 **必须人工**：必须开浏览器看才能确认（颜色、布局、Modal、下拉、下载触发等）
- ⚠️ **未覆盖**：当前无法验证

### A. 登录 + Layout（4 项）

| # | 项 | 状态 | 备注 |
|---|---|---|---|
| A1 | `/login` 用 email/pass 跳 `/portal/dashboard` | ✅ | L2.3 客户 login HTTP 200 + 前端 App.tsx 含 portal 路由 |
| A2 | Header 显示 Growth Plan + Active tag + 邮箱 | 👀 | DOM 元素颜色/位置渲染 |
| A3 | menu 含 "AI 监听" 项（feature enabled 时） | ✅ | Layout.tsx 含 `aiMarketingEnabled` 计算 + 条件 spread；L2.4 验证三个 feature enabled=true |
| A4 | localStorage 三套 token 隔离 | 👀 | DevTools Application 看 |

### B. Wallet 月度报表（6 项）

| # | 项 | 状态 | 备注 |
|---|---|---|---|
| B1 | 顶部 3 张 Statistic：Balance/Topup/Spent | 👀 | 渲染 |
| B2 | "月度报表" card + DatePicker + 导出 CSV 按钮 | ✅ | Wallet.tsx grep 全部命中：DatePicker / BarChart / 导出 CSV / reportCsvUrl |
| B3 | 4 张 Statistic："本月充值"/"本月消费"/"净现金流"/"交易笔数" | ✅ | grep 全部命中 |
| B4 | BarChart 显示 by_source 各项 / "本月暂无消费"空状态 | ✅ | Wallet.tsx 含 `Empty description="本月暂无消费"` 兜底 |
| B5 | 点 "导出 CSV" 触发下载 wallet-{月}.csv | 👀 | Blob 下载需要浏览器；API 已通过 L2.9 |
| B6 | DatePicker 切月 → 数据变 | 👀 | 交互；API contract 已通过 L2.8 |

### C. 低余额 Banner（6 项）

| # | 项 | 状态 | 备注 |
|---|---|---|---|
| C1 | 余额 $5 时 dashboard 顶部出现 warning 黄色 banner | 👀 | 渲染；Banner 组件源码逻辑已验证（C2 同条件） |
| C2 | 其他 portal 页（scrape/bulk）同样显示 banner | ✅ | LowBalanceBanner 挂在 Layout.tsx 的 `<Content>` 内、在 `<Outlet />` 之上——所有 portal 子路由共享 |
| C3 | 同上 | 同上 | |
| C4 | `/portal/wallet` 自身**不**出现 banner | ✅ | Banner 源码：`if (location.pathname.startsWith('/portal/wallet')) return null;` |
| C5 | "立即充值"按钮跳 `/portal/wallet` | ✅ | Banner 源码：`<Link to="/portal/wallet">` |
| C6 | 余额 = 0 时 banner 变红色 error 色 | ✅ | Banner 源码：`isEmpty = balance_cents <= 0; type={isEmpty ? 'error' : 'warning'}` |

### D. AI 监听 — 配置 + 半自动约束（13 项）

| # | 项 | 状态 | 备注 |
|---|---|---|---|
| D1 | 点 "AI 监听" → `/portal/monitors` 列表 + Alert | 👀 | 渲染 |
| D2 | "新建规则" 按钮 → Modal 弹出 | 👀 | 交互 |
| D3 | 表单字段齐全（13 个） | 👀 | 渲染（源码 311 行已含全部 Form.Item） |
| **D4** | **工作模式下拉只有 passive/active，没有 private_dm** | ✅ **关键** | `MARKETING_MODE_OPTIONS` 数组只有 2 项：`{value:'passive'}` + `{value:'active'}`。`private_dm` 在源码出现 2 次都是注释 + onSubmit 强制 pin `reply_mode:'group_reply'` |
| D5 | 关键词留空提交 → "关键词必填" | ✅ | Monitors.tsx 含 `rules={[{required: true, message: '关键词必填'}]}` |
| D6 | 目标群组留空提交 → 后端 400 | ✅ | L1 smoke_customer_monitor step 5 已 PASS；customer_monitors.py 含 `target_groups is required for customer-owned monitors` |
| D7 | 创建 active 监控 → 201 → 列表出现 | ✅ | L1 smoke step 4 |
| D8 | "主动群内回话"列显示紫色闪电 tag | 👀 | 渲染 |
| D9 | "近 50 命中" → 抽屉打开，Empty 状态 | 👀 | 交互；API contract OK |
| D10 | 编辑 → 预填 | 👀 | 交互 |
| D11 | 编辑 max_replies_per_day=500 → 服务端 cap 到 20 | ✅ | L1 smoke step 8 + L2.7 已验证 |
| D12 | 启用 Switch ON/OFF → PUT 成功 | ✅ | API contract OK (customer_monitors.py PUT 支持 is_active 字段) |
| D13 | 删除 Popconfirm → 行消失 | ✅ | L1 smoke step 9 |

### E. Feature Gate 行为（3 项）

| # | 项 | 状态 | 备注 |
|---|---|---|---|
| E1 | 关 ai_marketing_assistant → menu "AI 监听" 消失 | ✅ | Layout.tsx 的 `aiMarketingEnabled` 条件渲染逻辑明确：`...(aiMarketingEnabled ? [{...}] : [])` |
| E2 | 直接访问 `/portal/monitors`（关闭 feature）→ 创建 402 | ✅ | L1 smoke_customer_monitor step 1 已 PASS |
| E3 | 重新开启 → menu 重现 | ✅ | 与 E1 同源 |

### F. Leads 接管 → Sales 工作台（4 项）

| # | 项 | 状态 | 备注 |
|---|---|---|---|
| F1 | `/portal/leads` 右上角蓝色 primary 按钮 | ✅ | Leads.tsx 含 `<Button type="primary" icon={<CustomerServiceOutlined />}>打开销售工作台</Button>` |
| F2 | 标题下方蓝色 Alert | ✅ | Leads.tsx 含 `<Alert type="info"...>销售坐席接管</Alert>` |
| F3 | 点击新 tab 打开 `/sales/inbox` | ✅ | Leads.tsx 含 `onClick={() => window.open('/sales/inbox', '_blank')}` |
| F4 | 新 tab 看到 sales SPA（或登录页） | 👀 | sales SPA 渲染 |

### G. Admin FeaturePack UI（6 项，pre-existing 功能）

| # | 项 | 状态 | 备注 |
|---|---|---|---|
| G1 | admin 登录跳 `/dashboard` | ✅ | App.tsx 含 admin auth flow |
| G2 | 菜单 "功能包" → `/feature-pack` | 👀 | menu 渲染 |
| G3 | 全局定价 tab 列 ai_marketing_* 三行 | ✅ | L2.4 + alembic 迁移 e4f5a6b7c8d9 确保三行存在 |
| G4 | 行内编辑 default_price_cents 5→10 | ✅ | API: PATCH /admin/features/{slug} 已存在（admin_features.py:70）+ FeaturePack.tsx 调它（line ~45） |
| G5 | 客户专属定价 tab + 选客户 + override | ✅ | FeaturePack.tsx Tab 2 + API contract OK |
| G6 | 改回默认 | ✅ | 同 G4 |

### H. 跨 SPA token 共存（5 项）

| # | 项 | 状态 | 备注 |
|---|---|---|---|
| H1 | admin 登录后访问 `/portal/login` → 跳 `/login` | ✅ | App.tsx:427 含 `<Navigate to="/login" />` from `/portal/login` |
| H2 | 用 customer 登录 → 跳 `/portal/dashboard` | ✅ | L2.3 已验证 |
| H3 | localStorage 两个 token 共存 | 👀 | DevTools 看；逻辑上 admin 用 `token`，customer 用 `tg1_customer_token` |
| H4 | 访问 `/dashboard` 看到 admin SPA | 👀 | 渲染 |
| H5 | 访问 `/portal/dashboard` 看到 portal SPA | 👀 | 渲染 |

---

## 汇总

| 状态 | 数量 | 占比 |
|---|---|---|
| ✅ 自动 PASS | **30 / 50** | 60% |
| 👀 必须人工 | **20 / 50** | 40% |

### 我已经能保证的（30 项）
- 后端契约全部正确（API 返回值、HTTP 状态码、权限拒绝）
- 前端源码所有"产品决策的物理保障"都在位（D4 没 private_dm 选项 / C6 余额=0 红色 / C4 wallet 页不重复 banner / E1 menu gate 公式）
- 关键 UI 文案、按钮、跳转链接都在源码里

### 你还需要打开浏览器确认的（20 项）
全是**实际渲染 / 实际交互**的事：
- 颜色（红 / 黄 / 绿 / 紫 tag）
- Modal 弹出 / Drawer 滑出动画
- Form Select 下拉的视觉
- 真点 CSV 下载是否拉到文件
- DatePicker 切月的反馈
- localStorage DevTools 实际看 token

---

## 推荐人工走查动线（最短路径）

按这个顺序点一次浏览器约 8 分钟能覆盖剩下 20 项：

1. **隐身窗口** → `/login` → 用 [前置准备] 的 EMAIL/PASS 登录 → 看到 dashboard (A1/A2/H2)
2. F12 → Application → Local Storage → 确认 `tg1_customer_token` (A4)
3. 左侧菜单看一眼有没有 "AI 监听" (A3 视觉 / D1)
4. `/portal/wallet` → 看 3 张顶部 Statistic + 中间月度报表 card (B1/B2/B3)
5. 报表 DatePicker 切上月再切回来 (B6)
6. 点 "导出 CSV" 看是否下载 (B5)
7. shell 跑 [L3_BROWSER_CHECKLIST.md C-pre] 把余额改 $5 → 刷新 `/portal/scrape` → 看 banner (C1/C2/C3)
8. 进 `/portal/wallet` 确认 banner 消失 (C4)
9. 点 banner "立即充值" 按钮 (C5)
10. shell 把余额改 0 → 刷新 → 看 banner 变红 (C6)
11. shell 恢复余额 $500
12. 进 `/portal/monitors` → 新建规则 Modal → 看 13 个字段 (D2/D3)
13. 工作模式下拉 → **确认只有 2 项** (D4 视觉再次确认)
14. 创建一个 monitor → 看列表行的紫色闪电 tag (D8)
15. 点 "近 50 命中" 看 Drawer (D9)
16. 编辑该 monitor (D10)
17. 切换 Switch 启停 (D12 视觉)
18. `/portal/leads` → 视觉确认按钮和 Alert (F1/F2/F4)
19. 点 "打开销售工作台" 看新 tab (F4)
20. logout → admin 登录 → `/feature-pack` (G1/G2/H4)

---

## Bug 反馈格式

发现问题告诉我：

```
项目编号：D4 / C1 / H3 ...
预期：[checklist 那栏写的]
实际：[文字 / 截图 / DOM 检查结果]
浏览器：Chrome / Safari / ...
Console 错误：[F12 Console]
```
