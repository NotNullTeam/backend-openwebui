"""
知识管理模块单元测试
"""

import pytest
import json
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI, UploadFile
from io import BytesIO

from open_webui.routers.knowledge_migrated import router
from open_webui.models.files import FileModel

# 创建测试应用
app = FastAPI()
app.include_router(router, prefix="/api/v1")
client = TestClient(app)

class TestKnowledgeRouter:
    """知识管理路由测试类"""
    
    @pytest.fixture
    def mock_user(self):
        """模拟用户"""
        user = Mock()
        user.id = "test_user_id"
        user.email = "test@example.com"
        user.role = "user"
        return user
    
    @pytest.fixture
    def mock_file(self):
        """模拟文件对象"""
        file = Mock(spec=FileModel)
        file.id = "test_file_id"
        file.filename = "test_document.pdf"
        file.user_id = "test_user_id"
        file.created_at = "2024-01-01T00:00:00Z"
        file.updated_at = "2024-01-01T00:00:00Z"
        file.meta = {
            "size": 1024,
            "content_type": "application/pdf",
            "vendor": "华为",
            "tags": ["网络", "故障"]
        }
        return file
    
    @pytest.fixture
    def sample_upload_file(self):
        """示例上传文件"""
        content = b"This is a test PDF content"
        file = UploadFile(
            filename="test.pdf",
            file=BytesIO(content),
            headers={"content-type": "application/pdf"}
        )
        return file
    
    @patch('open_webui.routers.knowledge_migrated.get_verified_user')
    @patch('open_webui.routers.knowledge_migrated.Files')
    def test_get_documents_success(self, mock_files, mock_get_user, mock_user):
        """测试获取文档列表成功"""
        # 设置模拟
        mock_get_user.return_value = mock_user
        mock_files.get_files_by_user_id.return_value = [self.mock_file()]
        
        # 发送请求
        response = client.get("/api/v1/documents")
        
        # 验证结果
        assert response.status_code == 200
        data = response.json()
        assert "documents" in data
        assert "pagination" in data
        assert len(data["documents"]) == 1
        
        # 验证调用
        mock_files.get_files_by_user_id.assert_called_once()
    
    @patch('open_webui.routers.knowledge_migrated.get_verified_user')
    @patch('open_webui.routers.knowledge_migrated.Files')
    def test_get_documents_with_filters(self, mock_files, mock_get_user, mock_user):
        """测试带过滤条件获取文档列表"""
        # 设置模拟
        mock_get_user.return_value = mock_user
        mock_files.get_files_by_user_id.return_value = []
        
        # 发送请求
        response = client.get("/api/v1/documents?vendor=华为&tags=网络,故障&page=1&pageSize=10")
        
        # 验证结果
        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["per_page"] == 10
    
    @patch('open_webui.routers.knowledge_migrated.get_verified_user')
    @patch('open_webui.routers.knowledge_migrated.Files')
    @patch('open_webui.routers.knowledge_migrated.queue_document_for_processing')
    @patch('open_webui.routers.knowledge_migrated.allowed_file')
    def test_upload_document_success(self, mock_allowed_file, mock_queue_processing, 
                                   mock_files, mock_get_user, mock_user):
        """测试上传文档成功"""
        # 设置模拟
        mock_get_user.return_value = mock_user
        mock_allowed_file.return_value = True
        mock_files.insert_new_file.return_value = self.mock_file()
        mock_queue_processing.return_value = True
        
        # 创建测试文件
        test_content = b"Test PDF content"
        files = {"file": ("test.pdf", BytesIO(test_content), "application/pdf")}
        data = {"vendor": "华为", "tags": ["网络", "故障"]}
        
        # 发送请求
        response = client.post("/api/v1/documents", files=files, data=data)
        
        # 验证结果
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["status"] == "QUEUED"
        assert "文档已加入处理队列" in response_data["message"]
        
        # 验证调用
        mock_files.insert_new_file.assert_called_once()
        mock_queue_processing.assert_called_once()
    
    @patch('open_webui.routers.knowledge_migrated.get_verified_user')
    @patch('open_webui.routers.knowledge_migrated.allowed_file')
    def test_upload_document_invalid_file_type(self, mock_allowed_file, mock_get_user, mock_user):
        """测试上传无效文件类型"""
        # 设置模拟
        mock_get_user.return_value = mock_user
        mock_allowed_file.return_value = False
        
        # 创建测试文件
        test_content = b"Test content"
        files = {"file": ("test.exe", BytesIO(test_content), "application/octet-stream")}
        
        # 发送请求
        response = client.post("/api/v1/documents", files=files)
        
        # 验证结果
        assert response.status_code == 400
        assert "不支持的文件类型" in response.json()["detail"]
    
    @patch('open_webui.routers.knowledge_migrated.get_verified_user')
    @patch('open_webui.routers.knowledge_migrated.allowed_file')
    @patch('open_webui.routers.knowledge_migrated.MAX_FILE_SIZE', 100)  # 设置小的文件大小限制
    def test_upload_document_file_too_large(self, mock_allowed_file, mock_get_user, mock_user):
        """测试上传文件过大"""
        # 设置模拟
        mock_get_user.return_value = mock_user
        mock_allowed_file.return_value = True
        
        # 创建大文件
        large_content = b"x" * 200  # 超过限制的100字节
        files = {"file": ("large.pdf", BytesIO(large_content), "application/pdf")}
        
        # 发送请求
        response = client.post("/api/v1/documents", files=files)
        
        # 验证结果
        assert response.status_code == 400
        assert "文件大小超过限制" in response.json()["detail"]
    
    @patch('open_webui.routers.knowledge_migrated.get_verified_user')
    @patch('open_webui.routers.knowledge_migrated.Files')
    @patch('open_webui.routers.knowledge_migrated.get_document_processing_status')
    def test_get_document_detail_success(self, mock_get_status, mock_files, mock_get_user, mock_user):
        """测试获取文档详情成功"""
        # 设置模拟
        mock_get_user.return_value = mock_user
        mock_file = self.mock_file()
        mock_files.get_file_by_id.return_value = mock_file
        mock_get_status.return_value = {
            "status": "COMPLETED",
            "progress": 100,
            "completed_at": "2024-01-01T01:00:00Z"
        }
        
        # 发送请求
        response = client.get(f"/api/v1/documents/{mock_file.id}")
        
        # 验证结果
        assert response.status_code == 200
        data = response.json()
        assert data["docId"] == mock_file.id
        assert data["fileName"] == mock_file.filename
        assert data["status"] == "COMPLETED"
        assert data["progress"] == 100
    
    @patch('open_webui.routers.knowledge_migrated.get_verified_user')
    @patch('open_webui.routers.knowledge_migrated.Files')
    def test_get_document_detail_not_found(self, mock_files, mock_get_user, mock_user):
        """测试获取不存在的文档详情"""
        # 设置模拟
        mock_get_user.return_value = mock_user
        mock_files.get_file_by_id.return_value = None
        
        # 发送请求
        response = client.get("/api/v1/documents/nonexistent_id")
        
        # 验证结果
        assert response.status_code == 404
        assert "文档不存在" in response.json()["detail"]
    
    @patch('open_webui.routers.knowledge_migrated.get_verified_user')
    @patch('open_webui.routers.knowledge_migrated.Files')
    def test_get_document_detail_permission_denied(self, mock_files, mock_get_user, mock_user):
        """测试无权限访问文档详情"""
        # 设置模拟
        mock_get_user.return_value = mock_user
        mock_file = self.mock_file()
        mock_file.user_id = "other_user_id"  # 不同用户
        mock_files.get_file_by_id.return_value = mock_file
        
        # 发送请求
        response = client.get(f"/api/v1/documents/{mock_file.id}")
        
        # 验证结果
        assert response.status_code == 403
        assert "无权访问" in response.json()["detail"]
    
    @patch('open_webui.routers.knowledge_migrated.get_verified_user')
    @patch('open_webui.routers.knowledge_migrated.Files')
    @patch('open_webui.routers.knowledge_migrated.get_document_processing_status')
    def test_get_processing_status_endpoint(self, mock_get_status, mock_files, mock_get_user, mock_user):
        """测试获取文档处理状态端点"""
        # 设置模拟
        mock_get_user.return_value = mock_user
        mock_file = self.mock_file()
        mock_files.get_file_by_id.return_value = mock_file
        mock_status = {
            "status": "PROCESSING",
            "progress": 50,
            "error": None,
            "retry_count": 0,
            "is_processing": True
        }
        mock_get_status.return_value = mock_status
        
        # 发送请求
        response = client.get(f"/api/v1/documents/{mock_file.id}/processing-status")
        
        # 验证结果
        assert response.status_code == 200
        data = response.json()
        assert data == mock_status
    
    @patch('open_webui.routers.knowledge_migrated.get_verified_user')
    @patch('open_webui.routers.knowledge_migrated.Files')
    @patch('open_webui.routers.knowledge_migrated.document_processor')
    async def test_retry_document_processing_success(self, mock_processor, mock_files, mock_get_user, mock_user):
        """测试重试文档处理成功"""
        # 设置模拟
        mock_get_user.return_value = mock_user
        mock_file = self.mock_file()
        mock_files.get_file_by_id.return_value = mock_file
        mock_processor.retry_failed_document = AsyncMock(return_value=True)
        
        # 发送请求
        response = client.post(f"/api/v1/documents/{mock_file.id}/retry-processing")
        
        # 验证结果
        assert response.status_code == 200
        data = response.json()
        assert "重新加入处理队列" in data["message"]
    
    @patch('open_webui.routers.knowledge_migrated.get_verified_user')
    @patch('open_webui.routers.knowledge_migrated.Files')
    @patch('open_webui.routers.knowledge_migrated.document_processor')
    async def test_cancel_document_processing_success(self, mock_processor, mock_files, mock_get_user, mock_user):
        """测试取消文档处理成功"""
        # 设置模拟
        mock_get_user.return_value = mock_user
        mock_file = self.mock_file()
        mock_files.get_file_by_id.return_value = mock_file
        mock_processor.cancel_processing = AsyncMock(return_value=True)
        
        # 发送请求
        response = client.delete(f"/api/v1/documents/{mock_file.id}/cancel-processing")
        
        # 验证结果
        assert response.status_code == 200
        data = response.json()
        assert "处理已取消" in data["message"]
    
    @patch('open_webui.routers.knowledge_migrated.get_verified_user')
    @patch('open_webui.routers.knowledge_migrated.Files')
    def test_update_document_metadata_success(self, mock_files, mock_get_user, mock_user):
        """测试更新文档元数据成功"""
        # 设置模拟
        mock_get_user.return_value = mock_user
        mock_file = self.mock_file()
        mock_files.get_file_by_id.return_value = mock_file
        mock_files.update_file_metadata_by_id.return_value = True
        
        # 发送请求
        update_data = {"tags": ["新标签"], "vendor": "思科"}
        response = client.put(f"/api/v1/documents/{mock_file.id}", json=update_data)
        
        # 验证结果
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "文档元数据更新成功"
        
        # 验证调用
        mock_files.update_file_metadata_by_id.assert_called_once()
    
    @patch('open_webui.routers.knowledge_migrated.get_verified_user')
    @patch('open_webui.routers.knowledge_migrated.Files')
    def test_delete_document_success(self, mock_files, mock_get_user, mock_user):
        """测试删除文档成功"""
        # 设置模拟
        mock_get_user.return_value = mock_user
        mock_file = self.mock_file()
        mock_files.get_file_by_id.return_value = mock_file
        mock_files.delete_file_by_id.return_value = True
        
        # 发送请求
        response = client.delete(f"/api/v1/documents/{mock_file.id}")
        
        # 验证结果
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "文档删除成功"
        
        # 验证调用
        mock_files.delete_file_by_id.assert_called_once_with(mock_file.id)

