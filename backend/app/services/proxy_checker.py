"""
代理连通性检测服务
使用 aiohttp 或 requests 测试代理是否可用
支持 SOCKS5 和 HTTP 代理
"""
import asyncio
from typing import Tuple, Optional, Dict, Any
from app.models.proxy import Proxy

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

try:
    from aiohttp_socks import ProxyConnector
    HAS_AIOHTTP_SOCKS = True
except ImportError:
    HAS_AIOHTTP_SOCKS = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

import socket

async def check_proxy_connectivity_async(proxy: Proxy, fetch_details: bool = False) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """异步检测代理连通性"""
    if not HAS_AIOHTTP:
        # 如果没有 aiohttp，使用同步方法
        return check_proxy_connectivity(proxy, fetch_details)
    
    try:
        timeout = aiohttp.ClientTimeout(total=20) # 增加超时时间以容纳详细信息查询
        details = None
        
        # 处理 SOCKS5 代理
        if proxy.protocol.lower() in ['socks5', 'socks4', 'socks4a']:
            if HAS_AIOHTTP_SOCKS:
                # 使用 aiohttp-socks 支持 SOCKS 代理
                proxy_ip = f"[{proxy.ip}]" if ':' in proxy.ip else proxy.ip
                connector = ProxyConnector.from_url(
                    f"{proxy.protocol}://{proxy.username or ''}:{proxy.password or ''}@{proxy_ip}:{proxy.port}",
                    rdns=True
                )
                async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                    # 1. 基础连通性测试
                    test_urls = [
                        "http://httpbin.org/ip",
                        "http://api.ipify.org?format=json",
                        "http://ifconfig.me/ip",
                    ]
                    
                    connected = False
                    for test_url in test_urls:
                        try:
                            async with session.get(test_url, timeout=10) as response:
                                if response.status == 200:
                                    connected = True
                                    break
                        except Exception:
                            continue
                    
                    if not connected:
                        return False, "All test URLs failed", None

                    # 2. 获取详细信息 (如果请求)
                    if fetch_details:
                        try:
                            # ip-api.com 免费版限制 45 req/min
                            async with session.get("http://ip-api.com/json/?fields=status,message,country,countryCode,isp,org,as,hosting,query", timeout=10) as resp:
                                if resp.status == 200:
                                    data = await resp.json()
                                    if data.get('status') == 'success':
                                        details = data
                        except Exception as e:
                            # 详细信息获取失败不影响连通性结果
                            pass
                            
                    return True, None, details

            else:
                # 如果没有 aiohttp-socks，降级到 socket 测试
                return check_proxy_connectivity(proxy, fetch_details)
        else:
            # HTTP/HTTPS 代理
            proxy_url = f"{proxy.protocol}://"
            if proxy.username and proxy.password:
                proxy_url += f"{proxy.username}:{proxy.password}@"
            
            proxy_ip = f"[{proxy.ip}]" if ':' in proxy.ip else proxy.ip
            proxy_url += f"{proxy_ip}:{proxy.port}"
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                test_urls = [
                    "http://httpbin.org/ip",
                    "http://api.ipify.org?format=json",
                ]
                
                connected = False
                for test_url in test_urls:
                    try:
                        async with session.get(
                            test_url,
                            proxy=proxy_url,
                            timeout=10
                        ) as response:
                            if response.status == 200:
                                connected = True
                                break
                    except Exception:
                        continue
                
                if not connected:
                    return False, "All test URLs failed", None

                if fetch_details:
                    try:
                        async with session.get(
                            "http://ip-api.com/json/?fields=status,message,country,countryCode,isp,org,as,hosting,query",
                            proxy=proxy_url,
                            timeout=10
                        ) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                if data.get('status') == 'success':
                                    details = data
                    except Exception as e:
                        pass
                        
                return True, None, details

    except asyncio.TimeoutError:
        return False, "Connection timeout", None
    except aiohttp.ClientError as e:
        return False, str(e), None
    except Exception as e:
        return False, f"Unexpected error: {str(e)}", None

def check_proxy_connectivity(proxy: Proxy, fetch_details: bool = False) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """同步检测代理连通性（使用 requests 或 socket）"""
    if HAS_AIOHTTP:
        # 如果有 aiohttp，使用异步版本
        # 始终创建新的事件循环，避免在 Celery worker 中出现 "Event loop is closed" 错误
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(check_proxy_connectivity_async(proxy, fetch_details))
        finally:
            loop.close()
    
    # 使用 requests（如果可用）
    if HAS_REQUESTS:
        try:
            # 处理 SOCKS5 代理
            if proxy.protocol.lower() in ['socks5', 'socks4', 'socks4a']:
                try:
                    import socks
                    import socket as std_socket
                    sock = socks.socksocket()
                    sock.set_proxy(
                        getattr(socks, proxy.protocol.upper()),
                        proxy.ip,
                        proxy.port,
                        username=proxy.username,
                        password=proxy.password
                    )
                    sock.settimeout(10)
                    sock.connect(('httpbin.org', 80))
                    sock.close()
                    # Requests 暂不支持通过 SOCKS 简单获取详情 (需要依赖 requests[socks])
                    # 这里简化处理，如果只是 socket 通了，就返回成功，不 fetch details
                    return True, None, None
                except Exception as e:
                    # 尝试裸 socket
                    pass
            else:
                # HTTP/HTTPS 代理
                proxy_ip = f"[{proxy.ip}]" if ':' in proxy.ip else proxy.ip
                proxy_dict = {
                    'http': f"{proxy.protocol}://{proxy_ip}:{proxy.port}",
                    'https': f"{proxy.protocol}://{proxy_ip}:{proxy.port}"
                }
                
                auth = None
                if proxy.username and proxy.password:
                    from requests.auth import HTTPProxyAuth
                    auth = HTTPProxyAuth(proxy.username, proxy.password)
                
                response = requests.get("http://httpbin.org/ip", proxies=proxy_dict, auth=auth, timeout=10)
                if response.status_code == 200:
                    details = None
                    if fetch_details:
                        try:
                            resp = requests.get(
                                "http://ip-api.com/json/?fields=status,message,country,countryCode,isp,org,as,hosting,query",
                                proxies=proxy_dict, 
                                auth=auth, 
                                timeout=10
                            )
                            if resp.status_code == 200:
                                data = resp.json()
                                if data.get('status') == 'success':
                                    details = data
                        except Exception:
                            pass
                    return True, None, details
                
                return False, "Request failed", None
        except Exception as e:
            return False, f"Request error: {str(e)}", None
    
    # 裸 Socket (仅检测端口)
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        result = sock.connect_ex((proxy.ip, proxy.port))
        sock.close()
        if result == 0:
            return True, None, None
        else:
            return False, "Connection refused", None
    except Exception as e:
        return False, str(e), None
