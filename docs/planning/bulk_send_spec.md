# TG Bulk Send (群发服务) SPEC

> 新 SKU：TG 群发 + 双向回复 + 按条计费
> 决策日期：2026-05-19
> 状态：W1 开发中

---

## 1. 产品定位

类似 Twilio SMS 的"双向消息平台"，但走 TG 协议：

- **客户**提供目标列表（CSV）+ 文案模板
- **平台**用账号池批量发送 + 监听回复
- **客户后台**实时看进度 + 在 Inbox 里看回复 + 销售可接管对话
- **按条计费**：纯用量、钱包预存模式

## 2. 商业模式

### 2.1 计费机制

**Wallet 预存 + 阶梯单价**

| 累计已发送量 | 单条价格 |
|---|---|
| 0 - 10,000 | $0.15 |
| 10,001 - 50,000 | $0.10 |
| 50,001 - 200,000 | $0.07 |
| 200,001+ | $0.05 |

### 2.2 充值档位

| 预存金额 | 赠送比例 | 实际可用余额 |
|---|---|---|
| $100 | 0% | $100 |
| $500 | 2% | $510 |
| $1,000 | 5% | $1,050 |
| $5,000 | 10% | $5,500 |

### 2.3 余额管理

- 起充 $100
- 余额 < $20 触发邮件 + 主号 Saved Messages 提醒
- 余额耗尽 → 所有运行中 batch 自动暂停
- 余额负数禁止（计费扣款用行锁防超扣）

### 2.4 Add-on（后续）

- **AI 自动回复**：+30% 单价
- **高质量老号**：+50% 单价
- **急速发送**：+30% 单价
- **销售外包托管**：$999/月起 + 转化抽成 15-20%

## 3. 技术架构

### 3.1 数据模型

#### 新增 5 张表

```sql
-- 客户钱包
customer_wallet (
    customer_id PK FK,
    balance_cents INTEGER NOT NULL DEFAULT 0,
    total_topup_cents INTEGER NOT NULL DEFAULT 0,
    total_spent_cents INTEGER NOT NULL DEFAULT 0,
    created_at, updated_at
)

-- 钱包流水
wallet_transaction (
    id PK,
    customer_id FK,
    type VARCHAR(20),  -- topup | charge | refund | adjust
    amount_cents INTEGER NOT NULL,  -- 正数=入账，负数=扣账
    balance_after_cents INTEGER NOT NULL,
    description VARCHAR(200),
    bulk_batch_id INTEGER NULL,
    invoice_id INTEGER NULL,
    idempotency_key VARCHAR(100) UNIQUE,
    created_at
)

-- 群发批次
bulk_batch (
    id PK,
    customer_id FK,
    name VARCHAR(100),
    message_template TEXT,
    total_targets, sent, delivered, failed, replied,
    status,  -- draft|pending|running|paused|completed|failed
    started_at, completed_at,
    created_by_user_id
)

-- 目标用户（去重在此）
bulk_target (
    id PK,
    batch_id FK,
    customer_id FK,
    tg_user_id BIGINT NULL,
    tg_username VARCHAR(100) NULL,
    phone VARCHAR(20) NULL,
    status VARCHAR(20),  -- pending|sending|sent|delivered|failed|replied|opted_out
    assigned_account_id FK,
    sent_at, failed_reason,
    UNIQUE(customer_id, tg_user_id)  -- 全平台去重
)

-- 文案变体池（同 batch 多个版本，发送时随机选）
bulk_template_variant (
    id PK,
    batch_id FK,
    content TEXT,
    weight INTEGER DEFAULT 1
)
```

#### 现有表改造（最小侵入）

```sql
-- lead 表加 source 标记（区分 monitor / bulk）
ALTER TABLE lead ADD COLUMN source VARCHAR(20) DEFAULT 'monitor';
ALTER TABLE lead ADD COLUMN bulk_batch_id INTEGER NULL;
```

### 3.2 计费扣款机制

每条消息**发送成功**（status=sent → delivered，TG 回执确认）后触发 Celery `bulk_wallet_charge` 任务：

