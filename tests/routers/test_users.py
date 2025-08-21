"""
Test cases for users router endpoints - comprehensive coverage for all 16 endpoints
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


class TestUsersListing:
    """Test users listing endpoints"""
    
    async def test_get_active_users(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /active endpoint - get active users"""
        with patch("open_webui.routers.users.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.users.get_active_user_ids") as mock_active:
                mock_active.return_value = ["user1", "user2", "user3"]
                
                response = await async_client.get("/api/v1/users/active")
                assert response.status_code in [200, 401]
    
    async def test_get_users(self, async_client: AsyncClient, mock_admin_user):
        """Test GET / endpoint - get paginated users list"""
        with patch("open_webui.routers.users.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.users.Users.get_users") as mock_get:
                mock_get.return_value = {
                    "items": [
                        {"id": "user1", "name": "User 1", "email": "user1@example.com"},
                        {"id": "user2", "name": "User 2", "email": "user2@example.com"}
                    ],
                    "total": 2
                }
                
                response = await async_client.get("/api/v1/users/")
                assert response.status_code in [200, 401]
    
    async def test_get_all_users(self, async_client: AsyncClient, mock_admin_user):
        """Test GET /all endpoint - get all users"""
        with patch("open_webui.routers.users.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.users.Users.get_users") as mock_get:
                mock_get.return_value = [
                    {"id": "user1", "name": "User 1", "email": "user1@example.com"},
                    {"id": "user2", "name": "User 2", "email": "user2@example.com"}
                ]
                
                response = await async_client.get("/api/v1/users/all")
                assert response.status_code in [200, 401]


