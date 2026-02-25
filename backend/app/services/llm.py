import openai
from typing import Optional, List, Dict
import logging
import json
from app.models.system_config import SystemConfig
from app.models.ai_config import AIConfig
from sqlmodel import Session, select

logger = logging.getLogger(__name__)

# Try to import Google GenAI SDK (new version)
try:
    from google import genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("google-genai not installed, Gemini support disabled")

# 各提供商的默认 Base URL
DEFAULT_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "moonshot": "https://api.moonshot.cn/v1",
    "zhipu": "https://open.bigmodel.cn/api/paas/v4",
    "doubao": "https://ark.cn-beijing.volces.com/api/v3",
    "openrouter": "https://openrouter.ai/api/v1",
}


class LLMService:
    def __init__(self, db_session: Session, config_id: int = None):
        """
        初始化 LLM 服务
        
        Args:
            db_session: 数据库会话
            config_id: 指定的 AI 配置 ID。如果不传，则使用默认配置或旧的 SystemConfig
        """
        self.session = db_session
        self.config_id = config_id
        self.client = None
        self.gemini_client = None
        
        # 尝试从 AIConfig 表加载配置
        config = self._load_ai_config(config_id)
        
        if config:
            # 使用 AIConfig 配置
            self.api_key = config.api_key
            self.provider = config.provider
            self.model = config.model
            self.base_url = config.base_url or DEFAULT_BASE_URLS.get(config.provider, "")
            self.config_name = config.name
        else:
            # 回退到旧的 SystemConfig 配置（兼容性）
            self.api_key = self._get_system_config("llm_api_key")
            self.provider = self._get_system_config("llm_provider") or "openai"
            self.model = self._get_system_config("llm_model") or "gpt-3.5-turbo"
            configured_base_url = self._get_system_config("llm_base_url")
            self.base_url = configured_base_url or DEFAULT_BASE_URLS.get(self.provider, "https://api.openai.com/v1")
            self.config_name = "Legacy Config"
        
        # 初始化客户端
        if self.api_key:
            if self.provider == "gemini" and GEMINI_AVAILABLE:
                self._init_gemini()
            else:
                # 所有其他提供商都使用 OpenAI 兼容的 API
                self._init_openai()

    def _load_ai_config(self, config_id: int = None) -> Optional[AIConfig]:
        """
        加载 AI 配置
        
        Args:
            config_id: 指定的配置 ID。如果为 None，则加载默认配置
        
        Returns:
            AIConfig 对象或 None
        """
        try:
            if config_id:
                # 加载指定配置
                config = self.session.get(AIConfig, config_id)
                if config and config.is_active:
                    return config
            else:
                # 加载默认配置
                config = self.session.exec(
                    select(AIConfig)
                    .where(AIConfig.is_default == True)
                    .where(AIConfig.is_active == True)
                ).first()
                if config:
                    return config
        except Exception as e:
            # 表可能不存在（首次运行）
            logger.debug(f"Failed to load AIConfig: {e}")
        
        return None

    def _get_system_config(self, key: str) -> Optional[str]:
        """从旧的 SystemConfig 表获取配置（兼容性）"""
        try:
            config = self.session.exec(select(SystemConfig).where(SystemConfig.key == key)).first()
            return config.value if config else None
        except Exception:
            return None

    def _init_openai(self):
        """Initialize OpenAI-compatible client for various providers"""
        # OpenRouter 需要额外的请求头
        default_headers = {}
        if self.provider == "openrouter":
            default_headers = {
                "HTTP-Referer": "https://tgsc.local",
                "X-Title": "TGSC Marketing System"
            }
        
        self.client = openai.OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            default_headers=default_headers if default_headers else None
        )
        logger.info(f"OpenAI-compatible client initialized for {self.provider} with model: {self.model}")

    def _init_gemini(self):
        """Initialize Google Gemini client using new google-genai SDK"""
        # Default to gemini-2.5-flash if not specified or using old model name
        model_name = self.model
        if not model_name or model_name.startswith("gpt"):
            model_name = "gemini-2.5-flash"
        self.model = model_name
        
        # Create client with API key
        self.gemini_client = genai.Client(api_key=self.api_key)
        logger.info(f"Gemini client initialized with model: {model_name}")

    def is_configured(self) -> bool:
        if self.provider == "gemini":
            return bool(self.gemini_client)
        return bool(self.client)

    async def test_connection(self) -> bool:
        if self.provider == "gemini" and self.gemini_client:
            return await self._test_gemini_connection()
        elif self.client:
            return await self._test_openai_connection()
        return False

    async def _test_openai_connection(self) -> bool:
        try:
            self.client.models.list()
            return True
        except Exception as e:
            logger.error(f"OpenAI connection test failed: {e}")
            return False

    async def _test_gemini_connection(self) -> bool:
        try:
            # Simple test generation using new SDK
            response = self.gemini_client.models.generate_content(
                model=self.model,
                contents="Hello, respond with 'OK' only."
            )
            return response.text is not None
        except Exception as e:
            logger.error(f"Gemini connection test failed: {e}")
            return False

    async def get_response(
        self, 
        prompt: str, 
        system_prompt: str = "You are a helpful assistant.",
        history: List[Dict[str, str]] = None
    ) -> Optional[str]:
        if self.provider == "gemini" and self.gemini_client:
            return await self._get_gemini_response(prompt, system_prompt, history)
        elif self.client:
            return await self._get_openai_response(prompt, system_prompt, history)
        else:
            logger.warning("LLM client not configured")
            return None

    async def _get_openai_response(
        self,
        prompt: str,
        system_prompt: str,
        history: List[Dict[str, str]] = None
    ) -> Optional[str]:
        messages = [{"role": "system", "content": system_prompt}]
        
        if history:
            messages.extend(history)
            
        messages.append({"role": "user", "content": prompt})

        try:
            chat_completion = self.client.chat.completions.create(
                messages=messages,
                model=self.model,
                temperature=0.7,
            )
            return chat_completion.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI generation failed: {e}")
            return None

    async def _get_gemini_response(
        self,
        prompt: str,
        system_prompt: str,
        history: List[Dict[str, str]] = None
    ) -> Optional[str]:
        try:
            # Build contents list for Gemini
            contents = []
            
            # Add history if provided
            if history:
                for msg in history:
                    role = "user" if msg["role"] == "user" else "model"
                    contents.append({
                        "role": role,
                        "parts": [{"text": msg["content"]}]
                    })
            
            # Combine system prompt with user prompt
            # (Gemini uses system_instruction for system prompts in config)
            full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
            contents.append({
                "role": "user",
                "parts": [{"text": full_prompt}]
            })
            
            # Generate response using new SDK
            response = self.gemini_client.models.generate_content(
                model=self.model,
                contents=contents
            )
            return response.text
        except Exception as e:
            logger.error(f"Gemini generation failed: {e}")
            return None

    async def analyze_intent(self, message: str, history: List[Dict[str, str]] = None) -> Dict:
        """
        Analyze the intent of a user message.
        Returns a dict with: intent (str), confidence (float), tags (List[str]), reply_suggestion (str)
        """
        if not self.is_configured():
            return {"intent": "unknown", "confidence": 0.0, "tags": [], "summary": "LLM not configured"}

        system_prompt = """
        You are an expert sales assistant analyzing customer messages on Telegram.
        Your goal is to classify the INTENT of the message and extract key TAGS.
        
        Possible Intents:
        - inquiry: Asking about product, price, features (High Value)
        - purchase: Explicitly wants to buy (Very High Value)
        - support: Asking for help, complaining (Medium Value)
        - chat: Casual conversation, greeting (Low Value)
        - spam: Ads, links, irrelevant content (Ignore)
        
        Output Format: JSON only.
        {
            "intent": "inquiry", 
            "confidence": 0.9, 
            "tags": ["price", "shipping"], 
            "summary": "User asking for price",
            "is_high_value": true
        }
        """
        
        user_prompt = f"Analyze this message: '{message}'"
        
        # Consider history for context
        if history:
            # Take last 3 messages for context
            context_msgs = history[-3:]
            context_str = "\n".join([f"{m['role']}: {m['content']}" for m in context_msgs])
            user_prompt = f"Context:\n{context_str}\n\nAnalyze this message: '{message}'"

        try:
            response = await self.get_response(user_prompt, system_prompt)
            if not response:
                return {"intent": "unknown", "confidence": 0.0, "tags": []}
                
            # Parse JSON
            try:
                # Cleanup potential markdown code blocks
                cleaned = response.replace("```json", "").replace("```", "").strip()
                result = json.loads(cleaned)
                return result
            except json.JSONDecodeError:
                logger.error(f"Failed to parse intent JSON: {response}")
                return {"intent": "unknown", "confidence": 0.0, "tags": []}
                
        except Exception as e:
            logger.error(f"Intent analysis failed: {e}")
            return {"intent": "unknown", "confidence": 0.0, "tags": []}
