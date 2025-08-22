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
    
    async def test_import_config_success(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /import endpoint - success case"""
        test_config = {"test_key": "test_value", "enabled": True}
        with patch("open_webui.routers.configs.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.configs.save_config") as mock_save:
                with patch("open_webui.routers.configs.get_config", return_value=test_config):
                    response = await async_client.post(
                        "/api/v1/configs/import",
                        json={"config": test_config}
                    )
                    assert response.status_code == 200
                    assert response.json() == test_config
                    mock_save.assert_called_once_with(test_config)
    
    async def test_import_config_unauthorized(self, async_client: AsyncClient):
        """Test POST /import endpoint - unauthorized"""
        with patch("open_webui.routers.configs.get_admin_user", side_effect=Exception("Unauthorized")):
            response = await async_client.post(
                "/api/v1/configs/import",
                json={"config": {}}
            )
            assert response.status_code in [401, 403, 500]
    
    async def test_export_config_success(self, async_client: AsyncClient, mock_admin_user):
        """Test GET /export endpoint - success case"""
        export_config = {"test": "value", "version": "1.0"}
        with patch("open_webui.routers.configs.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.configs.get_config", return_value=export_config):
                response = await async_client.get("/api/v1/configs/export")
                assert response.status_code == 200
                assert response.json() == export_config
    
    async def test_export_config_unauthorized(self, async_client: AsyncClient):
        """Test GET /export endpoint - unauthorized"""
        with patch("open_webui.routers.configs.get_admin_user", side_effect=Exception("Unauthorized")):
            response = await async_client.get("/api/v1/configs/export")
            assert response.status_code in [401, 403, 500]


class TestConnectionsConfig:
    """Test connections configuration endpoints"""
    
    async def test_get_connections_config_success(self, async_client: AsyncClient, mock_admin_user):
        """Test GET /connections endpoint - success case"""
        with patch("open_webui.routers.configs.get_admin_user", return_value=mock_admin_user):
            response = await async_client.get("/api/v1/configs/connections")
            assert response.status_code == 200
            data = response.json()
            assert "ENABLE_DIRECT_CONNECTIONS" in data
            assert "ENABLE_BASE_MODELS_CACHE" in data
    
    async def test_get_connections_config_unauthorized(self, async_client: AsyncClient):
        """Test GET /connections endpoint - unauthorized"""
        with patch("open_webui.routers.configs.get_admin_user", side_effect=Exception("Unauthorized")):
            response = await async_client.get("/api/v1/configs/connections")
            assert response.status_code in [401, 403, 500]
    
    async def test_set_connections_config_success(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /connections endpoint - success case"""
        config_data = {
            "ENABLE_DIRECT_CONNECTIONS": True,
            "ENABLE_BASE_MODELS_CACHE": False
        }
        with patch("open_webui.routers.configs.get_admin_user", return_value=mock_admin_user):
            response = await async_client.post(
                "/api/v1/configs/connections",
                json=config_data
            )
            assert response.status_code == 200
            assert response.json() == config_data
    
    async def test_set_connections_config_invalid_data(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /connections endpoint - invalid data"""
        with patch("open_webui.routers.configs.get_admin_user", return_value=mock_admin_user):
            response = await async_client.post(
                "/api/v1/configs/connections",
                json={"invalid_field": "value"}
            )
            assert response.status_code in [400, 422]


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
            with patch("open_webui.routers.configs.get_tool_servers_data", return_value={}):
                response = await async_client.post(
                    "/api/v1/configs/tool_servers",
                    json={
                        "TOOL_SERVER_CONNECTIONS": [
                            {
                                "url": "http://localhost:8080",
                                "path": "/api",
                                "auth_type": "bearer",
                                "key": "test-key"
                            }
                        ]
                    }
                )
                assert response.status_code in [200, 401]
    
    async def test_verify_tool_servers_config(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /tool_servers/verify endpoint"""
        with patch("open_webui.routers.configs.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.configs.get_tool_server_data", return_value={"status": "ok"}):
                response = await async_client.post(
                    "/api/v1/configs/tool_servers/verify",
                    json={
                        "url": "http://localhost:8080",
                        "path": "/api",
                        "auth_type": "bearer",
                        "key": "test-key",
                        "config": {}
                    }
                )
                assert response.status_code in [200, 400, 401]
    
    async def test_verify_tool_servers_config_error(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /tool_servers/verify endpoint with error"""
        with patch("open_webui.routers.configs.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.configs.get_tool_server_data", side_effect=Exception("Connection failed")):
                response = await async_client.post(
                    "/api/v1/configs/tool_servers/verify",
                    json={
                        "url": "http://localhost:8080",
                        "path": "/api",
                        "auth_type": "bearer",
                        "key": "test-key"
                    }
                )
                assert response.status_code == 400


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
                    "CODE_EXECUTION_ENGINE": "local",
                    "CODE_EXECUTION_JUPYTER_URL": "http://localhost:8888",
                    "CODE_EXECUTION_JUPYTER_AUTH": "token",
                    "CODE_EXECUTION_JUPYTER_AUTH_TOKEN": "test-token",
                    "CODE_EXECUTION_JUPYTER_AUTH_PASSWORD": "password",
                    "CODE_EXECUTION_JUPYTER_TIMEOUT": 30,
                    "ENABLE_CODE_INTERPRETER": True,
                    "CODE_INTERPRETER_ENGINE": "local",
                    "CODE_INTERPRETER_PROMPT_TEMPLATE": "Execute: {code}",
                    "CODE_INTERPRETER_JUPYTER_URL": "http://localhost:8888",
                    "CODE_INTERPRETER_JUPYTER_AUTH": "token",
                    "CODE_INTERPRETER_JUPYTER_AUTH_TOKEN": "test-token",
                    "CODE_INTERPRETER_JUPYTER_AUTH_PASSWORD": "password",
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
                    "DEFAULT_MODELS": "gpt-3.5-turbo,gpt-4",
                    "MODEL_ORDER_LIST": ["gpt-4", "gpt-3.5-turbo"]
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
                            "content": "Test content"
                        }
                    ]
                }
            )
            assert response.status_code in [200, 401]
    
    async def test_set_banners_success(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /banners endpoint - success case"""
        banner_data = [
            {
                "id": "banner1",
                "type": "info",
                "title": "Test Banner",
                "content": "This is a test banner",
                "dismissible": True,
                "timestamp": 1234567890
            }
        ]
        with patch("open_webui.routers.configs.get_admin_user", return_value=mock_admin_user):
            response = await async_client.post(
                "/api/v1/configs/banners",
                json={"banners": banner_data}
            )
            assert response.status_code == 200
            assert response.json() == banner_data
    
    async def test_set_banners_empty(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /banners endpoint - empty banners"""
        with patch("open_webui.routers.configs.get_admin_user", return_value=mock_admin_user):
            response = await async_client.post(
                "/api/v1/configs/banners",
                json={"banners": []}
            )
            assert response.status_code == 200
            assert response.json() == []
    
    async def test_set_banners_unauthorized(self, async_client: AsyncClient):
        """Test POST /banners endpoint - unauthorized"""
        with patch("open_webui.routers.configs.get_admin_user", side_effect=Exception("Unauthorized")):
            response = await async_client.post(
                "/api/v1/configs/banners",
                json={"banners": []}
            )
            assert response.status_code in [401, 403, 500]
    
    async def test_get_banners_success(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /banners endpoint - success case"""
        with patch("open_webui.routers.configs.get_verified_user", return_value=mock_verified_user):
            response = await async_client.get("/api/v1/configs/banners")
            assert response.status_code == 200
            assert isinstance(response.json(), list)
    
    async def test_get_banners_unauthorized(self, async_client: AsyncClient):
        """Test GET /banners endpoint - unauthorized"""
        with patch("open_webui.routers.configs.get_verified_user", side_effect=Exception("Unauthorized")):
            response = await async_client.get("/api/v1/configs/banners")
            assert response.status_code in [401, 403, 500]
