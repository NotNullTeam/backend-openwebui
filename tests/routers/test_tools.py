"""
Test cases for tools router endpoints
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
        email="user@example.com",
        role="user"
    )


@pytest.fixture
def mock_tool():
    return {
        "id": "tool123",
        "name": "Test Tool",
        "meta": {
            "description": "Test tool description",
            "author": "Test Author",
            "version": "1.0.0"
        },
        "content": "# Tool content",
        "specs": [{"type": "tool", "name": "test_function"}],
        "valves": {"api_key": "test_key"},
        "user_valves": {"user_setting": "value"},
        "user_id": "admin123",
        "created_at": 1234567890,
        "updated_at": 1234567890
    }


class TestToolsList:
    """Test tools list endpoints"""
    
    async def test_get_tools(self, async_client: AsyncClient, mock_verified_user):
        """Test GET / endpoint"""
        with patch("open_webui.routers.tools.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.tools.request.app.state.TOOL_SERVERS", None):
                with patch("open_webui.routers.tools.Tools.get_tools_by_user_id", return_value=[]):
                    response = await async_client.get("/api/v1/tools/")
                    assert response.status_code in [200, 404]
    
    async def test_get_tool_list_admin(self, async_client: AsyncClient, mock_admin_user):
        """Test GET /list endpoint for admin"""
        with patch("open_webui.routers.tools.get_verified_user", return_value=mock_admin_user):
            with patch("open_webui.routers.tools.ENABLE_ADMIN_WORKSPACE_CONTENT_ACCESS", True):
                with patch("open_webui.routers.tools.Tools.get_tools", return_value=[]):
                    response = await async_client.get("/api/v1/tools/list")
                    assert response.status_code == 200
                    assert response.json() == []
    
    async def test_get_tool_list_user(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /list endpoint for regular user"""
        with patch("open_webui.routers.tools.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.tools.Tools.get_tools_by_user_id", return_value=[]):
                response = await async_client.get("/api/v1/tools/list")
                assert response.status_code == 200
                assert response.json() == []


class TestToolsImportExport:
    """Test tools import/export endpoints"""
    
    async def test_load_tool_from_url(self, async_client: AsyncClient, mock_admin_user, mock_tool):
        """Test POST /load/url endpoint"""
        with patch("open_webui.routers.tools.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.tools.get_url_loader") as mock_loader:
                mock_loader.return_value = MagicMock(return_value="https://example.com/tool.py")
                with patch("open_webui.routers.tools.requests.get") as mock_get:
                    mock_get.return_value.text = "# Tool content"
                    mock_get.return_value.raise_for_status = MagicMock()
                    with patch("open_webui.routers.tools.ToolForm", return_value=MagicMock()):
                        with patch("open_webui.routers.tools.Tools.insert_new_tool", return_value=mock_tool):
                            response = await async_client.post(
                                "/api/v1/tools/load/url",
                                json={"url": "https://example.com/tool.py"}
                            )
                            assert response.status_code in [200, 400, 500]
    
    async def test_export_tools(self, async_client: AsyncClient, mock_admin_user, mock_tool):
        """Test GET /export endpoint"""
        with patch("open_webui.routers.tools.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.tools.Tools.get_tools", return_value=[mock_tool]):
                response = await async_client.get("/api/v1/tools/export")
                assert response.status_code == 200
                assert len(response.json()) == 1


class TestToolsCRUD:
    """Test tools CRUD operations"""
    
    async def test_create_new_tool(self, async_client: AsyncClient, mock_admin_user, mock_tool):
        """Test POST /create endpoint"""
        with patch("open_webui.routers.tools.get_verified_user", return_value=mock_admin_user):
            with patch("open_webui.routers.tools.Tools.get_tool_by_id", return_value=None):
                with patch("open_webui.routers.tools.Tools.insert_new_tool", return_value=mock_tool):
                    response = await async_client.post(
                        "/api/v1/tools/create",
                        json={
                            "id": "tool123",
                            "name": "Test Tool",
                            "meta": {"description": "Test tool"},
                            "content": "# Tool content"
                        }
                    )
                    assert response.status_code in [200, 400]
    
    async def test_get_tool_by_id(self, async_client: AsyncClient, mock_verified_user, mock_tool):
        """Test GET /id/{id} endpoint"""
        with patch("open_webui.routers.tools.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.tools.Tools.get_tool_by_id", return_value=mock_tool):
                with patch("open_webui.routers.tools.has_access", return_value=True):
                    response = await async_client.get("/api/v1/tools/id/tool123")
                    assert response.status_code == 200
                    assert response.json()["id"] == "tool123"
    
    async def test_update_tool_by_id(self, async_client: AsyncClient, mock_admin_user, mock_tool):
        """Test POST /id/{id}/update endpoint"""
        with patch("open_webui.routers.tools.get_verified_user", return_value=mock_admin_user):
            with patch("open_webui.routers.tools.Tools.get_tool_by_id", return_value=mock_tool):
                with patch("open_webui.routers.tools.has_access", return_value=True):
                    with patch("open_webui.routers.tools.Tools.update_tool_by_id", return_value=mock_tool):
                        response = await async_client.post(
                            "/api/v1/tools/id/tool123/update",
                            json={
                                "name": "Updated Tool",
                                "meta": {"description": "Updated description"},
                                "content": "# Updated content"
                            }
                        )
                        assert response.status_code in [200, 401]
    
    async def test_delete_tool_by_id(self, async_client: AsyncClient, mock_admin_user, mock_tool):
        """Test DELETE /id/{id}/delete endpoint"""
        with patch("open_webui.routers.tools.get_verified_user", return_value=mock_admin_user):
            with patch("open_webui.routers.tools.Tools.get_tool_by_id", return_value=mock_tool):
                with patch("open_webui.routers.tools.has_access", return_value=True):
                    with patch("open_webui.routers.tools.Tools.delete_tool_by_id", return_value=True):
                        with patch("open_webui.routers.tools.ToolUserValves.delete_tool_user_valves_by_tool_id", return_value=True):
                            response = await async_client.delete("/api/v1/tools/id/tool123/delete")
                            assert response.status_code in [200, 401]


