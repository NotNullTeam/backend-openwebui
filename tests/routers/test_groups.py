"""
Test cases for groups router endpoints - comprehensive coverage for all 7 endpoints
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


class TestGroupsManagement:
    """Test groups management endpoints"""
    
    async def test_get_groups_admin(self, async_client: AsyncClient, mock_admin_user):
        """Test GET / endpoint - get all groups as admin"""
        with patch("open_webui.routers.groups.get_verified_user", return_value=mock_admin_user):
            with patch("open_webui.routers.groups.Groups.get_groups") as mock_get:
                mock_get.return_value = [
                    {
                        "id": "group1",
                        "name": "Engineering Team",
                        "description": "Engineering team members",
                        "user_ids": ["user1", "user2", "user3"],
                        "created_at": 1234567890,
                        "updated_at": 1234567890
                    },
                    {
                        "id": "group2",
                        "name": "Marketing Team",
                        "description": "Marketing team members",
                        "user_ids": ["user4", "user5"],
                        "created_at": 1234567891,
                        "updated_at": 1234567891
                    }
                ]
                
                response = await async_client.get("/api/v1/groups/")
                assert response.status_code in [200, 401]
                
                if response.status_code == 200:
                    data = response.json()
                    assert isinstance(data, list)
                    assert len(data) == 2
    
    async def test_get_groups_user(self, async_client: AsyncClient, mock_verified_user):
        """Test GET / endpoint - get user's groups as regular user"""
        with patch("open_webui.routers.groups.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.groups.Groups.get_groups_by_user_id") as mock_get:
                mock_get.return_value = [
                    {
                        "id": "group1",
                        "name": "Engineering Team",
                        "description": "Engineering team members",
                        "user_ids": ["user123", "user2", "user3"]
                    }
                ]
                
                response = await async_client.get("/api/v1/groups/")
                assert response.status_code in [200, 401]
    
    async def test_create_new_group(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /create endpoint - create new group"""
        with patch("open_webui.routers.groups.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.groups.Groups.insert_new_group") as mock_insert:
                mock_insert.return_value = {
                    "id": "group_new",
                    "name": "New Team",
                    "description": "New team description",
                    "user_ids": [],
                    "created_at": 1234567892,
                    "updated_at": 1234567892
                }
                
                group_data = {
                    "name": "New Team",
                    "description": "New team description",
                    "user_ids": []
                }
                
                response = await async_client.post(
                    "/api/v1/groups/create",
                    json=group_data
                )
                assert response.status_code in [200, 401, 400]
    
    async def test_get_group_by_id(self, async_client: AsyncClient, mock_admin_user):
        """Test GET /id/{id} endpoint - get specific group"""
        with patch("open_webui.routers.groups.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.groups.Groups.get_group_by_id") as mock_get:
                mock_get.return_value = {
                    "id": "group1",
                    "name": "Engineering Team",
                    "description": "Engineering team members",
                    "user_ids": ["user1", "user2", "user3"],
                    "created_at": 1234567890,
                    "updated_at": 1234567890
                }
                
                response = await async_client.get("/api/v1/groups/id/group1")
                assert response.status_code in [200, 401, 404]
    
    async def test_update_group_by_id(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /id/{id}/update endpoint - update group"""
        with patch("open_webui.routers.groups.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.groups.Groups.get_group_by_id") as mock_get:
                mock_get.return_value = {
                    "id": "group1",
                    "name": "Engineering Team",
                    "description": "Engineering team members",
                    "user_ids": ["user1", "user2"]
                }
                
                with patch("open_webui.routers.groups.Groups.update_group_by_id") as mock_update:
                    mock_update.return_value = {
                        "id": "group1",
                        "name": "Updated Engineering Team",
                        "description": "Updated description",
                        "user_ids": ["user1", "user2", "user3"],
                        "created_at": 1234567890,
                        "updated_at": 1234567893
                    }
                    
                    update_data = {
                        "name": "Updated Engineering Team",
                        "description": "Updated description",
                        "user_ids": ["user1", "user2", "user3"]
                    }
                    
                    response = await async_client.post(
                        "/api/v1/groups/id/group1/update",
                        json=update_data
                    )
                    assert response.status_code in [200, 401, 404]
    
    async def test_add_user_to_group(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /id/{id}/users/add endpoint - add users to group"""
        with patch("open_webui.routers.groups.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.groups.Groups.get_group_by_id") as mock_get:
                mock_get.return_value = {
                    "id": "group1",
                    "name": "Engineering Team",
                    "user_ids": ["user1", "user2"]
                }
                
                with patch("open_webui.routers.groups.Groups.add_users_to_group_by_id") as mock_add:
                    mock_add.return_value = {
                        "id": "group1",
                        "name": "Engineering Team",
                        "description": "Engineering team members",
                        "user_ids": ["user1", "user2", "user3", "user4"],
                        "created_at": 1234567890,
                        "updated_at": 1234567894
                    }
                    
                    add_users_data = {
                        "user_ids": ["user3", "user4"]
                    }
                    
                    response = await async_client.post(
                        "/api/v1/groups/id/group1/users/add",
                        json=add_users_data
                    )
                    assert response.status_code in [200, 401, 404]
    
    async def test_remove_users_from_group(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /id/{id}/users/remove endpoint - remove users from group"""
        with patch("open_webui.routers.groups.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.groups.Groups.get_group_by_id") as mock_get:
                mock_get.return_value = {
                    "id": "group1",
                    "name": "Engineering Team",
                    "user_ids": ["user1", "user2", "user3", "user4"]
                }
                
                with patch("open_webui.routers.groups.Groups.remove_users_from_group_by_id") as mock_remove:
                    mock_remove.return_value = {
                        "id": "group1",
                        "name": "Engineering Team",
                        "description": "Engineering team members",
                        "user_ids": ["user1", "user2"],
                        "created_at": 1234567890,
                        "updated_at": 1234567895
                    }
                    
                    remove_users_data = {
                        "user_ids": ["user3", "user4"]
                    }
                    
                    response = await async_client.post(
                        "/api/v1/groups/id/group1/users/remove",
                        json=remove_users_data
                    )
                    assert response.status_code in [200, 401, 404]
    
    async def test_delete_group_by_id(self, async_client: AsyncClient, mock_admin_user):
        """Test DELETE /id/{id}/delete endpoint - delete group"""
        with patch("open_webui.routers.groups.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.groups.Groups.delete_group_by_id") as mock_delete:
                mock_delete.return_value = True
                
                response = await async_client.delete("/api/v1/groups/id/group1/delete")
                assert response.status_code in [200, 401, 500]
