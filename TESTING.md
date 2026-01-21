# Stage 9 全流程测试指南

本指南用于验证 **Stage 9 (高级转化与增长)** 的核心功能，包括关键词监控、账号分级、AI 意图识别和 CRM 标签流转。

## 1. 自动化集成测试 (Backend)

我们提供了一个自动化测试脚本，用于验证后端核心逻辑（无需真实 Telegram 连接）。

### 运行方式
在 `backend` 目录下运行：
```bash
python test_stage_9_integration.py
```

### 测试内容
1.  **账号分级权限 (Tiering)**: 验证 Tier 1 账号是否被禁止执行拉人/群发任务，Tier 3 是否允许。
2.  **AI 意图识别 (Intent)**: 模拟 AI 分析 "What is the price?" 消息，验证 CRM Lead 是否自动打上 `intent:inquiry` 标签。
3.  **关键词监控 (Monitor)**: 验证关键词命中记录 (Hit) 的创建与关联逻辑。

---

## 2. 手动功能验证 (Frontend & Full Loop)

### 2.1 账号分级 (Account Tiering)
1.  进入 **Accounts (账号管理)** 页面。
2.  编辑任意账号，点击 **设置角色**。
3.  在弹窗中选择 **账号分级 (Tier)**，设置为 `Tier 1 (Premium)`。
4.  保存后，列表应显示金色的 `TIER1` 标签。
5.  进入 **Invites (批量拉人)** 页面，尝试创建任务并选择该 Tier 1 账号。
    *   *预期结果*: 如果后端 API 拦截生效，任务创建应失败或返回错误提示（取决于前端是否预先过滤，目前逻辑主要在后端拦截）。

### 2.2 关键词监控与自动回复 (Keyword Monitor & Shill)
1.  进入 **Monitor (监控引流)** 页面。
2.  点击 **Create Monitor**。
3.  设置关键词 (e.g., "测试")。
4.  **Action** 选择 `Trigger Script`。
5.  选择一个现有的脚本（如果没有，先去 Scripts 页面创建一个简单的脚本）。
6.  点击保存。
7.  *真实测试需运行 Listener*: 确保 `python listener.py` 正在后台运行，并使用另一个 TG 账号在被监听的群组发送包含 "测试" 的消息。
8.  刷新 **Hits Log**，应能看到新的命中记录。

### 2.3 AI 意图识别与 CRM (AI SDR)
1.  进入 **Inbox / CRM** 页面。
2.  *模拟场景*: 当系统收到客户消息（如 "多少钱？"）时，AI 会在后台自动分析。
    *   *注*: 需要确保账号开启了 `Auto Reply` 且配置了有效的 OpenAI API Key。
3.  如果识别成功，客户列表中的该用户条目会出现 🔥 火焰图标。
4.  点击客户查看详情，**标签**栏应包含 `intent:inquiry` 或 `intent:purchase` 标签（红色高亮）。
