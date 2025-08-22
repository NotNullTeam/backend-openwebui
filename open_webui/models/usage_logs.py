"""
使用日志数据模型
用于跟踪系统各项功能的使用情况
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Float, Integer, Boolean, JSON, ForeignKey, Index
from sqlalchemy.orm import relationship

from open_webui.internal.db import Base


class UsageLog(Base):
    """使用日志表"""
    __tablename__ = "usage_logs"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    action_type = Column(String, nullable=False, index=True)  # search, retrieval, generation, feedback
    resource_type = Column(String, nullable=True)  # case, knowledge, file
    resource_id = Column(String, nullable=True, index=True)
    
    # 详细信息
    query_text = Column(Text, nullable=True)
    response_text = Column(Text, nullable=True)
    metadata_ = Column("metadata", JSON, nullable=True)  # 额外的元数据
    
    # 性能指标
    response_time = Column(Float, nullable=True)  # 响应时间（秒）
    tokens_used = Column(Integer, nullable=True)  # 使用的token数
    relevance_score = Column(Float, nullable=True)  # 相关度分数
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # 索引优化
    __table_args__ = (
        Index('idx_usage_user_action', 'user_id', 'action_type'),
        Index('idx_usage_resource', 'resource_type', 'resource_id'),
        Index('idx_usage_created', 'created_at'),
    )


class KnowledgeUsageLog(Base):
    """知识库使用日志表"""
    __tablename__ = "knowledge_usage_logs"
    
    id = Column(String, primary_key=True)
    knowledge_id = Column(String, nullable=False, index=True)
    case_id = Column(String, nullable=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    
    # 使用详情
    query = Column(Text, nullable=True)
    chunk_id = Column(String, nullable=True)  # 使用的具体片段ID
    relevance_score = Column(Float, nullable=True)  # 相关度分数
    distance = Column(Float, nullable=True)  # 向量距离
    
    # 反馈
    was_helpful = Column(Boolean, nullable=True)  # 是否有帮助
    user_rating = Column(Integer, nullable=True)  # 用户评分 1-5
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # 索引
    __table_args__ = (
        Index('idx_knowledge_usage_knowledge', 'knowledge_id'),
        Index('idx_knowledge_usage_user', 'user_id'),
        Index('idx_knowledge_usage_created', 'created_at'),
    )


class SearchLog(Base):
    """搜索日志表"""
    __tablename__ = "search_logs"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    session_id = Column(String, nullable=True, index=True)  # 会话ID
    
    # 搜索信息
    query = Column(Text, nullable=False)
    search_type = Column(String, nullable=True)  # keyword, semantic, hybrid
    filters = Column(JSON, nullable=True)  # 搜索过滤条件
    
    # 结果信息
    result_count = Column(Integer, nullable=True)
    clicked_results = Column(JSON, nullable=True)  # 点击的结果ID列表
    selected_result_id = Column(String, nullable=True)  # 最终选择的结果
    
    # 性能指标
    response_time = Column(Float, nullable=True)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # 索引
    __table_args__ = (
        Index('idx_search_user', 'user_id'),
        Index('idx_search_created', 'created_at'),
        Index('idx_search_session', 'session_id'),
    )


# Pydantic模型
class UsageLogModel(BaseModel):
    """使用日志数据模型"""
    id: str
    user_id: str
    action_type: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    query_text: Optional[str] = None
    response_text: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    response_time: Optional[float] = None
    tokens_used: Optional[int] = None
    relevance_score: Optional[float] = None
    created_at: datetime


class KnowledgeUsageLogModel(BaseModel):
    """知识库使用日志数据模型"""
    id: str
    knowledge_id: str
    case_id: Optional[str] = None
    user_id: str
    query: Optional[str] = None
    chunk_id: Optional[str] = None
    relevance_score: Optional[float] = None
    distance: Optional[float] = None
    was_helpful: Optional[bool] = None
    user_rating: Optional[int] = Field(None, ge=1, le=5)
    created_at: datetime


class SearchLogModel(BaseModel):
    """搜索日志数据模型"""
    id: str
    user_id: str
    session_id: Optional[str] = None
    query: str
    search_type: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None
    result_count: Optional[int] = None
    clicked_results: Optional[List[str]] = None
    selected_result_id: Optional[str] = None
    response_time: Optional[float] = None
    created_at: datetime


# 数据访问类
class UsageLogs:
    """使用日志数据访问类"""
    
    @staticmethod
    def log_action(
        db,
        user_id: str,
        action_type: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        **kwargs
    ) -> UsageLog:
        """记录用户操作"""
        import uuid
        
        log = UsageLog(
            id=str(uuid.uuid4()),
            user_id=user_id,
            action_type=action_type,
            resource_type=resource_type,
            resource_id=resource_id,
            query_text=kwargs.get('query_text'),
            response_text=kwargs.get('response_text'),
            metadata_=kwargs.get('metadata'),
            response_time=kwargs.get('response_time'),
            tokens_used=kwargs.get('tokens_used'),
            relevance_score=kwargs.get('relevance_score'),
            created_at=kwargs.get('created_at', datetime.utcnow())
        )
        
        db.add(log)
        db.commit()
        db.refresh(log)
        return log
    
    @staticmethod
    def log_knowledge_usage(
        db,
        knowledge_id: str,
        user_id: str,
        **kwargs
    ) -> KnowledgeUsageLog:
        """记录知识库使用"""
        import uuid
        
        log = KnowledgeUsageLog(
            id=str(uuid.uuid4()),
            knowledge_id=knowledge_id,
            user_id=user_id,
            case_id=kwargs.get('case_id'),
            query=kwargs.get('query'),
            chunk_id=kwargs.get('chunk_id'),
            relevance_score=kwargs.get('relevance_score'),
            distance=kwargs.get('distance'),
            was_helpful=kwargs.get('was_helpful'),
            user_rating=kwargs.get('user_rating'),
            created_at=kwargs.get('created_at', datetime.utcnow())
        )
        
        db.add(log)
        db.commit()
        db.refresh(log)
        return log
    
    @staticmethod
    def log_search(
        db,
        user_id: str,
        query: str,
        **kwargs
    ) -> SearchLog:
        """记录搜索操作"""
        import uuid
        
        log = SearchLog(
            id=str(uuid.uuid4()),
            user_id=user_id,
            query=query,
            session_id=kwargs.get('session_id'),
            search_type=kwargs.get('search_type'),
            filters=kwargs.get('filters'),
            result_count=kwargs.get('result_count'),
            clicked_results=kwargs.get('clicked_results'),
            selected_result_id=kwargs.get('selected_result_id'),
            response_time=kwargs.get('response_time'),
            created_at=kwargs.get('created_at', datetime.utcnow())
        )
        
        db.add(log)
        db.commit()
        db.refresh(log)
        return log
    
    @staticmethod
    def get_user_actions(db, user_id: str, limit: int = 100):
        """获取用户操作日志"""
        return db.query(UsageLog).filter(
            UsageLog.user_id == user_id
        ).order_by(UsageLog.created_at.desc()).limit(limit).all()
    
    @staticmethod
    def get_knowledge_usage_stats(db, knowledge_id: str, days: int = 30):
        """获取知识库使用统计"""
        from datetime import timedelta
        from sqlalchemy import func, and_
        
        start_date = datetime.utcnow() - timedelta(days=days)
        
        stats = db.query(
            func.count(KnowledgeUsageLog.id).label('usage_count'),
            func.avg(KnowledgeUsageLog.relevance_score).label('avg_relevance'),
            func.avg(KnowledgeUsageLog.user_rating).label('avg_rating'),
            func.max(KnowledgeUsageLog.created_at).label('last_used')
        ).filter(
            and_(
                KnowledgeUsageLog.knowledge_id == knowledge_id,
                KnowledgeUsageLog.created_at >= start_date
            )
        ).first()
        
        return {
            'usage_count': stats.usage_count or 0,
            'avg_relevance': float(stats.avg_relevance) if stats.avg_relevance else 0,
            'avg_rating': float(stats.avg_rating) if stats.avg_rating else 0,
            'last_used': stats.last_used
        }
