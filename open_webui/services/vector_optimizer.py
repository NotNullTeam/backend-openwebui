"""
向量检索性能优化服务

提供向量检索的性能优化功能：
1. 索引优化
2. 查询优化
3. 缓存策略
4. 批量处理
"""

import time
import logging
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np
from redis import Redis
import json

logger = logging.getLogger(__name__)

@dataclass
class SearchConfig:
    """搜索配置"""
    top_k: int = 10
    similarity_threshold: float = 0.7
    enable_cache: bool = True
    cache_ttl: int = 3600  # 1小时
    enable_rerank: bool = True
    batch_size: int = 100
    max_workers: int = 4

@dataclass
class OptimizationMetrics:
    """优化指标"""
    search_time: float
    cache_hit_rate: float
    index_size: int
    memory_usage: float
    throughput: float

class VectorIndexOptimizer:
    """向量索引优化器"""
    
    def __init__(self, redis_client: Optional[Redis] = None):
        self.redis_client = redis_client
        self.cache_prefix = "vector_search:"
        self.index_cache = {}
        self.search_stats = {
            "total_searches": 0,
            "cache_hits": 0,
            "total_time": 0.0
        }
    
    def optimize_index(self, vector_db, collection_name: str) -> Dict[str, Any]:
        """优化向量索引"""
        try:
            start_time = time.time()
            
            # 获取集合统计信息
            stats = self._get_collection_stats(vector_db, collection_name)
            
            # 优化索引参数
            optimization_params = self._calculate_optimal_params(stats)
            
            # 重建索引（如果需要）
            if optimization_params["should_rebuild"]:
                self._rebuild_index(vector_db, collection_name, optimization_params)
            
            # 预热索引
            self._warmup_index(vector_db, collection_name)
            
            optimization_time = time.time() - start_time
            
            return {
                "status": "success",
                "optimization_time": optimization_time,
                "params": optimization_params,
                "stats": stats
            }
            
        except Exception as e:
            logger.error(f"索引优化失败: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    def _get_collection_stats(self, vector_db, collection_name: str) -> Dict[str, Any]:
        """获取集合统计信息"""
        try:
            # 获取向量数量
            vector_count = vector_db.get_collection_size(collection_name)
            
            # 获取向量维度
            sample_vectors = vector_db.get_sample_vectors(collection_name, limit=10)
            vector_dim = len(sample_vectors[0]) if sample_vectors else 0
            
            # 计算数据分布
            distribution_stats = self._analyze_vector_distribution(sample_vectors)
            
            return {
                "vector_count": vector_count,
                "vector_dimension": vector_dim,
                "distribution": distribution_stats,
                "memory_usage": self._estimate_memory_usage(vector_count, vector_dim)
            }
            
        except Exception as e:
            logger.warning(f"获取集合统计信息失败: {e}")
            return {
                "vector_count": 0,
                "vector_dimension": 0,
                "distribution": {},
                "memory_usage": 0
            }
    
    def _analyze_vector_distribution(self, vectors: List[List[float]]) -> Dict[str, float]:
        """分析向量分布"""
        if not vectors:
            return {}
        
        try:
            vectors_array = np.array(vectors)
            
            return {
                "mean_norm": float(np.mean(np.linalg.norm(vectors_array, axis=1))),
                "std_norm": float(np.std(np.linalg.norm(vectors_array, axis=1))),
                "sparsity": float(np.mean(vectors_array == 0)),
                "dimension_variance": float(np.mean(np.var(vectors_array, axis=0)))
            }
            
        except Exception as e:
            logger.warning(f"向量分布分析失败: {e}")
            return {}
    
    def _calculate_optimal_params(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        """计算最优参数"""
        vector_count = stats.get("vector_count", 0)
        vector_dim = stats.get("vector_dimension", 0)
        
        # 根据数据量选择索引类型和参数
        if vector_count < 1000:
            index_type = "FLAT"
            params = {"metric": "COSINE"}
            should_rebuild = False
        elif vector_count < 10000:
            index_type = "IVF_FLAT"
            nlist = min(int(np.sqrt(vector_count)), 1024)
            params = {"metric": "COSINE", "nlist": nlist}
            should_rebuild = True
        else:
            index_type = "IVF_PQ"
            nlist = min(int(np.sqrt(vector_count)), 4096)
            m = min(vector_dim // 8, 64)  # PQ分段数
            params = {"metric": "COSINE", "nlist": nlist, "m": m}
            should_rebuild = True
        
        return {
            "index_type": index_type,
            "params": params,
            "should_rebuild": should_rebuild,
            "estimated_memory": self._estimate_index_memory(vector_count, vector_dim, index_type)
        }
    
    def _estimate_memory_usage(self, vector_count: int, vector_dim: int) -> float:
        """估算内存使用量（MB）"""
        return (vector_count * vector_dim * 4) / (1024 * 1024)  # float32
    
    def _estimate_index_memory(self, vector_count: int, vector_dim: int, index_type: str) -> float:
        """估算索引内存使用量（MB）"""
        base_memory = self._estimate_memory_usage(vector_count, vector_dim)
        
        if index_type == "FLAT":
            return base_memory
        elif index_type == "IVF_FLAT":
            return base_memory * 1.2  # 20%额外开销
        elif index_type == "IVF_PQ":
            return base_memory * 0.3  # PQ压缩后约30%
        else:
            return base_memory
    
    def _rebuild_index(self, vector_db, collection_name: str, params: Dict[str, Any]):
        """重建索引"""
        try:
            logger.info(f"开始重建索引: {collection_name}")
            
            # 这里应该调用实际的向量数据库重建索引方法
            # vector_db.rebuild_index(collection_name, params["index_type"], params["params"])
            
            logger.info(f"索引重建完成: {collection_name}")
            
        except Exception as e:
            logger.error(f"索引重建失败: {e}")
            raise
    
    def _warmup_index(self, vector_db, collection_name: str, warmup_queries: int = 100):
        """预热索引"""
        try:
            logger.info(f"开始预热索引: {collection_name}")
            
            # 生成随机查询向量进行预热
            sample_vectors = vector_db.get_sample_vectors(collection_name, limit=10)
            if sample_vectors:
                vector_dim = len(sample_vectors[0])
                
                for _ in range(warmup_queries):
                    # 生成随机查询向量
                    query_vector = np.random.normal(0, 1, vector_dim).tolist()
                    
                    # 执行搜索（不记录结果）
                    vector_db.search(collection_name, query_vector, top_k=10)
            
            logger.info(f"索引预热完成: {collection_name}")
            
        except Exception as e:
            logger.warning(f"索引预热失败: {e}")

class QueryOptimizer:
    """查询优化器"""
    
    def __init__(self, redis_client: Optional[Redis] = None):
        self.redis_client = redis_client
        self.cache_prefix = "query_cache:"
    
    def optimize_search_query(self, query_vector: List[float], config: SearchConfig) -> Dict[str, Any]:
        """优化搜索查询"""
        
        # 查询向量归一化
        normalized_vector = self._normalize_vector(query_vector)
        
        # 生成缓存键
        cache_key = self._generate_cache_key(normalized_vector, config)
        
        # 检查缓存
        if config.enable_cache and self.redis_client:
            cached_result = self._get_cached_result(cache_key)
            if cached_result:
                return {
                    "vector": normalized_vector,
                    "cache_key": cache_key,
                    "from_cache": True,
                    "cached_result": cached_result
                }
        
        return {
            "vector": normalized_vector,
            "cache_key": cache_key,
            "from_cache": False,
            "optimization": {
                "normalized": True,
                "cache_enabled": config.enable_cache
            }
        }
    
    def _normalize_vector(self, vector: List[float]) -> List[float]:
        """向量归一化"""
        try:
            vector_array = np.array(vector)
            norm = np.linalg.norm(vector_array)
            
            if norm > 0:
                normalized = vector_array / norm
                return normalized.tolist()
            else:
                return vector
                
        except Exception as e:
            logger.warning(f"向量归一化失败: {e}")
            return vector
    
    def _generate_cache_key(self, vector: List[float], config: SearchConfig) -> str:
        """生成缓存键"""
        # 创建查询特征字符串
        query_features = {
            "vector_hash": hashlib.md5(str(vector).encode()).hexdigest()[:16],
            "top_k": config.top_k,
            "threshold": config.similarity_threshold,
            "rerank": config.enable_rerank
        }
        
        cache_key = f"{self.cache_prefix}{json.dumps(query_features, sort_keys=True)}"
        return hashlib.md5(cache_key.encode()).hexdigest()
    
    def _get_cached_result(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """获取缓存结果"""
        try:
            if self.redis_client:
                cached_data = self.redis_client.get(cache_key)
                if cached_data:
                    return json.loads(cached_data)
        except Exception as e:
            logger.warning(f"获取缓存失败: {e}")
        
        return None
    
    def cache_search_result(self, cache_key: str, result: Dict[str, Any], ttl: int = 3600):
        """缓存搜索结果"""
        try:
            if self.redis_client:
                self.redis_client.setex(
                    cache_key,
                    ttl,
                    json.dumps(result, ensure_ascii=False)
                )
        except Exception as e:
            logger.warning(f"缓存结果失败: {e}")

class BatchProcessor:
    """批量处理器"""
    
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
    
    def batch_search(self, vector_db, collection_name: str, 
                    query_vectors: List[List[float]], 
                    config: SearchConfig) -> List[Dict[str, Any]]:
        """批量搜索"""
        
        results = []
        
        # 分批处理
        for i in range(0, len(query_vectors), config.batch_size):
            batch = query_vectors[i:i + config.batch_size]
            batch_results = self._process_batch(vector_db, collection_name, batch, config)
            results.extend(batch_results)
        
        return results
    
    def _process_batch(self, vector_db, collection_name: str,
                      batch_vectors: List[List[float]],
                      config: SearchConfig) -> List[Dict[str, Any]]:
        """处理单个批次"""
        
        results = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交搜索任务
            future_to_vector = {
                executor.submit(
                    vector_db.search,
                    collection_name,
                    vector,
                    config.top_k,
                    config.similarity_threshold
                ): vector
                for vector in batch_vectors
            }
            
            # 收集结果
            for future in as_completed(future_to_vector):
                vector = future_to_vector[future]
                try:
                    result = future.result()
                    results.append({
                        "query_vector": vector,
                        "results": result,
                        "status": "success"
                    })
                except Exception as e:
                    logger.error(f"批量搜索失败: {e}")
                    results.append({
                        "query_vector": vector,
                        "results": [],
                        "status": "error",
                        "error": str(e)
                    })
        
        return results

class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self):
        self.metrics = {
            "search_count": 0,
            "total_search_time": 0.0,
            "cache_hits": 0,
            "cache_misses": 0,
            "error_count": 0
        }
    
    def record_search(self, search_time: float, cache_hit: bool = False, error: bool = False):
        """记录搜索指标"""
        self.metrics["search_count"] += 1
        self.metrics["total_search_time"] += search_time
        
        if cache_hit:
            self.metrics["cache_hits"] += 1
        else:
            self.metrics["cache_misses"] += 1
        
        if error:
            self.metrics["error_count"] += 1
    
    def get_performance_metrics(self) -> OptimizationMetrics:
        """获取性能指标"""
        total_searches = self.metrics["search_count"]
        
        if total_searches > 0:
            avg_search_time = self.metrics["total_search_time"] / total_searches
            cache_hit_rate = self.metrics["cache_hits"] / total_searches
            throughput = total_searches / self.metrics["total_search_time"] if self.metrics["total_search_time"] > 0 else 0
        else:
            avg_search_time = 0
            cache_hit_rate = 0
            throughput = 0
        
        return OptimizationMetrics(
            search_time=avg_search_time,
            cache_hit_rate=cache_hit_rate,
            index_size=0,  # 需要从向量数据库获取
            memory_usage=0,  # 需要从系统获取
            throughput=throughput
        )
    
    def reset_metrics(self):
        """重置指标"""
        self.metrics = {
            "search_count": 0,
            "total_search_time": 0.0,
            "cache_hits": 0,
            "cache_misses": 0,
            "error_count": 0
        }

# 全局优化器实例
vector_optimizer = VectorIndexOptimizer()
query_optimizer = QueryOptimizer()
batch_processor = BatchProcessor()
performance_monitor = PerformanceMonitor()

def optimize_vector_search(vector_db, collection_name: str, 
                          query_vector: List[float],
                          config: SearchConfig) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """优化向量搜索"""
    
    start_time = time.time()
    
    try:
        # 优化查询
        query_optimization = query_optimizer.optimize_search_query(query_vector, config)
        
        # 检查缓存
        if query_optimization["from_cache"]:
            performance_monitor.record_search(
                time.time() - start_time, 
                cache_hit=True
            )
            return query_optimization["cached_result"], {"from_cache": True}
        
        # 执行搜索
        optimized_vector = query_optimization["vector"]
        results = vector_db.search(
            collection_name,
            optimized_vector,
            config.top_k,
            config.similarity_threshold
        )
        
        # 缓存结果
        if config.enable_cache:
            query_optimizer.cache_search_result(
                query_optimization["cache_key"],
                results,
                config.cache_ttl
            )
        
        search_time = time.time() - start_time
        performance_monitor.record_search(search_time, cache_hit=False)
        
        return results, {
            "search_time": search_time,
            "from_cache": False,
            "optimizations_applied": query_optimization["optimization"]
        }
        
    except Exception as e:
        search_time = time.time() - start_time
        performance_monitor.record_search(search_time, error=True)
        logger.error(f"向量搜索优化失败: {e}")
        raise
