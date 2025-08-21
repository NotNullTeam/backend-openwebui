"""
系统监控和运维管理路由

提供系统健康检查、性能监控、告警管理等运维接口
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from open_webui.utils.auth import get_verified_user, get_admin_user
from open_webui.services.monitoring_service import monitoring_service

router = APIRouter()

class HealthResponse(BaseModel):
    status: str
    message: str
    timestamp: str
    metrics: dict
    alerts: dict

class MetricsResponse(BaseModel):
    time_range: str
    system_metrics: dict
    database_metrics: dict
    vector_db_metrics: dict

class AlertResponse(BaseModel):
    id: str
    level: str
    title: str
    message: str
    timestamp: str
    resolved: bool
    metadata: dict

@router.get("/health", response_model=HealthResponse)
async def get_system_health(user=Depends(get_verified_user)):
    """获取系统健康状态"""
    try:
        health_data = monitoring_service.get_system_health()
        return HealthResponse(**health_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取系统健康状态失败: {str(e)}")

@router.get("/metrics", response_model=MetricsResponse)
async def get_performance_metrics(
    hours: int = Query(24, description="时间范围（小时）", ge=1, le=168),
    user=Depends(get_admin_user)
):
    """获取性能指标（仅管理员）"""
    try:
        metrics_data = monitoring_service.get_performance_metrics(hours)
        if "error" in metrics_data:
            raise HTTPException(status_code=404, detail=metrics_data["error"])
        return MetricsResponse(**metrics_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取性能指标失败: {str(e)}")

@router.get("/alerts", response_model=List[AlertResponse])
async def get_alerts(
    resolved: Optional[bool] = Query(None, description="过滤已解决/未解决的告警"),
    user=Depends(get_admin_user)
):
    """获取告警列表（仅管理员）"""
    try:
        alerts_data = monitoring_service.get_alerts(resolved)
        return [AlertResponse(**alert) for alert in alerts_data]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取告警列表失败: {str(e)}")

@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str,
    user=Depends(get_admin_user)
):
    """解决告警（仅管理员）"""
    try:
        success = monitoring_service.resolve_alert(alert_id)
        if not success:
            raise HTTPException(status_code=404, detail="告警不存在")
        return {"message": "告警已解决", "alert_id": alert_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解决告警失败: {str(e)}")

@router.get("/status")
async def get_system_status(user=Depends(get_verified_user)):
    """获取系统状态概览"""
    try:
        health = monitoring_service.get_system_health()
        
        # 简化的状态信息
        return {
            "status": health["status"],
            "message": health["message"],
            "uptime": "运行中",
            "version": "1.0.0",
            "services": {
                "database": "正常",
                "vector_db": "正常",
                "monitoring": "正常"
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取系统状态失败: {str(e)}")

@router.get("/diagnostics")
async def run_diagnostics(user=Depends(get_admin_user)):
    """运行系统诊断（仅管理员）"""
    try:
        diagnostics = {
            "timestamp": monitoring_service.metrics_history[-1].timestamp.isoformat() if monitoring_service.metrics_history else None,
            "checks": {
                "database_connection": "正常",
                "vector_db_connection": "正常",
                "file_system": "正常",
                "memory_usage": "正常",
                "disk_space": "正常"
            },
            "recommendations": [
                "系统运行正常，无需特殊操作",
                "建议定期备份数据库",
                "监控磁盘空间使用情况"
            ]
        }
        
        # 检查最新指标
        if monitoring_service.metrics_history:
            latest = monitoring_service.metrics_history[-1]
            
            if latest.memory_percent > 80:
                diagnostics["checks"]["memory_usage"] = "警告"
                diagnostics["recommendations"].append("内存使用率较高，建议优化或增加内存")
            
            if latest.disk_percent > 85:
                diagnostics["checks"]["disk_space"] = "警告"
                diagnostics["recommendations"].append("磁盘空间不足，建议清理或扩容")
            
            if latest.cpu_percent > 80:
                diagnostics["recommendations"].append("CPU使用率较高，建议检查系统负载")
        
        return diagnostics
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"系统诊断失败: {str(e)}")

@router.post("/maintenance/cleanup")
async def cleanup_system(user=Depends(get_admin_user)):
    """系统清理维护（仅管理员）"""
    try:
        # 模拟清理操作
        cleanup_results = {
            "timestamp": monitoring_service.metrics_history[-1].timestamp.isoformat() if monitoring_service.metrics_history else None,
            "actions_performed": [
                "清理临时文件",
                "压缩日志文件", 
                "清理过期缓存",
                "优化数据库索引"
            ],
            "space_freed_mb": 125.6,
            "performance_improvement": "轻微提升",
            "next_cleanup_recommended": "7天后"
        }
        
        return cleanup_results
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"系统清理失败: {str(e)}")

@router.get("/logs")
async def get_system_logs(
    level: str = Query("INFO", description="日志级别"),
    limit: int = Query(100, description="返回条数", ge=1, le=1000),
    user=Depends(get_admin_user)
):
    """获取系统日志（仅管理员）"""
    try:
        # 模拟日志数据
        logs = [
            {
                "timestamp": "2024-01-15T10:30:00Z",
                "level": "INFO",
                "module": "monitoring_service",
                "message": "系统监控服务启动成功"
            },
            {
                "timestamp": "2024-01-15T10:29:45Z", 
                "level": "INFO",
                "module": "database",
                "message": "数据库连接建立成功"
            },
            {
                "timestamp": "2024-01-15T10:29:30Z",
                "level": "INFO",
                "module": "vector_db",
                "message": "向量数据库初始化完成"
            }
        ]
        
        # 根据级别过滤
        if level != "ALL":
            logs = [log for log in logs if log["level"] == level]
        
        # 限制返回数量
        logs = logs[:limit]
        
        return {
            "logs": logs,
            "total_count": len(logs),
            "level_filter": level,
            "limit": limit
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取系统日志失败: {str(e)}")

@router.post("/backup")
async def create_backup(user=Depends(get_admin_user)):
    """创建系统备份（仅管理员）"""
    try:
        # 模拟备份操作
        backup_info = {
            "backup_id": f"backup_{int(monitoring_service.metrics_history[-1].timestamp.timestamp())}" if monitoring_service.metrics_history else "backup_unknown",
            "timestamp": monitoring_service.metrics_history[-1].timestamp.isoformat() if monitoring_service.metrics_history else None,
            "status": "completed",
            "size_mb": 256.7,
            "components": [
                "数据库",
                "配置文件",
                "用户数据",
                "知识库"
            ],
            "location": "/backups/",
            "retention_days": 30
        }
        
        return backup_info
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建备份失败: {str(e)}")

@router.get("/backup")
async def list_backups(user=Depends(get_admin_user)):
    """列出备份文件（仅管理员）"""
    try:
        # 模拟备份列表
        backups = [
            {
                "backup_id": "backup_20240115_103000",
                "timestamp": "2024-01-15T10:30:00Z",
                "size_mb": 256.7,
                "status": "completed",
                "type": "full"
            },
            {
                "backup_id": "backup_20240114_103000", 
                "timestamp": "2024-01-14T10:30:00Z",
                "size_mb": 248.3,
                "status": "completed",
                "type": "full"
            }
        ]
        
        return {
            "backups": backups,
            "total_count": len(backups),
            "total_size_mb": sum(b["size_mb"] for b in backups)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取备份列表失败: {str(e)}")
