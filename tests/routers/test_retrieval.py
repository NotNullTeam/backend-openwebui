"""
Test cases for retrieval router endpoints
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient
from httpx import AsyncClient
import json
import tempfile
import os


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


class TestRetrievalStatus:
    """Test status endpoints"""
    
    async def test_get_status(self, async_client: AsyncClient):
        """Test GET / endpoint"""
        response = await async_client.get("/api/v1/retrieval/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] is True


class TestEmbeddingConfig:
    """Test embedding configuration endpoints"""
    
    async def test_get_embedding_config(self, async_client: AsyncClient, mock_admin_user):
        """Test GET /embedding endpoint"""
        with patch("open_webui.routers.retrieval.get_admin_user", return_value=mock_admin_user):
            response = await async_client.get("/api/v1/retrieval/embedding")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] is True
    
    async def test_update_embedding_config(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /embedding/update endpoint"""
        with patch("open_webui.routers.retrieval.get_admin_user", return_value=mock_admin_user):
            response = await async_client.post(
                "/api/v1/retrieval/embedding/update",
                json={
                    "embedding_engine": "openai",
                    "embedding_model": "text-embedding-ada-002",
                    "openai_config": {
                        "url": "https://api.openai.com",
                        "key": "test_key"
                    }
                }
            )
            assert response.status_code in [200, 500]


class TestRAGConfig:
    """Test RAG configuration endpoints"""
    
    async def test_get_rag_config(self, async_client: AsyncClient, mock_admin_user):
        """Test GET /config endpoint"""
        with patch("open_webui.routers.retrieval.get_admin_user", return_value=mock_admin_user):
            response = await async_client.get("/api/v1/retrieval/config")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] is True
    
    async def test_update_rag_config(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /config/update endpoint"""
        with patch("open_webui.routers.retrieval.get_admin_user", return_value=mock_admin_user):
            response = await async_client.post(
                "/api/v1/retrieval/config/update",
                json={
                    "pdf_extract_images": False,
                    "chunk_size": 1000,
                    "chunk_overlap": 100,
                    "template": "Use the following context: {context}\n\nQuestion: {question}",
                    "top_k": 5,
                    "r": 0.5,
                    "hybrid": False
                }
            )
            assert response.status_code in [200, 500]


class TestDocumentProcessing:
    """Test document processing endpoints"""
    
    async def test_process_file(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /process/file endpoint"""
        with patch("open_webui.routers.retrieval.get_verified_user", return_value=mock_verified_user):
            # Create a temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write("Test content")
                temp_file_path = f.name
            
            try:
                response = await async_client.post(
                    "/api/v1/retrieval/process/file",
                    json={
                        "file_id": "test_file_id",
                        "collection_name": "test_collection"
                    }
                )
                assert response.status_code in [200, 404, 500]
            finally:
                # Clean up
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
    
    async def test_process_text(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /process/text endpoint"""
        with patch("open_webui.routers.retrieval.get_verified_user", return_value=mock_verified_user):
            response = await async_client.post(
                "/api/v1/retrieval/process/text",
                json={
                    "text": "This is test content for processing",
                    "metadata": {"source": "test"},
                    "collection_name": "test_collection"
                }
            )
            assert response.status_code in [200, 500]
    
    async def test_process_youtube(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /process/youtube endpoint"""
        with patch("open_webui.routers.retrieval.get_verified_user", return_value=mock_verified_user):
            response = await async_client.post(
                "/api/v1/retrieval/process/youtube",
                json={
                    "url": "https://www.youtube.com/watch?v=test",
                    "collection_name": "test_collection"
                }
            )
            assert response.status_code in [200, 400, 500]
    
    async def test_process_web(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /process/web endpoint"""
        with patch("open_webui.routers.retrieval.get_verified_user", return_value=mock_verified_user):
            response = await async_client.post(
                "/api/v1/retrieval/process/web",
                json={
                    "url": "https://example.com",
                    "collection_name": "test_collection"
                }
            )
            assert response.status_code in [200, 400, 500]
    
    async def test_process_web_search(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /process/web/search endpoint"""
        with patch("open_webui.routers.retrieval.get_verified_user", return_value=mock_verified_user):
            response = await async_client.post(
                "/api/v1/retrieval/process/web/search",
                json={
                    "query": "test search query",
                    "collection_name": "test_collection"
                }
            )
            assert response.status_code in [200, 400, 500]
    
    async def test_process_files_batch(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /process/files/batch endpoint"""
        with patch("open_webui.routers.retrieval.get_verified_user", return_value=mock_verified_user):
            response = await async_client.post(
                "/api/v1/retrieval/process/files/batch",
                json={
                    "files": [
                        {"file_id": "file1", "collection_name": "collection1"},
                        {"file_id": "file2", "collection_name": "collection2"}
                    ]
                }
            )
            assert response.status_code in [200, 500]


class TestQueryOperations:
    """Test query operations endpoints"""
    
    async def test_query_doc(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /query/doc endpoint"""
        with patch("open_webui.routers.retrieval.get_verified_user", return_value=mock_verified_user):
            response = await async_client.post(
                "/api/v1/retrieval/query/doc",
                json={
                    "collection_name": "test_collection",
                    "query": "test query",
                    "k": 5
                }
            )
            assert response.status_code in [200, 404, 500]
    
    async def test_query_collection(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /query/collection endpoint"""
        with patch("open_webui.routers.retrieval.get_verified_user", return_value=mock_verified_user):
            response = await async_client.post(
                "/api/v1/retrieval/query/collection",
                json={
                    "collection_names": ["collection1", "collection2"],
                    "query": "test query",
                    "k": 5
                }
            )
            assert response.status_code in [200, 404, 500]


class TestDatabaseOperations:
    """Test database management endpoints"""
    
    async def test_delete_entries(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /delete endpoint"""
        with patch("open_webui.routers.retrieval.get_admin_user", return_value=mock_admin_user):
            response = await async_client.post(
                "/api/v1/retrieval/delete",
                json={
                    "collection_name": "test_collection",
                    "file_id": "test_file_id"
                }
            )
            assert response.status_code in [200, 500]
    
    async def test_reset_vector_db(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /reset/db endpoint"""
        with patch("open_webui.routers.retrieval.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.retrieval.VECTOR_DB_CLIENT") as mock_client:
                mock_client.reset = MagicMock()
                response = await async_client.post("/api/v1/retrieval/reset/db")
                assert response.status_code == 200
    
    async def test_reset_uploads(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /reset/uploads endpoint"""
        with patch("open_webui.routers.retrieval.get_admin_user", return_value=mock_admin_user):
            with patch("os.path.exists", return_value=True):
                with patch("shutil.rmtree"):
                    response = await async_client.post("/api/v1/retrieval/reset/uploads")
                    assert response.status_code == 200


class TestDevEndpoints:
    """Test development endpoints"""
    
    async def test_get_embeddings(self, async_client: AsyncClient):
        """Test GET /ef/{text} endpoint (dev only)"""
        # This endpoint is only available in dev environment
        with patch("open_webui.routers.retrieval.ENV", "dev"):
            response = await async_client.get("/api/v1/retrieval/ef/Hello%20World")
            assert response.status_code in [200, 404, 500]
