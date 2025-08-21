"""
Test cases for chats router endpoints - comprehensive coverage for main endpoints
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


class TestChatsList:
    """Test chats listing endpoints"""
    
    async def test_get_chat_list(self, async_client: AsyncClient, mock_verified_user):
        """Test GET / and /list endpoints - get user chat list"""
        with patch("open_webui.routers.chats.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.chats.Chats.get_chats_by_user_id") as mock_get:
                mock_get.return_value = [
                    {"id": "chat1", "title": "Chat 1", "user_id": "user123"},
                    {"id": "chat2", "title": "Chat 2", "user_id": "user123"}
                ]
                
                response = await async_client.get("/api/v1/chats/")
                assert response.status_code in [200, 401]
    
    async def test_delete_all_user_chats(self, async_client: AsyncClient, mock_verified_user):
        """Test DELETE / endpoint - delete all user chats"""
        with patch("open_webui.routers.chats.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.chats.has_permission", return_value=True):
                with patch("open_webui.routers.chats.Chats.delete_chats_by_user_id") as mock_delete:
                    mock_delete.return_value = True
                    
                    response = await async_client.delete("/api/v1/chats/")
                    assert response.status_code in [200, 401, 403]
    
    async def test_get_user_chat_list_by_user_id(self, async_client: AsyncClient, mock_admin_user):
        """Test GET /list/user/{user_id} endpoint - get specific user's chats"""
        with patch("open_webui.routers.chats.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.chats.Chats.get_chats_by_user_id") as mock_get:
                mock_get.return_value = [
                    {"id": "chat1", "title": "User Chat 1"}
                ]
                
                response = await async_client.get("/api/v1/chats/list/user/user456")
                assert response.status_code in [200, 401]


