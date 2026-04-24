"""
Enterprise Caching System for NexaFi
Multi-tier, high-performance caching with intelligent cache management
"""

import hashlib
import json
import logging
import pickle
import threading
import time
import zlib
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

import redis
import structlog
from sqlalchemy import Column, DateTime, Float, Integer, String, create_engine
from sqlalchemy.orm import declarative_base

# ── Optional serialisation / compression libs with stdlib fallbacks ──────────
try:
    import cbor2 as _cbor2
except ImportError:
    import json as _cbor2  # type: ignore[no-redef]

try:
    import lz4.frame as _lz4
except ImportError:

    class _lz4:  # type: ignore[no-redef]
        @staticmethod
        def compress(data: bytes, **k) -> bytes:
            return data

        @staticmethod
        def decompress(data: bytes, **k) -> bytes:
            return data


try:
    import msgpack as _msgpack  # type: ignore[assignment]
except ImportError:
    import json as _msgpack  # type: ignore[no-redef]

try:
    import orjson as _orjson  # type: ignore[assignment]
except ImportError:
    import json as _orjson  # type: ignore[no-redef]

try:
    import zstandard as zstd

    _zstd_compress = zstd.ZstdCompressor().compress
    _zstd_decompress = zstd.ZstdDecompressor().decompress
except ImportError:

    def _zstd_compress(data: bytes, **k) -> bytes:
        return data  # type: ignore[misc]

    def _zstd_decompress(data: bytes, **k) -> bytes:
        return data  # type: ignore[misc]


try:
    from cachetools import LFUCache, LRUCache, TTLCache
except ImportError:

    class TTLCache(dict):  # type: ignore[no-redef]
        def __init__(self, maxsize=128, ttl=600):
            super().__init__()

    class LRUCache(dict):  # type: ignore[no-redef]
        def __init__(self, maxsize=128):
            super().__init__()

    class LFUCache(dict):  # type: ignore[no-redef]
        def __init__(self, maxsize=128):
            super().__init__()


try:
    from consistent_hash import ConsistentHash as _ConsistentHashLib
except ImportError:

    class _ConsistentHashLib:  # type: ignore[no-redef]
        """Pure-Python consistent hashing ring using MD5."""

        def __init__(self, replicas: int = 100) -> None:
            self._replicas = replicas
            self._ring: dict = {}
            self._sorted_keys: list = []

        def add_node(self, node: str) -> None:
            import hashlib

            for i in range(self._replicas):
                key = int(hashlib.md5(f"{node}:{i}".encode()).hexdigest(), 16)
                self._ring[key] = node
            self._sorted_keys = sorted(self._ring.keys())

        def remove_node(self, node: str) -> None:
            import hashlib

            for i in range(self._replicas):
                key = int(hashlib.md5(f"{node}:{i}".encode()).hexdigest(), 16)
                self._ring.pop(key, None)
            self._sorted_keys = sorted(self._ring.keys())

        def get_node(self, request: str) -> Optional[str]:
            if not self._ring:
                return None
            import hashlib

            h = int(hashlib.md5(request.encode()).hexdigest(), 16)
            for k in self._sorted_keys:
                if h <= k:
                    return self._ring[k]
            return self._ring[self._sorted_keys[0]]


ConsistentHash = _ConsistentHashLib

try:
    from prometheus_client import Counter, Histogram
except ImportError:

    class Counter:  # type: ignore[no-redef]
        def __init__(self, *a, **k):
            pass

        def inc(self, *a, **k):
            pass

        def labels(self, **k):
            return self

    class Histogram:  # type: ignore[no-redef]
        def __init__(self, *a, **k):
            pass

        def observe(self, *a, **k):
            pass

        def labels(self, **k):
            return self

        def time(self):
            import contextlib

            return contextlib.nullcontext()


try:
    from pybloom_live import BloomFilter
except ImportError:

    class BloomFilter:  # type: ignore[no-redef]
        def __init__(self, capacity=100, error_rate=0.001):
            self._s: set = set()

        def add(self, item) -> None:
            self._s.add(item)

        def __contains__(self, item) -> bool:
            return item in self._s


