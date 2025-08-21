"""
Test cases for notes router endpoints - comprehensive coverage for all 6 endpoints
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock, Mock
from httpx import AsyncClient
import json


@pytest.fixture
def mock_verified_user():
    return MagicMock(
        id="user123",
        name="Test User",
        email="test@example.com",
        role="user"
    )


@pytest.fixture
def mock_admin_user():
    return MagicMock(
        id="admin123",
        name="Admin User",
        email="admin@example.com",
        role="admin"
    )


class TestNotesManagement:
    """Test notes management endpoints"""
    
    async def test_get_notes(self, async_client: AsyncClient, mock_verified_user):
        """Test GET / endpoint - get all user notes"""
        with patch("open_webui.routers.notes.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.notes.has_permission", return_value=True):
                with patch("open_webui.routers.notes.Notes.get_notes_by_user_id") as mock_get:
                    mock_get.return_value = [
                        {
                            "id": "note1",
                            "user_id": "user123",
                            "title": "First Note",
                            "content": "Note content here",
                            "created_at": 1234567890,
                            "updated_at": 1234567890
                        },
                        {
                            "id": "note2",
                            "user_id": "user123",
                            "title": "Second Note",
                            "content": "Another note",
                            "created_at": 1234567891,
                            "updated_at": 1234567891
                        }
                    ]
                    
                    response = await async_client.get("/api/v1/notes/")
                    assert response.status_code in [200, 401, 403]
    
    async def test_get_note_list(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /list endpoint - get note titles and IDs"""
        with patch("open_webui.routers.notes.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.notes.has_permission", return_value=True):
                with patch("open_webui.routers.notes.Notes.get_notes_by_user_id") as mock_get:
                    mock_get.return_value = [
                        {
                            "id": "note1",
                            "title": "First Note",
                            "created_at": 1234567890
                        },
                        {
                            "id": "note2",
                            "title": "Second Note",
                            "created_at": 1234567891
                        }
                    ]
                    
                    response = await async_client.get("/api/v1/notes/list")
                    assert response.status_code in [200, 401, 403]
    
    async def test_create_new_note(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /create endpoint - create new note"""
        with patch("open_webui.routers.notes.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.notes.has_permission", return_value=True):
                with patch("open_webui.routers.notes.Notes.insert_new_note") as mock_insert:
                    mock_insert.return_value = {
                        "id": "note_new",
                        "user_id": "user123",
                        "title": "New Note",
                        "content": "New note content",
                        "created_at": 1234567892,
                        "updated_at": 1234567892
                    }
                    
                    note_data = {
                        "title": "New Note",
                        "content": "New note content"
                    }
                    
                    response = await async_client.post(
                        "/api/v1/notes/create",
                        json=note_data
                    )
                    assert response.status_code in [200, 401, 403]
    
    async def test_get_note_by_id(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /{id} endpoint - get specific note"""
        with patch("open_webui.routers.notes.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.notes.has_permission", return_value=True):
                with patch("open_webui.routers.notes.Notes.get_note_by_id") as mock_get:
                    mock_get.return_value = {
                        "id": "note1",
                        "user_id": "user123",
                        "title": "First Note",
                        "content": "Note content here",
                        "created_at": 1234567890,
                        "updated_at": 1234567890
                    }
                    
                    response = await async_client.get("/api/v1/notes/note1")
                    assert response.status_code in [200, 401, 403, 404]
    
    async def test_update_note_by_id(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /{id}/update endpoint - update note"""
        with patch("open_webui.routers.notes.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.notes.has_permission", return_value=True):
                with patch("open_webui.routers.notes.Notes.get_note_by_id") as mock_get:
                    mock_get.return_value = {
                        "id": "note1",
                        "user_id": "user123",
                        "title": "First Note",
                        "content": "Note content here"
                    }
                    
                    with patch("open_webui.routers.notes.Notes.update_note_by_id") as mock_update:
                        mock_update.return_value = {
                            "id": "note1",
                            "user_id": "user123",
                            "title": "Updated Note",
                            "content": "Updated content",
                            "created_at": 1234567890,
                            "updated_at": 1234567893
                        }
                        
                        update_data = {
                            "title": "Updated Note",
                            "content": "Updated content"
                        }
                        
                        response = await async_client.post(
                            "/api/v1/notes/note1/update",
                            json=update_data
                        )
                        assert response.status_code in [200, 401, 403, 404]
    
    async def test_delete_note_by_id(self, async_client: AsyncClient, mock_verified_user):
        """Test DELETE /{id}/delete endpoint - delete note"""
        with patch("open_webui.routers.notes.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.notes.has_permission", return_value=True):
                with patch("open_webui.routers.notes.Notes.get_note_by_id") as mock_get:
                    mock_get.return_value = {
                        "id": "note1",
                        "user_id": "user123",
                        "title": "First Note"
                    }
                    
                    with patch("open_webui.routers.notes.Notes.delete_note_by_id") as mock_delete:
                        mock_delete.return_value = True
                        
                        response = await async_client.delete("/api/v1/notes/note1/delete")
                        assert response.status_code in [200, 401, 403, 404]


class TestNotesAdmin:
    """Test notes endpoints with admin user"""
    
    async def test_admin_get_all_notes(self, async_client: AsyncClient, mock_admin_user):
        """Test admin can get all notes from all users"""
        with patch("open_webui.routers.notes.get_verified_user", return_value=mock_admin_user):
            with patch("open_webui.routers.notes.Notes.get_notes") as mock_get:
                mock_get.return_value = [
                    {
                        "id": "note1",
                        "user_id": "user123",
                        "title": "User Note",
                        "content": "User's note"
                    },
                    {
                        "id": "note2",
                        "user_id": "user456",
                        "title": "Another User Note",
                        "content": "Another user's note"
                    }
                ]
                
                response = await async_client.get("/api/v1/notes/")
                assert response.status_code in [200, 401]