```python
@celery_app.task(bind=True)
def bulk_wallet_charge(self, batch_id, target_id, idempotency_key):
    with Session(engine) as db:
        # 1. 幂等校验：同 key 已扣过则跳过
        if db.exec(select(WalletTransaction).where(
            WalletTransaction.idempotency_key == idempotency_key
        )).first():
            return {'skipped': True}

        # 2. 行锁拿钱包
        wallet = db.exec(
            select(CustomerWallet)
            .where(CustomerWallet.customer_id == customer_id)
            .with_for_update()
        ).one()

        # 3. 按当前阶梯算单价
        unit_price = calculate_tier_price(wallet.total_spent_cents / 100)

        # 4. 余额不足 → 暂停 batch
        if wallet.balance_cents < unit_price:
            pause_batch(batch_id, reason='insufficient_balance')
            raise BalanceInsufficientError()

        # 5. 扣款 + 流水（同事务）
        wallet.balance_cents -= unit_price
        wallet.total_spent_cents += unit_price
        db.add(WalletTransaction(
            customer_id=customer_id,
            type='charge',
            amount_cents=-unit_price,
            balance_after_cents=wallet.balance_cents,
            bulk_batch_id=batch_id,
            idempotency_key=idempotency_key,
        ))
        db.commit()

        # 6. 余额低预警
        if wallet.balance_cents < 2000:  # $20
            notify_low_balance.delay(customer_id)
```

### 3.3 发送 Worker 调度

```
[bulk_batch created]
        │
        ▼
bulk_send_dispatcher_task
        │
        ├─► 选 N 个 healthy accounts (从 pool + bulk 专属池)
        ├─► 把 targets 分成 N 片
        └─► 派发 N 个 bulk_send_worker_task

bulk_send_worker_task(account_id, batch_id, shard_targets)
        │
        For each target in shard:
        │
        ├─► 文案变体随机选一个
        ├─► 调 client.send_message(target, content)
        ├─► 成功 → status=sent → 触发 bulk_wallet_charge
        ├─► 失败 → status=failed + 重试 1 次
        ├─► FloodWait → sleep then 继续
        ├─► sleep random(30-180s)  ← 反 spam
        └─► 30 分钟内连续 5 次失败 → 暂停该账号
```

### 3.4 Listener 改造

[listener_service.py](backend/app/services/listener_service.py) 在收到 worker 号的私聊回复时新增分支：

```python
# 现有逻辑：进 lead 表
existing_lead = find_lead(account_id, from_user_id)

# 新增：检查是否是 bulk 已发送对象
if not existing_lead:
    bulk_target = db.exec(select(BulkTarget).where(
        BulkTarget.tg_user_id == from_user_id,
        BulkTarget.status.in_(['sent', 'delivered'])
    )).first()

    if bulk_target:
        lead = Lead(
            account_id=account_id,
            telegram_user_id=from_user_id,
            customer_id=bulk_target.customer_id,
            source='bulk',
            bulk_batch_id=bulk_target.batch_id,
            ...
        )
        # 标记 target 为 replied
        bulk_target.status = 'replied'
        # 更新 batch.replied counter
        ...

# WebSocket 推 bulk_reply 事件给客户后台
broadcast({'type': 'bulk_reply', 'batch_id': X, 'lead_id': Y})
```

> 💡 **关键复用**：bulk 回复进 lead 表后，**自动出现在现有 Inbox/CRM**，AI 副驾驶 + 销售接管全免费继承。

### 3.5 反 Spam 风控

| 控制点 | 阈值 |
|---|---|
| 单号每小时新私聊 | ≤ 3 条 |
| 单号每天新私聊 | ≤ 80 条 |
| 文案变体最少 | ≥ 5 个（提交批次时强制校验） |
| 失败熔断 | 单号 30 分钟内 5 次失败 → 自动暂停 |
| 内容预审 | LLM 扫一遍，赌博/诈骗类拒接（需 LLM 恢复后启用） |
| 客户隔离 | 不同 customer 的 batch 用不同账号子池，避免相互污染 |

## 4. 账号池策略

### 4.1 池子来源

| 来源 | 数量 | 用途 |
|---|---|---|
| 现有 worker 号（id 75-80） | 6 | MVP 启动期共享，仅 customer_id=null 的 pool 号 |
| 新注册 bulk 专属号 | 50（目标） | 1 个月后上岗，与 AaaS 客户号隔离 |

### 4.2 账号选择算法

```python
def select_accounts_for_batch(batch, target_count):
    """
    1. 优先选 bulk 专属池（role='bulk_sender' or tags 含 'bulk'）
    2. 不够再选 pool worker 号（customer_id IS NULL, status='active', health>=80）
    3. 排除当天已达 RPH 上限的号
    4. 按 health_score DESC 取 N 个，N = ceil(target_count / 50)  -- 每号承接 50 条
    """
    accounts = db.exec(
        select(Account)
        .where(Account.status == 'active')
        .where(Account.health_score >= 80)
        .where(or_(Account.role == 'bulk_sender', Account.customer_id.is_(None)))
        .where(Account.id.notin_(daily_quota_exhausted_ids))
        .order_by(Account.health_score.desc())
        .limit(ceil(target_count / 50))
    ).all()
    return accounts
```

## 5. 客户后台（新增 5 页）