try:
    from pymemcache.client.hash import HashClient as MemcacheHashClient
except ImportError:

    class MemcacheHashClient:  # type: ignore[no-redef]
        def __init__(self, *a, **k):
            pass

        def get(self, k):
            return None

        def set(self, k, v, expire=0):
            return True

        def delete(self, k):
            return True


from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)
Base = declarative_base()


class CacheLevel(Enum):
    """Cache tier levels"""

    L1_MEMORY = 1
    L2_REDIS = 2
    L3_MEMCACHED = 3
    L4_DISTRIBUTED = 4
    L5_PERSISTENT = 5


class CacheStrategy(Enum):
    """Cache eviction strategies"""

    LRU = "lru"
    LFU = "lfu"
    TTL = "ttl"
    FIFO = "fifo"
    RANDOM = "random"
    ADAPTIVE = "adaptive"


class CompressionType(Enum):
    """Compression algorithms"""

    NONE = "none"
    ZLIB = "zlib"
    LZ4 = "lz4"
    ZSTD = "zstd"
    GZIP = "gzip"


class SerializationType(Enum):
    """Serialization formats"""

    PICKLE = "pickle"
    JSON = "json"
    MSGPACK = "msgpack"
    CBOR = "cbor"
    ORJSON = "orjson"


@dataclass
class CacheEntry:
    """Cache entry with metadata"""

    key: str
    value: object
    created_at: datetime
    last_accessed: datetime
    access_count: int
    ttl_seconds: Optional[int]
    size_bytes: int
    compression: CompressionType
    serialization: SerializationType
    tags: List[str]
    metadata: Dict[str, Any]


@dataclass
class CacheStats:
    """Cache statistics"""

    hits: int
    misses: int
    evictions: int
    size_bytes: int
    entry_count: int
    hit_ratio: float
    avg_access_time: float
    memory_usage: float


