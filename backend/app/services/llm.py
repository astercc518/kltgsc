import openai
from typing import Optional, List, Dict
import logging
import json
from app.models.system_config import SystemConfig
from sqlmodel import Session, select

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self, db_session: Session):
        self.session = db_session
        self.api_key = self._get_config("llm_api_key")
        self.base_url = self._get_config("llm_base_url") or "https://api.openai.com/v1"
        self.model = self._get_config("llm_model") or "gpt-3.5-turbo"
        
        self.client = None
        if self.api_key:
            self.client = openai.OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )

    def _get_config(self, key: str) -> Optional[str]:
        config = self.session.exec(select(SystemConfig).where(SystemConfig.key == key)).first()
        return config.value if config else None

    def is_configured(self) -> bool:
        return bool(self.client)

    async def test_connection(self) -> bool:
        if not self.client:
            return False
        try:
            self.client.models.list()
            return True
        except Exception as e:
            logger.error(f"LLM connection test failed: {e}")
            return False

    async def get_response(
        self, 
        prompt: str, 
        system_prompt: str = "You are a helpful assistant.",
        history: List[Dict[str, str]] = None
    ) -> Optional[str]:
        if not self.client:
            logger.warning("LLM client not configured")
            return None
            
        messages = [{"role": "system", "content": system_prompt}]
        
        if history:
            messages.extend(history)
            
        messages.append({"role": "user", "content": prompt})

        try:
            # Synchronous call wrapped in async context
            chat_completion = self.client.chat.completions.create(
                messages=messages,
                model=self.model,
                temperature=0.7,
            )
            return chat_completion.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return None

    async def analyze_intent(self, message: str, history: List[Dict[str, str]] = None) -> Dict:
        """
        Analyze the intent of a user message.
        Returns a dict with: intent (str), confidence (float), tags (List[str]), reply_suggestion (str)
        """
        if not self.client:
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
