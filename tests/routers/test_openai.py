"""
Test cases for openai router endpoints - comprehensive coverage for all 8 endpoints
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from httpx import AsyncClient
import json
from datetime import datetime
import base64


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
def mock_openai_config():
    return {
        "ENABLE_OPENAI_API": True,
        "OPENAI_API_BASE_URLS": ["https://api.openai.com/v1"],
        "OPENAI_API_KEYS": ["sk-test123"],
        "OPENAI_API_CONFIGS": {
            "model_configs": {
                "gpt-3.5-turbo": {"max_tokens": 4096},
                "gpt-4": {"max_tokens": 8192}
            }
        }
    }


@pytest.fixture
def mock_models_response():
    return {
        "data": [
            {
                "id": "gpt-3.5-turbo",
                "object": "model",
                "created": 1677610602,
                "owned_by": "openai"
            },
            {
                "id": "gpt-4",
                "object": "model",
                "created": 1677610602,
                "owned_by": "openai"
            }
        ]
    }


class TestOpenAIConfig:
    """Test OpenAI configuration endpoints"""
    
    async def test_get_config(self, async_client: AsyncClient, mock_admin_user, mock_openai_config):
        """Test GET /config endpoint"""
        with patch("open_webui.routers.openai.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.openai.request.app.state.config") as mock_config:
                mock_config.ENABLE_OPENAI_API = True
                mock_config.OPENAI_API_BASE_URLS = ["https://api.openai.com/v1"]
                mock_config.OPENAI_API_KEYS = ["sk-test123"]
                mock_config.OPENAI_API_CONFIGS = {}
                
                response = await async_client.get("/api/v1/openai/config")
                assert response.status_code == 200
                data = response.json()
                assert "ENABLE_OPENAI_API" in data
                assert data["ENABLE_OPENAI_API"] is True
                assert "OPENAI_API_BASE_URLS" in data
    
    async def test_get_config_unauthorized(self, async_client: AsyncClient):
        """Test GET /config without admin rights"""
        with patch("open_webui.routers.openai.get_admin_user", side_effect=Exception("Unauthorized")):
            response = await async_client.get("/api/v1/openai/config")
            assert response.status_code in [401, 403, 500]
    
    async def test_update_config(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /config/update endpoint"""
        with patch("open_webui.routers.openai.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.openai.request.app.state.config") as mock_config:
                update_data = {
                    "ENABLE_OPENAI_API": True,
                    "OPENAI_API_BASE_URLS": ["https://api.openai.com/v1", "https://api2.openai.com/v1"],
                    "OPENAI_API_KEYS": ["sk-new123", "sk-new456"],
                    "OPENAI_API_CONFIGS": {"timeout": 30}
                }
                
                response = await async_client.post(
                    "/api/v1/openai/config/update",
                    json=update_data
                )
                assert response.status_code == 200
                data = response.json()
                assert data["ENABLE_OPENAI_API"] is True
                assert len(data["OPENAI_API_BASE_URLS"]) == 2
    
    async def test_update_config_invalid_data(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /config/update with invalid data"""
        with patch("open_webui.routers.openai.get_admin_user", return_value=mock_admin_user):
            invalid_data = {
                "ENABLE_OPENAI_API": "not_a_boolean",
                "OPENAI_API_BASE_URLS": "not_a_list"
            }
            
            response = await async_client.post(
                "/api/v1/openai/config/update",
                json=invalid_data
            )
            assert response.status_code in [400, 422]


class TestAudioEndpoints:
    """Test audio-related endpoints"""
    
    async def test_speech_generation(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /audio/speech endpoint"""
        with patch("open_webui.routers.openai.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.openai.request.app.state.config.ENABLE_OPENAI_API", True):
                with patch("open_webui.routers.openai.aiohttp.ClientSession") as mock_session:
                    mock_response = MagicMock()
                    mock_response.status = 200
                    mock_response.content.read = AsyncMock(return_value=b"audio_data_here")
                    mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value = mock_response
                    
                    speech_data = {
                        "model": "tts-1",
                        "input": "Hello, this is a test.",
                        "voice": "alloy"
                    }
                    
                    response = await async_client.post(
                        "/api/v1/openai/audio/speech",
                        json=speech_data
                    )
                    assert response.status_code == 200
                    assert response.content == b"audio_data_here"
    
    async def test_speech_generation_api_disabled(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /audio/speech with API disabled"""
        with patch("open_webui.routers.openai.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.openai.request.app.state.config.ENABLE_OPENAI_API", False):
                speech_data = {
                    "model": "tts-1",
                    "input": "Test",
                    "voice": "alloy"
                }
                
                response = await async_client.post(
                    "/api/v1/openai/audio/speech",
                    json=speech_data
                )
                assert response.status_code == 404
    
    async def test_speech_generation_error(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /audio/speech with API error"""
        with patch("open_webui.routers.openai.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.openai.request.app.state.config.ENABLE_OPENAI_API", True):
                with patch("open_webui.routers.openai.aiohttp.ClientSession") as mock_session:
                    mock_session.return_value.__aenter__.return_value.post.side_effect = Exception("API Error")
                    
                    speech_data = {
                        "model": "tts-1",
                        "input": "Test",
                        "voice": "alloy"
                    }
                    
                    response = await async_client.post(
                        "/api/v1/openai/audio/speech",
                        json=speech_data
                    )
                    assert response.status_code in [400, 500]


class TestModelsEndpoints:
    """Test models endpoints"""
    
    async def test_get_models(self, async_client: AsyncClient, mock_verified_user, mock_models_response):
        """Test GET /models endpoint"""
        with patch("open_webui.routers.openai.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.openai.request.app.state.config.ENABLE_OPENAI_API", True):
                with patch("open_webui.routers.openai.aiohttp.ClientSession") as mock_session:
                    mock_response = MagicMock()
                    mock_response.status = 200
                    mock_response.json = AsyncMock(return_value=mock_models_response)
                    mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response
                    
                    response = await async_client.get("/api/v1/openai/models")
                    assert response.status_code == 200
                    data = response.json()
                    assert len(data) == 2
                    assert data[0]["id"] == "gpt-3.5-turbo"
    
    async def test_get_models_with_url_idx(self, async_client: AsyncClient, mock_verified_user, mock_models_response):
        """Test GET /models/{url_idx} endpoint"""
        with patch("open_webui.routers.openai.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.openai.request.app.state.config") as mock_config:
                mock_config.ENABLE_OPENAI_API = True
                mock_config.OPENAI_API_BASE_URLS = ["https://api.openai.com/v1", "https://api2.openai.com/v1"]
                
                with patch("open_webui.routers.openai.aiohttp.ClientSession") as mock_session:
                    mock_response = MagicMock()
                    mock_response.status = 200
                    mock_response.json = AsyncMock(return_value=mock_models_response)
                    mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response
                    
                    response = await async_client.get("/api/v1/openai/models/1")
                    assert response.status_code == 200
                    data = response.json()
                    assert len(data) > 0
    
    async def test_get_models_invalid_idx(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /models/{url_idx} with invalid index"""
        with patch("open_webui.routers.openai.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.openai.request.app.state.config") as mock_config:
                mock_config.ENABLE_OPENAI_API = True
                mock_config.OPENAI_API_BASE_URLS = ["https://api.openai.com/v1"]
                
                response = await async_client.get("/api/v1/openai/models/99")
                assert response.status_code in [400, 404]


class TestConnectionVerification:
    """Test connection verification endpoint"""
    
    async def test_verify_connection_success(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /verify endpoint with successful connection"""
        with patch("open_webui.routers.openai.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.openai.aiohttp.ClientSession") as mock_session:
                mock_response = MagicMock()
                mock_response.status = 200
                mock_response.json = AsyncMock(return_value={"data": [{"id": "gpt-3.5-turbo"}]})
                mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response
                
                verification_data = {
                    "url": "https://api.openai.com/v1",
                    "key": "sk-test123"
                }
                
                response = await async_client.post(
                    "/api/v1/openai/verify",
                    json=verification_data
                )
                assert response.status_code == 200
                data = response.json()
                assert data["status"] is True
    
    async def test_verify_connection_failure(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /verify with failed connection"""
        with patch("open_webui.routers.openai.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.openai.aiohttp.ClientSession") as mock_session:
                mock_session.return_value.__aenter__.return_value.get.side_effect = Exception("Connection failed")
                
                verification_data = {
                    "url": "https://api.openai.com/v1",
                    "key": "invalid-key"
                }
                
                response = await async_client.post(
                    "/api/v1/openai/verify",
                    json=verification_data
                )
                assert response.status_code == 200
                data = response.json()
                assert data["status"] is False
                assert "error" in data


class TestChatCompletions:
    """Test chat completions endpoint"""
    
    async def test_chat_completion(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /chat/completions endpoint"""
        with patch("open_webui.routers.openai.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.openai.request.app.state.config.ENABLE_OPENAI_API", True):
                with patch("open_webui.routers.openai.aiohttp.ClientSession") as mock_session:
                    mock_response = MagicMock()
                    mock_response.status = 200
                    mock_response.json = AsyncMock(return_value={
                        "id": "chatcmpl-123",
                        "object": "chat.completion",
                        "choices": [
                            {
                                "message": {
                                    "role": "assistant",
                                    "content": "Hello! How can I help you?"
                                },
                                "finish_reason": "stop"
                            }
                        ]
                    })
                    mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value = mock_response
                    
                    chat_data = {
                        "model": "gpt-3.5-turbo",
                        "messages": [
                            {"role": "user", "content": "Hello"}
                        ],
                        "stream": False
                    }
                    
                    response = await async_client.post(
                        "/api/v1/openai/chat/completions",
                        json=chat_data
                    )
                    assert response.status_code == 200
                    data = response.json()
                    assert "choices" in data
                    assert data["choices"][0]["message"]["content"] == "Hello! How can I help you?"
    
    async def test_chat_completion_streaming(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /chat/completions with streaming"""
        with patch("open_webui.routers.openai.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.openai.request.app.state.config.ENABLE_OPENAI_API", True):
                with patch("open_webui.routers.openai.aiohttp.ClientSession") as mock_session:
                    async def mock_iter():
                        yield b"data: {\"choices\":[{\"delta\":{\"content\":\"Hello\"}}]}\n\n"
                        yield b"data: [DONE]\n\n"
                    
                    mock_response = MagicMock()
                    mock_response.status = 200
                    mock_response.content.iter_any = mock_iter
                    mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value = mock_response
                    
                    chat_data = {
                        "model": "gpt-3.5-turbo",
                        "messages": [{"role": "user", "content": "Hello"}],
                        "stream": True
                    }
                    
                    response = await async_client.post(
                        "/api/v1/openai/chat/completions",
                        json=chat_data
                    )
                    assert response.status_code == 200
    
    async def test_chat_completion_api_disabled(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /chat/completions with API disabled"""
        with patch("open_webui.routers.openai.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.openai.request.app.state.config.ENABLE_OPENAI_API", False):
                chat_data = {
                    "model": "gpt-3.5-turbo",
                    "messages": [{"role": "user", "content": "Hello"}]
                }
                
                response = await async_client.post(
                    "/api/v1/openai/chat/completions",
                    json=chat_data
                )
                assert response.status_code == 404


class TestProxyEndpoint:
    """Test proxy endpoint"""
    
    async def test_proxy_get_request(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /{path:path} proxy endpoint"""
        with patch("open_webui.routers.openai.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.openai.request.app.state.config.ENABLE_OPENAI_API", True):
                with patch("open_webui.routers.openai.aiohttp.ClientSession") as mock_session:
                    mock_response = MagicMock()
                    mock_response.status = 200
                    mock_response.json = AsyncMock(return_value={"status": "ok"})
                    mock_session.return_value.__aenter__.return_value.request.return_value.__aenter__.return_value = mock_response
                    
                    response = await async_client.get("/api/v1/openai/some/proxy/path")
                    assert response.status_code == 200
    
    async def test_proxy_post_request(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /{path:path} proxy endpoint"""
        with patch("open_webui.routers.openai.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.openai.request.app.state.config.ENABLE_OPENAI_API", True):
                with patch("open_webui.routers.openai.aiohttp.ClientSession") as mock_session:
                    mock_response = MagicMock()
                    mock_response.status = 200
                    mock_response.json = AsyncMock(return_value={"result": "success"})
                    mock_session.return_value.__aenter__.return_value.request.return_value.__aenter__.return_value = mock_response
                    
                    response = await async_client.post(
                        "/api/v1/openai/some/proxy/path",
                        json={"data": "test"}
                    )
                    assert response.status_code == 200
    
    async def test_proxy_api_disabled(self, async_client: AsyncClient, mock_verified_user):
        """Test proxy endpoint with API disabled"""
        with patch("open_webui.routers.openai.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.openai.request.app.state.config.ENABLE_OPENAI_API", False):
                response = await async_client.get("/api/v1/openai/some/path")
                assert response.status_code == 404
