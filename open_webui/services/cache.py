"""
缓存服务
提供多级缓存策略和智能缓存管理
"""

import asyncio
import json
import hashlib
import logging
import time
from typing import Any, Optional, Union, Dict, List, Callable
from dataclasses import dataclass
from enum import Enum
from functools import wraps
import pickle

import redis
from redis.asyncio import Redis as AsyncRedis
from cachetools import TTLCache, LRUCache, LFUCache

log = logging.getLogger(__name__)


class CacheLevel(Enum):
    """缓存级别"""
    MEMORY = "memory"      # 内存缓存（最快）
    REDIS = "redis"        # Redis缓存（中等）
    DATABASE = "database"  # 数据库缓存（最慢但持久）


class CacheStrategy(Enum):
    """缓存策略"""
    LRU = "lru"  # 最近最少使用
    LFU = "lfu"  # 最少使用频率
    TTL = "ttl"  # 固定过期时间
    ADAPTIVE = "adaptive"  # 自适应策略


@dataclass
class CacheConfig:
    """缓存配置"""
    default_ttl: int = 3600  # 默认过期时间（秒）
    max_memory_items: int = 1000  # 内存缓存最大项数
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    enable_compression: bool = True  # 是否压缩大对象
    compression_threshold: int = 1024  # 压缩阈值（字节）
    enable_statistics: bool = True  # 是否统计命中率


class CacheStatistics:
    """缓存统计"""
    
    def __init__(self):
        self.hits = 0
        self.misses = 0
        self.sets = 0
        self.deletes = 0
        self.evictions = 0
        
    @property
    def hit_rate(self) -> float:
        """命中率"""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "sets": self.sets,
            "deletes": self.deletes,
            "evictions": self.evictions,
            "hit_rate": self.hit_rate
        }


