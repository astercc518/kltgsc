import logging
import aiohttp
from typing import List, Optional
from sqlmodel import Session, select
from app.models.proxy import Proxy
from app.core.config import settings

logger = logging.getLogger(__name__)

class ProxyFetcherService:
    def __init__(self, db_session: Session):
        self.session = db_session
        self.api_url = settings.IP2WORLD_API_URL

    async def fetch_from_ip2world(self, api_url: Optional[str] = None, category: str = "static", provider_type: str = "datacenter") -> int:
        """
        从 IP2World API 提取代理并存入数据库
        返回新增代理数量
        """
        target_url = api_url or self.api_url
        if not target_url:
            logger.warning("IP2World API URL not provided")
            return 0

        try:
            async with aiohttp.ClientSession() as client:
                async with client.get(target_url) as response:
                    if response.status != 200:
                        logger.error(f"IP2World API error: {response.status}")
                        return 0
                    
                    text = await response.text()
                    # 假设返回格式为每行一个代理: IP:Port:User:Pass
                    # 或者 IP:Port (如果是白名单模式)
                    lines = text.strip().split('\n')
                    
                    new_count = 0
                    for line in lines:
                        if not line.strip():
                            continue
                            
                        parts = line.strip().split(':')
                        proxy_data = {}
                        
                        if len(parts) == 2:
                            # IP:Port
                            proxy_data = {
                                "ip": parts[0],
                                "port": int(parts[1]),
                                "protocol": "socks5",
                                "category": category,
                                "provider_type": provider_type
                            }
                        elif len(parts) >= 4:
                            # IP:Port:User:Pass
                            proxy_data = {
                                "ip": parts[0],
                                "port": int(parts[1]),
                                "username": parts[2],
                                "password": parts[3],
                                "protocol": "socks5",
                                "category": category,
                                "provider_type": provider_type
                            }
                        else:
                            continue

                        # 检查去重
                        existing = self.session.exec(
                            select(Proxy).where(
                                Proxy.ip == proxy_data["ip"],
                                Proxy.port == proxy_data["port"]
                            )
                        ).first()

                        if not existing:
                            proxy = Proxy(**proxy_data)
                            self.session.add(proxy)
                            new_count += 1
                    
                    self.session.commit()
                    return new_count

        except Exception as e:
            logger.error(f"Failed to fetch proxies: {str(e)}")
            return 0

    def get_available_proxy(self) -> Optional[Proxy]:
        """获取一个可用的代理"""
        # 优先选择未被大量使用的代理 (这里简单实现为随机或取第一个 active)
        # 实际逻辑可以在 Account 表关联中统计使用次数
        statement = select(Proxy).where(Proxy.status == "active")
        result = self.session.exec(statement).first()
        return result