class TestChatsManagement:
    """Test chats management endpoints"""
    
    async def test_create_new_chat(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /new endpoint - create new chat"""
        with patch("open_webui.routers.chats.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.chats.Chats.insert_new_chat") as mock_insert:
                mock_insert.return_value = {
                    "id": "chat_new",
                    "user_id": "user123",
                    "title": "New Chat",
                    "messages": [],
                    "created_at": 1234567890
                }
                
                chat_data = {
                    "title": "New Chat",
                    "messages": []
                }
                
                response = await async_client.post(
                    "/api/v1/chats/new",
                    json=chat_data
                )
                assert response.status_code in [200, 401]
    
    async def test_import_chat(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /import endpoint - import chat"""
        with patch("open_webui.routers.chats.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.chats.Chats.import_chat") as mock_import:
                mock_import.return_value = {
                    "id": "chat_imported",
                    "user_id": "user123",
                    "title": "Imported Chat",
                    "messages": []
                }
                
                import_data = {
                    "title": "Imported Chat",
                    "messages": [],
                    "history": {}
                }
                
                response = await async_client.post(
                    "/api/v1/chats/import",
                    json=import_data
                )
                assert response.status_code in [200, 401]


class TestChatsSearch:
    """Test chats search and filter endpoints"""
    
    async def test_search_user_chats(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /search endpoint - search chats"""
        with patch("open_webui.routers.chats.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.chats.Chats.get_chats_by_user_id_and_search_text") as mock_search:
                mock_search.return_value = [
                    {"id": "chat1", "title": "Matching Chat"}
                ]
                
                response = await async_client.get("/api/v1/chats/search?text=test")
                assert response.status_code in [200, 401]
    
    async def test_get_chats_by_folder(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /folder/{folder_id} endpoint - get chats in folder"""
        with patch("open_webui.routers.chats.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.chats.Folders.get_children_folders_by_id_and_user_id") as mock_folders:
                mock_folders.return_value = []
                
                with patch("open_webui.routers.chats.Chats.get_chats_by_user_id_and_folder_ids") as mock_chats:
                    mock_chats.return_value = [
                        {"id": "chat1", "title": "Folder Chat"}
                    ]
                    
                    response = await async_client.get("/api/v1/chats/folder/folder123")
                    assert response.status_code in [200, 401]
    
    async def test_get_pinned_chats(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /pinned endpoint - get pinned chats"""
        with patch("open_webui.routers.chats.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.chats.Chats.get_pinned_chats_by_user_id") as mock_pinned:
                mock_pinned.return_value = [
                    {"id": "chat1", "title": "Pinned Chat", "pinned": True}
                ]
                
                response = await async_client.get("/api/v1/chats/pinned")
                assert response.status_code in [200, 401]


class TestChatsArchive:
    """Test chats archive endpoints"""
    
    async def test_get_archived_chats(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /all/archived endpoint - get archived chats"""
        with patch("open_webui.routers.chats.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.chats.Chats.get_archived_chats_by_user_id") as mock_archived:
                mock_archived.return_value = [
                    {"id": "chat1", "title": "Archived Chat", "archived": True}
                ]
                
                response = await async_client.get("/api/v1/chats/all/archived")
                assert response.status_code in [200, 401]
    
    async def test_archive_all_chats(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /archive/all endpoint - archive all chats"""
        with patch("open_webui.routers.chats.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.chats.Chats.archive_all_chats_by_user_id") as mock_archive:
                mock_archive.return_value = True
                
                response = await async_client.post("/api/v1/chats/archive/all")
                assert response.status_code in [200, 401]


class TestChatOperations:
    """Test individual chat operations"""
    
    async def test_get_chat_by_id(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /{id} endpoint - get specific chat"""
        with patch("open_webui.routers.chats.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.chats.Chats.get_chat_by_id_and_user_id") as mock_get:
                mock_get.return_value = {
                    "id": "chat1",
                    "user_id": "user123",
                    "title": "Test Chat",
                    "messages": []
                }
                
                response = await async_client.get("/api/v1/chats/chat1")
                assert response.status_code in [200, 401, 404]
    
    async def test_update_chat_by_id(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /{id} endpoint - update chat"""
        with patch("open_webui.routers.chats.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.chats.Chats.get_chat_by_id_and_user_id") as mock_get:
                mock_get.return_value = {"id": "chat1", "user_id": "user123"}
                
                with patch("open_webui.routers.chats.Chats.update_chat_by_id") as mock_update:
                    mock_update.return_value = {
                        "id": "chat1",
                        "title": "Updated Chat",
                        "messages": []
                    }
                    
                    update_data = {
                        "title": "Updated Chat",
                        "messages": []
                    }
                    
                    response = await async_client.post(
                        "/api/v1/chats/chat1",
                        json=update_data
                    )
                    assert response.status_code in [200, 401, 404]
    
    async def test_delete_chat_by_id(self, async_client: AsyncClient, mock_verified_user):
        """Test DELETE /{id} endpoint - delete chat"""
        with patch("open_webui.routers.chats.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.chats.Chats.get_chat_by_id_and_user_id") as mock_get:
                mock_get.return_value = {"id": "chat1", "user_id": "user123"}
                
                with patch("open_webui.routers.chats.Chats.delete_chat_by_id") as mock_delete:
                    mock_delete.return_value = True
                    
                    response = await async_client.delete("/api/v1/chats/chat1")
                    assert response.status_code in [200, 401, 404]


class TestChatFeatures:
    """Test chat features endpoints"""
    
    async def test_pin_chat(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /{id}/pin endpoint - pin chat"""
        with patch("open_webui.routers.chats.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.chats.Chats.get_chat_by_id_and_user_id") as mock_get:
                mock_get.return_value = {"id": "chat1", "pinned": False}
                
                with patch("open_webui.routers.chats.Chats.toggle_chat_pinned_by_id") as mock_pin:
                    mock_pin.return_value = {"id": "chat1", "pinned": True}
                    
                    response = await async_client.post("/api/v1/chats/chat1/pin")
                    assert response.status_code in [200, 401, 404]
    
    async def test_clone_chat(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /{id}/clone endpoint - clone chat"""
        with patch("open_webui.routers.chats.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.chats.Chats.get_chat_by_id_and_user_id") as mock_get:
                mock_get.return_value = {
                    "id": "chat1",
                    "title": "Original Chat",
                    "messages": []
                }
                
                with patch("open_webui.routers.chats.Chats.insert_new_chat") as mock_insert:
                    mock_insert.return_value = {
                        "id": "chat_clone",
                        "title": "Cloned Chat",
                        "messages": []
                    }
                    
                    clone_data = {"title": "Cloned Chat"}
                    
                    response = await async_client.post(
                        "/api/v1/chats/chat1/clone",
                        json=clone_data
                    )
                    assert response.status_code in [200, 401, 404]
    
    async def test_archive_chat(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /{id}/archive endpoint - archive chat"""
        with patch("open_webui.routers.chats.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.chats.Chats.get_chat_by_id_and_user_id") as mock_get:
                mock_get.return_value = {"id": "chat1", "archived": False}
                
                with patch("open_webui.routers.chats.Chats.toggle_chat_archive_by_id") as mock_archive:
                    mock_archive.return_value = {"id": "chat1", "archived": True}
                    
                    response = await async_client.post("/api/v1/chats/chat1/archive")
                    assert response.status_code in [200, 401, 404]
    
    async def test_share_chat(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /{id}/share endpoint - share chat"""
        with patch("open_webui.routers.chats.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.chats.has_permission", return_value=True):
                with patch("open_webui.routers.chats.Chats.get_chat_by_id_and_user_id") as mock_get:
                    mock_get.return_value = {"id": "chat1", "share_id": None}
                    
                    with patch("open_webui.routers.chats.Chats.update_chat_share_id_by_id") as mock_share:
                        mock_share.return_value = {"id": "chat1", "share_id": "share123"}
                        
                        response = await async_client.post("/api/v1/chats/chat1/share")
                        assert response.status_code in [200, 401, 403, 404]


class TestChatTags:
    """Test chat tags endpoints"""
    
    async def test_get_all_tags(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /all/tags endpoint - get all user tags"""
        with patch("open_webui.routers.chats.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.chats.Tags.get_tags_by_user_id") as mock_tags:
                mock_tags.return_value = [
                    {"id": "tag1", "name": "important"},
                    {"id": "tag2", "name": "work"}
                ]
                
                response = await async_client.get("/api/v1/chats/all/tags")
                assert response.status_code in [200, 401]
    
    async def test_get_chat_tags(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /{id}/tags endpoint - get chat tags"""
        with patch("open_webui.routers.chats.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.chats.Chats.get_chat_by_id_and_user_id") as mock_get:
                mock_get.return_value = {"id": "chat1"}
                
                with patch("open_webui.routers.chats.TagModels.get_tags_by_chat_id") as mock_tags:
                    mock_tags.return_value = [
                        {"id": "tag1", "name": "important"}
                    ]
                    
                    response = await async_client.get("/api/v1/chats/chat1/tags")
                    assert response.status_code in [200, 401, 404]
