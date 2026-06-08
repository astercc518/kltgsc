# 群发 username/phone Peer 解析 —— 设计文档

- 日期：2026-06-08
- 分支：feat/admin-customer-ops
- 范围：补齐 bulk_send 对 username / phone 目标的真实发送能力，关闭「只支持 tg_user_id 的 W3 MVP」缺口

## 背景与问题

客户需求：采集 5 个大群（按「尝试群发条数 = 30 万」口径规划号池）→ 对名单群发 → 回复者拉群 → 客户自助后台。代码审查结论：采集 / 群发 / 拉群 / 客户后台四条链路均已实现，**唯一缺口是群发的 peer 解析**。

现状 `_do_send`（[backend/app/tasks/bulk_send_tasks.py](../../../backend/app/tasks/bulk_send_tasks.py) 第 283 行）对没有 `tg_user_id` 的目标直接返回 `real_send_needs_tg_user_id_in_mvp`，username / phone 名单发不出。

### 关键技术事实（决定方案根基）

Pyrogram 给陌生人发消息需要 `(user_id + access_hash)` 或一个**可实时解析的 username**。`access_hash` **绑定具体账号**——只有「见过」该用户的账号才持有。

- 采集号用 `get_chat_members` 采群，access_hash 缓存在**采集号**；
- 群发由**号池里的其他号**执行，这些号没见过目标 → 用裸 `tg_user_id` 发会 `PEER_ID_INVALID`。

因此**裸 user_id 在号池冷发模式下基本不可用**。可靠的冷发标识优先级为：

1. **username** —— `send_message("@username")`，Pyrogram 实时解析，最可靠；
2. **phone** —— `import_contacts` 把手机号解析成 user 再发；
3. 裸 user_id —— 仅在「发送号恰好缓存过该 peer」时成功，号池场景基本作废。

采集时已存 username（[telegram_client.py](../../../backend/app/services/telegram_client.py) 第 540 行），所以让采集→群发名单携带 username，冷发即通。

## 目标 / 非目标

**目标**
- 群发支持 username 目标（实时解析发送）。
- 群发支持 phone 目标（`import_contacts` 解析 → 发送 → `delete_contacts` 清理）。
- 严格区分「目标级永久失败」与「账号级风控失败」，前者不冷却账号、不计入熔断。
- 创建批次时过滤掉「只有 user_id、无 username 无 phone」的不可达目标，标记 `skipped`、原因 `no_handle`，不扣费不占号。

**非目标（本期不做）**
- 不做解析结果缓存 / 不新增 `resolved_user_id` 列 / 不做数据库迁移（access_hash 不跨号缓存，重试受熔断限制，缓存收益有限）。
- 不改 mock 发送路径（`BULK_SEND_MOCK`）。
- 不做采集号回填 username（无句柄目标按「跳过+标记 unreachable」处理；后续可单独增强）。
- 不动计费、节流、熔断的现有公式。

## 设计

### 1. 新增 peer 解析发送层

在 [backend/app/services/telegram_client.py](../../../backend/app/services/telegram_client.py) 新增：

```
async def resolve_and_send_with_client(account, *, tg_user_id, tg_username, phone,
                                        message, db_session) -> (ok: bool, err: str|None)
```

复用现有 `_create_client_and_run` 的客户端生命周期 / 代理 / 设备指纹 / 解密 session / IPv6 重试 / FloodWait·PeerFlood·Banned 异常处理。解析优先级：

1. `tg_username` 存在 → `client.send_message("@"+username, message)`；
2. 否则 `phone` 存在 →
   - `users = client.import_contacts([InputPhoneContact(phone, first_name="x")])`
   - 命中 → `client.send_message(user.id, message)`；
   - `finally` 中 `client.delete_contacts([user.id])` 清理（无论发送成功与否，避免污染联系人、降低风控信号）；
   - 未命中（手机号不在 TG）→ 返回目标级永久失败 `phone_not_on_telegram`；
3. 否则裸 `tg_user_id` → 尝试 `client.send_message(int(tg_user_id), message)`，失败按错误分类处理。

`typing` 动作（`send_chat_action`）沿用现有拟人化逻辑。

### 2. 改 `_do_send`

- 删除 `if not target.tg_user_id: return False, "real_send_needs_tg_user_id_in_mvp"`。
- 改为：只要 `target` 有任一标识（user_id / username / phone）就调用 `resolve_and_send_with_client(...)`，把三个字段都传入。
- 三者皆空的目标本不应进入发送（已在创建期过滤），防御性返回 `no_handle`。

