"""
AI Engine - 统一管理所有 AI 能力

提供以下核心功能：
1. 用户画像分析 - 评估目标用户价值
2. 群组分析 - 评估流量源价值
3. 内容生成 - 开场白、回复、剧本
4. 风险检测 - 账号风控预警
"""
import json
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from sqlmodel import Session, select

from app.services.llm import LLMService
from app.models.ai_persona import AIPersona

logger = logging.getLogger(__name__)


@dataclass
class UserAnalysis:
    """用户分析结果"""
    score: int  # 0-100
    tags: List[str]
    is_bot: bool
    is_advertiser: bool
    interest_keywords: List[str]
    summary: str


@dataclass  
class GroupAnalysis:
    """群组分析结果"""
    score: int
    topics: List[str]
    spam_ratio: float
    best_time: str
    recommendation: str


class AIEngine:
    """AI 引擎 - 统一管理所有 AI 能力"""
    
    # Prompt 模板
    PROMPTS = {
        "user_scoring": """分析以下 Telegram 用户信息，判断其作为营销目标的价值。

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
- 简介包含投资/交易/crypto相关词汇 = 加分
- 疑似机器人或广告号 = 0分
- 活跃度高、互动多 = 加分

只输出JSON，不要任何其他内容。""",

        "personalized_opener": """你是一个 {tone} 的 Telegram 用户，正在私聊一个陌生人。

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

只输出消息内容，不要任何解释。""",

        "smart_reply": """你正在进行一场 Telegram 私聊对话。

你的人设：
{persona_prompt}

对话历史：
{conversation}

请生成下一条回复，要求：
1. 保持人设一致
2. 自然推进对话
3. 适当引导到产品/服务
4. 控制在100字以内
5. 如果对方表现出兴趣，可以询问联系方式

知识库参考（如果有）：
{knowledge}

只输出回复内容，不要任何解释。""",

        "shill_script": """场景：一个加密货币讨论群，需要制造热烈氛围

角色设定：
{roles}

话题：{topic}

请生成一段 {duration} 分钟的群聊剧本，要求：
1. 对话自然，像真人聊天
2. 角色性格鲜明
3. 逐步引导话题到我们的产品
4. 包含适当的emoji和网络用语
5. 每条消息控制在100字以内
6. 消息之间有合理的时间间隔

输出 JSON 数组格式：
[
    {{"role": "角色名", "content": "消息内容", "delay_seconds": 30}},
    ...
]

只输出JSON，不要任何其他内容。""",

        "content_rewrite": """将以下消息改写成 {count} 个不同的变体版本，保持原意但避免重复。

原始消息：
{content}

要求：
1. 每个变体语义相同但表达不同
2. 调整词序、用词、标点
3. 可以增减emoji
4. 保持相似的长度

输出 JSON 数组格式：
["变体1", "变体2", ...]

只输出JSON，不要任何其他内容。""",

        "group_analysis": """分析以下 Telegram 群组的最近消息，评估其作为营销目标的价值。

群组名称: {group_name}
最近消息 (共{message_count}条):
{messages}

请分析并输出 JSON 格式：
{{
    "score": 0-100的整数,
    "topics": ["主要话题1", "话题2"],
    "spam_ratio": 0-1的小数(广告/垃圾消息占比),
    "activity_level": "high/medium/low",
    "best_time": "最佳发言时间段，如 20:00-22:00",
    "user_quality": "用户质量评估",
    "recommendation": "营销建议"
}}

评分标准：
- 活跃度高、真人多 = 高分
- 话题与我们目标相关 = 加分
- 垃圾消息多、机器人多 = 扣分
- 管理严格、容易被踢 = 扣分

只输出JSON，不要任何其他内容。"""
    }
    
    def __init__(self, session: Optional[Session] = None):
        self.session = session
        self._llm = None
    
    @property
    def llm(self):
        """Lazy load LLM service"""
        if self._llm is None:
            self._llm = LLMService(self.session)
        return self._llm
    
    async def analyze_user(
        self,
        username: str,
        bio: Optional[str] = None,
        messages: Optional[List[str]] = None
    ) -> UserAnalysis:
        """
        分析用户画像
        
        Args:
            username: 用户名
            bio: 用户简介
            messages: 最近发言列表
            
        Returns:
            UserAnalysis 对象
        """
        prompt = self.PROMPTS["user_scoring"].format(
            username=username or "未知",
            bio=bio or "无",
            messages="\n".join(messages[:10]) if messages else "无发言记录"
        )
        
        try:
            response = await self.llm.generate(prompt)
            data = json.loads(response)
            
            return UserAnalysis(
                score=min(100, max(0, int(data.get("score", 50)))),
                tags=data.get("tags", []),
                is_bot=data.get("is_bot", False),
                is_advertiser=data.get("is_advertiser", False),
                interest_keywords=data.get("interest_keywords", []),
                summary=data.get("summary", "")
            )
        except Exception as e:
            logger.error(f"User analysis failed: {e}")
            return UserAnalysis(
                score=50,
                tags=[],
                is_bot=False,
                is_advertiser=False,
                interest_keywords=[],
                summary="分析失败"
            )
    
    async def analyze_group(
        self,
        group_name: str,
        messages: List[str]
    ) -> GroupAnalysis:
        """
        分析群组价值
        
        Args:
            group_name: 群组名称
            messages: 最近消息列表
            
        Returns:
            GroupAnalysis 对象
        """
        prompt = self.PROMPTS["group_analysis"].format(
            group_name=group_name,
            message_count=len(messages),
            messages="\n".join(messages[:100])  # 最多100条
        )
        
        try:
            response = await self.llm.generate(prompt)
            data = json.loads(response)
            
            return GroupAnalysis(
                score=min(100, max(0, int(data.get("score", 50)))),
                topics=data.get("topics", []),
                spam_ratio=float(data.get("spam_ratio", 0.3)),
                best_time=data.get("best_time", "20:00-22:00"),
                recommendation=data.get("recommendation", "")
            )
        except Exception as e:
            logger.error(f"Group analysis failed: {e}")
            return GroupAnalysis(
                score=50,
                topics=[],
                spam_ratio=0.3,
                best_time="20:00-22:00",
                recommendation="分析失败"
            )
    
    async def generate_opener(
        self,
        user_summary: str,
        persona_id: Optional[int] = None,
        persona_prompt: Optional[str] = None,
        tone: str = "friendly"
    ) -> str:
        """
        生成定制化开场白
        
        Args:
            user_summary: 目标用户画像摘要
            persona_id: AI人设ID (可选)
            persona_prompt: 直接传入的人设提示词 (可选)
            tone: 语气风格
            
        Returns:
            开场白文本
        """
        # 获取人设
        if persona_id and self.session:
            persona = self.session.get(AIPersona, persona_id)
            if persona:
                persona_prompt = persona.system_prompt
                tone = persona.tone
        
        if not persona_prompt:
            persona_prompt = "你是一个友好的网友，喜欢交流加密货币话题。"
        
        prompt = self.PROMPTS["personalized_opener"].format(
            tone=tone,
            user_summary=user_summary,
            persona_prompt=persona_prompt
        )
        
        try:
            response = await self.llm.generate(prompt)
            return response.strip()
        except Exception as e:
            logger.error(f"Opener generation failed: {e}")
            return "你好！最近有在关注加密市场吗？"
    
    async def generate_reply(
        self,
        conversation: List[Dict[str, str]],
        persona_id: Optional[int] = None,
        persona_prompt: Optional[str] = None,
        knowledge: Optional[str] = None
    ) -> str:
        """
        生成智能回复
        
        Args:
            conversation: 对话历史 [{"role": "user/assistant", "content": "..."}]
            persona_id: AI人设ID
            persona_prompt: 人设提示词
            knowledge: 知识库内容 (RAG)
            
        Returns:
            回复文本
        """
        if persona_id and self.session:
            persona = self.session.get(AIPersona, persona_id)
            if persona:
                persona_prompt = persona.system_prompt
        
        if not persona_prompt:
            persona_prompt = "你是一个友好的网友。"
        
        # 格式化对话历史
        conv_text = ""
        for msg in conversation[-10:]:  # 最近10条
            role = "我" if msg["role"] == "assistant" else "对方"
            conv_text += f"{role}: {msg['content']}\n"
        
        prompt = self.PROMPTS["smart_reply"].format(
            persona_prompt=persona_prompt,
            conversation=conv_text,
            knowledge=knowledge or "无"
        )
        
        try:
            response = await self.llm.generate(prompt)
            return response.strip()
        except Exception as e:
            logger.error(f"Reply generation failed: {e}")
            return "好的，我了解了。"
    
    async def generate_script(
        self,
        topic: str,
        roles: List[Dict[str, str]],
        duration_minutes: int = 5
    ) -> List[Dict[str, Any]]:
        """
        生成炒群剧本
        
        Args:
            topic: 话题
            roles: 角色列表 [{"name": "角色名", "personality": "性格描述"}]
            duration_minutes: 剧本时长
            
        Returns:
            剧本消息列表
        """
        roles_text = "\n".join([
            f"- {r['name']}: {r.get('personality', '普通群友')}"
            for r in roles
        ])
        
        prompt = self.PROMPTS["shill_script"].format(
            roles=roles_text,
            topic=topic,
            duration=duration_minutes
        )
        
        try:
            response = await self.llm.generate(prompt)
            script = json.loads(response)
            return script
        except Exception as e:
            logger.error(f"Script generation failed: {e}")
            return []
    
    async def rewrite_content(
        self,
        content: str,
        count: int = 5
    ) -> List[str]:
        """
        生成内容变体（防指纹检测）
        
        Args:
            content: 原始内容
            count: 变体数量
            
        Returns:
            变体列表
        """
        prompt = self.PROMPTS["content_rewrite"].format(
            content=content,
            count=count
        )
        
        try:
            response = await self.llm.generate(prompt)
            variants = json.loads(response)
            return variants if isinstance(variants, list) else [content]
        except Exception as e:
            logger.error(f"Content rewrite failed: {e}")
            return [content]
    
    async def batch_score_users(
        self,
        users: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        批量评分用户
        
        Args:
            users: 用户列表 [{"username": "", "bio": "", "messages": []}]
            
        Returns:
            带评分的用户列表
        """
        results = []
        for user in users:
            try:
                analysis = await self.analyze_user(
                    username=user.get("username"),
                    bio=user.get("bio"),
                    messages=user.get("messages")
                )
                results.append({
                    **user,
                    "ai_score": analysis.score,
                    "ai_tags": analysis.tags,
                    "ai_summary": analysis.summary,
                    "is_bot": analysis.is_bot,
                    "is_advertiser": analysis.is_advertiser
                })
            except Exception as e:
                logger.error(f"Batch score failed for {user.get('username')}: {e}")
                results.append({**user, "ai_score": 50, "ai_tags": [], "ai_summary": "评分失败"})
        
        return results
    
    async def detect_risk(
        self,
        error_logs: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        分析风控风险，建议调整策略 (STRATEGIC_PLAN 5.1)
        
        Args:
            error_logs: 错误日志列表 [{"type": "", "message": "", "account_id": "", "timestamp": ""}]
            
        Returns:
            {
                "risk_level": "low/medium/high/critical",
                "issues": [...],
                "recommendations": [...],
                "suggested_actions": {...}
            }
        """
        if not error_logs:
            return {
                "risk_level": "low",
                "issues": [],
                "recommendations": [],
                "suggested_actions": {}
            }
        
        prompt = f"""分析以下 Telegram 操作错误日志，评估风控风险等级并给出建议。

错误日志 (最近{len(error_logs)}条):
{json.dumps(error_logs[:20], ensure_ascii=False, indent=2)}

请输出 JSON 格式：
{{
    "risk_level": "low/medium/high/critical",
    "issues": ["问题1描述", "问题2描述"],
    "recommendations": ["建议1", "建议2"],
    "suggested_actions": {{
        "pause_accounts": [账号ID列表],
        "reduce_frequency": true/false,
        "switch_proxies": true/false,
        "wait_hours": 数字
    }}
}}

风险等级判断标准：
- low: 偶发错误，正常波动
- medium: 某类错误频繁出现，需要关注
- high: 多个账号出现相同问题，可能被针对
- critical: 大规模封号或频繁FloodWait，立即暂停
"""
        
        try:
            response = await self.llm.chat(prompt)
            result = json.loads(response)
            return result
        except Exception as e:
            logger.error(f"Risk detection failed: {e}")
            # 基于规则的降级分析
            error_types = [log.get("type", "") for log in error_logs]
            flood_count = sum(1 for t in error_types if "flood" in t.lower())
            ban_count = sum(1 for t in error_types if "ban" in t.lower() or "deactivated" in t.lower())
            
            if ban_count >= 3:
                return {
                    "risk_level": "critical",
                    "issues": [f"检测到 {ban_count} 个封号相关错误"],
                    "recommendations": ["立即暂停所有操作", "检查代理质量", "降低发送频率"],
                    "suggested_actions": {"wait_hours": 24, "reduce_frequency": True}
                }
            elif flood_count >= 5:
                return {
                    "risk_level": "high",
                    "issues": [f"检测到 {flood_count} 个 FloodWait 错误"],
                    "recommendations": ["增加消息间隔", "分散账号使用"],
                    "suggested_actions": {"wait_hours": 6, "reduce_frequency": True}
                }
            else:
                return {
                    "risk_level": "medium",
                    "issues": ["存在一些操作错误"],
                    "recommendations": ["持续监控"],
                    "suggested_actions": {}
                }


# 工厂函数 - 用于创建带session的实例
def get_ai_engine(session: Session) -> AIEngine:
    return AIEngine(session)