class CacheMetrics(Base):
    """Cache metrics model"""

    __tablename__ = "cache_metrics"
    id = Column(Integer, primary_key=True)
    cache_name = Column(String(100), nullable=False, index=True)
    level = Column(String(20), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    hits = Column(Integer, default=0)
    misses = Column(Integer, default=0)
    evictions = Column(Integer, default=0)
    size_bytes = Column(Integer, default=0)
    entry_count = Column(Integer, default=0)
    hit_ratio = Column(Float, default=0.0)
    avg_access_time = Column(Float, default=0.0)
    memory_usage = Column(Float, default=0.0)
    cpu_usage = Column(Float, default=0.0)
    network_io = Column(Float, default=0.0)


class CacheConfiguration:
    """Cache configuration management"""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        self.logger = structlog.get_logger(__name__)

    def get_cache_config(self, cache_name: str) -> Dict[str, Any]:
        """Get configuration for specific cache"""
        default_config = {
            "max_size_mb": 1024,
            "ttl_seconds": 3600,
            "compression": CompressionType.LZ4,
            "serialization": SerializationType.MSGPACK,
            "strategy": CacheStrategy.LRU,
            "levels": [CacheLevel.L1_MEMORY, CacheLevel.L2_REDIS],
            "replication_factor": 2,
            "consistency_level": "eventual",
            "enable_bloom_filter": True,
            "bloom_filter_size": 1000000,
            "bloom_filter_error_rate": 0.01,
        }
        cache_config = self.config.get("caches", {}).get(cache_name, {})
        for key, value in default_config.items():
            if key not in cache_config:
                cache_config[key] = value
        return cache_config


class CompressionManager:
    """Handles data compression and decompression"""

    @staticmethod
    def compress(data: bytes, compression_type: CompressionType) -> bytes:
        """Compress data using specified algorithm"""
        if compression_type == CompressionType.NONE:
            return data
        elif compression_type == CompressionType.ZLIB:
            return zlib.compress(data)
        elif compression_type == CompressionType.LZ4:
            return lz4.frame.compress(data)
        elif compression_type == CompressionType.ZSTD:
            cctx = zstd.ZstdCompressor()
            return cctx.compress(data)
        elif compression_type == CompressionType.GZIP:
            import gzip

            return gzip.compress(data)
        else:
            raise ValueError(f"Unsupported compression type: {compression_type}")

    @staticmethod
    def decompress(data: bytes, compression_type: CompressionType) -> bytes:
        """Decompress data using specified algorithm"""
        if compression_type == CompressionType.NONE:
            return data
        elif compression_type == CompressionType.ZLIB:
            return zlib.decompress(data)
        elif compression_type == CompressionType.LZ4:
            return lz4.frame.decompress(data)
        elif compression_type == CompressionType.ZSTD:
            dctx = zstd.ZstdDecompressor()
            return dctx.decompress(data)
        elif compression_type == CompressionType.GZIP:
            import gzip

            return gzip.decompress(data)
        else:
            raise ValueError(f"Unsupported compression type: {compression_type}")


class SerializationManager:
    """Handles data serialization and deserialization"""

    @staticmethod
    def serialize(data: object, serialization_type: SerializationType) -> bytes:
        """Serialize data using specified format"""
        if serialization_type == SerializationType.PICKLE:
            return pickle.dumps(data)
        elif serialization_type == SerializationType.JSON:
            return json.dumps(data).encode("utf-8")
        elif serialization_type == SerializationType.MSGPACK:
            return msgpack.packb(data, use_bin_type=True)
        elif serialization_type == SerializationType.CBOR:
            return cbor2.dumps(data)
        elif serialization_type == SerializationType.ORJSON:
            return orjson.dumps(data)
        else:
            raise ValueError(f"Unsupported serialization type: {serialization_type}")

    @staticmethod
    def deserialize(data: bytes, serialization_type: SerializationType) -> object:
        """Deserialize data using specified format"""
        if serialization_type == SerializationType.PICKLE:
            return pickle.loads(data)
        elif serialization_type == SerializationType.JSON:
            return json.loads(data.decode("utf-8"))
        elif serialization_type == SerializationType.MSGPACK:
            return msgpack.unpackb(data, raw=False)
        elif serialization_type == SerializationType.CBOR:
            return cbor2.loads(data)
        elif serialization_type == SerializationType.ORJSON:
            return orjson.loads(data)
        else:
            raise ValueError(f"Unsupported serialization type: {serialization_type}")


class L1MemoryCache:
    """Level 1 in-process memory cache"""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        self.logger = structlog.get_logger(__name__)
        max_size = config.get("max_size_mb", 256) * 1024 * 1024
        strategy = config.get("strategy", CacheStrategy.LRU)
        if strategy == CacheStrategy.LRU:
            self.cache = LRUCache(maxsize=max_size)
        elif strategy == CacheStrategy.LFU:
            self.cache = LFUCache(maxsize=max_size)
        elif strategy == CacheStrategy.TTL:
            ttl = config.get("ttl_seconds", 3600)
            self.cache = TTLCache(maxsize=max_size, ttl=ttl)
        else:
            self.cache = LRUCache(maxsize=max_size)
        self.stats = CacheStats(0, 0, 0, 0, 0, 0.0, 0.0, 0.0)
        self.lock = threading.RLock()

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        start_time = time.time()
        with self.lock:
            try:
                value = self.cache[key]
                self.stats.hits += 1
                access_time = time.time() - start_time
                self.stats.avg_access_time = (
                    self.stats.avg_access_time * (self.stats.hits - 1) + access_time
                ) / self.stats.hits
                return value
            except KeyError:
                self.stats.misses += 1
                return None

    def set(self, key: str, value: object, ttl: Optional[int] = None) -> bool:
        """Set value in cache"""
        with self.lock:
            try:
                size = len(pickle.dumps(value))
                if len(self.cache) >= self.cache.maxsize:
                    self.stats.evictions += 1
                self.cache[key] = value
                self.stats.entry_count = len(self.cache)
                self.stats.size_bytes += size
                return True
            except Exception as e:
                self.logger.error(f"L1 cache set failed: {str(e)}")
                return False

    def delete(self, key: str) -> bool:
        """Delete value from cache"""
        with self.lock:
            try:
                if key in self.cache:
                    del self.cache[key]
                    self.stats.entry_count = len(self.cache)
                    return True
                return False
            except Exception as e:
                self.logger.error(f"L1 cache delete failed: {str(e)}")
                return False

    def clear(self) -> None:
        """Clear all cache entries"""
        with self.lock:
            self.cache.clear()
            self.stats = CacheStats(0, 0, 0, 0, 0, 0.0, 0.0, 0.0)

    def get_stats(self) -> CacheStats:
        """Get cache statistics"""
        with self.lock:
            total_requests = self.stats.hits + self.stats.misses
            self.stats.hit_ratio = (
                self.stats.hits / total_requests if total_requests > 0 else 0.0
            )
            return self.stats


class L2RedisCache:
    """Level 2 Redis cache"""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        self.logger = structlog.get_logger(__name__)
        redis_config = config.get("redis", {})
        if redis_config.get("sentinel_enabled", False):
            sentinel_hosts = redis_config.get("sentinel_hosts", [("localhost", 26379)])
            service_name = redis_config.get("service_name", "mymaster")
            sentinel = redis.sentinel.Sentinel(sentinel_hosts)
            self.redis_client = sentinel.master_for(
                service_name, decode_responses=False
            )
        else:
            self.redis_client = redis.from_url(
                redis_config.get("url", "redis://localhost:6379/0"),
                decode_responses=False,
                connection_pool_kwargs={"max_connections": 50},
            )
        self.compression = config.get("compression", CompressionType.LZ4)
        self.serialization = config.get("serialization", SerializationType.MSGPACK)
        self.default_ttl = config.get("ttl_seconds", 3600)
        self.bloom_capacity = config.get("bloom_filter_size", 1000000)
        self.bloom_error_rate = config.get("bloom_filter_error_rate", 0.01)
        if config.get("enable_bloom_filter", True):
            self.bloom_filter = BloomFilter(
                capacity=self.bloom_capacity, error_rate=self.bloom_error_rate
            )
        else:
            self.bloom_filter = None
        self.stats = CacheStats(0, 0, 0, 0, 0, 0.0, 0.0, 0.0)
        self.lock = threading.RLock()

    def get(self, key: str) -> Optional[Any]:
        """Get value from Redis cache"""
        start_time = time.time()
        try:
            if self.bloom_filter and key not in self.bloom_filter:
                self.stats.misses += 1
                return None
            data = self.redis_client.get(key)
            if data is None:
                self.stats.misses += 1
                return None
            decompressed_data = CompressionManager.decompress(data, self.compression)
            value = SerializationManager.deserialize(
                decompressed_data, self.serialization
            )
            self.stats.hits += 1
            access_time = time.time() - start_time
            with self.lock:
                self.stats.avg_access_time = (
                    self.stats.avg_access_time * (self.stats.hits - 1) + access_time
                ) / self.stats.hits
            return value
        except Exception as e:
            self.logger.error(f"L2 cache get failed: {str(e)}")
            self.stats.misses += 1
            return None

    def set(self, key: str, value: object, ttl: Optional[int] = None) -> bool:
        """Set value in Redis cache"""
        try:
            serialized_data = SerializationManager.serialize(value, self.serialization)
            compressed_data = CompressionManager.compress(
                serialized_data, self.compression
            )
            ttl = ttl or self.default_ttl
            result = self.redis_client.setex(key, ttl, compressed_data)
            if self.bloom_filter:
                self.bloom_filter.add(key)
            with self.lock:
                self.stats.entry_count += 1
                self.stats.size_bytes += len(compressed_data)
            return bool(result)
        except Exception as e:
            self.logger.error(f"L2 cache set failed: {str(e)}")
            return False

    def delete(self, key: str) -> bool:
        """Delete value from Redis cache"""
        try:
            result = self.redis_client.delete(key)
            with self.lock:
                if result:
                    self.stats.entry_count -= 1
            return bool(result)
        except Exception as e:
            self.logger.error(f"L2 cache delete failed: {str(e)}")
            return False

    def clear(self) -> None:
        """Clear all cache entries"""
        try:
            self.redis_client.flushdb()
            with self.lock:
                self.stats = CacheStats(0, 0, 0, 0, 0, 0.0, 0.0, 0.0)
            if self.bloom_filter:
                self.bloom_filter = BloomFilter(
                    capacity=self.bloom_capacity, error_rate=self.bloom_error_rate
                )
        except Exception as e:
            self.logger.error(f"L2 cache clear failed: {str(e)}")

    def get_stats(self) -> CacheStats:
        """Get cache statistics"""
        with self.lock:
            total_requests = self.stats.hits + self.stats.misses
            self.stats.hit_ratio = (
                self.stats.hits / total_requests if total_requests > 0 else 0.0
            )
            return self.stats


class L3MemcachedCache:
    """Level 3 Memcached cache"""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        self.logger = structlog.get_logger(__name__)
        memcached_config = config.get("memcached", {})
        server_strings = memcached_config.get("servers", ["localhost:11211"])
        parsed_servers = []
        for server in server_strings:
            host, port = server.rsplit(":", 1)
            parsed_servers.append((host, int(port)))
        self.memcached_client = MemcacheHashClient(
            parsed_servers, serializer=self._serialize, deserializer=self._deserialize
        )
        self.compression = config.get("compression", CompressionType.LZ4)
        self.serialization = config.get("serialization", SerializationType.MSGPACK)
        self.default_ttl = config.get("ttl_seconds", 3600)
        self.stats = CacheStats(0, 0, 0, 0, 0, 0.0, 0.0, 0.0)
        self.lock = threading.RLock()

    def _serialize(self, key: str, value: object):
        """Custom serializer for Memcached"""
        serialized_data = SerializationManager.serialize(value, self.serialization)
        return CompressionManager.compress(serialized_data, self.compression), 0

    def _deserialize(self, key: str, data: bytes, flags: int) -> object:
        """Custom deserializer for Memcached"""
        decompressed_data = CompressionManager.decompress(data, self.compression)
        return SerializationManager.deserialize(decompressed_data, self.serialization)

    def get(self, key: str) -> Optional[Any]:
        """Get value from Memcached cache"""
        start_time = time.time()
        try:
            value = self.memcached_client.get(key)
            if value is None:
                self.stats.misses += 1
                return None
            self.stats.hits += 1
            access_time = time.time() - start_time
            with self.lock:
                self.stats.avg_access_time = (
                    self.stats.avg_access_time * (self.stats.hits - 1) + access_time
                ) / self.stats.hits
            return value
        except Exception as e:
            self.logger.error(f"L3 cache get failed: {str(e)}")
            self.stats.misses += 1
            return None

    def set(self, key: str, value: object, ttl: Optional[int] = None) -> bool:
        """Set value in Memcached cache"""
        try:
            ttl = ttl or self.default_ttl
            result = self.memcached_client.set(key, value, expire=ttl)
            with self.lock:
                if result:
                    self.stats.entry_count += 1
            return bool(result)
        except Exception as e:
            self.logger.error(f"L3 cache set failed: {str(e)}")
            return False

    def delete(self, key: str) -> bool:
        """Delete value from Memcached cache"""
        try:
            result = self.memcached_client.delete(key)
            with self.lock:
                if result:
                    self.stats.entry_count -= 1
            return bool(result)
        except Exception as e:
            self.logger.error(f"L3 cache delete failed: {str(e)}")
            return False

    def get_stats(self) -> CacheStats:
        """Get cache statistics"""
        with self.lock:
            total_requests = self.stats.hits + self.stats.misses
            self.stats.hit_ratio = (
                self.stats.hits / total_requests if total_requests > 0 else 0.0
            )
            return self.stats


class MultiTierCache:
    """Multi-tier cache system"""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        self.logger = structlog.get_logger(__name__)
        self.caches = {}
        levels = config.get("levels", [CacheLevel.L1_MEMORY, CacheLevel.L2_REDIS])
        if CacheLevel.L1_MEMORY in levels:
            self.caches[CacheLevel.L1_MEMORY] = L1MemoryCache(
                config.get("l1_config", {})
            )
        if CacheLevel.L2_REDIS in levels:
            self.caches[CacheLevel.L2_REDIS] = L2RedisCache(config.get("l2_config", {}))
        if CacheLevel.L3_MEMCACHED in levels:
            self.caches[CacheLevel.L3_MEMCACHED] = L3MemcachedCache(
                config.get("l3_config", {})
            )
        self.promotion_threshold = config.get("promotion_threshold", 3)
        self.access_counts = defaultdict(int)
        self.cache_hits = Counter("cache_hits_total", "Total cache hits", ["level"])
        self.cache_misses = Counter(
            "cache_misses_total", "Total cache misses", ["level"]
        )
        self.cache_operations = Histogram(
            "cache_operation_duration_seconds",
            "Cache operation duration",
            ["operation", "level"],
        )

    def get(self, key: str) -> Optional[Any]:
        """Get value from multi-tier cache"""
        time.time()
        for level in sorted(self.caches.keys(), key=lambda x: x.value):
            cache = self.caches[level]
            with self.cache_operations.labels(operation="get", level=level.name).time():
                value = cache.get(key)
            if value is not None:
                self.cache_hits.labels(level=level.name).inc()
                self.access_counts[key] += 1
                self._promote_to_higher_levels(key, value, level)
                return value
            else:
                self.cache_misses.labels(level=level.name).inc()
        return None

    def set(self, key: str, value: object, ttl: Optional[int] = None) -> bool:
        """Set value in multi-tier cache"""
        success = True
        for level, cache in self.caches.items():
            with self.cache_operations.labels(operation="set", level=level.name).time():
                result = cache.set(key, value, ttl)
                success = success and result
        return success

    def delete(self, key: str) -> bool:
        """Delete value from all cache levels"""
        success = True
        for level, cache in self.caches.items():
            with self.cache_operations.labels(
                operation="delete", level=level.name
            ).time():
                result = cache.delete(key)
                success = success and result
        if key in self.access_counts:
            del self.access_counts[key]
        return success

    def _promote_to_higher_levels(
        self, key: str, value: object, current_level: CacheLevel
    ) -> None:
        """Promote frequently accessed items to higher cache levels"""
        access_count = self.access_counts[key]
        if access_count >= self.promotion_threshold:
            for level in sorted(self.caches.keys(), key=lambda x: x.value):
                if level.value < current_level.value:
                    cache = self.caches[level]
                    cache.set(key, value)

    def get_stats(self) -> Dict[str, CacheStats]:
        """Get statistics for all cache levels"""
        stats: Dict[str, Any] = {}
        for level, cache in self.caches.items():
            stats[level.name] = cache.get_stats()
        return stats

    def clear_all(self) -> None:
        """Clear all cache levels"""
        for cache in self.caches.values():
            cache.clear()
        self.access_counts.clear()


class CacheManager:
    """Central cache management system"""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        self.logger = structlog.get_logger(__name__)
        self.config_manager = CacheConfiguration(config)
        self.caches = {}
        db_url = config.get("database_url", "sqlite:///cache_metrics.db")
        self.db_engine = create_engine(db_url)
        self.Session = sessionmaker(bind=self.db_engine)
        Base.metadata.create_all(bind=self.db_engine)
        self.is_running = False
        self.metrics_thread = None
        self.consistent_hash = ConsistentHash()

    def get_cache(self, cache_name: str) -> MultiTierCache:
        """Get or create cache instance"""
        if cache_name not in self.caches:
            cache_config = self.config_manager.get_cache_config(cache_name)
            self.caches[cache_name] = MultiTierCache(cache_config)
            self.logger.info(f"Created cache: {cache_name}")
        return self.caches[cache_name]

    def get(self, cache_name: str, key: str) -> Optional[Any]:
        """Get value from specified cache"""
        cache = self.get_cache(cache_name)
        return cache.get(key)

    def set(
        self, cache_name: str, key: str, value: object, ttl: Optional[int] = None
    ) -> bool:
        """Set value in specified cache"""
        cache = self.get_cache(cache_name)
        return cache.set(key, value, ttl)

    def delete(self, cache_name: str, key: str) -> bool:
        """Delete value from specified cache"""
        cache = self.get_cache(cache_name)
        return cache.delete(key)

    def invalidate_by_tags(self, cache_name: str, tags: List[str]) -> None:
        """Invalidate cache entries by tags"""
        self.get_cache(cache_name)
        self.logger.info(f"Tag-based invalidation requested for {cache_name}: {tags}")

    def warm_cache(
        self, cache_name: str, data_loader: Callable[[str], Any], keys: List[str]
    ) -> None:
        """Warm cache with data"""
        cache = self.get_cache(cache_name)

        def load_and_cache(key):
            try:
                value = data_loader(key)
                if value is not None:
                    cache.set(key, value)
                    return True
                return False
            except Exception as e:
                self.logger.error(f"Cache warming failed for key {key}: {str(e)}")
                return False

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(load_and_cache, key) for key in keys]
            successful = sum(1 for future in futures if future.result())
        self.logger.info(
            f"Cache warming completed: {successful}/{len(keys)} keys loaded"
        )

    def get_global_stats(self) -> Dict[str, Any]:
        """Get global cache statistics"""
        global_stats = {
            "total_caches": len(self.caches),
            "cache_stats": {},
            "memory_usage": 0,
            "total_hits": 0,
            "total_misses": 0,
            "global_hit_ratio": 0.0,
        }
        for cache_name, cache in self.caches.items():
            stats = cache.get_stats()
            global_stats["cache_stats"][cache_name] = stats
            for level_stats in stats.values():
                global_stats["total_hits"] += level_stats.hits
                global_stats["total_misses"] += level_stats.misses
                global_stats["memory_usage"] += level_stats.size_bytes
        total_requests = global_stats["total_hits"] + global_stats["total_misses"]
        if total_requests > 0:
            global_stats["global_hit_ratio"] = (
                global_stats["total_hits"] / total_requests
            )
        return global_stats

    def start_metrics_collection(self) -> None:
        """Start background metrics collection"""
        if self.is_running:
            return
        self.is_running = True

        def collect_metrics():
            while self.is_running:
                try:
                    self._collect_and_store_metrics()
                    time.sleep(60)
                except Exception as e:
                    self.logger.error(f"Metrics collection failed: {str(e)}")
                    time.sleep(10)

        self.metrics_thread = threading.Thread(target=collect_metrics, daemon=True)
        self.metrics_thread.start()
        self.logger.info("Started metrics collection")

    def stop_metrics_collection(self) -> None:
        """Stop background metrics collection"""
        self.is_running = False
        if self.metrics_thread:
            self.metrics_thread.join()
        self.logger.info("Stopped metrics collection")

    def _collect_and_store_metrics(self) -> None:
        """Collect and store cache metrics"""
        session = self.Session()
        try:
            for cache_name, cache in self.caches.items():
                stats = cache.get_stats()
                for level_name, level_stats in stats.items():
                    metric = CacheMetrics(
                        cache_name=cache_name,
                        level=level_name,
                        hits=level_stats.hits,
                        misses=level_stats.misses,
                        evictions=level_stats.evictions,
                        size_bytes=level_stats.size_bytes,
                        entry_count=level_stats.entry_count,
                        hit_ratio=level_stats.hit_ratio,
                        avg_access_time=level_stats.avg_access_time,
                        memory_usage=level_stats.memory_usage,
                    )
                    session.add(metric)
            session.commit()
        except Exception as e:
            self.logger.error(f"Metrics storage failed: {str(e)}")
            session.rollback()
        finally:
            session.close()


