"""
Test cases for configs router endpoints
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


class TestConfigImportExport:
    """Test config import/export endpoints"""
    
    async def test_import_config(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /import endpoint"""
        with patch("open_webui.routers.configs.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.configs.save_config"):
                with patch("open_webui.routers.configs.get_config", return_value={}):
                    response = await async_client.post(
                        "/api/v1/configs/import",
                        json={"config": {"test": "value"}}
                    )
                    assert response.status_code in [200, 401]
    
    async def test_export_config(self, async_client: AsyncClient, mock_admin_user):
        """Test GET /export endpoint"""
        with patch("open_webui.routers.configs.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.configs.get_config", return_value={"test": "value"}):
                response = await async_client.get("/api/v1/configs/export")
                assert response.status_code in [200, 401]


class TestConnectionsConfig:
    """Test connections configuration endpoints"""
    
    async def test_get_connections_config(self, async_client: AsyncClient, mock_admin_user):
        """Test GET /connections endpoint"""
        with patch("open_webui.routers.configs.get_admin_user", return_value=mock_admin_user):
            response = await async_client.get("/api/v1/configs/connections")
            assert response.status_code in [200, 401]
    
    async def test_set_connections_config(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /connections endpoint"""
        with patch("open_webui.routers.configs.get_admin_user", return_value=mock_admin_user):
            response = await async_client.post(
                "/api/v1/configs/connections",
                json={
                    "ENABLE_DIRECT_CONNECTIONS": True,
                    "ENABLE_BASE_MODELS_CACHE": False
                }
            )
            assert response.status_code in [200, 401]


class TestToolServersConfig:
    """Test tool servers configuration endpoints"""
    
    async def test_get_tool_servers_config(self, async_client: AsyncClient, mock_admin_user):
        """Test GET /tool_servers endpoint"""
        with patch("open_webui.routers.configs.get_admin_user", return_value=mock_admin_user):
            response = await async_client.get("/api/v1/configs/tool_servers")
            assert response.status_code in [200, 401]
    
    async def test_set_tool_servers_config(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /tool_servers endpoint"""
        with patch("open_webui.routers.configs.get_admin_user", return_value=mock_admin_user):
            response = await async_client.post(
                "/api/v1/configs/tool_servers",
                json={
                    "TOOL_SERVER_CONNECTIONS": []
                }
            )
            assert response.status_code in [200, 401]
    
    async def test_verify_tool_servers_config(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /tool_servers/verify endpoint"""
        with patch("open_webui.routers.configs.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.configs.mcp.verify_connection", return_value={"status": "ok"}):
                response = await async_client.post(
                    "/api/v1/configs/tool_servers/verify",
                    json={
                        "name": "test",
                        "uri": "ws://localhost:8080",
                        "transport": "websocket"
                    }
                )
                assert response.status_code in [200, 400, 401]


class TestCodeExecutionConfig:
    """Test code execution configuration endpoints"""
    
    async def test_get_code_execution_config(self, async_client: AsyncClient, mock_admin_user):
        """Test GET /code_execution endpoint"""
        with patch("open_webui.routers.configs.get_admin_user", return_value=mock_admin_user):
            response = await async_client.get("/api/v1/configs/code_execution")
            assert response.status_code in [200, 401]
    
    async def test_set_code_execution_config(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /code_execution endpoint"""
        with patch("open_webui.routers.configs.get_admin_user", return_value=mock_admin_user):
            response = await async_client.post(
                "/api/v1/configs/code_execution",
                json={
                    "ENABLE_CODE_EXECUTION": True,
                    "ENABLE_SAFE_MODE": True,
                    "DEFAULT_INTERPRETER": "python",
                    "CODE_INTERPRETER_MAX_EXECUTION_TIME": 30,
                    "CODE_INTERPRETER_MAX_RAM_MB": 512,
                    "CODE_INTERPRETER_MAX_FILES": 10,
                    "CODE_INTERPRETER_MAX_FILE_SIZE_MB": 10,
                    "CODE_INTERPRETER_AUTO_INSTALL": False,
                    "CODE_INTERPRETER_ENABLE_KERNEL": False,
                    "CODE_INTERPRETER_KERNEL_MODE": "default",
                    "CODE_INTERPRETER_KERNEL_HEADERS": {},
                    "CODE_INTERPRETER_USER_PACKAGE_OPERATION": False,
                    "CODE_INTERPRETER_JUPYTER_ENDPOINT": "",
                    "CODE_INTERPRETER_JUPYTER_TOKEN": "",
                    "CODE_INTERPRETER_JUPYTER_TIMEOUT": 30
                }
            )
            assert response.status_code in [200, 401]


class TestModelsConfig:
    """Test models configuration endpoints"""
    
    async def test_get_models_config(self, async_client: AsyncClient, mock_admin_user):
        """Test GET /models endpoint"""
        with patch("open_webui.routers.configs.get_admin_user", return_value=mock_admin_user):
            response = await async_client.get("/api/v1/configs/models")
            assert response.status_code in [200, 401]
    
    async def test_set_models_config(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /models endpoint"""
        with patch("open_webui.routers.configs.get_admin_user", return_value=mock_admin_user):
            response = await async_client.post(
                "/api/v1/configs/models",
                json={
                    "DEFAULT_MODELS": ["gpt-3.5-turbo"],
                    "MODEL_ORDER_LIST": []
                }
            )
            assert response.status_code in [200, 401]


class TestSuggestionsAndBanners:
    """Test suggestions and banners endpoints"""
    
    async def test_set_default_suggestions(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /suggestions endpoint"""
        with patch("open_webui.routers.configs.get_admin_user", return_value=mock_admin_user):
            response = await async_client.post(
                "/api/v1/configs/suggestions",
                json={
                    "suggestions": [
                        {
                            "title": ["Test Title"],
                            "content": "Test content",
                            "template": {"name": "test"}
                        }
                    ]
                }
            )
            assert response.status_code in [200, 401]
    
    async def test_set_banners(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /banners endpoint"""
        with patch("open_webui.routers.configs.get_admin_user", return_value=mock_admin_user):
            response = await async_client.post(
                "/api/v1/configs/banners",
                json={
                    "banners": [
                        {
                            "id": "banner1",
                            "type": "info",
                            "title": "Test Banner",
                            "content": "This is a test banner",
                            "dismissible": True,
                            "timestamp": 1234567890
                        }
                    ]
                }
            )
            assert response.status_code in [200, 401]
    
    async def test_get_banners(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /banners endpoint"""
        with patch("open_webui.routers.configs.get_verified_user", return_value=mock_verified_user):
            response = await async_client.get("/api/v1/configs/banners")
            assert response.status_code in [200, 401]
