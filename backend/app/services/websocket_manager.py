import logging
import asyncio
import json
from typing import Dict, List
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        # Store active connections: account_id -> List[WebSocket]
        # Or simpler: List[WebSocket] and broadcast to all admin panels
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: Dict):
        """
        Broadcast message to all connected clients
        """
        if not self.active_connections:
            return
            
        data = json.dumps(message)
        for connection in self.active_connections:
            try:
                await connection.send_text(data)
            except Exception as e:
                logger.error(f"Error broadcasting to socket: {e}")
                # We could remove broken connections here, but disconnect() handles it usually

manager = ConnectionManager()