class TestKnowledgeSearchRouter:
    """知识搜索路由测试类"""
    
    @pytest.fixture
    def mock_user(self):
        """模拟用户"""
        user = Mock()
        user.id = "test_user_id"
        user.email = "test@example.com"
        user.role = "user"
        return user
    
    @pytest.fixture
    def sample_search_results(self):
        """示例搜索结果"""
        return [
            {
                "content": "这是搜索结果内容1",
                "metadata": {
                    "source": "doc1.pdf",
                    "page": 1,
                    "file_id": "file1"
                },
                "score": 0.95
            },
            {
                "content": "这是搜索结果内容2",
                "metadata": {
                    "source": "doc2.pdf",
                    "page": 2,
                    "file_id": "file2"
                },
                "score": 0.85
            }
        ]
    
    @patch('open_webui.routers.knowledge_migrated.get_verified_user')
    @patch('open_webui.routers.knowledge_migrated.get_retrieval_vector_db')
    @patch('open_webui.routers.knowledge_migrated.similarity_normalizer')
    def test_search_knowledge_success(self, mock_normalizer, mock_get_vector_db, 
                                    mock_get_user, mock_user, sample_search_results):
        """测试知识搜索成功"""
        # 设置模拟
        mock_get_user.return_value = mock_user
        mock_vector_db = Mock()
        mock_get_vector_db.return_value = mock_vector_db
        mock_vector_db.search.return_value = sample_search_results
        mock_normalizer.normalize_scores.return_value = sample_search_results
        
        # 发送请求
        search_data = {
            "query": "网络故障排查",
            "topK": 5,
            "vendor": "华为"
        }
        response = client.post("/api/v1/knowledge/search", json=search_data)
        
        # 验证结果
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert len(data["results"]) == 2
        assert data["results"][0]["score"] == 0.95
        
        # 验证调用
        mock_vector_db.search.assert_called_once()
        mock_normalizer.normalize_scores.assert_called_once()
    
    @patch('open_webui.routers.knowledge_migrated.get_verified_user')
    def test_search_knowledge_empty_query(self, mock_get_user, mock_user):
        """测试空查询搜索"""
        # 设置模拟
        mock_get_user.return_value = mock_user
        
        # 发送请求
        search_data = {"query": "", "topK": 5}
        response = client.post("/api/v1/knowledge/search", json=search_data)
        
        # 验证结果
        assert response.status_code == 400
        assert "查询不能为空" in response.json()["detail"]
    
    @patch('open_webui.routers.knowledge_migrated.get_verified_user')
    @patch('open_webui.routers.knowledge_migrated.get_retrieval_vector_db')
    def test_search_knowledge_vector_db_unavailable(self, mock_get_vector_db, mock_get_user, mock_user):
        """测试向量数据库不可用"""
        # 设置模拟
        mock_get_user.return_value = mock_user
        mock_get_vector_db.return_value = None
        
        # 发送请求
        search_data = {"query": "网络故障", "topK": 5}
        response = client.post("/api/v1/knowledge/search", json=search_data)
        
        # 验证结果
        assert response.status_code == 503
        assert "向量数据库不可用" in response.json()["detail"]
    
    @patch('open_webui.routers.knowledge_migrated.get_verified_user')
    @patch('open_webui.routers.knowledge_migrated.get_retrieval_vector_db')
    def test_get_search_suggestions_success(self, mock_get_vector_db, mock_get_user, mock_user):
        """测试获取搜索建议成功"""
        # 设置模拟
        mock_get_user.return_value = mock_user
        mock_vector_db = Mock()
        mock_get_vector_db.return_value = mock_vector_db
        mock_vector_db.get_suggestions.return_value = [
            "网络故障排查",
            "路由配置错误",
            "交换机端口问题"
        ]
        
        # 发送请求
        response = client.get("/api/v1/knowledge/search-suggestions?query=网络")
        
        # 验证结果
        assert response.status_code == 200
        data = response.json()
        assert "suggestions" in data
        assert len(data["suggestions"]) == 3
        assert "网络故障排查" in data["suggestions"]
    
    @patch('open_webui.routers.knowledge_migrated.get_verified_user')
    @patch('open_webui.routers.knowledge_migrated.get_retrieval_vector_db')
    def test_get_knowledge_tags_success(self, mock_get_vector_db, mock_get_user, mock_user):
        """测试获取知识标签成功"""
        # 设置模拟
        mock_get_user.return_value = mock_user
        mock_vector_db = Mock()
        mock_get_vector_db.return_value = mock_vector_db
        mock_vector_db.get_tags.return_value = [
            {"tag": "网络", "count": 10},
            {"tag": "故障", "count": 8},
            {"tag": "华为", "count": 5}
        ]
        
        # 发送请求
        response = client.get("/api/v1/knowledge/tags")
        
        # 验证结果
        assert response.status_code == 200
        data = response.json()
        assert "tags" in data
        assert len(data["tags"]) == 3
        assert data["tags"][0]["tag"] == "网络"
        assert data["tags"][0]["count"] == 10

if __name__ == "__main__":
    pytest.main([__file__])
