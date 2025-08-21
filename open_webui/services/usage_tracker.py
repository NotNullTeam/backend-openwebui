"""
使用跟踪服务
用于在系统各个关键点记录用户操作和使用情况
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime
import time
from contextlib import contextmanager

from open_webui.models.usage_logs import UsageLogs
from open_webui.internal.db import get_db

log = logging.getLogger(__name__)


class UsageTracker:
    """使用跟踪器"""
    
    @staticmethod
    @contextmanager
    def track_action(user_id: str, action_type: str, **kwargs):
        """
        跟踪操作执行时间的上下文管理器
        
        使用示例:
            with UsageTracker.track_action(user_id, "search", query_text=query) as tracker:
                # 执行搜索操作
                results = search(query)
                tracker['result_count'] = len(results)
        """
        start_time = time.time()
        context = {}
        
        try:
            yield context
        finally:
            try:
                db = next(get_db())
                response_time = time.time() - start_time
                
                UsageLogs.log_action(
                    db,
                    user_id=user_id,
                    action_type=action_type,
                    response_time=response_time,
                    metadata=context,
                    **kwargs
                )
            except Exception as e:
                log.error(f"Failed to log action: {e}")
    
    @staticmethod
    def log_search(user_id: str, query: str, search_type: str = "hybrid", **kwargs):
        """记录搜索操作"""
        try:
            db = next(get_db())
            UsageLogs.log_search(
                db,
                user_id=user_id,
                query=query,
                search_type=search_type,
                **kwargs
            )
        except Exception as e:
            log.error(f"Failed to log search: {e}")
    
    @staticmethod
    def log_knowledge_usage(
        user_id: str,
        knowledge_id: str,
        case_id: Optional[str] = None,
        relevance_score: Optional[float] = None,
        **kwargs
    ):
        """记录知识库使用"""
        try:
            db = next(get_db())
            UsageLogs.log_knowledge_usage(
                db,
                knowledge_id=knowledge_id,
                user_id=user_id,
                case_id=case_id,
                relevance_score=relevance_score,
                **kwargs
            )
        except Exception as e:
            log.error(f"Failed to log knowledge usage: {e}")
    
    @staticmethod
    def log_api_call(
        user_id: str,
        endpoint: str,
        method: str,
        response_time: float,
        status_code: int,
        **kwargs
    ):
        """记录API调用"""
        try:
            db = next(get_db())
            UsageLogs.log_action(
                db,
                user_id=user_id,
                action_type="api_call",
                metadata={
                    "endpoint": endpoint,
                    "method": method,
                    "status_code": status_code,
                    **kwargs
                },
                response_time=response_time
            )
        except Exception as e:
            log.error(f"Failed to log API call: {e}")
    
    @staticmethod
    def log_llm_generation(
        user_id: str,
        prompt: str,
        response: str,
        model: str,
        tokens_used: int,
        response_time: float,
        **kwargs
    ):
        """记录LLM生成"""
        try:
            db = next(get_db())
            UsageLogs.log_action(
                db,
                user_id=user_id,
                action_type="llm_generation",
                query_text=prompt[:1000],  # 限制长度
                response_text=response[:1000],  # 限制长度
                metadata={
                    "model": model,
                    **kwargs
                },
                tokens_used=tokens_used,
                response_time=response_time
            )
        except Exception as e:
            log.error(f"Failed to log LLM generation: {e}")
    
    @staticmethod
    def update_knowledge_feedback(
        knowledge_id: str,
        user_id: str,
        was_helpful: bool,
        rating: Optional[int] = None
    ):
        """更新知识反馈"""
        try:
            db = next(get_db())
            from open_webui.models.usage_logs import KnowledgeUsageLog
            
            # 查找最近的使用记录
            recent_log = db.query(KnowledgeUsageLog).filter(
                KnowledgeUsageLog.knowledge_id == knowledge_id,
                KnowledgeUsageLog.user_id == user_id
            ).order_by(KnowledgeUsageLog.created_at.desc()).first()
            
            if recent_log:
                recent_log.was_helpful = was_helpful
                if rating:
                    recent_log.user_rating = rating
                db.commit()
                
        except Exception as e:
            log.error(f"Failed to update knowledge feedback: {e}")


# 装饰器版本，用于自动跟踪函数执行
def track_usage(action_type: str, **default_kwargs):
    """
    装饰器：自动跟踪函数执行
    
    使用示例:
        @track_usage("search", resource_type="knowledge")
        async def search_knowledge(query: str, user_id: str):
            # 搜索逻辑
            return results
    """
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            # 尝试从参数中提取user_id
            user_id = kwargs.get('user_id') or (
                args[0].user_id if hasattr(args[0], 'user_id') else None
            )
            
            if not user_id:
                # 没有user_id，直接执行原函数
                return await func(*args, **kwargs)
            
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                response_time = time.time() - start_time
                
                # 记录成功的操作
                try:
                    db = next(get_db())
                    metadata = {**default_kwargs}
                    
                    # 如果结果是列表，记录数量
                    if isinstance(result, list):
                        metadata['result_count'] = len(result)
                    
                    UsageLogs.log_action(
                        db,
                        user_id=user_id,
                        action_type=action_type,
                        response_time=response_time,
                        metadata=metadata
                    )
                except Exception as e:
                    log.error(f"Failed to log usage: {e}")
                
                return result
                
            except Exception as e:
                response_time = time.time() - start_time
                
                # 记录失败的操作
                try:
                    db = next(get_db())
                    metadata = {
                        **default_kwargs,
                        'error': str(e)
                    }
                    
                    UsageLogs.log_action(
                        db,
                        user_id=user_id,
                        action_type=action_type,
                        response_time=response_time,
                        metadata=metadata
                    )
                except Exception as log_error:
                    log.error(f"Failed to log error: {log_error}")
                
                raise
        
        def sync_wrapper(*args, **kwargs):
            # 同步版本
            user_id = kwargs.get('user_id') or (
                args[0].user_id if hasattr(args[0], 'user_id') else None
            )
            
            if not user_id:
                return func(*args, **kwargs)
            
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                response_time = time.time() - start_time
                
                try:
                    db = next(get_db())
                    metadata = {**default_kwargs}
                    
                    if isinstance(result, list):
                        metadata['result_count'] = len(result)
                    
                    UsageLogs.log_action(
                        db,
                        user_id=user_id,
                        action_type=action_type,
                        response_time=response_time,
                        metadata=metadata
                    )
                except Exception as e:
                    log.error(f"Failed to log usage: {e}")
                
                return result
                
            except Exception as e:
                response_time = time.time() - start_time
                
                try:
                    db = next(get_db())
                    metadata = {
                        **default_kwargs,
                        'error': str(e)
                    }
                    
                    UsageLogs.log_action(
                        db,
                        user_id=user_id,
                        action_type=action_type,
                        response_time=response_time,
                        metadata=metadata
                    )
                except Exception as log_error:
                    log.error(f"Failed to log error: {log_error}")
                
                raise
        
        # 根据函数类型返回对应的包装器
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator
