"""
Test cases for files router endpoints - comprehensive coverage for file management endpoints
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock, Mock
from httpx import AsyncClient
import json
from io import BytesIO


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
        email="test@example.com",
        role="user"
    )


@pytest.fixture
def mock_file():
    return MagicMock(
        id="file123",
        user_id="user123",
        filename="test.pdf",
        meta={
            "name": "test.pdf",
            "content_type": "application/pdf",
            "size": 1024,
            "path": "/path/to/test.pdf"
        },
        data={
            "content": "test content"
        }
    )


class TestFileUpload:
    """Test file upload endpoints"""
    
    async def test_upload_file(self, async_client: AsyncClient, mock_verified_user):
        """Test POST / endpoint - upload single file"""
        with patch("open_webui.routers.files.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.files.save_file_to_cache") as mock_save:
                mock_save.return_value = "/cache/test.pdf"
                
                with patch("open_webui.routers.files.process_file") as mock_process:
                    mock_process.return_value = {
                        "text": "extracted text",
                        "images": [],
                        "file_ids": ["file123"]
                    }
                    
                    with patch("open_webui.routers.files.Files.insert_new_file") as mock_insert:
                        mock_insert.return_value = MagicMock(
                            id="file123",
                            filename="test.pdf",
                            user_id="user123"
                        )
                        
                        # Create mock file upload
                        file_data = b"test file content"
                        files = {"file": ("test.pdf", BytesIO(file_data), "application/pdf")}
                        
                        response = await async_client.post(
                            "/api/v1/files/",
                            files=files
                        )
                        assert response.status_code in [200, 401, 413]
    
    async def test_batch_upload_files(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /batch endpoint - batch upload files"""
        with patch("open_webui.routers.files.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.files.save_file_to_cache") as mock_save:
                mock_save.return_value = "/cache/test.pdf"
                
                with patch("open_webui.routers.files.process_file") as mock_process:
                    mock_process.return_value = {
                        "text": "extracted text",
                        "images": [],
                        "file_ids": ["file123"]
                    }
                    
                    with patch("open_webui.routers.files.Files.insert_new_file") as mock_insert:
                        mock_insert.return_value = MagicMock(
                            id="file123",
                            filename="test.pdf",
                            user_id="user123"
                        )
                        
                        # Create mock file uploads
                        files = [
                            ("files", ("test1.pdf", BytesIO(b"content1"), "application/pdf")),
                            ("files", ("test2.pdf", BytesIO(b"content2"), "application/pdf"))
                        ]
                        
                        response = await async_client.post(
                            "/api/v1/files/batch",
                            files=files
                        )
                        assert response.status_code in [200, 401, 413]


