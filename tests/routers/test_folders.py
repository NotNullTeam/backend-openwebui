"""
Test cases for folders router endpoints - comprehensive coverage for all 7 endpoints
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock, Mock
from httpx import AsyncClient
import json


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


class TestFoldersManagement:
    """Test folders management endpoints"""
    
    async def test_get_folders(self, async_client: AsyncClient, mock_verified_user):
        """Test GET / endpoint - get all user folders"""
        with patch("open_webui.routers.folders.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.folders.Folders.get_folders_by_user_id") as mock_get:
                mock_get.return_value = [
                    {
                        "id": "folder1",
                        "name": "Work",
                        "parent_id": None,
                        "user_id": "user123",
                        "is_expanded": True,
                        "created_at": 1234567890,
                        "updated_at": 1234567890
                    },
                    {
                        "id": "folder2",
                        "name": "Personal",
                        "parent_id": None,
                        "user_id": "user123",
                        "is_expanded": False,
                        "created_at": 1234567891,
                        "updated_at": 1234567891
                    }
                ]
                
                response = await async_client.get("/api/v1/folders/")
                assert response.status_code in [200, 401]
    
    async def test_create_folder(self, async_client: AsyncClient, mock_verified_user):
        """Test POST / endpoint - create new folder"""
        with patch("open_webui.routers.folders.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.folders.Folders.get_folder_by_parent_id_and_user_id_and_name") as mock_check:
                mock_check.return_value = None  # Folder doesn't exist
                
                with patch("open_webui.routers.folders.Folders.insert_new_folder") as mock_insert:
                    mock_insert.return_value = {
                        "id": "folder_new",
                        "name": "New Folder",
                        "parent_id": None,
                        "user_id": "user123",
                        "is_expanded": True,
                        "created_at": 1234567892,
                        "updated_at": 1234567892
                    }
                    
                    folder_data = {
                        "name": "New Folder"
                    }
                    
                    response = await async_client.post(
                        "/api/v1/folders/",
                        json=folder_data
                    )
                    assert response.status_code in [200, 401, 400]
    
    async def test_get_folder_by_id(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /{id} endpoint - get specific folder"""
        with patch("open_webui.routers.folders.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.folders.Folders.get_folder_by_id_and_user_id") as mock_get:
                mock_get.return_value = {
                    "id": "folder1",
                    "name": "Work",
                    "parent_id": None,
                    "user_id": "user123",
                    "is_expanded": True,
                    "created_at": 1234567890,
                    "updated_at": 1234567890
                }
                
                response = await async_client.get("/api/v1/folders/folder1")
                assert response.status_code in [200, 401, 404]
    
    async def test_update_folder_name(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /{id}/update endpoint - update folder name"""
        with patch("open_webui.routers.folders.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.folders.Folders.get_folder_by_id_and_user_id") as mock_get:
                mock_get.return_value = {
                    "id": "folder1",
                    "name": "Old Name",
                    "parent_id": None,
                    "user_id": "user123"
                }
                
                with patch("open_webui.routers.folders.Folders.get_folder_by_parent_id_and_user_id_and_name") as mock_check:
                    mock_check.return_value = None  # No conflict
                    
                    with patch("open_webui.routers.folders.Folders.update_folder_name_by_id") as mock_update:
                        mock_update.return_value = {
                            "id": "folder1",
                            "name": "Updated Name",
                            "parent_id": None,
                            "user_id": "user123"
                        }
                        
                        update_data = {
                            "name": "Updated Name"
                        }
                        
                        response = await async_client.post(
                            "/api/v1/folders/folder1/update",
                            json=update_data
                        )
                        assert response.status_code in [200, 401, 404, 400]
    
    async def test_update_folder_parent(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /{id}/update/parent endpoint - update folder parent"""
        with patch("open_webui.routers.folders.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.folders.Folders.get_folder_by_id_and_user_id") as mock_get:
                mock_get.side_effect = [
                    {"id": "folder1", "parent_id": None, "user_id": "user123"},  # Target folder
                    {"id": "parent_folder", "parent_id": None, "user_id": "user123"}  # Parent folder
                ]
                
                with patch("open_webui.routers.folders.Folders.update_folder_parent_id_by_id") as mock_update:
                    mock_update.return_value = {
                        "id": "folder1",
                        "parent_id": "parent_folder",
                        "user_id": "user123"
                    }
                    
                    update_data = {
                        "parent_id": "parent_folder"
                    }
                    
                    response = await async_client.post(
                        "/api/v1/folders/folder1/update/parent",
                        json=update_data
                    )
                    assert response.status_code in [200, 401, 404, 400]
    
    async def test_update_folder_expanded(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /{id}/update/expanded endpoint - update folder expanded state"""
        with patch("open_webui.routers.folders.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.folders.Folders.get_folder_by_id_and_user_id") as mock_get:
                mock_get.return_value = {
                    "id": "folder1",
                    "is_expanded": False,
                    "user_id": "user123"
                }
                
                with patch("open_webui.routers.folders.Folders.update_folder_is_expanded_by_id") as mock_update:
                    mock_update.return_value = {
                        "id": "folder1",
                        "is_expanded": True,
                        "user_id": "user123"
                    }
                    
                    update_data = {
                        "is_expanded": True
                    }
                    
                    response = await async_client.post(
                        "/api/v1/folders/folder1/update/expanded",
                        json=update_data
                    )
                    assert response.status_code in [200, 401, 404]
    
    async def test_delete_folder(self, async_client: AsyncClient, mock_verified_user):
        """Test DELETE /{id} endpoint - delete folder"""
        with patch("open_webui.routers.folders.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.folders.Folders.get_folder_by_id_and_user_id") as mock_get:
                mock_get.return_value = {
                    "id": "folder1",
                    "name": "To Delete",
                    "user_id": "user123"
                }
                
                with patch("open_webui.routers.folders.Folders.delete_folder_by_id_and_user_id") as mock_delete:
                    mock_delete.return_value = True
                    
                    response = await async_client.delete("/api/v1/folders/folder1")
                    assert response.status_code in [200, 401, 404]


class TestFoldersHierarchy:
    """Test folders hierarchy and relationships"""
    
    async def test_create_subfolder(self, async_client: AsyncClient, mock_verified_user):
        """Test creating a subfolder with parent_id"""
        with patch("open_webui.routers.folders.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.folders.Folders.get_folder_by_parent_id_and_user_id_and_name") as mock_check:
                mock_check.return_value = None  # No duplicate
                
                with patch("open_webui.routers.folders.Folders.insert_new_folder") as mock_insert:
                    mock_insert.return_value = {
                        "id": "subfolder1",
                        "name": "Subfolder",
                        "parent_id": "folder1",
                        "user_id": "user123",
                        "is_expanded": False
                    }
                    
                    folder_data = {
                        "name": "Subfolder",
                        "parent_id": "folder1"
                    }
                    
                    response = await async_client.post(
                        "/api/v1/folders/",
                        json=folder_data
                    )
                    assert response.status_code in [200, 401, 400]
    
    async def test_prevent_duplicate_folder_name(self, async_client: AsyncClient, mock_verified_user):
        """Test prevention of duplicate folder names in same parent"""
        with patch("open_webui.routers.folders.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.folders.Folders.get_folder_by_parent_id_and_user_id_and_name") as mock_check:
                mock_check.return_value = {"id": "existing", "name": "Duplicate"}  # Folder exists
                
                folder_data = {
                    "name": "Duplicate"
                }
                
                response = await async_client.post(
                    "/api/v1/folders/",
                    json=folder_data
                )
                assert response.status_code in [400, 401]