def cached(
    cache_name: str = "default", ttl: int = 3600, key_func: Optional[Callable] = None
) -> object:
    """Decorator for caching function results"""

    def decorator(func):

        @wraps(func)
        def wrapper(*args, **kwargs):
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                key_parts = [func.__name__]
                key_parts.extend((str(arg) for arg in args))
                key_parts.extend((f"{k}={v}" for k, v in sorted(kwargs.items())))
                cache_key = hashlib.md5(":".join(key_parts).encode()).hexdigest()
            cache_manager = get_global_cache_manager()
            cached_result = cache_manager.get(cache_name, cache_key)
            if cached_result is not None:
                return cached_result
            result = func(*args, **kwargs)
            cache_manager.set(cache_name, cache_key, result, ttl)
            return result

        return wrapper

    return decorator


def cache_invalidate(
    cache_name: str = "default", key_func: Optional[Callable] = None
) -> object:
    """Decorator for invalidating cache entries"""

    def decorator(func):

        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                key_parts = [func.__name__]
                key_parts.extend((str(arg) for arg in args))
                key_parts.extend((f"{k}={v}" for k, v in sorted(kwargs.items())))
                cache_key = hashlib.md5(":".join(key_parts).encode()).hexdigest()
            cache_manager = get_global_cache_manager()
            cache_manager.delete(cache_name, cache_key)
            return result

        return wrapper

    return decorator


