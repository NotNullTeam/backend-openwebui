"""
性能优化服务

提供缓存管理、连接池优化、查询优化等性能提升功能
"""

import asyncio
import time
import hashlib
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from functools import wraps
import logging

from open_webui.internal.db import get_db
from open_webui.retrieval.vector.main import get_retrieval_vector_db

logger = logging.getLogger(__name__)

class CacheManager:
    """缓存管理器"""
    
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.access_times: Dict[str, datetime] = {}
        self.hit_count = 0
        self.miss_count = 0
    
    def _generate_key(self, prefix: str, **kwargs) -> str:
        """生成缓存键"""
        key_data = json.dumps(kwargs, sort_keys=True)
        key_hash = hashlib.md5(key_data.encode()).hexdigest()
        return f"{prefix}:{key_hash}"
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        if key not in self.cache:
            self.miss_count += 1
            return None
        
        cache_entry = self.cache[key]
        
        # 检查是否过期
        if datetime.now() > cache_entry['expires_at']:
            del self.cache[key]
            del self.access_times[key]
            self.miss_count += 1
            return None
        
        # 更新访问时间
        self.access_times[key] = datetime.now()
        self.hit_count += 1
        return cache_entry['value']
    
    def set(self, key: str, value: Any) -> None:
        """设置缓存值"""
        # 如果缓存已满，删除最久未访问的条目
        if len(self.cache) >= self.max_size:
            self._evict_lru()
        
        expires_at = datetime.now() + timedelta(seconds=self.ttl_seconds)
        self.cache[key] = {
            'value': value,
            'expires_at': expires_at,
            'created_at': datetime.now()
        }
        self.access_times[key] = datetime.now()
    
    def _evict_lru(self) -> None:
        """删除最久未访问的条目"""
        if not self.access_times:
            return
        
        lru_key = min(self.access_times.keys(), key=lambda k: self.access_times[k])
        del self.cache[lru_key]
        del self.access_times[lru_key]
    
    def clear(self) -> None:
        """清空缓存"""
        self.cache.clear()
        self.access_times.clear()
        self.hit_count = 0
        self.miss_count = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        total_requests = self.hit_count + self.miss_count
        hit_rate = (self.hit_count / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'size': len(self.cache),
            'max_size': self.max_size,
            'hit_count': self.hit_count,
            'miss_count': self.miss_count,
            'hit_rate': round(hit_rate, 2),
            'ttl_seconds': self.ttl_seconds
        }

class ConnectionPool:
    """数据库连接池管理"""
    
    def __init__(self, max_connections: int = 20):
        self.max_connections = max_connections
        self.active_connections = 0
        self.connection_queue = asyncio.Queue()
        self.stats = {
            'total_created': 0,
            'total_closed': 0,
            'current_active': 0,
            'peak_usage': 0,
            'queue_wait_times': []
        }
    
    async def get_connection(self):
        """获取数据库连接"""
        start_time = time.time()
        
        if self.active_connections < self.max_connections:
            self.active_connections += 1
            self.stats['total_created'] += 1
            self.stats['current_active'] = self.active_connections
            self.stats['peak_usage'] = max(self.stats['peak_usage'], self.active_connections)
            
            # 返回数据库会话
            return get_db()
        else:
            # 等待可用连接
            await self.connection_queue.get()
            wait_time = time.time() - start_time
            self.stats['queue_wait_times'].append(wait_time)
            return get_db()
    
    def release_connection(self):
        """释放数据库连接"""
        if self.active_connections > 0:
            self.active_connections -= 1
            self.stats['total_closed'] += 1
            self.stats['current_active'] = self.active_connections
            
            # 通知等待队列
            try:
                self.connection_queue.put_nowait(None)
            except asyncio.QueueFull:
                pass
    
    def get_stats(self) -> Dict[str, Any]:
        """获取连接池统计"""
        avg_wait_time = (
            sum(self.stats['queue_wait_times']) / len(self.stats['queue_wait_times'])
            if self.stats['queue_wait_times'] else 0
        )
        
        return {
            'max_connections': self.max_connections,
            'current_active': self.stats['current_active'],
            'peak_usage': self.stats['peak_usage'],
            'total_created': self.stats['total_created'],
            'total_closed': self.stats['total_closed'],
            'avg_queue_wait_time': round(avg_wait_time, 3),
            'utilization_rate': round((self.stats['current_active'] / self.max_connections) * 100, 2)
        }

class QueryOptimizer:
    """查询优化器"""
    
    def __init__(self):
        self.query_stats: Dict[str, Dict[str, Any]] = {}
        self.slow_query_threshold = 1.0  # 秒
    
    def record_query(self, query_type: str, execution_time: float, result_count: int = 0):
        """记录查询统计"""
        if query_type not in self.query_stats:
            self.query_stats[query_type] = {
                'count': 0,
                'total_time': 0,
                'min_time': float('inf'),
                'max_time': 0,
                'slow_queries': 0,
                'total_results': 0
            }
        
        stats = self.query_stats[query_type]
        stats['count'] += 1
        stats['total_time'] += execution_time
        stats['min_time'] = min(stats['min_time'], execution_time)
        stats['max_time'] = max(stats['max_time'], execution_time)
        stats['total_results'] += result_count
        
        if execution_time > self.slow_query_threshold:
            stats['slow_queries'] += 1
            logger.warning(f"慢查询检测: {query_type} 耗时 {execution_time:.3f}s")
    
    def get_query_stats(self) -> Dict[str, Any]:
        """获取查询统计"""
        optimized_stats = {}
        
        for query_type, stats in self.query_stats.items():
            avg_time = stats['total_time'] / stats['count'] if stats['count'] > 0 else 0
            avg_results = stats['total_results'] / stats['count'] if stats['count'] > 0 else 0
            slow_query_rate = (stats['slow_queries'] / stats['count'] * 100) if stats['count'] > 0 else 0
            
            optimized_stats[query_type] = {
                'total_queries': stats['count'],
                'avg_execution_time': round(avg_time, 3),
                'min_execution_time': round(stats['min_time'], 3) if stats['min_time'] != float('inf') else 0,
                'max_execution_time': round(stats['max_time'], 3),
                'slow_query_count': stats['slow_queries'],
                'slow_query_rate': round(slow_query_rate, 2),
                'avg_result_count': round(avg_results, 1)
            }
        
        return optimized_stats
    
    def get_optimization_suggestions(self) -> List[str]:
        """获取优化建议"""
        suggestions = []
        
        for query_type, stats in self.query_stats.items():
            if stats['count'] == 0:
                continue
            
            avg_time = stats['total_time'] / stats['count']
            slow_rate = (stats['slow_queries'] / stats['count']) * 100
            
            if slow_rate > 10:
                suggestions.append(f"{query_type}: 慢查询比例过高({slow_rate:.1f}%)，建议优化索引或查询逻辑")
            
            if avg_time > 2.0:
                suggestions.append(f"{query_type}: 平均执行时间过长({avg_time:.3f}s)，建议添加缓存或优化查询")
            
            if stats['count'] > 1000 and avg_time > 0.5:
                suggestions.append(f"{query_type}: 高频查询且耗时较长，建议实现查询结果缓存")
        
        if not suggestions:
            suggestions.append("查询性能良好，暂无优化建议")
        
        return suggestions

def cache_result(cache_manager: CacheManager, prefix: str, ttl: Optional[int] = None):
    """缓存装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 生成缓存键
            cache_key = cache_manager._generate_key(prefix, args=args, kwargs=kwargs)
            
            # 尝试从缓存获取
            cached_result = cache_manager.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # 执行函数并缓存结果
            result = await func(*args, **kwargs)
            
            # 设置缓存
            if ttl:
                original_ttl = cache_manager.ttl_seconds
                cache_manager.ttl_seconds = ttl
                cache_manager.set(cache_key, result)
                cache_manager.ttl_seconds = original_ttl
            else:
                cache_manager.set(cache_key, result)
            
            return result
        return wrapper
    return decorator

def measure_query_time(optimizer: QueryOptimizer, query_type: str):
    """查询时间测量装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            result = await func(*args, **kwargs)
            execution_time = time.time() - start_time
            
            # 记录查询统计
            result_count = len(result) if isinstance(result, (list, tuple)) else 1
            optimizer.record_query(query_type, execution_time, result_count)
            
            return result
        return wrapper
    return decorator

