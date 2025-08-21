"""
认证模块登录端点测试
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from open_webui.main import app


client = TestClient(app)


class TestAuthLogin:
    """登录端点测试"""
    
    @patch('open_webui.models.auths.Auths.authenticate_user')
    @patch('open_webui.utils.auth.create_token')
    def test_login_success(self, mock_create_token, mock_authenticate):
        """测试登录成功"""
        # 模拟用户数据
        mock_user = MagicMock()
        mock_user.id = "test-user-id"
        mock_user.email = "test@example.com"
        mock_user.name = "Test User"
        mock_user.role = "user"
        mock_user.profile_image_url = "/user.png"
        
        mock_authenticate.return_value = mock_user
        mock_create_token.return_value = "test-token-123"
        
        # 发送登录请求
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": "password123"
            }
        )
        
        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data["token"] == "test-token-123"
        assert data["token_type"] == "Bearer"
        assert data["user"]["email"] == "test@example.com"
        assert data["user"]["name"] == "Test User"
        
        # 验证cookie设置
        assert "token" in response.cookies
    
    @patch('open_webui.models.auths.Auths.authenticate_user')
    def test_login_invalid_credentials(self, mock_authenticate):
        """测试无效凭证登录"""
        mock_authenticate.return_value = None
        
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": "wrong_password"
            }
        )
        
        assert response.status_code == 401
        assert "Invalid credentials" in response.json()["detail"]
    
    def test_login_invalid_email_format(self):
        """测试无效邮箱格式"""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "invalid-email",
                "password": "password123"
            }
        )
        
        assert response.status_code == 400
        assert "Invalid email format" in response.json()["detail"]
    
    def test_login_missing_fields(self):
        """测试缺少必填字段"""
        # 缺少密码
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@example.com"
            }
        )
        assert response.status_code == 422
        
        # 缺少邮箱
        response = client.post(
            "/api/v1/auth/login",
            json={
                "password": "password123"
            }
        )
        assert response.status_code == 422
    
    @patch('open_webui.models.auths.Auths.authenticate_user')
    @patch('open_webui.utils.auth.create_token')
    def test_login_with_token_expiry(self, mock_create_token, mock_authenticate):
        """测试带有过期时间的token生成"""
        mock_user = MagicMock()
        mock_user.id = "test-user-id"
        mock_user.email = "test@example.com"
        mock_user.name = "Test User"
        mock_user.role = "admin"
        mock_user.profile_image_url = "/admin.png"
        
        mock_authenticate.return_value = mock_user
        mock_create_token.return_value = "test-token-with-expiry"
        
        with patch('open_webui.routers.auth.parse_duration') as mock_parse:
            mock_parse.return_value = timedelta(hours=24)
            
            response = client.post(
                "/api/v1/auth/login",
                json={
                    "email": "test@example.com",
                    "password": "password123"
                }
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["token"] == "test-token-with-expiry"
        assert "expires_at" in data
        assert data["expires_at"] is not None
