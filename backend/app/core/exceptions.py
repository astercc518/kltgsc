"""
标准化异常处理模块
定义所有业务异常和错误码
"""
import logging
from typing import Optional, Any, Dict
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_429_TOO_MANY_REQUESTS,
    HTTP_500_INTERNAL_SERVER_ERROR,
    HTTP_503_SERVICE_UNAVAILABLE,
)

logger = logging.getLogger(__name__)


# ==================== 基础异常类 ====================

class TGSCException(Exception):
    """TGSC 平台基础异常类"""
    
    error_code: str = "TGSC_ERROR"
    status_code: int = HTTP_500_INTERNAL_SERVER_ERROR
    
    def __init__(
        self, 
        message: str = "An error occurred",
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为响应字典"""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details
        }


# ==================== 账号相关异常 ====================

class AccountException(TGSCException):
    """账号相关异常基类"""
    error_code = "ACCOUNT_ERROR"
    status_code = HTTP_400_BAD_REQUEST


class AccountFloodWaitException(AccountException):
    """账号被限流，需要等待"""
    error_code = "ACCOUNT_FLOOD_WAIT"
    status_code = HTTP_429_TOO_MANY_REQUESTS
    
    def __init__(self, wait_seconds: int, message: str = "FloodWait"):
        self.wait_seconds = wait_seconds
        super().__init__(
            message=f"{message}: 需要等待 {wait_seconds} 秒",
            details={"wait_seconds": wait_seconds}
        )


class AccountBannedException(AccountException):
    """账号被封禁"""
    error_code = "ACCOUNT_BANNED"
    status_code = HTTP_403_FORBIDDEN
    
    def __init__(self, message: str = "账号已被封禁"):
        super().__init__(message=message)


class AccountSpamBlockException(AccountException):
    """账号被标记为 spam"""
    error_code = "ACCOUNT_SPAM_BLOCK"
    status_code = HTTP_403_FORBIDDEN
    
    def __init__(self, message: str = "账号受到垃圾消息限制"):
        super().__init__(message=message)


class AccountSessionInvalidException(AccountException):
    """Session 无效"""
    error_code = "ACCOUNT_SESSION_INVALID"
    status_code = HTTP_401_UNAUTHORIZED
    
    def __init__(self, message: str = "Session 已失效，请重新登录"):
        super().__init__(message=message)


class AccountNotFoundException(AccountException):
    """账号不存在"""
    error_code = "ACCOUNT_NOT_FOUND"
    status_code = HTTP_404_NOT_FOUND
    
    def __init__(self, account_id: Optional[int] = None):
        msg = f"账号 {account_id} 不存在" if account_id else "账号不存在"
        super().__init__(message=msg, details={"account_id": account_id})


class AccountCooldownException(AccountException):
    """账号在冷却中"""
    error_code = "ACCOUNT_COOLDOWN"
    status_code = HTTP_429_TOO_MANY_REQUESTS
    
    def __init__(self, cooldown_until: str, message: str = "账号在冷却中"):
        super().__init__(
            message=message,
            details={"cooldown_until": cooldown_until}
        )


# ==================== 代理相关异常 ====================

class ProxyException(TGSCException):
    """代理相关异常基类"""
    error_code = "PROXY_ERROR"
    status_code = HTTP_400_BAD_REQUEST


class ProxyConnectionException(ProxyException):
    """代理连接失败"""
    error_code = "PROXY_CONNECTION_FAILED"
    status_code = HTTP_503_SERVICE_UNAVAILABLE
    
    def __init__(self, proxy_id: Optional[int] = None, message: str = "代理连接失败"):
        super().__init__(
            message=message,
            details={"proxy_id": proxy_id}
        )


class ProxyNotFoundException(ProxyException):
    """代理不存在"""
    error_code = "PROXY_NOT_FOUND"
    status_code = HTTP_404_NOT_FOUND


class NoAvailableProxyException(ProxyException):
    """没有可用代理"""
    error_code = "NO_AVAILABLE_PROXY"
    status_code = HTTP_503_SERVICE_UNAVAILABLE
    
    def __init__(self, message: str = "没有可用的代理"):
        super().__init__(message=message)


# ==================== 任务相关异常 ====================

class TaskException(TGSCException):
    """任务相关异常基类"""
    error_code = "TASK_ERROR"
    status_code = HTTP_400_BAD_REQUEST


class TaskNotFoundException(TaskException):
    """任务不存在"""
    error_code = "TASK_NOT_FOUND"
    status_code = HTTP_404_NOT_FOUND


class TaskAlreadyRunningException(TaskException):
    """任务已在运行中"""
    error_code = "TASK_ALREADY_RUNNING"
    status_code = HTTP_400_BAD_REQUEST
    
    def __init__(self, task_id: Optional[int] = None):
        super().__init__(
            message="任务已在运行中",
            details={"task_id": task_id}
        )


# ==================== 认证相关异常 ====================

class AuthException(TGSCException):
    """认证相关异常基类"""
    error_code = "AUTH_ERROR"
    status_code = HTTP_401_UNAUTHORIZED


class InvalidCredentialsException(AuthException):
    """无效的凭证"""
    error_code = "INVALID_CREDENTIALS"
    
    def __init__(self, message: str = "用户名或密码错误"):
        super().__init__(message=message)


class TokenExpiredException(AuthException):
    """Token 已过期"""
    error_code = "TOKEN_EXPIRED"
    
    def __init__(self, message: str = "登录已过期，请重新登录"):
        super().__init__(message=message)


class InsufficientPermissionsException(AuthException):
    """权限不足"""
    error_code = "INSUFFICIENT_PERMISSIONS"
    status_code = HTTP_403_FORBIDDEN
    
    def __init__(self, message: str = "权限不足"):
        super().__init__(message=message)


# ==================== 加密相关异常 ====================

class EncryptionException(TGSCException):
    """加密相关异常"""
    error_code = "ENCRYPTION_ERROR"
    status_code = HTTP_500_INTERNAL_SERVER_ERROR


class DecryptionException(EncryptionException):
    """解密失败"""
    error_code = "DECRYPTION_FAILED"
    
    def __init__(self, message: str = "解密失败，密钥可能不正确"):
        super().__init__(message=message)


# ==================== 外部服务异常 ====================

class ExternalServiceException(TGSCException):
    """外部服务异常基类"""
    error_code = "EXTERNAL_SERVICE_ERROR"
    status_code = HTTP_503_SERVICE_UNAVAILABLE


class TelegramAPIException(ExternalServiceException):
    """Telegram API 异常"""
    error_code = "TELEGRAM_API_ERROR"


class SMSServiceException(ExternalServiceException):
    """短信服务异常"""
    error_code = "SMS_SERVICE_ERROR"


class LLMServiceException(ExternalServiceException):
    """LLM 服务异常"""
    error_code = "LLM_SERVICE_ERROR"


# ==================== 验证相关异常 ====================

class ValidationException(TGSCException):
    """数据验证异常"""
    error_code = "VALIDATION_ERROR"
    status_code = HTTP_400_BAD_REQUEST


class InvalidInputException(ValidationException):
    """无效输入"""
    error_code = "INVALID_INPUT"


# ==================== 异常处理器注册函数 ====================

def register_exception_handlers(app):
    """注册全局异常处理器"""
    
    @app.exception_handler(TGSCException)
    async def tgsc_exception_handler(request: Request, exc: TGSCException):
        """处理所有 TGSC 自定义异常"""
        logger.warning(
            f"TGSCException: {exc.error_code} - {exc.message} | "
            f"Path: {request.url.path} | Details: {exc.details}"
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                **exc.to_dict()
            }
        )
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """处理 HTTP 异常"""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error_code": f"HTTP_{exc.status_code}",
                "message": exc.detail,
                "details": {}
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """处理所有未捕获的异常"""
        logger.exception(
            f"Unhandled exception: {type(exc).__name__} - {str(exc)} | "
            f"Path: {request.url.path}"
        )
        return JSONResponse(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error_code": "INTERNAL_ERROR",
                "message": "服务器内部错误",
                "details": {"type": type(exc).__name__}
            }
        )
