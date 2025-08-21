"""
文档处理状态端点测试
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from datetime import datetime

from open_webui.main import app


client = TestClient(app)


class TestDocumentProcessingStatus:
    """文档处理状态端点测试"""
    
    @patch('open_webui.routers.knowledge_migrated.get_verified_user')
    @patch('open_webui.models.files.Files.get_file_by_id')
    @patch('open_webui.services.document_processor.get_document_processing_status')
    def test_get_processing_status_success(self, mock_get_status, mock_get_file, mock_get_user):
        """测试成功获取文档处理状态"""
        # 模拟用户
        mock_user = MagicMock()
        mock_user.id = "user-123"
        mock_user.role = "user"
        mock_get_user.return_value = mock_user
        
        # 模拟文件
        mock_file = MagicMock()
        mock_file.id = "doc-123"
        mock_file.user_id = "user-123"
        mock_file.meta = {
            "processing_status": "completed",
            "processing_progress": 100
        }
        mock_get_file.return_value = mock_file
        
        # 模拟处理状态
        mock_status = {
            "status": "completed",
            "progress": 100,
            "error": None,
            "started_at": "2025-01-21T10:00:00",
            "completed_at": "2025-01-21T10:05:00",
            "retry_count": 0,
            "is_processing": False
        }
        mock_get_status.return_value = mock_status
        
        # 发送请求
        response = client.get(
            "/api/v1/knowledge/documents/doc-123/processing-status",
            headers={"Authorization": "Bearer test-token"}
        )
        
        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["progress"] == 100
        assert data["is_processing"] is False
    
    @patch('open_webui.routers.knowledge_migrated.get_verified_user')
    @patch('open_webui.models.files.Files.get_file_by_id')
    def test_get_processing_status_not_found(self, mock_get_file, mock_get_user):
        """测试文档不存在的情况"""
        mock_user = MagicMock()
        mock_user.id = "user-123"
        mock_get_user.return_value = mock_user
        
        mock_get_file.return_value = None
        
        response = client.get(
            "/api/v1/knowledge/documents/doc-not-exist/processing-status",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 404
        assert "文档不存在" in response.json()["detail"]
    
    @patch('open_webui.routers.knowledge_migrated.get_verified_user')
    @patch('open_webui.models.files.Files.get_file_by_id')
    def test_get_processing_status_forbidden(self, mock_get_file, mock_get_user):
        """测试无权访问文档的情况"""
        # 模拟非所有者用户
        mock_user = MagicMock()
        mock_user.id = "user-456"
        mock_user.role = "user"
        mock_get_user.return_value = mock_user
        
        # 模拟文件（所有者是另一个用户）
        mock_file = MagicMock()
        mock_file.id = "doc-123"
        mock_file.user_id = "user-123"  # 不同的用户ID
        mock_get_file.return_value = mock_file
        
        response = client.get(
            "/api/v1/knowledge/documents/doc-123/processing-status",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 403
        assert "无权访问该文档" in response.json()["detail"]
    
    @patch('open_webui.routers.knowledge_migrated.get_verified_user')
    @patch('open_webui.models.files.Files.get_file_by_id')
    @patch('open_webui.services.document_processor.get_document_processing_status')
    def test_get_processing_status_admin_access(self, mock_get_status, mock_get_file, mock_get_user):
        """测试管理员访问其他用户文档"""
        # 模拟管理员用户
        mock_user = MagicMock()
        mock_user.id = "admin-123"
        mock_user.role = "admin"
        mock_get_user.return_value = mock_user
        
        # 模拟文件（所有者是另一个用户）
        mock_file = MagicMock()
        mock_file.id = "doc-123"
        mock_file.user_id = "user-456"
        mock_get_file.return_value = mock_file
        
        mock_status = {
            "status": "processing",
            "progress": 50,
            "error": None,
            "is_processing": True
        }
        mock_get_status.return_value = mock_status
        
        response = client.get(
            "/api/v1/knowledge/documents/doc-123/processing-status",
            headers={"Authorization": "Bearer admin-token"}
        )
        
        # 管理员应该能访问
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "processing"
        assert data["progress"] == 50
    
    @patch('open_webui.routers.knowledge_migrated.get_verified_user')
    @patch('open_webui.models.files.Files.get_file_by_id')
    @patch('open_webui.services.document_processor.get_document_processing_status')
    def test_get_processing_status_with_error(self, mock_get_status, mock_get_file, mock_get_user):
        """测试处理失败的状态"""
        mock_user = MagicMock()
        mock_user.id = "user-123"
        mock_get_user.return_value = mock_user
        
        mock_file = MagicMock()
        mock_file.id = "doc-123"
        mock_file.user_id = "user-123"
        mock_get_file.return_value = mock_file
        
        # 模拟处理失败状态
        mock_status = {
            "status": "failed",
            "progress": 30,
            "error": "文档解析失败：无法识别的文件格式",
            "started_at": "2025-01-21T10:00:00",
            "completed_at": None,
            "retry_count": 3,
            "is_processing": False
        }
        mock_get_status.return_value = mock_status
        
        response = client.get(
            "/api/v1/knowledge/documents/doc-123/processing-status",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert data["error"] == "文档解析失败：无法识别的文件格式"
        assert data["retry_count"] == 3
        assert data["is_processing"] is False
