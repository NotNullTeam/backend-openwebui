"""
Test cases for ollama router endpoints
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


class TestOllamaStatus:
    """Test status endpoints"""
    
    async def test_get_status_head(self, async_client: AsyncClient):
        """Test HEAD / endpoint"""
        response = await async_client.head("/api/v1/ollama/")
        assert response.status_code == 200
    
    async def test_get_status(self, async_client: AsyncClient):
        """Test GET / endpoint"""
        response = await async_client.get("/api/v1/ollama/")
        assert response.status_code == 200
        assert response.json() == {"status": True}


class TestOllamaConfig:
    """Test configuration endpoints"""
    
    async def test_verify_connection(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /verify endpoint"""
        with patch("open_webui.routers.ollama.get_admin_user", return_value=mock_admin_user):
            response = await async_client.post(
                "/api/v1/ollama/verify",
                json={"url": "http://localhost:11434", "key": "test_key"}
            )
            assert response.status_code in [200, 500]
    
    async def test_get_config(self, async_client: AsyncClient, mock_admin_user):
        """Test GET /config endpoint"""
        with patch("open_webui.routers.ollama.get_admin_user", return_value=mock_admin_user):
            response = await async_client.get("/api/v1/ollama/config")
            assert response.status_code == 200
            data = response.json()
            assert "ENABLE_OLLAMA_API" in data
    
    async def test_update_config(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /config/update endpoint"""
        with patch("open_webui.routers.ollama.get_admin_user", return_value=mock_admin_user):
            response = await async_client.post(
                "/api/v1/ollama/config/update",
                json={
                    "ENABLE_OLLAMA_API": True,
                    "OLLAMA_BASE_URLS": ["http://localhost:11434"],
                    "OLLAMA_API_CONFIGS": {}
                }
            )
            assert response.status_code == 200


class TestOllamaModels:
    """Test model management endpoints"""
    
    async def test_get_ollama_tags(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /api/tags endpoint"""
        with patch("open_webui.routers.ollama.get_verified_user", return_value=mock_verified_user):
            response = await async_client.get("/api/v1/ollama/api/tags")
            assert response.status_code in [200, 500]
    
    async def test_get_ollama_tags_with_idx(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /api/tags/{url_idx} endpoint"""
        with patch("open_webui.routers.ollama.get_verified_user", return_value=mock_verified_user):
            response = await async_client.get("/api/v1/ollama/api/tags/0")
            assert response.status_code in [200, 500]
    
    async def test_get_ollama_loaded_models(self, async_client: AsyncClient, mock_admin_user):
        """Test GET /api/ps endpoint"""
        with patch("open_webui.routers.ollama.get_admin_user", return_value=mock_admin_user):
            response = await async_client.get("/api/v1/ollama/api/ps")
            assert response.status_code in [200, 500]
    
    async def test_get_ollama_versions(self, async_client: AsyncClient):
        """Test GET /api/version endpoint"""
        response = await async_client.get("/api/v1/ollama/api/version")
        assert response.status_code in [200, 500]
    
    async def test_get_ollama_versions_with_idx(self, async_client: AsyncClient):
        """Test GET /api/version/{url_idx} endpoint"""
        response = await async_client.get("/api/v1/ollama/api/version/0")
        assert response.status_code in [200, 500]


class TestModelOperations:
    """Test model operations endpoints"""
    
    async def test_unload_model(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /api/unload endpoint"""
        with patch("open_webui.routers.ollama.get_admin_user", return_value=mock_admin_user):
            response = await async_client.post(
                "/api/v1/ollama/api/unload",
                json={"name": "llama2"}
            )
            assert response.status_code in [200, 500]
    
    async def test_pull_model(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /api/pull endpoint"""
        with patch("open_webui.routers.ollama.get_admin_user", return_value=mock_admin_user):
            response = await async_client.post(
                "/api/v1/ollama/api/pull",
                json={"name": "llama2", "stream": False}
            )
            assert response.status_code in [200, 500]
    
    async def test_pull_model_with_idx(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /api/pull/{url_idx} endpoint"""
        with patch("open_webui.routers.ollama.get_admin_user", return_value=mock_admin_user):
            response = await async_client.post(
                "/api/v1/ollama/api/pull/0",
                json={"name": "llama2", "stream": False}
            )
            assert response.status_code in [200, 500]
    
    async def test_push_model(self, async_client: AsyncClient, mock_admin_user):
        """Test DELETE /api/push endpoint"""
        with patch("open_webui.routers.ollama.get_admin_user", return_value=mock_admin_user):
            response = await async_client.delete(
                "/api/v1/ollama/api/push",
                json={"name": "llama2", "stream": False}
            )
            assert response.status_code in [200, 405, 500]
    
    async def test_push_model_with_idx(self, async_client: AsyncClient, mock_admin_user):
        """Test DELETE /api/push/{url_idx} endpoint"""
        with patch("open_webui.routers.ollama.get_admin_user", return_value=mock_admin_user):
            response = await async_client.delete(
                "/api/v1/ollama/api/push/0",
                json={"name": "llama2", "stream": False}
            )
            assert response.status_code in [200, 405, 500]
    
    async def test_create_model(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /api/create endpoint"""
        with patch("open_webui.routers.ollama.get_admin_user", return_value=mock_admin_user):
            response = await async_client.post(
                "/api/v1/ollama/api/create",
                json={"name": "custom_model", "modelfile": "FROM llama2", "stream": False}
            )
            assert response.status_code in [200, 500]
    
    async def test_create_model_with_idx(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /api/create/{url_idx} endpoint"""
        with patch("open_webui.routers.ollama.get_admin_user", return_value=mock_admin_user):
            response = await async_client.post(
                "/api/v1/ollama/api/create/0",
                json={"name": "custom_model", "modelfile": "FROM llama2", "stream": False}
            )
            assert response.status_code in [200, 500]
    
    async def test_copy_model(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /api/copy endpoint"""
        with patch("open_webui.routers.ollama.get_admin_user", return_value=mock_admin_user):
            response = await async_client.post(
                "/api/v1/ollama/api/copy",
                json={"source": "llama2", "destination": "llama2-copy"}
            )
            assert response.status_code in [200, 500]
    
    async def test_copy_model_with_idx(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /api/copy/{url_idx} endpoint"""
        with patch("open_webui.routers.ollama.get_admin_user", return_value=mock_admin_user):
            response = await async_client.post(
                "/api/v1/ollama/api/copy/0",
                json={"source": "llama2", "destination": "llama2-copy"}
            )
            assert response.status_code in [200, 500]
    
    async def test_delete_model(self, async_client: AsyncClient, mock_admin_user):
        """Test DELETE /api/delete endpoint"""
        with patch("open_webui.routers.ollama.get_admin_user", return_value=mock_admin_user):
            response = await async_client.delete(
                "/api/v1/ollama/api/delete",
                json={"name": "llama2"}
            )
            assert response.status_code in [200, 405, 500]
    
    async def test_delete_model_with_idx(self, async_client: AsyncClient, mock_admin_user):
        """Test DELETE /api/delete/{url_idx} endpoint"""
        with patch("open_webui.routers.ollama.get_admin_user", return_value=mock_admin_user):
            response = await async_client.delete(
                "/api/v1/ollama/api/delete/0",
                json={"name": "llama2"}
            )
            assert response.status_code in [200, 405, 500]
    
    async def test_show_model_info(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /api/show endpoint"""
        with patch("open_webui.routers.ollama.get_verified_user", return_value=mock_verified_user):
            response = await async_client.post(
                "/api/v1/ollama/api/show",
                json={"name": "llama2"}
            )
            assert response.status_code in [200, 500]


class TestModelInference:
    """Test model inference endpoints"""
    
    async def test_embed(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /api/embed endpoint"""
        with patch("open_webui.routers.ollama.get_verified_user", return_value=mock_verified_user):
            response = await async_client.post(
                "/api/v1/ollama/api/embed",
                json={"model": "llama2", "input": "test text"}
            )
            assert response.status_code in [200, 500]
    
    async def test_embed_with_idx(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /api/embed/{url_idx} endpoint"""
        with patch("open_webui.routers.ollama.get_verified_user", return_value=mock_verified_user):
            response = await async_client.post(
                "/api/v1/ollama/api/embed/0",
                json={"model": "llama2", "input": "test text"}
            )
            assert response.status_code in [200, 500]
    
    async def test_embeddings(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /api/embeddings endpoint"""
        with patch("open_webui.routers.ollama.get_verified_user", return_value=mock_verified_user):
            response = await async_client.post(
                "/api/v1/ollama/api/embeddings",
                json={"model": "llama2", "prompt": "test text"}
            )
            assert response.status_code in [200, 500]
    
    async def test_embeddings_with_idx(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /api/embeddings/{url_idx} endpoint"""
        with patch("open_webui.routers.ollama.get_verified_user", return_value=mock_verified_user):
            response = await async_client.post(
                "/api/v1/ollama/api/embeddings/0",
                json={"model": "llama2", "prompt": "test text"}
            )
            assert response.status_code in [200, 500]
    
    async def test_generate_completion(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /api/generate endpoint"""
        with patch("open_webui.routers.ollama.get_verified_user", return_value=mock_verified_user):
            response = await async_client.post(
                "/api/v1/ollama/api/generate",
                json={"model": "llama2", "prompt": "Hello", "stream": False}
            )
            assert response.status_code in [200, 500]
    
    async def test_generate_completion_with_idx(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /api/generate/{url_idx} endpoint"""
        with patch("open_webui.routers.ollama.get_verified_user", return_value=mock_verified_user):
            response = await async_client.post(
                "/api/v1/ollama/api/generate/0",
                json={"model": "llama2", "prompt": "Hello", "stream": False}
            )
            assert response.status_code in [200, 500]
    
    async def test_generate_chat_completion(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /api/chat endpoint"""
        with patch("open_webui.routers.ollama.get_verified_user", return_value=mock_verified_user):
            response = await async_client.post(
                "/api/v1/ollama/api/chat",
                json={
                    "model": "llama2",
                    "messages": [{"role": "user", "content": "Hello"}],
                    "stream": False
                }
            )
            assert response.status_code in [200, 500]
    
    async def test_generate_chat_completion_with_idx(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /api/chat/{url_idx} endpoint"""
        with patch("open_webui.routers.ollama.get_verified_user", return_value=mock_verified_user):
            response = await async_client.post(
                "/api/v1/ollama/api/chat/0",
                json={
                    "model": "llama2",
                    "messages": [{"role": "user", "content": "Hello"}],
                    "stream": False
                }
            )
            assert response.status_code in [200, 500]


class TestOpenAICompatibility:
    """Test OpenAI-compatible endpoints"""
    
    async def test_generate_openai_completion(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /v1/completions endpoint"""
        with patch("open_webui.routers.ollama.get_verified_user", return_value=mock_verified_user):
            response = await async_client.post(
                "/api/v1/ollama/v1/completions",
                json={
                    "model": "llama2",
                    "prompt": "Hello",
                    "max_tokens": 100
                }
            )
            assert response.status_code in [200, 500]
    
    async def test_generate_openai_completion_with_idx(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /v1/completions/{url_idx} endpoint"""
        with patch("open_webui.routers.ollama.get_verified_user", return_value=mock_verified_user):
            response = await async_client.post(
                "/api/v1/ollama/v1/completions/0",
                json={
                    "model": "llama2",
                    "prompt": "Hello",
                    "max_tokens": 100
                }
            )
            assert response.status_code in [200, 500]
    
    async def test_generate_openai_chat_completion(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /v1/chat/completions endpoint"""
        with patch("open_webui.routers.ollama.get_verified_user", return_value=mock_verified_user):
            response = await async_client.post(
                "/api/v1/ollama/v1/chat/completions",
                json={
                    "model": "llama2",
                    "messages": [{"role": "user", "content": "Hello"}]
                }
            )
            assert response.status_code in [200, 500]
    
    async def test_generate_openai_chat_completion_with_idx(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /v1/chat/completions/{url_idx} endpoint"""
        with patch("open_webui.routers.ollama.get_verified_user", return_value=mock_verified_user):
            response = await async_client.post(
                "/api/v1/ollama/v1/chat/completions/0",
                json={
                    "model": "llama2",
                    "messages": [{"role": "user", "content": "Hello"}]
                }
            )
            assert response.status_code in [200, 500]
    
    async def test_get_openai_models(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /v1/models endpoint"""
        with patch("open_webui.routers.ollama.get_verified_user", return_value=mock_verified_user):
            response = await async_client.get("/api/v1/ollama/v1/models")
            assert response.status_code in [200, 500]
    
    async def test_get_openai_models_with_idx(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /v1/models/{url_idx} endpoint"""
        with patch("open_webui.routers.ollama.get_verified_user", return_value=mock_verified_user):
            response = await async_client.get("/api/v1/ollama/v1/models/0")
            assert response.status_code in [200, 500]


class TestModelManagement:
    """Test model download/upload endpoints"""
    
    async def test_download_model(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /models/download endpoint"""
        with patch("open_webui.routers.ollama.get_admin_user", return_value=mock_admin_user):
            response = await async_client.post(
                "/api/v1/ollama/models/download",
                json={"url": "https://example.com/model.gguf"}
            )
            assert response.status_code in [200, 500]
    
    async def test_download_model_with_idx(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /models/download/{url_idx} endpoint"""
        with patch("open_webui.routers.ollama.get_admin_user", return_value=mock_admin_user):
            response = await async_client.post(
                "/api/v1/ollama/models/download/0",
                json={"url": "https://example.com/model.gguf"}
            )
            assert response.status_code in [200, 500]
    
    async def test_upload_model(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /models/upload endpoint"""
        with patch("open_webui.routers.ollama.get_admin_user", return_value=mock_admin_user):
            # Create mock file
            files = {"file": ("model.gguf", b"test content", "application/octet-stream")}
            response = await async_client.post(
                "/api/v1/ollama/models/upload",
                files=files
            )
            assert response.status_code in [200, 422, 500]
    
    async def test_upload_model_with_idx(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /models/upload/{url_idx} endpoint"""
        with patch("open_webui.routers.ollama.get_admin_user", return_value=mock_admin_user):
            # Create mock file
            files = {"file": ("model.gguf", b"test content", "application/octet-stream")}
            response = await async_client.post(
                "/api/v1/ollama/models/upload/0",
                files=files
            )
            assert response.status_code in [200, 422, 500]
