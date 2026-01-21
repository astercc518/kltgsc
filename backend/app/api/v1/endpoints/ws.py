from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from jose import jwt, JWTError
from app.core.config import settings
from app.services.websocket_manager import manager
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(None, description="JWT Token for authentication")
):
    """
    WebSocket 端点 - 需要 JWT Token 认证
    连接示例: ws://host/api/v1/ws?token=your_jwt_token
    """
    # 验证 Token
    if not token:
        logger.warning(f"WebSocket connection rejected: Missing token from {websocket.client.host if websocket.client else 'unknown'}")
        await websocket.close(code=4001, reason="Authentication required")
        return
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username = payload.get("sub")
        if not username:
            logger.warning(f"WebSocket connection rejected: Invalid token payload")
            await websocket.close(code=4002, reason="Invalid token")
            return
    except JWTError as e:
        logger.warning(f"WebSocket connection rejected: Token error - {str(e)}")
        await websocket.close(code=4003, reason="Token expired or invalid")
        return

    # 认证成功，建立连接
    logger.info(f"WebSocket connected: user={username}")
    await manager.connect(websocket)
    
    try:
        while True:
            # 保持连接 / 接收前端命令
            data = await websocket.receive_text()
            # 可以处理心跳或其他命令
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: user={username}")
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        manager.disconnect(websocket)