| 路径 | 主要内容 |
|---|---|
| `/portal/wallet` | 余额 + 充值表单 + 流水表 |
| `/portal/bulk` | 批次列表（status 筛选） |
| `/portal/bulk/new` | 上传 CSV + 编辑模板 + 文案变体 + 预览成本 + 提交 |
| `/portal/bulk/{id}` | 实时进度（已发/失败/已回复/ETA）+ 暂停/恢复按钮 |
| `/portal/bulk/inbox` | 收件箱（复用现有 Leads 页，filter `source=bulk`） |

## 6. API Endpoints（新增）

### 客户 API

```
# Wallet
POST   /api/v1/customer/wallet/topup           # 充值（创建 USDT invoice）
GET    /api/v1/customer/wallet                 # 余额 + 累计统计
GET    /api/v1/customer/wallet/transactions    # 流水（分页）

# Bulk Batches
POST   /api/v1/customer/bulk/batches           # 创建批次（含 targets CSV 上传）
GET    /api/v1/customer/bulk/batches           # 列表
GET    /api/v1/customer/bulk/batches/{id}      # 详情进度
POST   /api/v1/customer/bulk/batches/{id}/start  # 启动
POST   /api/v1/customer/bulk/batches/{id}/pause  # 暂停
POST   /api/v1/customer/bulk/batches/{id}/cancel # 取消

# 收件箱（复用 leads）
GET    /api/v1/customer/leads?source=bulk     # bulk 回复（filter）
```

### 受信 webhook 改造

```
# 现有 webhook 增加 invoice_type=wallet_topup 处理分支
POST   /api/v1/webhooks/nowpayments
       └─ if invoice.metadata.type == 'wallet_topup':
            创建 wallet_transaction(type='topup') + 增加 balance
          else:  # 原 subscription 流程
            激活 subscription
```

## 7. 实施计划（6 周）

### W1：基础数据模型 + Wallet（当前周）

- ✅ SPEC 文档
- [ ] `customer_wallet` + `wallet_transaction` model
- [ ] Alembic 迁移
- [ ] Wallet API（topup / balance / transactions）
- [ ] NowPayments webhook 改造识别 wallet_topup
- [ ] Portal `/wallet` 页面
- [ ] 集成测试

### W2：Batch 模型 + CSV 上传

- `bulk_batch` + `bulk_target` + `bulk_template_variant` model
- Alembic 迁移
- 创建批次 API（含 CSV 解析）
- 成本预览计算（按阶梯单价）
- Portal `/bulk/new` 页面

### W3：发送 Worker + 扣款

- `bulk_send_dispatcher_task` + `bulk_send_worker_task` Celery 任务
- 账号选择算法
- 反 spam 控制（RPH / 失败熔断 / 间隔）
- `bulk_wallet_charge` 原子扣款
- Portal `/bulk` + `/bulk/{id}` 进度页

### W4：Listener 改造 + 回复关联

- listener 收到回复时关联 bulk_target
- lead 表 source 字段 + bulk_batch_id 字段
- WebSocket `bulk_reply` 事件
- Portal `/bulk/inbox` 页（复用 Leads filter）

### W5：客户后台收尾 + 文案变体

- 文案变体编辑器（同 batch 多版本）
- 变体随机选择算法
- 余额预警 + 暂停 batch

### W6：集成测试 + 上线准备

- 端到端测试（注册 → 充值 → 创建 batch → 发送 → 回复 → 接管）
- 文档：用户手册 bulk 章节
- 监控告警：账号封号率、扣款失败率、余额低客户数

## 8. 风险与对策

| 风险 | 概率 | 对策 |
|---|---|---|
| 账号池不够支撑客户量 | 高 | 客户充值时按"可用配额"显示 ETA，超量自动队列等 |
| 反 spam 封号率高 | 高 | RPH=3 强限速 + 文案变体 ≥5 + 客户隔离 + 失败熔断 |
| 客户内容违规（赌博/诈骗） | 中 | 提交批次时 LLM 预审 + 黑名单关键词正则 + 人工抽查 |
| 计费扣款竞态超扣 | 中 | wallet 行锁 + idempotency_key UNIQUE |
| 余额耗尽继续发送 | 中 | 余额 < 单条最小价时 batch 自动暂停 |
| Google 账号 suspend 影响 AI add-on | 已发生 | bulk 主功能不依赖 LLM，AI 回复是可选 add-on，等恢复 |

## 9. 不在 MVP 范围

- 客户自带账号（BYOA）
- API 接入（让客户编程发送）
- 高级模板（变量替换、A/B 测试）
- 多账号编排（按客户分配子池）
- 实时仪表板（暂时用列表 + polling）

这些 Phase 4 及之后再做。

---

**版本历史**

| 版本 | 日期 | 修订 |
|---|---|---|
| v1.0 | 2026-05-19 | 初版 SPEC，W1 开工 |
