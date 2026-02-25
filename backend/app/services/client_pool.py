"""
Telegram Client Connection Pool
Reuses Pyrogram clients to avoid repeated TLS handshakes.

Usage:
    The pool maintains a dictionary of connected Pyrogram Client instances,
    keyed by account_id. Instead of creating a new client for every operation
    (which incurs 1-3s of TLS/MTProto handshake overhead each time), callers
    can obtain an already-connected client from the pool.

    Example integration (gradual - does not require rewriting existing code):

        from app.services.client_pool import client_pool

        async def some_operation(account: Account):
            async def factory():
                client = Client(name=..., workdir="sessions", ...)
                await client.connect()
                return client

            client = await client_pool.get_client(account.id, factory)
            try:
                result = await client.send_message(...)
                await client_pool.release_client(account.id)
                return result
            except (AuthKeyUnregistered, SessionRevoked):
                # Session is dead, remove from pool
                await client_pool.remove_client(account.id)
                raise

    Cleanup:
        Call `await client_pool.cleanup_expired()` periodically (e.g. every 60s)
        to disconnect clients that have been idle longer than the TTL.

        Call `await client_pool.close_all()` on application shutdown.
"""
import asyncio
import time
import logging
from typing import Dict
from pyrogram import Client

logger = logging.getLogger(__name__)


class TelegramClientPool:
    """LRU connection pool for Pyrogram clients, keyed by account_id."""

    def __init__(self, max_size: int = 50, ttl: int = 300):
        self.max_size = max_size
        self.ttl = ttl  # seconds before idle client is disconnected
        self._pool: Dict[int, dict] = {}  # account_id -> {"client": Client, "last_used": float}
        self._lock = asyncio.Lock()

    async def get_client(self, account_id: int, client_factory) -> Client:
        """Get or create a client for the given account.
        client_factory is an async callable that returns a connected Client."""
        async with self._lock:
            entry = self._pool.get(account_id)
            if entry and entry["client"].is_connected:
                entry["last_used"] = time.time()
                return entry["client"]

            # Evict oldest if at capacity
            if len(self._pool) >= self.max_size:
                await self._evict_oldest()

        # Create new client outside the lock
        client = await client_factory()

        async with self._lock:
            self._pool[account_id] = {
                "client": client,
                "last_used": time.time()
            }
        return client

    async def release_client(self, account_id: int):
        """Mark client as available (update last_used)."""
        async with self._lock:
            if account_id in self._pool:
                self._pool[account_id]["last_used"] = time.time()

    async def remove_client(self, account_id: int):
        """Disconnect and remove a client (on error)."""
        async with self._lock:
            entry = self._pool.pop(account_id, None)
        if entry:
            try:
                await entry["client"].stop()
            except Exception:
                pass

    async def _evict_oldest(self):
        """Remove the least recently used client."""
        if not self._pool:
            return
        oldest_id = min(self._pool, key=lambda k: self._pool[k]["last_used"])
        entry = self._pool.pop(oldest_id)
        try:
            await entry["client"].stop()
        except Exception:
            pass
        logger.debug(f"Evicted client for account {oldest_id}")

    async def cleanup_expired(self):
        """Remove clients that have been idle longer than TTL."""
        now = time.time()
        expired = []
        async with self._lock:
            for account_id, entry in list(self._pool.items()):
                if now - entry["last_used"] > self.ttl:
                    expired.append(self._pool.pop(account_id))

        for entry in expired:
            try:
                await entry["client"].stop()
            except Exception:
                pass

    async def close_all(self):
        """Disconnect all pooled clients."""
        async with self._lock:
            entries = list(self._pool.values())
            self._pool.clear()
        for entry in entries:
            try:
                await entry["client"].stop()
            except Exception:
                pass


# Global pool instance
client_pool = TelegramClientPool(max_size=50, ttl=300)
