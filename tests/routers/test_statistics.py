"""
统计分析模块测试用例
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import json

from open_webui.main import app
from open_webui.models.users import UserModel


@pytest.fixture
def verified_user():
    """已验证用户fixture"""
    return UserModel(
        id="user_123",
        email="user@example.com",
        name="Test User",
        role="user",
        is_active=True
    )


@pytest.fixture
def auth_headers():
    """认证头"""
    return {"Authorization": "Bearer test_token"}


class TestHotIssuesStatistics:
    """热点问题统计测试"""
    
    def test_get_hot_issues_default(self, client: TestClient, auth_headers, verified_user):
        """测试获取默认热点问题统计"""
        with patch('open_webui.routers.statistics.get_verified_user', return_value=verified_user):
            with patch('open_webui.routers.statistics.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value = mock_db
                
                # 模拟查询结果
                mock_result = [
                    ("IP地址冲突", 150),
                    ("网络连接中断", 120),
                    ("路由器配置错误", 95),
                    ("DNS解析失败", 88),
                    ("DHCP分配异常", 76)
                ]
                mock_db.query().join().filter().group_by().order_by().limit().all.return_value = mock_result
                
                response = client.get(
                    "/api/v1/statistics/hot-issues",
                    headers=auth_headers
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "success"
                assert "data" in data
                assert len(data["data"]) <= 10
                if len(data["data"]) > 0:
                    assert "issue_type" in data["data"][0]
                    assert "count" in data["data"][0]
                    assert "percentage" in data["data"][0]
    
    def test_get_hot_issues_with_date_range(self, client: TestClient, auth_headers, verified_user):
        """测试带日期范围的热点问题统计"""
        with patch('open_webui.routers.statistics.get_verified_user', return_value=verified_user):
            with patch('open_webui.routers.statistics.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value = mock_db
                
                mock_result = [("网络故障", 50)]
                mock_db.query().join().filter().group_by().order_by().limit().all.return_value = mock_result
                
                response = client.get(
                    "/api/v1/statistics/hot-issues?start_date=2024-01-01&end_date=2024-01-31&top_n=5",
                    headers=auth_headers
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "success"
    
    def test_get_hot_issues_invalid_date(self, client: TestClient, auth_headers, verified_user):
        """测试无效日期格式"""
        with patch('open_webui.routers.statistics.get_verified_user', return_value=verified_user):
            response = client.get(
                "/api/v1/statistics/hot-issues?start_date=invalid-date",
                headers=auth_headers
            )
            
            assert response.status_code == 400


class TestUserActivityStatistics:
    """用户活跃度统计测试"""
    
    def test_get_user_activity_default(self, client: TestClient, auth_headers, verified_user):
        """测试获取默认用户活跃度统计"""
        with patch('open_webui.routers.statistics.get_verified_user', return_value=verified_user):
            with patch('open_webui.routers.statistics.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value = mock_db
                
                # 模拟查询结果
                mock_daily = [
                    (datetime.now().date() - timedelta(days=i), 50 - i*2)
                    for i in range(7)
                ]
                mock_db.query().filter().group_by().order_by().all.return_value = mock_daily
                
                # 模拟活跃用户
                mock_db.query().filter().distinct().count.return_value = 100
                
                # 模拟新用户
                mock_db.query().filter().count.return_value = 15
                
                response = client.get(
                    "/api/v1/statistics/user-activity",
                    headers=auth_headers
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "success"
                assert "daily_active_users" in data["data"]
                assert "total_active_users" in data["data"]
                assert "new_users" in data["data"]
                assert "activity_trend" in data["data"]
    
    def test_get_user_activity_monthly(self, client: TestClient, auth_headers, verified_user):
        """测试月度用户活跃度统计"""
        with patch('open_webui.routers.statistics.get_verified_user', return_value=verified_user):
            with patch('open_webui.routers.statistics.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value = mock_db
                
                # 模拟月度数据
                mock_monthly = [
                    (datetime(2024, i, 1).date(), 1000 + i*100)
                    for i in range(1, 7)
                ]
                mock_db.query().filter().group_by().order_by().all.return_value = mock_monthly
                mock_db.query().filter().distinct().count.return_value = 500
                mock_db.query().filter().count.return_value = 50
                
                response = client.get(
                    "/api/v1/statistics/user-activity?period=month",
                    headers=auth_headers
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "success"
                assert "monthly_active_users" in data["data"]


class TestKnowledgeUsageStatistics:
    """知识使用率统计测试"""
    
    def test_get_knowledge_usage(self, client: TestClient, auth_headers, verified_user):
        """测试获取知识使用率统计"""
        with patch('open_webui.routers.statistics.get_verified_user', return_value=verified_user):
            with patch('open_webui.routers.statistics.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value = mock_db
                
                # 模拟知识库文档统计
                mock_db.query().count.return_value = 1000
                
                # 模拟最常用文档
                mock_docs = [
                    (Mock(id="doc1", name="网络配置手册", description="网络配置相关文档"), 500),
                    (Mock(id="doc2", name="故障排查指南", description="常见故障排查"), 450),
                    (Mock(id="doc3", name="安全设置", description="安全配置指南"), 380)
                ]
                mock_db.query().outerjoin().group_by().order_by().limit().all.return_value = mock_docs
                
                # 模拟分类使用统计
                mock_categories = [
                    ("网络配置", 1200),
                    ("故障排查", 890),
                    ("安全设置", 650)
                ]
                mock_db.query().outerjoin().group_by().order_by().all.return_value = mock_categories
                
                response = client.get(
                    "/api/v1/statistics/knowledge-usage",
                    headers=auth_headers
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "success"
                assert "total_documents" in data["data"]
                assert "total_usage_count" in data["data"]
                assert "most_used_documents" in data["data"]
                assert "category_usage" in data["data"]
    
    def test_get_knowledge_usage_with_params(self, client: TestClient, auth_headers, verified_user):
        """测试带参数的知识使用率统计"""
        with patch('open_webui.routers.statistics.get_verified_user', return_value=verified_user):
            with patch('open_webui.routers.statistics.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value = mock_db
                
                mock_db.query().count.return_value = 500
                mock_db.query().outerjoin().group_by().order_by().limit().all.return_value = []
                mock_db.query().outerjoin().group_by().order_by().all.return_value = []
                
                response = client.get(
                    "/api/v1/statistics/knowledge-usage?top_n=5&category=network",
                    headers=auth_headers
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "success"


class TestSystemOverview:
    """系统概览统计测试"""
    
    def test_get_system_overview(self, client: TestClient, auth_headers, verified_user):
        """测试获取系统概览"""
        with patch('open_webui.routers.statistics.get_verified_user', return_value=verified_user):
            with patch('open_webui.routers.statistics.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value = mock_db
                
                # 模拟各种统计数据
                mock_db.query().count.side_effect = [1000, 5000, 2000, 50000]  # 用户、案例、知识、反馈
                mock_db.query().filter().count.side_effect = [100, 4500]  # 今日新增用户、已解决案例
                
                # 模拟解决率查询
                mock_db.query().filter().scalar.return_value = 90.5
                
                # 模拟响应时间
                mock_db.query().filter().scalar.return_value = 2.5
                
                response = client.get(
                    "/api/v1/statistics/system-overview",
                    headers=auth_headers
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "success"
                assert "total_users" in data["data"]
                assert "total_cases" in data["data"]
                assert "total_knowledge" in data["data"]
                assert "total_feedback" in data["data"]
                assert "today_new_users" in data["data"]
                assert "resolution_rate" in data["data"]
                assert "avg_response_time" in data["data"]
    
    def test_get_system_overview_with_cache(self, client: TestClient, auth_headers, verified_user):
        """测试带缓存的系统概览"""
        with patch('open_webui.routers.statistics.get_verified_user', return_value=verified_user):
            with patch('open_webui.routers.statistics.get_db') as mock_get_db:
                with patch('open_webui.routers.statistics.redis_client') as mock_redis:
                    mock_db = MagicMock()
                    mock_get_db.return_value = mock_db
                    
                    # 模拟Redis缓存命中
                    cached_data = {
                        "total_users": 1000,
                        "total_cases": 5000,
                        "total_knowledge": 2000,
                        "total_feedback": 50000,
                        "today_new_users": 100,
                        "resolution_rate": 90.5,
                        "avg_response_time": 2.5
                    }
                    mock_redis.get.return_value = json.dumps(cached_data)
                    
                    response = client.get(
                        "/api/v1/statistics/system-overview",
                        headers=auth_headers
                    )
                    
                    assert response.status_code == 200
                    data = response.json()
                    assert data["status"] == "success"
                    assert data["data"]["total_users"] == 1000


class TestStatisticsErrorHandling:
    """统计模块错误处理测试"""
    
    def test_database_error_handling(self, client: TestClient, auth_headers, verified_user):
        """测试数据库错误处理"""
        with patch('open_webui.routers.statistics.get_verified_user', return_value=verified_user):
            with patch('open_webui.routers.statistics.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value = mock_db
                
                # 模拟数据库错误
                mock_db.query.side_effect = Exception("Database connection error")
                
                response = client.get(
                    "/api/v1/statistics/hot-issues",
                    headers=auth_headers
                )
                
                assert response.status_code == 500
                data = response.json()
                assert "detail" in data
    
    def test_invalid_parameters(self, client: TestClient, auth_headers, verified_user):
        """测试无效参数"""
        with patch('open_webui.routers.statistics.get_verified_user', return_value=verified_user):
            # 测试无效的top_n参数
            response = client.get(
                "/api/v1/statistics/hot-issues?top_n=-1",
                headers=auth_headers
            )
            
            assert response.status_code in [400, 422]
            
            # 测试无效的period参数
            response = client.get(
                "/api/v1/statistics/user-activity?period=invalid",
                headers=auth_headers
            )
            
            assert response.status_code in [400, 422]
    
    def test_unauthorized_access(self, client: TestClient):
        """测试未授权访问"""
        response = client.get("/api/v1/statistics/hot-issues")
        assert response.status_code in [401, 403]
        
        response = client.get("/api/v1/statistics/user-activity")
        assert response.status_code in [401, 403]
        
        response = client.get("/api/v1/statistics/knowledge-usage")
        assert response.status_code in [401, 403]
