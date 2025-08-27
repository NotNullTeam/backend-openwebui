import time
import os
import psutil
import platform
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, text
from open_webui.utils.auth import get_verified_user, get_admin_user
from open_webui.internal.db import get_db
from open_webui.models.cases import Case, CaseNode, CaseEdge
from open_webui.models.knowledge import Knowledge
from open_webui.models.files import File
from open_webui.models.users import User
from open_webui.models.chats import Chat
from open_webui.models.notifications import Notification
from open_webui.services.knowledge_unified import KnowledgeService
from open_webui.env import VERSION, CACHE_DIR, DATA_DIR


router = APIRouter()


@router.get("/health")
async def health(user=Depends(get_verified_user)):
    """基础健康检查"""
    return {"status": "ok", "version": VERSION, "time": int(time.time())}


@router.get("/health/detailed")
async def health_detailed(user=Depends(get_admin_user)):
    """详细系统健康检查（仅管理员）"""
    try:
        # CPU和内存信息
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # 数据库连接检查
        db_healthy = True
        db_response_time = 0
        try:
            start = time.time()
            with get_db() as db:
                db.execute(text("SELECT 1"))
            db_response_time = round((time.time() - start) * 1000, 2)  # ms
        except Exception as e:
            db_healthy = False
            db_error = str(e)
        
        # 缓存目录大小
        cache_size = 0
        if os.path.exists(CACHE_DIR):
            for dirpath, dirnames, filenames in os.walk(CACHE_DIR):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    if os.path.exists(fp):
                        cache_size += os.path.getsize(fp)
        
        # 数据目录大小
        data_size = 0
        if os.path.exists(DATA_DIR):
            for dirpath, dirnames, filenames in os.walk(DATA_DIR):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    if os.path.exists(fp):
                        data_size += os.path.getsize(fp)
        
        health_status = {
            "status": "healthy" if db_healthy and cpu_percent < 90 and memory.percent < 90 else "degraded",
            "version": VERSION,
            "timestamp": datetime.utcnow().isoformat(),
            "system": {
                "platform": platform.platform(),
                "python_version": platform.python_version(),
                "cpu_count": psutil.cpu_count(),
                "cpu_percent": cpu_percent,
                "memory": {
                    "total": memory.total,
                    "available": memory.available,
                    "percent": memory.percent,
                    "used": memory.used,
                },
                "disk": {
                    "total": disk.total,
                    "used": disk.used,
                    "free": disk.free,
                    "percent": disk.percent,
                },
            },
            "database": {
                "healthy": db_healthy,
                "response_time_ms": db_response_time,
                "error": db_error if not db_healthy else None,
            },
            "storage": {
                "cache_size_bytes": cache_size,
                "data_size_bytes": data_size,
                "cache_size_mb": round(cache_size / (1024 * 1024), 2),
                "data_size_mb": round(data_size / (1024 * 1024), 2),
            },
        }
        
        return health_status
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


