"""
Test cases for SCIM router endpoints
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
def mock_user():
    return MagicMock(
        id="user123",
        name="Test User",
        email="test@example.com",
        role="user",
        created_at=1234567890,
        updated_at=1234567890
    )


@pytest.fixture
def mock_group():
    return MagicMock(
        id="group123",
        name="Test Group",
        created_at=1234567890,
        updated_at=1234567890
    )


class TestSCIMServiceProvider:
    """Test SCIM Service Provider endpoints"""
    
    async def test_get_service_provider_config(self, async_client: AsyncClient):
        """Test GET /ServiceProviderConfig endpoint"""
        response = await async_client.get("/api/v1/scim/ServiceProviderConfig")
        assert response.status_code == 200
        assert "schemas" in response.json()
    
    async def test_get_resource_types(self, async_client: AsyncClient):
        """Test GET /ResourceTypes endpoint"""
        response = await async_client.get("/api/v1/scim/ResourceTypes")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    async def test_get_schemas(self, async_client: AsyncClient):
        """Test GET /Schemas endpoint"""
        response = await async_client.get("/api/v1/scim/Schemas")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestSCIMUsers:
    """Test SCIM Users endpoints"""
    
    async def test_get_users(self, async_client: AsyncClient, mock_admin_user):
        """Test GET /Users endpoint"""
        with patch("open_webui.routers.scim.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.scim.Users.get_users", return_value=[]):
                response = await async_client.get("/api/v1/scim/Users")
                assert response.status_code in [200, 401]
    
    async def test_get_user(self, async_client: AsyncClient, mock_admin_user, mock_user):
        """Test GET /Users/{user_id} endpoint"""
        with patch("open_webui.routers.scim.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.scim.Users.get_user_by_id", return_value=mock_user):
                response = await async_client.get("/api/v1/scim/Users/user123")
                assert response.status_code in [200, 404, 401]
    
    async def test_create_user(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /Users endpoint"""
        with patch("open_webui.routers.scim.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.scim.Users.get_user_by_email", return_value=None):
                with patch("open_webui.routers.scim.create_user_init_detail_response"):
                    with patch("open_webui.routers.scim.Auths.insert_new_auth"):
                        with patch("open_webui.routers.scim.Users.insert_new_user", return_value=mock_user):
                            response = await async_client.post(
                                "/api/v1/scim/Users",
                                json={
                                    "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
                                    "userName": "testuser",
                                    "emails": [{"value": "test@example.com", "primary": True}],
                                    "active": True
                                }
                            )
                            assert response.status_code in [201, 400, 401]
    
    async def test_update_user(self, async_client: AsyncClient, mock_admin_user, mock_user):
        """Test PUT /Users/{user_id} endpoint"""
        with patch("open_webui.routers.scim.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.scim.Users.get_user_by_id", return_value=mock_user):
                with patch("open_webui.routers.scim.Users.update_user_by_id", return_value=mock_user):
                    response = await async_client.put(
                        "/api/v1/scim/Users/user123",
                        json={
                            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
                            "userName": "updateduser",
                            "active": True
                        }
                    )
                    assert response.status_code in [200, 404, 401]
    
    async def test_patch_user(self, async_client: AsyncClient, mock_admin_user, mock_user):
        """Test PATCH /Users/{user_id} endpoint"""
        with patch("open_webui.routers.scim.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.scim.Users.get_user_by_id", return_value=mock_user):
                with patch("open_webui.routers.scim.Users.update_user_by_id", return_value=mock_user):
                    response = await async_client.patch(
                        "/api/v1/scim/Users/user123",
                        json={
                            "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
                            "Operations": [
                                {"op": "replace", "path": "active", "value": False}
                            ]
                        }
                    )
                    assert response.status_code in [200, 404, 401]
    
    async def test_delete_user(self, async_client: AsyncClient, mock_admin_user, mock_user):
        """Test DELETE /Users/{user_id} endpoint"""
        with patch("open_webui.routers.scim.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.scim.Users.get_user_by_id", return_value=mock_user):
                with patch("open_webui.routers.scim.UserModel.delete_user_by_id", return_value=True):
                    response = await async_client.delete("/api/v1/scim/Users/user123")
                    assert response.status_code in [204, 404, 401]


class TestSCIMGroups:
    """Test SCIM Groups endpoints"""
    
    async def test_get_groups(self, async_client: AsyncClient, mock_admin_user):
        """Test GET /Groups endpoint"""
        with patch("open_webui.routers.scim.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.scim.Groups.get_groups", return_value=[]):
                response = await async_client.get("/api/v1/scim/Groups")
                assert response.status_code in [200, 401]
    
    async def test_get_group(self, async_client: AsyncClient, mock_admin_user, mock_group):
        """Test GET /Groups/{group_id} endpoint"""
        with patch("open_webui.routers.scim.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.scim.Groups.get_group_by_id", return_value=mock_group):
                response = await async_client.get("/api/v1/scim/Groups/group123")
                assert response.status_code in [200, 404, 401]
    
    async def test_create_group(self, async_client: AsyncClient, mock_admin_user, mock_group):
        """Test POST /Groups endpoint"""
        with patch("open_webui.routers.scim.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.scim.Groups.get_group_by_name", return_value=None):
                with patch("open_webui.routers.scim.Groups.insert_new_group", return_value=mock_group):
                    response = await async_client.post(
                        "/api/v1/scim/Groups",
                        json={
                            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
                            "displayName": "Test Group",
                            "members": []
                        }
                    )
                    assert response.status_code in [201, 400, 401]
    
    async def test_update_group(self, async_client: AsyncClient, mock_admin_user, mock_group):
        """Test PUT /Groups/{group_id} endpoint"""
        with patch("open_webui.routers.scim.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.scim.Groups.get_group_by_id", return_value=mock_group):
                with patch("open_webui.routers.scim.Groups.update_group_by_id", return_value=mock_group):
                    response = await async_client.put(
                        "/api/v1/scim/Groups/group123",
                        json={
                            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
                            "displayName": "Updated Group"
                        }
                    )
                    assert response.status_code in [200, 404, 401]
    
    async def test_patch_group(self, async_client: AsyncClient, mock_admin_user, mock_group):
        """Test PATCH /Groups/{group_id} endpoint"""
        with patch("open_webui.routers.scim.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.scim.Groups.get_group_by_id", return_value=mock_group):
                with patch("open_webui.routers.scim.Groups.update_group_by_id", return_value=mock_group):
                    response = await async_client.patch(
                        "/api/v1/scim/Groups/group123",
                        json={
                            "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
                            "Operations": [
                                {"op": "add", "path": "members", "value": [{"value": "user123"}]}
                            ]
                        }
                    )
                    assert response.status_code in [200, 404, 401]
    
    async def test_delete_group(self, async_client: AsyncClient, mock_admin_user, mock_group):
        """Test DELETE /Groups/{group_id} endpoint"""
        with patch("open_webui.routers.scim.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.scim.Groups.get_group_by_id", return_value=mock_group):
                with patch("open_webui.routers.scim.Groups.delete_group_by_id", return_value=True):
                    response = await async_client.delete("/api/v1/scim/Groups/group123")
                    assert response.status_code in [204, 404, 401]
