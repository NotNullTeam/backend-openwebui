"""
开发调试模块测试用例
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import json

from open_webui.main import app
from open_webui.models.users import UserModel
from open_webui.models.prompts import PromptModel


@pytest.fixture
def admin_user():
    """管理员用户fixture"""
    return UserModel(
        id="admin_123",
        email="admin@example.com",
        name="Admin User",
        role="admin",
        is_active=True
    )


@pytest.fixture
def regular_user():
    """普通用户fixture"""
    return UserModel(
        id="user_456",
        email="user@example.com",
        name="Regular User",
        role="user",
        is_active=True
    )


@pytest.fixture
def auth_headers_admin():
    """管理员认证头"""
    return {"Authorization": "Bearer admin_token"}


@pytest.fixture
def auth_headers_user():
    """普通用户认证头"""
    return {"Authorization": "Bearer user_token"}


class TestPromptTesting:
    """提示词测试相关接口测试"""
    
    def test_test_analysis_prompt(self, client: TestClient, auth_headers_user, regular_user):
        """测试分析提示词接口"""
        with patch('open_webui.routers.dev.get_verified_user', return_value=regular_user):
            response = client.post(
                "/api/v1/dev/prompts/test/analysis",
                headers=auth_headers_user,
                json={
                    "issue_description": "网络连接中断",
                    "context": {"device_type": "router"}
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert "analysis_result" in data["data"]
            assert "tokens_used" in data["data"]
    
    def test_test_clarification_prompt(self, client: TestClient, auth_headers_user, regular_user):
        """测试澄清提示词接口"""
        with patch('open_webui.routers.dev.get_verified_user', return_value=regular_user):
            response = client.post(
                "/api/v1/dev/prompts/test/clarification",
                headers=auth_headers_user,
                json={
                    "issue_description": "网络慢",
                    "conversation_history": []
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert "clarification_questions" in data["data"]
    
    def test_test_solution_prompt(self, client: TestClient, auth_headers_user, regular_user):
        """测试解决方案提示词接口"""
        with patch('open_webui.routers.dev.get_verified_user', return_value=regular_user):
            response = client.post(
                "/api/v1/dev/prompts/test/solution",
                headers=auth_headers_user,
                json={
                    "issue_description": "IP地址冲突",
                    "analysis": "两台设备使用了相同的IP地址"
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert "solution_steps" in data["data"]


class TestVendorAndPerformance:
    """厂商和性能相关接口测试"""
    
    def test_get_supported_vendors(self, client: TestClient, auth_headers_user, regular_user):
        """测试获取支持的厂商列表"""
        with patch('open_webui.routers.dev.get_verified_user', return_value=regular_user):
            response = client.get(
                "/api/v1/dev/vendors",
                headers=auth_headers_user
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert isinstance(data["data"], list)
            assert len(data["data"]) > 0
    
    def test_get_performance_metrics(self, client: TestClient, auth_headers_user, regular_user):
        """测试获取性能指标"""
        with patch('open_webui.routers.dev.get_verified_user', return_value=regular_user):
            response = client.get(
                "/api/v1/dev/performance",
                headers=auth_headers_user
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert "avg_response_time" in data["data"]
            assert "total_requests" in data["data"]
            assert "error_rate" in data["data"]


class TestCacheManagement:
    """缓存管理相关接口测试"""
    
    def test_get_cache_status(self, client: TestClient, auth_headers_user, regular_user):
        """测试获取缓存状态"""
        with patch('open_webui.routers.dev.get_verified_user', return_value=regular_user):
            response = client.get(
                "/api/v1/dev/cache/status",
                headers=auth_headers_user
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "success" in data
            assert "total_keys" in data["data"]
            assert "memory_usage" in data["data"]
    
    def test_clear_cache(self, client: TestClient, auth_headers_admin, admin_user):
        """测试清除缓存（需要管理员权限）"""
        with patch('open_webui.routers.dev.get_admin_user', return_value=admin_user):
            response = client.post(
                "/api/v1/dev/cache/clear",
                headers=auth_headers_admin,
                json={"pattern": "test:*"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] == True
            assert "cleared_count" in data["data"]
    
    def test_clear_cache_unauthorized(self, client: TestClient, auth_headers_user, regular_user):
        """测试非管理员清除缓存（应该失败）"""
        with patch('open_webui.routers.dev.get_admin_user', side_effect=Exception("Unauthorized")):
            response = client.post(
                "/api/v1/dev/cache/clear",
                headers=auth_headers_user,
                json={"pattern": "test:*"}
            )
            
            assert response.status_code in [401, 403, 500]


class TestPromptTemplateManagement:
    """提示词模板管理测试"""
    
    def test_create_prompt_template(self, client: TestClient, auth_headers_user, regular_user):
        """测试创建提示词模板"""
        with patch('open_webui.routers.dev.get_verified_user', return_value=regular_user):
            with patch('open_webui.routers.dev.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value = mock_db
                mock_db.query().filter_by().first.return_value = None
                
                response = client.post(
                    "/api/v1/dev/prompts",
                    headers=auth_headers_user,
                    json={
                        "name": "Test Template",
                        "content": "This is a test template",
                        "category": "analysis"
                    }
                )
                
                assert response.status_code == 201
                data = response.json()
                assert data["code"] == 201
                assert data["status"] == "success"
    
    def test_get_prompt_templates(self, client: TestClient, auth_headers_user, regular_user):
        """测试获取提示词模板列表"""
        with patch('open_webui.routers.dev.get_verified_user', return_value=regular_user):
            with patch('open_webui.routers.dev.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value = mock_db
                
                # 模拟查询结果
                mock_prompt = Mock()
                mock_prompt.id = "1"
                mock_prompt.title = "Test Template"
                mock_prompt.content = "Test content"
                mock_prompt.command = "/test_template"
                mock_prompt.created_at = datetime.utcnow()
                mock_prompt.updated_at = datetime.utcnow()
                
                mock_db.query().count.return_value = 1
                mock_db.query().offset().limit().all.return_value = [mock_prompt]
                
                response = client.get(
                    "/api/v1/dev/prompts?page=1&per_page=10",
                    headers=auth_headers_user
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["code"] == 200
                assert "data" in data
                assert "pagination" in data
    
    def test_update_prompt_template(self, client: TestClient, auth_headers_user, regular_user):
        """测试更新提示词模板"""
        with patch('open_webui.routers.dev.get_verified_user', return_value=regular_user):
            with patch('open_webui.routers.dev.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value = mock_db
                
                # 模拟现有模板
                mock_prompt = Mock()
                mock_prompt.id = "1"
                mock_prompt.user_id = regular_user.id
                mock_prompt.title = "Old Template"
                mock_prompt.content = "Old content"
                mock_prompt.command = "/old_template"
                mock_prompt.created_at = datetime.utcnow()
                mock_prompt.updated_at = datetime.utcnow()
                
                mock_db.query().filter_by().first.return_value = mock_prompt
                mock_db.query().filter().first.return_value = None
                
                response = client.put(
                    "/api/v1/dev/prompts/1",
                    headers=auth_headers_user,
                    json={
                        "name": "Updated Template",
                        "content": "Updated content"
                    }
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["code"] == 200
    
    def test_delete_prompt_template(self, client: TestClient, auth_headers_user, regular_user):
        """测试删除提示词模板"""
        with patch('open_webui.routers.dev.get_verified_user', return_value=regular_user):
            with patch('open_webui.routers.dev.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value = mock_db
                
                # 模拟现有模板
                mock_prompt = Mock()
                mock_prompt.id = "1"
                mock_prompt.user_id = regular_user.id
                
                mock_db.query().filter_by().first.return_value = mock_prompt
                
                response = client.delete(
                    "/api/v1/dev/prompts/1",
                    headers=auth_headers_user
                )
                
                assert response.status_code == 204


class TestVectorDatabaseManagement:
    """向量数据库管理测试"""
    
    def test_get_vector_status(self, client: TestClient, auth_headers_user, regular_user):
        """测试获取向量数据库状态"""
        with patch('open_webui.routers.dev.get_verified_user', return_value=regular_user):
            response = client.get(
                "/api/v1/dev/vector/status",
                headers=auth_headers_user
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] == True
            assert "total_documents" in data["data"]
            assert "total_chunks" in data["data"]
    
    def test_test_vector_connection(self, client: TestClient, auth_headers_user, regular_user):
        """测试向量数据库连接"""
        with patch('open_webui.routers.dev.get_verified_user', return_value=regular_user):
            response = client.post(
                "/api/v1/dev/vector/test",
                headers=auth_headers_user
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] == True
            assert "connection_ok" in data["data"]
    
    def test_search_vectors(self, client: TestClient, auth_headers_user, regular_user):
        """测试向量搜索"""
        with patch('open_webui.routers.dev.get_verified_user', return_value=regular_user):
            response = client.post(
                "/api/v1/dev/vector/search",
                headers=auth_headers_user,
                json={
                    "query": "IP地址配置",
                    "top_k": 5
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] == True
            assert "results" in data["data"]
    
    def test_delete_document_vectors(self, client: TestClient, auth_headers_admin, admin_user):
        """测试删除文档向量（需要管理员权限）"""
        with patch('open_webui.routers.dev.get_admin_user', return_value=admin_user):
            response = client.delete(
                "/api/v1/dev/vector/documents/doc_123",
                headers=auth_headers_admin
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] == True
    
    def test_test_embedding(self, client: TestClient, auth_headers_user, regular_user):
        """测试嵌入服务"""
        with patch('open_webui.routers.dev.get_verified_user', return_value=regular_user):
            response = client.post(
                "/api/v1/dev/vector/embedding/test",
                headers=auth_headers_user,
                json={"text": "测试文本"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] == True
            assert "embedding_dimension" in data["data"]
            assert "embedding_sample" in data["data"]
    
    def test_get_vector_config(self, client: TestClient, auth_headers_user, regular_user):
        """测试获取向量配置"""
        with patch('open_webui.routers.dev.get_verified_user', return_value=regular_user):
            response = client.get(
                "/api/v1/dev/vector/config",
                headers=auth_headers_user
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] == True
            assert "db_type" in data["data"]
            assert "is_valid" in data["data"]


class TestHealthCheck:
    """健康检查测试"""
    
    def test_health_check(self, client: TestClient):
        """测试健康检查端点"""
        response = client.get("/api/v1/dev/health")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] in ["healthy", "degraded", "unhealthy"]
        assert "services" in data
        assert "llm" in data["services"]
        assert "cache" in data["services"]
        assert "vector" in data["services"]


class TestDebugInfo:
    """调试信息测试"""
    
    def test_get_debug_info_admin(self, client: TestClient, auth_headers_admin, admin_user):
        """测试管理员获取调试信息"""
        with patch('open_webui.routers.dev.get_admin_user', return_value=admin_user):
            with patch('open_webui.routers.dev.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value = mock_db
                
                # 模拟数据库查询
                mock_db.query().count.return_value = 100
                
                response = client.get(
                    "/api/v1/dev/debug",
                    headers=auth_headers_admin
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["code"] == 200
                assert "system_info" in data["data"]
                assert "database_stats" in data["data"]
    
    def test_get_debug_info_unauthorized(self, client: TestClient, auth_headers_user):
        """测试非管理员获取调试信息（应该失败）"""
        with patch('open_webui.routers.dev.get_admin_user', side_effect=Exception("Unauthorized")):
            response = client.get(
                "/api/v1/dev/debug",
                headers=auth_headers_user
            )
            
            assert response.status_code in [401, 403, 500]
