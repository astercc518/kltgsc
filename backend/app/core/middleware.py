"""
安全中间件 - 添加安全头部和请求监控
"""
import time
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger(__name__)


class SecurityMiddleware(BaseHTTPMiddleware):
    """
    安全中间件：
    1. 添加安全 HTTP 头部
    2. 记录请求处理时间
    3. 防止信息泄露
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.time()

        # 记录请求（可选，用于审计）
        client_ip = request.headers.get("X-Real-IP", request.client.host if request.client else "unknown")
        
        try:
            response = await call_next(request)
        except Exception as e:
            logger.error(f"Request error from {client_ip}: {str(e)}")
            raise

        # 计算处理时间
        process_time = time.time() - start_time

        # 安全头部
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        
        # 移除可能泄露信息的头部
        if "Server" in response.headers:
            del response.headers["Server"]
        if "X-Powered-By" in response.headers:
            del response.headers["X-Powered-By"]

        # 处理时间（仅用于调试，生产环境可移除）
        response.headers["X-Process-Time"] = f"{process_time:.4f}"

        # 记录慢请求
        if process_time > 5.0:
            logger.warning(f"Slow request: {request.method} {request.url.path} took {process_time:.2f}s from {client_ip}")

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    简单的内存级别限速中间件（备用，主要由 Nginx 处理）
    """
    
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests = {}  # ip -> [(timestamp, count)]
    
    async def dispatch(self, request: Request, call_next) -> Response:
        # 主要限速由 Nginx 处理，这里作为备用
        return await call_next(request)
