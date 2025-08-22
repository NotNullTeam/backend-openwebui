"""
优化的搜索建议模块
包含智能搜索建议、热词推荐、历史记录等功能
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Set
from datetime import datetime, timedelta
from collections import Counter, defaultdict
import re
import jieba
import jieba.analyse
import hashlib
import json
from redis import Redis
import numpy as np
from sqlalchemy import func, desc, and_, or_, distinct

from open_webui.env import SRC_LOG_LEVELS, REDIS_HOST, REDIS_PORT, REDIS_PASSWORD
from open_webui.utils.auth import get_verified_user
from open_webui.models.cases import Cases
from open_webui.models.knowledge import Knowledges
from open_webui.models.files import Files
from open_webui.internal.db import get_db
from open_webui.retrieval.vector.factory import VECTOR_DB_CLIENT
from open_webui.retrieval.utils import get_embedding_function
from open_webui.config import (
    RAG_EMBEDDING_ENGINE,
    RAG_EMBEDDING_MODEL,
    RAG_EMBEDDING_BATCH_SIZE,
    RAG_OPENAI_API_BASE_URL,
    RAG_OPENAI_API_KEY,
)
from open_webui.services.usage_tracker import UsageTracker

# 初始化 logging
log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])

# Redis连接
try:
    redis_client = Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD,
        decode_responses=True,
        socket_connect_timeout=5
    )
    redis_client.ping()
    REDIS_AVAILABLE = True
except Exception as e:
    log.warning(f"Redis not available: {e}. Using in-memory cache.")
    redis_client = None
    REDIS_AVAILABLE = False

router = APIRouter()


class SearchSuggestion(BaseModel):
    """搜索建议项"""
    text: str
    type: str  # "history", "hotword", "semantic", "completion"
    score: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SearchSuggestionsResponse(BaseModel):
    """搜索建议响应"""
    query: str
    suggestions: List[SearchSuggestion]
    total: int


class SearchHistoryItem(BaseModel):
    """搜索历史项"""
    query: str
    timestamp: datetime
    result_count: int
    clicked_results: List[str] = Field(default_factory=list)


# 内存中的搜索历史存储（Redis不可用时的后备）
_search_history: Dict[str, List[SearchHistoryItem]] = {}

# 热词缓存
_hot_words_cache: Dict[str, List[tuple]] = {}
_hot_words_cache_time: Dict[str, datetime] = {}

# 停用词集合（扩展版）
STOP_WORDS = {
    '的', '是', '在', '和', '了', '有', '我', '你', '他', '她', '它', 
    '这', '那', '吗', '啊', '吧', '呢', '着', '把', '被', '给', '让',
    '对', '向', '从', '到', '为', '与', '或', '且', '但', '如果', '因为',
    '所以', '虽然', '可是', '不过', '也', '都', '很', '非常', '最', '更',
    'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should'
}


def extract_keywords(text: str, top_k: int = 10, use_tfidf: bool = True) -> List[str]:
    """提取关键词（增强版）"""
    if not text:
        return []
    
    # 使用TF-IDF提取关键词
    if use_tfidf:
        try:
            # 使用jieba的TF-IDF算法
            keywords = jieba.analyse.extract_tags(
                text, 
                topK=top_k, 
                withWeight=False,
                allowPOS=('n', 'nr', 'ns', 'nt', 'nw', 'nz', 'v', 'vn')  # 只保留名词和动词
            )
            return keywords
        except Exception as e:
            log.debug(f"TF-IDF extraction failed: {e}")
    
    # 后备方案：使用基础分词
    words = jieba.cut_for_search(text)
    
    # 过滤停用词和短词
    keywords = [w for w in words if len(w) > 1 and w not in STOP_WORDS]
    
    # 统计词频并返回高频词
    word_freq = Counter(keywords)
    return [word for word, _ in word_freq.most_common(top_k)]


def calculate_similarity(text1: str, text2: str, method: str = "jaccard") -> float:
    """计算文本相似度（增强版）"""
    words1 = set(extract_keywords(text1.lower(), use_tfidf=False))
    words2 = set(extract_keywords(text2.lower(), use_tfidf=False))
    
    if not words1 or not words2:
        return 0.0
    
    if method == "jaccard":
        # Jaccard相似度
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        return len(intersection) / len(union) if union else 0.0
    
    elif method == "cosine":
        # 余弦相似度（基于词频）
        all_words = list(words1.union(words2))
        vec1 = [1 if w in words1 else 0 for w in all_words]
        vec2 = [1 if w in words2 else 0 for w in all_words]
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5
        
        if norm1 * norm2 == 0:
            return 0.0
        return dot_product / (norm1 * norm2)
    
    else:
        # 默认使用Jaccard
        return calculate_similarity(text1, text2, "jaccard")


async def get_history_suggestions(query: str, user_id: str) -> List[SearchSuggestion]:
    """获取历史搜索建议（优化版）"""
    suggestions = []
    query_lower = query.lower()
    
    # 尝试从Redis获取
    if REDIS_AVAILABLE:
        try:
            history_key = f"search:history:{user_id}"
            history_data = redis_client.lrange(history_key, 0, 99)
            user_history = [json.loads(item) for item in history_data]
        except Exception as e:
            log.debug(f"Failed to get history from Redis: {e}")
            user_history = []
            for item in _search_history.get(user_id, []):
                user_history.append({
                    'query': item.query,
                    'timestamp': item.timestamp.isoformat(),
                    'result_count': item.result_count
                })
    else:
        user_history = []
        for item in _search_history.get(user_id, []):
            user_history.append({
                'query': item.query,
                'timestamp': item.timestamp.isoformat(),
                'result_count': item.result_count
            })
    
    # 计算相似度并生成建议
    for item in user_history:
        item_query = item.get('query', '')
        if query_lower in item_query.lower():
            # 使用余弦相似度
            similarity = calculate_similarity(query, item_query, method="cosine")
            if similarity > 0.3:
                suggestions.append(SearchSuggestion(
                    text=item_query,
                    type="history",
                    score=similarity * 1.2 + 0.1,  # 历史记录加权
                    metadata={
                        "last_searched": item.get('timestamp', datetime.utcnow().isoformat()),
                        "result_count": item.get('result_count', 0)
                    }
                ))
    
    # 排序
    suggestions.sort(key=lambda x: x.score, reverse=True)
    return suggestions


async def get_hotword_suggestions(query: str) -> List[SearchSuggestion]:
    """获取热词建议（优化版）"""
    suggestions = []
    query_lower = query.lower()
    hot_words = await get_hot_words()
    
    for word, score in hot_words:
        # 多种匹配策略
        if query_lower in word.lower():
            match_score = 1.0
        elif word.lower() in query_lower:
            match_score = 0.8
        else:
            # 计算编辑距离
            similarity = calculate_similarity(query, word, method="cosine")
            if similarity < 0.2:
                continue
            match_score = similarity
        
        suggestions.append(SearchSuggestion(
            text=word,
            type="hotword",
            score=match_score * score * 1.1,  # 结合热度分数
            metadata={
                "popularity": "high" if score > 0.7 else "medium",
                "heat_score": score
            }
        ))
    
    return suggestions


class SearchRequest(BaseModel):
    query: str
    limit: int = 10
    include_history: bool = True
    include_hotwords: bool = True
    include_semantic: bool = True

@router.post("/suggestions")
async def get_search_suggestions(
    request: SearchRequest,
    user=Depends(get_verified_user)
) -> SearchSuggestionsResponse:
    """
    获取智能搜索建议
    
    包含多种建议来源：
    - 用户搜索历史
    - 热门搜索词
    - 语义相关建议
    - 自动补全
    """
    try:
        # 记录搜索操作
        UsageTracker.log_search(
            user_id=user.id,
            query=request.query,
            search_type="suggestions"
        )
        
        suggestions = []
        query_lower = request.query.lower()
        
        # 1. 从搜索历史获取建议（优化版）
        if request.include_history:
            history_suggestions = await get_history_suggestions(query_lower, user.id)
            suggestions.extend(history_suggestions[:5])
        
        # 2. 获取热词建议（优化版）
        if request.include_hotwords:
            hotword_suggestions = await get_hotword_suggestions(query_lower)
            suggestions.extend(hotword_suggestions)
        
        # 3. 语义相关建议（基于向量搜索）
        if request.include_semantic:
            semantic_suggestions = await get_semantic_suggestions(query_lower, limit=5)
            suggestions.extend(semantic_suggestions)
        
        # 4. 自动补全建议（基于前缀匹配）
        completion_suggestions = await get_completion_suggestions(query_lower, user.id)
        suggestions.extend(completion_suggestions)
        
        # 去重和排序
        seen_texts = set()
        unique_suggestions = []
        for suggestion in suggestions:
            if suggestion.text not in seen_texts:
                seen_texts.add(suggestion.text)
                unique_suggestions.append(suggestion)
        
        # 按分数排序
        unique_suggestions.sort(key=lambda x: x.score, reverse=True)
        
        # 限制返回数量
        final_suggestions = unique_suggestions[:request.limit]
        
        return SearchSuggestionsResponse(
            query=request.query,
            suggestions=final_suggestions,
            total=len(final_suggestions)
        )
        
    except Exception as e:
        log.error(f"Failed to get search suggestions: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"获取搜索建议失败: {str(e)}"
        )


async def get_hot_words() -> List[tuple]:
    """获取热词列表（返回词和热度分数）"""
    # 检查Redis缓存
    if REDIS_AVAILABLE:
        try:
            cache_key = "search:hotwords:global"
            cached_data = redis_client.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
        except Exception as e:
            log.debug(f"Failed to get hotwords from Redis: {e}")
    
    # 检查内存缓存
    cache_key = "global"
    if cache_key in _hot_words_cache:
        cache_time = _hot_words_cache_time.get(cache_key)
        if cache_time and (datetime.utcnow() - cache_time).seconds < 3600:  # 1小时缓存
            return _hot_words_cache[cache_key]
    
    try:
        db = next(get_db())
        
        # 从最近7天的案例中提取热词
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=7)
        
        recent_cases = db.query(Cases.title).filter(
            and_(
                Cases.created_at >= start_date,
                Cases.created_at <= end_date,
                Cases.is_deleted == False
            )
        ).limit(100).all()
        
        # 提取所有关键词
        all_keywords = []
        for case in recent_cases:
            if case.title:
                keywords = extract_keywords(case.title)
                all_keywords.extend(keywords)
        
        # 统计词频
        word_counter = Counter(all_keywords)
        
        # 获取前20个热词，计算热度分数
        total_count = sum(word_counter.values())
        hot_words = []
        for word, count in word_counter.most_common(20):
            # 计算归一化的热度分数
            heat_score = min(1.0, count / max(5, total_count / 100))
            hot_words.append((word, heat_score))
        
        # 更新缓存
        _hot_words_cache[cache_key] = hot_words
        _hot_words_cache_time[cache_key] = datetime.utcnow()
        
        # 存储到Redis
        if REDIS_AVAILABLE:
            try:
                redis_key = "search:hotwords:global"
                redis_client.setex(
                    redis_key,
                    3600,  # 1小时过期
                    json.dumps(hot_words)
                )
            except Exception as e:
                log.debug(f"Failed to cache hotwords to Redis: {e}")
        
        return hot_words
        
    except Exception as e:
        log.error(f"Failed to get hot words: {str(e)}")
        return []


async def get_semantic_suggestions(query: str, limit: int = 5) -> List[SearchSuggestion]:
    """获取语义相关的搜索建议（优化版）"""
    try:
        # 检查缓存
        if REDIS_AVAILABLE:
            cache_key = f"search:semantic:{hashlib.md5(query.encode()).hexdigest()}"
            try:
                cached_suggestions = redis_client.get(cache_key)
                if cached_suggestions:
                    return [SearchSuggestion(**s) for s in json.loads(cached_suggestions)][:limit]
            except Exception as e:
                log.debug(f"Failed to get semantic cache: {e}")
        
        # 获取嵌入函数
        embedding_function = get_embedding_function(
            embedding_engine=RAG_EMBEDDING_ENGINE,
            embedding_model=RAG_EMBEDDING_MODEL,
            embedding_function=None,
            url=RAG_OPENAI_API_BASE_URL,
            key=RAG_OPENAI_API_KEY,
            embedding_batch_size=RAG_EMBEDDING_BATCH_SIZE,
            azure_api_version=None,
        )
        
        # 获取查询向量
        query_vector = embedding_function(query)
        
        # 从知识库中搜索相似内容
        db = next(get_db())
        knowledge_bases = Knowledges.get_knowledge_bases()
        
        semantic_suggestions = []
        
        for kb in knowledge_bases[:3]:  # 限制搜索的知识库数量
            try:
                # 向量搜索
                results = VECTOR_DB_CLIENT.search(
                    collection_name=kb.id,
                    vectors=[query_vector],
                    limit=3
                )
                
                if results and results.documents:
                    for i, doc in enumerate(results.documents[0]):
                        # 提取关键句子作为建议
                        sentences = re.split(r'[。！？\n]', doc)
                        
                        # 智能句子选择
                        best_sentences = []
                        for sentence in sentences:
                            sentence = sentence.strip()
                            if 10 < len(sentence) < 60:
                                # 计算句子与查询的相关性
                                sent_similarity = calculate_similarity(query, sentence, "cosine")
                                if sent_similarity > 0.15:
                                    best_sentences.append((sentence, sent_similarity))
                        
                        # 选择最相关的句子
                        best_sentences.sort(key=lambda x: x[1], reverse=True)
                        for sentence, sent_score in best_sentences[:2]:
                            similarity_score = 1.0 - results.distances[0][i] if results.distances else 0.5
                            combined_score = similarity_score * 0.7 + sent_score * 0.3
                            
                            semantic_suggestions.append(SearchSuggestion(
                                text=sentence,
                                type="semantic",
                                score=combined_score,
                                metadata={
                                    "source": kb.name,
                                    "knowledge_id": kb.id,
                                    "relevance": "high" if combined_score > 0.7 else "medium"
                                }
                            ))
            except Exception as e:
                log.debug(f"Semantic search failed for knowledge base {kb.id}: {e}")
                continue
        
        # 排序并返回前N个
        semantic_suggestions.sort(key=lambda x: x.score, reverse=True)
        result = semantic_suggestions[:limit]
        
        # 缓存结果
        if REDIS_AVAILABLE and result:
            try:
                cache_key = f"search:semantic:{hashlib.md5(query.encode()).hexdigest()}"
                redis_client.setex(
                    cache_key,
                    600,  # 10分钟缓存
                    json.dumps([s.dict() for s in result])
                )
            except Exception as e:
                log.debug(f"Failed to cache semantic suggestions: {e}")
        
        return result
        
    except Exception as e:
        log.error(f"Failed to get semantic suggestions: {str(e)}")
        return []


async def get_completion_suggestions(query: str, user_id: str) -> List[SearchSuggestion]:
    """获取自动补全建议（增强版）"""
    try:
        db = next(get_db())
        
        # 多种匹配策略
        completions = []
        
        # 1. 前缀匹配
        prefix_matches = db.query(Cases.title).filter(
            and_(
                Cases.title.ilike(f"{query}%"),
                Cases.is_deleted == False
            )
        ).distinct().limit(3).all()
        
        for title in prefix_matches:
            if title.title and title.title != query:
                completions.append(SearchSuggestion(
                    text=title.title,
                    type="completion",
                    score=0.9,
                    metadata={"match_type": "prefix", "source": "cases"}
                ))
        
        # 2. 包含匹配
        if len(completions) < 5:
            contain_matches = db.query(Cases.title).filter(
                and_(
                    Cases.title.ilike(f"%{query}%"),
                    Cases.title.notilike(f"{query}%"),  # 排除前缀匹配
                    Cases.is_deleted == False
                )
            ).distinct().limit(3).all()
            
            for title in contain_matches:
                if title.title and title.title != query:
                    completions.append(SearchSuggestion(
                        text=title.title,
                        type="completion",
                        score=0.7,
                        metadata={"match_type": "contains", "source": "cases"}
                    ))
        
        # 3. 从知识库标题获取补全
        if len(completions) < 5:
            knowledge_matches = db.query(distinct(Knowledges.name)).filter(
                Knowledges.name.ilike(f"%{query}%")
            ).limit(2).all()
            
            for name in knowledge_matches:
                if name[0] and name[0] != query:
                    completions.append(SearchSuggestion(
                        text=name[0],
                        type="completion",
                        score=0.6,
                        metadata={"match_type": "knowledge", "source": "knowledge_base"}
                    ))
        
        return completions[:5]
        
    except Exception as e:
        log.error(f"Failed to get completion suggestions: {str(e)}")
        return []


@router.post("/history")
async def save_search_history(
    history_item: SearchHistoryItem,
    user=Depends(get_verified_user)
):
    """
    保存搜索历史（支持Redis持久化）
    """
    user_id = user.id
    
    # 序列化历史记录
    history_data = {
        "query": history_item.query,
        "timestamp": history_item.timestamp.isoformat(),
        "result_count": history_item.result_count,
        "clicked_results": history_item.clicked_results
    }
    
    # 保存到Redis
    if REDIS_AVAILABLE:
        try:
            history_key = f"search:history:{user_id}"
            # 添加到列表头部
            redis_client.lpush(history_key, json.dumps(history_data))
            # 限制列表长度
            redis_client.ltrim(history_key, 0, 99)
            # 设置过期时间（30天）
            redis_client.expire(history_key, 30 * 24 * 3600)
        except Exception as e:
            log.error(f"Failed to save history to Redis: {e}")
    
    # 同时保存到内存（作为后备）
    if user_id not in _search_history:
        _search_history[user_id] = []
    
    _search_history[user_id].insert(0, history_item)
    
    # 限制历史记录数量
    max_history = 100
    if len(_search_history[user_id]) > max_history:
        _search_history[user_id] = _search_history[user_id][:max_history]
    
    return {"message": "搜索历史已保存"}


@router.get("/history", response_model=List[SearchHistoryItem])
async def get_search_history(
    limit: int = Query(default=20, ge=1, le=100),
    user=Depends(get_verified_user)
):
    """
    获取搜索历史
    """
    user_id = user.id
    history = _search_history.get(user_id, [])
    return history[:limit]


@router.delete("/history")
async def clear_search_history(user=Depends(get_verified_user)):
    """
    清除搜索历史
    """
    user_id = user.id
    if user_id in _search_history:
        del _search_history[user_id]
    
    return {"message": "搜索历史已清除"}


@router.get("/trending")
async def get_trending_searches(
    days: int = Query(default=7, ge=1, le=30, description="统计天数"),
    limit: int = Query(default=10, ge=1, le=20, description="返回数量")
):
    """
    获取热门搜索趋势
    """
    try:
        db = next(get_db())
        
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # 从案例中提取热门查询
        recent_cases = db.query(
            Cases.title,
            func.count(Cases.id).label("count")
        ).filter(
            and_(
                Cases.created_at >= start_date,
                Cases.created_at <= end_date,
                Cases.is_deleted == False
            )
        ).group_by(Cases.title).order_by(desc("count")).limit(limit).all()
        
        trending = []
        for case in recent_cases:
            trending.append({
                "query": case.title,
                "count": case.count,
                "trend": "up"  # 可以通过对比上一周期来计算实际趋势
            })
        
        return {
            "period": f"最近{days}天",
            "trending": trending
        }
        
    except Exception as e:
        log.error(f"Failed to get trending searches: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"获取热门搜索失败: {str(e)}"
        )
