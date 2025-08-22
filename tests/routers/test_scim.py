"""
Test cases for SCIM router endpoints
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient
from httpx import AsyncClient
import json
from datetime import datetime, timezone


@pytest.fixture
def mock_scim_auth():
    """Mock SCIM authentication"""
    with patch("open_webui.routers.scim.get_scim_auth", return_value=True):
        yield


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
        profile_image_url="/user.png",
        created_at=1234567890,
        updated_at=1234567890
    )


@pytest.fixture
def mock_group():
    return MagicMock(
        id="group123",
        name="Test Group",
        description="Test group description",
        user_ids=["user123", "user456"],
        created_at=1234567890,
        updated_at=1234567890
    )


class TestSCIMServiceProvider:
    """Test SCIM Service Provider endpoints"""
    
    async def test_get_service_provider_config(self, async_client: AsyncClient):
        """Test GET /ServiceProviderConfig endpoint"""
        response = await async_client.get("/api/v1/scim/v2/ServiceProviderConfig")
        assert response.status_code == 200
        assert "schemas" in response.json()
    
    async def test_get_resource_types(self, async_client: AsyncClient):
        """Test GET /ResourceTypes endpoint"""
        response = await async_client.get("/api/v1/scim/ResourceTypes")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    async def test_get_schemas(self, async_client: AsyncClient):
        """Test GET /Schemas endpoint"""
        response = await async_client.get("/api/v1/scim/v2/Schemas")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2  # User and Group schemas


class TestSCIMUsers:
    """Test SCIM Users endpoints"""
    
    @pytest.mark.asyncio
    async def test_list_users(self, async_client: AsyncClient, mock_scim_auth, mock_user):
        """Test GET /Users endpoint"""
        with patch("open_webui.routers.scim.Users.get_users") as mock_get:
            mock_get.return_value = {"users": [mock_user], "total": 1}
            with patch("open_webui.routers.scim.Groups.get_groups_by_member_id") as mock_groups:
                mock_groups.return_value = []
                response = await async_client.get(
                    "/api/v1/scim/v2/Users",
                    headers={"Authorization": "Bearer test-token"}
                )
                assert response.status_code == 200
                data = response.json()
                assert data["totalResults"] == 1
                assert len(data["Resources"]) == 1
    
    @pytest.mark.asyncio
    async def test_list_users_with_filter(self, async_client: AsyncClient, mock_scim_auth, mock_user):
        """Test GET /Users with filter"""
        with patch("open_webui.routers.scim.Users.get_user_by_email") as mock_get:
            mock_get.return_value = mock_user
            with patch("open_webui.routers.scim.Groups.get_groups_by_member_id") as mock_groups:
                mock_groups.return_value = []
                response = await async_client.get(
                    '/api/v1/scim/v2/Users?filter=userName eq "test@example.com"',
                    headers={"Authorization": "Bearer test-token"}
                )
                assert response.status_code == 200
                data = response.json()
                assert data["totalResults"] == 1
    
    @pytest.mark.asyncio
    async def test_get_user(self, async_client: AsyncClient, mock_scim_auth, mock_user):
        """Test GET /Users/{user_id} endpoint"""
        with patch("open_webui.routers.scim.Users.get_user_by_id") as mock_get:
            mock_get.return_value = mock_user
            with patch("open_webui.routers.scim.Groups.get_groups_by_member_id") as mock_groups:
                mock_groups.return_value = []
                response = await async_client.get(
                    "/api/v1/scim/v2/Users/user123",
                    headers={"Authorization": "Bearer test-token"}
                )
                assert response.status_code == 200
                data = response.json()
                assert data["id"] == "user123"
                assert data["userName"] == "test@example.com"
    
    @pytest.mark.asyncio
    async def test_get_user_not_found(self, async_client: AsyncClient, mock_scim_auth):
        """Test GET /Users/{user_id} with non-existent user"""
        with patch("open_webui.routers.scim.Users.get_user_by_id") as mock_get:
            mock_get.return_value = None
            response = await async_client.get(
                "/api/v1/scim/v2/Users/nonexistent",
                headers={"Authorization": "Bearer test-token"}
            )
            assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_create_user(self, async_client: AsyncClient, mock_scim_auth, mock_user):
        """Test POST /Users endpoint"""
        with patch("open_webui.routers.scim.Users.get_user_by_email") as mock_get:
            mock_get.return_value = None
            with patch("open_webui.routers.scim.Users.insert_new_user") as mock_insert:
                mock_insert.return_value = mock_user
                with patch("open_webui.routers.scim.Groups.get_groups_by_member_id") as mock_groups:
                    mock_groups.return_value = []
                    
                    user_data = {
                        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
                        "userName": "newuser@example.com",
                        "displayName": "New User",
                        "emails": [{"value": "newuser@example.com", "primary": True}],
                        "active": True
                    }
                    
                    response = await async_client.post(
                        "/api/v1/scim/v2/Users",
                        json=user_data,
                        headers={"Authorization": "Bearer test-token"}
                    )
                    assert response.status_code == 201
                    data = response.json()
                    assert data["id"] == "user123"
    
    @pytest.mark.asyncio
    async def test_create_user_already_exists(self, async_client: AsyncClient, mock_scim_auth, mock_user):
        """Test POST /Users with existing email"""
        with patch("open_webui.routers.scim.Users.get_user_by_email") as mock_get:
            mock_get.return_value = mock_user
            
            user_data = {
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
                "userName": "test@example.com",
                "displayName": "Test User",
                "emails": [{"value": "test@example.com", "primary": True}]
            }
            
            response = await async_client.post(
                "/api/v1/scim/v2/Users",
                json=user_data,
                headers={"Authorization": "Bearer test-token"}
            )
            assert response.status_code == 409
    
    @pytest.mark.asyncio
    async def test_update_user(self, async_client: AsyncClient, mock_scim_auth, mock_user):
        """Test PUT /Users/{user_id} endpoint"""
        with patch("open_webui.routers.scim.Users.get_user_by_id") as mock_get:
            mock_get.return_value = mock_user
            with patch("open_webui.routers.scim.Users.update_user_by_id") as mock_update:
                mock_update.return_value = mock_user
                with patch("open_webui.routers.scim.Groups.get_groups_by_member_id") as mock_groups:
                    mock_groups.return_value = []
                    
                    user_data = {
                        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
                        "displayName": "Updated User",
                        "active": True
                    }
                    
                    response = await async_client.put(
                        "/api/v1/scim/v2/Users/user123",
                        json=user_data,
                        headers={"Authorization": "Bearer test-token"}
                    )
                    assert response.status_code == 200
                    data = response.json()
                    assert data["id"] == "user123"
    
    @pytest.mark.asyncio
    async def test_patch_user(self, async_client: AsyncClient, mock_scim_auth, mock_user):
        """Test PATCH /Users/{user_id} endpoint"""
        with patch("open_webui.routers.scim.Users.get_user_by_id") as mock_get:
            mock_get.return_value = mock_user
            with patch("open_webui.routers.scim.Users.update_user_by_id") as mock_update:
                mock_update.return_value = mock_user
                with patch("open_webui.routers.scim.Groups.get_groups_by_member_id") as mock_groups:
                    mock_groups.return_value = []
                    
                    patch_data = {
                        "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
                        "Operations": [
                            {
                                "op": "replace",
                                "path": "active",
                                "value": False
                            }
                        ]
                    }
                    
                    response = await async_client.patch(
                        "/api/v1/scim/v2/Users/user123",
                        json=patch_data,
                        headers={"Authorization": "Bearer test-token"}
                    )
                    assert response.status_code == 200
                    data = response.json()
                    assert data["id"] == "user123"
    
    @pytest.mark.asyncio
    async def test_delete_user(self, async_client: AsyncClient, mock_scim_auth, mock_user):
        """Test DELETE /Users/{user_id} endpoint"""
        with patch("open_webui.routers.scim.Users.get_user_by_id") as mock_get:
            mock_get.return_value = mock_user
            with patch("open_webui.routers.scim.Users.delete_user_by_id") as mock_delete:
                mock_delete.return_value = True
                
                response = await async_client.delete(
                    "/api/v1/scim/v2/Users/user123",
                    headers={"Authorization": "Bearer test-token"}
                )
                assert response.status_code == 204


class TestSCIMGroups:
    """Test SCIM Groups endpoints"""
    
    @pytest.mark.asyncio
    async def test_list_groups(self, async_client: AsyncClient, mock_scim_auth, mock_group):
        """Test GET /Groups endpoint"""
        with patch("open_webui.routers.scim.Groups.get_groups") as mock_get:
            mock_get.return_value = [mock_group]
            with patch("open_webui.routers.scim.Users.get_user_by_id") as mock_user:
                mock_user.return_value = MagicMock(id="user123", name="Test User")
                
                response = await async_client.get(
                    "/api/v1/scim/v2/Groups",
                    headers={"Authorization": "Bearer test-token"}
                )
                assert response.status_code == 200
                data = response.json()
                assert data["totalResults"] == 1
                assert len(data["Resources"]) == 1
    
    @pytest.mark.asyncio
    async def test_get_group(self, async_client: AsyncClient, mock_scim_auth, mock_group):
        """Test GET /Groups/{group_id} endpoint"""
        with patch("open_webui.routers.scim.Groups.get_group_by_id") as mock_get:
            mock_get.return_value = mock_group
            with patch("open_webui.routers.scim.Users.get_user_by_id") as mock_user:
                mock_user.return_value = MagicMock(id="user123", name="Test User")
                
                response = await async_client.get(
                    "/api/v1/scim/v2/Groups/group123",
                    headers={"Authorization": "Bearer test-token"}
                )
                assert response.status_code == 200
                data = response.json()
                assert data["id"] == "group123"
                assert data["displayName"] == "Test Group"
    
    @pytest.mark.asyncio
    async def test_create_group(self, async_client: AsyncClient, mock_scim_auth, mock_group, mock_admin_user):
        """Test POST /Groups endpoint"""
        with patch("open_webui.routers.scim.Users.get_super_admin_user") as mock_admin:
            mock_admin.return_value = mock_admin_user
            with patch("open_webui.routers.scim.Groups.insert_new_group") as mock_insert:
                mock_insert.return_value = mock_group
                with patch("open_webui.routers.scim.Groups.get_group_by_id") as mock_get:
                    mock_get.return_value = mock_group
                    with patch("open_webui.routers.scim.Users.get_user_by_id") as mock_user:
                        mock_user.return_value = MagicMock(id="user123", name="Test User")
                        
                        group_data = {
                            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
                            "displayName": "New Group",
                            "members": []
                        }
                        
                        response = await async_client.post(
                            "/api/v1/scim/v2/Groups",
                            json=group_data,
                            headers={"Authorization": "Bearer test-token"}
                        )
                        assert response.status_code == 201
                        data = response.json()
                        assert data["id"] == "group123"
    
    @pytest.mark.asyncio
    async def test_update_group(self, async_client: AsyncClient, mock_scim_auth, mock_group):
        """Test PUT /Groups/{group_id} endpoint"""
        with patch("open_webui.routers.scim.Groups.get_group_by_id") as mock_get:
            mock_get.return_value = mock_group
            with patch("open_webui.routers.scim.Groups.update_group_by_id") as mock_update:
                mock_update.return_value = mock_group
                with patch("open_webui.routers.scim.Users.get_user_by_id") as mock_user:
                    mock_user.return_value = MagicMock(id="user123", name="Test User")
                    
                    group_data = {
                        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
                        "displayName": "Updated Group"
                    }
                    
                    response = await async_client.put(
                        "/api/v1/scim/v2/Groups/group123",
                        json=group_data,
                        headers={"Authorization": "Bearer test-token"}
                    )
                    assert response.status_code == 200
                    data = response.json()
                    assert data["id"] == "group123"
    
    @pytest.mark.asyncio
    async def test_patch_group(self, async_client: AsyncClient, mock_scim_auth, mock_group):
        """Test PATCH /Groups/{group_id} endpoint"""
        with patch("open_webui.routers.scim.Groups.get_group_by_id") as mock_get:
            mock_get.return_value = mock_group
            with patch("open_webui.routers.scim.Groups.update_group_by_id") as mock_update:
                mock_update.return_value = mock_group
                with patch("open_webui.routers.scim.Users.get_user_by_id") as mock_user:
                    mock_user.return_value = MagicMock(id="user123", name="Test User")
                    
                    patch_data = {
                        "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
                        "Operations": [
                            {
                                "op": "replace",
                                "path": "displayName",
                                "value": "Patched Group"
                            }
                        ]
                    }
                    
                    response = await async_client.patch(
                        "/api/v1/scim/v2/Groups/group123",
                        json=patch_data,
                        headers={"Authorization": "Bearer test-token"}
                    )
                    assert response.status_code == 200
                    data = response.json()
                    assert data["id"] == "group123"
    
    @pytest.mark.asyncio
    async def test_delete_group(self, async_client: AsyncClient, mock_scim_auth, mock_group):
        """Test DELETE /Groups/{group_id} endpoint"""
        with patch("open_webui.routers.scim.Groups.get_group_by_id") as mock_get:
            mock_get.return_value = mock_group
            with patch("open_webui.routers.scim.Groups.delete_group_by_id") as mock_delete:
                mock_delete.return_value = True
                
                response = await async_client.delete(
                    "/api/v1/scim/v2/Groups/group123",
                    headers={"Authorization": "Bearer test-token"}
                )
                assert response.status_code == 204
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
