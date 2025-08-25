import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import func, desc, and_

from open_webui.env import SRC_LOG_LEVELS
from open_webui.utils.auth import get_verified_user
from open_webui.models.cases import Case as Cases
from open_webui.models.feedbacks import Feedbacks
from open_webui.models.usage_logs import UsageLogs, KnowledgeUsageLog, SearchLog
from open_webui.internal.db import get_db

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])

router = APIRouter()


class TopIssueItem(BaseModel):
    """热点问题项"""
    question: str
    category: str | None = None
    count: int
    percentage: float
    trend: str  # "up", "down", "stable"
    avg_resolution_time: float | None = None  # 平均解决时间（小时）
    satisfaction_rate: float | None = None  # 满意度


class TopIssuesResponse(BaseModel):
    """热点问题统计响应"""
    period: str  # 统计周期描述
    total_issues: int
    top_issues: List[TopIssueItem]
    categories_distribution: Dict[str, int]
    time_trend: List[Dict[str, Any]]  # 时间趋势数据


@router.get("/top-issues", response_model=TopIssuesResponse)
async def get_top_issues(
    days: int = Query(default=7, ge=1, le=90, description="统计天数"),
    limit: int = Query(default=10, ge=1, le=50, description="返回热点问题数量"),
    category: Optional[str] = Query(default=None, description="筛选分类"),
    user=Depends(get_verified_user)
):
    """
    获取热点问题统计
    
    - **days**: 统计最近N天的数据（1-90天）
    - **limit**: 返回前N个热点问题（1-50个）
    - **category**: 可选的分类筛选
    """
    try:
        db = next(get_db())
        
        # 计算时间范围
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # 基础查询条件
        base_filter = [
            Cases.created_at >= start_date,
            Cases.created_at <= end_date,
            Cases.is_deleted == False
        ]
        
        if category:
            base_filter.append(Cases.case_type == category)
        
        # 1. 获取热点问题（按问题分组统计）
        question_stats = db.query(
            Cases.title.label("question"),
            Cases.case_type.label("category"),
            func.count(Cases.id).label("count"),
            func.avg(
                func.extract('epoch', Cases.updated_at - Cases.created_at) / 3600
            ).label("avg_resolution_time")
        ).filter(
            and_(*base_filter)
        ).group_by(
            Cases.title,
            Cases.case_type
        ).order_by(
            desc("count")
        ).limit(limit).all()
        
        # 获取总问题数
        total_issues = db.query(func.count(Cases.id)).filter(
            and_(*base_filter)
        ).scalar() or 0
        
        # 2. 计算满意度（如果有反馈数据）
        satisfaction_data = {}
        if hasattr(Feedbacks, '__tablename__'):
            satisfaction_query = db.query(
                Cases.title,
                func.avg(
                    func.case(
                        (Feedbacks.rating >= 4, 1.0),
                        else_=0.0
                    )
                ).label("satisfaction_rate")
            ).join(
                Feedbacks, Cases.id == Feedbacks.case_id
            ).filter(
                and_(*base_filter)
            ).group_by(Cases.title).all()
            
            satisfaction_data = {item.title: item.satisfaction_rate for item in satisfaction_query}
        
        # 3. 计算趋势（对比上一周期）
        prev_start_date = start_date - timedelta(days=days)
        prev_end_date = start_date
        
        prev_stats = db.query(
            Cases.title,
            func.count(Cases.id).label("count")
        ).filter(
            and_(
                Cases.created_at >= prev_start_date,
                Cases.created_at < prev_end_date,
                Cases.is_deleted == False
            )
        ).group_by(Cases.title).all()
        
        prev_counts = {item.title: item.count for item in prev_stats}
        
        # 4. 构建热点问题列表
        top_issues = []
        for stat in question_stats:
            prev_count = prev_counts.get(stat.question, 0)
            
            # 计算趋势
            if prev_count == 0:
                trend = "up" if stat.count > 0 else "stable"
            elif stat.count > prev_count * 1.1:
                trend = "up"
            elif stat.count < prev_count * 0.9:
                trend = "down"
            else:
                trend = "stable"
            
            top_issues.append(TopIssueItem(
                question=stat.question,
                category=stat.category,
                count=stat.count,
                percentage=round((stat.count / total_issues * 100) if total_issues > 0 else 0, 2),
                trend=trend,
                avg_resolution_time=round(float(stat.avg_resolution_time), 2) if stat.avg_resolution_time else None,
                satisfaction_rate=satisfaction_data.get(stat.question)
            ))
        
        # 5. 获取分类分布
        category_stats = db.query(
            Cases.case_type,
            func.count(Cases.id).label("count")
        ).filter(
            and_(*base_filter)
        ).group_by(Cases.case_type).all()
        
        categories_distribution = {
            item.case_type or "未分类": item.count 
            for item in category_stats
        }
        
        # 6. 获取时间趋势数据（按天分组）
        time_trend = []
        for i in range(days):
            day_start = start_date + timedelta(days=i)
            day_end = day_start + timedelta(days=1)
            
            day_count = db.query(func.count(Cases.id)).filter(
                and_(
                    Cases.created_at >= day_start,
                    Cases.created_at < day_end,
                    Cases.is_deleted == False
                )
            ).scalar() or 0
            
            time_trend.append({
                "date": day_start.strftime("%Y-%m-%d"),
                "count": day_count
            })
        
        # 构建响应
        return TopIssuesResponse(
            period=f"最近{days}天",
            total_issues=total_issues,
            top_issues=top_issues,
            categories_distribution=categories_distribution,
            time_trend=time_trend
        )
        
    except Exception as e:
        log.error(f"Failed to get top issues statistics: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"获取热点问题统计失败: {str(e)}"
        )


