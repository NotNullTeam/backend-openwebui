"""
用户设置模块完整测试套件
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime
import json

from open_webui.main import app


client = TestClient(app)


class TestUserSettingsEndpoints:
    """用户设置所有端点的完整测试"""
    
    # ===== GET /user/settings 获取用户设置 =====
    @patch('open_webui.routers.user_settings.get_verified_user')
    @patch('open_webui.routers.user_settings.UserSettings.get_settings_by_user')
    def test_get_user_settings(self, mock_get_settings, mock_user):
        """测试获取用户设置"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_get_settings.return_value = {
            "user_id": "user-123",
            "theme": "dark",
            "language": "zh-CN",
            "notification_enabled": True,
            "email_notifications": {
                "case_updates": True,
                "system_alerts": False,
                "weekly_digest": True
            },
            "display_preferences": {
                "items_per_page": 20,
                "sidebar_collapsed": False,
                "show_tips": True
            }
        }
        
        response = client.get(
            "/api/v1/user/settings",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["theme"] == "dark"
        assert data["language"] == "zh-CN"
        assert data["notification_enabled"] is True
    
    # ===== PUT /user/settings 更新用户设置 =====
    @patch('open_webui.routers.user_settings.get_verified_user')
    @patch('open_webui.routers.user_settings.UserSettings.update_settings')
    def test_update_user_settings(self, mock_update, mock_user):
        """测试更新用户设置"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_update.return_value = {
            "user_id": "user-123",
            "theme": "light",
            "language": "en-US",
            "updated_at": datetime.utcnow().isoformat()
        }
        
        response = client.put(
            "/api/v1/user/settings",
            json={
                "theme": "light",
                "language": "en-US"
            },
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["theme"] == "light"
        assert data["language"] == "en-US"
    
    # ===== GET /user/profile 获取用户资料 =====
    @patch('open_webui.routers.user_settings.get_verified_user')
    @patch('open_webui.routers.user_settings.Users.get_user_by_id')
    def test_get_user_profile(self, mock_get_user, mock_user):
        """测试获取用户资料"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_get_user.return_value = {
            "id": "user-123",
            "name": "张三",
            "email": "zhangsan@example.com",
            "role": "user",
            "avatar": "https://example.com/avatar.jpg",
            "created_at": datetime.utcnow().isoformat(),
            "last_login": datetime.utcnow().isoformat()
        }
        
        response = client.get(
            "/api/v1/user/profile",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "张三"
        assert data["email"] == "zhangsan@example.com"
    
    # ===== PUT /user/profile 更新用户资料 =====
    @patch('open_webui.routers.user_settings.get_verified_user')
    @patch('open_webui.routers.user_settings.Users.update_user')
    def test_update_user_profile(self, mock_update, mock_user):
        """测试更新用户资料"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_update.return_value = {
            "id": "user-123",
            "name": "李四",
            "avatar": "https://example.com/new-avatar.jpg"
        }
        
        response = client.put(
            "/api/v1/user/profile",
            json={
                "name": "李四",
                "avatar": "https://example.com/new-avatar.jpg"
            },
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "李四"
    
    # ===== PUT /user/password 修改密码 =====
    @patch('open_webui.routers.user_settings.get_verified_user')
    @patch('open_webui.routers.user_settings.verify_password')
    @patch('open_webui.routers.user_settings.hash_password')
    @patch('open_webui.routers.user_settings.Users.update_password')
    def test_change_password(self, mock_update_pw, mock_hash, mock_verify, mock_user):
        """测试修改密码"""
        mock_user.return_value = MagicMock(id="user-123", password="old_hash")
        mock_verify.return_value = True
        mock_hash.return_value = "new_hash"
        mock_update_pw.return_value = True
        
        response = client.put(
            "/api/v1/user/password",
            json={
                "old_password": "oldpass123",
                "new_password": "newpass456"
            },
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        assert response.json()["message"] == "密码修改成功"
    
    # ===== GET /user/notifications/preferences 通知偏好 =====
    @patch('open_webui.routers.user_settings.get_verified_user')
    @patch('open_webui.routers.user_settings.NotificationPreferences.get_by_user')
    def test_get_notification_preferences(self, mock_get_prefs, mock_user):
        """测试获取通知偏好"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_get_prefs.return_value = {
            "email": {
                "enabled": True,
                "frequency": "instant",
                "types": ["case_updates", "mentions"]
            },
            "web_push": {
                "enabled": False
            },
            "in_app": {
                "enabled": True,
                "sound": True,
                "desktop": True
            }
        }
        
        response = client.get(
            "/api/v1/user/notifications/preferences",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"]["enabled"] is True
        assert data["in_app"]["sound"] is True
    
    # ===== PUT /user/notifications/preferences 更新通知偏好 =====
    @patch('open_webui.routers.user_settings.get_verified_user')
    @patch('open_webui.routers.user_settings.NotificationPreferences.update')
    def test_update_notification_preferences(self, mock_update, mock_user):
        """测试更新通知偏好"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_update.return_value = {
            "email": {"enabled": False},
            "web_push": {"enabled": True}
        }
        
        response = client.put(
            "/api/v1/user/notifications/preferences",
            json={
                "email": {"enabled": False},
                "web_push": {"enabled": True}
            },
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"]["enabled"] is False
    
    # ===== GET /user/shortcuts 快捷键设置 =====
    @patch('open_webui.routers.user_settings.get_verified_user')
    @patch('open_webui.routers.user_settings.UserShortcuts.get_by_user')
    def test_get_keyboard_shortcuts(self, mock_get_shortcuts, mock_user):
        """测试获取快捷键设置"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_get_shortcuts.return_value = {
            "new_case": "Ctrl+N",
            "search": "Ctrl+K",
            "save": "Ctrl+S",
            "help": "F1",
            "custom": {
                "quick_analysis": "Alt+A",
                "export_report": "Ctrl+E"
            }
        }
        
        response = client.get(
            "/api/v1/user/shortcuts",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["new_case"] == "Ctrl+N"
        assert data["custom"]["quick_analysis"] == "Alt+A"
    
    # ===== PUT /user/shortcuts 更新快捷键 =====
    @patch('open_webui.routers.user_settings.get_verified_user')
    @patch('open_webui.routers.user_settings.UserShortcuts.update')
    def test_update_keyboard_shortcuts(self, mock_update, mock_user):
        """测试更新快捷键设置"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_update.return_value = {
            "search": "Ctrl+F",
            "custom": {"quick_save": "Ctrl+Q"}
        }
        
        response = client.put(
            "/api/v1/user/shortcuts",
            json={
                "search": "Ctrl+F",
                "custom": {"quick_save": "Ctrl+Q"}
            },
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["search"] == "Ctrl+F"
    
    # ===== POST /user/export 导出用户数据 =====
    @patch('open_webui.routers.user_settings.get_verified_user')
    @patch('open_webui.routers.user_settings.export_user_data')
    def test_export_user_data(self, mock_export, mock_user):
        """测试导出用户数据"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_export.return_value = b"exported data content"
        
        response = client.post(
            "/api/v1/user/export",
            json={"format": "json", "include": ["settings", "cases", "files"]},
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
    
    # ===== DELETE /user/account 删除账户 =====
    @patch('open_webui.routers.user_settings.get_verified_user')
    @patch('open_webui.routers.user_settings.verify_password')
    @patch('open_webui.routers.user_settings.Users.delete_user')
    def test_delete_account(self, mock_delete, mock_verify, mock_user):
        """测试删除账户"""
        mock_user.return_value = MagicMock(id="user-123", password="hash")
        mock_verify.return_value = True
        mock_delete.return_value = True
        
        response = client.delete(
            "/api/v1/user/account",
            json={"password": "password123", "confirmation": "DELETE"},
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        assert response.json()["message"] == "账户已删除"
    
    # ===== 边界条件和异常测试 =====
    @patch('open_webui.routers.user_settings.get_verified_user')
    @patch('open_webui.routers.user_settings.verify_password')
    def test_change_password_wrong_old(self, mock_verify, mock_user):
        """测试修改密码时旧密码错误"""
        mock_user.return_value = MagicMock(id="user-123", password="hash")
        mock_verify.return_value = False
        
        response = client.put(
            "/api/v1/user/password",
            json={
                "old_password": "wrongpass",
                "new_password": "newpass456"
            },
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 401
        assert "旧密码错误" in response.json()["detail"]
    
    @patch('open_webui.routers.user_settings.get_verified_user')
    def test_weak_password_rejected(self, mock_user):
        """测试弱密码被拒绝"""
        mock_user.return_value = MagicMock(id="user-123")
        
        response = client.put(
            "/api/v1/user/password",
            json={
                "old_password": "oldpass",
                "new_password": "123"  # 太弱
            },
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 400
        assert "密码强度" in response.json()["detail"]
    
    @patch('open_webui.routers.user_settings.get_verified_user')
    def test_invalid_theme_rejected(self, mock_user):
        """测试无效主题被拒绝"""
        mock_user.return_value = MagicMock(id="user-123")
        
        response = client.put(
            "/api/v1/user/settings",
            json={"theme": "invalid-theme"},
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 422
    
    @patch('open_webui.routers.user_settings.get_verified_user')
    @patch('open_webui.routers.user_settings.export_user_data')
    def test_export_large_data_limit(self, mock_export, mock_user):
        """测试导出数据大小限制"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_export.side_effect = MemoryError("Data too large")
        
        response = client.post(
            "/api/v1/user/export",
            json={"format": "json", "include": ["all"]},
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 413
        assert "数据太大" in response.json()["detail"]
