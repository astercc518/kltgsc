from typing import Optional

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from jose import jwt, JWTError
from pydantic import ValidationError
from sqlmodel import Session, select

from app.core.db import get_session
from app.core.config import settings
from app.core.security import is_token_revoked
from app.models.token import TokenPayload
from app.models.user import USER_ROLE_ADMIN, User
from app.services.websocket_manager import manager
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


class WebSocketAuthError(Exception):
    def __init__(self, close_code: int, reason: str):
        self.close_code = close_code
        self.reason = reason
        super().__init__(reason)


def authenticate_websocket_admin(token: Optional[str], session: Session) -> User:
    """Resolve an active platform admin before a global socket is accepted."""
    if not token:
        raise WebSocketAuthError(4001, "Authentication required")

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        token_data = TokenPayload(**payload)
    except (JWTError, ValidationError) as exc:
        raise WebSocketAuthError(4003, "Token expired or invalid") from exc

    if (
        token_data.type not in {None, "access"}
        or not token_data.sub
        or not token_data.jti
    ):
        raise WebSocketAuthError(4003, "Invalid platform access token")

    try:
        revoked = is_token_revoked(token_data.jti)
    except Exception as exc:
        raise WebSocketAuthError(4003, "Authentication unavailable") from exc
    if revoked:
        raise WebSocketAuthError(4003, "Token revoked")

    user = session.exec(
        select(User).where(User.username == token_data.sub)
    ).first()
    if not user or not user.is_active:
        raise WebSocketAuthError(4003, "User unavailable")
    if user.role != USER_ROLE_ADMIN and not user.is_superuser:
        raise WebSocketAuthError(4004, "Admin role required")
    return user


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None, description="JWT Token for authentication"),
    session: Session = Depends(get_session),
):
    """
    WebSocket 端点 - 需要 JWT Token 认证
    连接示例: ws://host/api/v1/ws?token=your_jwt_token
    """
    try:
        user = authenticate_websocket_admin(token, session)
    except WebSocketAuthError as exc:
        client_host = websocket.client.host if websocket.client else "unknown"
        logger.warning(
            "WebSocket connection rejected: code=%s client=%s",
            exc.close_code,
            client_host,
        )
        await websocket.close(code=exc.close_code, reason=exc.reason)
        return

    # 认证成功，建立连接
    logger.info("WebSocket connected: user=%s", user.username)
    await manager.connect(websocket)
    
    try:
        while True:
            # 保持连接 / 接收前端命令
            data = await websocket.receive_text()
            # 可以处理心跳或其他命令
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: user=%s", user.username)
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        manager.disconnect(websocket)