class UserActivityStats(BaseModel):
    """用户活跃度统计"""
    active_users: int
    new_users: int
    total_queries: int
    avg_queries_per_user: float
    peak_hour: int  # 0-23
    peak_day: str  # 星期几


@router.get("/user-activity", response_model=UserActivityStats)
async def get_user_activity(
    days: int = Query(default=7, ge=1, le=30, description="统计天数"),
    user=Depends(get_verified_user)
):
    """
    获取用户活跃度统计
    """
    try:
        db = next(get_db())
        
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # 从使用日志获取真实的活跃用户数
        from open_webui.models.usage_logs import UsageLog
        active_users = db.query(
            func.count(func.distinct(UsageLog.user_id))
        ).filter(
            and_(
                UsageLog.created_at >= start_date,
                UsageLog.created_at <= end_date
            )
        ).scalar() or 0
        
        # 如果没有使用日志，回退到案例统计
        if active_users == 0:
            active_users = db.query(
                func.count(func.distinct(Cases.user_id))
            ).filter(
                and_(
                    Cases.created_at >= start_date,
                    Cases.created_at <= end_date,
                    Cases.is_deleted == False
                )
            ).scalar() or 0
        
        # 从搜索日志获取真实的查询数
        total_queries = db.query(func.count(SearchLog.id)).filter(
            and_(
                SearchLog.created_at >= start_date,
                SearchLog.created_at <= end_date
            )
        ).scalar() or 0
        
        # 如果没有搜索日志，回退到案例统计
        if total_queries == 0:
            total_queries = db.query(func.count(Cases.id)).filter(
                and_(
                    Cases.created_at >= start_date,
                    Cases.created_at <= end_date,
                    Cases.is_deleted == False
                )
            ).scalar() or 0
        
        # 计算平均每用户查询数
        avg_queries = round(total_queries / active_users, 2) if active_users > 0 else 0
        
        # 获取高峰时段（按小时统计）
        hour_stats = db.query(
            func.extract('hour', Cases.created_at).label("hour"),
            func.count(Cases.id).label("count")
        ).filter(
            and_(
                Cases.created_at >= start_date,
                Cases.created_at <= end_date,
                Cases.is_deleted == False
            )
        ).group_by("hour").order_by(desc("count")).first()
        
        peak_hour = int(hour_stats.hour) if hour_stats else 0
        
        # 获取高峰日期（按星期统计）
        dow_stats = db.query(
            func.extract('dow', Cases.created_at).label("dow"),  # 0=Sunday, 1=Monday, etc.
            func.count(Cases.id).label("count")
        ).filter(
            and_(
                Cases.created_at >= start_date,
                Cases.created_at <= end_date,
                Cases.is_deleted == False
            )
        ).group_by("dow").order_by(desc("count")).first()
        
        dow_map = {
            0: "星期日", 1: "星期一", 2: "星期二", 3: "星期三",
            4: "星期四", 5: "星期五", 6: "星期六"
        }
        peak_day = dow_map.get(int(dow_stats.dow), "未知") if dow_stats else "未知"
        
        return UserActivityStats(
            active_users=active_users,
            new_users=0,  # 需要用户表支持
            total_queries=total_queries,
            avg_queries_per_user=avg_queries,
            peak_hour=peak_hour,
            peak_day=peak_day
        )
        
    except Exception as e:
        log.error(f"Failed to get user activity statistics: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"获取用户活跃度统计失败: {str(e)}"
        )


