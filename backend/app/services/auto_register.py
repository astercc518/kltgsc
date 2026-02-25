import logging
import asyncio
import random
import os
from typing import Optional, Dict, Tuple
from datetime import datetime

from sqlmodel import Session
from pyrogram import Client
from pyrogram.errors import (
    PhoneNumberBanned, 
    PhoneCodeInvalid, 
    PhoneCodeExpired,
    FloodWait
)

from app.models.account import Account
from app.models.proxy import Proxy
from app.services.device_generator import DeviceGenerator
from app.services.sms_activate import SMSActivateService
from app.services.telegram_client import get_proxy_dict
from app.core.config import settings

logger = logging.getLogger(__name__)

class AutoRegisterService:
    def __init__(self, db_session: Session):
        self.session = db_session
        
        # Try to get API key from SystemConfig first
        try:
            from app.models.system_config import SystemConfig
            config = db_session.get(SystemConfig, "sms_activate_api_key")
            api_key = config.value if config else None
        except Exception as e:
            logger.warning(f"Failed to load system config: {e}")
            api_key = None
            
        self.sms_service = SMSActivateService(api_key=api_key)

    async def register_account(
        self, 
        country: int = 0, 
        api_id: int = 6, 
        api_hash: str = "eb06d4abfb49dc3eeb1aeb98ae0f581e",
        proxy_category: str = "rotating"
    ) -> Dict:
        """
        执行单个账号自动注册流程
        """
        client = None
        activation_id = None
        
        # 1. 获取可用代理
        # TODO: 这里应该实现更复杂的代理选择策略(如IP复用限制)
        proxy = self._get_available_proxy(category=proxy_category)
        if not proxy:
            # Fallback to any active proxy if specific category not found
            proxy = self._get_available_proxy(category=None)
        
        if not proxy:
            return {"status": "error", "message": "No available proxies"}
            
        proxy_dict = get_proxy_dict(proxy)
        
        try:
            # 2. 获取手机号
            logger.info("Requesting number from SMS-Activate...")
            activation = await self.sms_service.get_number(country=country)
            phone_number = activation['number']
            activation_id = activation['id']
            logger.info(f"Got number: {phone_number} (ID: {activation_id})")

            # 3. 生成设备指纹与随机身份
            device_info = DeviceGenerator.generate()
            first_name, last_name = self._generate_random_name()

            # 4. 初始化 Pyrogram 客户端 (内存模式)
            client = Client(
                name=f"reg_{phone_number}",
                in_memory=True,
                api_id=api_id,
                api_hash=api_hash,
                proxy=proxy_dict,
                device_model=device_info["device_model"],
                system_version=device_info["system_version"],
                app_version=device_info["app_version"],
                lang_code="en"
            )

            logger.info(f"Connecting to Telegram with proxy {proxy.ip}...")
            await client.connect()

            # 5. 发送验证码
            try:
                sent_code = await client.send_code(phone_number)
            except PhoneNumberBanned:
                logger.warning(f"Phone number {phone_number} is banned.")
                await self.sms_service.set_status(activation_id, 8) # Cancel
                return {"status": "failed", "message": "Phone number banned"}
            except FloodWait as e:
                logger.warning(f"FloodWait: {e.value}")
                await self.sms_service.set_status(activation_id, 8)
                return {"status": "failed", "message": f"FloodWait: {e.value}s"}

            # 拟人化延迟
            await asyncio.sleep(random.uniform(2, 5))

            # 6. 等待验证码
            logger.info("Waiting for SMS code...")
            try:
                code = await self.sms_service.wait_for_code(activation_id)
                logger.info(f"Received code: {code}")
            except TimeoutError:
                await self.sms_service.set_status(activation_id, 8)
                return {"status": "failed", "message": "Timeout waiting for code"}

            # 拟人化延迟
            await asyncio.sleep(random.uniform(1, 3))

            # 7. 提交注册
            try:
                user = await client.sign_up(
                    phone_number=phone_number, 
                    phone_code_hash=sent_code.phone_code_hash, 
                    phone_code=code,
                    first_name=first_name, 
                    last_name=last_name
                )
                
                # 通知接码平台成功
                await self.sms_service.set_status(activation_id, 6)
                
                # 8. 设置 2FA (风控关键)
                # 随机延迟后再设置
                await asyncio.sleep(random.uniform(3, 8))
                
                password = settings.DEFAULT_2FA_PASSWORD
                if password:
                    await client.enable_cloud_password(password=password)
                    logger.info("2FA enabled successfully")

                # 9. 导出 Session 并保存
                session_string = await client.export_session_string()
                
                new_account = Account(
                    phone_number=phone_number,
                    api_id=api_id,
                    api_hash=api_hash,
                    session_string=session_string,
                    device_model=device_info["device_model"],
                    system_version=device_info["system_version"],
                    app_version=device_info["app_version"],
                    proxy_id=proxy.id,
                    status="active", # 刚注册完暂时标记为 active，或者专门的 warmup 状态
                    last_active=datetime.utcnow()
                )
                
                self.session.add(new_account)
                self.session.commit()
                self.session.refresh(new_account)
                
                return {
                    "status": "success", 
                    "phone": phone_number, 
                    "account_id": new_account.id
                }

            except (PhoneCodeInvalid, PhoneCodeExpired):
                await self.sms_service.set_status(activation_id, 8)
                return {"status": "failed", "message": "Invalid code"}

        except Exception as e:
            logger.error(f"Registration failed: {str(e)}")
            if activation_id:
                try:
                    await self.sms_service.set_status(activation_id, 8)
                except Exception:
                    pass
            return {"status": "error", "message": str(e)}
            
        finally:
            if client and client.is_connected:
                await client.disconnect()

    def _get_available_proxy(self, category: Optional[str] = None) -> Optional[Proxy]:
        """
        获取一个可用的 ISP 代理
        简单的策略：取 active 状态且失败次数少的代理
        """
        # 实际生产中这里应该有更复杂的逻辑，比如每个IP每天注册限制
        from sqlmodel import select
        query = select(Proxy).where(Proxy.status == "active")
        if category:
            query = query.where(Proxy.category == category)
        
        statement = query.order_by(Proxy.fail_count)
        # 随机取前5个中的一个，避免并发冲突
        results = self.session.exec(statement).fetchmany(5)
        if results:
            return random.choice(results)
        return None

    def _generate_random_name(self) -> Tuple[str, str]:
        """生成随机欧美姓名"""
        first_names = ["James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph", "Thomas", "Charles"]
        last_names = ["Smith", "Johnson", "Williams", "Jones", "Brown", "Davis", "Miller", "Wilson", "Moore", "Taylor"]
        
        return random.choice(first_names), random.choice(last_names)
