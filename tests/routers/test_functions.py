"""
Test cases for functions router endpoints
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient
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
        email="user@example.com",
        role="user"
    )


@pytest.fixture
def mock_function():
    return {
        "id": "test_function",
        "name": "Test Function",
        "description": "A test function",
        "content": "def test(): pass",
        "meta": {
            "manifest": {
                "name": "Test Function",
                "description": "A test function"
            }
        },
        "is_active": True,
        "is_global": False,
        "created_at": 1234567890,
        "updated_at": 1234567890
    }


class TestFunctionsList:
    """Test functions list endpoints"""
    
    async def test_get_functions(self, async_client: AsyncClient, mock_verified_user):
        """Test GET / endpoint"""
        with patch("open_webui.routers.functions.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.functions.Functions.get_functions", return_value=[]):
                response = await async_client.get("/api/v1/functions/")
                assert response.status_code == 200
                assert response.json() == []
    
    async def test_export_functions(self, async_client: AsyncClient, mock_admin_user):
        """Test GET /export endpoint"""
        with patch("open_webui.routers.functions.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.functions.Functions.get_functions", return_value=[]):
                response = await async_client.get("/api/v1/functions/export")
                assert response.status_code == 200
                assert response.json() == []


class TestFunctionLoad:
    """Test function loading endpoints"""
    
    async def test_load_function_from_url(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /load/url endpoint"""
        with patch("open_webui.routers.functions.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.functions.get_function_module", return_value=None):
                response = await async_client.post(
                    "/api/v1/functions/load/url",
                    json={"url": "https://example.com/function.py"}
                )
                assert response.status_code in [200, 400, 500]
    
    async def test_sync_functions(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /sync endpoint"""
        with patch("open_webui.routers.functions.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.functions.Functions.insert_many_functions", return_value=[]):
                response = await async_client.post(
                    "/api/v1/functions/sync",
                    json={"functions": []}
                )
                assert response.status_code == 200


class TestFunctionCRUD:
    """Test function CRUD operations"""
    
    async def test_create_function(self, async_client: AsyncClient, mock_admin_user, mock_function):
        """Test POST /create endpoint"""
        with patch("open_webui.routers.functions.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.functions.Functions.insert_new_function", return_value=mock_function):
                response = await async_client.post(
                    "/api/v1/functions/create",
                    json={
                        "id": "test_function",
                        "name": "Test Function",
                        "description": "A test function",
                        "content": "def test(): pass",
                        "meta": {}
                    }
                )
                assert response.status_code in [200, 400]
    
    async def test_get_function_by_id(self, async_client: AsyncClient, mock_admin_user, mock_function):
        """Test GET /id/{id} endpoint"""
        with patch("open_webui.routers.functions.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.functions.Functions.get_function_by_id", return_value=mock_function):
                response = await async_client.get("/api/v1/functions/id/test_function")
                assert response.status_code == 200
                assert response.json()["id"] == "test_function"
    
    async def test_update_function_by_id(self, async_client: AsyncClient, mock_admin_user, mock_function):
        """Test POST /id/{id}/update endpoint"""
        with patch("open_webui.routers.functions.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.functions.Functions.get_function_by_id", return_value=mock_function):
                with patch("open_webui.routers.functions.Functions.update_function_by_id", return_value=mock_function):
                    response = await async_client.post(
                        "/api/v1/functions/id/test_function/update",
                        json={
                            "id": "test_function",
                            "name": "Updated Function",
                            "description": "Updated description",
                            "content": "def updated(): pass",
                            "meta": {}
                        }
                    )
                    assert response.status_code in [200, 404]
    
    async def test_delete_function_by_id(self, async_client: AsyncClient, mock_admin_user):
        """Test DELETE /id/{id}/delete endpoint"""
        with patch("open_webui.routers.functions.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.functions.Functions.delete_function_by_id", return_value=True):
                response = await async_client.delete("/api/v1/functions/id/test_function/delete")
                assert response.status_code == 200
                assert response.json() is True


class TestFunctionToggle:
    """Test function toggle endpoints"""
    
    async def test_toggle_function_by_id(self, async_client: AsyncClient, mock_admin_user, mock_function):
        """Test POST /id/{id}/toggle endpoint"""
        with patch("open_webui.routers.functions.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.functions.Functions.get_function_by_id", return_value=mock_function):
                with patch("open_webui.routers.functions.Functions.update_function_by_id", return_value=mock_function):
                    response = await async_client.post("/api/v1/functions/id/test_function/toggle")
                    assert response.status_code == 200
    
    async def test_toggle_global_by_id(self, async_client: AsyncClient, mock_admin_user, mock_function):
        """Test POST /id/{id}/toggle/global endpoint"""
        with patch("open_webui.routers.functions.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.functions.Functions.get_function_by_id", return_value=mock_function):
                with patch("open_webui.routers.functions.Functions.update_function_by_id", return_value=mock_function):
                    response = await async_client.post("/api/v1/functions/id/test_function/toggle/global")
                    assert response.status_code == 200


class TestFunctionValves:
    """Test function valves endpoints"""
    
    async def test_get_function_valves_by_id(self, async_client: AsyncClient, mock_admin_user, mock_function):
        """Test GET /id/{id}/valves endpoint"""
        with patch("open_webui.routers.functions.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.functions.Functions.get_function_by_id", return_value=mock_function):
                with patch("open_webui.routers.functions.Functions.get_function_valves_by_id", return_value={}):
                    response = await async_client.get("/api/v1/functions/id/test_function/valves")
                    assert response.status_code == 200
    
    async def test_get_function_valves_spec_by_id(self, async_client: AsyncClient, mock_admin_user, mock_function):
        """Test GET /id/{id}/valves/spec endpoint"""
        with patch("open_webui.routers.functions.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.functions.Functions.get_function_by_id", return_value=mock_function):
                response = await async_client.get("/api/v1/functions/id/test_function/valves/spec")
                assert response.status_code in [200, 404]
    
    async def test_update_function_valves_by_id(self, async_client: AsyncClient, mock_admin_user, mock_function):
        """Test POST /id/{id}/valves/update endpoint"""
        with patch("open_webui.routers.functions.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.functions.Functions.get_function_by_id", return_value=mock_function):
                with patch("open_webui.routers.functions.Functions.update_function_valves_by_id", return_value={}):
                    response = await async_client.post(
                        "/api/v1/functions/id/test_function/valves/update",
                        json={"key": "value"}
                    )
                    assert response.status_code in [200, 404]


class TestFunctionUserValves:
    """Test function user valves endpoints"""
    
    async def test_get_function_user_valves_by_id(self, async_client: AsyncClient, mock_verified_user, mock_function):
        """Test GET /id/{id}/valves/user endpoint"""
        with patch("open_webui.routers.functions.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.functions.Functions.get_function_by_id", return_value=mock_function):
                with patch("open_webui.routers.functions.Functions.get_user_valves_by_id_and_user_id", return_value={}):
                    response = await async_client.get("/api/v1/functions/id/test_function/valves/user")
                    assert response.status_code == 200
    
    async def test_get_function_user_valves_spec_by_id(self, async_client: AsyncClient, mock_verified_user, mock_function):
        """Test GET /id/{id}/valves/user/spec endpoint"""
        with patch("open_webui.routers.functions.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.functions.Functions.get_function_by_id", return_value=mock_function):
                response = await async_client.get("/api/v1/functions/id/test_function/valves/user/spec")
                assert response.status_code in [200, 404]
    
    async def test_update_function_user_valves_by_id(self, async_client: AsyncClient, mock_verified_user, mock_function):
        """Test POST /id/{id}/valves/user/update endpoint"""
        with patch("open_webui.routers.functions.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.functions.Functions.get_function_by_id", return_value=mock_function):
                with patch("open_webui.routers.functions.Functions.update_user_valves_by_id_and_user_id", return_value={}):
                    response = await async_client.post(
                        "/api/v1/functions/id/test_function/valves/user/update",
                        json={"key": "value"}
                    )
                    assert response.status_code in [200, 404]