class KnowledgeUsageItem(BaseModel):
    """知识使用项"""
    document_id: str
    document_name: str
    usage_count: int
    last_used: datetime | None
    relevance_score: float  # 平均相关度分数
    feedback_score: float | None  # 用户反馈分数


class KnowledgeUsageStats(BaseModel):
    """知识使用率统计"""
    total_documents: int
    used_documents: int
    usage_rate: float  # 使用率百分比
    total_retrievals: int
    avg_relevance_score: float
    top_used_documents: List[KnowledgeUsageItem]
    unused_documents_count: int
    low_quality_documents: List[str]  # 低质量文档ID列表


@router.get("/knowledge-usage", response_model=KnowledgeUsageStats)
async def get_knowledge_usage(
    days: int = Query(default=30, ge=1, le=90, description="统计天数"),
    limit: int = Query(default=10, ge=1, le=50, description="返回热门文档数量"),
    user=Depends(get_verified_user)
):
    """
    获取知识库使用率统计
    
    - **days**: 统计最近N天的数据（1-90天）
    - **limit**: 返回前N个热门文档（1-50个）
    """
    try:
        from open_webui.services.knowledge_unified import KnowledgeService
        
        db = next(get_db())
        
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # 获取总文档数 - 使用新的知识服务
        knowledge_service = KnowledgeService()
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            stats = loop.run_until_complete(knowledge_service.get_stats("system"))
            total_documents = stats.total_knowledge_bases if stats else 0
        finally:
            loop.close() or 0
        
        # 从真实的知识使用日志中获取数据
        knowledge_usage_stats = db.query(
            KnowledgeUsageLog.knowledge_id,
            func.count(KnowledgeUsageLog.id).label('usage_count'),
            func.avg(KnowledgeUsageLog.relevance_score).label('avg_relevance'),
            func.avg(KnowledgeUsageLog.user_rating).label('avg_rating'),
            func.max(KnowledgeUsageLog.created_at).label('last_used')
        ).filter(
            and_(
                KnowledgeUsageLog.created_at >= start_date,
                KnowledgeUsageLog.created_at <= end_date
            )
        ).group_by(
            KnowledgeUsageLog.knowledge_id
        ).order_by(
            desc('usage_count')
        ).limit(limit * 2).all()  # 获取更多数据以便过滤
        
        # 简化实现：在新的统一系统中，暂时返回基础统计
        # 因为知识使用日志的表结构可能已经改变
        knowledge_usage = []
        
        # 可以在这里添加新的统计逻辑
        # 比如从知识库服务获取使用统计
        
        # 排序并取前N个
        top_used = knowledge_usage[:limit]
        
        # 计算统计指标
        used_documents = 0
        usage_rate = 0.0
        total_retrievals = 0
        avg_relevance = 0.0
        
        # 找出低质量文档（相关度分数低于0.6）
        low_quality = [
            item.document_id for item in knowledge_usage 
            if item.relevance_score < 0.6
        ]
        
        return KnowledgeUsageStats(
            total_documents=total_documents,
            used_documents=used_documents,
            usage_rate=usage_rate,
            total_retrievals=total_retrievals,
            avg_relevance_score=avg_relevance,
            top_used_documents=top_used,
            unused_documents_count=total_documents - used_documents,
            low_quality_documents=low_quality
        )
        
    except Exception as e:
        log.error(f"Failed to get knowledge usage statistics: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"获取知识使用率统计失败: {str(e)}"
        )


