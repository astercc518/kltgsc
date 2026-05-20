# TG群控系统 - 三维矩阵 + AI赋能 战略升级方案

> **核心理念**：账号是子弹，功能是武器，一切为了"打下金币"

---

## 一、战略框架概述

### 1.1 三维矩阵模型

| 维度 | 定位 | 核心问题 |
|------|------|----------|
| **账号 (Account)** | 弹药管理 | 我用谁去打？ |
| **业务 (Campaign)** | 战役管理 | 我要做什么？ |
| **群组 (Target)** | 猎场管理 | 我去哪里打？ |

### 1.2 AI 赋能层

| AI 能力 | 应用场景 |
|---------|----------|
| 智能分析 | 用户画像、群组价值评估 |
| 内容生成 | 话术变体、定制开场白、剧本对话 |
| 自动决策 | 风控感知、发送时机优化 |
| 智能对话 | RAG知识库驱动的销售机器人 |

---

## 二、数据库设计

### 2.1 账号维度扩展

```sql
-- 修改 account 表，增加战略分组字段
ALTER TABLE account ADD COLUMN IF NOT EXISTS 
    combat_role VARCHAR(20) DEFAULT 'cannon';  -- cannon/scout/actor/sniper

ALTER TABLE account ADD COLUMN IF NOT EXISTS 
    health_score INTEGER DEFAULT 100;  -- 0-100 健康分

ALTER TABLE account ADD COLUMN IF NOT EXISTS 
    daily_action_count INTEGER DEFAULT 0;  -- 今日操作次数

ALTER TABLE account ADD COLUMN IF NOT EXISTS 
    last_error_type VARCHAR(50);  -- 最后错误类型

CREATE INDEX IF NOT EXISTS idx_account_combat_role ON account(combat_role);
CREATE INDEX IF NOT EXISTS idx_account_health_score ON account(health_score);
```

### 2.2 业务/战役表 (新增)

```sql
CREATE TABLE IF NOT EXISTS campaign (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,           -- 战役名称
    description TEXT,                      -- 描述
    status VARCHAR(20) DEFAULT 'active',   -- active/paused/completed
    
    -- 资源配置
    allowed_roles TEXT DEFAULT 'cannon,scout',  -- 允许使用的账号角色
    daily_budget INTEGER DEFAULT 1000,     -- 每日消息上限
    daily_account_limit INTEGER DEFAULT 100, -- 每日账号消耗上限
    
    -- AI 配置
    ai_persona_id INTEGER,                 -- 关联的AI人设
    ai_knowledge_base_id INTEGER,          -- 关联的知识库
    
    -- 统计
    total_messages_sent INTEGER DEFAULT 0,
    total_replies_received INTEGER DEFAULT 0,
    total_conversions INTEGER DEFAULT 0,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_campaign_status ON campaign(status);
```

### 2.3 流量源/猎场表 (新增)

```sql
CREATE TABLE IF NOT EXISTS source_group (
    id SERIAL PRIMARY KEY,
    link VARCHAR(255) NOT NULL,            -- 群链接
    name VARCHAR(100),                     -- 群名称
    
    -- 分类
    type VARCHAR(20) DEFAULT 'traffic',    -- competitor/industry/traffic
    risk_level VARCHAR(10) DEFAULT 'low',  -- low/medium/high (防守等级)
    
    -- 状态
    status VARCHAR(20) DEFAULT 'active',   -- active/exhausted/banned/honeypot
    member_count INTEGER DEFAULT 0,        -- 群成员数
    
    -- 采集统计
    last_scraped_at TIMESTAMP,
    total_scraped INTEGER DEFAULT 0,
    high_value_count INTEGER DEFAULT 0,    -- 高价值用户数
    
    -- AI 评估
    ai_score INTEGER,                      -- AI评分 0-100
    ai_analysis TEXT,                      -- AI分析结果JSON
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_source_group_type ON source_group(type);
CREATE INDEX IF NOT EXISTS idx_source_group_status ON source_group(status);
```

### 2.4 营销群/私塘表 (新增)

