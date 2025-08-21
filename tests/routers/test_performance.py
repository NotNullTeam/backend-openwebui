"""
Test cases for performance router endpoints - comprehensive coverage for all 7 endpoints
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from httpx import AsyncClient
import json
from datetime import datetime


@pytest.fixture
def mock_admin_user():
    return MagicMock(
        id="admin123",
        name="Admin User",
        email="admin@example.com",
        role="admin"
    )


@pytest.fixture
def mock_verified_user():
    return MagicMock(
        id="user123",
        name="Test User",
        email="user@example.com",
        role="user"
    )


@pytest.fixture
def mock_performance_report():
    return {
        "timestamp": datetime.now().isoformat(),
        "cpu_usage": 45.2,
        "memory_usage": 67.8,
        "disk_usage": 52.3,
        "active_connections": 15,
        "request_rate": 120.5,
        "response_time_avg": 0.085,
        "cache_hit_rate": 0.78,
        "database_connections": 10,
        "vector_db_status": "healthy"
    }


@pytest.fixture
def mock_cache_stats():
    return {
        "total_entries": 1500,
        "memory_used": "256MB",
        "hit_rate": 0.78,
        "miss_rate": 0.22,
        "evictions": 230,
        "last_cleared": datetime.now().isoformat()
    }


class TestPerformanceReport:
    """Test performance report endpoints"""
    
    async def test_get_performance_report(self, async_client: AsyncClient, mock_admin_user, mock_performance_report):
        """Test GET /report endpoint"""
        with patch("open_webui.routers.performance.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.performance.get_current_performance_metrics") as mock_metrics:
                mock_metrics.return_value = mock_performance_report
                response = await async_client.get("/api/v1/performance/report")
                assert response.status_code == 200
                data = response.json()
                assert "cpu_usage" in data
                assert "memory_usage" in data
                assert "vector_db_status" in data
    
    async def test_get_performance_report_unauthorized(self, async_client: AsyncClient):
        """Test GET /report endpoint unauthorized access"""
        with patch("open_webui.routers.performance.get_admin_user", side_effect=Exception("Unauthorized")):
            response = await async_client.get("/api/v1/performance/report")
            assert response.status_code in [401, 403, 500]


class TestCacheManagement:
    """Test cache management endpoints"""
    
    async def test_clear_caches(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /cache/clear endpoint"""
        with patch("open_webui.routers.performance.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.performance.clear_all_caches") as mock_clear:
                mock_clear.return_value = {"cleared": True, "timestamp": datetime.now().isoformat()}
                response = await async_client.post("/api/v1/performance/cache/clear")
                assert response.status_code == 200
                data = response.json()
                assert data["cleared"] is True
    
    async def test_warmup_caches(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /cache/warmup endpoint"""
        with patch("open_webui.routers.performance.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.performance.warmup_vector_search_cache") as mock_warmup:
                mock_warmup.return_value = {
                    "warmed_up": 5,
                    "failed": 0,
                    "duration": 1.23
                }
                response = await async_client.post(
                    "/api/v1/performance/cache/warmup",
                    json={"queries": ["test query 1", "test query 2", "test query 3"]}
                )
                assert response.status_code == 200
                data = response.json()
                assert data["warmed_up"] == 5
    
    async def test_get_cache_stats(self, async_client: AsyncClient, mock_admin_user, mock_cache_stats):
        """Test GET /cache/stats endpoint"""
        with patch("open_webui.routers.performance.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.performance.get_cache_statistics") as mock_stats:
                mock_stats.return_value = mock_cache_stats
                response = await async_client.get("/api/v1/performance/cache/stats")
                assert response.status_code == 200
                data = response.json()
                assert "total_entries" in data
                assert "hit_rate" in data
                assert data["hit_rate"] == 0.78


class TestOptimization:
    """Test optimization endpoints"""
    
    async def test_get_optimization_suggestions(self, async_client: AsyncClient, mock_admin_user):
        """Test GET /optimization/suggestions endpoint"""
        with patch("open_webui.routers.performance.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.performance.analyze_and_suggest_optimizations") as mock_analyze:
                mock_analyze.return_value = {
                    "suggestions": [
                        {
                            "category": "database",
                            "priority": "high",
                            "description": "Add index on frequently queried columns",
                            "impact": "30% query performance improvement"
                        },
                        {
                            "category": "cache",
                            "priority": "medium",
                            "description": "Increase cache TTL for static content",
                            "impact": "Reduce database load by 20%"
                        }
                    ],
                    "overall_health": "good",
                    "score": 78
                }
                response = await async_client.get("/api/v1/performance/optimization/suggestions")
                assert response.status_code == 200
                data = response.json()
                assert "suggestions" in data
                assert len(data["suggestions"]) == 2
                assert data["overall_health"] == "good"


class TestBatchOperations:
    """Test batch operations endpoints"""
    
    async def test_batch_vector_search(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /search/batch endpoint"""
        with patch("open_webui.routers.performance.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.performance.batch_vector_search_parallel") as mock_search:
                mock_search.return_value = [
                    {
                        "query": "test query 1",
                        "results": [
                            {"id": "doc1", "score": 0.95, "content": "Result 1"},
                            {"id": "doc2", "score": 0.88, "content": "Result 2"}
                        ]
                    },
                    {
                        "query": "test query 2",
                        "results": [
                            {"id": "doc3", "score": 0.92, "content": "Result 3"}
                        ]
                    }
                ]
                response = await async_client.post(
                    "/api/v1/performance/search/batch",
                    params={
                        "queries": ["test query 1", "test query 2"],
                        "limit": 10
                    }
                )
                assert response.status_code == 200
                data = response.json()
                assert "results" in data
                assert len(data["results"]) == 2
                assert data["results"][0]["query"] == "test query 1"
    
    async def test_batch_vector_search_empty_queries(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /search/batch with empty queries"""
        with patch("open_webui.routers.performance.get_admin_user", return_value=mock_admin_user):
            response = await async_client.post(
                "/api/v1/performance/search/batch",
                params={"queries": [], "limit": 10}
            )
            assert response.status_code in [400, 422]


class TestPerformanceMetrics:
    """Test performance metrics endpoints"""
    
    async def test_get_performance_metrics(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /metrics endpoint"""
        with patch("open_webui.routers.performance.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.performance.get_basic_performance_metrics") as mock_metrics:
                mock_metrics.return_value = {
                    "system": {
                        "cpu": 45.2,
                        "memory": 67.8,
                        "disk": 52.3
                    },
                    "application": {
                        "requests_per_second": 120,
                        "active_users": 45,
                        "response_time_ms": 85
                    },
                    "database": {
                        "connections": 10,
                        "query_time_avg_ms": 12.5
                    }
                }
                response = await async_client.get("/api/v1/performance/metrics")
                assert response.status_code == 200
                data = response.json()
                assert "system" in data
                assert "application" in data
                assert "database" in data
                assert data["system"]["cpu"] == 45.2
    
    async def test_get_performance_metrics_error(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /metrics endpoint with error"""
        with patch("open_webui.routers.performance.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.performance.get_basic_performance_metrics", side_effect=Exception("Metrics error")):
                response = await async_client.get("/api/v1/performance/metrics")
                assert response.status_code == 500


class TestPerformanceErrorHandling:
    """Test error handling for performance endpoints"""
    
    async def test_clear_cache_error(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /cache/clear with error"""
        with patch("open_webui.routers.performance.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.performance.clear_all_caches", side_effect=Exception("Cache clear failed")):
                response = await async_client.post("/api/v1/performance/cache/clear")
                assert response.status_code == 500
                assert "清理缓存失败" in response.json()["detail"]
    
    async def test_warmup_cache_error(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /cache/warmup with error"""
        with patch("open_webui.routers.performance.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.performance.warmup_vector_search_cache", side_effect=Exception("Warmup failed")):
                response = await async_client.post(
                    "/api/v1/performance/cache/warmup",
                    json={"queries": ["test"]}
                )
                assert response.status_code == 500
                assert "缓存预热失败" in response.json()["detail"]
    
    async def test_cache_stats_error(self, async_client: AsyncClient, mock_admin_user):
        """Test GET /cache/stats with error"""
        with patch("open_webui.routers.performance.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.performance.get_cache_statistics", side_effect=Exception("Stats failed")):
                response = await async_client.get("/api/v1/performance/cache/stats")
                assert response.status_code == 500
                assert "获取缓存统计失败" in response.json()["detail"]
    
    async def test_optimization_suggestions_error(self, async_client: AsyncClient, mock_admin_user):
        """Test GET /optimization/suggestions with error"""
        with patch("open_webui.routers.performance.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.performance.analyze_and_suggest_optimizations", side_effect=Exception("Analysis failed")):
                response = await async_client.get("/api/v1/performance/optimization/suggestions")
                assert response.status_code == 500
                assert "获取优化建议失败" in response.json()["detail"]
    
    async def test_batch_search_error(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /search/batch with error"""
        with patch("open_webui.routers.performance.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.performance.batch_vector_search_parallel", side_effect=Exception("Search failed")):
                response = await async_client.post(
                    "/api/v1/performance/search/batch",
                    params={"queries": ["test"], "limit": 10}
                )
                assert response.status_code == 500
                assert "批量搜索失败" in response.json()["detail"]
