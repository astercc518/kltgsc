# 群内 AI 销售员（Group AI Sales Presence）设计

**日期**：2026-05-28
**作者**：通过 brainstorming session 与产品方共同设计
**关联记忆**：[[project-core-direction]] · [[ai-reply-pipeline-state]] · [[project-kb-and-handoff-decisions]] · [[project-epic5-state]] · [[project-epic4-kb-state]]
**关联 Epic**：本设计属于"群控 + AI 客服"主线的核心新链路，与 Epic 5（主号接管）和 Epic 4（行业 KB）并列

---

## 1. 目标与产品形态

### 1.1 用户痛点
当前 TGSC 项目里，群控账号的群聊链路只有两条：
- **关键词命中 → 私聊 DM 截流**（`intercept_service.py`）
- **主动营销话术**（`shill_dispatcher.py`）

**还不存在「群控账号像真人销售一样、在群里主动识别业务线索并精准回复」的能力。** `ai_reply_service.py` 仅对私聊生效，KB+RAG+反幻觉等基础设施只服务私聊管线。

### 1.2 产品形态
群控账号在所监听的群里，遇到客户发出的业务线索消息时，**直接在群内三段式公开回复**：

1. **方案段**：针对客户需求点提出业务解决方案（2-3 句，专业但不官方化）
2. **案例段**：引用一条真实成交案例 + 具体数字（1 句，避免编造）
3. **引导段**：自然提议私聊深聊（1 句，不出现"+V"等暴露词）

整段不超过 80 中文字，单次单账号发出。

### 1.3 风控总要求 —— **极致拟人**
- 同一线索在同群仅 1 个 worker 账号回复（账号互避）
- 消息进来后**先观望 60-900s**，看是否已有真人接话，避让真人优先
- 发送前模拟人类打字时长（30-120s 随机）
- 每个 worker 账号有独立人设（地区/职业/口头禅/方言/活跃时段）
- 账号有"日常生活感"：每天定额发 5-10 条**非业务闲聊**到群里刷存在感
- 各种日额、群额、cooldown 全部可调

---

## 2. 总体架构

候选架构：**责任链 + Postgres 状态机 + Celery 延时任务**（候选 B，最终选定）。

### 2.1 数据流

```
listener_service 收到群消息
    ↓
group_reply_pipeline.entrypoint(msg, account, monitor)
  · 早返：collector 角色 / 未归属客户 / 客户未开 ai_group_reply feature
    ↓
LeadDetector 三层过滤
  · Layer 1: 关键词预筛 (keyword_filters: include/exclude/mode)
  · Layer 2: ICP 画像 embedding 相似度 ≥ threshold
  · Layer 3: LLM 评分 + 需求提取 (score ≥ 60 AND confidence ≥ 0.7)
    ↓
pending_replies 行入库 (status=observing, fire_at=now+random(60..900s))
    ↓
Celery beat (每 30s) 扫 fire_at <= now AND status=observing
    ↓
RiskController
  · 检查 1: 是否在 responder candidate 的 active_hours 内（否→推迟 fire_at）
  · 检查 2: 5 min 内群里是否已有真人/其他号接话
  · 检查 3: 同 (chat_id, source_user_id) 48h 内是否已被自家任一账号回过
  · 检查 4: 选 responder account（加权随机：剩余日额×0.5 + 距上次发送×0.5 + 人设匹配加权）
    ↓
ReplyComposer
  · Step A: KB 检索 (kb_retrieval pgvector + reranker top 3)
  · Step B: case_studies 匹配 (embedding 余弦 top 1-2)
  · Step C: LLM 拼三段式 (vertex gemini-flash, temperature=0.7)
  · Step D: 反幻觉过滤 (复用 shill_dispatcher._anti_hallucination_filter
                       + 数字一致性 + 模板重复检测)
  · Step E: 失败重试 2 次仍失败 → 转副驾驶 (写 LeadInteraction kind=ai_suggestion
                                          + ws_manager 推 Inbox)
    ↓
Persona 改写（纯字符串变换，无 LLM）
  · speaking_style 调整 · 30% 概率插入口头禅 · 标点拟人化
    ↓
Dispatcher
  · 随机 30-120s typing 时延
  · Telethon 发群
  · 写 lead + LeadInteraction
  · billing_service 扣费 $0.50
  · status=sent

并行 Celery beat:
ChitchatScheduler (每 5 min tick)
  · 对每个 worker 账号 × 每个常驻群
  · 概率 = remaining_quota / hours_left_today
  · 与业务回复 5 min 互斥
  · 闲聊话题不命中本群 monitor 关键词
  · LLM 生成具体闲聊文本 + 反幻觉
  · 入队随机 30-600s 后发送
  · 写 chitchat_log
```

### 2.2 模块清单