@router.get("/statistics")
async def statistics(
    days: int = Query(7, description="Number of days for trend analysis"),
    user=Depends(get_verified_user)
):
    """获取系统统计信息，包括趋势分析"""
    with get_db() as db:
        # 基础统计
        cases_total = db.query(Case).count()
        nodes_total = db.query(CaseNode).count()
        edges_total = db.query(CaseEdge).count()
        files_total = db.query(File).count()
        knowledge_total = db.query(Knowledge).count()
        users_total = db.query(User).count()
        chats_total = db.query(Chat).count()
        notifications_total = db.query(Notification).count()
        
        # 时间范围统计
        cutoff_ts = int(time.time()) - days * 86400
        
        # 近期新增案例
        recent_cases = db.query(Case).filter(Case.created_at >= cutoff_ts).count()
        
        # 近期活跃用户
        recent_active_users = db.query(func.count(func.distinct(Chat.user_id))).filter(
            Chat.created_at >= cutoff_ts
        ).scalar() or 0
        
        # 近期新增知识
        recent_knowledge = db.query(Knowledge).filter(
            Knowledge.created_at >= cutoff_ts
        ).count()
        
        # 未读通知统计
        unread_notifications = db.query(Notification).filter(
            Notification.read == False
        ).count()
        
    return {
        "summary": {
            "total_cases": cases_total,
            "total_users": users_total,
            "total_knowledge": knowledge_total,
            "total_chats": chats_total,
        },
        "details": {
            "cases": {
                "total": cases_total,
                "recent": recent_cases,
                "nodes": nodes_total,
                "edges": edges_total,
            },
            "users": {
                "total": users_total,
                "active_recent": recent_active_users,
            },
            "knowledge": {
                "total": knowledge_total,
                "recent": recent_knowledge,
                "files": files_total,
            },
            "notifications": {
                "total": notifications_total,
                "unread": unread_notifications,
            },
        },
        "period_days": days,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/metrics")
async def metrics(
    metric_type: str = Query("all", description="Type of metrics: all, performance, usage, errors"),
    user=Depends(get_admin_user)
):
    """获取系统指标（仅管理员）"""
    with get_db() as db:
        metrics_data = {}
        
        if metric_type in ["all", "performance"]:
            # 性能指标
            avg_response_time = db.query(
                func.avg(Chat.updated_at - Chat.created_at)
            ).scalar()
            
            metrics_data["performance"] = {
                "avg_response_time": str(avg_response_time) if avg_response_time else "N/A",
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "memory_percent": psutil.virtual_memory().percent,
            }
        
        if metric_type in ["all", "usage"]:
            # 使用指标
            daily_active_users = db.query(func.count(func.distinct(Chat.user_id))).filter(
                Chat.created_at >= datetime.utcnow() - timedelta(days=1)
            ).scalar() or 0
            
            weekly_active_users = db.query(func.count(func.distinct(Chat.user_id))).filter(
                Chat.created_at >= datetime.utcnow() - timedelta(days=7)
            ).scalar() or 0
            
            monthly_active_users = db.query(func.count(func.distinct(Chat.user_id))).filter(
                Chat.created_at >= datetime.utcnow() - timedelta(days=30)
            ).scalar() or 0
            
            metrics_data["usage"] = {
                "daily_active_users": daily_active_users,
                "weekly_active_users": weekly_active_users,
                "monthly_active_users": monthly_active_users,
                "total_chats": db.query(Chat).count(),
                "total_cases": db.query(Case).count(),
                "total_knowledge": db.query(Knowledge).count(),
            }
        
        if metric_type in ["all", "errors"]:
            # 错误指标（基于反馈表）
            from open_webui.models.feedbacks import Feedback
            
            total_feedback = db.query(Feedback).count()
            negative_feedback = db.query(Feedback).filter(
                Feedback.rating < 3  # 假设评分低于3为负面反馈
            ).count()
            
            metrics_data["errors"] = {
                "total_feedback": total_feedback,
                "negative_feedback": negative_feedback,
                "error_rate": round(negative_feedback / total_feedback * 100, 2) if total_feedback > 0 else 0,
            }
        
        metrics_data["timestamp"] = datetime.utcnow().isoformat()
        return metrics_data


@router.get("/activity")
async def activity(
    hours: int = Query(24, description="Number of hours to look back"),
    user=Depends(get_verified_user)
):
    """获取系统活动日志"""
    cutoff_ts = int(time.time()) - hours * 3600
    
    with get_db() as db:
        # 最近的聊天活动
        recent_chats = db.query(
            Chat.id,
            Chat.user_id,
            Chat.title,
            Chat.created_at
        ).filter(
            Chat.created_at >= cutoff_ts
        ).order_by(Chat.created_at.desc()).limit(10).all()
        
        # 最近的案例活动
        recent_cases = db.query(
            Case.id,
            Case.title,
            Case.created_at,
            Case.updated_at
        ).filter(
            Case.updated_at >= cutoff_ts
        ).order_by(Case.updated_at.desc()).limit(10).all()
        
        # 最近的知识库更新
        recent_knowledge = db.query(
            Knowledge.id,
            Knowledge.name,
            Knowledge.created_at,
            Knowledge.updated_at
        ).filter(
            Knowledge.updated_at >= cutoff_ts
        ).order_by(Knowledge.updated_at.desc()).limit(10).all()
        
        return {
            "period_hours": hours,
            "recent_chats": [
                {
                    "id": chat.id,
                    "user_id": chat.user_id,
                    "title": chat.title,
                    "created_at": datetime.utcfromtimestamp(chat.created_at).isoformat() if chat.created_at else None,
                }
                for chat in recent_chats
            ],
            "recent_cases": [
                {
                    "id": case.id,
                    "title": case.title,
                    "created_at": datetime.utcfromtimestamp(case.created_at).isoformat() if case.created_at else None,
                    "updated_at": datetime.utcfromtimestamp(case.updated_at).isoformat() if case.updated_at else None,
                }
                for case in recent_cases
            ],
            "recent_knowledge": [
                {
                    "id": k.id,
                    "name": k.name,
                    "created_at": datetime.utcfromtimestamp(k.created_at).isoformat() if k.created_at else None,
                    "updated_at": datetime.utcfromtimestamp(k.updated_at).isoformat() if k.updated_at else None,
                }
                for k in recent_knowledge
            ],
            "timestamp": datetime.utcnow().isoformat()
        }
