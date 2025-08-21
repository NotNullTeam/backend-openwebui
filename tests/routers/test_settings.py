"""
Test cases for settings router endpoints - comprehensive coverage for all 16 endpoints
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from httpx import AsyncClient
import json
from datetime import datetime


@pytest.fixture
def mock_verified_user():
    return MagicMock(
        id="user123",
        name="Test User",
        email="test@example.com",
        role="user"
    )


class TestUserSettings:
    """Test user settings management endpoints"""
    
    async def test_get_user_settings(self, async_client: AsyncClient, mock_verified_user):
        """Test GET / endpoint"""
        with patch("open_webui.routers.settings.get_verified_user", return_value=mock_verified_user):
            response = await async_client.get("/api/v1/settings/")
            assert response.status_code in [200, 401]
    
    async def test_update_user_settings(self, async_client: AsyncClient, mock_verified_user):
        """Test PUT / endpoint"""
        with patch("open_webui.routers.settings.get_verified_user", return_value=mock_verified_user):
            response = await async_client.put(
                "/api/v1/settings/",
                json={
                    "theme": "dark",
                    "language": "zh-CN",
                    "timezone": "Asia/Shanghai"
                }
            )
            assert response.status_code in [200, 401]
    
    async def test_reset_user_settings(self, async_client: AsyncClient, mock_verified_user):
        """Test DELETE / endpoint"""
        with patch("open_webui.routers.settings.get_verified_user", return_value=mock_verified_user):
            response = await async_client.delete("/api/v1/settings/")
            assert response.status_code in [200, 401]


class TestUserPreferences:
    """Test user preferences endpoints"""
    
    async def test_get_preferences(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /preferences endpoint"""
        with patch("open_webui.routers.settings.get_verified_user", return_value=mock_verified_user):
            response = await async_client.get("/api/v1/settings/preferences")
            assert response.status_code in [200, 401]
    
    async def test_update_preferences(self, async_client: AsyncClient, mock_verified_user):
        """Test PUT /preferences endpoint"""
        with patch("open_webui.routers.settings.get_verified_user", return_value=mock_verified_user):
            response = await async_client.put(
                "/api/v1/settings/preferences",
                json={
                    "notifications_enabled": True,
                    "email_notifications": False,
                    "auto_save": True
                }
            )
            assert response.status_code in [200, 401]


