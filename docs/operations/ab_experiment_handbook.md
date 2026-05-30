# 群内 AI 销售员 A/B 实验操作手册

> 适用范围：内部运营 / 调参用。客户视角不直接见 A/B 实验。
> 后端：Phase 4a + Phase 5 落地。前端 admin UI：Portal phase。

## 实验生命周期

1. **草稿 (draft)**：创建实验，定义 variants + primary_metric，不分流
2. **运行中 (running)**：流量按 variant weights 分配，指标自动写
3. **结束 (finished)**：手动停，报告固化

## 何时该跑 A/B

- 给客户调阈值（layer3_score / layer2_sim / layer3_confidence）
- 给客户调人设（speaking_style / catchphrases）
- 给客户调闲聊频率（daily_chitchat_quota）
- 给客户调 cooldown / quota（per_chat_cooldown_minutes / daily_reply_quota）

**何时不该跑**：

- 单客户 < 100 触发样本 / 周（统计功效不足，CI 太宽看不出差异）
- 灰度 < 1 周（短期波动盖过真实效果）
- 同时已经在跑一个 customer-scope 实验（Phase 4a `find_applicable_experiments` 只取首个匹配，重叠会被忽略）

## 创建实验

```http
POST /admin/group-ai/ab/experiments
Authorization: Bearer <admin-token>
Content-Type: application/json

{
  "name": "layer3_score_v1_v2_2026q3",
  "description": "对比 layer3 阈值 60 vs 70",
  "scope": "customer",
  "scope_value": 1,
  "primary_metric": "private_conversion_rate",
  "variants": [
    {"tag": "v1", "weight": 0.5, "params": {"layer3_score": 60}},
    {"tag": "v2", "weight": 0.5, "params": {"layer3_score": 70}}
  ]
}
```

返回：`{"id": <experiment_id>}`

**字段约定**：

- `scope`: `global` / `customer` / `monitor`
- `scope_value`: 对应 ID；global 时填 null
- `primary_metric`: 指标名（用于显著性检验的指标）
  - `reply_rate` — sent / 总触发
  - `private_conversion_rate` — 私聊转化（Phase 5 简化版返回 0，Phase 6 接入 Lead 表后真实）
  - `kick_rate` — 踢号率（基于 account_lifecycle_events）
- `variants[].weight`: 任意正数，自动归一
- `variants[].params`: 覆盖 customer `lead_detector_thresholds` 的 keys（不在 params 里的不改）。仅这一次请求 in-memory 生效，不持久化

### 启动 / 停止

```http
PUT /admin/group-ai/ab/experiments/{id}/start    # draft → running
PUT /admin/group-ai/ab/experiments/{id}/stop     # running → finished
```

无法从 `paused` 状态停（Phase 4a 没暴露 pause endpoint，可忽略）。

## 查看实验结果

### 简略指标

```http
GET /admin/group-ai/ab/experiments/{id}/metrics
```

返回 per-variant counters + 4 rates，不算显著性。最快速看个差异：

```json
{
  "v1": {
    "sent": 100, "suggested": 5, "skipped_total": 30, "failed": 2,
    "reply_rate": 0.730, "private_conversion_rate": 0.0,
    "kick_rate": 0.020, "anti_hallucination_failure_rate": 0.048
  },
  "v2": { ... }
}
```

### 完整报告

```http
GET /admin/group-ai/ab/experiments/{id}/report
```

返回 JSON 含每变体 95% 置信区间 + 两比例 Z 检验 p 值 + 显著性 bool。

关键字段：

- `variants[].reply_rate / private_conversion_rate / kick_rate / anti_hallucination_failure_rate` — 每变体指标值
- `variants[].reply_ci_lo / reply_ci_hi` 等 — 4 个指标各自的 95% 置信区间
- `significance.metric` — primary metric 名
- `significance.z` — z 统计量
- `significance.p_value` — 双侧 p 值
- `significance.significant_at_95` — bool, p < 0.05

### CSV 导出（给离线分析）

```http
GET /admin/group-ai/ab/experiments/{id}/report.csv
```

返回 `text/csv` 附件下载。header + 1 行 / variant + 1 行显著性 footer。

## 解读

### 看 primary_metric 的两个 variant 数值差距 + 显著性

