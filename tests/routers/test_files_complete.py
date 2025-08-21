"""
文件管理模块完整测试套件
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime
import io
import os

from open_webui.main import app


client = TestClient(app)


class TestFilesEndpoints:
    """文件管理所有端点的完整测试"""
    
    # ===== POST /files/upload 上传文件 =====
    @patch('open_webui.routers.files.get_verified_user')
    @patch('open_webui.routers.files.Files.insert_new_file')
    @patch('open_webui.routers.files.save_file_to_storage')
    def test_upload_file_success(self, mock_save, mock_insert, mock_user):
        """测试成功上传文件"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_save.return_value = "/storage/files/file-123.pdf"
        mock_insert.return_value = {
            "id": "file-123",
            "filename": "report.pdf",
            "size": 1024000,
            "content_type": "application/pdf",
            "path": "/storage/files/file-123.pdf",
            "user_id": "user-123",
            "created_at": datetime.utcnow().isoformat()
        }
        
        file_content = b"PDF content here"
        files = {"file": ("report.pdf", io.BytesIO(file_content), "application/pdf")}
        
        response = client.post(
            "/api/v1/files/upload",
            files=files,
            data={"description": "月度报告"},
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "report.pdf"
        assert data["id"] == "file-123"
    
    # ===== GET /files 获取文件列表 =====
    @patch('open_webui.routers.files.get_verified_user')
    @patch('open_webui.routers.files.Files.get_files_by_user')
    def test_get_files_list(self, mock_get_files, mock_user):
        """测试获取文件列表"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_get_files.return_value = [
            {
                "id": "file-1",
                "filename": "config.json",
                "size": 2048,
                "content_type": "application/json",
                "created_at": datetime.utcnow().isoformat()
            },
            {
                "id": "file-2",
                "filename": "image.png",
                "size": 500000,
                "content_type": "image/png",
                "created_at": datetime.utcnow().isoformat()
            }
        ]
        
        response = client.get(
            "/api/v1/files?page=1&page_size=10",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["items"][0]["filename"] == "config.json"
    
    # ===== GET /files/{file_id}/download 下载文件 =====
    @patch('open_webui.routers.files.get_verified_user')
    @patch('open_webui.routers.files.Files.get_file_by_id')
    @patch('open_webui.routers.files.get_file_content')
    def test_download_file(self, mock_content, mock_get_file, mock_user):
        """测试下载文件"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_get_file.return_value = {
            "id": "file-123",
            "user_id": "user-123",
            "filename": "document.pdf",
            "content_type": "application/pdf",
            "path": "/storage/files/file-123.pdf"
        }
        mock_content.return_value = b"PDF content"
        
        response = client.get(
            "/api/v1/files/file-123/download",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert response.headers["content-disposition"] == 'attachment; filename="document.pdf"'
    
    # ===== DELETE /files/{file_id} 删除文件 =====
    @patch('open_webui.routers.files.get_verified_user')
    @patch('open_webui.routers.files.Files.get_file_by_id')
    @patch('open_webui.routers.files.Files.delete_file')
    @patch('open_webui.routers.files.delete_file_from_storage')
    def test_delete_file(self, mock_del_storage, mock_del_db, mock_get_file, mock_user):
        """测试删除文件"""
        mock_user.return_value = MagicMock(id="user-123", role="user")
        mock_get_file.return_value = {
            "id": "file-123",
            "user_id": "user-123",
            "path": "/storage/files/file-123.pdf"
        }
        mock_del_db.return_value = True
        mock_del_storage.return_value = True
        
        response = client.delete(
            "/api/v1/files/file-123",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        assert response.json()["message"] == "文件已删除"
    
    # ===== POST /files/batch-upload 批量上传 =====
    @patch('open_webui.routers.files.get_verified_user')
    @patch('open_webui.routers.files.Files.batch_insert')
    @patch('open_webui.routers.files.save_file_to_storage')
    def test_batch_upload_files(self, mock_save, mock_batch, mock_user):
        """测试批量上传文件"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_save.side_effect = [f"/storage/file-{i}.txt" for i in range(3)]
        mock_batch.return_value = [
            {"id": f"file-{i}", "filename": f"file{i}.txt"} 
            for i in range(3)
        ]
        
        files = [
            ("files", (f"file{i}.txt", io.BytesIO(b"content"), "text/plain"))
            for i in range(3)
        ]
        
        response = client.post(
            "/api/v1/files/batch-upload",
            files=files,
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["uploaded"]) == 3
        assert data["total"] == 3
    
    # ===== DELETE /files/batch 批量删除 =====
    @patch('open_webui.routers.files.get_verified_user')
    @patch('open_webui.routers.files.Files.get_files_by_ids')
    @patch('open_webui.routers.files.Files.batch_delete')
    @patch('open_webui.routers.files.delete_files_from_storage')
    def test_batch_delete_files(self, mock_del_storage, mock_batch_del, mock_get_files, mock_user):
        """测试批量删除文件"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_get_files.return_value = [
            {"id": f"file-{i}", "user_id": "user-123", "path": f"/storage/file-{i}.txt"}
            for i in range(3)
        ]
        mock_batch_del.return_value = 3
        mock_del_storage.return_value = 3
        
        response = client.delete(
            "/api/v1/files/batch",
            json={"file_ids": ["file-0", "file-1", "file-2"]},
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] == 3
    
    # ===== PUT /files/{file_id}/metadata 更新元数据 =====
    @patch('open_webui.routers.files.get_verified_user')
    @patch('open_webui.routers.files.Files.get_file_by_id')
    @patch('open_webui.routers.files.Files.update_metadata')
    def test_update_file_metadata(self, mock_update, mock_get_file, mock_user):
        """测试更新文件元数据"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_get_file.return_value = {
            "id": "file-123",
            "user_id": "user-123",
            "meta": {}
        }
        mock_update.return_value = {
            "id": "file-123",
            "meta": {
                "description": "更新后的描述",
                "tags": ["重要", "技术文档"]
            }
        }
        
        response = client.put(
            "/api/v1/files/file-123/metadata",
            json={
                "description": "更新后的描述",
                "tags": ["重要", "技术文档"]
            },
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["meta"]["description"] == "更新后的描述"
    
    # ===== POST /files/{file_id}/scan 安全扫描 =====
    @patch('open_webui.routers.files.get_verified_user')
    @patch('open_webui.routers.files.Files.get_file_by_id')
    @patch('open_webui.routers.files.scan_file_for_security')
    def test_scan_file_security(self, mock_scan, mock_get_file, mock_user):
        """测试文件安全扫描"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_get_file.return_value = {
            "id": "file-123",
            "user_id": "user-123",
            "path": "/storage/file-123.exe"
        }
        mock_scan.return_value = {
            "status": "safe",
            "threats": [],
            "scan_time": 1.5
        }
        
        response = client.post(
            "/api/v1/files/file-123/scan",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "safe"
        assert len(data["threats"]) == 0
    
    # ===== GET /files/stats 文件统计 =====
    @patch('open_webui.routers.files.get_verified_user')
    @patch('open_webui.routers.files.Files.get_user_stats')
    def test_get_file_statistics(self, mock_stats, mock_user):
        """测试获取文件统计"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_stats.return_value = {
            "total_files": 50,
            "total_size": 100000000,
            "file_types": {
                "pdf": 20,
                "docx": 15,
                "png": 10,
                "other": 5
            },
            "storage_used": 95000000,
            "storage_limit": 1000000000
        }
        
        response = client.get(
            "/api/v1/files/stats",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_files"] == 50
        assert data["file_types"]["pdf"] == 20
    
    # ===== POST /files/{file_id}/share 文件分享 =====
    @patch('open_webui.routers.files.get_verified_user')
    @patch('open_webui.routers.files.Files.get_file_by_id')
    @patch('open_webui.routers.files.create_share_link')
    def test_share_file(self, mock_share, mock_get_file, mock_user):
        """测试创建文件分享链接"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_get_file.return_value = {
            "id": "file-123",
            "user_id": "user-123",
            "filename": "share.pdf"
        }
        mock_share.return_value = {
            "share_id": "share-abc123",
            "url": "https://example.com/share/abc123",
            "expires_at": datetime.utcnow().isoformat()
        }
        
        response = client.post(
            "/api/v1/files/file-123/share",
            json={
                "expires_in": 86400,  # 24小时
                "password": "secure123"
            },
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "share_id" in data
        assert "url" in data
    
    # ===== 边界条件和异常测试 =====
    @patch('open_webui.routers.files.get_verified_user')
    def test_upload_file_size_exceeded(self, mock_user):
        """测试上传文件超过大小限制"""
        mock_user.return_value = MagicMock(id="user-123")
        
        # 创建超大文件（假设限制为50MB）
        large_content = b"x" * (50 * 1024 * 1024 + 1)
        files = {"file": ("large.pdf", io.BytesIO(large_content), "application/pdf")}
        
        response = client.post(
            "/api/v1/files/upload",
            files=files,
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 413
        assert "文件太大" in response.json()["detail"]
    
    @patch('open_webui.routers.files.get_verified_user')
    def test_upload_unsupported_file_type(self, mock_user):
        """测试上传不支持的文件类型"""
        mock_user.return_value = MagicMock(id="user-123")
        
        files = {"file": ("malware.exe", io.BytesIO(b"exe content"), "application/x-msdownload")}
        
        response = client.post(
            "/api/v1/files/upload",
            files=files,
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 400
        assert "不支持的文件类型" in response.json()["detail"]
    
    @patch('open_webui.routers.files.get_verified_user')
    @patch('open_webui.routers.files.Files.get_file_by_id')
    def test_download_nonexistent_file(self, mock_get_file, mock_user):
        """测试下载不存在的文件"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_get_file.return_value = None
        
        response = client.get(
            "/api/v1/files/nonexistent/download",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 404
        assert "文件不存在" in response.json()["detail"]
    
    @patch('open_webui.routers.files.get_verified_user')
    @patch('open_webui.routers.files.Files.get_file_by_id')
    def test_access_other_user_file(self, mock_get_file, mock_user):
        """测试访问其他用户的文件"""
        mock_user.return_value = MagicMock(id="user-123", role="user")
        mock_get_file.return_value = {
            "id": "file-456",
            "user_id": "user-456"  # 不同用户
        }
        
        response = client.get(
            "/api/v1/files/file-456/download",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 403
        assert "无权访问" in response.json()["detail"]
    
    @patch('open_webui.routers.files.get_verified_user')
    @patch('open_webui.routers.files.Files.get_file_by_id')
    @patch('open_webui.routers.files.scan_file_for_security')
    def test_scan_file_with_virus(self, mock_scan, mock_get_file, mock_user):
        """测试扫描包含病毒的文件"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_get_file.return_value = {
            "id": "file-123",
            "user_id": "user-123",
            "path": "/storage/infected.exe"
        }
        mock_scan.return_value = {
            "status": "infected",
            "threats": ["Trojan.Generic", "Malware.Suspicious"],
            "scan_time": 2.3
        }
        
        response = client.post(
            "/api/v1/files/file-123/scan",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "infected"
        assert len(data["threats"]) > 0
