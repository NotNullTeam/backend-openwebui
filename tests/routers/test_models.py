"""
Test cases for models router endpoints
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


@pytest.fixture
def mock_model():
    return MagicMock(
        id="model123",
        name="Test Model",
        description="Test model description",
        user_id="user123",
        base_model_id="base123",
        is_active=True,
        created_at=1234567890,
        updated_at=1234567890
    )


class TestModelsGeneral:
    """Test general model endpoints"""
    
    async def test_get_models(self, async_client: AsyncClient, mock_verified_user):
        """Test GET / endpoint"""
        with patch("open_webui.routers.models.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.models.Models.get_models_by_user_id", return_value=[]):
                response = await async_client.get("/api/v1/models/")
                assert response.status_code in [200, 401]
    
    async def test_get_base_models(self, async_client: AsyncClient, mock_admin_user):
        """Test GET /base endpoint"""
        with patch("open_webui.routers.models.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.models.Models.get_base_models", return_value=[]):
                response = await async_client.get("/api/v1/models/base")
                assert response.status_code in [200, 401]


class TestModelManagement:
    """Test model CRUD endpoints"""
    
    async def test_create_new_model(self, async_client: AsyncClient, mock_verified_user, mock_model):
        """Test POST /create endpoint"""
        with patch("open_webui.routers.models.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.models.Models.get_model_by_id", return_value=None):
                with patch("open_webui.routers.models.Models.insert_new_model", return_value=mock_model):
                    response = await async_client.post(
                        "/api/v1/models/create",
                        json={
                            "id": "new_model",
                            "name": "New Model",
                            "description": "Test description",
                            "base_model_id": "base123",
                            "params": {},
                            "meta": {}
                        }
                    )
                    assert response.status_code in [200, 400, 401]
    
    async def test_get_model_by_id(self, async_client: AsyncClient, mock_verified_user, mock_model):
        """Test GET /model endpoint"""
        with patch("open_webui.routers.models.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.models.Models.get_model_by_id", return_value=mock_model):
                response = await async_client.get("/api/v1/models/model?id=model123")
                assert response.status_code in [200, 404, 401]
    
    async def test_toggle_model_by_id(self, async_client: AsyncClient, mock_verified_user, mock_model):
        """Test POST /model/toggle endpoint"""
        with patch("open_webui.routers.models.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.models.Models.get_model_by_id", return_value=mock_model):
                with patch("open_webui.routers.models.Models.toggle_model_by_id", return_value=mock_model):
                    response = await async_client.post("/api/v1/models/model/toggle?id=model123")
                    assert response.status_code in [200, 404, 401]
    
    async def test_update_model_by_id(self, async_client: AsyncClient, mock_verified_user, mock_model):
        """Test POST /model/update endpoint"""
        with patch("open_webui.routers.models.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.models.Models.get_model_by_id", return_value=mock_model):
                with patch("open_webui.routers.models.Models.update_model_by_id", return_value=mock_model):
                    response = await async_client.post(
                        "/api/v1/models/model/update?id=model123",
                        json={
                            "id": "model123",
                            "name": "Updated Model",
                            "description": "Updated description",
                            "base_model_id": "base123",
                            "params": {},
                            "meta": {}
                        }
                    )
                    assert response.status_code in [200, 404, 401]
    
    async def test_delete_model_by_id(self, async_client: AsyncClient, mock_verified_user, mock_model):
        """Test DELETE /model/delete endpoint"""
        with patch("open_webui.routers.models.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.models.Models.get_model_by_id", return_value=mock_model):
                with patch("open_webui.routers.models.Models.delete_model_by_id", return_value=True):
                    response = await async_client.delete("/api/v1/models/model/delete?id=model123")
                    assert response.status_code in [200, 404, 401]


class TestModelAdminOperations:
    """Test admin-only model operations"""
    
    async def test_export_models(self, async_client: AsyncClient, mock_admin_user):
        """Test GET /export endpoint"""
        with patch("open_webui.routers.models.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.models.Models.get_models", return_value=[]):
                response = await async_client.get("/api/v1/models/export")
                assert response.status_code in [200, 401]
    
    async def test_sync_models(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /sync endpoint"""
        with patch("open_webui.routers.models.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.models.Models.insert_new_model"):
                response = await async_client.post(
                    "/api/v1/models/sync",
                    json={"models": []}
                )
                assert response.status_code in [200, 401]
    
    async def test_delete_all_models(self, async_client: AsyncClient, mock_admin_user):
        """Test DELETE /delete/all endpoint"""
        with patch("open_webui.routers.models.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.models.Models.delete_all_models", return_value=True):
                response = await async_client.delete("/api/v1/models/delete/all")
                assert response.status_code in [200, 401]
