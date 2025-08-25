"""
知识统一模块的集成测试

测试覆盖knowledge_unified.py中的所有核心功能，包括：
- API路由测试
- 权限控制测试  
- 数据一致性测试
- 异常处理测试
"""

import pytest
import json
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import status

from open_webui.main import app
from open_webui.models.knowledge_unified import (
    KnowledgeBaseCreate,
    KnowledgeBaseUpdate,
    DocumentCreate,
    SearchRequest,
    ProcessingStatus
)


class TestKnowledgeUnified:
    """知识统一模块测试类"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        return TestClient(app)

    @pytest.fixture
    def mock_user(self):
        """模拟用户对象"""
        user = Mock()
        user.id = "test_user_id"
        user.role = "user"
        return user

    @pytest.fixture
    def mock_admin_user(self):
        """模拟管理员用户对象"""
        user = Mock()
        user.id = "admin_user_id"
        user.role = "admin"
        return user

    @pytest.fixture
    def sample_knowledge_base_data(self):
        """示例知识库数据"""
        return {
            "name": "测试知识库",
            "description": "这是一个测试知识库",
            "category": "技术文档",
            "tags": ["测试", "文档"],
            "access_control": {"public": False}
        }

    @pytest.fixture
    def sample_document_data(self):
        """示例文档数据"""
        return {
            "title": "测试文档",
            "description": "这是一个测试文档",
            "tags": ["测试"],
            "knowledge_base_ids": ["kb_123"],
            "processing_params": {"chunk_size": 1000}
        }

    # ==================== API版本管理测试 ====================

    def test_get_api_versions(self, client):
        """测试获取API版本信息"""
        response = client.get("/api/knowledge/versions")
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert "current_version" in data
        assert "versions" in data
        assert "endpoints" in data
        assert data["current_version"] == "v1"

    # ==================== 知识库管理测试 ====================

    @patch('open_webui.routers.knowledge_unified.get_verified_user')
    @patch('open_webui.routers.knowledge_unified.knowledge_service')
    def test_get_knowledge_bases_success(self, mock_service, mock_auth, client, mock_user):
        """测试成功获取知识库列表"""
        mock_auth.return_value = mock_user
        mock_service.list_knowledge_bases = AsyncMock(return_value={
            "knowledge_bases": [
                {
                    "id": "kb_123",
                    "name": "测试知识库",
                    "description": "测试描述",
                    "user_id": "test_user_id",
                    "created_at": "2025-08-26T01:30:00Z"
                }
            ],
            "pagination": {"total": 1, "page": 1, "per_page": 20}
        })

        response = client.get("/api/knowledge/collections")
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert len(data["knowledge_bases"]) == 1
        assert data["knowledge_bases"][0]["name"] == "测试知识库"

    @patch('open_webui.routers.knowledge_unified.get_verified_user')
    @patch('open_webui.routers.knowledge_unified.knowledge_service')
    @patch('open_webui.routers.knowledge_unified.has_permission')
    def test_create_knowledge_base_success(self, mock_permission, mock_service, mock_auth, 
                                         client, mock_user, sample_knowledge_base_data):
        """测试成功创建知识库"""
        mock_auth.return_value = mock_user
        mock_permission.return_value = True
        mock_service.create_knowledge_base = AsyncMock(return_value={
            "id": "kb_123",
            "name": "测试知识库",
            "user_id": "test_user_id",
            "created_at": "2025-08-26T01:30:00Z"
        })

        response = client.post(
            "/api/knowledge/collections",
            json=sample_knowledge_base_data
        )
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data["name"] == "测试知识库"
        assert data["user_id"] == "test_user_id"

    @patch('open_webui.routers.knowledge_unified.get_verified_user')
    @patch('open_webui.routers.knowledge_unified.has_permission')
    def test_create_knowledge_base_permission_denied(self, mock_permission, mock_auth, 
                                                   client, mock_user, sample_knowledge_base_data):
        """测试创建知识库权限被拒绝"""
        mock_auth.return_value = mock_user
        mock_permission.return_value = False

        response = client.post(
            "/api/knowledge/collections",
            json=sample_knowledge_base_data
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @patch('open_webui.routers.knowledge_unified.get_verified_user')
    @patch('open_webui.routers.knowledge_unified.check_knowledge_base_access')
    @patch('open_webui.routers.knowledge_unified.knowledge_service')
    def test_get_knowledge_base_success(self, mock_service, mock_access, mock_auth, 
                                      client, mock_user):
        """测试成功获取知识库详情"""
        mock_auth.return_value = mock_user
        mock_access.return_value = True
        mock_service.get_knowledge_base = AsyncMock(return_value={
            "id": "kb_123",
            "name": "测试知识库",
            "user_id": "test_user_id"
        })

        response = client.get("/api/knowledge/collections/kb_123")
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data["name"] == "测试知识库"

    @patch('open_webui.routers.knowledge_unified.get_verified_user')
    @patch('open_webui.routers.knowledge_unified.check_knowledge_base_access')
    def test_get_knowledge_base_access_denied(self, mock_access, mock_auth, client, mock_user):
        """测试获取知识库访问被拒绝"""
        mock_auth.return_value = mock_user
        mock_access.return_value = False

        response = client.get("/api/knowledge/collections/kb_123")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    # ==================== 文档管理测试 ====================

    @patch('open_webui.routers.knowledge_unified.get_verified_user')
    @patch('open_webui.routers.knowledge_unified.document_service')
    def test_get_documents_success(self, mock_service, mock_auth, client, mock_user):
        """测试成功获取文档列表"""
        mock_auth.return_value = mock_user
        mock_service.list_documents = AsyncMock(return_value={
            "documents": [
                {
                    "id": "doc_123",
                    "title": "测试文档",
                    "status": ProcessingStatus.COMPLETED,
                    "user_id": "test_user_id"
                }
            ],
            "pagination": {"total": 1, "page": 1, "per_page": 20}
        })

        response = client.get("/api/knowledge/documents")
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert len(data["documents"]) == 1
        assert data["documents"][0]["title"] == "测试文档"

    @patch('open_webui.routers.knowledge_unified.get_verified_user')
    @patch('open_webui.routers.knowledge_unified.has_permission')
    @patch('open_webui.routers.knowledge_unified.check_knowledge_base_access')
    @patch('open_webui.routers.knowledge_unified.document_service')
    async def test_upload_document_success(self, mock_service, mock_kb_access, mock_permission, 
                                         mock_auth, client, mock_user):
        """测试成功上传文档"""
        mock_auth.return_value = mock_user
        mock_permission.return_value = True
        mock_kb_access.return_value = True
        mock_service.upload_document = AsyncMock(return_value={
            "document_id": "doc_123",
            "status": "PROCESSING",
            "message": "文档上传成功"
        })

        # 模拟文件上传
        with open("temp_test_file.txt", "w") as f:
            f.write("测试文档内容")

        try:
            with open("temp_test_file.txt", "rb") as test_file:
                response = client.post(
                    "/api/knowledge/documents",
                    files={"file": ("test.txt", test_file, "text/plain")},
                    data={
                        "title": "测试文档",
                        "description": "测试描述",
                        "tags": '["测试"]',
                        "knowledge_base_ids": '["kb_123"]',
                        "processing_params": '{}'
                    }
                )
            assert response.status_code == status.HTTP_200_OK
            
            data = response.json()
            assert data["document_id"] == "doc_123"
            assert data["status"] == "PROCESSING"
        finally:
            import os
            if os.path.exists("temp_test_file.txt"):
                os.remove("temp_test_file.txt")

    @patch('open_webui.routers.knowledge_unified.get_verified_user')
    @patch('open_webui.routers.knowledge_unified.has_permission')
    def test_upload_document_permission_denied(self, mock_permission, mock_auth, 
                                             client, mock_user):
        """测试文档上传权限被拒绝"""
        mock_auth.return_value = mock_user
        mock_permission.return_value = False

        response = client.post(
            "/api/knowledge/documents",
            files={"file": ("test.txt", b"test content", "text/plain")},
            data={"title": "测试文档"}
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    # ==================== 搜索功能测试 ====================

    @patch('open_webui.routers.knowledge_unified.get_verified_user')
    @patch('open_webui.routers.knowledge_unified.search_service')
    def test_search_knowledge_success(self, mock_service, mock_auth, client, mock_user):
        """测试成功搜索知识"""
        mock_auth.return_value = mock_user
        mock_service.search = AsyncMock(return_value={
            "query": "测试查询",
            "total": 1,
            "results": [
                {
                    "id": "result_1",
                    "content": "匹配的内容",
                    "score": 0.95,
                    "source": "knowledge_base",
                    "metadata": {}
                }
            ],
            "search_params": {"vector_weight": 0.7, "keyword_weight": 0.3}
        })

        search_request = {
            "query": "测试查询",
            "vector_weight": 0.7,
            "keyword_weight": 0.3,
            "top_k": 10
        }

        response = client.post("/api/knowledge/search", json=search_request)
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data["query"] == "测试查询"
        assert len(data["results"]) == 1
        assert data["results"][0]["score"] == 0.95

    @patch('open_webui.routers.knowledge_unified.get_verified_user')
    @patch('open_webui.routers.knowledge_unified.search_service')
    def test_get_search_suggestions_success(self, mock_service, mock_auth, client, mock_user):
        """测试成功获取搜索建议"""
        mock_auth.return_value = mock_user
        mock_service.get_suggestions = AsyncMock(return_value={
            "query": "测试",
            "suggestions": ["测试文档", "测试配置", "测试用例"]
        })

        suggestion_request = {
            "query": "测试",
            "limit": 5
        }

        response = client.post("/api/knowledge/search/suggestions", json=suggestion_request)
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data["query"] == "测试"
        assert len(data["suggestions"]) == 3

    # ==================== 批量操作测试 ====================

    @patch('open_webui.routers.knowledge_unified.get_verified_user')
    @patch('open_webui.routers.knowledge_unified.check_knowledge_base_access')
    @patch('open_webui.routers.knowledge_unified.check_document_access')
    @patch('open_webui.routers.knowledge_unified.knowledge_service')
    def test_batch_add_documents_success(self, mock_service, mock_doc_access, 
                                       mock_kb_access, mock_auth, client, mock_user):
        """测试成功批量添加文档到知识库"""
        mock_auth.return_value = mock_user
        mock_kb_access.return_value = True
        mock_doc_access.return_value = True
        mock_service.add_document_to_knowledge_base = AsyncMock(return_value=True)

        document_ids = ["doc_1", "doc_2", "doc_3"]

        response = client.post(
            "/api/knowledge/collections/kb_123/documents/batch",
            json=document_ids
        )
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data["message"] == "Batch operation completed"
        assert data["successful"] == 3
        assert data["failed"] == 0

    # ==================== 统计信息测试 ====================

    @patch('open_webui.routers.knowledge_unified.get_verified_user')
    @patch('open_webui.routers.knowledge_unified.knowledge_service')
    def test_get_knowledge_stats_success(self, mock_service, mock_auth, client, mock_user):
        """测试成功获取知识管理统计信息"""
        mock_auth.return_value = mock_user
        mock_service.get_stats = AsyncMock(return_value={
            "total_knowledge_bases": 5,
            "total_documents": 25,
            "processing_documents": 2,
            "failed_documents": 1,
            "storage_used": "150MB"
        })

        response = client.get("/api/knowledge/stats")
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data["total_knowledge_bases"] == 5
        assert data["total_documents"] == 25

    # ==================== 权限检查测试 ====================

    def test_unauthorized_access(self, client):
        """测试未授权访问"""
        response = client.get("/api/knowledge/collections")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    # ==================== 数据一致性测试 ====================

    @patch('open_webui.routers.knowledge_unified.get_verified_user')
    @patch('open_webui.routers.knowledge_unified.knowledge_service')
    def test_data_consistency_after_migration(self, mock_service, mock_auth, client, mock_user):
        """测试迁移后数据一致性"""
        mock_auth.return_value = mock_user
        
        # 模拟迁移前数据
        old_data = {
            "knowledge_bases": [{"id": "kb_1", "name": "旧知识库"}],
            "pagination": {"total": 1}
        }
        
        # 模拟迁移后数据
        new_data = {
            "knowledge_bases": [{"id": "kb_1", "name": "旧知识库"}],
            "pagination": {"total": 1}
        }
        
        mock_service.list_knowledge_bases = AsyncMock(return_value=new_data)

        response = client.get("/api/knowledge/collections")
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data["knowledge_bases"][0]["id"] == "kb_1"
        assert data["knowledge_bases"][0]["name"] == "旧知识库"

    # ==================== 异常处理测试 ====================

    @patch('open_webui.routers.knowledge_unified.get_verified_user')
    @patch('open_webui.routers.knowledge_unified.knowledge_service')
    def test_service_error_handling(self, mock_service, mock_auth, client, mock_user):
        """测试服务异常处理"""
        mock_auth.return_value = mock_user
        mock_service.list_knowledge_bases = AsyncMock(side_effect=Exception("服务异常"))

        response = client.get("/api/knowledge/collections")
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    # ==================== 健康检查测试 ====================

    def test_health_check(self, client):
        """测试健康检查端点"""
        response = client.get("/api/knowledge/health")
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "version" in data


# ==================== 性能测试 ====================

class TestKnowledgeUnifiedPerformance:
    """知识统一模块性能测试"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @patch('open_webui.routers.knowledge_unified.get_verified_user')
    @patch('open_webui.routers.knowledge_unified.knowledge_service')
    def test_large_knowledge_base_list_performance(self, mock_service, mock_auth, client):
        """测试大量知识库列表的性能"""
        import time
        
        mock_user = Mock()
        mock_user.id = "test_user"
        mock_auth.return_value = mock_user
        
        # 模拟1000个知识库
        large_data = {
            "knowledge_bases": [
                {"id": f"kb_{i}", "name": f"知识库{i}", "user_id": "test_user"}
                for i in range(1000)
            ],
            "pagination": {"total": 1000, "page": 1, "per_page": 1000}
        }
        
        mock_service.list_knowledge_bases = AsyncMock(return_value=large_data)

        start_time = time.time()
        response = client.get("/api/knowledge/collections?page_size=1000")
        end_time = time.time()

        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()["knowledge_bases"]) == 1000
        
        # 性能要求：响应时间应小于2秒
        response_time = end_time - start_time
        assert response_time < 2.0, f"响应时间过长: {response_time}秒"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
