"""
通知系统完整测试套件
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from datetime import datetime

from open_webui.main import app


client = TestClient(app)


class TestNotificationEndpoints:
    """通知系统所有端点的完整测试"""
    
    # ===== GET /notifications 获取通知列表 =====
    @patch('open_webui.routers.notifications.get_verified_user')
    @patch('open_webui.routers.notifications.Notifications.get_notifications_by_user_id')
    def test_get_notifications_success(self, mock_get_notifs, mock_user):
        """测试成功获取通知列表"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_get_notifs.return_value = [
            {
                "id": "notif-1",
                "user_id": "user-123",
                "title": "系统通知",
                "content": "您有新的任务",
                "type": "info",
                "read": False,
                "created_at": datetime.utcnow().isoformat()
            },
            {
                "id": "notif-2",
                "user_id": "user-123",
                "title": "警告",
                "content": "存储空间不足",
                "type": "warning",
                "read": True,
                "created_at": datetime.utcnow().isoformat()
            }
        ]
        
        response = client.get(
            "/api/v1/notifications",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["title"] == "系统通知"
        assert data[0]["read"] is False
        assert data[1]["type"] == "warning"
    
    @patch('open_webui.routers.notifications.get_verified_user')
    @patch('open_webui.routers.notifications.Notifications.get_notifications_by_user_id')
    def test_get_notifications_empty(self, mock_get_notifs, mock_user):
        """测试空通知列表"""
        mock_user.return_value = MagicMock(id="user-456")
        mock_get_notifs.return_value = []
        
        response = client.get(
            "/api/v1/notifications",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        assert response.json() == []
    
    # ===== POST /notifications 创建通知 =====
    @patch('open_webui.routers.notifications.get_admin_user')
    @patch('open_webui.routers.notifications.Notifications.insert_notification')
    def test_create_notification_admin(self, mock_insert, mock_admin):
        """测试管理员创建通知"""
        mock_admin.return_value = MagicMock(id="admin-123", role="admin")
        mock_insert.return_value = {
            "id": "notif-new",
            "user_id": "target-user",
            "title": "新通知",
            "content": "通知内容",
            "type": "info",
            "read": False,
            "created_at": datetime.utcnow().isoformat()
        }
        
        response = client.post(
            "/api/v1/notifications",
            json={
                "user_id": "target-user",
                "title": "新通知",
                "content": "通知内容",
                "type": "info"
            },
            headers={"Authorization": "Bearer admin-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "新通知"
        assert data["user_id"] == "target-user"
    
    @patch('open_webui.routers.notifications.get_admin_user')
    def test_create_notification_non_admin(self, mock_admin):
        """测试非管理员无法创建通知"""
        mock_admin.return_value = None
        
        response = client.post(
            "/api/v1/notifications",
            json={
                "user_id": "target-user",
                "title": "新通知",
                "content": "通知内容",
                "type": "info"
            },
            headers={"Authorization": "Bearer user-token"}
        )
        
        assert response.status_code == 403
    
    # ===== PUT /notifications/{id}/read 标记已读 =====
    @patch('open_webui.routers.notifications.get_verified_user')
    @patch('open_webui.routers.notifications.Notifications.get_notification_by_id')
    @patch('open_webui.routers.notifications.Notifications.mark_as_read')
    def test_mark_notification_read_success(self, mock_mark, mock_get, mock_user):
        """测试成功标记通知已读"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_get.return_value = {
            "id": "notif-1",
            "user_id": "user-123",
            "read": False
        }
        mock_mark.return_value = True
        
        response = client.put(
            "/api/v1/notifications/notif-1/read",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        assert response.json()["message"] == "通知已标记为已读"
    
    @patch('open_webui.routers.notifications.get_verified_user')
    @patch('open_webui.routers.notifications.Notifications.get_notification_by_id')
    def test_mark_notification_read_not_found(self, mock_get, mock_user):
        """测试标记不存在的通知"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_get.return_value = None
        
        response = client.put(
            "/api/v1/notifications/notif-999/read",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 404
    
    @patch('open_webui.routers.notifications.get_verified_user')
    @patch('open_webui.routers.notifications.Notifications.get_notification_by_id')
    def test_mark_notification_read_forbidden(self, mock_get, mock_user):
        """测试标记其他用户的通知"""
        mock_user.return_value = MagicMock(id="user-456", role="user")
        mock_get.return_value = {
            "id": "notif-1",
            "user_id": "user-123",  # 不同用户
            "read": False
        }
        
        response = client.put(
            "/api/v1/notifications/notif-1/read",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 403
    
    # ===== PUT /notifications/read-all 标记全部已读 =====
    @patch('open_webui.routers.notifications.get_verified_user')
    @patch('open_webui.routers.notifications.Notifications.mark_all_as_read')
    def test_mark_all_notifications_read(self, mock_mark_all, mock_user):
        """测试标记所有通知已读"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_mark_all.return_value = 5  # 标记了5条
        
        response = client.put(
            "/api/v1/notifications/read-all",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        assert response.json()["count"] == 5
    
    # ===== DELETE /notifications/{id} 删除通知 =====
    @patch('open_webui.routers.notifications.get_verified_user')
    @patch('open_webui.routers.notifications.Notifications.get_notification_by_id')
    @patch('open_webui.routers.notifications.Notifications.delete_notification')
    def test_delete_notification_success(self, mock_delete, mock_get, mock_user):
        """测试成功删除通知"""
        mock_user.return_value = MagicMock(id="user-123", role="user")
        mock_get.return_value = {
            "id": "notif-1",
            "user_id": "user-123"
        }
        mock_delete.return_value = True
        
        response = client.delete(
            "/api/v1/notifications/notif-1",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        assert response.json()["message"] == "通知已删除"
    
    @patch('open_webui.routers.notifications.get_verified_user')
    @patch('open_webui.routers.notifications.Notifications.get_notification_by_id')
    @patch('open_webui.routers.notifications.Notifications.delete_notification')
    def test_delete_notification_admin(self, mock_delete, mock_get, mock_user):
        """测试管理员删除任何通知"""
        mock_user.return_value = MagicMock(id="admin-123", role="admin")
        mock_get.return_value = {
            "id": "notif-1",
            "user_id": "user-456"  # 其他用户的通知
        }
        mock_delete.return_value = True
        
        response = client.delete(
            "/api/v1/notifications/notif-1",
            headers={"Authorization": "Bearer admin-token"}
        )
        
        assert response.status_code == 200
    
    # ===== DELETE /notifications/clear 清空通知 =====
    @patch('open_webui.routers.notifications.get_verified_user')
    @patch('open_webui.routers.notifications.Notifications.delete_all_by_user_id')
    def test_clear_all_notifications(self, mock_delete_all, mock_user):
        """测试清空所有通知"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_delete_all.return_value = 10  # 删除了10条
        
        response = client.delete(
            "/api/v1/notifications/clear",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        assert response.json()["count"] == 10
    
    # ===== 边界条件和异常测试 =====
    def test_invalid_notification_type(self):
        """测试无效的通知类型"""
        with patch('open_webui.routers.notifications.get_admin_user') as mock_admin:
            mock_admin.return_value = MagicMock(role="admin")
            
            response = client.post(
                "/api/v1/notifications",
                json={
                    "user_id": "user-123",
                    "title": "测试",
                    "content": "内容",
                    "type": "invalid_type"  # 无效类型
                },
                headers={"Authorization": "Bearer admin-token"}
            )
            
            assert response.status_code == 400
    
    @patch('open_webui.routers.notifications.get_verified_user')
    @patch('open_webui.routers.notifications.Notifications.get_notifications_by_user_id')
    def test_database_error_handling(self, mock_get_notifs, mock_user):
        """测试数据库错误处理"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_get_notifs.side_effect = Exception("Database connection failed")
        
        response = client.get(
            "/api/v1/notifications",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 500
    
    def test_missing_required_fields(self):
        """测试缺少必填字段"""
        with patch('open_webui.routers.notifications.get_admin_user') as mock_admin:
            mock_admin.return_value = MagicMock(role="admin")
            
            # 缺少title
            response = client.post(
                "/api/v1/notifications",
                json={
                    "user_id": "user-123",
                    "content": "内容",
                    "type": "info"
                },
                headers={"Authorization": "Bearer admin-token"}
            )
            
            assert response.status_code == 422
    
    @patch('open_webui.routers.notifications.get_verified_user')
    @patch('open_webui.routers.notifications.Notifications.get_notifications_by_user_id')
    def test_pagination_support(self, mock_get_notifs, mock_user):
        """测试分页支持"""
        mock_user.return_value = MagicMock(id="user-123")
        
        # 生成大量通知数据
        notifications = [
            {
                "id": f"notif-{i}",
                "user_id": "user-123",
                "title": f"通知 {i}",
                "content": f"内容 {i}",
                "type": "info",
                "read": i % 2 == 0,
                "created_at": datetime.utcnow().isoformat()
            }
            for i in range(100)
        ]
        mock_get_notifs.return_value = notifications[:20]  # 返回前20条
        
        response = client.get(
            "/api/v1/notifications?page=1&limit=20",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 20
