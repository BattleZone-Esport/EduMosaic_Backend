"""
Cache management using Redis
Provides caching utilities with fallback when Redis is unavailable
"""

import asyncio
import json
import logging
import pickle
from datetime import timedelta
from functools import wraps
from typing import Any, Optional, Union

import redis.asyncio as redis
from redis.exceptions import ConnectionError, RedisError

from app.core.config import settings

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Redis cache manager with automatic fallback
    """

    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.connected = False
        self._connection_attempts = 0
        self._max_connection_attempts = 3

    async def connect(self) -> bool:
        """
        Connect to Redis

        Returns:
            True if connected successfully, False otherwise
        """
        if not settings.REDIS_ENABLED:
            logger.info("Redis caching is disabled")
            return False

        if self.connected:
            return True

        while self._connection_attempts < self._max_connection_attempts:
            try:
                self.redis_client = redis.from_url(
                    settings.get_redis_url(),
                    max_connections=settings.REDIS_POOL_MAX_CONNECTIONS,
                    decode_responses=True,
                )

                # Test connection
                await self.redis_client.ping()
                self.connected = True
                logger.info("Connected to Redis successfully")
                return True

            except (RedisError, ConnectionError) as e:
                self._connection_attempts += 1
                logger.warning(
                    f"Failed to connect to Redis (attempt {self._connection_attempts}/{self._max_connection_attempts}): {e}"
                )

                if self._connection_attempts >= self._max_connection_attempts:
                    logger.error("Max Redis connection attempts reached. Cache will be disabled.")
                    self.connected = False
                    return False

                await asyncio.sleep(1)  # Wait before retry

        return False

    async def disconnect(self):
        """Disconnect from Redis"""
        if self.redis_client:
            await self.redis_client.close()
            self.connected = False
            logger.info("Disconnected from Redis")

    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found or Redis is unavailable
        """
        if not self.connected:
            return None

        try:
            value = await self.redis_client.get(key)

            if value is None:
                return None

            # Try to deserialize JSON first
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                # If JSON fails, try pickle
                try:
                    return pickle.loads(value.encode("latin-1"))
                except:
                    # Return as string if both fail
                    return value

        except (RedisError, ConnectionError) as e:
            logger.error(f"Redis get error for key {key}: {e}")
            self.connected = False
            return None

    async def set(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        """
        Set value in cache

        Args:
            key: Cache key
            value: Value to cache
            expire: Expiration time in seconds

        Returns:
            True if successful, False otherwise
        """
        if not self.connected:
            return False

        try:
            # Try to serialize as JSON first
            try:
                serialized = json.dumps(value)
            except (TypeError, ValueError):
                # Fall back to pickle for complex objects
                serialized = pickle.dumps(value).decode("latin-1")

            expire = expire or settings.REDIS_CACHE_TTL
            await self.redis_client.setex(key, expire, serialized)
            return True

        except (RedisError, ConnectionError) as e:
            logger.error(f"Redis set error for key {key}: {e}")
            self.connected = False
            return False

    async def delete(self, key: str) -> bool:
        """
        Delete value from cache

        Args:
            key: Cache key

        Returns:
            True if successful, False otherwise
        """
        if not self.connected:
            return False

        try:
            await self.redis_client.delete(key)
            return True

        except (RedisError, ConnectionError) as e:
            logger.error(f"Redis delete error for key {key}: {e}")
            self.connected = False
            return False

    async def exists(self, key: str) -> bool:
        """
        Check if key exists in cache

        Args:
            key: Cache key

        Returns:
            True if exists, False otherwise
        """
        if not self.connected:
            return False

        try:
            return await self.redis_client.exists(key) > 0

        except (RedisError, ConnectionError) as e:
            logger.error(f"Redis exists error for key {key}: {e}")
            self.connected = False
            return False

    async def clear_pattern(self, pattern: str) -> int:
        """
        Clear all keys matching pattern

        Args:
            pattern: Key pattern (e.g., "user:*")

        Returns:
            Number of keys deleted
        """
        if not self.connected:
            return 0

        try:
            keys = []
            async for key in self.redis_client.scan_iter(match=pattern):
                keys.append(key)

            if keys:
                return await self.redis_client.delete(*keys)
            return 0

        except (RedisError, ConnectionError) as e:
            logger.error(f"Redis clear pattern error for pattern {pattern}: {e}")
            self.connected = False
            return 0

    async def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """
        Increment a counter in cache

        Args:
            key: Cache key
            amount: Increment amount

        Returns:
            New value after increment or None if failed
        """
        if not self.connected:
            return None

        try:
            return await self.redis_client.incrby(key, amount)

        except (RedisError, ConnectionError) as e:
            logger.error(f"Redis increment error for key {key}: {e}")
            self.connected = False
            return None

    async def get_ttl(self, key: str) -> Optional[int]:
        """
        Get TTL for a key

        Args:
            key: Cache key

        Returns:
            TTL in seconds or None if key doesn't exist or Redis unavailable
        """
        if not self.connected:
            return None

        try:
            ttl = await self.redis_client.ttl(key)
            return ttl if ttl >= 0 else None

        except (RedisError, ConnectionError) as e:
            logger.error(f"Redis TTL error for key {key}: {e}")
            self.connected = False
            return None

    async def set_hash(self, key: str, mapping: dict, expire: Optional[int] = None) -> bool:
        """
        Set multiple fields in a hash

        Args:
            key: Hash key
            mapping: Dictionary of field-value pairs
            expire: Expiration time in seconds

        Returns:
            True if successful, False otherwise
        """
        if not self.connected:
            return False

        try:
            # Convert values to strings
            str_mapping = {
                k: json.dumps(v) if not isinstance(v, str) else v for k, v in mapping.items()
            }

            await self.redis_client.hset(key, mapping=str_mapping)

            if expire:
                await self.redis_client.expire(key, expire)

            return True

        except (RedisError, ConnectionError) as e:
            logger.error(f"Redis hash set error for key {key}: {e}")
            self.connected = False
            return False

    async def get_hash(self, key: str) -> Optional[dict]:
        """
        Get all fields from a hash

        Args:
            key: Hash key

        Returns:
            Dictionary of field-value pairs or None if not found
        """
        if not self.connected:
            return None

        try:
            result = await self.redis_client.hgetall(key)

            if not result:
                return None

            # Try to deserialize JSON values
            decoded = {}
            for k, v in result.items():
                try:
                    decoded[k] = json.loads(v)
                except json.JSONDecodeError:
                    decoded[k] = v

            return decoded

        except (RedisError, ConnectionError) as e:
            logger.error(f"Redis hash get error for key {key}: {e}")
            self.connected = False
            return None


# Global cache instance
cache_manager = CacheManager()


def cache_key(*args, **kwargs) -> str:
    """
    Generate cache key from arguments

    Args:
        *args: Positional arguments
        **kwargs: Keyword arguments

    Returns:
        Cache key string
    """
    parts = [str(arg) for arg in args]
    parts.extend([f"{k}:{v}" for k, v in sorted(kwargs.items())])
    return ":".join(parts)


def cached(
    expire: Optional[int] = None,
    key_prefix: Optional[str] = None,
    key_builder: Optional[callable] = None,
):
    """
    Decorator for caching function results

    Args:
        expire: Cache expiration time in seconds
        key_prefix: Prefix for cache key
        key_builder: Custom function to build cache key

    Example:
        @cached(expire=3600, key_prefix="user")
        async def get_user(user_id: int):
            return await db.query(User).filter(User.id == user_id).first()
    """

    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Build cache key
            if key_builder:
                cache_key_str = key_builder(*args, **kwargs)
            else:
                prefix = key_prefix or func.__name__
                cache_key_str = cache_key(prefix, *args, **kwargs)

            # Try to get from cache
            cached_value = await cache_manager.get(cache_key_str)
            if cached_value is not None:
                logger.debug(f"Cache hit for key: {cache_key_str}")
                return cached_value

            # Call original function
            result = await func(*args, **kwargs)

            # Cache the result
            await cache_manager.set(cache_key_str, result, expire)
            logger.debug(f"Cached result for key: {cache_key_str}")

            return result

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For synchronous functions, we can't use async cache
            # Just call the original function
            logger.debug(f"Sync function {func.__name__} called without caching")
            return func(*args, **kwargs)

        # Return appropriate wrapper
        import inspect

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def invalidate_cache(pattern: Optional[str] = None):
    """
    Decorator to invalidate cache after function execution

    Args:
        pattern: Cache key pattern to invalidate

    Example:
        @invalidate_cache(pattern="user:*")
        async def update_user(user_id: int, data: dict):
            # Update user in database
            pass
    """

    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)

            # Invalidate cache
            if pattern:
                deleted = await cache_manager.clear_pattern(pattern)
                logger.debug(f"Invalidated {deleted} cache keys matching pattern: {pattern}")

            return result

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            result = func(*args, **kwargs)

            # Can't invalidate cache synchronously
            logger.debug(f"Sync function {func.__name__} completed without cache invalidation")

            return result

        # Return appropriate wrapper
        import inspect

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator
