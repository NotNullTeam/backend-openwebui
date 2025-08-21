"""
开发调试模块完整测试套件
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, Mock, AsyncMock
from datetime import datetime
import json

from open_webui.main import app


client = TestClient(app)


class TestDevEndpoints:
    """开发调试所有端点的完整测试"""
    
    # ===== GET /dev/prompts 获取提示词模板 =====
    @patch('open_webui.routers.dev.get_admin_user')
    @patch('open_webui.routers.dev.get_prompt_templates')
    def test_get_prompt_templates(self, mock_templates, mock_admin):
        """测试获取提示词模板"""
        mock_admin.return_value = MagicMock(role="admin")
        mock_templates.return_value = [
            {
                "id": "template-1",
                "name": "网络故障诊断",
                "content": "分析以下网络故障：{problem}",
                "variables": ["problem"],
                "category": "network"
            },
            {
                "id": "template-2",
                "name": "配置优化建议",
                "content": "为{device}提供配置优化建议",
                "variables": ["device"],
                "category": "optimization"
            }
        ]
        
        response = client.get(
            "/api/v1/dev/prompts",
            headers={"Authorization": "Bearer admin-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["name"] == "网络故障诊断"
    
    # ===== POST /dev/prompts 创建提示词模板 =====
    @patch('open_webui.routers.dev.get_admin_user')
    @patch('open_webui.routers.dev.create_prompt_template')
    def test_create_prompt_template(self, mock_create, mock_admin):
        """测试创建提示词模板"""
        mock_admin.return_value = MagicMock(role="admin")
        mock_create.return_value = {
            "id": "template-new",
            "name": "安全检查",
            "content": "检查{system}的安全配置",
            "variables": ["system"],
            "created_at": datetime.utcnow().isoformat()
        }
        
        response = client.post(
            "/api/v1/dev/prompts",
            json={
                "name": "安全检查",
                "content": "检查{system}的安全配置",
                "variables": ["system"],
                "category": "security"
            },
            headers={"Authorization": "Bearer admin-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "安全检查"
    
    # ===== POST /dev/index/rebuild 重建向量索引 =====
    @patch('open_webui.routers.dev.get_admin_user')
    @patch('open_webui.routers.dev.rebuild_vector_index_async')
    def test_rebuild_vector_index(self, mock_rebuild, mock_admin):
        """测试重建向量索引"""
        mock_admin.return_value = MagicMock(role="admin")
        mock_rebuild.return_value = {
            "task_id": "task-123",
            "status": "started",
            "estimated_time": 300
        }
        
        response = client.post(
            "/api/v1/dev/index/rebuild",
            json={"force": True, "collection": "knowledge"},
            headers={"Authorization": "Bearer admin-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"
        assert data["task_id"] == "task-123"
    
    # ===== GET /dev/index/status 获取索引状态 =====
    @patch('open_webui.routers.dev.get_admin_user')
    @patch('open_webui.routers.dev.get_index_status')
    def test_get_index_status(self, mock_status, mock_admin):
        """测试获取向量索引状态"""
        mock_admin.return_value = MagicMock(role="admin")
        mock_status.return_value = {
            "collections": [
                {
                    "name": "knowledge",
                    "count": 10000,
                    "size": 500000000,
                    "last_updated": datetime.utcnow().isoformat()
                },
                {
                    "name": "cases",
                    "count": 5000,
                    "size": 250000000,
                    "last_updated": datetime.utcnow().isoformat()
                }
            ],
            "total_size": 750000000,
            "health": "healthy"
        }
        
        response = client.get(
            "/api/v1/dev/index/status",
            headers={"Authorization": "Bearer admin-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["collections"]) == 2
        assert data["health"] == "healthy"
    
    # ===== POST /dev/llm/test 测试LLM连接 =====
    @patch('open_webui.routers.dev.get_admin_user')
    @patch('open_webui.routers.dev.test_llm_connection')
    def test_llm_connection(self, mock_test, mock_admin):
        """测试LLM连接"""
        mock_admin.return_value = MagicMock(role="admin")
        mock_test.return_value = {
            "status": "connected",
            "model": "gpt-4",
            "response_time": 0.5,
            "test_response": "连接成功"
        }
        
        response = client.post(
            "/api/v1/dev/llm/test",
            json={
                "model": "gpt-4",
                "test_prompt": "Hello"
            },
            headers={"Authorization": "Bearer admin-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "connected"
        assert data["model"] == "gpt-4"
    
    # ===== GET /dev/logs 获取调试日志 =====
    @patch('open_webui.routers.dev.get_admin_user')
    @patch('open_webui.routers.dev.get_debug_logs')
    def test_get_debug_logs(self, mock_logs, mock_admin):
        """测试获取调试日志"""
        mock_admin.return_value = MagicMock(role="admin")
        mock_logs.return_value = [
            {
                "timestamp": datetime.utcnow().isoformat(),
                "level": "DEBUG",
                "module": "vector_search",
                "message": "Query executed in 0.2s",
                "context": {"query": "test", "results": 10}
            },
            {
                "timestamp": datetime.utcnow().isoformat(),
                "level": "INFO",
                "module": "llm_service",
                "message": "Response generated",
                "context": {"tokens": 150}
            }
        ]
        
        response = client.get(
            "/api/v1/dev/logs?module=vector_search&limit=100",
            headers={"Authorization": "Bearer admin-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
        assert data[0]["module"] == "vector_search"
    
    # ===== POST /dev/cache/clear 清除缓存 =====
    @patch('open_webui.routers.dev.get_admin_user')
    @patch('open_webui.routers.dev.clear_cache')
    def test_clear_cache(self, mock_clear, mock_admin):
        """测试清除缓存"""
        mock_admin.return_value = MagicMock(role="admin")
        mock_clear.return_value = {
            "cleared": True,
            "types": ["query_cache", "embedding_cache"],
            "freed_memory": 100000000
        }
        
        response = client.post(
            "/api/v1/dev/cache/clear",
            json={"cache_types": ["all"]},
            headers={"Authorization": "Bearer admin-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["cleared"] is True
        assert data["freed_memory"] > 0
    
    # ===== GET /dev/performance 性能监控 =====
    @patch('open_webui.routers.dev.get_admin_user')
    @patch('open_webui.routers.dev.get_performance_metrics')
    def test_get_performance_metrics(self, mock_metrics, mock_admin):
        """测试获取性能指标"""
        mock_admin.return_value = MagicMock(role="admin")
        mock_metrics.return_value = {
            "api_latency": {
                "avg": 150,
                "p50": 100,
                "p95": 500,
                "p99": 1000
            },
            "database": {
                "query_time_avg": 20,
                "connection_pool": {"active": 5, "idle": 10}
            },
            "vector_search": {
                "avg_search_time": 50,
                "index_size": 1000000
            }
        }
        
        response = client.get(
            "/api/v1/dev/performance",
            headers={"Authorization": "Bearer admin-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "api_latency" in data
        assert data["api_latency"]["avg"] == 150
    
    # ===== POST /dev/config/update 更新配置 =====
    @patch('open_webui.routers.dev.get_admin_user')
    @patch('open_webui.routers.dev.update_dev_config')
    def test_update_dev_config(self, mock_update, mock_admin):
        """测试更新开发配置"""
        mock_admin.return_value = MagicMock(role="admin")
        mock_update.return_value = {
            "updated": True,
            "config": {
                "debug_mode": True,
                "log_level": "DEBUG",
                "profiling": True
            }
        }
        
        response = client.post(
            "/api/v1/dev/config/update",
            json={
                "debug_mode": True,
                "log_level": "DEBUG",
                "profiling": True
            },
            headers={"Authorization": "Bearer admin-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["updated"] is True
        assert data["config"]["debug_mode"] is True
    
    # ===== POST /dev/database/query 执行数据库查询 =====
    @patch('open_webui.routers.dev.get_admin_user')
    @patch('open_webui.routers.dev.execute_query')
    def test_execute_database_query(self, mock_execute, mock_admin):
        """测试执行数据库查询"""
        mock_admin.return_value = MagicMock(role="admin")
        mock_execute.return_value = {
            "rows": [
                {"id": 1, "name": "Case 1"},
                {"id": 2, "name": "Case 2"}
            ],
            "count": 2,
            "execution_time": 0.05
        }
        
        response = client.post(
            "/api/v1/dev/database/query",
            json={
                "query": "SELECT id, name FROM cases LIMIT 2",
                "read_only": True
            },
            headers={"Authorization": "Bearer admin-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["rows"]) == 2
        assert data["count"] == 2
    
    # ===== 边界条件和异常测试 =====
    @patch('open_webui.routers.dev.get_admin_user')
    def test_non_admin_access_denied(self, mock_admin):
        """测试非管理员访问被拒绝"""
        mock_admin.return_value = None
        
        response = client.get(
            "/api/v1/dev/prompts",
            headers={"Authorization": "Bearer user-token"}
        )
        
        assert response.status_code == 403
        assert "管理员权限" in response.json()["detail"]
    
    @patch('open_webui.routers.dev.get_admin_user')
    @patch('open_webui.routers.dev.test_llm_connection')
    def test_llm_connection_timeout(self, mock_test, mock_admin):
        """测试LLM连接超时"""
        mock_admin.return_value = MagicMock(role="admin")
        mock_test.side_effect = TimeoutError("Connection timeout")
        
        response = client.post(
            "/api/v1/dev/llm/test",
            json={"model": "gpt-4"},
            headers={"Authorization": "Bearer admin-token"}
        )
        
        assert response.status_code == 504
        assert "超时" in response.json()["detail"]
    
    @patch('open_webui.routers.dev.get_admin_user')
    @patch('open_webui.routers.dev.rebuild_vector_index_async')
    def test_rebuild_index_already_running(self, mock_rebuild, mock_admin):
        """测试索引重建已在进行中"""
        mock_admin.return_value = MagicMock(role="admin")
        mock_rebuild.side_effect = RuntimeError("Rebuild already in progress")
        
        response = client.post(
            "/api/v1/dev/index/rebuild",
            headers={"Authorization": "Bearer admin-token"}
        )
        
        assert response.status_code == 409
        assert "已在进行" in response.json()["detail"]
    
    @patch('open_webui.routers.dev.get_admin_user')
    @patch('open_webui.routers.dev.execute_query')
    def test_dangerous_query_blocked(self, mock_execute, mock_admin):
        """测试危险查询被阻止"""
        mock_admin.return_value = MagicMock(role="admin")
        
        response = client.post(
            "/api/v1/dev/database/query",
            json={
                "query": "DROP TABLE cases",
                "read_only": True
            },
            headers={"Authorization": "Bearer admin-token"}
        )
        
        assert response.status_code == 400
        assert "危险操作" in response.json()["detail"]
    
    @patch('open_webui.routers.dev.get_admin_user')
    @patch('open_webui.routers.dev.get_performance_metrics')
    def test_performance_metrics_high_latency(self, mock_metrics, mock_admin):
        """测试高延迟性能警告"""
        mock_admin.return_value = MagicMock(role="admin")
        mock_metrics.return_value = {
            "api_latency": {
                "avg": 5000,  # 5秒，非常高
                "p99": 10000
            },
            "warnings": ["API响应时间过高", "数据库连接池耗尽"]
        }
        
        response = client.get(
            "/api/v1/dev/performance",
            headers={"Authorization": "Bearer admin-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["api_latency"]["avg"] == 5000
        assert len(data["warnings"]) > 0