| 模块 | 性质 | 文件 |
|---|---|---|
| `group_reply_pipeline` | 新建 | `backend/app/services/group_reply_pipeline.py` |
| `lead_detector` | 新建 | `backend/app/services/lead_detector.py` |
| `icp_embedding_match` | 新建 | `backend/app/services/icp_embedding_match.py` |
| `risk_controller` | 新建 | `backend/app/services/risk_controller.py` |
| `reply_composer` | 新建 | `backend/app/services/reply_composer.py` |
| `persona_rewriter` | 新建 | `backend/app/services/persona_rewriter.py` |
| `group_dispatcher` | 新建 | `backend/app/services/group_dispatcher.py` |
| `chitchat_scheduler` | 新建 | `backend/app/services/chitchat_scheduler.py` + Celery beat |
| `kb_retrieval` | 复用 | pgvector + reranker 已就绪 |
| `llm.analyze_intent` | 扩展 | 新增 `score_lead_message` 函数 |
| `keyword_monitor_service` | 复用 | 作为 Layer 1 实现 |
| `listener_service` | 改 1 行 | 仅添加 `await group_reply_pipeline.entrypoint(...)` |
| `intercept_service` | 不动 | 保留私聊截流场景 |
| `ai_reply_service` | Phase 4 扩展 | 接入群→私聊上下文 |
| `shill_dispatcher._anti_hallucination_filter` | 复用 | 反幻觉过滤函数 |
| `billing_service` | 复用 | $0.50/条扣费（沿用 PR#4 idempotent 机制） |

### 2.3 三条 AI 链路边界

| 链路 | 触发 | 处理服务 |
|---|---|---|
| **群内主动回复**（本设计） | 群消息命中三层过滤 | `group_reply_pipeline` |
| **私聊深谈** | 客户私聊主号 | `ai_reply_service`（已有） |
| **销售接管副驾驶** | 销售在 Inbox 点接管 | `ai_enabled=false` + 建议模式（已有） |

三条互不污染。群→私聊衔接由 `ai_reply_service` 在 Phase 4 查 `pending_replies.lead_id` 上下文实现。

---

## 3. LeadDetector 三层过滤

### 3.1 Layer 1：关键词预筛

扩展 `monitor` 表新增 `keyword_filters JSONB`：

```json
{
  "include": ["BTC", "比特币", "USDT", "求渠道"],
  "exclude": ["免费", "广告", "求带"],
  "mode": "any"
}
```

- 旧 `keyword` 字段保留，作为向后兼容。当 `keyword_filters` 为 NULL 时降级用旧字段。
- 输出：`{pass: bool, matched: [string]}`
- 成本：纯字符串匹配，零开销

### 3.2 Layer 2：ICP 画像 embedding 相似度

新增 `customer` 表 3 字段：
- `icp_profile_text TEXT` —— 客户在 portal 填的理想客户描述（200-500 字自由文本）
- `icp_profile_embedding vector(768)` —— save 时自动用 Vertex `gemini-embedding-001` 生成
- `lead_detector_thresholds JSONB DEFAULT '{"layer2_sim":0.55,"layer3_score":60,"layer3_confidence":0.7}'`

流程：
1. 客户在 portal 录入 ICP 文本 → `embedding_service.embed()` → 写入 `icp_profile_embedding`
2. Layer 1 通过的群消息：`embed(message.text)` → 与 `customer.icp_profile_embedding` 算余弦相似度
3. 相似度 ≥ `thresholds.layer2_sim` → 通过
4. 输出：`{similarity: float, pass: bool}`

成本估算（1000 客户 × 10 监控 × 500 群消息/日 → 5M 消息/日总量，Layer 1 通过率 ~5%）：
- 250k embedding/日 × ~50 token = 12.5M token/日 × Vertex `gemini-embedding-001` $0.025/M = **~$0.3/日**
- 单客户日均 < $0.001，可忽略

### 3.3 Layer 3：LLM 评分与需求提取

扩展 `llm.py`，新增 `score_lead_message(text, icp_text, kb_top3, recent_context)` 函数。

**输入上下文**：
- 当前消息 `text`
- 客户 ICP 文本 `icp_text`
- KB 检索 top 3 块（限制：单个客户的 tenant filter）
- 最近 5 条群上下文（用 group_history 的最近 5 条，避免孤立判断）

**输出结构化 JSON**：

```json
{
  "score": 0-100,
  "intent_type": "buy|sell|ask|chat|spam|other",
  "extracted_needs": ["想买 100k USDT 一次性", "海外汇款"],
  "suggested_solution_topic": "USDT 大额场外结算",
  "confidence": 0.0-1.0,
  "reason": "用户明确询问 100k 量级 USDT 渠道..."
}
```

**通过条件**：`score >= thresholds.layer3_score AND confidence >= thresholds.layer3_confidence`

**边界值处理**：
- score / confidence 落在阈值附近（如 score 55-60、confidence 0.6-0.7）的样本：仍写 `pending_replies` 但 `status='skipped_borderline'`，用于后续训练阈值