_global_cache_manager = None


def get_global_cache_manager() -> CacheManager:
    """Get global cache manager instance"""
    global _global_cache_manager
    if _global_cache_manager is None:
        config = {
            "caches": {
                "default": {
                    "levels": [CacheLevel.L1_MEMORY, CacheLevel.L2_REDIS],
                    "l1_config": {"max_size_mb": 256},
                    "l2_config": {"redis": {"url": "redis://localhost:6379/0"}},
                }
            }
        }
        _global_cache_manager = CacheManager(config)
    return _global_cache_manager


def create_cache_manager(config: Dict[str, Any]) -> CacheManager:
    """Factory function to create cache manager"""
    return CacheManager(config)


if __name__ == "__main__":
    import structlog

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    config = {
        "database_url": "sqlite:///cache_metrics.db",
        "caches": {
            "user_data": {
                "levels": [CacheLevel.L1_MEMORY, CacheLevel.L2_REDIS],
                "max_size_mb": 512,
                "ttl_seconds": 1800,
                "l1_config": {"max_size_mb": 128},
                "l2_config": {
                    "redis": {"url": "redis://localhost:6379/0"},
                    "compression": CompressionType.LZ4,
                    "serialization": SerializationType.MSGPACK,
                },
            },
            "financial_data": {
                "levels": [
                    CacheLevel.L1_MEMORY,
                    CacheLevel.L2_REDIS,
                    CacheLevel.L3_MEMCACHED,
                ],
                "max_size_mb": 1024,
                "ttl_seconds": 3600,
                "l1_config": {"max_size_mb": 256},
                "l2_config": {"redis": {"url": "redis://localhost:6379/1"}},
                "l3_config": {"memcached": {"servers": ["localhost:11211"]}},
            },
        },
    }
    cache_manager = create_cache_manager(config)
    cache_manager.start_metrics_collection()
    cache_manager.set("user_data", "user:123", {"name": "John Doe", "balance": 1000.0})
    user_data = cache_manager.get("user_data", "user:123")
    logger.info(f"User data: {user_data}")

    @cached(cache_name="financial_data", ttl=1800)
    def get_stock_price(symbol: str) -> float:
        time.sleep(0.1)
        return 150.25

    price1 = get_stock_price("AAPL")
    logger.info(f"Stock price (first call): {price1}")
    price2 = get_stock_price("AAPL")
    logger.info(f"Stock price (cached): {price2}")
    stats = cache_manager.get_global_stats()
    logger.info(f"Cache Statistics: {json.dumps(stats, indent=2, default=str)}")
    cache_manager.stop_metrics_collection()