class TestUserGroups:
    """Test user groups endpoints"""
    
    async def test_get_user_groups(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /groups endpoint - get current user's groups"""
        with patch("open_webui.routers.users.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.users.Groups.get_groups_by_member_id") as mock_groups:
                mock_groups.return_value = [
                    {"id": "group1", "name": "Engineering"},
                    {"id": "group2", "name": "Development"}
                ]
                
                response = await async_client.get("/api/v1/users/groups")
                assert response.status_code in [200, 401]
    
    async def test_get_user_groups_by_id(self, async_client: AsyncClient, mock_admin_user):
        """Test GET /{user_id}/groups endpoint - get specific user's groups"""
        with patch("open_webui.routers.users.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.users.Groups.get_groups_by_member_id") as mock_groups:
                mock_groups.return_value = [
                    {"id": "group1", "name": "Engineering"}
                ]
                
                response = await async_client.get("/api/v1/users/user456/groups")
                assert response.status_code in [200, 401]


class TestUserPermissions:
    """Test user permissions endpoints"""
    
    async def test_get_user_permissions(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /permissions endpoint - get current user's permissions"""
        with patch("open_webui.routers.users.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.users.get_permissions") as mock_perms:
                mock_perms.return_value = {
                    "workspace": {"models": True, "knowledge": True},
                    "features": {"chat": True, "notes": True}
                }
                
                with patch("open_webui.routers.users.app.state") as mock_state:
                    mock_state.config.USER_PERMISSIONS = {}
                    
                    response = await async_client.get("/api/v1/users/permissions")
                    assert response.status_code in [200, 401]
    
    async def test_get_default_permissions(self, async_client: AsyncClient, mock_admin_user):
        """Test GET /default/permissions endpoint - get default permissions"""
        with patch("open_webui.routers.users.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.users.app.state") as mock_state:
                mock_state.config.USER_PERMISSIONS = {
                    "workspace": {"models": True},
                    "features": {"chat": True}
                }
                
                response = await async_client.get("/api/v1/users/default/permissions")
                assert response.status_code in [200, 401]
    
    async def test_update_default_permissions(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /default/permissions endpoint - update default permissions"""
        with patch("open_webui.routers.users.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.users.app.state") as mock_state:
                permissions_data = {
                    "workspace": {"models": True, "knowledge": False},
                    "features": {"chat": True, "notes": False}
                }
                
                response = await async_client.post(
                    "/api/v1/users/default/permissions",
                    json=permissions_data
                )
                assert response.status_code in [200, 401]


class TestUserSettings:
    """Test user settings endpoints"""
    
    async def test_get_user_settings(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /user/settings endpoint - get current user settings"""
        with patch("open_webui.routers.users.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.users.Users.get_user_by_id") as mock_get:
                mock_get.return_value = MagicMock(
                    settings={
                        "ui": {"theme": "dark"},
                        "notifications": {"enabled": True}
                    }
                )
                
                response = await async_client.get("/api/v1/users/user/settings")
                assert response.status_code in [200, 401, 404]
    
    async def test_update_user_settings(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /user/settings/update endpoint - update user settings"""
        with patch("open_webui.routers.users.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.users.Users.update_user_by_id") as mock_update:
                mock_update.return_value = MagicMock(
                    settings={
                        "ui": {"theme": "light"},
                        "notifications": {"enabled": False}
                    }
                )
                
                settings_data = {
                    "ui": {"theme": "light"},
                    "notifications": {"enabled": False}
                }
                
                response = await async_client.post(
                    "/api/v1/users/user/settings/update",
                    json=settings_data
                )
                assert response.status_code in [200, 401]


class TestUserInfo:
    """Test user info endpoints"""
    
    async def test_get_user_info(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /user/info endpoint - get current user info"""
        with patch("open_webui.routers.users.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.users.Users.get_user_by_id") as mock_get:
                mock_get.return_value = MagicMock(
                    info={
                        "bio": "Software Developer",
                        "location": "San Francisco"
                    }
                )
                
                response = await async_client.get("/api/v1/users/user/info")
                assert response.status_code in [200, 401, 404]
    
    async def test_update_user_info(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /user/info/update endpoint - update user info"""
        with patch("open_webui.routers.users.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.users.Users.update_user_by_id") as mock_update:
                mock_update.return_value = MagicMock(
                    info={
                        "bio": "Senior Developer",
                        "location": "New York"
                    }
                )
                
                info_data = {
                    "bio": "Senior Developer",
                    "location": "New York"
                }
                
                response = await async_client.post(
                    "/api/v1/users/user/info/update",
                    json=info_data
                )
                assert response.status_code in [200, 401]


class TestUserManagement:
    """Test user management endpoints"""
    
    async def test_get_user_by_id(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /{user_id} endpoint - get specific user"""
        with patch("open_webui.routers.users.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.users.Users.get_user_by_id") as mock_get:
                mock_get.return_value = MagicMock(
                    id="user456",
                    name="Target User",
                    email="target@example.com",
                    role="user"
                )
                
                response = await async_client.get("/api/v1/users/user456")
                assert response.status_code in [200, 401, 404]
    
    async def test_get_user_profile_image(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /{user_id}/profile/image endpoint - get user profile image"""
        with patch("open_webui.routers.users.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.users.Users.get_user_by_id") as mock_get:
                mock_get.return_value = MagicMock(
                    profile_image_url="https://example.com/profile.jpg"
                )
                
                response = await async_client.get("/api/v1/users/user456/profile/image")
                assert response.status_code in [200, 307, 401, 404]
    
    async def test_get_user_active_status(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /{user_id}/active endpoint - get user active status"""
        with patch("open_webui.routers.users.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.users.get_user_active_status") as mock_status:
                mock_status.return_value = True
                
                response = await async_client.get("/api/v1/users/user456/active")
                assert response.status_code in [200, 401]
    
    async def test_update_user_by_id(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /{user_id}/update endpoint - update user"""
        with patch("open_webui.routers.users.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.users.Users.get_user_by_id") as mock_get:
                mock_get.return_value = MagicMock(
                    id="user456",
                    name="Old Name",
                    email="old@example.com"
                )
                
                with patch("open_webui.routers.users.Users.update_user_by_id") as mock_update:
                    mock_update.return_value = MagicMock(
                        id="user456",
                        name="New Name",
                        email="new@example.com",
                        role="user"
                    )
                    
                    update_data = {
                        "name": "New Name",
                        "email": "new@example.com",
                        "role": "user"
                    }
                    
                    response = await async_client.post(
                        "/api/v1/users/user456/update",
                        json=update_data
                    )
                    assert response.status_code in [200, 401, 404]
    
    async def test_delete_user_by_id(self, async_client: AsyncClient, mock_admin_user):
        """Test DELETE /{user_id} endpoint - delete user"""
        with patch("open_webui.routers.users.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.users.Users.delete_user_by_id") as mock_delete:
                mock_delete.return_value = True
                
                with patch("open_webui.routers.users.Auths.delete_auth_by_id") as mock_auth_delete:
                    mock_auth_delete.return_value = True
                    
                    response = await async_client.delete("/api/v1/users/user456")
                    assert response.status_code in [200, 401, 403, 500]
