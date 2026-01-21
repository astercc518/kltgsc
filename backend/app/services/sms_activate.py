import logging
import aiohttp
import asyncio
from app.core.config import settings

logger = logging.getLogger(__name__)

class SMSActivateService:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.SMS_ACTIVATE_API_KEY
        self.base_url = "https://api.sms-activate.org/stubs/handler_api.php"

    async def get_number(self, country: int = 0, operator: str = "any") -> dict:
        """
        获取手机号
        :param country: 国家ID (0=Russia, 6=Indonesia etc.)
        :param operator: 运营商
        :return: {"id": activation_id, "number": phone_number}
        """
        if not self.api_key:
            raise ValueError("SMS_ACTIVATE_API_KEY not configured")

        params = {
            "api_key": self.api_key,
            "action": "getNumber",
            "service": "tg",
            "country": country,
            "operator": operator
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(self.base_url, params=params) as resp:
                text = await resp.text()
                if "ACCESS_NUMBER" in text:
                    # ACCESS_NUMBER:$id:$number
                    parts = text.split(":")
                    return {"id": parts[1], "number": parts[2]}
                elif "NO_NUMBERS" in text:
                    raise Exception("No numbers available")
                elif "BAD_KEY" in text:
                    raise ValueError("Invalid SMS Activate API Key")
                else:
                    raise Exception(f"SMS-Activate Error: {text}")

    async def wait_for_code(self, activation_id: str, timeout: int = 120) -> str:
        """
        轮询等待验证码
        """
        params = {
            "api_key": self.api_key,
            "action": "getStatus",
            "id": activation_id
        }
        
        start_time = asyncio.get_event_loop().time()
        
        async with aiohttp.ClientSession() as session:
            while (asyncio.get_event_loop().time() - start_time) < timeout:
                try:
                    async with session.get(self.base_url, params=params) as resp:
                        text = await resp.text()
                        
                        if "STATUS_OK" in text:
                            # STATUS_OK:$code
                            return text.split(":")[1]
                        elif "STATUS_CANCEL" in text:
                            raise Exception("Activation canceled")
                        elif "BAD_KEY" in text:
                            raise ValueError("Invalid SMS Activate API Key")
                        
                        # STATUS_WAIT_CODE - continue waiting
                        await asyncio.sleep(5)
                except Exception as e:
                    logger.error(f"Error checking status: {e}")
                    await asyncio.sleep(5)
                
        raise TimeoutError("Timeout waiting for SMS code")

    async def set_status(self, activation_id: str, status: int):
        """
        设置激活状态
        1: 准备好 (Ready)
        3: 要求重发 (Request another code)
        6: 完成且通过 (Complete)
        8: 取消/封号 (Cancel/Banned)
        """
        params = {
            "api_key": self.api_key,
            "action": "setStatus",
            "id": activation_id,
            "status": status
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(self.base_url, params=params) as resp:
                return await resp.text()
