"""
Test cases for channels router endpoints
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
def mock_channel():
    return {
        "id": "channel123",
        "name": "Test Channel",
        "data": {"description": "Test channel description"},
        "meta": {},
        "access_control": {"read": {"users": []}, "write": {"users": []}},
        "user_id": "admin123",
        "created_at": 1234567890,
        "updated_at": 1234567890
    }


@pytest.fixture
def mock_message():
    return {
        "id": "msg123",
        "channel_id": "channel123",
        "user_id": "user123",
        "content": "Test message content",
        "data": {},
        "meta": {},
        "created_at": 1234567890,
        "updated_at": 1234567890
    }


class TestChannelsList:
    """Test channels list endpoints"""
    
    async def test_get_channels(self, async_client: AsyncClient, mock_verified_user):
        """Test GET / endpoint"""
        with patch("open_webui.routers.channels.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.channels.Channels.get_channels_by_user_id", return_value=[]):
                response = await async_client.get("/api/v1/channels/")
                assert response.status_code == 200
                assert response.json() == []
    
    async def test_get_all_channels(self, async_client: AsyncClient, mock_admin_user):
        """Test GET /list endpoint"""
        with patch("open_webui.routers.channels.get_verified_user", return_value=mock_admin_user):
            with patch("open_webui.routers.channels.Channels.get_channels", return_value=[]):
                response = await async_client.get("/api/v1/channels/list")
                assert response.status_code == 200
                assert response.json() == []


class TestChannelCRUD:
    """Test channel CRUD operations"""
    
    async def test_create_channel(self, async_client: AsyncClient, mock_admin_user, mock_channel):
        """Test POST /create endpoint"""
        with patch("open_webui.routers.channels.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.channels.Channels.insert_new_channel", return_value=mock_channel):
                response = await async_client.post(
                    "/api/v1/channels/create",
                    json={
                        "name": "Test Channel",
                        "data": {"description": "Test channel description"},
                        "meta": {},
                        "access_control": {}
                    }
                )
                assert response.status_code == 200
                assert response.json()["id"] == "channel123"
    
    async def test_get_channel_by_id(self, async_client: AsyncClient, mock_verified_user, mock_channel):
        """Test GET /{id} endpoint"""
        with patch("open_webui.routers.channels.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.channels.Channels.get_channel_by_id", return_value=mock_channel):
                with patch("open_webui.routers.channels.has_access", return_value=True):
                    response = await async_client.get("/api/v1/channels/channel123")
                    assert response.status_code == 200
                    assert response.json()["id"] == "channel123"
    
    async def test_update_channel_by_id(self, async_client: AsyncClient, mock_admin_user, mock_channel):
        """Test POST /{id}/update endpoint"""
        with patch("open_webui.routers.channels.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.channels.Channels.get_channel_by_id", return_value=mock_channel):
                with patch("open_webui.routers.channels.Channels.update_channel_by_id", return_value=mock_channel):
                    response = await async_client.post(
                        "/api/v1/channels/channel123/update",
                        json={
                            "name": "Updated Channel",
                            "data": {"description": "Updated description"},
                            "meta": {},
                            "access_control": {}
                        }
                    )
                    assert response.status_code == 200
    
    async def test_delete_channel_by_id(self, async_client: AsyncClient, mock_admin_user, mock_channel):
        """Test DELETE /{id}/delete endpoint"""
        with patch("open_webui.routers.channels.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.channels.Channels.get_channel_by_id", return_value=mock_channel):
                with patch("open_webui.routers.channels.Channels.delete_channel_by_id", return_value=True):
                    with patch("open_webui.routers.channels.Messages.delete_messages_by_channel_id", return_value=True):
                        response = await async_client.delete("/api/v1/channels/channel123/delete")
                        assert response.status_code == 200
                        assert response.json() is True


class TestChannelMessages:
    """Test channel messages endpoints"""
    
    async def test_get_channel_messages(self, async_client: AsyncClient, mock_verified_user, mock_channel):
        """Test GET /{id}/messages endpoint"""
        with patch("open_webui.routers.channels.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.channels.Channels.get_channel_by_id", return_value=mock_channel):
                with patch("open_webui.routers.channels.has_access", return_value=True):
                    with patch("open_webui.routers.channels.Messages.get_messages_by_channel_id", return_value=[]):
                        response = await async_client.get("/api/v1/channels/channel123/messages")
                        assert response.status_code == 200
                        assert response.json() == []
    
    async def test_post_new_message(self, async_client: AsyncClient, mock_verified_user, mock_channel, mock_message):
        """Test POST /{id}/messages/post endpoint"""
        with patch("open_webui.routers.channels.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.channels.Channels.get_channel_by_id", return_value=mock_channel):
                with patch("open_webui.routers.channels.has_access", return_value=True):
                    with patch("open_webui.routers.channels.Messages.insert_new_message", return_value=mock_message):
                        response = await async_client.post(
                            "/api/v1/channels/channel123/messages/post",
                            json={
                                "content": "Test message content",
                                "data": {}
                            }
                        )
                        assert response.status_code == 200
                        assert response.json()["id"] == "msg123"
    
    async def test_get_channel_message(self, async_client: AsyncClient, mock_verified_user, mock_channel, mock_message):
        """Test GET /{id}/messages/{message_id} endpoint"""
        with patch("open_webui.routers.channels.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.channels.Channels.get_channel_by_id", return_value=mock_channel):
                with patch("open_webui.routers.channels.has_access", return_value=True):
                    with patch("open_webui.routers.channels.Messages.get_message_by_id", return_value=mock_message):
                        response = await async_client.get("/api/v1/channels/channel123/messages/msg123")
                        assert response.status_code == 200
    
    async def test_get_channel_thread_messages(self, async_client: AsyncClient, mock_verified_user, mock_channel):
        """Test GET /{id}/messages/{message_id}/thread endpoint"""
        with patch("open_webui.routers.channels.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.channels.Channels.get_channel_by_id", return_value=mock_channel):
                with patch("open_webui.routers.channels.has_access", return_value=True):
                    with patch("open_webui.routers.channels.Messages.get_messages_by_channel_id_and_parent_id", return_value=[]):
                        response = await async_client.get("/api/v1/channels/channel123/messages/msg123/thread")
                        assert response.status_code == 200
                        assert response.json() == []
    
    async def test_update_message_by_id(self, async_client: AsyncClient, mock_verified_user, mock_channel, mock_message):
        """Test POST /{id}/messages/{message_id}/update endpoint"""
        with patch("open_webui.routers.channels.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.channels.Channels.get_channel_by_id", return_value=mock_channel):
                with patch("open_webui.routers.channels.has_access", return_value=True):
                    with patch("open_webui.routers.channels.Messages.get_message_by_id", return_value=mock_message):
                        with patch("open_webui.routers.channels.Messages.update_message_by_id", return_value=mock_message):
                            response = await async_client.post(
                                "/api/v1/channels/channel123/messages/msg123/update",
                                json={"content": "Updated message"}
                            )
                            assert response.status_code == 200
    
    async def test_delete_message_by_id(self, async_client: AsyncClient, mock_verified_user, mock_channel, mock_message):
        """Test DELETE /{id}/messages/{message_id}/delete endpoint"""
        with patch("open_webui.routers.channels.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.channels.Channels.get_channel_by_id", return_value=mock_channel):
                with patch("open_webui.routers.channels.has_access", return_value=True):
                    with patch("open_webui.routers.channels.Messages.get_message_by_id", return_value=mock_message):
                        with patch("open_webui.routers.channels.Messages.delete_message_by_id", return_value=True):
                            with patch("open_webui.routers.channels.Messages.delete_messages_by_channel_id_and_parent_id", return_value=True):
                                response = await async_client.delete("/api/v1/channels/channel123/messages/msg123/delete")
                                assert response.status_code == 200
                                assert response.json() is True


class TestMessageReactions:
    """Test message reactions endpoints"""
    
    async def test_add_reaction_to_message(self, async_client: AsyncClient, mock_verified_user, mock_channel, mock_message):
        """Test POST /{id}/messages/{message_id}/reactions/add endpoint"""
        with patch("open_webui.routers.channels.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.channels.Channels.get_channel_by_id", return_value=mock_channel):
                with patch("open_webui.routers.channels.has_access", return_value=True):
                    with patch("open_webui.routers.channels.Messages.get_message_by_id", return_value=mock_message):
                        with patch("open_webui.routers.channels.Messages.update_message_by_id", return_value=mock_message):
                            response = await async_client.post(
                                "/api/v1/channels/channel123/messages/msg123/reactions/add",
                                json={"name": "👍"}
                            )
                            assert response.status_code == 200
    
    async def test_remove_reaction(self, async_client: AsyncClient, mock_verified_user, mock_channel, mock_message):
        """Test POST /{id}/messages/{message_id}/reactions/remove endpoint"""
        # Add a reaction to the message first
        mock_message_with_reaction = mock_message.copy()
        mock_message_with_reaction["meta"] = {
            "reactions": {
                "👍": ["user123"]
            }
        }
        
        with patch("open_webui.routers.channels.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.channels.Channels.get_channel_by_id", return_value=mock_channel):
                with patch("open_webui.routers.channels.has_access", return_value=True):
                    with patch("open_webui.routers.channels.Messages.get_message_by_id", return_value=mock_message_with_reaction):
                        with patch("open_webui.routers.channels.Messages.update_message_by_id", return_value=mock_message):
                            response = await async_client.post(
                                "/api/v1/channels/channel123/messages/msg123/reactions/remove",
                                json={"name": "👍"}
                            )
                            assert response.status_code == 200
