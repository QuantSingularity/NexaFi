"""
Shared caching utilities for NexaFi services
"""

import hashlib
import json
from functools import wraps
from typing import Any, Optional

import redis

from ..config.infrastructure import InfrastructureConfig


class CacheManager:
    """Redis-based cache manager"""

    def __init__(self) -> None:
        self.redis_client = redis.Redis(**InfrastructureConfig.get_redis_config())
        self.default_timeout = InfrastructureConfig.CACHE_DEFAULT_TIMEOUT
        self.key_prefix = InfrastructureConfig.CACHE_KEY_PREFIX

    def _make_key(self, key: str) -> str:
        """Create a prefixed cache key"""
        return f"{self.key_prefix}{key}"

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            value = self.redis_client.get(self._make_key(key))
            if value:
                return json.loads(value)
            return None
        except Exception:
            return None

    def set(self, key: str, value: Any, timeout: Optional[int] = None) -> bool:
        """Set value in cache"""
        try:
            timeout = timeout or self.default_timeout
            serialized_value = json.dumps(value, default=str)
            return self.redis_client.setex(
                self._make_key(key), timeout, serialized_value
            )
        except Exception:
            return False

    def delete(self, key: str) -> bool:
        """Delete value from cache"""
        try:
            return bool(self.redis_client.delete(self._make_key(key)))
        except Exception:
            return False

    def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        try:
            return bool(self.redis_client.exists(self._make_key(key)))
        except Exception:
            return False

    def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching pattern"""
        try:
            keys = self.redis_client.keys(self._make_key(pattern))
            if keys:
                return self.redis_client.delete(*keys)
            return 0
        except Exception:
            return 0

    def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """Increment a counter"""
        try:
            return self.redis_client.incr(self._make_key(key), amount)
        except Exception:
            return None

    def expire(self, key: str, timeout: int) -> bool:
        """Set expiration for a key"""
        try:
            return bool(self.redis_client.expire(self._make_key(key), timeout))
        except Exception:
            return False


cache = CacheManager()


def cached(timeout: Optional[int] = None, key_func: Optional[callable] = None) -> Any:
    """Decorator for caching function results"""

    def decorator(func):

        @wraps(func)
        def wrapper(*args, **kwargs):
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                key_parts = [func.__name__]
                key_parts.extend((str(arg) for arg in args))
                key_parts.extend((f"{k}:{v}" for k, v in sorted(kwargs.items())))
                cache_key = hashlib.md5(":".join(key_parts).encode()).hexdigest()
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, timeout)
            return result

        return wrapper

    return decorator


def cache_key_for_user(user_id: str, *args, **kwargs) -> str:
    """Generate cache key for user-specific data"""
    key_parts = [str(user_id)]
    key_parts.extend((str(arg) for arg in args))
    key_parts.extend((f"{k}:{v}" for k, v in sorted(kwargs.items())))
    return hashlib.md5(":".join(key_parts).encode()).hexdigest()