**成本估算**：每条 LLM 调用 ~1k token in, 200 token out。Layer 1+2 通过率假设 0.5% → 5M × 0.5% = 25k LLM 调用/日 × $0.0005 = **~$12.5/日全平台**，单客户分摊 1 分钱量级。

---

## 4. 数据模型

### 4.1 现有表扩展

#### `customer`
```sql
ALTER TABLE customers ADD COLUMN icp_profile_text TEXT;
ALTER TABLE customers ADD COLUMN icp_profile_embedding vector(768);
ALTER TABLE customers ADD COLUMN lead_detector_thresholds JSONB
    DEFAULT '{"layer2_sim":0.55,"layer3_score":60,"layer3_confidence":0.7}';
ALTER TABLE customers ADD COLUMN param_version TEXT DEFAULT 'v1';  -- A/B 标签
```

#### `monitor`
```sql
ALTER TABLE monitors ADD COLUMN keyword_filters JSONB;  -- {include, exclude, mode}
```

### 4.2 新表

#### `pending_replies` —— 全管线状态机

```sql
CREATE TABLE pending_replies (
  id BIGSERIAL PRIMARY KEY,
  customer_id INT NOT NULL REFERENCES customers(id),
  monitor_id INT NOT NULL REFERENCES monitors(id),
  responder_account_id INT REFERENCES accounts(id),

  chat_id BIGINT NOT NULL,
  message_id BIGINT NOT NULL,
  source_user_id BIGINT NOT NULL,
  source_text TEXT NOT NULL,

  layer1_matched JSONB,
  layer2_similarity FLOAT,
  layer3_score INT,
  layer3_needs JSONB,
  layer3_solution_topic TEXT,
  layer3_confidence FLOAT,

  status TEXT NOT NULL,
  -- observing | risk_check | composing | sent
  -- | skipped_human_replied | skipped_throttled | skipped_dup
  -- | skipped_borderline | skipped_no_account | failed | suggested
  fire_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  decided_at TIMESTAMPTZ,
  sent_at TIMESTAMPTZ,
  skip_reason TEXT,

  reply_text TEXT,
  lead_id INT REFERENCES leads(id),

  experiment_tag TEXT  -- A/B 实验分组标签
);

CREATE INDEX idx_pending_replies_scan ON pending_replies(status, fire_at);
CREATE INDEX idx_pending_replies_dedup ON pending_replies(customer_id, chat_id, source_user_id, created_at);
```

#### `case_studies` —— 成交案例库

```sql
CREATE TABLE case_studies (
  id BIGSERIAL PRIMARY KEY,
  customer_id INT NOT NULL REFERENCES customers(id),

  industry TEXT, deal_size TEXT, period TEXT,
  problem TEXT, solution TEXT, outcome TEXT,
  tags JSONB,
  embedding vector(768),

  source TEXT NOT NULL,  -- 'manual_portal' | 'auto_extracted' | 'ai_confirmed'
  active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  last_used_at TIMESTAMPTZ
);

CREATE INDEX idx_case_studies_emb ON case_studies USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_case_studies_customer ON case_studies(customer_id) WHERE active = true;
```

#### `account_personas` —— 账号人设

```sql
CREATE TABLE account_personas (
  id BIGSERIAL PRIMARY KEY,
  account_id INT NOT NULL UNIQUE REFERENCES accounts(id),
  customer_id INT NOT NULL REFERENCES customers(id),

  display_name TEXT,
  age_range TEXT, region TEXT, occupation TEXT,
  speaking_style TEXT,
  -- formal | casual | techy | cute | northeastern_dialect | cantonese_flavor

  catchphrases JSONB DEFAULT '[]',
  active_hours JSONB DEFAULT '{"mon":[[9,18]],"tue":[[9,18]],"wed":[[9,18]],"thu":[[9,18]],"fri":[[9,18]],"sat":[],"sun":[]}',

  daily_reply_quota INT DEFAULT 5,
  per_chat_daily_quota INT DEFAULT 2,
  per_chat_cooldown_minutes INT DEFAULT 120,
  daily_chitchat_quota INT DEFAULT 7,  -- 用户决策范围 5-10, 默认取中位 7
  observation_window_seconds_range JSONB DEFAULT '[60,900]',
  typing_delay_seconds_range JSONB DEFAULT '[30,120]',

  param_version TEXT DEFAULT 'v1',  -- A/B 标签
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### `chitchat_pool` —— 闲聊话题库

```sql
CREATE TABLE chitchat_pool (
  id BIGSERIAL PRIMARY KEY,
  customer_id INT REFERENCES customers(id),  -- NULL = 全局内置话题
  topic_category TEXT,  -- weather | news | food | life | tech | gossip
  prompt_template TEXT NOT NULL,
  tags JSONB,
  active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### `chitchat_log` —— 防重 + 审计

```sql
CREATE TABLE chitchat_log (
  id BIGSERIAL PRIMARY KEY,
  account_id INT NOT NULL REFERENCES accounts(id),
  chat_id BIGINT NOT NULL,
  topic_id INT REFERENCES chitchat_pool(id),
  sent_text TEXT,
  sent_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX uq_chitchat_log_day ON chitchat_log(account_id, topic_id, chat_id, (sent_at::date));
```

### 4.3 A/B 实验框架表（Phase 4 引入）

#### `ab_experiments`

```sql
CREATE TABLE ab_experiments (
  id SERIAL PRIMARY KEY,
  name TEXT UNIQUE,
  description TEXT,
  scope TEXT,  -- 'global' | 'customer' | 'monitor'
  scope_value INT,
  variants JSONB,
  -- [{"tag":"v1","weight":0.5,"params":{"layer3_score":60}},
  --  {"tag":"v2","weight":0.5,"params":{"layer3_score":70}}]
  status TEXT,  -- 'draft' | 'running' | 'paused' | 'finished'
  primary_metric TEXT,  -- 'reply_rate' | 'private_conversion_rate' | 'kick_rate' | ...
  started_at TIMESTAMPTZ,
  ended_at TIMESTAMPTZ
);
```

实验框架细节见 §10。

### 4.4 Alembic 迁移

一次性迁移加上面 5 张新表 + 4 个字段。pgvector 扩展已在 Epic 4 阶段启用，HNSW 索引模式与 `ai_knowledge_base` 一致，无需额外配置。新字段默认 NULL/默认值，无需 backfill —— 客户在 portal 录入后生效；旧客户的群控账号在没有 persona 之前走兜底默认值（详见 §6.3）。

---

## 5. RiskController 决策规则

每条 `pending_replies` 行被 Celery beat 取出后，按以下顺序跑决策。每次跳过都写明确的 `skip_reason`，用于后续阈值调参和 A/B 分析。

### 5.1 决策序列

```
1. 当前时间在"此群任一 worker 候选账号的 active_hours"内吗？
   候选 = 此群中 customer_id 一致的 worker 账号集合
   ├─ 全部不在窗口内 → fire_at 推迟到"最早开窗的候选账号的窗口起点 + random(0..30min)"
   │                   status 维持 observing, return
   └─ 至少 1 个在窗口内 → 继续

2. 5 min 内群里是否已有真人/其他号接话？
   信号:
   - source_user_id 后续是否收到至少 1 条针对性 reply（reply_to_message_id 指向 source_message_id）
   - 同 chat 内其他用户在 source_message 后 5min 内提到 layer3_solution_topic 关键词
   - 同 chat 内 customer 旗下其它 worker 账号已 status='sent' 过这条
   ├─ 是 → status=skipped_human_replied, return
   └─ 否 → 继续

3. 同 (chat_id, source_user_id) 48h 内是否已被自家任一账号回过？
   ├─ 是 → status=skipped_dup, return
   └─ 否 → 继续

4. 选 responder account（核心调度）:
   候选 = 此群所有 worker 账号 ∩ 活跃窗口内 ∩ 未超日额 ∩ 未超群日额 ∩
          上次发送距今 > per_chat_cooldown
   权重 = (剩余日额 × 0.5) + (距上次发送时长 normalized × 0.5)
          + 人设匹配加权(persona.occupation 与 layer3_solution_topic 相关时 +0.3)
   ├─ 候选为空 → status=skipped_throttled, return
   └─ 加权随机选 1 个 → responder_account_id=X, status=composing
```

### 5.2 真人接话检测细节

`is_human_or_other_account_replied(pending_reply)` 实现思路：
- 查询 `group_messages` 表（listener 已存所有群消息）where chat_id=X AND message_id > pending_reply.message_id AND created_at < created_at + 5min
- 筛 reply chain：`reply_to_message_id == pending_reply.message_id` → 命中
- 关键词共现：消息文本包含 `layer3_solution_topic` 拆词后任一关键词 → 弱命中
- 自家其它账号（同 customer_id）已 sent 同线索 → 命中
- 任一命中即返回 true

### 5.3 配额检查

所有日额从 `account_personas` 取值，按账号本地时间（active_hours 暗示账号所在时区，可后续支持显式时区字段）的"今日"计算：

- `daily_reply_quota`：扫 `pending_replies` where responder_account_id=X AND status='sent' AND sent_at >= today
- `per_chat_daily_quota`：同上 + AND chat_id=Y
- `per_chat_cooldown_minutes`：取该账号该群最近一次 sent_at，与 now 差值

---

## 6. ReplyComposer 三段式生成

### 6.1 流水线

```
Step A: KB 检索 (kb_retrieval.search)
   query = layer3_solution_topic
   tenant_filter: customer_id
   top_k=5 → reranker top 3

Step B: case_study 匹配
   query_embedding = embed(json.dumps(layer3_needs))
   SELECT * FROM case_studies
   WHERE customer_id=X AND active=true
   ORDER BY embedding <=> query_embedding
   LIMIT 2
   ├─ 无匹配（< 阈值 0.4） → 用 KB 兜底, 标记 case_fallback=true
   └─ 取 case_top1

Step C: LLM 拼三段式草稿 (vertex gemini-flash, temperature=0.7)
   见 §6.2 prompt 模板

Step D: 反幻觉过滤
   - 复用 shill_dispatcher._anti_hallucination_filter (暴露词)
   - 数字一致性: 回复中所有数字必须能在 case_top1 或 kb_top3 中找到来源
   - 长度截断: 超过 80 字截断到最近的句末
   - 重复模板检测: 与同 customer 最近 3 条已发回复 cosine sim 不能 > 0.85

   失败 → goto Step C 重新生成最多 2 次

Step E: 2 次仍失败 → status=suggested
   - 写 LeadInteraction kind='ai_suggestion', not_sent=true
   - ws_manager.broadcast({"type":"ai_suggestion_pending", lead_id, suggested_text})
   - 销售在 Inbox 看到，一键发出或改写后发出
   - 不扣 $0.50（仅 sent 状态扣费）
```

### 6.2 LLM Prompt 模板

```
你扮演 {persona.display_name} ({persona.region} / {persona.occupation})，
风格 {persona.speaking_style}，正在 TG 群里看到陌生人发了一条消息。

群最近 5 条上下文:
{recent_context}

刚才那条触发消息原文:「{source_text}」

你提取到的对方需求点: {layer3_needs}
建议谈论的方案主题: {layer3_solution_topic}

你的业务知识 (来自 KB):
{kb_top3 拼接}

你最近的真实成交案例 (必须使用其中的具体数字, 不要编):
{case_top1}

请回复 3 句话, 共不超 80 中文字:
1. 一句话方案: 针对对方需求点提出做法 (专业但不要"作为专业人士..."这种官话)
2. 一句话案例: 引用上面的真实案例 + 具体数字
3. 一句话引导: 自然提议私聊深聊

禁止:
- 出现"作为 AI"/"我是助手"/"作为大模型"等暴露词
- 出现"+V"/"加我 V"/"扫码"/"微信" (TG 群里反常)
- 编造任何未在案例数据里出现的数字
- 超过 80 字
- 使用超过 1 个 emoji
- 模板化套话 (如"亲，了解一下"、"专业解答"、"竭诚为您服务")
```

### 6.3 兜底 Persona

当 worker 账号尚未配置 `account_personas` 时使用以下保守默认（**注意：默认值与 §4.2 表 DDL 不同，是为了"未配置即降级"**）：

```python
DEFAULT_PERSONA = {
    "display_name": "用户",  # 用 TG 账号自身昵称
    "region": "未配置",
    "occupation": "未配置",
    "speaking_style": "casual",
    "catchphrases": [],
    "active_hours": "工作日 9-22",
    "daily_reply_quota": 3,  # 偏保守
    "per_chat_daily_quota": 1,
    "per_chat_cooldown_minutes": 240,
    "daily_chitchat_quota": 0,  # 默认不闲聊
    "observation_window_seconds_range": [120, 900],
    "typing_delay_seconds_range": [45, 120]
}
```

### 6.4 数字一致性反幻觉

```python
def numeric_consistency_check(reply_text, case_top1, kb_top3):
    reply_numbers = extract_numbers(reply_text)  # 抽取所有数字（整数+小数+百分号+量级单位）
    source_numbers = set()
    for src in [case_top1, *kb_top3]:
        source_numbers.update(extract_numbers(src))
    hallucinated = [n for n in reply_numbers if n not in source_numbers]
    return len(hallucinated) == 0, hallucinated
```

抽取规则：连续数字 + 可选量级（k/万/百万/M/亿/B）+ 可选单位（USDT/RMB/USD/%/天/笔/单），都视为同一标识符做比较。

---

## 7. Persona 改写 + ChitchatScheduler

### 7.1 Persona 改写（无 LLM，纯字符串变换）

```
1. 按 speaking_style 词表替换:
   - formal: 不变
   - casual: 句末 30% 概率加 "哈/咯/嗯"
   - techy: 1-2 个术语替换 (e.g., "客户"→"用户", "方案"→"打法")
   - northeastern_dialect: 词替换表 "搞"→"整", "应该"→"得"
   - cantonese_flavor: 词替换表 "是"→"系", 句末加 "啦"

2. 30% 概率插入 1 个口头禅 (从 persona.catchphrases 随机)
   插入位置: 句首或句中(逗号后), 不在句末

3. 标点拟人化:
   - 30% 概率句末省略标点
   - 偶尔双标点 ("..." 或 "?!", 5%)
   - 偶尔小写英文/打错字, 5%

4. 长度二次校验, 超 80 字 → 截断到最近句末
```

确定性、零 LLM 成本、易测试。

### 7.2 ChitchatScheduler

独立 Celery beat，**与业务回复管线完全解耦**：

```python
@celery_app.task
def chitchat_scheduler_tick():
    for account in active_worker_accounts():
        for chat_id in account.joined_groups:
            persona = get_persona(account.id)
            if not persona or persona.daily_chitchat_quota <= 0:
                continue

            sent_today = count_chitchat_log_today(account.id, chat_id)
            quota_left = persona.daily_chitchat_quota - sent_today
            if quota_left <= 0:
                continue

            # 当天均匀分布的概率
            hours_left = max(0.5, hours_until_active_window_end(persona))
            fire_prob = min(0.5, quota_left / hours_left / 12)  # 12 = beat 每 5min 跑一次
            if random() > fire_prob:
                continue

            # 业务回复互斥窗口
            if recent_business_reply(account.id, chat_id, minutes=5):
                continue

            # 选话题 (排除当天已发, 排除会命中本群 monitor 关键词)
            topic = pick_chitchat_topic(account, chat_id)
            if not topic:
                continue

            # LLM 演绎成具体内容
            text = llm.generate_chitchat(topic.prompt_template, persona)
            text = anti_hallucination_chitchat(text)
            if not text:  # filter 失败
                continue

            # 关键词命中再次校验 (避免触发自家 LeadDetector)
            if matches_any_monitor_keyword(text, chat_id):
                continue

            # 入队
            delay = random.randint(30, 600)
            schedule_send.apply_async(args=[account.id, chat_id, text], countdown=delay)

            # 立即写 log 占位防重
            insert_chitchat_log(account.id, chat_id, topic.id, text, sent_at=now + timedelta(seconds=delay))
```

### 7.3 关键互斥保证

| 场景 | 处理 |
|---|---|
| 同账号是 5 个客户的 worker | account.customer_id 是唯一归属，persona 也归属唯一 customer；不会出现"一号多人格" |
| 同账号同群同时被业务和闲聊调度 | 业务回复优先；闲聊检测 5min 内有业务发送会跳过 |
| 闲聊话题不慎命中关键词 | 选题阶段过滤 + 反幻觉 filter 二次校验 + 发送前最终再校验 |
| Layer 2 ICP embedding 服务挂 | 降级到 Layer 1 + Layer 3 直跑（warn 日志），不停摆全管线 |
| LLM 持续失败 | pending_reply status=failed/suggested，不阻塞下一条 |
| Persona 未配置 | 用 §6.3 兜底默认值 |

---

## 8. 与现有系统集成

### 8.1 后端集成点（4 处改动）

1. **`backend/app/services/listener_service.py`** —— 群消息处理 fn 加 1 行：
   ```python
   await group_reply_pipeline.entrypoint(message, account, monitor)
   ```
   入口自己判断 skip（collector 角色 / 未归属客户 / customer feature 未开）

2. **`backend/app/services/ai_reply_service.py`**（Phase 4 改动） —— 私聊 LLM context 拼接时新增查询：
   ```sql
   SELECT * FROM pending_replies
   WHERE customer_id = $1 AND source_user_id = $2 AND status = 'sent'
   ORDER BY sent_at DESC LIMIT 3
   ```
   把"群内 AI 之前对此用户的回复 + extracted_needs"喂给私聊 LLM，保证群→私聊深聊上下文连续

3. **`backend/app/services/billing_service.py`** —— `pending_replies.status='sent'` 触发 $0.50 扣费（复用 PR#4 idempotent 机制）；status='suggested'/'failed' 不扣费

4. **副驾驶通道集成** —— 反幻觉 2 次失败 → 写 `LeadInteraction (kind='ai_suggestion', is_sent=false)` + `ws_manager.broadcast({type:'ai_suggestion_pending', lead_id, suggested_text})` 推送 Inbox（复用 Epic 5 副驾驶 UI）

### 8.2 Portal 客户配置 UI（新增 1 个 nav 项「群内 AI 销售员」）

```
[群内 AI 销售员] (Portal 新增 nav 项)
├─ ICP 画像
│   - 自由文本编辑器 200-500 字, 内嵌示例引导
│   - 保存按钮 → 自动重新生成 embedding
│
├─ 关键词过滤 (per monitor)
│   - include / exclude 标签编辑器
│   - 匹配模式: all | any
│
├─ 识别灵敏度
│   - layer2_sim 阈值滑块 (0.3-0.8)
│   - layer3_score 阈值滑块 (40-90)
│   - layer3_confidence 阈值滑块 (0.5-0.95)
│   - [恢复默认] 按钮
│
├─ 案例库
│   - [+ 手动录入] 表单（Phase 2）
│   - [扫描历史会话自动生成] 按钮（Phase 2）
│   - 案例列表卡片视图（编辑/禁用/删除）
│
├─ 账号人设 (per worker account 一张卡, Phase 3)
│   - 显示名 / 地区 / 职业 / 风格 / 口头禅编辑器
│   - 活跃时段选择器（周×小时网格）
│   - 各种日额/群额/cooldown 数值输入
│
├─ 闲聊话题库 (Phase 3)
│   - 全局话题勾选: [√ 天气][√ 美食][√ 时事][ 科技八卦]...
│   - [+ 自定义话题] (prompt_template 编辑)
│
└─ 实时统计 (精简版, Phase 4)
    今天:  命中 142  |  发出 53  |  转化 12 (22%)
    [展开] 跳过明细 / 拦截率分布 / 阈值调整建议
```

精简版统计只显示 3 个核心数字，详细 skip_reason 分布作为可展开二级视图。

---

## 9. 实施顺序（9 周路线）

> 即使"全部一起上"，工程内部仍有依赖关系。骨架先通、皮肉后填。

### Phase 1 — 骨架打通（week 1-2）
**目标：群消息能产生一条简陋但完整的群内回复。**

- Alembic 迁移：5 张新表 + 4 个字段
- `group_reply_pipeline.entrypoint` + listener 一行 hook
- `LeadDetector` 只跑 **Layer 1**（复用 keyword_monitor）
- `pending_replies` 状态机 + Celery beat scan
- `RiskController` 基础规则：账号日额 + 同线索 48h 去重 + cooldown
- `ReplyComposer` 不接案例库，纯 KB → 三段式 LLM 出草稿
- `Dispatcher` 时延发送
- 反幻觉沿用 shill_dispatcher 现成 filter
- **里程碑**：一条群消息走完整管线发出一句话回复

### Phase 2 — 三层过滤完整 + 素材（week 3-4）
- Layer 2 ICP embedding + portal ICP 编辑器
- Layer 3 LLM 评分（扩 `analyze_intent`）
- `case_studies` 表 + portal 录入 UI
- 案例库自动抽取脚本 + portal "扫描历史"按钮
- ReplyComposer 接入 case_studies，**数字一致性反幻觉上线**
- **里程碑**：回复质量从"能发"到"像销售"

### Phase 3 — 拟人化生命体（week 5-6）
- `account_personas` + portal 人设编辑器
- RiskController 升级：**观望窗口 + 真人接话检测**
- `persona_rewriter` 实装（方言/口头禅/标点拟人化）
- `chitchat_scheduler` + `chitchat_pool`
- portal 闲聊话题编辑
- **里程碑**：账号在群里有"生活感"，回复时机自然

### Phase 4 — 衔接销售（week 7-8）
- `ai_reply_service` 接入群→私聊上下文
- Inbox 新增"群内 AI 互动"视图
- 反幻觉失败 → 副驾驶 Inbox 落地
- portal 实时统计（精简版） + skip_reason 拦截率明细
- A/B 框架数据基础：`ab_experiments` 表 + 流量分组路由 + `experiment_tag` 字段全管线贯通
- **里程碑**：闭环可观察可调参

### Phase 5 — A/B 框架完整化（week 9）
- A/B 指标采集（reply_rate, private_conversion_rate, kick_rate, anti_hallucination_failure_rate）
- A/B 后台分析页（实验定义 / 流量分配 / 指标对比 / 统计显著性提示）
- 内部 A/B 操作手册
- **里程碑**：可启动第一个真实 A/B 实验

### Phase 6 — 灰度 + 调参（持续）
- 灰度 1-2 个客户跑 1 周
- 按 `skip_reason` 拦截率反推阈值调整
- 监控被踢号事件，回溯哪条规则没拦住
- 沉淀风控策略归纳到默认 persona 模板
- 真实 A/B 实验：默认阈值 vs 调整阈值

---

## 10. A/B 实验框架详细设计

### 10.1 实验定义

```sql
INSERT INTO ab_experiments (name, scope, scope_value, variants, status, primary_metric)
VALUES (
  'layer3_score_threshold_2026q3',
  'customer', 1,  -- 仅 customer #1
  '[{"tag":"v1","weight":0.5,"params":{"layer3_score":60}},
    {"tag":"v2","weight":0.5,"params":{"layer3_score":70}}]'::jsonb,
  'running',
  'private_conversion_rate'
);
```

### 10.2 流量分配（确定性哈希）

```python
def assign_variant(experiment, source_user_id):
    """同一 source_user_id 永远进同一变体，避免变体间污染"""
    h = hashlib.md5(f"{experiment.id}:{source_user_id}".encode()).hexdigest()
    bucket = int(h[:8], 16) / 0xffffffff  # 0..1
    cumulative = 0
    for v in experiment.variants:
        cumulative += v["weight"]
        if bucket < cumulative:
            return v
    return experiment.variants[-1]
```

### 10.3 参数注入

Pipeline 在 `LeadDetector.run()` 入口处查询适用实验：
- 客户级 → `WHERE scope='customer' AND scope_value=customer_id AND status='running'`
- monitor 级 → 同上 + scope='monitor'
- 全局 → scope='global'

按 source_user_id 分配 variant，把 variant.params 合并到当条 pending_reply 的阈值字典，并写入 `experiment_tag = f"{experiment.name}:{variant.tag}"`。

### 10.4 指标采集

每条 pending_reply 终止状态（sent / suggested / skipped_*）写 `experiment_tag`。后台分析页按 tag 聚合：

- `reply_rate` = sent / 触发总数
- `private_conversion_rate` = 后续 24h 内 source_user 私聊主号的比例
- `kick_rate` = 触发后 48h 内监听账号被踢出该群的比例
- `anti_hallucination_failure_rate` = suggested / (sent + suggested)

### 10.5 分析后台

Portal admin 视图（不暴露给客户）：
- 实验列表 / 编辑 / 启停
- 实验详情：每变体的 N / 各指标值 / 95% 置信区间 / Z-test 显著性提示
- 一键导出 CSV 给离线分析

---

## 11. 风险与不确定性

### 11.1 设计层面的不确定性

1. **真人接话检测的"信号灵敏度"**：单靠 `reply_to_message_id` 可能漏掉"不引用直接回复"的真人；关键词共现可能误报。需在 Phase 5 灰度阶段调权重。
2. **闲聊频率上调到 5-10/天/群是否过高**：超出默认 3 倍可能触发 TG 群限速。Phase 3 上线后第 1 周强监控。
3. **数字一致性反幻觉的提取规则**：复杂量级表达（"上周帮某客户成交 5 单总额 30 万"）可能误判为有 3 个数字（5、30、万），但 case 数据只有"30 万"。规则需迭代。
4. **ICP embedding 在小语料下的判别力**：客户填的 ICP 文本 200-500 字，向量化后区分度可能不够。备选：用 LLM 直接判断 ICP 匹配（更准但更贵），Phase 5 评估是否切换。

### 11.2 工程层面的风险

1. **Celery beat 扫描频率与 fire_at 精度**：当前设 30s 扫一次，意味着 fire_at 实际触发延迟 0-30s。如果观望窗口设 60s，相对误差可达 50%。Phase 1 后压缩到 10s 扫描频率，或换 Redis sorted set。
2. **同一账号被多个 customer 共用**：当前 account.customer_id 是唯一归属，但 Epic 5 之后实际可能有共享池场景。设计保守地按"一号一主"假设，共享池场景需要 future work。
3. **被踢号回溯困难**：账号被踢通常是 TG 平台滞后通知，难精确定位到具体哪条消息。Phase 5 需配套被踢号事件采集 + 时间窗口归因分析。

### 11.3 业务层面的风险

1. **群内三段式回复触发群主反感**：尤其是案例段提及竞品或大数字时。需在 portal 提供"案例审核开关"，让客户可指定哪些案例不允许在群内引用。
2. **多账号轮流回不同线索的"水军感"**：即使账号互避（同线索仅 1 账号回），多账号在群里都"正好懂某个业务"也可能露馅。Phase 3 的 persona 差异化 + 闲聊生活化必须真做到位。
3. **合规边界**：群内主动 AI 回复 + 拟真人设可能触及 TG ToS 和部分国家法规。建议在 portal 显著位置提示客户：「本功能需在合法合规的群内使用，禁止对实名社群、公益群使用」。

---

## 12. 成功标准

灰度 1 个月（Phase 5）后，下列指标达成视为成功：

| 指标 | 目标 |
|---|---|
| 群内回复被踢号率 | < 5% 周率 |
| 群内回复后 24h 内私聊转化率 | > 15% |
| 反幻觉失败率（suggested / sent+suggested） | < 8% |
| RiskController 跳过的"真人已接话"事件中，**实际**确有真人回复的精确率 | > 80% |
| 客户对 portal 配置 UI 的可用性反馈 | 5 个种子客户中 ≥ 4 个能独立完成首次配置 |

---

## 13. 关联记忆与文档

- [[project-core-direction]] —— 项目主线：群控 + AI 客服，AI 完成初谈后销售在 Inbox 接管
- [[ai-reply-pipeline-state]] —— AI 回复管线现状（截至 2026-05-17 盘点）
- [[project-kb-and-handoff-decisions]] —— pgvector + 副驾驶模式 + Inbox 接管路径
- [[project-epic5-state]] —— 主号 QR 登录 + 聊天历史 → KB（本设计的群→私聊衔接基础）
- [[project-epic4-kb-state]] —— 行业 KB 自动生成（本设计的 KB 检索基础）
- [[project-reranker-state]] —— BGE cross-encoder reranker（本设计的 KB top 3 重排序基础）
- [[project-ai-marketing-verification-2026-05-26]] —— 当前 Vertex/AI Studio 凭证状态，影响 LLM/embedding 调用
- [[project-capacity-plan]] —— 容量规划（本设计在该容量下应稳定运行）

