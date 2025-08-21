"""
性能优化管理路由

提供性能监控、缓存管理、查询优化等接口
"""

from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from open_webui.utils.auth import get_verified_user, get_admin_user
from open_webui.services.performance_service import performance_service

router = APIRouter()

class PerformanceReport(BaseModel):
    timestamp: str
    cache_performance: Dict[str, Any]
    connection_pool: Dict[str, Any]
    query_performance: Dict[str, Any]
    api_performance: Dict[str, Any]
    vector_search_performance: Dict[str, Any]
    optimization_suggestions: List[str]
    total_cache_operations: int
    optimizations_applied: int

class CacheWarmupRequest(BaseModel):
    queries: List[str]

@router.get("/report", response_model=PerformanceReport)
async def get_performance_report(user=Depends(get_admin_user)):
    """获取性能报告（仅管理员）"""
    try:
        report_data = performance_service.get_performance_report()
        return PerformanceReport(**report_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取性能报告失败: {str(e)}")

@router.post("/cache/clear")
async def clear_caches(user=Depends(get_admin_user)):
    """清理所有缓存（仅管理员）"""
    try:
        await performance_service.cleanup_caches()
        return {"message": "缓存已清理", "timestamp": performance_service.cache_manager.access_times}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清理缓存失败: {str(e)}")

@router.post("/cache/warmup")
async def warmup_caches(
    request: CacheWarmupRequest,
    user=Depends(get_admin_user)
):
    """预热缓存（仅管理员）"""
    try:
        await performance_service.warm_up_caches(request.queries)
        return {
            "message": "缓存预热完成",
            "queries_processed": len(request.queries),
            "cache_stats": performance_service.cache_manager.get_stats()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"缓存预热失败: {str(e)}")

@router.get("/cache/stats")
async def get_cache_stats(user=Depends(get_admin_user)):
    """获取缓存统计（仅管理员）"""
    try:
        return {
            "main_cache": performance_service.cache_manager.get_stats(),
            "vector_cache": performance_service.vector_cache.get_stats(),
            "connection_pool": performance_service.connection_pool.get_stats()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取缓存统计失败: {str(e)}")

@router.get("/optimization/suggestions")
async def get_optimization_suggestions(user=Depends(get_admin_user)):
    """获取优化建议（仅管理员）"""
    try:
        suggestions = performance_service.query_optimizer.get_optimization_suggestions()
        query_stats = performance_service.query_optimizer.get_query_stats()
        
        return {
            "suggestions": suggestions,
            "query_statistics": query_stats,
            "timestamp": performance_service.performance_metrics
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取优化建议失败: {str(e)}")

@router.post("/search/batch")
async def batch_vector_search(
    queries: List[str] = Query(..., description="批量搜索查询列表"),
    limit: int = Query(10, description="每个查询的结果数量"),
    user=Depends(get_verified_user)
):
    """批量向量搜索优化"""
    try:
        if len(queries) > 50:
            raise HTTPException(status_code=400, detail="批量查询数量不能超过50个")
        
        results = await performance_service.batch_vector_search(queries, limit)
        
        return {
            "results": results,
            "total_queries": len(queries),
            "cache_stats": performance_service.vector_cache.get_stats()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量搜索失败: {str(e)}")

@router.get("/metrics")
async def get_performance_metrics(user=Depends(get_verified_user)):
    """获取性能指标概览"""
    try:
        # 简化的性能指标，普通用户可见
        cache_stats = performance_service.cache_manager.get_stats()
        vector_cache_stats = performance_service.vector_cache.get_stats()
        
        return {
            "cache_hit_rate": cache_stats["hit_rate"],
            "vector_cache_hit_rate": vector_cache_stats["hit_rate"],
            "total_cache_operations": performance_service.performance_metrics["cache_operations"],
            "system_status": "optimal" if cache_stats["hit_rate"] > 70 else "needs_optimization"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取性能指标失败: {str(e)}")