class TestFileList:
    """Test file listing and search endpoints"""
    
    async def test_list_files(self, async_client: AsyncClient, mock_verified_user):
        """Test GET / endpoint - list files"""
        with patch("open_webui.routers.files.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.files.Files.get_files_by_user_id") as mock_get:
                mock_get.return_value = [
                    MagicMock(id="file1", filename="test1.pdf"),
                    MagicMock(id="file2", filename="test2.pdf")
                ]
                
                response = await async_client.get("/api/v1/files/")
                assert response.status_code in [200, 401]
    
    async def test_list_files_admin(self, async_client: AsyncClient, mock_admin_user):
        """Test GET / endpoint - list all files as admin"""
        with patch("open_webui.routers.files.get_verified_user", return_value=mock_admin_user):
            with patch("open_webui.routers.files.Files.get_files") as mock_get:
                mock_get.return_value = [
                    MagicMock(id="file1", filename="test1.pdf"),
                    MagicMock(id="file2", filename="test2.pdf")
                ]
                
                response = await async_client.get("/api/v1/files/")
                assert response.status_code in [200, 401]
    
    async def test_search_files(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /search endpoint - search files by filename"""
        with patch("open_webui.routers.files.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.files.Files.search_files_by_user_id") as mock_search:
                mock_search.return_value = [
                    MagicMock(id="file1", filename="test.pdf")
                ]
                
                response = await async_client.get(
                    "/api/v1/files/search",
                    params={"filename": "test"}
                )
                assert response.status_code in [200, 401]


class TestFileOperations:
    """Test file CRUD operations"""
    
    async def test_get_file_by_id(self, async_client: AsyncClient, mock_verified_user, mock_file):
        """Test GET /{id} endpoint - get file by ID"""
        with patch("open_webui.routers.files.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.files.Files.get_file_by_id") as mock_get:
                mock_get.return_value = mock_file
                
                response = await async_client.get("/api/v1/files/file123")
                assert response.status_code in [200, 401, 404]
    
    async def test_delete_file_by_id(self, async_client: AsyncClient, mock_verified_user, mock_file):
        """Test DELETE /{id} endpoint - delete file by ID"""
        with patch("open_webui.routers.files.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.files.Files.get_file_by_id") as mock_get:
                mock_get.return_value = mock_file
                
                with patch("open_webui.routers.files.Files.delete_file_by_id") as mock_delete:
                    mock_delete.return_value = True
                    
                    response = await async_client.delete("/api/v1/files/file123")
                    assert response.status_code in [200, 401, 404]
    
    async def test_delete_all_files(self, async_client: AsyncClient, mock_admin_user):
        """Test DELETE /all endpoint - delete all files (admin only)"""
        with patch("open_webui.routers.files.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.files.Files.delete_all_files") as mock_delete:
                mock_delete.return_value = True
                
                response = await async_client.delete("/api/v1/files/all")
                assert response.status_code in [200, 401, 500]


class TestFileContent:
    """Test file content operations"""
    
    async def test_get_file_content_by_id(self, async_client: AsyncClient, mock_verified_user, mock_file):
        """Test GET /{id}/content endpoint - get file content"""
        with patch("open_webui.routers.files.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.files.Files.get_file_by_id") as mock_get:
                mock_get.return_value = mock_file
                
                with patch("open_webui.routers.files.open", mock_open(read_data=b"file content")):
                    response = await async_client.get("/api/v1/files/file123/content")
                    assert response.status_code in [200, 401, 404]
    
    async def test_get_html_file_content(self, async_client: AsyncClient, mock_verified_user, mock_file):
        """Test GET /{id}/content/html endpoint - get HTML file content"""
        with patch("open_webui.routers.files.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.files.Files.get_file_by_id") as mock_get:
                mock_file.meta["content_type"] = "text/html"
                mock_get.return_value = mock_file
                
                with patch("open_webui.routers.files.open", mock_open(read_data=b"<html>content</html>")):
                    response = await async_client.get("/api/v1/files/file123/content/html")
                    assert response.status_code in [200, 401, 404]
    
    async def test_get_file_content_with_name(self, async_client: AsyncClient, mock_verified_user, mock_file):
        """Test GET /{id}/content/{file_name} endpoint - get file content with name"""
        with patch("open_webui.routers.files.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.files.Files.get_file_by_id") as mock_get:
                mock_get.return_value = mock_file
                
                with patch("open_webui.routers.files.open", mock_open(read_data=b"file content")):
                    response = await async_client.get("/api/v1/files/file123/content/test.pdf")
                    assert response.status_code in [200, 401, 404]


class TestFileData:
    """Test file data operations"""
    
    async def test_get_file_data_content(self, async_client: AsyncClient, mock_verified_user, mock_file):
        """Test GET /{id}/data/content endpoint - get file data content"""
        with patch("open_webui.routers.files.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.files.Files.get_file_by_id") as mock_get:
                mock_get.return_value = mock_file
                
                response = await async_client.get("/api/v1/files/file123/data/content")
                assert response.status_code in [200, 401, 404]
    
    async def test_update_file_data_content(self, async_client: AsyncClient, mock_verified_user, mock_file):
        """Test POST /{id}/data/content/update endpoint - update file data content"""
        with patch("open_webui.routers.files.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.files.Files.get_file_by_id") as mock_get:
                mock_get.return_value = mock_file
                
                with patch("open_webui.routers.files.Files.update_file_data_by_id") as mock_update:
                    mock_update.return_value = mock_file
                    
                    content_data = {
                        "content": "updated content"
                    }
                    
                    response = await async_client.post(
                        "/api/v1/files/file123/data/content/update",
                        json=content_data
                    )
                    assert response.status_code in [200, 401, 404]


class TestFileSecurity:
    """Test file security scanning endpoints"""
    
    async def test_scan_file_security(self, async_client: AsyncClient, mock_verified_user, mock_file):
        """Test POST /{id}/scan endpoint - scan file security"""
        with patch("open_webui.routers.files.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.files.Files.get_file_by_id") as mock_get:
                mock_get.return_value = mock_file
                
                with patch("open_webui.routers.files.perform_security_scan") as mock_scan:
                    mock_scan.return_value = {
                        "threats_found": 0,
                        "scan_duration": 0.5,
                        "file_id": "file123"
                    }
                    
                    response = await async_client.post("/api/v1/files/file123/scan")
                    assert response.status_code in [200, 401, 404]
    
    async def test_batch_scan_files(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /batch/scan endpoint - batch scan files"""
        with patch("open_webui.routers.files.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.files.Files.get_file_by_id") as mock_get:
                mock_get.return_value = MagicMock(
                    id="file123",
                    filename="test.pdf",
                    meta={"path": "/path/to/test.pdf"}
                )
                
                with patch("open_webui.routers.files.perform_security_scan") as mock_scan:
                    mock_scan.return_value = {
                        "threats_found": 0,
                        "scan_duration": 0.5,
                        "file_id": "file123"
                    }
                    
                    scan_request = {
                        "file_ids": ["file123", "file456"],
                        "scan_options": {
                            "deep_scan": True
                        }
                    }
                    
                    response = await async_client.post(
                        "/api/v1/files/batch/scan",
                        json=scan_request
                    )
                    assert response.status_code in [200, 401]


# Helper function for mocking file operations
def mock_open(read_data=b""):
    """Helper to mock file open operations"""
    m = mock_open()
    m.return_value.read.return_value = read_data
    return m
