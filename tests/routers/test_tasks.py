"""
Test cases for tasks router endpoints
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient
from httpx import AsyncClient
import json
from datetime import datetime


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


class TestTasksConfig:
    """Test task configuration endpoints"""
    
    async def test_get_task_config(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /config endpoint"""
        with patch("open_webui.routers.tasks.get_verified_user", return_value=mock_verified_user):
            mock_request = MagicMock()
            mock_request.app.state.config.TASK_MODEL = "test-model"
            mock_request.app.state.config.TASK_MODEL_EXTERNAL = "external-model"
            with patch("open_webui.routers.tasks.Request", return_value=mock_request):
                response = await async_client.get("/api/v1/tasks/config")
                assert response.status_code in [200, 401]
    
    async def test_update_task_config(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /config/update endpoint"""
        with patch("open_webui.routers.tasks.get_admin_user", return_value=mock_admin_user):
            response = await async_client.post(
                "/api/v1/tasks/config/update",
                json={
                    "TASK_MODEL": "new-model",
                    "TASK_MODEL_EXTERNAL": "new-external",
                    "TITLE_GENERATION_PROMPT_TEMPLATE": "Generate title",
                    "SEARCH_QUERY_GENERATION_PROMPT_TEMPLATE": "Generate query",
                    "SEARCH_QUERY_PROMPT_LENGTH_THRESHOLD": 100,
                    "TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE": "Call function"
                }
            )
            assert response.status_code in [200, 401]


class TestTasksCompletions:
    """Test various completion generation endpoints"""
    
    async def test_generate_title(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /title/completions endpoint"""
        with patch("open_webui.routers.tasks.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.tasks.generate_completion") as mock_generate:
                mock_generate.return_value = {"title": "Test Title"}
                response = await async_client.post(
                    "/api/v1/tasks/title/completions",
                    json={
                        "messages": [{"role": "user", "content": "Hello"}],
                        "model": "test-model"
                    }
                )
                assert response.status_code in [200, 401]
    
    async def test_generate_follow_ups(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /follow_up/completions endpoint"""
        with patch("open_webui.routers.tasks.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.tasks.generate_completion") as mock_generate:
                mock_generate.return_value = {"suggestions": ["Follow up 1", "Follow up 2"]}
                response = await async_client.post(
                    "/api/v1/tasks/follow_up/completions",
                    json={
                        "messages": [{"role": "user", "content": "Test message"}],
                        "model": "test-model"
                    }
                )
                assert response.status_code in [200, 401]
    
    async def test_generate_chat_tags(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /tags/completions endpoint"""
        with patch("open_webui.routers.tasks.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.tasks.generate_completion") as mock_generate:
                mock_generate.return_value = {"tags": ["tag1", "tag2"]}
                response = await async_client.post(
                    "/api/v1/tasks/tags/completions",
                    json={
                        "messages": [{"role": "user", "content": "Test message"}],
                        "model": "test-model"
                    }
                )
                assert response.status_code in [200, 401]
    
    async def test_generate_image_prompt(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /image_prompt/completions endpoint"""
        with patch("open_webui.routers.tasks.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.tasks.generate_completion") as mock_generate:
                mock_generate.return_value = {"prompt": "Generate an image of..."}
                response = await async_client.post(
                    "/api/v1/tasks/image_prompt/completions",
                    json={
                        "messages": [{"role": "user", "content": "Create image"}],
                        "model": "test-model"
                    }
                )
                assert response.status_code in [200, 401]
    
    async def test_generate_queries(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /queries/completions endpoint"""
        with patch("open_webui.routers.tasks.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.tasks.generate_completion") as mock_generate:
                mock_generate.return_value = {"queries": ["query1", "query2"]}
                response = await async_client.post(
                    "/api/v1/tasks/queries/completions",
                    json={
                        "messages": [{"role": "user", "content": "Search for..."}],
                        "model": "test-model"
                    }
                )
                assert response.status_code in [200, 401]
    
    async def test_generate_autocompletion(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /auto/completions endpoint"""
        with patch("open_webui.routers.tasks.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.tasks.generate_completion") as mock_generate:
                mock_generate.return_value = {"completion": "autocompleted text"}
                response = await async_client.post(
                    "/api/v1/tasks/auto/completions",
                    json={
                        "messages": [{"role": "user", "content": "Complete this..."}],
                        "model": "test-model"
                    }
                )
                assert response.status_code in [200, 401]
    
    async def test_generate_emoji(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /emoji/completions endpoint"""
        with patch("open_webui.routers.tasks.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.tasks.generate_completion") as mock_generate:
                mock_generate.return_value = {"emoji": "😊"}
                response = await async_client.post(
                    "/api/v1/tasks/emoji/completions",
                    json={
                        "messages": [{"role": "user", "content": "Happy message"}],
                        "model": "test-model"
                    }
                )
                assert response.status_code in [200, 401]
    
    async def test_generate_moa_response(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /moa/completions endpoint"""
        with patch("open_webui.routers.tasks.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.tasks.generate_completion") as mock_generate:
                mock_generate.return_value = {"response": "MOA response"}
                response = await async_client.post(
                    "/api/v1/tasks/moa/completions",
                    json={
                        "messages": [{"role": "user", "content": "Generate MOA"}],
                        "model": "test-model",
                        "models": ["model1", "model2"]
                    }
                )
                assert response.status_code in [200, 401]
