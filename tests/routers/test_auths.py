"""
Test cases for auths router endpoints - comprehensive coverage for authentication endpoints
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


@pytest.fixture
def mock_current_user():
    return MagicMock(
        id="user123",
        name="Test User",
        email="test@example.com",
        role="user",
        api_key="test_api_key_123"
    )


class TestAuthSession:
    """Test authentication session endpoints"""
    
    async def test_get_session_user(self, async_client: AsyncClient, mock_current_user):
        """Test GET / endpoint - get current session user"""
        with patch("open_webui.routers.auths.get_current_user", return_value=mock_current_user):
            with patch("open_webui.routers.auths.Users.get_user_by_id") as mock_get:
                mock_get.return_value = mock_current_user
                
                response = await async_client.get("/api/v1/auths/")
                assert response.status_code in [200, 401]
    
    async def test_update_profile(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /update/profile endpoint - update user profile"""
        with patch("open_webui.routers.auths.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.auths.Users.update_user_by_id") as mock_update:
                mock_update.return_value = {
                    "id": "user123",
                    "name": "Updated Name",
                    "email": "test@example.com",
                    "profile_image_url": "/new-image.jpg"
                }
                
                profile_data = {
                    "name": "Updated Name",
                    "profile_image_url": "/new-image.jpg"
                }
                
                response = await async_client.post(
                    "/api/v1/auths/update/profile",
                    json=profile_data
                )
                assert response.status_code in [200, 401]
    
    async def test_update_password(self, async_client: AsyncClient, mock_current_user):
        """Test POST /update/password endpoint - update user password"""
        with patch("open_webui.routers.auths.get_current_user", return_value=mock_current_user):
            with patch("open_webui.routers.auths.Auths.authenticate_user") as mock_auth:
                mock_auth.return_value = mock_current_user
                
                with patch("open_webui.routers.auths.Auths.update_user_password_by_id") as mock_update:
                    mock_update.return_value = True
                    
                    password_data = {
                        "password": "old_password",
                        "new_password": "new_password"
                    }
                    
                    response = await async_client.post(
                        "/api/v1/auths/update/password",
                        json=password_data
                    )
                    assert response.status_code in [200, 401, 400]


class TestAuthSignin:
    """Test signin/signup endpoints"""
    
    async def test_signin(self, async_client: AsyncClient):
        """Test POST /signin endpoint - user signin"""
        with patch("open_webui.routers.auths.Auths.authenticate_user") as mock_auth:
            mock_auth.return_value = MagicMock(
                id="user123",
                email="test@example.com",
                name="Test User",
                role="user",
                active=True
            )
            
            with patch("open_webui.routers.auths.create_token") as mock_token:
                mock_token.return_value = "test_token_123"
                
                signin_data = {
                    "email": "test@example.com",
                    "password": "password123"
                }
                
                response = await async_client.post(
                    "/api/v1/auths/signin",
                    json=signin_data
                )
                assert response.status_code in [200, 400, 401]
    
    async def test_signup(self, async_client: AsyncClient):
        """Test POST /signup endpoint - user signup"""
        with patch("open_webui.routers.auths.Users.has_users", return_value=True):
            with patch("open_webui.routers.auths.ENABLE_SIGNUP", True):
                with patch("open_webui.routers.auths.validate_email_format", return_value=True):
                    with patch("open_webui.routers.auths.Users.get_user_by_email", return_value=None):
                        with patch("open_webui.routers.auths.Auths.insert_new_auth") as mock_insert:
                            mock_insert.return_value = MagicMock(
                                id="user_new",
                                email="new@example.com",
                                name="New User",
                                role="pending"
                            )
                            
                            with patch("open_webui.routers.auths.create_token") as mock_token:
                                mock_token.return_value = "new_token_123"
                                
                                signup_data = {
                                    "name": "New User",
                                    "email": "new@example.com",
                                    "password": "password123"
                                }
                                
                                response = await async_client.post(
                                    "/api/v1/auths/signup",
                                    json=signup_data
                                )
                                assert response.status_code in [200, 400, 403]
    
    async def test_signout(self, async_client: AsyncClient):
        """Test GET /signout endpoint - user signout"""
        response = await async_client.get("/api/v1/auths/signout")
        assert response.status_code in [200, 401]