- p < 0.05 → 差距显著，可以决策（推荐用 v2 或 v1）
- p >= 0.05 → 差距未达显著，看 CI 是否重叠决定继续观察还是停
  - CI 重叠很多 → 继续跑（样本不够）
  - CI 几乎不重叠但 p 略 > 0.05 → 接近显著，多跑一周
  - CI 完全重叠且差距小 → 没差异，停实验，按操作偏好选

### 看 kick_rate 副指标

如果某 variant kick 异常高（> 5% 周率），即使 primary 显著也要止损 —— 业务转化率高但账号死得快，长期 LTV 会崩。

### 看 anti_hallucination_failure_rate

`> 8%` 说明 LLM 出 spam 词频繁，可能：
- temperature 太高
- KB 内容不够 → 模型在编
- case_studies 没匹配上 → numeric anti-halluc 频繁拒

## 常见陷阱

- **同一 source_user 永远进同一 variant**（确定性 md5 哈希）—— 不会"换组"。Phase 4a Task 6 落地
- **同一时间一个 (customer, monitor) 只支持一个 running 实验** —— Phase 4a `find_applicable_experiments` 取首个匹配，多实验重叠后果未定义
- **样本量不平衡**：即使 50/50 weights，短期内可能有 60/40，看 CI 而非 raw 数字
- **`kick_rate` 算的是 sent 之后 48h 任意 kick 事件**，可能与本 sent 无因果（同一账号同时被多个事件影响），当作"相关性"看，不是"因果率"
- **样本太小时 CI 会很宽**，报告里数字看着差但其实可能没差异。N < 100 / variant 基本不可信
- **`private_conversion_rate` Phase 5 是 placeholder（返 0）**。Phase 6 接 Lead 表后才有真值

## 常见实验剧本

### 剧本 A：调 layer3_score 阈值

- v1: 60 (默认)
- v2: 70 (更严)
- primary_metric: `reply_rate`（希望 v2 触发更少但回复质量更高）
- 跑 1-2 周，看 v1 vs v2 reply_rate 是否过低，anti_hallucination_failure_rate 是否降低

### 剧本 B：调 layer2_sim ICP 阈值

- v1: 0.55 (默认)
- v2: 0.65 (更严)
- primary_metric: `private_conversion_rate`（希望识别更准的客户转化更高）
- 跑 2-3 周

### 剧本 C：调 persona speaking_style

- 改 worker_persona 数据时直接打 `param_version` 标签（Phase 1 字段）
- 不需要走 A/B 实验机制；离线对比 v1 (casual) vs v2 (techy) 的 conversion
- 对比 metrics_service 按 `customer.param_version` 聚合（需要扩展 service）

### 剧本 D：调闲聊频率

- v1: daily_chitchat_quota=7
- v2: daily_chitchat_quota=3
- primary_metric: `kick_rate`（闲聊太多踢号率会升？）
- 跑 4 周（kick_rate 变化慢）

## 故障排查

### 实验 start 后 0 流量

- 检查 `find_applicable_experiments` 是否返回非空：
  - `scope='customer'` 且 `scope_value` 是真实 customer_id
  - `scope='global'` 不带 `scope_value`
  - `status='running'`（不是 draft）

### experiment_tag 没写到 pending_replies

- 检查 pipeline 日志，看是否触发 "AB experiment lookup failed" warning（Phase 4a Critical 4 fix）
- 检查 `variant['weight']` 字段是否齐（malformed variant 会触发 except 但跳过 tag）

### metrics 算出来都是 0

- 检查 `experiment_tag` 实际值（PG: `SELECT DISTINCT experiment_tag FROM pending_replies`）
- 与查询的 tag 字符串完全匹配（区分大小写、空格、`:` 分隔符）

### CSV 下载 ContentType 不对

- 检查 `Content-Disposition` header 是否被 nginx 代理吃掉（生产 nginx config）

## 关联文档

- Spec: `docs/superpowers/specs/2026-05-28-group-ai-sales-presence-design.md` §10
- Plan Phase 4a: `docs/superpowers/plans/2026-05-29-group-ai-sales-phase4a.md`
- Plan Phase 5: `docs/superpowers/plans/2026-05-29-group-ai-sales-phase5.md`
- Memory: `project_group_ai_phase4a_state.md`, `project_group_ai_phase5_state.md`（运行后写）
