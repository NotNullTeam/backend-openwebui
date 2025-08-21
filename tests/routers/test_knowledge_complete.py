"""
知识管理模块完整测试套件
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, Mock, AsyncMock
from datetime import datetime
import json
import io

from open_webui.main import app


client = TestClient(app)


class TestKnowledgeEndpoints:
    """知识管理所有端点的完整测试"""
    
    # ===== GET /knowledge/documents 获取文档列表 =====
    @patch('open_webui.routers.knowledge_migrated.get_verified_user')
    @patch('open_webui.routers.knowledge_migrated.Files.get_files_by_user_id')
    def test_get_documents_list(self, mock_get_files, mock_user):
        """测试获取文档列表"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_get_files.return_value = [
            {
                "id": "doc-1",
                "filename": "RFC1234.pdf",
                "size": 1024000,
                "content_type": "application/pdf",
                "created_at": datetime.utcnow().isoformat(),
                "meta": {"pages": 50, "processed": True}
            },
            {
                "id": "doc-2",
                "filename": "华为配置手册.docx",
                "size": 2048000,
                "content_type": "application/docx",
                "created_at": datetime.utcnow().isoformat(),
                "meta": {"pages": 100, "processed": False}
            }
        ]
        
        response = client.get(
            "/api/v1/knowledge/documents",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["filename"] == "RFC1234.pdf"
    
    # ===== POST /knowledge/documents/upload 上传文档 =====
    @patch('open_webui.routers.knowledge_migrated.get_verified_user')
    @patch('open_webui.routers.knowledge_migrated.Files.insert_new_file')
    @patch('open_webui.routers.knowledge_migrated.process_document_async')
    def test_upload_document_success(self, mock_process, mock_insert, mock_user):
        """测试成功上传文档"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_insert.return_value = {
            "id": "doc-new",
            "filename": "test.pdf",
            "user_id": "user-123",
            "size": 1024,
            "content_type": "application/pdf"
        }
        mock_process.return_value = None
        
        file_content = b"PDF content here"
        files = {"file": ("test.pdf", io.BytesIO(file_content), "application/pdf")}
        
        response = client.post(
            "/api/v1/knowledge/documents/upload",
            files=files,
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "test.pdf"
        assert data["id"] == "doc-new"
    
    # ===== POST /knowledge/documents/{doc_id}/parse IDP解析 =====
    @patch('open_webui.routers.knowledge_migrated.get_verified_user')
    @patch('open_webui.routers.knowledge_migrated.Files.get_file_by_id')
    @patch('open_webui.routers.knowledge_migrated.parse_document_with_idp')
    def test_parse_document_with_idp(self, mock_parse, mock_get_file, mock_user):
        """测试IDP文档解析"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_get_file.return_value = {
            "id": "doc-123",
            "user_id": "user-123",
            "filename": "document.pdf",
            "meta": {}
        }
        mock_parse.return_value = {
            "status": "success",
            "pages": 10,
            "extracted_text": "文档内容...",
            "tables": [],
            "figures": []
        }
        
        response = client.post(
            "/api/v1/knowledge/documents/doc-123/parse",
            json={"parse_options": {"extract_tables": True}},
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["pages"] == 10
    
    # ===== POST /knowledge/search 混合检索 =====
    @patch('open_webui.routers.knowledge_migrated.get_verified_user')
    @patch('open_webui.routers.knowledge_migrated.hybrid_search')
    def test_hybrid_search(self, mock_search, mock_user):
        """测试混合检索"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_search.return_value = {
            "results": [
                {
                    "doc_id": "doc-1",
                    "chunk_id": "chunk-1",
                    "content": "IP地址冲突解决方案...",
                    "score": 0.95,
                    "metadata": {"source": "RFC1234.pdf", "page": 5}
                },
                {
                    "doc_id": "doc-2",
                    "chunk_id": "chunk-2",
                    "content": "DHCP配置步骤...",
                    "score": 0.88,
                    "metadata": {"source": "华为手册.docx", "page": 20}
                }
            ],
            "total": 2,
            "query": "IP地址冲突"
        }
        
        response = client.post(
            "/api/v1/knowledge/search",
            json={
                "query": "IP地址冲突",
                "top_k": 10,
                "filters": {"file_type": "pdf"}
            },
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 2
        assert data["results"][0]["score"] > data["results"][1]["score"]
    
    # ===== POST /knowledge/rerank 重排序 =====
    @patch('open_webui.routers.knowledge_migrated.get_verified_user')
    @patch('open_webui.routers.knowledge_migrated.rerank_results')
    def test_rerank_search_results(self, mock_rerank, mock_user):
        """测试搜索结果重排序"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_rerank.return_value = [
            {
                "doc_id": "doc-2",
                "content": "最相关内容",
                "rerank_score": 0.98
            },
            {
                "doc_id": "doc-1",
                "content": "次相关内容",
                "rerank_score": 0.85
            }
        ]
        
        response = client.post(
            "/api/v1/knowledge/rerank",
            json={
                "query": "IP配置",
                "documents": [
                    {"doc_id": "doc-1", "content": "内容1"},
                    {"doc_id": "doc-2", "content": "内容2"}
                ]
            },
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data[0]["rerank_score"] > data[1]["rerank_score"]
    
    # ===== DELETE /knowledge/documents/{doc_id} 删除文档 =====
    @patch('open_webui.routers.knowledge_migrated.get_verified_user')
    @patch('open_webui.routers.knowledge_migrated.Files.get_file_by_id')
    @patch('open_webui.routers.knowledge_migrated.Files.delete_file')
    @patch('open_webui.routers.knowledge_migrated.delete_document_vectors')
    def test_delete_document(self, mock_del_vectors, mock_del_file, mock_get_file, mock_user):
        """测试删除文档"""
        mock_user.return_value = MagicMock(id="user-123", role="user")
        mock_get_file.return_value = {
            "id": "doc-123",
            "user_id": "user-123"
        }
        mock_del_file.return_value = True
        mock_del_vectors.return_value = True
        
        response = client.delete(
            "/api/v1/knowledge/documents/doc-123",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        assert response.json()["message"] == "文档已删除"
    
    # ===== POST /knowledge/documents/batch-upload 批量上传 =====
    @patch('open_webui.routers.knowledge_migrated.get_verified_user')
    @patch('open_webui.routers.knowledge_migrated.Files.insert_new_file')
    @patch('open_webui.routers.knowledge_migrated.process_document_async')
    def test_batch_upload_documents(self, mock_process, mock_insert, mock_user):
        """测试批量上传文档"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_insert.side_effect = [
            {"id": f"doc-{i}", "filename": f"file{i}.pdf"} 
            for i in range(3)
        ]
        
        files = [
            ("files", (f"file{i}.pdf", io.BytesIO(b"content"), "application/pdf"))
            for i in range(3)
        ]
        
        response = client.post(
            "/api/v1/knowledge/documents/batch-upload",
            files=files,
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["uploaded"]) == 3
    
    # ===== GET /knowledge/suggestions 搜索建议 =====
    @patch('open_webui.routers.knowledge_migrated.get_verified_user')
    @patch('open_webui.routers.knowledge_migrated.get_search_suggestions')
    def test_get_search_suggestions(self, mock_suggestions, mock_user):
        """测试获取搜索建议"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_suggestions.return_value = [
            "IP地址冲突解决",
            "IP地址分配策略",
            "IP地址管理"
        ]
        
        response = client.get(
            "/api/v1/knowledge/suggestions?q=IP地址",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        assert all("IP地址" in s for s in data)
    
    # ===== POST /knowledge/index/rebuild 重建索引 =====
    @patch('open_webui.routers.knowledge_migrated.get_admin_user')
    @patch('open_webui.routers.knowledge_migrated.rebuild_vector_index')
    def test_rebuild_vector_index(self, mock_rebuild, mock_admin):
        """测试重建向量索引"""
        mock_admin.return_value = MagicMock(role="admin")
        mock_rebuild.return_value = {
            "status": "completed",
            "documents_processed": 100,
            "time_taken": 300
        }
        
        response = client.post(
            "/api/v1/knowledge/index/rebuild",
            headers={"Authorization": "Bearer admin-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["documents_processed"] == 100
    
    # ===== 边界条件和异常测试 =====
    @patch('open_webui.routers.knowledge_migrated.get_verified_user')
    def test_upload_invalid_file_type(self, mock_user):
        """测试上传无效文件类型"""
        mock_user.return_value = MagicMock(id="user-123")
        
        files = {"file": ("test.exe", io.BytesIO(b"exe content"), "application/exe")}
        
        response = client.post(
            "/api/v1/knowledge/documents/upload",
            files=files,
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 400
        assert "不支持的文件类型" in response.json()["detail"]
    
    @patch('open_webui.routers.knowledge_migrated.get_verified_user')
    def test_upload_file_size_limit(self, mock_user):
        """测试文件大小限制"""
        mock_user.return_value = MagicMock(id="user-123")
        
        # 创建超大文件（假设限制为100MB）
        large_content = b"x" * (100 * 1024 * 1024 + 1)
        files = {"file": ("large.pdf", io.BytesIO(large_content), "application/pdf")}
        
        response = client.post(
            "/api/v1/knowledge/documents/upload",
            files=files,
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 413
    
    @patch('open_webui.routers.knowledge_migrated.get_verified_user')
    @patch('open_webui.routers.knowledge_migrated.hybrid_search')
    def test_search_empty_query(self, mock_search, mock_user):
        """测试空查询"""
        mock_user.return_value = MagicMock(id="user-123")
        
        response = client.post(
            "/api/v1/knowledge/search",
            json={"query": "", "top_k": 10},
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 400
    
    @patch('open_webui.routers.knowledge_migrated.get_verified_user')
    @patch('open_webui.routers.knowledge_migrated.Files.get_file_by_id')
    @patch('open_webui.routers.knowledge_migrated.parse_document_with_idp')
    def test_parse_document_timeout(self, mock_parse, mock_get_file, mock_user):
        """测试文档解析超时"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_get_file.return_value = {"id": "doc-123", "user_id": "user-123"}
        mock_parse.side_effect = TimeoutError("IDP service timeout")
        
        response = client.post(
            "/api/v1/knowledge/documents/doc-123/parse",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 504
