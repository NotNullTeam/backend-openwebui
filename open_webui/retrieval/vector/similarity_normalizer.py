"""
向量相似度归一化工具

统一不同向量数据库的相似度分数，确保一致的排序和阈值处理。
"""

import logging
from typing import List, Dict, Any, Optional
from enum import Enum

log = logging.getLogger(__name__)


class VectorDBType(Enum):
    """支持的向量数据库类型"""
    WEAVIATE = "weaviate"
    CHROMA = "chroma"
    QDRANT = "qdrant"
    MILVUS = "milvus"
    PINECONE = "pinecone"
    PGVECTOR = "pgvector"
    ELASTICSEARCH = "elasticsearch"
    OPENSEARCH = "opensearch"


class SimilarityNormalizer:
    """相似度分数归一化器"""
    
    def __init__(self):
        # 不同向量数据库的分数特性
        self.score_characteristics = {
            VectorDBType.WEAVIATE: {
                "type": "distance",  # 距离，越小越相似
                "range": (0, float('inf')),
                "optimal": "min"
            },
            VectorDBType.CHROMA: {
                "type": "distance", 
                "range": (0, 2),  # 余弦距离范围
                "optimal": "min"
            },
            VectorDBType.QDRANT: {
                "type": "similarity",  # 相似度，越大越相似
                "range": (-1, 1),  # 余弦相似度范围
                "optimal": "max"
            },
            VectorDBType.MILVUS: {
                "type": "distance",
                "range": (0, float('inf')),
                "optimal": "min"
            },
            VectorDBType.PINECONE: {
                "type": "similarity",
                "range": (-1, 1),
                "optimal": "max"
            },
            VectorDBType.PGVECTOR: {
                "type": "distance",
                "range": (0, 2),
                "optimal": "min"
            },
            VectorDBType.ELASTICSEARCH: {
                "type": "similarity",
                "range": (0, 1),
                "optimal": "max"
            },
            VectorDBType.OPENSEARCH: {
                "type": "similarity", 
                "range": (0, 1),
                "optimal": "max"
            }
        }
    
    def normalize_scores(
        self, 
        scores: List[float], 
        db_type: VectorDBType,
        target_range: tuple = (0, 1)
    ) -> List[float]:
        """
        将向量数据库的原始分数归一化到目标范围
        
        Args:
            scores: 原始分数列表
            db_type: 向量数据库类型
            target_range: 目标分数范围，默认(0,1)，1表示最相似
            
        Returns:
            归一化后的分数列表，越大表示越相似
        """
        if not scores:
            return []
            
        characteristics = self.score_characteristics.get(db_type)
        if not characteristics:
            log.warning(f"Unknown vector DB type: {db_type}, using raw scores")
            return scores
            
        normalized = []
        min_target, max_target = target_range
        
        for score in scores:
            if score is None:
                normalized.append(0.0)
                continue
                
            # 根据数据库类型进行归一化
            if characteristics["type"] == "distance":
                # 距离类型：越小越相似，需要转换
                if db_type == VectorDBType.WEAVIATE:
                    # Weaviate距离可能很大，使用倒数映射
                    norm_score = 1.0 / (1.0 + float(score))
                elif db_type in [VectorDBType.CHROMA, VectorDBType.PGVECTOR]:
                    # 余弦距离范围[0,2]，转换为相似度[1,0]
                    norm_score = max(0, 1.0 - float(score) / 2.0)
                else:
                    # 其他距离类型，使用通用倒数映射
                    norm_score = 1.0 / (1.0 + float(score))
            else:
                # 相似度类型：越大越相似
                if db_type == VectorDBType.QDRANT:
                    # 余弦相似度[-1,1] -> [0,1]
                    norm_score = (float(score) + 1.0) / 2.0
                elif db_type == VectorDBType.PINECONE:
                    # 余弦相似度[-1,1] -> [0,1]
                    norm_score = (float(score) + 1.0) / 2.0
                else:
                    # 已经是[0,1]范围的相似度
                    norm_score = float(score)
            
            # 映射到目标范围
            final_score = min_target + norm_score * (max_target - min_target)
            normalized.append(max(min_target, min(max_target, final_score)))
            
        return normalized
    
    def normalize_search_results(
        self, 
        results: List[Dict[str, Any]], 
        db_type: VectorDBType,
        score_key: str = "distance"
    ) -> List[Dict[str, Any]]:
        """
        归一化搜索结果中的分数
        
        Args:
            results: 搜索结果列表
            db_type: 向量数据库类型
            score_key: 分数字段名称
            
        Returns:
            归一化后的搜索结果
        """
        if not results:
            return results
            
        # 提取原始分数
        raw_scores = [r.get(score_key, 0.0) for r in results]
        
        # 归一化分数
        normalized_scores = self.normalize_scores(raw_scores, db_type)
        
        # 更新结果
        normalized_results = []
        for i, result in enumerate(results):
            updated_result = result.copy()
            updated_result["score"] = normalized_scores[i]
            # 保留原始分数用于调试
            updated_result[f"raw_{score_key}"] = raw_scores[i]
            normalized_results.append(updated_result)
            
        # 按归一化分数降序排序
        normalized_results.sort(key=lambda x: x.get("score", 0), reverse=True)
        
        return normalized_results
    
    def get_similarity_threshold(self, db_type: VectorDBType, quality: str = "medium") -> float:
        """
        获取不同质量级别的相似度阈值
        
        Args:
            db_type: 向量数据库类型
            quality: 质量级别 ("high", "medium", "low")
            
        Returns:
            归一化后的相似度阈值
        """
        # 基础阈值定义（归一化后的值）
        thresholds = {
            "high": 0.8,    # 高质量匹配
            "medium": 0.6,  # 中等质量匹配
            "low": 0.4      # 低质量匹配
        }
        
        return thresholds.get(quality, 0.6)
    
    def filter_by_threshold(
        self, 
        results: List[Dict[str, Any]], 
        threshold: float,
        score_key: str = "score"
    ) -> List[Dict[str, Any]]:
        """
        根据阈值过滤搜索结果
        
        Args:
            results: 搜索结果列表
            threshold: 相似度阈值
            score_key: 分数字段名称
            
        Returns:
            过滤后的结果
        """
        return [r for r in results if r.get(score_key, 0) >= threshold]


def get_db_type_from_config(vector_db_config: str) -> VectorDBType:
    """从配置字符串获取数据库类型"""
    config_lower = vector_db_config.lower()
    
    type_mapping = {
        "weaviate": VectorDBType.WEAVIATE,
        "chroma": VectorDBType.CHROMA,
        "qdrant": VectorDBType.QDRANT,
        "milvus": VectorDBType.MILVUS,
        "pinecone": VectorDBType.PINECONE,
        "pgvector": VectorDBType.PGVECTOR,
        "elasticsearch": VectorDBType.ELASTICSEARCH,
        "opensearch": VectorDBType.OPENSEARCH,
    }
    
    for key, db_type in type_mapping.items():
        if key in config_lower:
            return db_type
    
    log.warning(f"Unknown vector DB config: {vector_db_config}, defaulting to Weaviate")
    return VectorDBType.WEAVIATE


# 全局归一化器实例
similarity_normalizer = SimilarityNormalizer()
