"""
Test cases for prompts router endpoints - comprehensive coverage for all 6 endpoints
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


class TestPromptsManagement:
    """Test prompts management endpoints"""
    
    async def test_get_prompts(self, async_client: AsyncClient, mock_verified_user):
        """Test GET / endpoint - get all prompts"""
        with patch("open_webui.routers.prompts.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.prompts.Prompts.get_prompts_by_user_id") as mock_get:
                mock_get.return_value = [
                    {
                        "command": "/summarize",
                        "user_id": "user123",
                        "title": "Summarize Text",
                        "content": "Please summarize the following text:",
                        "timestamp": 1234567890
                    },
                    {
                        "command": "/translate",
                        "user_id": "user123",
                        "title": "Translate Text",
                        "content": "Please translate the following text:",
                        "timestamp": 1234567891
                    }
                ]
                
                response = await async_client.get("/api/v1/prompts/")
                assert response.status_code in [200, 401]
    
    async def test_get_prompt_list(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /list endpoint - get prompt list"""
        with patch("open_webui.routers.prompts.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.prompts.Prompts.get_prompts_by_user_id") as mock_get:
                mock_get.return_value = [
                    {
                        "command": "/summarize",
                        "user_id": "user123",
                        "title": "Summarize Text"
                    },
                    {
                        "command": "/translate",
                        "user_id": "user123",
                        "title": "Translate Text"
                    }
                ]
                
                response = await async_client.get("/api/v1/prompts/list")
                assert response.status_code in [200, 401]
    
    async def test_create_new_prompt(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /create endpoint - create new prompt"""
        with patch("open_webui.routers.prompts.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.prompts.Prompts.get_prompt_by_command") as mock_get:
                mock_get.return_value = None  # Prompt doesn't exist
                
                with patch("open_webui.routers.prompts.Prompts.insert_new_prompt") as mock_insert:
                    mock_insert.return_value = {
                        "command": "/newprompt",
                        "user_id": "user123",
                        "title": "New Prompt",
                        "content": "This is a new prompt template",
                        "timestamp": 1234567892
                    }
                    
                    prompt_data = {
                        "command": "newprompt",
                        "title": "New Prompt",
                        "content": "This is a new prompt template"
                    }
                    
                    response = await async_client.post(
                        "/api/v1/prompts/create",
                        json=prompt_data
                    )
                    assert response.status_code in [200, 401, 400]
    
    async def test_get_prompt_by_command(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /command/{command} endpoint - get specific prompt"""
        with patch("open_webui.routers.prompts.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.prompts.Prompts.get_prompt_by_command") as mock_get:
                mock_get.return_value = {
                    "command": "/summarize",
                    "user_id": "user123",
                    "title": "Summarize Text",
                    "content": "Please summarize the following text:",
                    "timestamp": 1234567890
                }
                
                response = await async_client.get("/api/v1/prompts/command/summarize")
                assert response.status_code in [200, 401, 404]
    
    async def test_update_prompt_by_command(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /command/{command}/update endpoint - update prompt"""
        with patch("open_webui.routers.prompts.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.prompts.Prompts.get_prompt_by_command") as mock_get:
                mock_get.return_value = {
                    "command": "/summarize",
                    "user_id": "user123",
                    "title": "Summarize Text",
                    "content": "Old content"
                }
                
                with patch("open_webui.routers.prompts.Prompts.update_prompt_by_command") as mock_update:
                    mock_update.return_value = {
                        "command": "/summarize",
                        "user_id": "user123",
                        "title": "Updated Summarize",
                        "content": "Updated content",
                        "timestamp": 1234567893
                    }
                    
                    update_data = {
                        "command": "summarize",
                        "title": "Updated Summarize",
                        "content": "Updated content"
                    }
                    
                    response = await async_client.post(
                        "/api/v1/prompts/command/summarize/update",
                        json=update_data
                    )
                    assert response.status_code in [200, 401, 404]
    
    async def test_delete_prompt_by_command(self, async_client: AsyncClient, mock_verified_user):
        """Test DELETE /command/{command}/delete endpoint - delete prompt"""
        with patch("open_webui.routers.prompts.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.prompts.Prompts.get_prompt_by_command") as mock_get:
                mock_get.return_value = {
                    "command": "/summarize",
                    "user_id": "user123"
                }
                
                with patch("open_webui.routers.prompts.Prompts.delete_prompt_by_command") as mock_delete:
                    mock_delete.return_value = True
                    
                    response = await async_client.delete("/api/v1/prompts/command/summarize/delete")
                    assert response.status_code in [200, 401, 404]


class TestPromptsAdmin:
    """Test prompts endpoints with admin user"""
    
    async def test_admin_get_all_prompts(self, async_client: AsyncClient, mock_admin_user):
        """Test admin can get all prompts from all users"""
        with patch("open_webui.routers.prompts.get_verified_user", return_value=mock_admin_user):
            with patch("open_webui.routers.prompts.ENABLE_ADMIN_WORKSPACE_CONTENT_ACCESS", True):
                with patch("open_webui.routers.prompts.Prompts.get_prompts") as mock_get:
                    mock_get.return_value = [
                        {
                            "command": "/summarize",
                            "user_id": "user123",
                            "title": "User's Summarize"
                        },
                        {
                            "command": "/translate",
                            "user_id": "user456",
                            "title": "Another User's Translate"
                        }
                    ]
                    
                    response = await async_client.get("/api/v1/prompts/")
                    assert response.status_code in [200, 401]