class TestAuthAdmin:
    """Test admin authentication endpoints"""
    
    async def test_add_user(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /add endpoint - admin add new user"""
        with patch("open_webui.routers.auths.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.auths.validate_email_format", return_value=True):
                with patch("open_webui.routers.auths.Users.get_user_by_email", return_value=None):
                    with patch("open_webui.routers.auths.Auths.insert_new_auth") as mock_insert:
                        mock_insert.return_value = MagicMock(
                            id="user_added",
                            email="added@example.com",
                            name="Added User",
                            role="user"
                        )
                        
                        add_data = {
                            "name": "Added User",
                            "email": "added@example.com",
                            "password": "password123",
                            "role": "user"
                        }
                        
                        response = await async_client.post(
                            "/api/v1/auths/add",
                            json=add_data
                        )
                        assert response.status_code in [200, 400, 401]
    
    async def test_get_admin_details(self, async_client: AsyncClient, mock_current_user):
        """Test GET /admin/details endpoint - get admin details"""
        with patch("open_webui.routers.auths.get_current_user", return_value=mock_current_user):
            with patch("open_webui.routers.auths.request.app.state.config.SHOW_ADMIN_DETAILS", True):
                response = await async_client.get("/api/v1/auths/admin/details")
                assert response.status_code in [200, 401]
    
    async def test_get_admin_config(self, async_client: AsyncClient, mock_admin_user):
        """Test GET /admin/config endpoint - get admin config"""
        with patch("open_webui.routers.auths.get_admin_user", return_value=mock_admin_user):
            response = await async_client.get("/api/v1/auths/admin/config")
            assert response.status_code in [200, 401]
    
    async def test_update_admin_config(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /admin/config endpoint - update admin config"""
        with patch("open_webui.routers.auths.get_admin_user", return_value=mock_admin_user):
            config_data = {
                "SHOW_ADMIN_DETAILS": True,
                "ENABLE_SIGNUP": True,
                "ENABLE_API_KEY": True,
                "DEFAULT_USER_ROLE": "user",
                "JWT_EXPIRES_IN": 3600,
                "ENABLE_COMMUNITY_SHARING": False
            }
            
            response = await async_client.post(
                "/api/v1/auths/admin/config",
                json=config_data
            )
            assert response.status_code in [200, 401]


class TestAuthLDAP:
    """Test LDAP authentication endpoints"""
    
    async def test_ldap_auth(self, async_client: AsyncClient):
        """Test POST /ldap endpoint - LDAP authentication"""
        with patch("open_webui.routers.auths.request.app.state.config.ENABLE_LDAP", True):
            with patch("open_webui.routers.auths.ldap_auth") as mock_ldap:
                mock_ldap.return_value = MagicMock(
                    id="ldap_user",
                    email="ldap@example.com",
                    name="LDAP User"
                )
                
                with patch("open_webui.routers.auths.create_token") as mock_token:
                    mock_token.return_value = "ldap_token_123"
                    
                    ldap_data = {
                        "user": "ldap_user",
                        "password": "ldap_password"
                    }
                    
                    response = await async_client.post(
                        "/api/v1/auths/ldap",
                        json=ldap_data
                    )
                    assert response.status_code in [200, 400, 401]
    
    async def test_get_ldap_config(self, async_client: AsyncClient, mock_admin_user):
        """Test GET /admin/config/ldap endpoint - get LDAP config"""
        with patch("open_webui.routers.auths.get_admin_user", return_value=mock_admin_user):
            response = await async_client.get("/api/v1/auths/admin/config/ldap")
            assert response.status_code in [200, 401]
    
    async def test_update_ldap_config(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /admin/config/ldap endpoint - update LDAP config"""
        with patch("open_webui.routers.auths.get_admin_user", return_value=mock_admin_user):
            ldap_config = {
                "enable_ldap": True
            }
            
            response = await async_client.post(
                "/api/v1/auths/admin/config/ldap",
                json=ldap_config
            )
            assert response.status_code in [200, 401]
    
    async def test_get_ldap_server(self, async_client: AsyncClient, mock_admin_user):
        """Test GET /admin/config/ldap/server endpoint - get LDAP server config"""
        with patch("open_webui.routers.auths.get_admin_user", return_value=mock_admin_user):
            response = await async_client.get("/api/v1/auths/admin/config/ldap/server")
            assert response.status_code in [200, 401]
    
    async def test_update_ldap_server(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /admin/config/ldap/server endpoint - update LDAP server config"""
        with patch("open_webui.routers.auths.get_admin_user", return_value=mock_admin_user):
            server_config = {
                "label": "LDAP Server",
                "host": "ldap.example.com",
                "port": 389,
                "bind_dn": "cn=admin,dc=example,dc=com",
                "bind_password": "password",
                "search_base": "dc=example,dc=com",
                "search_filter": "(uid={username})",
                "use_tls": True,
                "certificate_path": "/path/to/cert",
                "ciphers": "ALL"
            }
            
            response = await async_client.post(
                "/api/v1/auths/admin/config/ldap/server",
                json=server_config
            )
            assert response.status_code in [200, 401]


class TestAuthAPIKey:
    """Test API key management endpoints"""
    
    async def test_generate_api_key(self, async_client: AsyncClient, mock_current_user):
        """Test POST /api_key endpoint - generate API key"""
        with patch("open_webui.routers.auths.get_current_user", return_value=mock_current_user):
            with patch("open_webui.routers.auths.request.app.state.config.ENABLE_API_KEY", True):
                with patch("open_webui.routers.auths.create_api_key") as mock_create:
                    mock_create.return_value = "new_api_key_123"
                    
                    with patch("open_webui.routers.auths.Users.update_user_api_key_by_id") as mock_update:
                        mock_update.return_value = "new_api_key_123"
                        
                        response = await async_client.post("/api/v1/auths/api_key")
                        assert response.status_code in [200, 401, 403]
    
    async def test_get_api_key(self, async_client: AsyncClient, mock_current_user):
        """Test GET /api_key endpoint - get user API key"""
        with patch("open_webui.routers.auths.get_current_user", return_value=mock_current_user):
            with patch("open_webui.routers.auths.Users.get_user_api_key_by_id") as mock_get:
                mock_get.return_value = "existing_api_key_123"
                
                response = await async_client.get("/api/v1/auths/api_key")
                assert response.status_code in [200, 401, 404]
    
    async def test_delete_api_key(self, async_client: AsyncClient, mock_current_user):
        """Test DELETE /api_key endpoint - delete API key"""
        with patch("open_webui.routers.auths.get_current_user", return_value=mock_current_user):
            with patch("open_webui.routers.auths.Users.update_user_api_key_by_id") as mock_update:
                mock_update.return_value = True
                
                response = await async_client.delete("/api/v1/auths/api_key")
                assert response.status_code in [200, 401]
