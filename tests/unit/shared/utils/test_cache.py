import hashlib
import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from NexaFi.backend.shared.config.infrastructure import InfrastructureConfig
from NexaFi.backend.shared.utils.cache import CacheManager, cache_key_for_user, cached


@pytest.fixture
def mock_redis_client() -> Any:
    with patch("redis.Redis") as mock_redis:
        mock_instance = MagicMock()
        mock_redis.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def cache_manager(mock_redis_client: Any) -> Any:
    with patch.object(InfrastructureConfig, "REDIS_HOST", "localhost"), patch.object(
        InfrastructureConfig, "REDIS_PORT", 6379
    ), patch.object(InfrastructureConfig, "REDIS_DB", 0), patch.object(
        InfrastructureConfig, "REDIS_PASSWORD", None
    ), patch.object(
        InfrastructureConfig, "CACHE_DEFAULT_TIMEOUT", 300
    ), patch.object(
        InfrastructureConfig, "CACHE_KEY_PREFIX", "nexafi:"
    ):
        yield CacheManager()


class TestCacheManager:

    def test_get_existing_key(self, cache_manager: Any, mock_redis_client: Any) -> Any:
        mock_redis_client.get.return_value = json.dumps({"data": "test_value"}).encode(
            "utf-8"
        )
        result = cache_manager.get("test_key")
        assert result == {"data": "test_value"}
        mock_redis_client.get.assert_called_once_with("nexafi:test_key")

    def test_get_non_existing_key(
        self, cache_manager: Any, mock_redis_client: Any
    ) -> Any:
        mock_redis_client.get.return_value = None
        result = cache_manager.get("non_existent_key")
        assert result is None

    def test_set_key(self, cache_manager: Any, mock_redis_client: Any) -> Any:
        cache_manager.set("test_key", {"data": "new_value"}, timeout=60)
        mock_redis_client.setex.assert_called_once_with(
            "nexafi:test_key",
            60,
            json.dumps({"data": "new_value"}, default=str).encode("utf-8"),
        )

    def test_set_key_default_timeout(
        self, cache_manager: Any, mock_redis_client: Any
    ) -> Any:
        cache_manager.set("test_key", {"data": "new_value"})
        mock_redis_client.setex.assert_called_once_with(
            "nexafi:test_key",
            300,
            json.dumps({"data": "new_value"}, default=str).encode("utf-8"),
        )

    def test_delete_key(self, cache_manager: Any, mock_redis_client: Any) -> Any:
        mock_redis_client.delete.return_value = 1
        result = cache_manager.delete("test_key")
        assert result is True
        mock_redis_client.delete.assert_called_once_with("nexafi:test_key")

    def test_exists_key(self, cache_manager: Any, mock_redis_client: Any) -> Any:
        mock_redis_client.exists.return_value = 1
        result = cache_manager.exists("test_key")
        assert result is True
        mock_redis_client.exists.assert_called_once_with("nexafi:test_key")

    def test_clear_pattern(self, cache_manager: Any, mock_redis_client: Any) -> Any:
        mock_redis_client.keys.return_value = [b"nexafi:key1", b"nexafi:key2"]
        mock_redis_client.delete.return_value = 2
        result = cache_manager.clear_pattern("key*")
        assert result == 2
        mock_redis_client.keys.assert_called_once_with("nexafi:key*")
        mock_redis_client.delete.assert_called_once_with(b"nexafi:key1", b"nexafi:key2")

    def test_increment(self, cache_manager: Any, mock_redis_client: Any) -> Any:
        mock_redis_client.incr.return_value = 10
        result = cache_manager.increment("counter_key", 5)
        assert result == 10
        mock_redis_client.incr.assert_called_once_with("nexafi:counter_key", 5)

    def test_expire(self, cache_manager: Any, mock_redis_client: Any) -> Any:
        mock_redis_client.expire.return_value = 1
        result = cache_manager.expire("test_key", 3600)
        assert result is True
        mock_redis_client.expire.assert_called_once_with("nexafi:test_key", 3600)


class TestCachedDecorator:

    @patch("NexaFi.backend.shared.utils.cache.cache")
    def test_cached_decorator_no_key_func(
        self, mock_cache: Any, cache_manager: Any
    ) -> Any:
        mock_cache.get.return_value = None
        mock_cache.set.return_value = True

        @cached(timeout=100)
        def test_func(a, b):
            return a + b

        result = test_func(1, 2)
        assert result == 3
        key_parts = ["test_func", "1", "2"]
        expected_cache_key = hashlib.md5(":".join(key_parts).encode()).hexdigest()
        mock_cache.get.assert_called_once_with(expected_cache_key)
        mock_cache.set.assert_called_once_with(expected_cache_key, 3, 100)

    @patch("NexaFi.backend.shared.utils.cache.cache")
    def test_cached_decorator_with_key_func(
        self, mock_cache: Any, cache_manager: Any
    ) -> Any:
        mock_cache.get.return_value = None
        mock_cache.set.return_value = True

        def custom_key_func(x, y):
            return f"custom_key_{x}_{y}"

        @cached(timeout=100, key_func=custom_key_func)
        def test_func_with_key_func(x, y):
            return x * y

        result = test_func_with_key_func(3, 4)
        assert result == 12
        mock_cache.get.assert_called_once_with("custom_key_3_4")
        mock_cache.set.assert_called_once_with("custom_key_3_4", 12, 100)

    @patch("NexaFi.backend.shared.utils.cache.cache")
    def test_cached_decorator_returns_cached_value(
        self, mock_cache: Any, cache_manager: Any
    ) -> Any:
        mock_cache.get.return_value = "cached_result"

        @cached()
        def test_func_cached():
            return "original_result"

        result = test_func_cached()
        assert result == "cached_result"
        mock_cache.get.assert_called_once()
        mock_cache.set.assert_not_called()


class TestCacheKeyForUser:

    def test_cache_key_for_user_generation(self) -> Any:
        user_id = "user123"
        arg1 = "data1"
        kwarg1 = "value1"
        kwarg2 = "value2"
        sorted_kwargs = sorted(
            [(k, v) for k, v in {"kwarg2": kwarg2, "kwarg1": kwarg1}.items()]
        )
        expected_key_parts_sorted = [user_id, arg1]
        expected_key_parts_sorted.extend((f"{k}:{v}" for k, v in sorted_kwargs))
        expected_cache_key_sorted = hashlib.md5(
            ":".join(expected_key_parts_sorted).encode()
        ).hexdigest()
        generated_key = cache_key_for_user(user_id, arg1, kwarg2=kwarg2, kwarg1=kwarg1)
        assert generated_key == expected_cache_key_sorted
