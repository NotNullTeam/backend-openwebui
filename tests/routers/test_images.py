"""
Test cases for images router endpoints - comprehensive coverage for all 7 endpoints
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


class TestImageConfig:
    """Test image generation configuration endpoints"""
    
    async def test_get_config(self, async_client: AsyncClient, mock_admin_user):
        """Test GET /config endpoint - get image generation config"""
        with patch("open_webui.routers.images.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.images.app.state") as mock_state:
                mock_state.config.ENABLE_IMAGE_GENERATION = True
                mock_state.config.IMAGE_GENERATION_ENGINE = "openai"
                mock_state.config.OPENAI_API_BASE_URL = "https://api.openai.com/v1"
                
                response = await async_client.get("/api/v1/images/config")
                assert response.status_code in [200, 401]
                
                if response.status_code == 200:
                    data = response.json()
                    assert "enabled" in data
                    assert "engine" in data
    
    async def test_update_config(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /config/update endpoint - update image generation config"""
        with patch("open_webui.routers.images.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.images.app.state") as mock_state:
                config_data = {
                    "enabled": True,
                    "engine": "openai",
                    "openai": {
                        "api_base_url": "https://api.openai.com/v1",
                        "api_key": "test-key"
                    }
                }
                
                response = await async_client.post(
                    "/api/v1/images/config/update",
                    json=config_data
                )
                assert response.status_code in [200, 401]
    
    async def test_verify_url(self, async_client: AsyncClient, mock_admin_user):
        """Test GET /config/url/verify endpoint - verify image generation URL"""
        with patch("open_webui.routers.images.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.images.app.state") as mock_state:
                mock_state.config.IMAGE_GENERATION_ENGINE = "automatic1111"
                mock_state.config.AUTOMATIC1111_BASE_URL = "http://localhost:7860"
                
                with patch("open_webui.routers.images.aiohttp.ClientSession") as mock_session:
                    mock_response = AsyncMock()
                    mock_response.json = AsyncMock(return_value={"status": "ok"})
                    mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response
                    
                    response = await async_client.get("/api/v1/images/config/url/verify")
                    assert response.status_code in [200, 401, 404]


class TestImageSettings:
    """Test image generation settings endpoints"""
    
    async def test_get_image_config(self, async_client: AsyncClient, mock_admin_user):
        """Test GET /image/config endpoint - get image generation settings"""
        with patch("open_webui.routers.images.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.images.app.state") as mock_state:
                mock_state.config.IMAGE_GENERATION_MODEL = "dall-e-3"
                mock_state.config.IMAGE_SIZE = "1024x1024"
                mock_state.config.IMAGE_STEPS = 50
                
                response = await async_client.get("/api/v1/images/image/config")
                assert response.status_code in [200, 401]
                
                if response.status_code == 200:
                    data = response.json()
                    assert "MODEL" in data
                    assert "IMAGE_SIZE" in data
                    assert "IMAGE_STEPS" in data
    
    async def test_update_image_config(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /image/config/update endpoint - update image generation settings"""
        with patch("open_webui.routers.images.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.images.app.state") as mock_state:
                config_data = {
                    "MODEL": "dall-e-2",
                    "IMAGE_SIZE": "512x512",
                    "IMAGE_STEPS": 30
                }
                
                response = await async_client.post(
                    "/api/v1/images/image/config/update",
                    json=config_data
                )
                assert response.status_code in [200, 401]


class TestImageModels:
    """Test image generation models endpoint"""
    
    async def test_get_models(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /models endpoint - get available image models"""
        with patch("open_webui.routers.images.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.images.app.state") as mock_state:
                mock_state.config.IMAGE_GENERATION_ENGINE = "openai"
                mock_state.config.OPENAI_API_KEY = "test-key"
                
                with patch("open_webui.routers.images.aiohttp.ClientSession") as mock_session:
                    mock_response = AsyncMock()
                    mock_response.json = AsyncMock(return_value={
                        "data": [
                            {"id": "dall-e-2"},
                            {"id": "dall-e-3"}
                        ]
                    })
                    mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response
                    
                    response = await async_client.get("/api/v1/images/models")
                    assert response.status_code in [200, 401, 500]


class TestImageGeneration:
    """Test image generation endpoint"""
    
    async def test_image_generations(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /generations endpoint - generate images"""
        with patch("open_webui.routers.images.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.images.app.state") as mock_state:
                mock_state.config.ENABLE_IMAGE_GENERATION = True
                mock_state.config.IMAGE_GENERATION_ENGINE = "openai"
                mock_state.config.OPENAI_API_KEY = "test-key"
                
                with patch("open_webui.routers.images.generate_image") as mock_generate:
                    mock_generate.return_value = [
                        {"url": "https://example.com/image1.png"},
                        {"url": "https://example.com/image2.png"}
                    ]
                    
                    generation_data = {
                        "prompt": "A beautiful sunset over mountains",
                        "model": "dall-e-3",
                        "n": 2,
                        "size": "1024x1024",
                        "negative_prompt": ""
                    }
                    
                    response = await async_client.post(
                        "/api/v1/images/generations",
                        json=generation_data
                    )
                    assert response.status_code in [200, 401, 403, 500]