class MultiLevelCache:
    """多级缓存系统"""
    
    def __init__(self, config: CacheConfig = None):
        self.config = config or CacheConfig()
        
        # 初始化内存缓存
        self._init_memory_cache()
        
        # 初始化Redis缓存
        self._init_redis_cache()
        
        # 统计信息
        self.stats = CacheStatistics()
        
    def _init_memory_cache(self):
        """初始化内存缓存"""
        self.memory_lru = LRUCache(maxsize=self.config.max_memory_items)
        self.memory_lfu = LFUCache(maxsize=self.config.max_memory_items)
        self.memory_ttl = TTLCache(
            maxsize=self.config.max_memory_items,
            ttl=self.config.default_ttl
        )
        
    def _init_redis_cache(self):
        """初始化Redis缓存"""
        try:
            self.redis_client = redis.Redis(
                host=self.config.redis_host,
                port=self.config.redis_port,
                db=self.config.redis_db,
                password=self.config.redis_password,
                decode_responses=False  # 使用二进制模式
            )
            
            self.async_redis = AsyncRedis(
                host=self.config.redis_host,
                port=self.config.redis_port,
                db=self.config.redis_db,
                password=self.config.redis_password,
                decode_responses=False
            )
            
            # 测试连接
            self.redis_client.ping()
            self.redis_enabled = True
        except Exception as e:
            log.warning(f"Redis connection failed: {e}. Using memory cache only.")
            self.redis_enabled = False
    
    def _get_cache_key(self, key: str, namespace: str = None) -> str:
        """生成缓存键"""
        if namespace:
            return f"{namespace}:{key}"
        return key
    
    def _serialize(self, value: Any) -> bytes:
        """序列化值"""
        try:
            serialized = pickle.dumps(value)
            
            # 压缩大对象
            if self.config.enable_compression and len(serialized) > self.config.compression_threshold:
                import zlib
                return b"COMPRESSED:" + zlib.compress(serialized)
            
            return serialized
        except Exception as e:
            log.error(f"Serialization failed: {e}")
            raise
    
    def _deserialize(self, data: bytes) -> Any:
        """反序列化值"""
        try:
            # 检查是否压缩
            if data.startswith(b"COMPRESSED:"):
                import zlib
                data = zlib.decompress(data[11:])
            
            return pickle.loads(data)
        except Exception as e:
            log.error(f"Deserialization failed: {e}")
            raise
    
    async def get(
        self,
        key: str,
        namespace: str = None,
        level: CacheLevel = None
    ) -> Optional[Any]:
        """获取缓存值"""
        cache_key = self._get_cache_key(key, namespace)
        
        # 1. 尝试内存缓存
        value = self._get_from_memory(cache_key)
        if value is not None:
            self.stats.hits += 1
            return value
        
        # 2. 尝试Redis缓存
        if self.redis_enabled and level != CacheLevel.MEMORY:
            value = await self._get_from_redis(cache_key)
            if value is not None:
                # 回填到内存缓存
                self._set_to_memory(cache_key, value)
                self.stats.hits += 1
                return value
        
        self.stats.misses += 1
        return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: int = None,
        namespace: str = None,
        level: CacheLevel = None
    ) -> bool:
        """设置缓存值"""
        cache_key = self._get_cache_key(key, namespace)
        ttl = ttl or self.config.default_ttl
        
        self.stats.sets += 1
        
        # 1. 设置内存缓存
        if level in [None, CacheLevel.MEMORY]:
            self._set_to_memory(cache_key, value, ttl)
        
        # 2. 设置Redis缓存
        if self.redis_enabled and level in [None, CacheLevel.REDIS]:
            success = await self._set_to_redis(cache_key, value, ttl)
            if not success:
                log.warning(f"Failed to set Redis cache for key: {cache_key}")
        
        return True
    
    async def delete(
        self,
        key: str,
        namespace: str = None,
        pattern: bool = False
    ) -> int:
        """删除缓存"""
        if pattern:
            return await self._delete_pattern(key, namespace)
        
        cache_key = self._get_cache_key(key, namespace)
        count = 0
        
        # 删除内存缓存
        if self._delete_from_memory(cache_key):
            count += 1
        
        # 删除Redis缓存
        if self.redis_enabled:
            if await self._delete_from_redis(cache_key):
                count += 1
        
        self.stats.deletes += count
        return count
    
    async def clear(self, namespace: str = None) -> int:
        """清空缓存"""
        if namespace:
            return await self._delete_pattern("*", namespace)
        
        count = 0
        
        # 清空内存缓存
        count += len(self.memory_lru)
        count += len(self.memory_lfu)
        count += len(self.memory_ttl)
        
        self.memory_lru.clear()
        self.memory_lfu.clear()
        self.memory_ttl.clear()
        
        # 清空Redis缓存
        if self.redis_enabled:
            try:
                await self.async_redis.flushdb()
            except Exception as e:
                log.error(f"Failed to clear Redis cache: {e}")
        
        return count
    
    def _get_from_memory(self, key: str) -> Optional[Any]:
        """从内存缓存获取"""
        # 依次尝试不同的缓存策略
        for cache in [self.memory_ttl, self.memory_lru, self.memory_lfu]:
            if key in cache:
                return cache[key]
        return None
    
    def _set_to_memory(self, key: str, value: Any, ttl: int = None):
        """设置内存缓存"""
        # 使用TTL缓存作为主要策略
        self.memory_ttl[key] = value
        
        # 同时更新LRU缓存
        self.memory_lru[key] = value
    
    def _delete_from_memory(self, key: str) -> bool:
        """从内存缓存删除"""
        deleted = False
        
        for cache in [self.memory_ttl, self.memory_lru, self.memory_lfu]:
            if key in cache:
                del cache[key]
                deleted = True
        
        return deleted
    
    async def _get_from_redis(self, key: str) -> Optional[Any]:
        """从Redis缓存获取"""
        try:
            data = await self.async_redis.get(key)
            if data:
                return self._deserialize(data)
        except Exception as e:
            log.error(f"Redis get failed: {e}")
        return None
    
    async def _set_to_redis(self, key: str, value: Any, ttl: int) -> bool:
        """设置Redis缓存"""
        try:
            data = self._serialize(value)
            await self.async_redis.setex(key, ttl, data)
            return True
        except Exception as e:
            log.error(f"Redis set failed: {e}")
            return False
    
    async def _delete_from_redis(self, key: str) -> bool:
        """从Redis缓存删除"""
        try:
            result = await self.async_redis.delete(key)
            return result > 0
        except Exception as e:
            log.error(f"Redis delete failed: {e}")
            return False
    
    async def _delete_pattern(self, pattern: str, namespace: str = None) -> int:
        """删除匹配模式的缓存"""
        cache_pattern = self._get_cache_key(pattern, namespace)
        count = 0
        
        # 删除内存缓存中的匹配项
        for cache in [self.memory_ttl, self.memory_lru, self.memory_lfu]:
            keys_to_delete = [
                k for k in cache.keys()
                if self._match_pattern(k, cache_pattern)
            ]
            for key in keys_to_delete:
                del cache[key]
                count += 1
        
        # 删除Redis缓存中的匹配项
        if self.redis_enabled:
            try:
                cursor = 0
                while True:
                    cursor, keys = await self.async_redis.scan(
                        cursor, match=cache_pattern, count=100
                    )
                    if keys:
                        await self.async_redis.delete(*keys)
                        count += len(keys)
                    if cursor == 0:
                        break
            except Exception as e:
                log.error(f"Redis pattern delete failed: {e}")
        
        return count
    
    def _match_pattern(self, key: str, pattern: str) -> bool:
        """匹配模式"""
        import fnmatch
        return fnmatch.fnmatch(key, pattern)
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = self.stats.to_dict()
        
        # 添加内存缓存信息
        stats["memory_cache"] = {
            "lru_size": len(self.memory_lru),
            "lfu_size": len(self.memory_lfu),
            "ttl_size": len(self.memory_ttl),
            "max_size": self.config.max_memory_items
        }
        
        # 添加Redis信息
        if self.redis_enabled:
            try:
                info = self.redis_client.info("memory")
                stats["redis_cache"] = {
                    "used_memory": info.get("used_memory_human"),
                    "connected": True
                }
            except:
                stats["redis_cache"] = {"connected": False}
        
        return stats