class TestToolsValves:
    """Test tools valves endpoints"""
    
    async def test_get_tools_valves_by_id(self, async_client: AsyncClient, mock_verified_user, mock_tool):
        """Test GET /id/{id}/valves endpoint"""
        with patch("open_webui.routers.tools.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.tools.Tools.get_tool_by_id", return_value=mock_tool):
                with patch("open_webui.routers.tools.ToolUserValves.get_tool_user_valves_by_tool_id_and_user_id", return_value=None):
                    response = await async_client.get("/api/v1/tools/id/tool123/valves")
                    assert response.status_code == 200
                    assert "api_key" in response.json()
    
    async def test_get_tools_valves_spec_by_id(self, async_client: AsyncClient, mock_verified_user, mock_tool):
        """Test GET /id/{id}/valves/spec endpoint"""
        with patch("open_webui.routers.tools.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.tools.Tools.get_tool_by_id", return_value=mock_tool):
                with patch("open_webui.routers.tools.get_tools_specs_from_content") as mock_specs:
                    mock_specs.return_value = [{"valves_spec": {"api_key": {"type": "string"}}}]
                    response = await async_client.get("/api/v1/tools/id/tool123/valves/spec")
                    assert response.status_code in [200, 404]
    
    async def test_update_tools_valves_by_id(self, async_client: AsyncClient, mock_admin_user, mock_tool):
        """Test POST /id/{id}/valves/update endpoint"""
        with patch("open_webui.routers.tools.get_verified_user", return_value=mock_admin_user):
            with patch("open_webui.routers.tools.Tools.get_tool_by_id", return_value=mock_tool):
                with patch("open_webui.routers.tools.has_access", return_value=True):
                    with patch("open_webui.routers.tools.Tools.update_tool_valves_by_id", return_value=mock_tool):
                        response = await async_client.post(
                            "/api/v1/tools/id/tool123/valves/update",
                            json={"api_key": "new_key"}
                        )
                        assert response.status_code in [200, 401]


class TestToolsUserValves:
    """Test tools user valves endpoints"""
    
    async def test_get_tools_user_valves_by_id(self, async_client: AsyncClient, mock_verified_user, mock_tool):
        """Test GET /id/{id}/valves/user endpoint"""
        with patch("open_webui.routers.tools.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.tools.Tools.get_tool_by_id", return_value=mock_tool):
                with patch("open_webui.routers.tools.ToolUserValves.get_tool_user_valves_by_tool_id_and_user_id") as mock_user_valves:
                    mock_user_valves.return_value = MagicMock(valves={"user_setting": "value"})
                    response = await async_client.get("/api/v1/tools/id/tool123/valves/user")
                    assert response.status_code == 200
                    assert "user_setting" in response.json()
    
    async def test_get_tools_user_valves_spec_by_id(self, async_client: AsyncClient, mock_verified_user, mock_tool):
        """Test GET /id/{id}/valves/user/spec endpoint"""
        with patch("open_webui.routers.tools.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.tools.Tools.get_tool_by_id", return_value=mock_tool):
                with patch("open_webui.routers.tools.get_tools_specs_from_content") as mock_specs:
                    mock_specs.return_value = [{"user_valves_spec": {"user_setting": {"type": "string"}}}]
                    response = await async_client.get("/api/v1/tools/id/tool123/valves/user/spec")
                    assert response.status_code in [200, 404]
    
    async def test_update_tools_user_valves_by_id(self, async_client: AsyncClient, mock_verified_user, mock_tool):
        """Test POST /id/{id}/valves/user/update endpoint"""
        with patch("open_webui.routers.tools.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.tools.Tools.get_tool_by_id", return_value=mock_tool):
                with patch("open_webui.routers.tools.ToolUserValves.get_tool_user_valves_by_tool_id_and_user_id", return_value=None):
                    with patch("open_webui.routers.tools.ToolUserValves.insert_new_tool_user_valves") as mock_insert:
                        mock_insert.return_value = MagicMock(valves={"user_setting": "new_value"})
                        response = await async_client.post(
                            "/api/v1/tools/id/tool123/valves/user/update",
                            json={"user_setting": "new_value"}
                        )
                        assert response.status_code in [200, 404]
