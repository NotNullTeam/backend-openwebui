"""
混合检索服务 - 从原后端完整迁移

实现混合检索算法，结合向量检索、关键词检索和重排序机制。
支持多种向量数据库和相似度归一化。
"""

import re
import math
import logging
from typing import List, Dict, Any, Optional, Union
from collections import Counter
from dataclasses import dataclass
import jieba
from jieba import analyse

from open_webui.retrieval.vector.factory import VECTOR_DB_CLIENT
from open_webui.retrieval.vector.similarity_normalizer import SimilarityNormalizer, VectorDBType
from open_webui.config import RAG_EMBEDDING_ENGINE, RAG_EMBEDDING_MODEL

logger = logging.getLogger(__name__)

@dataclass
class SearchResult:
    """搜索结果数据结构"""
    content: str
    title: str
    score: float
    source_type: str  # 'vector', 'keyword', 'hybrid'
    document_id: str
    chunk_id: str
    metadata: Dict[str, Any]
    relevance_explanation: str = ""

class HybridRetrievalService:
    """混合检索算法实现类"""

    def __init__(self,
                 vector_weight: float = 0.7,
                 keyword_weight: float = 0.3,
                 rerank_top_k: int = 50,
                 final_top_k: int = 10):
        """
        初始化混合检索器

        Args:
            vector_weight: 向量检索权重
            keyword_weight: 关键词检索权重
            rerank_top_k: 重排序候选数量
            final_top_k: 最终返回结果数量
        """
        self.vector_weight = vector_weight
        self.keyword_weight = keyword_weight
        self.rerank_top_k = rerank_top_k
        self.final_top_k = final_top_k

        # 初始化相似度归一化工具
        self.similarity_normalizer = SimilarityNormalizer()

        logger.info(f"混合检索器初始化完成: vector_weight={vector_weight}, keyword_weight={keyword_weight}")

    def search(self,
               query: str,
               collection_name: str = "knowledge",
               filters: Optional[Dict[str, Any]] = None,
               boost_params: Optional[Dict[str, float]] = None) -> List[SearchResult]:
        """
        执行混合检索

        Args:
            query: 用户查询
            collection_name: 集合名称
            filters: 过滤条件 {'vendor': '华为', 'category': '路由协议'}
            boost_params: 权重调整参数 {'title_boost': 1.5, 'recent_boost': 1.2}

        Returns:
            List[SearchResult]: 排序后的搜索结果
        """
        try:
            logger.info(f"开始混合检索: query='{query}', filters={filters}")

            # 第一阶段：并行执行向量检索和关键词检索
            vector_results = self._vector_search(query, collection_name, filters)
            keyword_results = self._keyword_search(query, collection_name, filters)

            logger.info(f"向量检索返回 {len(vector_results)} 个结果")
            logger.info(f"关键词检索返回 {len(keyword_results)} 个结果")

            # 第二阶段：结果融合
            fused_results = self._fuse_results(vector_results, keyword_results, query)

            # 第三阶段：重排序
            reranked_results = self._rerank_results(fused_results, query, boost_params)

            # 返回最终结果
            final_results = reranked_results[:self.final_top_k]

            logger.info(f"混合检索完成，返回 {len(final_results)} 个结果")
            return final_results

        except Exception as e:
            logger.error(f"混合检索失败: {str(e)}")
            # 降级到纯向量检索
            return self._fallback_vector_search(query, collection_name, filters)

    def _vector_search(self, query: str, collection_name: str, filters: Optional[Dict[str, Any]] = None) -> List[SearchResult]:
        """执行向量检索"""
        try:
            # 使用Open WebUI的向量数据库客户端进行检索
            results = VECTOR_DB_CLIENT.search(
                collection_name=collection_name,
                query=query,
                limit=self.rerank_top_k,
                filter=filters
            )

            # 获取向量数据库类型并归一化分数
            db_type = self._get_db_type()
            if results:
                scores = [result.get('score', 0) for result in results]
                normalized_scores = self.similarity_normalizer.normalize_scores(scores, db_type)
                
                for i, result in enumerate(results):
                    result['normalized_score'] = normalized_scores[i]

            search_results = []
            for result in results:
                search_result = SearchResult(
                    content=result.get('content', ''),
                    title=result.get('title', ''),
                    score=result.get('normalized_score', result.get('score', 0.0)),
                    source_type='vector',
                    document_id=result.get('document_id', result.get('file_id', '')),
                    chunk_id=result.get('chunk_id', result.get('id', '')),
                    metadata=result.get('metadata', {}),
                    relevance_explanation="基于向量语义相似度匹配"
                )
                search_results.append(search_result)

            return search_results

        except Exception as e:
            logger.warning(f"向量检索失败: {str(e)}")
            return []

    def _keyword_search(self, query: str, collection_name: str, filters: Optional[Dict[str, Any]] = None) -> List[SearchResult]:
        """执行关键词检索"""
        try:
            # 提取查询关键词
            keywords = self._extract_keywords(query)
            if not keywords:
                return []

            logger.info(f"提取的关键词: {keywords}")

            # 获取候选文档（使用向量检索获取候选集）
            candidates = self._get_keyword_candidates(keywords, collection_name, filters)

            # 计算TF-IDF分数
            scored_results = []
            for candidate in candidates:
                score = self._calculate_keyword_score(keywords, candidate)
                if score > 0:
                    search_result = SearchResult(
                        content=candidate.get('content', ''),
                        title=candidate.get('title', ''),
                        score=score,
                        source_type='keyword',
                        document_id=candidate.get('document_id', candidate.get('file_id', '')),
                        chunk_id=candidate.get('chunk_id', candidate.get('id', '')),
                        metadata=candidate.get('metadata', {}),
                        relevance_explanation=f"关键词匹配: {', '.join(keywords)}"
                    )
                    scored_results.append(search_result)

            # 按分数排序
            scored_results.sort(key=lambda x: x.score, reverse=True)
            return scored_results[:self.rerank_top_k]

        except Exception as e:
            logger.warning(f"关键词检索失败: {str(e)}")
            return []

    def _extract_keywords(self, query: str) -> List[str]:
        """提取查询关键词"""
        try:
            # 使用jieba提取关键词
            keywords = analyse.extract_tags(query, topK=10, withWeight=False)

            # 添加技术术语和缩写
            tech_terms = self._extract_tech_terms(query)
            keywords.extend(tech_terms)

            # 去重并过滤
            keywords = list(set(keywords))
            keywords = [kw for kw in keywords if len(kw) > 1]  # 过滤单字符

            return keywords

        except Exception as e:
            logger.warning(f"关键词提取失败: {str(e)}")
            # 降级到简单分词
            return query.split()

    def _extract_tech_terms(self, query: str) -> List[str]:
        """提取技术术语和缩写"""
        tech_patterns = [
            r'(?:OSPF|BGP|RIP|ISIS|EIGRP)',  # 路由协议
            r'(?:VLAN|STP|TRUNK|ACCESS)',    # 交换技术
            r'(?:ACL|VPN|IPSEC|GRE)',        # 安全协议
            r'(?:QoS|DSCP|COS)',             # QoS
            r'(?:MPLS|LDP|RSVP-TE)',         # MPLS
            r'(?:IP|TCP|UDP|ICMP)',          # 网络协议
            r'(?:华为|思科|华三|Cisco|Huawei|H3C)'  # 厂商
        ]

        terms = []
        for pattern in tech_patterns:
            matches = re.findall(pattern, query, re.IGNORECASE)
            terms.extend([match.upper() if match.isupper() or match.isalpha() else match for match in matches])

        return list(set(terms))  # 去重

    def _get_keyword_candidates(self, keywords: List[str], collection_name: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """获取关键词检索候选结果"""
        try:
            # 使用向量服务获取候选文档
            # 这里使用一个宽泛的查询来获取候选集
            candidates = VECTOR_DB_CLIENT.search(
                collection_name=collection_name,
                query=' '.join(keywords),
                limit=100,  # 获取更多候选
                filter=filters
            )

            return candidates

        except Exception as e:
            logger.warning(f"获取关键词候选失败: {str(e)}")
            return []

    def _calculate_keyword_score(self, keywords: List[str], document: Dict[str, Any]) -> float:
        """计算关键词匹配分数"""
        content = document.get('content', '').lower()
        title = document.get('title', '').lower()

        if not content:
            return 0.0

        total_score = 0.0

        for keyword in keywords:
            keyword_lower = keyword.lower()

            # 计算在内容中的TF
            content_tf = content.count(keyword_lower)
            title_tf = title.count(keyword_lower)

            # 标题匹配给予更高权重
            keyword_score = content_tf + (title_tf * 2.0)

            # 技术术语匹配给予额外权重
            if self._is_tech_term(keyword):
                keyword_score *= 1.5

            total_score += keyword_score

        # 归一化分数
        content_length = len(content.split())
        if content_length > 0:
            total_score = total_score / math.sqrt(content_length)

        return total_score

    def _is_tech_term(self, term: str) -> bool:
        """判断是否为技术术语"""
        tech_terms = {
            'ospf', 'bgp', 'rip', 'isis', 'eigrp',
            'vlan', 'stp', 'trunk', 'access',
            'acl', 'vpn', 'ipsec', 'gre',
            'qos', 'dscp', 'cos',
            'mpls', 'ldp', 'rsvp-te',
            'ip', 'tcp', 'udp', 'icmp',
            '华为', '思科', '华三', 'cisco', 'huawei', 'h3c'
        }
        return term.lower() in tech_terms

    def _fuse_results(self, vector_results: List[SearchResult],
                     keyword_results: List[SearchResult],
                     query: str) -> List[SearchResult]:
        """融合向量检索和关键词检索结果"""
        # 创建结果字典，以chunk_id为键
        result_dict = {}

        # 处理向量检索结果
        for result in vector_results:
            key = f"{result.document_id}_{result.chunk_id}"
            if key not in result_dict:
                result_dict[key] = result
                result_dict[key].score *= self.vector_weight
            else:
                # 如果已存在，更新向量分数
                result_dict[key].score += result.score * self.vector_weight

        # 处理关键词检索结果
        for result in keyword_results:
            key = f"{result.document_id}_{result.chunk_id}"
            if key not in result_dict:
                result_dict[key] = result
                result_dict[key].score *= self.keyword_weight
                result_dict[key].source_type = 'keyword'
            else:
                # 融合分数
                existing_result = result_dict[key]
                existing_result.score += result.score * self.keyword_weight
                existing_result.source_type = 'hybrid'
                existing_result.relevance_explanation += f" + {result.relevance_explanation}"

        # 转换为列表并排序
        fused_results = list(result_dict.values())
        fused_results.sort(key=lambda x: x.score, reverse=True)

        return fused_results

    def _rerank_results(self, results: List[SearchResult],
                       query: str,
                       boost_params: Optional[Dict[str, float]] = None) -> List[SearchResult]:
        """重排序结果"""
        if not results:
            return results

        boost_params = boost_params or {}

        # 应用各种权重调整
        for result in results:
            original_score = result.score

            # 标题匹配权重提升
            title_boost = boost_params.get('title_boost', 1.2)
            if self._has_query_terms_in_title(query, result.title):
                result.score *= title_boost

            # 文档类型权重调整
            doc_type_boost = boost_params.get('doc_type_boost', 1.0)
            if result.metadata.get('category') in ['配置管理', '故障排除']:
                result.score *= doc_type_boost

            # 厂商匹配权重提升
            vendor_boost = boost_params.get('vendor_boost', 1.1)
            if self._has_vendor_match(query, result.metadata.get('vendor', '')):
                result.score *= vendor_boost

            # 内容质量分数
            quality_score = self._calculate_quality_score(result)
            result.score *= quality_score

            logger.debug(f"重排序: {original_score:.3f} -> {result.score:.3f}")

        # 最终排序
        results.sort(key=lambda x: x.score, reverse=True)

        return results

    def _has_query_terms_in_title(self, query: str, title: str) -> bool:
        """检查查询词是否在标题中"""
        if not title:
            return False

        # 首先检查技术术语精确匹配
        tech_terms = self._extract_tech_terms(query)
        title_lower = title.lower()

        # 如果查询包含技术术语，必须精确匹配
        if tech_terms:
            for term in tech_terms:
                if term.lower() in title_lower:
                    return True
            return False

        # 对于非技术术语查询，使用分词匹配
        query_terms = list(jieba.cut(query.lower()))
        for term in query_terms:
            term = term.strip()
            if len(term) > 1 and term in title_lower:
                return True

        return False

    def _has_vendor_match(self, query: str, vendor: str) -> bool:
        """检查厂商匹配"""
        if not vendor:
            return False

        query_lower = query.lower()
        vendor_lower = vendor.lower()

        vendor_keywords = {
            '华为': ['华为', 'huawei', 'vrp'],
            '思科': ['思科', 'cisco', 'ios'],
            '华三': ['华三', 'h3c', 'comware']
        }

        if vendor_lower in vendor_keywords:
            return any(keyword in query_lower for keyword in vendor_keywords[vendor_lower])

        return vendor_lower in query_lower

    def _calculate_quality_score(self, result: SearchResult) -> float:
        """计算内容质量分数"""
        score = 1.0

        # 内容长度适中加分
        content_length = len(result.content)
        if 100 <= content_length <= 2000:
            score *= 1.1
        elif content_length < 50:
            score *= 0.8

        # 有标题加分
        if result.title and len(result.title) > 0:
            score *= 1.05

        # 有结构化内容加分
        if any(marker in result.content for marker in ['1.', '2.', '步骤', '配置', '命令']):
            score *= 1.1

        return score

    def _get_db_type(self) -> VectorDBType:
        """获取向量数据库类型"""
        # 根据Open WebUI的配置确定数据库类型
        try:
            db_client_name = type(VECTOR_DB_CLIENT).__name__.lower()
            if 'weaviate' in db_client_name:
                return VectorDBType.WEAVIATE
            elif 'chroma' in db_client_name:
                return VectorDBType.CHROMA
            elif 'qdrant' in db_client_name:
                return VectorDBType.QDRANT
            elif 'milvus' in db_client_name:
                return VectorDBType.MILVUS
            elif 'pinecone' in db_client_name:
                return VectorDBType.PINECONE
            elif 'pgvector' in db_client_name:
                return VectorDBType.PGVECTOR
            elif 'elasticsearch' in db_client_name:
                return VectorDBType.ELASTICSEARCH
            elif 'opensearch' in db_client_name:
                return VectorDBType.OPENSEARCH
            else:
                return VectorDBType.WEAVIATE  # 默认
        except Exception:
            return VectorDBType.WEAVIATE  # 默认

    def _fallback_vector_search(self, query: str, collection_name: str, filters: Optional[Dict[str, Any]] = None) -> List[SearchResult]:
        """降级到纯向量检索"""
        logger.warning("降级到纯向量检索")
        try:
            return self._vector_search(query, collection_name, filters)
        except Exception as e:
            logger.error(f"降级检索也失败: {str(e)}")
            return []

# 全局检索服务实例
_hybrid_retrieval_instance = None

def get_hybrid_retrieval() -> HybridRetrievalService:
    """获取混合检索服务实例"""
    global _hybrid_retrieval_instance
    if _hybrid_retrieval_instance is None:
        _hybrid_retrieval_instance = HybridRetrievalService()
    return _hybrid_retrieval_instance

def search_knowledge(query: str,
                    collection_name: str = "knowledge",
                    filters: Optional[Dict[str, Any]] = None,
                    vector_weight: float = 0.7,
                    keyword_weight: float = 0.3,
                    top_k: int = 10) -> List[Dict[str, Any]]:
    """
    便捷的知识检索函数

    Args:
        query: 查询文本
        collection_name: 集合名称
        filters: 过滤条件
        vector_weight: 向量检索权重
        keyword_weight: 关键词检索权重
        top_k: 返回结果数量

    Returns:
        List[Dict]: 检索结果列表
    """
    try:
        # 创建临时检索器实例
        retrieval = HybridRetrievalService(
            vector_weight=vector_weight,
            keyword_weight=keyword_weight,
            final_top_k=top_k
        )

        results = retrieval.search(query, collection_name, filters)

        # 转换为字典格式
        return [
            {
                'content': result.content,
                'title': result.title,
                'score': result.score,
                'source_type': result.source_type,
                'document_id': result.document_id,
                'chunk_id': result.chunk_id,
                'metadata': result.metadata,
                'relevance_explanation': result.relevance_explanation
            }
            for result in results
        ]

    except Exception as e:
        logger.error(f"知识检索失败: {str(e)}")
        return []