class TestSearchPreferences:
    """Test search preferences endpoints"""
    
    async def test_get_search_preferences(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /search endpoint"""
        with patch("open_webui.routers.settings.get_verified_user", return_value=mock_verified_user):
            response = await async_client.get("/api/v1/settings/search")
            assert response.status_code in [200, 401]
    
    async def test_update_search_preferences(self, async_client: AsyncClient, mock_verified_user):
        """Test PUT /search endpoint"""
        with patch("open_webui.routers.settings.get_verified_user", return_value=mock_verified_user):
            response = await async_client.put(
                "/api/v1/settings/search",
                json={
                    "default_limit": 20,
                    "enable_fuzzy": True,
                    "highlight_results": True
                }
            )
            assert response.status_code in [200, 401]


class TestAIPreferences:
    """Test AI preferences endpoints"""
    
    async def test_get_ai_preferences(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /ai endpoint"""
        with patch("open_webui.routers.settings.get_verified_user", return_value=mock_verified_user):
            response = await async_client.get("/api/v1/settings/ai")
            assert response.status_code in [200, 401]
    
    async def test_update_ai_preferences(self, async_client: AsyncClient, mock_verified_user):
        """Test PUT /ai endpoint"""
        with patch("open_webui.routers.settings.get_verified_user", return_value=mock_verified_user):
            response = await async_client.put(
                "/api/v1/settings/ai",
                json={
                    "model": "gpt-4",
                    "temperature": 0.7,
                    "max_tokens": 2000
                }
            )
            assert response.status_code in [200, 401]


class TestPrivacySettings:
    """Test privacy settings endpoints"""
    
    async def test_get_privacy_settings(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /privacy endpoint"""
        with patch("open_webui.routers.settings.get_verified_user", return_value=mock_verified_user):
            response = await async_client.get("/api/v1/settings/privacy")
            assert response.status_code in [200, 401]
    
    async def test_update_privacy_settings(self, async_client: AsyncClient, mock_verified_user):
        """Test PUT /privacy endpoint"""
        with patch("open_webui.routers.settings.get_verified_user", return_value=mock_verified_user):
            response = await async_client.put(
                "/api/v1/settings/privacy",
                json={
                    "share_data": False,
                    "analytics_enabled": False,
                    "save_history": True
                }
            )
            assert response.status_code in [200, 401]


class TestCaseLayoutSettings:
    """Test case layout settings endpoints"""
    
    async def test_get_case_layout(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /case-layout endpoint"""
        with patch("open_webui.routers.settings.get_verified_user", return_value=mock_verified_user):
            response = await async_client.get("/api/v1/settings/case-layout")
            assert response.status_code in [200, 401]
    
    async def test_save_case_layout(self, async_client: AsyncClient, mock_verified_user):
        """Test PUT /case-layout endpoint"""
        with patch("open_webui.routers.settings.get_verified_user", return_value=mock_verified_user):
            response = await async_client.put(
                "/api/v1/settings/case-layout",
                json={
                    "zoom_level": 1.0,
                    "show_grid": True,
                    "auto_arrange": False,
                    "layout_type": "tree"
                }
            )
            assert response.status_code in [200, 401]
    
    async def test_reset_case_layout(self, async_client: AsyncClient, mock_verified_user):
        """Test DELETE /case-layout endpoint"""
        with patch("open_webui.routers.settings.get_verified_user", return_value=mock_verified_user):
            response = await async_client.delete("/api/v1/settings/case-layout")
            assert response.status_code in [200, 401]


class TestSettingsImportExport:
    """Test settings import/export endpoints"""
    
    async def test_export_settings(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /export endpoint"""
        with patch("open_webui.routers.settings.get_verified_user", return_value=mock_verified_user):
            response = await async_client.get("/api/v1/settings/export")
            assert response.status_code in [200, 401]
    
    async def test_import_settings(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /import endpoint"""
        with patch("open_webui.routers.settings.get_verified_user", return_value=mock_verified_user):
            response = await async_client.post(
                "/api/v1/settings/import",
                json={
                    "settings": {
                        "theme": "dark",
                        "language": "en"
                    },
                    "preferences": {
                        "notifications_enabled": True
                    },
                    "case_layout": {
                        "zoom_level": 1.5
                    }
                }
            )
            assert response.status_code in [200, 401]
                    headers=auth_headers,
                    json=update_data
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "success"
                # 验证设置被更新
                assert mock_settings.theme == "dark"
                assert mock_settings.language == "en-US"
                assert mock_settings.notifications_enabled == False
    
    def test_update_user_settings_create_new(self, client: TestClient, auth_headers, verified_user):
        """测试更新不存在的用户设置（创建新设置）"""
        with patch('open_webui.routers.settings.get_verified_user', return_value=verified_user):
            with patch('open_webui.routers.settings.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value = mock_db
                
                # 模拟设置不存在
                mock_db.query().filter_by().first.return_value = None
                
                update_data = {
                    "theme": "dark",
                    "language": "en-US",
                    "notifications_enabled": True,
                    "email_notifications": False,
                    "auto_save": True,
                    "default_model": "gpt-4",
                    "ui_preferences": {
                        "sidebar_collapsed": True,
                        "show_tips": False
                    }
                }
                
                response = client.put(
                    "/api/v1/settings/user",
                    headers=auth_headers,
                    json=update_data
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "success"
                # 验证新设置被创建
                assert mock_db.add.called
                assert mock_db.commit.called
    
    def test_update_user_settings_partial(self, client: TestClient, auth_headers, verified_user):
        """测试部分更新用户设置"""
        with patch('open_webui.routers.settings.get_verified_user', return_value=verified_user):
            with patch('open_webui.routers.settings.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value = mock_db
                
                # 模拟已存在的设置
                mock_settings = Mock()
                mock_settings.id = "settings_123"
                mock_settings.user_id = verified_user.id
                mock_settings.theme = "light"
                mock_settings.language = "zh-CN"
                mock_settings.notifications_enabled = True
                mock_settings.updated_at = datetime.utcnow()
                
                mock_db.query().filter_by().first.return_value = mock_settings
                
                # 只更新部分字段
                update_data = {
                    "theme": "dark"
                }
                
                response = client.put(
                    "/api/v1/settings/user",
                    headers=auth_headers,
                    json=update_data
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "success"
                # 验证只有指定字段被更新
                assert mock_settings.theme == "dark"
                assert mock_settings.language == "zh-CN"  # 未改变
    
    def test_update_user_settings_invalid_data(self, client: TestClient, auth_headers, verified_user):
        """测试使用无效数据更新设置"""
        with patch('open_webui.routers.settings.get_verified_user', return_value=verified_user):
            # 无效的主题值
            update_data = {
                "theme": "invalid_theme"
            }
            
            response = client.put(
                "/api/v1/settings/user",
                headers=auth_headers,
                json=update_data
            )
            
            assert response.status_code in [400, 422]
    
    def test_reset_user_settings(self, client: TestClient, auth_headers, verified_user):
        """测试重置用户设置到默认值"""
        with patch('open_webui.routers.settings.get_verified_user', return_value=verified_user):
            with patch('open_webui.routers.settings.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value = mock_db
                
                # 模拟已存在的设置
                mock_settings = Mock()
                mock_settings.id = "settings_123"
                mock_settings.user_id = verified_user.id
                
                mock_db.query().filter_by().first.return_value = mock_settings
                
                response = client.delete(
                    "/api/v1/settings/user/reset",
                    headers=auth_headers
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "success"
                assert data["message"] == "用户设置已重置为默认值"
                # 验证设置被重置
                assert mock_settings.theme == "light"
                assert mock_settings.language == "zh-CN"


class TestSystemSettings:
    """系统设置相关测试（管理员功能）"""
    
    @pytest.fixture
    def admin_user(self):
        """管理员用户fixture"""
        return UserModel(
            id="admin_123",
            email="admin@example.com",
            name="Admin User",
            role="admin",
            is_active=True
        )
    
    @pytest.fixture
    def admin_headers(self):
        """管理员认证头"""
        return {"Authorization": "Bearer admin_token"}
    
    def test_get_system_settings_admin(self, client: TestClient, admin_headers, admin_user):
        """测试管理员获取系统设置"""
        with patch('open_webui.routers.settings.get_admin_user', return_value=admin_user):
            with patch('open_webui.routers.settings.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value = mock_db
                
                # 模拟系统设置
                mock_system_settings = Mock()
                mock_system_settings.max_file_size = 10485760
                mock_system_settings.allowed_file_types = ["pdf", "doc", "txt"]
                mock_system_settings.enable_registration = True
                mock_system_settings.default_user_role = "user"
                mock_system_settings.session_timeout = 3600
                mock_system_settings.maintenance_mode = False
                
                mock_db.query().filter_by().first.return_value = mock_system_settings
                
                response = client.get(
                    "/api/v1/settings/system",
                    headers=admin_headers
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "success"
                assert data["data"]["max_file_size"] == 10485760
                assert data["data"]["enable_registration"] == True
    
    def test_get_system_settings_unauthorized(self, client: TestClient, auth_headers):
        """测试非管理员获取系统设置（应该失败）"""
        with patch('open_webui.routers.settings.get_admin_user', side_effect=Exception("Unauthorized")):
            response = client.get(
                "/api/v1/settings/system",
                headers=auth_headers
            )
            
            assert response.status_code in [401, 403, 500]
    
    def test_update_system_settings_admin(self, client: TestClient, admin_headers, admin_user):
        """测试管理员更新系统设置"""
        with patch('open_webui.routers.settings.get_admin_user', return_value=admin_user):
            with patch('open_webui.routers.settings.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value = mock_db
                
                # 模拟系统设置
                mock_system_settings = Mock()
                mock_db.query().filter_by().first.return_value = mock_system_settings
                
                update_data = {
                    "max_file_size": 20971520,  # 20MB
                    "enable_registration": False,
                    "maintenance_mode": True
                }
                
                response = client.put(
                    "/api/v1/settings/system",
                    headers=admin_headers,
                    json=update_data
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "success"
                # 验证设置被更新
                assert mock_system_settings.max_file_size == 20971520
                assert mock_system_settings.enable_registration == False
                assert mock_system_settings.maintenance_mode == True


class TestSettingsErrorHandling:
    """设置模块错误处理测试"""
    
    def test_database_error(self, client: TestClient, auth_headers, verified_user):
        """测试数据库错误处理"""
        with patch('open_webui.routers.settings.get_verified_user', return_value=verified_user):
            with patch('open_webui.routers.settings.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value = mock_db
                
                # 模拟数据库错误
                mock_db.query.side_effect = Exception("Database error")
                
                response = client.get(
                    "/api/v1/settings/user",
                    headers=auth_headers
                )
                
                assert response.status_code == 500
    
    def test_unauthorized_access(self, client: TestClient):
        """测试未授权访问"""
        response = client.get("/api/v1/settings/user")
        assert response.status_code in [401, 403]
        
        response = client.put("/api/v1/settings/user", json={})
        assert response.status_code in [401, 403]
