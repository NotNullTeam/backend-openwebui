"""
开发调试模块增强功能测试

测试新增的向量索引重建、LLM连接测试、日志查看等功能
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from open_webui.main import app
from open_webui.models.auths import UserModel


@pytest.fixture
def client():
    """测试客户端"""
    return TestClient(app)


@pytest.fixture
def admin_user():
    """管理员用户"""
    return UserModel(
        id="admin_user_id",
        name="Admin User",
        email="admin@example.com",
        role="admin"
    )


@pytest.fixture
def regular_user():
    """普通用户"""
    return UserModel(
        id="regular_user_id",
        name="Regular User",
        email="user@example.com",
        role="user"
    )


class TestVectorIndexRebuild:
    """向量索引重建功能测试"""
    
    @patch('open_webui.utils.auth.get_admin_user')
    def test_rebuild_all_vector_index(self, mock_get_admin_user, client, admin_user):
        """测试重建全部向量索引"""
        mock_get_admin_user.return_value = admin_user
        
        response = client.post("/api/v1/dev/vector/rebuild")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "total_documents" in data["data"]
        assert "chunks_processed" in data["data"]
        assert data["data"]["status"] == "completed"
    
    @patch('open_webui.utils.auth.get_admin_user')
    def test_rebuild_specific_document_index(self, mock_get_admin_user, client, admin_user):
        """测试重建特定文档的向量索引"""
        mock_get_admin_user.return_value = admin_user
        
        response = client.post("/api/v1/dev/vector/rebuild?document_id=doc_123")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["document_id"] == "doc_123"
        assert "chunks_processed" in data["data"]
    
    @patch('open_webui.utils.auth.get_verified_user')
    def test_get_rebuild_status(self, mock_get_verified_user, client, regular_user):
        """测试获取重建状态"""
        mock_get_verified_user.return_value = regular_user
        
        response = client.get("/api/v1/dev/vector/rebuild/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "is_running" in data["data"]
        assert "progress" in data["data"]


class TestLLMConnection:
    """LLM连接测试功能"""
    
    @patch('open_webui.utils.auth.get_verified_user')
    def test_test_llm_connection_default_model(self, mock_get_verified_user, client, regular_user):
        """测试默认模型连接"""
        mock_get_verified_user.return_value = regular_user
        
        response = client.post("/api/v1/dev/test/llm")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["model"] == "qwen-plus"
        assert data["data"]["response"] == "连接正常"
        assert "response_time" in data["data"]
        assert "token_count" in data["data"]
    
    @patch('open_webui.utils.auth.get_verified_user')
    def test_test_llm_connection_specific_model(self, mock_get_verified_user, client, regular_user):
        """测试指定模型连接"""
        mock_get_verified_user.return_value = regular_user
        
        response = client.post("/api/v1/dev/test/llm?model_name=qwen-turbo")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["model"] == "qwen-turbo"
    
    @patch('open_webui.utils.auth.get_verified_user')
    def test_get_available_models(self, mock_get_verified_user, client, regular_user):
        """测试获取可用模型列表"""
        mock_get_verified_user.return_value = regular_user
        
        response = client.get("/api/v1/dev/llm/models")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]) >= 3
        
        # 检查模型信息结构
        model = data["data"][0]
        assert "name" in model
        assert "display_name" in model
        assert "provider" in model
        assert "status" in model


class TestDebugLogs:
    """调试日志功能测试"""
    
    @patch('open_webui.utils.auth.get_admin_user')
    def test_get_debug_logs_default(self, mock_get_admin_user, client, admin_user):
        """测试获取默认调试日志"""
        mock_get_admin_user.return_value = admin_user
        
        response = client.get("/api/v1/dev/debug/logs")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "logs" in data["data"]
        assert "total_count" in data["data"]
        assert data["data"]["level_filter"] == "INFO"
        assert data["data"]["lines_requested"] == 100
    
    @patch('open_webui.utils.auth.get_admin_user')
    def test_get_debug_logs_with_filters(self, mock_get_admin_user, client, admin_user):
        """测试带过滤条件的调试日志"""
        mock_get_admin_user.return_value = admin_user
        
        response = client.get("/api/v1/dev/debug/logs?level=ERROR&lines=50")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["level_filter"] == "ERROR"
        assert data["data"]["lines_requested"] == 50
    
    @patch('open_webui.utils.auth.get_verified_user')
    def test_get_log_levels(self, mock_get_verified_user, client, regular_user):
        """测试获取日志级别列表"""
        mock_get_verified_user.return_value = regular_user
        
        response = client.get("/api/v1/dev/debug/logs/levels")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]) == 6  # DEBUG, INFO, WARNING, ERROR, CRITICAL, ALL
        
        # 检查日志级别结构
        level = data["data"][0]
        assert "value" in level
        assert "label" in level
        assert "color" in level


class TestSystemMetrics:
    """系统监控功能测试"""
    
    @patch('open_webui.utils.auth.get_verified_user')
    def test_get_system_metrics(self, mock_get_verified_user, client, regular_user):
        """测试获取系统性能指标"""
        mock_get_verified_user.return_value = regular_user
        
        response = client.get("/api/v1/dev/system/metrics")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "cpu" in data["data"]
        assert "memory" in data["data"]
        assert "disk" in data["data"]
        assert "timestamp" in data["data"]
        
        # 检查CPU指标
        cpu = data["data"]["cpu"]
        assert "usage_percent" in cpu
        assert "core_count" in cpu
        
        # 检查内存指标
        memory = data["data"]["memory"]
        assert "total" in memory
        assert "used" in memory
        assert "percent" in memory


class TestHealthCheck:
    """健康检查功能测试"""
    
    def test_basic_health_check(self, client):
        """测试基础健康检查"""
        response = client.get("/api/v1/dev/health")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "services" in data
        assert "timestamp" in data
        assert "version" in data
        assert "environment" in data
        
        # 检查服务状态
        services = data["services"]
        assert "llm" in services
        assert "cache" in services
        assert "vector" in services
        assert "database" in services
    
    @patch('open_webui.utils.auth.get_admin_user')
    def test_detailed_health_check(self, mock_get_admin_user, client, admin_user):
        """测试详细健康检查"""
        mock_get_admin_user.return_value = admin_user
        
        response = client.get("/api/v1/dev/health/detailed")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "overall_status" in data["data"]
        assert "services" in data["data"]
        assert "system_info" in data["data"]
        
        # 检查详细服务信息
        services = data["data"]["services"]
        assert "database" in services
        assert "llm" in services
        assert "vector_db" in services
        assert "cache" in services
        
        # 检查数据库服务详情
        db_service = services["database"]
        assert "status" in db_service
        assert "response_time" in db_service
        assert "connections" in db_service


class TestPermissions:
    """权限控制测试"""
    
    @patch('open_webui.utils.auth.get_verified_user')
    def test_admin_only_endpoints_denied_for_regular_user(self, mock_get_verified_user, client, regular_user):
        """测试普通用户访问管理员接口被拒绝"""
        mock_get_verified_user.return_value = regular_user
        
        # 测试向量索引重建（需要管理员权限）
        response = client.post("/api/v1/dev/vector/rebuild")
        assert response.status_code == 403 or response.status_code == 401
        
        # 测试调试日志（需要管理员权限）
        response = client.get("/api/v1/dev/debug/logs")
        assert response.status_code == 403 or response.status_code == 401
        
        # 测试详细健康检查（需要管理员权限）
        response = client.get("/api/v1/dev/health/detailed")
        assert response.status_code == 403 or response.status_code == 401


class TestErrorHandling:
    """错误处理测试"""
    
    @patch('open_webui.utils.auth.get_verified_user')
    @patch('open_webui.routers.dev.logger')
    def test_llm_connection_error_handling(self, mock_logger, mock_get_verified_user, client, regular_user):
        """测试LLM连接错误处理"""
        mock_get_verified_user.return_value = regular_user
        
        # 模拟LLM连接异常
        with patch('open_webui.routers.dev.test_llm_connection') as mock_test:
            mock_test.side_effect = Exception("Connection failed")
            
            response = client.post("/api/v1/dev/test/llm")
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert "error" in data
    
    @patch('open_webui.utils.auth.get_admin_user')
    def test_vector_rebuild_error_handling(self, mock_get_admin_user, client, admin_user):
        """测试向量重建错误处理"""
        mock_get_admin_user.return_value = admin_user
        
        # 模拟向量重建异常
        with patch('open_webui.routers.dev.rebuild_vector_index') as mock_rebuild:
            mock_rebuild.side_effect = Exception("Rebuild failed")
            
            response = client.post("/api/v1/dev/vector/rebuild")
            
            # 应该返回500错误
            assert response.status_code == 500


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