def cached(
    ttl: int = 3600,
    namespace: str = None,
    key_builder: Callable = None,
    level: CacheLevel = None
):
    """缓存装饰器"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # 构建缓存键
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                # 默认使用函数名和参数哈希
                key_data = {
                    "func": func.__name__,
                    "args": str(args),
                    "kwargs": str(sorted(kwargs.items()))
                }
                cache_key = hashlib.md5(
                    json.dumps(key_data).encode()
                ).hexdigest()
            
            # 尝试从缓存获取
            cached_value = await cache.get(cache_key, namespace, level)
            if cached_value is not None:
                return cached_value
            
            # 执行函数
            result = await func(*args, **kwargs)
            
            # 设置缓存
            await cache.set(cache_key, result, ttl, namespace, level)
            
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # 同步版本的包装器
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(
                    async_wrapper(*args, **kwargs)
                )
            finally:
                loop.close()
        
        # 根据函数类型返回相应的包装器
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


class SmartCache:
    """智能缓存（自动调整策略）"""
    
    def __init__(self, base_cache: MultiLevelCache):
        self.cache = base_cache
        self.access_patterns = {}  # 访问模式记录
        self.performance_metrics = {}  # 性能指标
        
    async def adaptive_get(self, key: str, namespace: str = None) -> Optional[Any]:
        """自适应获取（根据访问模式调整策略）"""
        # 记录访问模式
        self._record_access(key)
        
        # 根据访问频率决定缓存级别
        access_count = self.access_patterns.get(key, {}).get("count", 0)
        
        if access_count > 100:  # 高频访问，使用内存缓存
            level = CacheLevel.MEMORY
        elif access_count > 10:  # 中频访问，使用Redis
            level = CacheLevel.REDIS
        else:  # 低频访问，可能不缓存或使用数据库
            level = None
        
        return await self.cache.get(key, namespace, level)
    
    async def adaptive_set(
        self,
        key: str,
        value: Any,
        namespace: str = None
    ) -> bool:
        """自适应设置（根据数据特征调整TTL）"""
        # 分析数据特征
        data_size = len(self.cache._serialize(value))
        
        # 根据数据大小调整TTL
        if data_size < 1024:  # 小数据，长TTL
            ttl = 7200
        elif data_size < 10240:  # 中等数据
            ttl = 3600
        else:  # 大数据，短TTL
            ttl = 1800
        
        # 根据访问模式调整缓存级别
        access_count = self.access_patterns.get(key, {}).get("count", 0)
        
        if access_count > 50:
            level = CacheLevel.MEMORY
        else:
            level = CacheLevel.REDIS
        
        return await self.cache.set(key, value, ttl, namespace, level)
    
    def _record_access(self, key: str):
        """记录访问模式"""
        if key not in self.access_patterns:
            self.access_patterns[key] = {
                "count": 0,
                "last_access": time.time(),
                "access_times": []
            }
        
        pattern = self.access_patterns[key]
        pattern["count"] += 1
        pattern["last_access"] = time.time()
        pattern["access_times"].append(time.time())
        
        # 只保留最近100次访问时间
        if len(pattern["access_times"]) > 100:
            pattern["access_times"] = pattern["access_times"][-100:]
    
    def analyze_patterns(self) -> Dict[str, Any]:
        """分析访问模式"""
        analysis = {
            "hot_keys": [],  # 热点键
            "cold_keys": [],  # 冷键
            "burst_keys": []  # 突发访问键
        }
        
        current_time = time.time()
        
        for key, pattern in self.access_patterns.items():
            # 热点键：高频访问
            if pattern["count"] > 100:
                analysis["hot_keys"].append({
                    "key": key,
                    "count": pattern["count"]
                })
            
            # 冷键：长时间未访问
            if current_time - pattern["last_access"] > 3600:
                analysis["cold_keys"].append({
                    "key": key,
                    "last_access": pattern["last_access"]
                })
            
            # 突发访问：短时间内大量访问
            if len(pattern["access_times"]) >= 10:
                recent_times = pattern["access_times"][-10:]
                time_span = recent_times[-1] - recent_times[0]
                if time_span < 60:  # 1分钟内10次访问
                    analysis["burst_keys"].append({
                        "key": key,
                        "rate": 10 / time_span
                    })
        
        return analysis


# 全局缓存实例
cache = MultiLevelCache()
smart_cache = SmartCache(cache)