class PerformanceService:
    """性能服务"""
    
    def __init__(self):
        self.cache_manager = CacheManager(max_size=2000, ttl_seconds=1800)  # 30分钟TTL
        self.connection_pool = ConnectionPool(max_connections=25)
        self.query_optimizer = QueryOptimizer()
        self.vector_cache = CacheManager(max_size=500, ttl_seconds=900)  # 向量搜索缓存15分钟
        
        # 性能指标
        self.performance_metrics = {
            'api_response_times': [],
            'vector_search_times': [],
            'db_query_times': [],
            'cache_operations': 0,
            'optimization_applied': 0
        }
    
    async def optimize_vector_search(self, query: str, limit: int = 10, filters: Dict = None) -> List[Dict]:
        """优化向量搜索"""
        # 使用缓存
        cache_key = self.vector_cache._generate_key("vector_search", query=query, limit=limit, filters=filters)
        cached_result = self.vector_cache.get(cache_key)
        
        if cached_result:
            return cached_result
        
        # 执行搜索
        start_time = time.time()
        vector_db = get_retrieval_vector_db()
        
        if not vector_db:
            return []
        
        try:
            results = vector_db.search(query=query, limit=limit, filters=filters or {})
            search_time = time.time() - start_time
            
            # 记录性能指标
            self.performance_metrics['vector_search_times'].append(search_time)
            self.query_optimizer.record_query("vector_search", search_time, len(results))
            
            # 缓存结果
            self.vector_cache.set(cache_key, results)
            self.performance_metrics['cache_operations'] += 1
            
            return results
            
        except Exception as e:
            logger.error(f"向量搜索优化失败: {e}")
            return []
    
    async def batch_vector_search(self, queries: List[str], limit: int = 10) -> Dict[str, List[Dict]]:
        """批量向量搜索优化"""
        results = {}
        
        # 检查缓存
        uncached_queries = []
        for query in queries:
            cache_key = self.vector_cache._generate_key("vector_search", query=query, limit=limit)
            cached_result = self.vector_cache.get(cache_key)
            
            if cached_result:
                results[query] = cached_result
            else:
                uncached_queries.append(query)
        
        # 批量执行未缓存的查询
        if uncached_queries:
            vector_db = get_retrieval_vector_db()
            if vector_db:
                start_time = time.time()
                
                # 并发执行搜索
                tasks = []
                for query in uncached_queries:
                    task = asyncio.create_task(self._single_vector_search(vector_db, query, limit))
                    tasks.append((query, task))
                
                # 等待所有任务完成
                for query, task in tasks:
                    try:
                        search_results = await task
                        results[query] = search_results
                        
                        # 缓存结果
                        cache_key = self.vector_cache._generate_key("vector_search", query=query, limit=limit)
                        self.vector_cache.set(cache_key, search_results)
                        
                    except Exception as e:
                        logger.error(f"批量搜索失败 {query}: {e}")
                        results[query] = []
                
                total_time = time.time() - start_time
                self.query_optimizer.record_query("batch_vector_search", total_time, len(uncached_queries))
        
        return results
    
    async def _single_vector_search(self, vector_db, query: str, limit: int) -> List[Dict]:
        """单个向量搜索"""
        try:
            return vector_db.search(query=query, limit=limit)
        except Exception as e:
            logger.error(f"向量搜索失败: {e}")
            return []
    
    def record_api_response_time(self, endpoint: str, response_time: float):
        """记录API响应时间"""
        self.performance_metrics['api_response_times'].append({
            'endpoint': endpoint,
            'time': response_time,
            'timestamp': datetime.now()
        })
        
        # 保留最近1000条记录
        if len(self.performance_metrics['api_response_times']) > 1000:
            self.performance_metrics['api_response_times'] = self.performance_metrics['api_response_times'][-1000:]
    
    def get_performance_report(self) -> Dict[str, Any]:
        """获取性能报告"""
        # 计算API响应时间统计
        api_times = [r['time'] for r in self.performance_metrics['api_response_times']]
        api_stats = {
            'count': len(api_times),
            'avg_time': sum(api_times) / len(api_times) if api_times else 0,
            'min_time': min(api_times) if api_times else 0,
            'max_time': max(api_times) if api_times else 0
        }
        
        # 计算向量搜索时间统计
        vector_times = self.performance_metrics['vector_search_times']
        vector_stats = {
            'count': len(vector_times),
            'avg_time': sum(vector_times) / len(vector_times) if vector_times else 0,
            'min_time': min(vector_times) if vector_times else 0,
            'max_time': max(vector_times) if vector_times else 0
        }
        
        return {
            'timestamp': datetime.now().isoformat(),
            'cache_performance': {
                'main_cache': self.cache_manager.get_stats(),
                'vector_cache': self.vector_cache.get_stats()
            },
            'connection_pool': self.connection_pool.get_stats(),
            'query_performance': self.query_optimizer.get_query_stats(),
            'api_performance': api_stats,
            'vector_search_performance': vector_stats,
            'optimization_suggestions': self.query_optimizer.get_optimization_suggestions(),
            'total_cache_operations': self.performance_metrics['cache_operations'],
            'optimizations_applied': self.performance_metrics['optimization_applied']
        }
    
    async def cleanup_caches(self):
        """清理缓存"""
        self.cache_manager.clear()
        self.vector_cache.clear()
        logger.info("缓存已清理")
    
    async def warm_up_caches(self, common_queries: List[str]):
        """预热缓存"""
        logger.info(f"开始预热缓存，查询数量: {len(common_queries)}")
        
        for query in common_queries:
            try:
                await self.optimize_vector_search(query, limit=5)
            except Exception as e:
                logger.error(f"缓存预热失败 {query}: {e}")
        
        logger.info("缓存预热完成")

# 全局性能服务实例
performance_service = PerformanceService()
