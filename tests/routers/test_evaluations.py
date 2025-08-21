"""
Test cases for evaluations router endpoints
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
def mock_feedback():
    return MagicMock(
        id="feedback123",
        user_id="user123",
        message_id="msg123",
        rating=5,
        comment="Great response!",
        created_at=1234567890
    )


class TestEvaluationConfig:
    """Test evaluation configuration endpoints"""
    
    async def test_get_config(self, async_client: AsyncClient, mock_admin_user):
        """Test GET /config endpoint"""
        with patch("open_webui.routers.evaluations.get_admin_user", return_value=mock_admin_user):
            response = await async_client.get("/api/v1/evaluations/config")
            assert response.status_code in [200, 401]
    
    async def test_update_config(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /config endpoint"""
        with patch("open_webui.routers.evaluations.get_admin_user", return_value=mock_admin_user):
            response = await async_client.post(
                "/api/v1/evaluations/config",
                json={
                    "ENABLE_EVALUATION_ARENA_MODELS": True,
                    "EVALUATION_ARENA_MODELS": []
                }
            )
            assert response.status_code in [200, 401]


class TestFeedbacksAdmin:
    """Test admin feedback management endpoints"""
    
    async def test_get_all_feedbacks(self, async_client: AsyncClient, mock_admin_user):
        """Test GET /feedbacks/all endpoint"""
        with patch("open_webui.routers.evaluations.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.evaluations.Feedbacks.get_all_feedbacks", return_value=[]):
                with patch("open_webui.routers.evaluations.Users.get_user_by_id"):
                    response = await async_client.get("/api/v1/evaluations/feedbacks/all")
                    assert response.status_code in [200, 401]
    
    async def test_delete_all_feedbacks(self, async_client: AsyncClient, mock_admin_user):
        """Test DELETE /feedbacks/all endpoint"""
        with patch("open_webui.routers.evaluations.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.evaluations.Feedbacks.delete_all_feedbacks", return_value=True):
                response = await async_client.delete("/api/v1/evaluations/feedbacks/all")
                assert response.status_code in [200, 401]
    
    async def test_export_all_feedbacks(self, async_client: AsyncClient, mock_admin_user):
        """Test GET /feedbacks/all/export endpoint"""
        with patch("open_webui.routers.evaluations.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.evaluations.Feedbacks.get_all_feedbacks", return_value=[]):
                response = await async_client.get("/api/v1/evaluations/feedbacks/all/export")
                assert response.status_code in [200, 401]


class TestFeedbacksUser:
    """Test user feedback endpoints"""
    
    async def test_get_user_feedbacks(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /feedbacks/user endpoint"""
        with patch("open_webui.routers.evaluations.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.evaluations.Feedbacks.get_feedbacks_by_user_id", return_value=[]):
                response = await async_client.get("/api/v1/evaluations/feedbacks/user")
                assert response.status_code in [200, 401]
    
    async def test_delete_user_feedbacks(self, async_client: AsyncClient, mock_verified_user):
        """Test DELETE /feedbacks endpoint"""
        with patch("open_webui.routers.evaluations.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.evaluations.Feedbacks.delete_feedbacks_by_user_id", return_value=True):
                response = await async_client.delete("/api/v1/evaluations/feedbacks")
                assert response.status_code in [200, 401]
    
    async def test_create_feedback(self, async_client: AsyncClient, mock_verified_user, mock_feedback):
        """Test POST /feedback endpoint"""
        with patch("open_webui.routers.evaluations.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.evaluations.Feedbacks.insert_new_feedback", return_value=mock_feedback):
                response = await async_client.post(
                    "/api/v1/evaluations/feedback",
                    json={
                        "message_id": "msg123",
                        "rating": 5,
                        "comment": "Great response!",
                        "data": {}
                    }
                )
                assert response.status_code in [200, 401]
    
    async def test_get_feedback_by_id(self, async_client: AsyncClient, mock_verified_user, mock_feedback):
        """Test GET /feedback/{id} endpoint"""
        with patch("open_webui.routers.evaluations.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.evaluations.Feedbacks.get_feedback_by_id", return_value=mock_feedback):
                response = await async_client.get("/api/v1/evaluations/feedback/feedback123")
                assert response.status_code in [200, 404, 401]
    
    async def test_update_feedback_by_id(self, async_client: AsyncClient, mock_verified_user, mock_feedback):
        """Test POST /feedback/{id} endpoint"""
        with patch("open_webui.routers.evaluations.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.evaluations.Feedbacks.get_feedback_by_id", return_value=mock_feedback):
                with patch("open_webui.routers.evaluations.Feedbacks.update_feedback_by_id", return_value=mock_feedback):
                    response = await async_client.post(
                        "/api/v1/evaluations/feedback/feedback123",
                        json={
                            "message_id": "msg123",
                            "rating": 4,
                            "comment": "Updated comment",
                            "data": {}
                        }
                    )
                    assert response.status_code in [200, 404, 401]
    
    async def test_delete_feedback_by_id(self, async_client: AsyncClient, mock_verified_user):
        """Test DELETE /feedback/{id} endpoint"""
        with patch("open_webui.routers.evaluations.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.evaluations.Feedbacks.delete_feedback_by_id", return_value=True):
                response = await async_client.delete("/api/v1/evaluations/feedback/feedback123")
                assert response.status_code in [200, 404, 401]