class SystemOverviewStats(BaseModel):
    """系统概览统计"""
    total_cases: int
    resolved_cases: int
    resolution_rate: float
    avg_resolution_time: float  # 小时
    total_users: int
    total_knowledge_docs: int
    system_health_score: float  # 0-100
    recent_errors: int
    api_response_time: float  # 毫秒


@router.get("/overview", response_model=SystemOverviewStats)
async def get_system_overview(
    user=Depends(get_verified_user)
):
    """
    获取系统概览统计数据
    """
    try:
        from open_webui.models.users import Users
        from open_webui.services.knowledge_unified import KnowledgeService
        
        db = next(get_db())
        
        # 获取案例统计
        total_cases = db.query(func.count(Cases.id)).filter(
            Cases.is_deleted == False
        ).scalar() or 0
        
        resolved_cases = db.query(func.count(Cases.id)).filter(
            and_(
                Cases.is_deleted == False,
                Cases.status == "resolved"
            )
        ).scalar() or 0
        
        resolution_rate = round(
            (resolved_cases / total_cases * 100) if total_cases > 0 else 0, 2
        )
        
        # 计算平均解决时间
        avg_resolution = db.query(
            func.avg(
                func.extract('epoch', Cases.updated_at - Cases.created_at) / 3600
            )
        ).filter(
            and_(
                Cases.is_deleted == False,
                Cases.status == "resolved"
            )
        ).scalar()
        
        avg_resolution_time = round(float(avg_resolution), 2) if avg_resolution else 0
        
        # 获取用户总数
        total_users = db.query(func.count(Users.id)).scalar() or 0
        
        # 获取知识文档总数 - 使用统一知识服务
        knowledge_service = KnowledgeService()
        try:
            knowledge_stats = await knowledge_service.get_stats(user.id)
            total_knowledge = knowledge_stats.get("total_knowledge_bases", 0) + knowledge_stats.get("total_documents", 0)
        except Exception:
            total_knowledge = 0
        
        # 计算系统健康分数（简化版本）
        health_score = min(100, round(
            (resolution_rate * 0.4) +  # 解决率占40%
            (min(100, total_knowledge * 2) * 0.3) +  # 知识库完整度占30%
            (min(100, 100 - avg_resolution_time) * 0.3)  # 响应速度占30%
        , 1))
        
        # 从使用日志获取真实的错误数和API响应时间
        from open_webui.models.usage_logs import UsageLog
        
        # 获取最近24小时的错误数（响应时间超过5秒的请求）
        error_threshold = 5.0  # 5秒
        recent_time = datetime.utcnow() - timedelta(hours=24)
        recent_errors = db.query(func.count(UsageLog.id)).filter(
            and_(
                UsageLog.created_at >= recent_time,
                UsageLog.response_time > error_threshold
            )
        ).scalar() or 0
        
        # 计算平均API响应时间（毫秒）
        avg_response = db.query(
            func.avg(UsageLog.response_time)
        ).filter(
            and_(
                UsageLog.created_at >= recent_time,
                UsageLog.response_time.isnot(None)
            )
        ).scalar()
        
        api_response_time = round(float(avg_response) * 1000, 2) if avg_response else 100.0
        
        return SystemOverviewStats(
            total_cases=total_cases,
            resolved_cases=resolved_cases,
            resolution_rate=resolution_rate,
            avg_resolution_time=avg_resolution_time,
            total_users=total_users,
            total_knowledge_docs=total_knowledge,
            system_health_score=health_score,
            recent_errors=recent_errors,
            api_response_time=api_response_time
        )
        
    except Exception as e:
        log.error(f"Failed to get system overview statistics: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"获取系统概览统计失败: {str(e)}"
        )