### 3. 错误分类（核心）

把 `resolve_and_send_with_client` 的返回错误归两类，`_do_send` / worker 据此分流：

**目标级永久失败**（标记 target `failed` + `failed_reason`，不重试、**不冷却账号、不计入连续失败熔断**）：
- `USERNAME_NOT_OCCUPIED` / `USERNAME_INVALID`
- `phone_not_on_telegram`（import_contacts 未命中）
- `USER_PRIVACY_RESTRICTED` / `PRIVACY_RESTRICTED`
- `PEER_ID_INVALID`（裸 user_id 不可达）

**账号级失败**（沿用现状：账号进 cooldown、target 回 pending 等重发、计入熔断）：
- `FloodWait` / `PeerFlood` / `UserBannedInChannel` / `UserDeactivated`

实现上：`resolve_and_send_with_client` 永久失败时返回 `(False, "perm:<code>")` 前缀；账号级仍按现有 `AccountException` 抛出由上层捕获。`_do_send` 解析 `perm:` 前缀决定是否惩罚账号 / 计熔断。

### 4. 创建期过滤无句柄目标

在目标落库点（`bulk_send_service.parse_targets_csv` 之后的持久化环节，或 `customer_bulk` 创建批次处）：
- 解析出的行若 `tg_user_id` 存在但 `tg_username` 与 `phone` 均空 → 以 `status=skipped`、`failed_reason="no_handle"` 落库，计入 `skipped_count`，不计入待发数、不预扣费。
- 在创建响应 summary 增加 `skipped_no_handle` 计数，前端成本预览可提示「N 个目标无 username/phone，号池冷发不可达，已跳过」。

## 数据流

```
CSV/采集名单 → parse_targets_csv → 落库(无句柄→skipped:no_handle)
  → start batch → worker 取 pending target + 分配账号
  → _do_send → resolve_and_send_with_client
       ├─ username: send_message("@u")
       ├─ phone: import_contacts → send → delete_contacts
       └─ user_id: send_message(id)  (多半 PEER_ID_INVALID)
  → 成功: target=sent, 扣费
  → 目标级永久失败: target=failed(reason), 账号无惩罚
  → 账号级失败: 账号 cooldown, target 回 pending, 计熔断
```

## 测试策略（TDD）

mock pyrogram `Client`，先写测试后写实现：

1. username 目标 → 调用 `send_message("@u", ...)`、返回成功。
2. phone 命中 → `import_contacts` → `send_message(user.id)` → `delete_contacts` 被调用（成功与失败路径都清理）。
3. phone 未命中 → 返回 `perm:phone_not_on_telegram`，不抛账号异常。
4. `USERNAME_NOT_OCCUPIED` / `USER_PRIVACY_RESTRICTED` → `perm:` 前缀，账号不冷却、不计熔断。
5. `FloodWait` / `PeerFlood` → 抛 `AccountFloodWaitException`，账号 cooldown，target 回队列。
6. `_do_send` 解析优先级：同时有 username+phone+user_id 时走 username。
7. 创建期过滤：只有 user_id 的行落库为 `skipped:no_handle`，不计待发、不预扣费。
8. mock 路径（`BULK_SEND_MOCK=1`）行为不变（回归保护）。

## 影响文件

- `backend/app/services/telegram_client.py` —— 新增 `resolve_and_send_with_client`。
- `backend/app/tasks/bulk_send_tasks.py` —— 改 `_do_send` 解析优先级 + 错误分类分流。
- `backend/app/services/bulk_send_service.py` 或 `backend/app/api/v1/endpoints/customer_bulk.py` —— 创建期过滤无句柄目标。
- `backend/tests/` —— 新增上述 8 项测试。

无数据库迁移、无 API 破坏性变更。

## 风险与备注

- **风控**：phone 路径的 `import_contacts` 风控信号更重，且会短暂写入联系人；`delete_contacts` 必须在 `finally` 保证清理。
- **配额**：username/phone 解析消耗 ResolveUsername/import 配额，可能触发 24h FloodWait——已归入账号级失败由 cooldown 吸收。
- **可达性预期**：大量目标因隐私设置（`USER_PRIVACY_RESTRICTED`）天然收不到，属正常，计入 failed 不惩罚账号；这会让「发 30 万」的实际送达显著低于尝试数，运营侧需以 pilot 实测率为准。
- **内容风控**：群发文案需先过 L0/L1 内容过滤（见 LLM 安全架构记忆），避免触发 Vertex/账号封禁——本期不在范围内，但上线前置依赖。
