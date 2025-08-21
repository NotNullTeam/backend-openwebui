"""
用户设置模块测试
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from datetime import datetime

from open_webui.models.user_settings import (
    UserSettingsModel,
    UserSettingsUpdateModel,
    UserSettingsManager
)


@pytest.fixture
def mock_user():
    """模拟已验证用户"""
    user = MagicMock()
    user.id = "test_user_123"
    user.email = "test@example.com"
    user.role = "user"
    return user


@pytest.fixture
def mock_settings():
    """模拟用户设置数据"""
    return UserSettingsModel(
        theme="dark",
        notifications={
            "solution": True,
            "mention": False,
            "system": True
        },
        preferences={
            "language": "zh-cn",
            "autoSave": True,
            "showHints": True,
            "fontSize": "medium",
            "sidebarCollapsed": False,
            "codeTheme": "monokai"
        },
        updated_at=datetime.utcnow()
    )


class TestUserSettingsAPI:
    """用户设置API测试类"""
    
    def test_get_user_settings_success(self, client: TestClient, mock_user, mock_settings):
        """测试获取用户设置成功"""
        with patch("open_webui.routers.user_settings.get_verified_user", return_value=mock_user):
            with patch.object(UserSettingsManager, "get_or_create_user_settings", return_value=mock_settings):
                response = client.get("/api/v1/user/settings")
                assert response.status_code == 200
                data = response.json()
                assert data["theme"] == "dark"
                assert data["notifications"]["solution"] is True
                assert data["preferences"]["language"] == "zh-cn"
    
    def test_get_user_settings_error(self, client: TestClient, mock_user):
        """测试获取用户设置失败"""
        with patch("open_webui.routers.user_settings.get_verified_user", return_value=mock_user):
            with patch.object(UserSettingsManager, "get_or_create_user_settings", side_effect=Exception("Database error")):
                response = client.get("/api/v1/user/settings")
                assert response.status_code == 500
                assert "获取用户设置失败" in response.json()["detail"]
    
    def test_update_user_settings_success(self, client: TestClient, mock_user, mock_settings):
        """测试更新用户设置成功"""
        update_data = {
            "theme": "light",
            "notifications": {
                "solution": False,
                "mention": True,
                "system": True
            }
        }
        
        updated_settings = UserSettingsModel(
            theme="light",
            notifications=update_data["notifications"],
            preferences=mock_settings.preferences,
            updated_at=datetime.utcnow()
        )
        
        with patch("open_webui.routers.user_settings.get_verified_user", return_value=mock_user):
            with patch.object(UserSettingsManager, "update_user_settings", return_value=updated_settings):
                response = client.put("/api/v1/user/settings", json=update_data)
                assert response.status_code == 200
                data = response.json()
                assert data["theme"] == "light"
                assert data["notifications"]["solution"] is False
                assert data["notifications"]["mention"] is True
    
    def test_update_user_settings_not_found(self, client: TestClient, mock_user):
        """测试更新不存在的用户设置"""
        update_data = {"theme": "light"}
        
        with patch("open_webui.routers.user_settings.get_verified_user", return_value=mock_user):
            with patch.object(UserSettingsManager, "update_user_settings", return_value=None):
                response = client.put("/api/v1/user/settings", json=update_data)
                assert response.status_code == 404
                assert "用户设置不存在" in response.json()["detail"]
    
    def test_get_user_preferences(self, client: TestClient, mock_user, mock_settings):
        """测试获取用户偏好设置"""
        with patch("open_webui.routers.user_settings.get_verified_user", return_value=mock_user):
            with patch.object(UserSettingsManager, "get_or_create_user_settings", return_value=mock_settings):
                response = client.get("/api/v1/user/preferences")
                assert response.status_code == 200
                data = response.json()
                assert data["code"] == 200
                assert data["status"] == "success"
                assert data["data"]["language"] == "zh-cn"
                assert data["data"]["autoSave"] is True
    
    def test_update_user_preferences(self, client: TestClient, mock_user, mock_settings):
        """测试更新用户偏好设置"""
        new_preferences = {
            "language": "en-us",
            "autoSave": False,
            "showHints": False,
            "fontSize": "large",
            "sidebarCollapsed": True,
            "codeTheme": "github"
        }
        
        updated_settings = UserSettingsModel(
            theme=mock_settings.theme,
            notifications=mock_settings.notifications,
            preferences=new_preferences,
            updated_at=datetime.utcnow()
        )
        
        with patch("open_webui.routers.user_settings.get_verified_user", return_value=mock_user):
            with patch.object(UserSettingsManager, "update_user_settings", return_value=updated_settings):
                response = client.put("/api/v1/user/preferences", json={"preferences": new_preferences})
                assert response.status_code == 200
                data = response.json()
                assert data["code"] == 200
                assert data["message"] == "用户偏好更新成功"
                assert data["data"]["language"] == "en-us"
                assert data["data"]["fontSize"] == "large"
    
    def test_get_user_theme(self, client: TestClient, mock_user, mock_settings):
        """测试获取用户主题设置"""
        with patch("open_webui.routers.user_settings.get_verified_user", return_value=mock_user):
            with patch.object(UserSettingsManager, "get_or_create_user_settings", return_value=mock_settings):
                response = client.get("/api/v1/user/theme")
                assert response.status_code == 200
                data = response.json()
                assert data["code"] == 200
                assert data["data"]["theme"] == "dark"
    
    def test_update_user_theme_success(self, client: TestClient, mock_user):
        """测试更新主题设置成功"""
        with patch("open_webui.routers.user_settings.get_verified_user", return_value=mock_user):
            with patch.object(UserSettingsManager, "update_theme", return_value=True):
                response = client.put("/api/v1/user/theme", json={"theme": "light"})
                assert response.status_code == 200
                data = response.json()
                assert data["code"] == 200
                assert data["message"] == "主题更新成功"
                assert data["data"]["theme"] == "light"
    
    def test_update_user_theme_invalid(self, client: TestClient, mock_user):
        """测试更新主题设置为无效值"""
        with patch("open_webui.routers.user_settings.get_verified_user", return_value=mock_user):
            response = client.put("/api/v1/user/theme", json={"theme": "invalid_theme"})
            assert response.status_code == 400
            assert "无效的主题值" in response.json()["detail"]
    
    def test_update_notification_preference_success(self, client: TestClient, mock_user):
        """测试更新通知偏好成功"""
        with patch("open_webui.routers.user_settings.get_verified_user", return_value=mock_user):
            with patch.object(UserSettingsManager, "update_notification_preference", return_value=True):
                response = client.put(
                    "/api/v1/user/notifications/preference",
                    json={"type": "solution", "enabled": False}
                )
                assert response.status_code == 200
                data = response.json()
                assert data["code"] == 200
                assert data["message"] == "通知偏好更新成功"
                assert data["data"]["type"] == "solution"
                assert data["data"]["enabled"] is False
    
    def test_update_notification_preference_invalid_type(self, client: TestClient, mock_user):
        """测试更新通知偏好使用无效类型"""
        with patch("open_webui.routers.user_settings.get_verified_user", return_value=mock_user):
            response = client.put(
                "/api/v1/user/notifications/preference",
                json={"type": "invalid_type", "enabled": True}
            )
            assert response.status_code == 400
            assert "无效的通知类型" in response.json()["detail"]
    
    def test_delete_user_settings_success(self, client: TestClient, mock_user):
        """测试删除用户设置成功"""
        with patch("open_webui.routers.user_settings.get_verified_user", return_value=mock_user):
            with patch.object(UserSettingsManager, "delete_user_settings", return_value=True):
                response = client.delete("/api/v1/user/settings")
                assert response.status_code == 200
                data = response.json()
                assert data["code"] == 200
                assert data["message"] == "用户设置已重置为默认值"
    
    def test_delete_user_settings_not_found(self, client: TestClient, mock_user):
        """测试删除不存在的用户设置"""
        with patch("open_webui.routers.user_settings.get_verified_user", return_value=mock_user):
            with patch.object(UserSettingsManager, "delete_user_settings", return_value=False):
                response = client.delete("/api/v1/user/settings")
                assert response.status_code == 200
                data = response.json()
                assert data["message"] == "用户设置已经是默认值"


class TestUserSettingsModel:
    """用户设置模型测试类"""
    
    def test_user_settings_model_defaults(self):
        """测试用户设置模型默认值"""
        settings = UserSettingsModel()
        assert settings.theme == "system"
        assert settings.notifications["solution"] is True
        assert settings.notifications["mention"] is False
        assert settings.notifications["system"] is True
        assert settings.preferences["language"] == "zh-cn"
        assert settings.preferences["autoSave"] is True
    
    def test_user_settings_update_model(self):
        """测试用户设置更新模型"""
        update = UserSettingsUpdateModel(
            theme="dark",
            notifications={"solution": False}
        )
        assert update.theme == "dark"
        assert update.notifications["solution"] is False
        assert update.preferences is None
    
    def test_user_settings_manager_get_or_create(self):
        """测试获取或创建用户设置"""
        with patch("open_webui.internal.db.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value.__enter__.return_value = mock_db
            
            # 模拟不存在的情况
            mock_db.query.return_value.filter_by.return_value.first.return_value = None
            
            settings = UserSettingsManager.get_or_create_user_settings("new_user_id")
            
            # 验证创建了新记录
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
