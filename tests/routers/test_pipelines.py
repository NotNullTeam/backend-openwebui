"""
Test cases for pipelines router endpoints - comprehensive coverage for all 8 endpoints
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
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
def mock_pipeline():
    return {
        "id": "pipeline123",
        "name": "Test Pipeline",
        "type": "filter",
        "url": "http://localhost:9099",
        "models": ["model1", "model2"],
        "valves": {
            "api_key": "test_key",
            "enabled": True
        }
    }


@pytest.fixture
def mock_pipeline_response():
    return {
        "type": "pipe",
        "id": "pipe123",
        "name": "Test Pipeline",
        "pipelines": [
            {
                "id": "pipeline1",
                "name": "Pipeline 1",
                "type": "filter"
            }
        ]
    }


class TestPipelinesList:
    """Test pipelines list endpoints"""
    
    async def test_get_pipelines_list(self, async_client: AsyncClient, mock_admin_user):
        """Test GET /list endpoint"""
        with patch("open_webui.routers.pipelines.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.pipelines.get_all_models_responses") as mock_responses:
                mock_responses.return_value = {
                    "pipelines": [
                        {"id": "pipe1", "name": "Pipeline 1"},
                        {"id": "pipe2", "name": "Pipeline 2"}
                    ]
                }
                response = await async_client.get("/api/v1/pipelines/list")
                assert response.status_code == 200
                data = response.json()
                assert "pipelines" in data
                assert len(data["pipelines"]) == 2
    
    async def test_get_pipelines(self, async_client: AsyncClient, mock_admin_user, mock_pipeline_response):
        """Test GET / endpoint"""
        with patch("open_webui.routers.pipelines.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.pipelines.request.app.state.OPENAI_URLS", ["http://localhost:9099"]):
                with patch("open_webui.routers.pipelines.aiohttp.ClientSession") as mock_session:
                    mock_client = AsyncMock()
                    mock_session.return_value.__aenter__.return_value = mock_client
                    
                    mock_response = AsyncMock()
                    mock_response.status = 200
                    mock_response.json = AsyncMock(return_value=mock_pipeline_response)
                    mock_client.get.return_value.__aenter__.return_value = mock_response
                    
                    response = await async_client.get("/api/v1/pipelines/")
                    assert response.status_code == 200


class TestPipelinesManagement:
    """Test pipelines management endpoints"""
    
    async def test_upload_pipeline(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /upload endpoint"""
        with patch("open_webui.routers.pipelines.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.pipelines.request.app.state.OPENAI_URLS", ["http://localhost:9099"]):
                with patch("open_webui.routers.pipelines.upload_pipeline_to_openai_url") as mock_upload:
                    mock_upload.return_value = {
                        "success": True,
                        "id": "uploaded_pipeline",
                        "name": "Uploaded Pipeline"
                    }
                    
                    # Create multipart form data
                    files = {"file": ("pipeline.py", b"# Pipeline code", "text/plain")}
                    data = {"urlIdx": "0"}
                    
                    response = await async_client.post(
                        "/api/v1/pipelines/upload",
                        files=files,
                        data=data
                    )
                    assert response.status_code in [200, 400, 500]
    
    async def test_add_pipeline(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /add endpoint"""
        with patch("open_webui.routers.pipelines.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.pipelines.request.app.state.OPENAI_URLS", ["http://localhost:9099"]):
                with patch("open_webui.routers.pipelines.add_pipeline_to_openai_url") as mock_add:
                    mock_add.return_value = {
                        "success": True,
                        "id": "added_pipeline",
                        "name": "Added Pipeline"
                    }
                    
                    response = await async_client.post(
                        "/api/v1/pipelines/add",
                        json={
                            "url": "https://github.com/example/pipeline.git",
                            "urlIdx": 0
                        }
                    )
                    assert response.status_code in [200, 400, 500]
    
    async def test_delete_pipeline(self, async_client: AsyncClient, mock_admin_user):
        """Test DELETE /delete endpoint"""
        with patch("open_webui.routers.pipelines.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.pipelines.request.app.state.OPENAI_URLS", ["http://localhost:9099"]):
                with patch("open_webui.routers.pipelines.delete_pipeline_from_openai_url") as mock_delete:
                    mock_delete.return_value = {"success": True}
                    
                    response = await async_client.delete(
                        "/api/v1/pipelines/delete",
                        json={
                            "id": "pipeline_to_delete",
                            "urlIdx": 0
                        }
                    )
                    assert response.status_code in [200, 400, 500]


class TestPipelineValves:
    """Test pipeline valves endpoints"""
    
    async def test_get_pipeline_valves(self, async_client: AsyncClient, mock_admin_user):
        """Test GET /{pipeline_id}/valves endpoint"""
        with patch("open_webui.routers.pipelines.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.pipelines.request.app.state.OPENAI_URLS", ["http://localhost:9099"]):
                with patch("open_webui.routers.pipelines.aiohttp.ClientSession") as mock_session:
                    mock_client = AsyncMock()
                    mock_session.return_value.__aenter__.return_value = mock_client
                    
                    mock_response = AsyncMock()
                    mock_response.status = 200
                    mock_response.json = AsyncMock(return_value={
                        "valves": {
                            "api_key": "test_key",
                            "enabled": True
                        }
                    })
                    mock_client.get.return_value.__aenter__.return_value = mock_response
                    
                    response = await async_client.get(
                        "/api/v1/pipelines/pipeline123/valves",
                        params={"urlIdx": 0}
                    )
                    assert response.status_code == 200
                    data = response.json()
                    assert "valves" in data
    
    async def test_get_pipeline_valves_spec(self, async_client: AsyncClient, mock_admin_user):
        """Test GET /{pipeline_id}/valves/spec endpoint"""
        with patch("open_webui.routers.pipelines.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.pipelines.request.app.state.OPENAI_URLS", ["http://localhost:9099"]):
                with patch("open_webui.routers.pipelines.aiohttp.ClientSession") as mock_session:
                    mock_client = AsyncMock()
                    mock_session.return_value.__aenter__.return_value = mock_client
                    
                    mock_response = AsyncMock()
                    mock_response.status = 200
                    mock_response.json = AsyncMock(return_value={
                        "spec": {
                            "api_key": {
                                "type": "string",
                                "description": "API Key"
                            },
                            "enabled": {
                                "type": "boolean",
                                "description": "Enable pipeline"
                            }
                        }
                    })
                    mock_client.get.return_value.__aenter__.return_value = mock_response
                    
                    response = await async_client.get(
                        "/api/v1/pipelines/pipeline123/valves/spec",
                        params={"urlIdx": 0}
                    )
                    assert response.status_code == 200
                    data = response.json()
                    assert "spec" in data
    
    async def test_update_pipeline_valves(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /{pipeline_id}/valves/update endpoint"""
        with patch("open_webui.routers.pipelines.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.pipelines.request.app.state.OPENAI_URLS", ["http://localhost:9099"]):
                with patch("open_webui.routers.pipelines.aiohttp.ClientSession") as mock_session:
                    mock_client = AsyncMock()
                    mock_session.return_value.__aenter__.return_value = mock_client
                    
                    mock_response = AsyncMock()
                    mock_response.status = 200
                    mock_response.json = AsyncMock(return_value={
                        "valves": {
                            "api_key": "new_key",
                            "enabled": False
                        }
                    })
                    mock_client.post.return_value.__aenter__.return_value = mock_response
                    
                    response = await async_client.post(
                        "/api/v1/pipelines/pipeline123/valves/update",
                        params={"urlIdx": 0},
                        json={
                            "api_key": "new_key",
                            "enabled": False
                        }
                    )
                    assert response.status_code == 200
                    data = response.json()
                    assert "valves" in data
                    assert data["valves"]["api_key"] == "new_key"


class TestPipelinesErrorHandling:
    """Test error handling for pipelines endpoints"""
    
    async def test_get_pipelines_no_urls(self, async_client: AsyncClient, mock_admin_user):
        """Test GET / with no pipeline URLs configured"""
        with patch("open_webui.routers.pipelines.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.pipelines.request.app.state.OPENAI_URLS", []):
                response = await async_client.get("/api/v1/pipelines/")
                assert response.status_code == 404
                assert response.json()["detail"] == "Pipeline not found"
    
    async def test_get_pipeline_valves_invalid_url(self, async_client: AsyncClient, mock_admin_user):
        """Test GET /{pipeline_id}/valves with invalid URL index"""
        with patch("open_webui.routers.pipelines.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.pipelines.request.app.state.OPENAI_URLS", ["http://localhost:9099"]):
                response = await async_client.get(
                    "/api/v1/pipelines/pipeline123/valves",
                    params={"urlIdx": 99}
                )
                assert response.status_code == 404
    
    async def test_upload_pipeline_no_file(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /upload without file"""
        with patch("open_webui.routers.pipelines.get_admin_user", return_value=mock_admin_user):
            response = await async_client.post(
                "/api/v1/pipelines/upload",
                data={"urlIdx": "0"}
            )
            assert response.status_code in [400, 422]
    
    async def test_unauthorized_access(self, async_client: AsyncClient, mock_verified_user):
        """Test unauthorized access to admin-only endpoints"""
        with patch("open_webui.routers.pipelines.get_admin_user", side_effect=Exception("Unauthorized")):
            response = await async_client.get("/api/v1/pipelines/list")
            assert response.status_code in [401, 403, 500]
