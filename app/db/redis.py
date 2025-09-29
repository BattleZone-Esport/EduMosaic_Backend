"""
Redis cache configuration for EduMosaic
"""

import redis.asyncio as redis
from typing import Optional
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

class RedisCache:
    """Redis cache manager with graceful fallback"""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.is_connected = False
    
    async def connect(self):
        """Connect to Redis"""
        try:
            if settings.REDIS_URL:
                self.redis_client = redis.from_url(
                    settings.get_redis_url(),
                    encoding="utf-8",
                    decode_responses=True
                )
                await self.redis_client.ping()
                self.is_connected = True
                logger.info("Redis connected successfully")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. Running without cache.")
            self.is_connected = False
    
    async def disconnect(self):
        """Disconnect from Redis"""
        if self.redis_client:
            await self.redis_client.close()
            self.is_connected = False
    
    async def get(self, key: str) -> Optional[str]:
        """Get value from cache"""
        if not self.is_connected:
            return None
        try:
            return await self.redis_client.get(key)
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return None
    
    async def set(self, key: str, value: str, ttl: int = None) -> bool:
        """Set value in cache"""
        if not self.is_connected:
            return False
        try:
            ttl = ttl or settings.CACHE_TTL
            await self.redis_client.set(key, value, ex=ttl)
            return True
        except Exception as e:
            logger.error(f"Redis set error: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        if not self.is_connected:
            return False
        try:
            await self.redis_client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
            return False

# Global cache instance
cache = RedisCache()