```sql
CREATE TABLE IF NOT EXISTS funnel_group (
    id SERIAL PRIMARY KEY,
    link VARCHAR(255) NOT NULL,
    name VARCHAR(100),
    
    -- 分类
    type VARCHAR(20) DEFAULT 'nurture',    -- filter/nurture/vip
    campaign_id INTEGER REFERENCES campaign(id),
    
    -- 配置
    welcome_message TEXT,                  -- 入群欢迎语
    auto_kick_ads BOOLEAN DEFAULT true,    -- 自动踢广告
    
    -- 统计
    member_count INTEGER DEFAULT 0,
    today_joined INTEGER DEFAULT 0,
    today_left INTEGER DEFAULT 0,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 2.5 AI 人设表 (新增)

```sql
CREATE TABLE IF NOT EXISTS ai_persona (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,            -- 人设名称
    description TEXT,
    
    -- 人设配置
    system_prompt TEXT NOT NULL,           -- 系统提示词
    tone VARCHAR(50) DEFAULT 'friendly',   -- 语气: friendly/professional/casual
    language VARCHAR(20) DEFAULT 'zh',     -- 语言
    
    -- 约束
    forbidden_topics TEXT,                 -- 禁止话题 JSON数组
    required_keywords TEXT,                -- 必须包含的关键词
    
    -- 统计
    usage_count INTEGER DEFAULT 0,
    avg_reply_rate DECIMAL(5,2),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 预设人设
INSERT INTO ai_persona (name, system_prompt, tone) VALUES 
('金牌销售', '你是一个专业的加密货币投资顾问，热情友好，善于倾听客户需求，引导客户了解我们的产品优势。不要直接推销，先建立信任。', 'friendly'),
('技术分析师', '你是一个资深的技术分析师，说话专业但不晦涩，善于用数据说话，偶尔分享盈利截图增加可信度。', 'professional'),
('热心群友', '你是群里的活跃用户，经常分享自己的投资心得，语气轻松随意，会用emoji和网络用语。', 'casual');
```

### 2.6 AI 知识库表 (新增)

```sql
CREATE TABLE IF NOT EXISTS ai_knowledge_base (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    
    -- 内容
    content TEXT NOT NULL,                 -- 知识内容(Markdown)
    
    -- 配置
    auto_update BOOLEAN DEFAULT false,     -- 是否自动更新
    source_url VARCHAR(255),               -- 来源URL
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 关联表：知识库 <-> 战役
CREATE TABLE IF NOT EXISTS campaign_knowledge_link (
    campaign_id INTEGER REFERENCES campaign(id),
    knowledge_base_id INTEGER REFERENCES ai_knowledge_base(id),
    PRIMARY KEY (campaign_id, knowledge_base_id)
);
```

### 2.7 用户画像扩展

```sql
-- 扩展 targetuser 表
ALTER TABLE targetuser ADD COLUMN IF NOT EXISTS 
    ai_score INTEGER;  -- AI评分 0-100

ALTER TABLE targetuser ADD COLUMN IF NOT EXISTS 
    ai_tags TEXT;  -- AI生成的标签 JSON数组

ALTER TABLE targetuser ADD COLUMN IF NOT EXISTS 
    ai_summary TEXT;  -- AI生成的用户摘要

ALTER TABLE targetuser ADD COLUMN IF NOT EXISTS 
    source_group_id INTEGER;  -- 来源群组ID

ALTER TABLE targetuser ADD COLUMN IF NOT EXISTS 
    funnel_stage VARCHAR(20) DEFAULT 'raw';  -- raw/qualified/contacted/replied/converted

CREATE INDEX IF NOT EXISTS idx_targetuser_ai_score ON targetuser(ai_score);
CREATE INDEX IF NOT EXISTS idx_targetuser_funnel_stage ON targetuser(funnel_stage);
```

---

## 三、账号分组策略

### 3.1 四大战斗角色

| 角色 | 代号 | 定位 | 允许操作 | 风控等级 |
|------|------|------|----------|----------|
| **炮灰** | `cannon` | 廉价弹药，用完即弃 | 群发、拉人、炸群 | 无限制 |
| **侦察** | `scout` | 情报收集，低调潜伏 | 采集、监控、检测 | 只读操作 |
| **演员** | `actor` | 信任铺垫，气氛制造 | 炒群、剧本对话 | 中度限制 |
| **狙击** | `sniper` | 精准打击，成交转化 | 私聊高意向客户 | 严格限制 |

### 3.2 生命周期与流转

```
[新账号入库]
     ↓
[Cannon 炮灰组] ──存活7天──→ [Scout 侦察组]
     │                              │
     │                        养号30天
     ↓                              ↓
  [封号回收]               [Actor 演员组]
                                    │
                              权重极高
                                    ↓
                           [Sniper 狙击组]
                                    │
                              降权/异常
                                    ↓
                         [降级回 Cannon 榨干]
```

### 3.3 角色配置参数

```python
COMBAT_ROLE_CONFIG = {
    "cannon": {
        "display_name": "炮灰组",
        "daily_message_limit": 100,      # 每日发送上限
        "min_delay_seconds": 30,         # 最小间隔
        "max_delay_seconds": 60,
        "rest_after_sends": 0,           # 不休息
        "allowed_actions": ["mass_dm", "invite", "spam"],
        "risk_tolerance": "high",        # 高风险容忍
        "auto_retire_on_ban": True,      # 封号后自动退役
    },
    "scout": {
        "display_name": "侦察组", 
        "daily_message_limit": 0,        # 禁止发消息
        "allowed_actions": ["scrape", "monitor", "join_group"],
        "risk_tolerance": "low",
        "stealth_mode": True,            # 隐身模式
    },
    "actor": {
        "display_name": "演员组",
        "daily_message_limit": 50,
        "min_delay_seconds": 120,
        "max_delay_seconds": 300,
        "rest_after_sends": 10,
        "rest_duration_min": 600,        # 休息10分钟
        "allowed_actions": ["shill", "script_chat"],
        "require_script": True,          # 必须使用剧本
    },
    "sniper": {
        "display_name": "狙击组",
        "daily_message_limit": 20,       # 严格限制
        "min_delay_seconds": 300,        # 5分钟间隔
        "max_delay_seconds": 600,
        "rest_after_sends": 3,           # 每3条休息
        "rest_duration_min": 1800,       # 休息30分钟
        "allowed_actions": ["precision_dm"],
        "require_high_value_target": True,  # 只打高分用户
        "require_residential_proxy": True,  # 必须用住宅IP
    }
}
```

---

## 四、群组分层策略

### 4.1 三层漏斗模型

```
┌─────────────────────────────────────────────────┐
│                   猎场层 (公海)                  │
│  ┌─────────┐  ┌─────────┐  ┌─────────────────┐  │
│  │ 竞品群  │  │ 行业群  │  │    泛流量群     │  │
│  │ (精准)  │  │ (潜力)  │  │    (海量)       │  │
│  └────┬────┘  └────┬────┘  └───────┬─────────┘  │
└───────┼────────────┼───────────────┼────────────┘
        │            │               │
        ▼            ▼               ▼
┌─────────────────────────────────────────────────┐
│                  中转层 (洗炼厂)                 │
│  ┌─────────────────────────────────────────┐    │
│  │              AI 用户评分                 │    │
│  │         高分 → 精准池 → Sniper          │    │
│  │         中分 → 养鱼群 → Actor           │    │
│  │         低分 → 丢弃                     │    │
│  └─────────────────────────────────────────┘    │
└─────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────┐
│                  变现层 (金库)                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
│  │ 养鱼群   │  │ VIP群    │  │   私聊成交   │   │
│  │ (培育)   │  │ (付费)   │  │   (转化)     │   │
│  └──────────┘  └──────────┘  └──────────────┘   │
└─────────────────────────────────────────────────┘
```

### 4.2 群组类型配置

```python
SOURCE_GROUP_CONFIG = {
    "competitor": {
        "display_name": "竞品群",
        "priority": 1,                   # 最高优先级
        "scrape_frequency": "daily",     # 每日采集
        "intercept_new_members": True,   # 截流新成员
        "ai_analyze": True,              # AI分析群聊
    },
    "industry": {
        "display_name": "行业群",
        "priority": 2,
        "scrape_frequency": "weekly",
        "keyword_monitor": True,         # 关键词监控
        "soft_marketing": True,          # 软广策略
    },
    "traffic": {
        "display_name": "泛流量群",
        "priority": 3,
        "scrape_frequency": "monthly",
        "bulk_invite": True,             # 批量拉人
        "use_cannon_only": True,         # 只用炮灰
    }
}

FUNNEL_GROUP_CONFIG = {
    "filter": {
        "display_name": "过滤群",
        "purpose": "验证真人",
        "auto_captcha": True,
        "auto_kick_bots": True,
    },
    "nurture": {
        "display_name": "养鱼群",
        "purpose": "培育信任",
        "enable_shill_script": True,     # 启用炒群剧本
        "actor_ratio": 0.3,              # 30%是演员
    },
    "vip": {
        "display_name": "VIP群",
        "purpose": "付费服务",
        "entry_fee": True,               # 需要付费进入
        "human_only": True,              # 只允许人工操作
    }
}
```

---

## 五、AI 赋能模块

### 5.1 AI 服务架构

```python
# app/services/ai_engine.py

class AIEngine:
    """AI 引擎 - 统一管理所有 AI 能力"""
    
    async def analyze_user(self, user_profile: dict) -> dict:
        """
        分析用户画像
        输入: {username, bio, recent_messages}
        输出: {score: 0-100, tags: [], summary: ""}
        """
        pass
    
    async def analyze_group(self, group_messages: list) -> dict:
        """
        分析群组价值
        输入: 最近1000条消息
        输出: {score, topics, spam_ratio, best_time, recommendation}
        """
        pass
    
    async def generate_opener(self, target_user: dict, persona_id: int) -> str:
        """
        生成定制化开场白
        根据目标用户画像 + AI人设 生成
        """
        pass
    
    async def generate_reply(self, 
                            conversation: list, 
                            persona_id: int,
                            knowledge_base_id: int = None) -> str:
        """
        生成智能回复
        支持 RAG 知识库检索
        """
        pass
    
    async def generate_script(self, 
                             topic: str, 
                             roles: list,
                             duration_minutes: int = 5) -> list:
        """
        生成炒群剧本
        """
        pass
    
    async def rewrite_content(self, content: str, variations: int = 5) -> list:
        """
        生成内容变体（防指纹检测）
        """
        pass
    
    async def detect_risk(self, error_logs: list) -> dict:
        """
        分析风控风险，建议调整策略
        """
        pass
```

### 5.2 AI Prompt 模板

```python
AI_PROMPTS = {
    "user_scoring": """
分析以下 Telegram 用户信息，判断其作为营销目标的价值。

用户信息：
- 用户名: {username}
- 简介: {bio}
- 最近发言: {messages}

请输出 JSON 格式：
{{
    "score": 0-100的整数,
    "tags": ["标签1", "标签2"],
    "is_bot": true/false,
    "is_advertiser": true/false,
    "interest_keywords": ["关键词"],
    "summary": "一句话总结该用户"
}}

评分标准：
- 有头像+有简介+近期活跃 = 高分
- 简介包含投资/交易相关词汇 = 加分
- 疑似机器人或广告号 = 0分
""",
    
    "personalized_opener": """
你是一个 {persona_tone} 的 Telegram 用户，正在私聊一个陌生人。

目标用户画像：
{user_summary}

你的人设：
{persona_prompt}

请生成一条自然的开场白，要求：
1. 不要直接推销
2. 找到共同话题切入
3. 引发对方回复的兴趣
4. 控制在50字以内
5. 可以适当使用emoji

只输出消息内容，不要任何解释。
""",

    "shill_script": """
场景：一个加密货币讨论群，需要制造热烈氛围

角色：
{roles}

话题：{topic}

请生成一段 {duration} 分钟的群聊剧本，要求：
1. 对话自然，像真人聊天
2. 角色性格鲜明
3. 逐步引导话题到我们的产品
4. 包含适当的emoji和网络用语
5. 每条消息控制在100字以内

输出 JSON 数组格式：
[
    {{"role": "角色名", "content": "消息内容", "delay_seconds": 30}},
    ...
]
"""
}
```

### 5.3 AI 工作流

```
┌──────────────────────────────────────────────────────────────┐
│                        采集阶段                               │
│  Scout采集用户 → AI评分筛选 → 高分入精准池 / 低分丢弃        │
└──────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│                        触达阶段                               │
│  取高分用户 → AI生成定制开场白 → Sniper发送 → 等待回复       │
└──────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│                        转化阶段                               │
│  用户回复 → AI+RAG生成回复 → 多轮对话 → 引导注册/付款        │
└──────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│                        复盘阶段                               │
│  统计转化率 → AI分析失败原因 → 优化话术/调整策略             │
└──────────────────────────────────────────────────────────────┘
```

---

## 六、核心业务流程

### 6.1 流程一：竞品截流

```yaml
名称: 竞品截流战术
目标: 实时截取竞品群新加入的用户

步骤:
  1. 部署侦察:
     - 分配 Scout 账号进入竞品群
     - 开启"新成员监控"功能
     
  2. 实时捕获:
     - 检测到新成员加入事件
     - 立即获取用户信息 (username, bio)
     
  3. AI 评估:
     - 调用 AI 分析用户价值
     - 分数 >= 70 进入"热门线索池"
     
  4. 即时触达:
     - Sniper 账号在 5 分钟内发起私聊
     - AI 生成基于用户画像的定制开场白
     
  5. 智能跟进:
     - 用户回复后，AI 接管对话
     - 多轮引导至注册/付款

触发条件: 实时 (Event-Driven)
使用账号: Scout (监控) + Sniper (触达)
```

### 6.2 流程二：批量洗群

```yaml
名称: 批量洗群漏斗
目标: 将公域流量转化为私域流量

步骤:
  1. 采集数据:
     - Scout 从多个 Source Group 采集成员
     - 每群采集 500-1000 人
     
  2. AI 清洗:
     - 批量调用 AI 评分
     - 过滤机器人、广告号、死粉
     - 按分数分层: A(>=80) / B(50-79) / C(<50)
     
  3. 分层触达:
     - A层: Sniper 精准私聊
     - B层: Cannon 批量拉入养鱼群
     - C层: 丢弃
     
  4. 养鱼培育:
     - Actor 在养鱼群执行炒群剧本
     - 制造热度，建立信任
     
  5. 收割转化:
     - 活跃用户被 Sniper 私聊成交
     - 或主动联系群主 (Sniper)

执行周期: 每周一次大采集
使用账号: Scout + Cannon + Actor + Sniper 全链路
```

### 6.3 流程三：炒群造势

```yaml
名称: AI 驱动的炒群剧本
目标: 在营销群中制造热烈氛围

步骤:
  1. 剧本生成:
     - 输入: 今日话题 (如: BTC突破10万)
     - AI 生成 30 分钟的多角色对话剧本
     
  2. 角色分配:
     - 从 Actor 组选取 5-10 个账号
     - 分配角色: 小白、老手、分析师、获利者
     
  3. 自动执行:
     - 按剧本时间轴自动发送消息
     - 穿插真实用户的消息 (动态适应)
     
  4. 效果监控:
     - 统计真实用户发言数
     - 统计私聊咨询数

执行频率: 每日 2-3 轮高峰期
```

---

## 七、系统模块规划

### 7.1 后端 API 结构

```
/api/v1/
├── accounts/
│   ├── GET    /                    # 账号列表 (支持 role 筛选)
│   ├── GET    /{id}/stats          # 账号战斗统计
│   ├── POST   /{id}/promote        # 晋升角色
│   ├── POST   /{id}/demote         # 降级角色
│   └── POST   /batch-assign-role   # 批量分配角色
│
├── campaigns/
│   ├── GET    /                    # 战役列表
│   ├── POST   /                    # 创建战役
│   ├── GET    /{id}/dashboard      # 战役数据大屏
│   ├── POST   /{id}/launch-task    # 在战役下创建任务
│   └── GET    /{id}/tasks          # 战役下的所有任务
│
├── source-groups/
│   ├── GET    /                    # 猎场列表
│   ├── POST   /                    # 添加猎场
│   ├── POST   /{id}/analyze        # AI 分析群组
│   ├── POST   /{id}/scrape         # 执行采集
│   └── GET    /{id}/users          # 该群采集的用户
│
├── funnel-groups/
│   ├── GET    /                    # 营销群列表
│   ├── POST   /                    # 创建营销群
│   └── GET    /{id}/stats          # 群统计
│
├── ai/
│   ├── POST   /analyze-user        # AI 分析用户
│   ├── POST   /analyze-group       # AI 分析群组
│   ├── POST   /generate-opener     # 生成开场白
│   ├── POST   /generate-reply      # 生成回复
│   ├── POST   /generate-script     # 生成剧本
│   └── POST   /rewrite             # 内容改写
│
├── personas/
│   ├── GET    /                    # AI 人设列表
│   ├── POST   /                    # 创建人设
│   └── PUT    /{id}                # 修改人设
│
└── knowledge-bases/
    ├── GET    /                    # 知识库列表
    ├── POST   /                    # 创建知识库
    └── PUT    /{id}                # 更新知识库
```

### 7.2 前端页面规划

```
├── 资源中心 (Resources)
│   ├── 账号管理 (Accounts)
│   │   ├── 账号列表 (按角色分Tab: 炮灰/侦察/演员/狙击)
│   │   ├── 角色分配 (批量调整)
│   │   └── 健康监控 (封号率、存活率)
│   │
│   └── 流量源管理 (Source Groups)
│       ├── 猎场列表 (竞品/行业/泛流量)
│       ├── 添加群组 (批量导入链接)
│       └── AI 分析报告
│
├── 作战中心 (Operations)
│   ├── 战役管理 (Campaigns)
│   │   ├── 战役列表
│   │   ├── 创建战役 (配置目标、预算、AI人设)
│   │   └── 数据大屏 (ROI、转化漏斗)
│   │
│   ├── 任务调度 (Tasks)
│   │   ├── 采集任务
│   │   ├── 群发任务
│   │   ├── 拉人任务
│   │   └── 炒群任务
│   │
│   └── 营销群管理 (Funnel Groups)
│       ├── 群列表
│       └── 炒群剧本配置
│
├── AI 中心 (AI Hub)
│   ├── 人设管理 (Personas)
│   ├── 知识库 (Knowledge Bases)
│   ├── 话术库 (生成的开场白/回复模板)
│   └── 剧本库 (生成的炒群剧本)
│
└── 数据中心 (Analytics)
    ├── 总览仪表盘
    ├── 账号消耗报表
    ├── 转化漏斗分析
    └── AI 效果分析
```

---

## 八、实施路线图

### Phase 1: 基础设施 (1-2周)
- [ ] 数据库表结构变更
- [ ] 账号角色字段 + 筛选功能
- [ ] Campaign 基础 CRUD
- [ ] SourceGroup 基础 CRUD

### Phase 2: 账号分层 (1周)
- [ ] 角色配置参数系统
- [ ] 账号晋升/降级逻辑
- [ ] 任务创建时的角色限制

### Phase 3: 群组管理 (1周)
- [ ] 猎场管理页面
- [ ] 营销群管理页面
- [ ] 采集关联群组来源

### Phase 4: AI 集成 (2周)
- [ ] AI Engine 服务
- [ ] 用户画像评分
- [ ] 智能开场白生成
- [ ] 炒群剧本生成

### Phase 5: 高级功能 (2周)
- [ ] 战役数据大屏
- [ ] RAG 知识库对话
- [ ] 竞品群实时截流
- [ ] 自动化工作流

---

## 九、关键指标 (KPIs)

| 指标 | 说明 | 目标 |
|------|------|------|
| **账号存活率** | 账号7日存活比例 | > 60% |
| **采集有效率** | AI评分>=70的用户占比 | > 30% |
| **触达回复率** | 私聊后获得回复的比例 | > 15% |
| **转化率** | 从回复到付款的比例 | > 5% |
| **单号产出** | 每个账号带来的成交金额 | 覆盖成本的3倍 |

---

*文档版本: v1.0*
*更新时间: 2026-01-22*
