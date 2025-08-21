"""
文件管理增强功能测试用例
"""
import pytest
from fastapi.testclient import TestClient
from fastapi import UploadFile
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime
import json
import io
from typing import List

from open_webui.main import app
from open_webui.models.users import UserModel
from open_webui.models.files import FileModel


@pytest.fixture
def verified_user():
    """已验证用户fixture"""
    return UserModel(
        id="user_123",
        email="user@example.com",
        name="Test User",
        role="user",
        is_active=True
    )


@pytest.fixture
def auth_headers():
    """认证头"""
    return {"Authorization": "Bearer test_token"}


class TestFileBatchUpload:
    """文件批量上传测试"""
    
    def test_batch_upload_success(self, client: TestClient, auth_headers, verified_user):
        """测试成功批量上传文件"""
        with patch('open_webui.routers.files.get_verified_user', return_value=verified_user):
            with patch('open_webui.routers.files.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value = mock_db
                
                # 创建测试文件
                files = [
                    ("files", ("test1.txt", b"Test content 1", "text/plain")),
                    ("files", ("test2.pdf", b"PDF content", "application/pdf")),
                    ("files", ("test3.doc", b"Doc content", "application/msword"))
                ]
                
                # 模拟文件保存
                with patch('open_webui.routers.files.save_file') as mock_save:
                    mock_save.return_value = {"path": "/uploads/test.txt", "size": 100}
                    
                    response = client.post(
                        "/api/v1/files/batch",
                        headers=auth_headers,
                        files=files
                    )
                    
                    assert response.status_code == 200
                    data = response.json()
                    assert data["status"] == "success"
                    assert "uploaded_files" in data["data"]
                    assert "failed_files" in data["data"]
                    assert data["data"]["total_files"] == 3
    
    def test_batch_upload_partial_failure(self, client: TestClient, auth_headers, verified_user):
        """测试部分文件上传失败的情况"""
        with patch('open_webui.routers.files.get_verified_user', return_value=verified_user):
            with patch('open_webui.routers.files.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value = mock_db
                
                files = [
                    ("files", ("valid.txt", b"Valid content", "text/plain")),
                    ("files", ("invalid.exe", b"Invalid content", "application/x-msdownload")),
                    ("files", ("large.bin", b"x" * 100000000, "application/octet-stream"))
                ]
                
                with patch('open_webui.routers.files.save_file') as mock_save:
                    def save_side_effect(file, user_id):
                        if file.filename == "valid.txt":
                            return {"path": "/uploads/valid.txt", "size": 13}
                        elif file.filename == "invalid.exe":
                            raise ValueError("不支持的文件类型")
                        else:
                            raise ValueError("文件大小超过限制")
                    
                    mock_save.side_effect = save_side_effect
                    
                    response = client.post(
                        "/api/v1/files/batch",
                        headers=auth_headers,
                        files=files
                    )
                    
                    assert response.status_code == 200
                    data = response.json()
                    assert data["status"] == "partial_success"
                    assert len(data["data"]["uploaded_files"]) == 1
                    assert len(data["data"]["failed_files"]) == 2
    
    def test_batch_upload_empty_files(self, client: TestClient, auth_headers, verified_user):
        """测试空文件列表上传"""
        with patch('open_webui.routers.files.get_verified_user', return_value=verified_user):
            response = client.post(
                "/api/v1/files/batch",
                headers=auth_headers
            )
            
            assert response.status_code == 400
            data = response.json()
            assert "detail" in data
    
    def test_batch_upload_with_metadata(self, client: TestClient, auth_headers, verified_user):
        """测试带元数据的批量上传"""
        with patch('open_webui.routers.files.get_verified_user', return_value=verified_user):
            with patch('open_webui.routers.files.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value = mock_db
                
                files = [
                    ("files", ("report.pdf", b"PDF content", "application/pdf"))
                ]
                
                # 添加元数据
                data = {
                    "category": "reports",
                    "tags": json.dumps(["monthly", "2024", "finance"]),
                    "description": "Monthly financial report"
                }
                
                with patch('open_webui.routers.files.save_file') as mock_save:
                    mock_save.return_value = {"path": "/uploads/report.pdf", "size": 1024}
                    
                    response = client.post(
                        "/api/v1/files/batch",
                        headers=auth_headers,
                        files=files,
                        data=data
                    )
                    
                    assert response.status_code == 200
                    data = response.json()
                    assert data["status"] == "success"
    
    def test_batch_upload_duplicate_handling(self, client: TestClient, auth_headers, verified_user):
        """测试重复文件处理"""
        with patch('open_webui.routers.files.get_verified_user', return_value=verified_user):
            with patch('open_webui.routers.files.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value = mock_db
                
                # 模拟已存在的文件
                existing_file = Mock()
                existing_file.filename = "existing.txt"
                existing_file.hash = "abc123"
                mock_db.query().filter_by().first.return_value = existing_file
                
                files = [
                    ("files", ("existing.txt", b"Duplicate content", "text/plain"))
                ]
                
                response = client.post(
                    "/api/v1/files/batch",
                    headers=auth_headers,
                    files=files
                )
                
                assert response.status_code in [200, 409]


class TestFileMetadataManagement:
    """文件元数据管理测试"""
    
    def test_get_file_metadata(self, client: TestClient, auth_headers, verified_user):
        """测试获取文件元数据"""
        with patch('open_webui.routers.files.get_verified_user', return_value=verified_user):
            with patch('open_webui.routers.files.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value = mock_db
                
                # 模拟文件
                mock_file = Mock()
                mock_file.id = "file_123"
                mock_file.filename = "document.pdf"
                mock_file.size = 2048
                mock_file.content_type = "application/pdf"
                mock_file.created_at = datetime.utcnow()
                mock_file.updated_at = datetime.utcnow()
                mock_file.meta = {
                    "title": "Important Document",
                    "author": "John Doe",
                    "tags": ["important", "2024"],
                    "category": "documents",
                    "description": "This is an important document",
                    "custom_fields": {
                        "department": "IT",
                        "project": "Network Upgrade"
                    }
                }
                
                mock_db.query().filter_by().first.return_value = mock_file
                
                response = client.get(
                    "/api/v1/files/file_123/metadata",
                    headers=auth_headers
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "success"
                assert data["data"]["file_id"] == "file_123"
                assert data["data"]["filename"] == "document.pdf"
                assert "metadata" in data["data"]
                assert data["data"]["metadata"]["title"] == "Important Document"
    
    def test_get_file_metadata_not_found(self, client: TestClient, auth_headers, verified_user):
        """测试获取不存在文件的元数据"""
        with patch('open_webui.routers.files.get_verified_user', return_value=verified_user):
            with patch('open_webui.routers.files.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value = mock_db
                
                mock_db.query().filter_by().first.return_value = None
                
                response = client.get(
                    "/api/v1/files/nonexistent/metadata",
                    headers=auth_headers
                )
                
                assert response.status_code == 404
    
    def test_update_file_metadata(self, client: TestClient, auth_headers, verified_user):
        """测试更新文件元数据"""
        with patch('open_webui.routers.files.get_verified_user', return_value=verified_user):
            with patch('open_webui.routers.files.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value = mock_db
                
                # 模拟文件
                mock_file = Mock()
                mock_file.id = "file_123"
                mock_file.user_id = verified_user.id
                mock_file.meta = {
                    "title": "Old Title",
                    "tags": ["old"]
                }
                
                mock_db.query().filter_by().first.return_value = mock_file
                
                update_data = {
                    "title": "New Title",
                    "author": "Jane Smith",
                    "tags": ["new", "updated", "2024"],
                    "category": "reports",
                    "description": "Updated description",
                    "custom_fields": {
                        "priority": "high",
                        "status": "reviewed"
                    }
                }
                
                response = client.put(
                    "/api/v1/files/file_123/metadata",
                    headers=auth_headers,
                    json=update_data
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "success"
                # 验证元数据被更新
                assert mock_file.meta["title"] == "New Title"
                assert mock_file.meta["author"] == "Jane Smith"
                assert len(mock_file.meta["tags"]) == 3
    
    def test_update_file_metadata_unauthorized(self, client: TestClient, auth_headers, verified_user):
        """测试未授权更新文件元数据"""
        with patch('open_webui.routers.files.get_verified_user', return_value=verified_user):
            with patch('open_webui.routers.files.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value = mock_db
                
                # 模拟其他用户的文件
                mock_file = Mock()
                mock_file.id = "file_123"
                mock_file.user_id = "other_user_id"
                
                mock_db.query().filter_by().first.return_value = mock_file
                
                update_data = {"title": "Hacked Title"}
                
                response = client.put(
                    "/api/v1/files/file_123/metadata",
                    headers=auth_headers,
                    json=update_data
                )
                
                assert response.status_code == 403
    
    def test_partial_update_metadata(self, client: TestClient, auth_headers, verified_user):
        """测试部分更新元数据"""
        with patch('open_webui.routers.files.get_verified_user', return_value=verified_user):
            with patch('open_webui.routers.files.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value = mock_db
                
                # 模拟文件
                mock_file = Mock()
                mock_file.id = "file_123"
                mock_file.user_id = verified_user.id
                mock_file.meta = {
                    "title": "Original Title",
                    "author": "Original Author",
                    "tags": ["tag1", "tag2"]
                }
                
                mock_db.query().filter_by().first.return_value = mock_file
                
                # 只更新标题
                update_data = {"title": "Updated Title"}
                
                response = client.put(
                    "/api/v1/files/file_123/metadata",
                    headers=auth_headers,
                    json=update_data
                )
                
                assert response.status_code == 200
                # 验证只有标题被更新，其他字段保持不变
                assert mock_file.meta["title"] == "Updated Title"
                assert mock_file.meta["author"] == "Original Author"
                assert mock_file.meta["tags"] == ["tag1", "tag2"]
    
    def test_delete_file_metadata(self, client: TestClient, auth_headers, verified_user):
        """测试删除文件元数据"""
        with patch('open_webui.routers.files.get_verified_user', return_value=verified_user):
            with patch('open_webui.routers.files.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value = mock_db
                
                # 模拟文件
                mock_file = Mock()
                mock_file.id = "file_123"
                mock_file.user_id = verified_user.id
                mock_file.meta = {
                    "title": "To be deleted",
                    "tags": ["delete", "me"]
                }
                
                mock_db.query().filter_by().first.return_value = mock_file
                
                response = client.delete(
                    "/api/v1/files/file_123/metadata",
                    headers=auth_headers
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "success"
                # 验证元数据被清空
                assert mock_file.meta == {}


class TestFileSearchWithMetadata:
    """基于元数据的文件搜索测试"""
    
    def test_search_files_by_tags(self, client: TestClient, auth_headers, verified_user):
        """测试按标签搜索文件"""
        with patch('open_webui.routers.files.get_verified_user', return_value=verified_user):
            with patch('open_webui.routers.files.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value = mock_db
                
                # 模拟搜索结果
                mock_files = [
                    Mock(id="1", filename="file1.pdf", meta={"tags": ["report", "2024"]}),
                    Mock(id="2", filename="file2.doc", meta={"tags": ["report", "monthly"]})
                ]
                
                mock_db.query().filter().all.return_value = mock_files
                
                response = client.get(
                    "/api/v1/files/search?tags=report",
                    headers=auth_headers
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "success"
                assert len(data["data"]) == 2
    
    def test_search_files_by_category(self, client: TestClient, auth_headers, verified_user):
        """测试按分类搜索文件"""
        with patch('open_webui.routers.files.get_verified_user', return_value=verified_user):
            with patch('open_webui.routers.files.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value = mock_db
                
                mock_files = [
                    Mock(id="1", filename="doc1.pdf", meta={"category": "documents"}),
                    Mock(id="2", filename="doc2.pdf", meta={"category": "documents"})
                ]
                
                mock_db.query().filter().all.return_value = mock_files
                
                response = client.get(
                    "/api/v1/files/search?category=documents",
                    headers=auth_headers
                )
                
                assert response.status_code == 200
                data = response.json()
                assert len(data["data"]) == 2
    
    def test_search_files_advanced(self, client: TestClient, auth_headers, verified_user):
        """测试高级文件搜索"""
        with patch('open_webui.routers.files.get_verified_user', return_value=verified_user):
            with patch('open_webui.routers.files.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value = mock_db
                
                mock_files = [
                    Mock(
                        id="1",
                        filename="report.pdf",
                        size=1024,
                        created_at=datetime.utcnow(),
                        meta={
                            "title": "Annual Report",
                            "category": "reports",
                            "tags": ["annual", "2024", "finance"]
                        }
                    )
                ]
                
                mock_db.query().filter().filter().filter().all.return_value = mock_files
                
                response = client.get(
                    "/api/v1/files/search?query=annual&category=reports&tags=finance&size_min=500&size_max=2000",
                    headers=auth_headers
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "success"
