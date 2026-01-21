import redis
import time
from contextlib import contextmanager
from app.core.config import settings

redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

class RedisSemaphore:
    def __init__(self, client, limit: int, name: str = "global_semaphore", timeout: int = 10):
        self.client = client
        self.limit = limit
        self.name = name
        self.timeout = timeout

    def acquire(self) -> bool:
        """
        Simple non-blocking acquire (or with short retry).
        For Celery, we might just want to fail or retry later if full.
        """
        # Remove expired keys first (simple cleanup)
        # In production, use sorted sets for better timeout management, 
        # but here we'll use a simple counter with expiration for individual locks if we were doing distributed locks.
        # For a simple semaphore, we can use a counter.
        
        # LUA script for atomic check-and-increment
        lua_script = """
        local current = redis.call('get', KEYS[1])
        if current and tonumber(current) >= tonumber(ARGV[1]) then
            return 0
        else
            redis.call('incr', KEYS[1])
            return 1
        end
        """
        script = self.client.register_script(lua_script)
        result = script(keys=[self.name], args=[self.limit])
        return bool(result)

    def release(self):
        self.client.decr(self.name)

    @contextmanager
    def acquire_lock(self):
        # Blocking acquire with timeout
        start = time.time()
        acquired = False
        while time.time() - start < self.timeout:
            if self.acquire():
                acquired = True
                break
            time.sleep(0.1)
        
        if not acquired:
            raise Exception(f"Could not acquire semaphore '{self.name}' within {self.timeout}s")
        
        try:
            yield
        finally:
            self.release()

# Global helper
def get_redis_semaphore(limit: int = 5, name: str = "global_concurrency"):
    return RedisSemaphore(redis_client, limit, name)
