"""
边界条件和异常场景综合测试套件
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime
import json
import io

from open_webui.main import app


client = TestClient(app)


class TestBoundaryConditions:
    """边界条件测试"""
    
    # ===== 大数据量测试 =====
    @patch('open_webui.routers.cases_migrated.get_verified_user')
    @patch('open_webui.routers.cases_migrated.Cases.batch_create')
    def test_batch_create_limit_exceeded(self, mock_create, mock_user):
        """测试批量创建超过限制"""
        mock_user.return_value = MagicMock(id="user-123")
        
        # 尝试创建101个案例（假设限制为100）
        cases = [{"title": f"案例{i}", "description": f"描述{i}"} for i in range(101)]
        
        response = client.post(
            "/api/v1/cases/batch",
            json={"cases": cases},
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 400
        assert "批量限制" in response.json()["detail"]
    
    @patch('open_webui.routers.files_migrated.get_verified_user')
    def test_file_upload_size_limit(self, mock_user):
        """测试文件大小限制"""
        mock_user.return_value = MagicMock(id="user-123")
        
        # 创建超大文件（101MB，假设限制100MB）
        large_file = b"x" * (101 * 1024 * 1024)
        
        response = client.post(
            "/api/v1/files/upload",
            files={"file": ("large.bin", large_file, "application/octet-stream")},
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 413
        assert "文件太大" in response.json()["detail"]
    
    @patch('open_webui.routers.knowledge_migrated.get_verified_user')
    @patch('open_webui.routers.knowledge_migrated.hybrid_search')
    def test_search_result_limit(self, mock_search, mock_user):
        """测试搜索结果数量限制"""
        mock_user.return_value = MagicMock(id="user-123")
        
        response = client.post(
            "/api/v1/knowledge/search",
            json={"query": "test", "top_k": 10000},  # 请求过多结果
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 400
        assert "最大返回数量" in response.json()["detail"]
    
    # ===== 并发和竞态条件测试 =====
    @patch('open_webui.routers.cases_migrated.get_verified_user')
    @patch('open_webui.routers.cases_migrated.Cases.update_case')
    def test_concurrent_case_update_conflict(self, mock_update, mock_user):
        """测试并发更新冲突"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_update.side_effect = RuntimeError("Concurrent update conflict")
        
        response = client.put(
            "/api/v1/cases/case-123",
            json={"title": "更新标题", "version": 1},
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 409
        assert "并发冲突" in response.json()["detail"]
    
    @patch('open_webui.routers.dev.get_admin_user')
    @patch('open_webui.routers.dev.rebuild_vector_index_async')
    def test_multiple_rebuild_requests(self, mock_rebuild, mock_admin):
        """测试多个重建请求"""
        mock_admin.return_value = MagicMock(role="admin")
        mock_rebuild.side_effect = [
            {"task_id": "task-1", "status": "started"},
            RuntimeError("Another rebuild in progress")
        ]
        
        # 第一个请求成功
        response1 = client.post(
            "/api/v1/dev/index/rebuild",
            headers={"Authorization": "Bearer admin-token"}
        )
        assert response1.status_code == 200
        
        # 第二个请求被拒绝
        response2 = client.post(
            "/api/v1/dev/index/rebuild",
            headers={"Authorization": "Bearer admin-token"}
        )
        assert response2.status_code == 409
    
    # ===== 资源耗尽测试 =====
    @patch('open_webui.routers.system_migrated.get_admin_user')
    @patch('open_webui.routers.system_migrated.get_system_metrics')
    def test_memory_exhaustion_warning(self, mock_metrics, mock_admin):
        """测试内存耗尽警告"""
        mock_admin.return_value = MagicMock(role="admin")
        mock_metrics.return_value = {
            "memory": {
                "used": 95,
                "available": 5,
                "warning": "内存即将耗尽"
            }
        }
        
        response = client.get(
            "/api/v1/system/metrics",
            headers={"Authorization": "Bearer admin-token"}
        )
        
        assert response.status_code == 200
        assert "warning" in response.json()["memory"]
    
    @patch('open_webui.routers.system_migrated.get_admin_user')
    @patch('open_webui.routers.system_migrated.perform_backup')
    def test_disk_space_insufficient(self, mock_backup, mock_admin):
        """测试磁盘空间不足"""
        mock_admin.return_value = MagicMock(role="admin")
        mock_backup.side_effect = IOError("Insufficient disk space")
        
        response = client.post(
            "/api/v1/system/backup",
            json={"type": "full"},
            headers={"Authorization": "Bearer admin-token"}
        )
        
        assert response.status_code == 507
        assert "磁盘空间不足" in response.json()["detail"]


class TestExceptionHandling:
    """异常处理测试"""
    
    # ===== 数据库异常 =====
    @patch('open_webui.routers.cases_migrated.get_verified_user')
    @patch('open_webui.routers.cases_migrated.Cases.get_user_cases')
    def test_database_connection_lost(self, mock_get, mock_user):
        """测试数据库连接丢失"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_get.side_effect = ConnectionError("Database connection lost")
        
        response = client.get(
            "/api/v1/cases",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 503
        assert "数据库连接" in response.json()["detail"]
    
    @patch('open_webui.routers.cases_migrated.get_verified_user')
    @patch('open_webui.routers.cases_migrated.Cases.insert_new_case')
    def test_database_deadlock(self, mock_insert, mock_user):
        """测试数据库死锁"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_insert.side_effect = RuntimeError("Database deadlock detected")
        
        response = client.post(
            "/api/v1/cases",
            json={"title": "测试案例"},
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 500
        assert "数据库死锁" in response.json()["detail"]
    
    # ===== 外部服务异常 =====
    @patch('open_webui.routers.knowledge_migrated.get_verified_user')
    @patch('open_webui.routers.knowledge_migrated.parse_with_idp')
    def test_idp_service_unavailable(self, mock_parse, mock_user):
        """测试IDP服务不可用"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_parse.side_effect = ConnectionError("IDP service unavailable")
        
        response = client.post(
            "/api/v1/knowledge/parse",
            json={"doc_id": "doc-123"},
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 503
        assert "IDP服务" in response.json()["detail"]
    
    @patch('open_webui.routers.analysis_migrated.get_verified_user')
    @patch('open_webui.routers.analysis_migrated.test_llm_connection')
    def test_llm_api_rate_limit(self, mock_test, mock_user):
        """测试LLM API限流"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_test.side_effect = RuntimeError("Rate limit exceeded")
        
        response = client.post(
            "/api/v1/analysis/logs",
            json={"logs": "test logs"},
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 429
        assert "请求过于频繁" in response.json()["detail"]
    
    # ===== 权限和安全异常 =====
    @patch('open_webui.routers.auth.get_verified_user')
    def test_jwt_token_expired(self, mock_user):
        """测试JWT令牌过期"""
        mock_user.side_effect = RuntimeError("Token expired")
        
        response = client.get(
            "/api/v1/cases",
            headers={"Authorization": "Bearer expired-token"}
        )
        
        assert response.status_code == 401
        assert "令牌已过期" in response.json()["detail"]
    
    @patch('open_webui.routers.system_migrated.get_admin_user')
    def test_insufficient_privileges(self, mock_admin):
        """测试权限不足"""
        mock_admin.return_value = MagicMock(role="user")  # 非管理员
        
        response = client.post(
            "/api/v1/system/backup",
            headers={"Authorization": "Bearer user-token"}
        )
        
        assert response.status_code == 403
        assert "权限不足" in response.json()["detail"]
    
    @patch('open_webui.routers.files_migrated.get_verified_user')
    @patch('open_webui.routers.files_migrated.scan_file_for_virus')
    def test_malicious_file_detected(self, mock_scan, mock_user):
        """测试恶意文件检测"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_scan.return_value = {"safe": False, "threats": ["Trojan.Generic"]}
        
        response = client.post(
            "/api/v1/files/file-123/scan",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 400
        assert "检测到威胁" in response.json()["detail"]
    
    # ===== 输入验证异常 =====
    @patch('open_webui.routers.cases_migrated.get_verified_user')
    def test_sql_injection_attempt(self, mock_user):
        """测试SQL注入尝试"""
        mock_user.return_value = MagicMock(id="user-123")
        
        response = client.get(
            "/api/v1/cases?search='; DROP TABLE cases; --",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 400
        assert "非法字符" in response.json()["detail"]
    
    @patch('open_webui.routers.knowledge_migrated.get_verified_user')
    def test_xss_injection_attempt(self, mock_user):
        """测试XSS注入尝试"""
        mock_user.return_value = MagicMock(id="user-123")
        
        response = client.post(
            "/api/v1/knowledge/search",
            json={"query": "<script>alert('XSS')</script>"},
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 400
        assert "非法输入" in response.json()["detail"]
    
    @patch('open_webui.routers.files_migrated.get_verified_user')
    def test_path_traversal_attempt(self, mock_user):
        """测试路径遍历攻击"""
        mock_user.return_value = MagicMock(id="user-123")
        
        response = client.get(
            "/api/v1/files/download/../../etc/passwd",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 400
        assert "非法路径" in response.json()["detail"]
    
    # ===== 超时异常 =====
    @patch('open_webui.routers.analysis_migrated.get_verified_user')
    @patch('open_webui.routers.analysis_migrated.analyze_network_issue')
    def test_analysis_timeout(self, mock_analyze, mock_user):
        """测试分析超时"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_analyze.side_effect = TimeoutError("Analysis timeout after 30s")
        
        response = client.post(
            "/api/v1/analysis/network",
            json={"description": "complex network issue"},
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 504
        assert "处理超时" in response.json()["detail"]
    
    @patch('open_webui.routers.knowledge_migrated.get_verified_user')
    @patch('open_webui.routers.knowledge_migrated.process_file_async')
    def test_file_processing_timeout(self, mock_process, mock_user):
        """测试文件处理超时"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_process.side_effect = TimeoutError("Processing timeout")
        
        response = client.post(
            "/api/v1/knowledge/process",
            json={"doc_id": "doc-123"},
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 504
        assert "处理超时" in response.json()["detail"]


class TestEdgeCases:
    """边缘场景测试"""
    
    @patch('open_webui.routers.cases_migrated.get_verified_user')
    def test_empty_request_body(self, mock_user):
        """测试空请求体"""
        mock_user.return_value = MagicMock(id="user-123")
        
        response = client.post(
            "/api/v1/cases",
            json={},
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 422
    
    @patch('open_webui.routers.knowledge_migrated.get_verified_user')
    def test_special_characters_in_query(self, mock_user):
        """测试查询中的特殊字符"""
        mock_user.return_value = MagicMock(id="user-123")
        
        response = client.post(
            "/api/v1/knowledge/search",
            json={"query": "测试🔍查询#@!"},
            headers={"Authorization": "Bearer test-token"}
        )
        
        # 应该正常处理特殊字符
        assert response.status_code in [200, 400]
    
    @patch('open_webui.routers.cases_migrated.get_verified_user')
    @patch('open_webui.routers.cases_migrated.Cases.get_case_by_id')
    def test_case_not_found(self, mock_get, mock_user):
        """测试案例不存在"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_get.return_value = None
        
        response = client.get(
            "/api/v1/cases/non-existent-case",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 404
        assert "案例不存在" in response.json()["detail"]
    
    @patch('open_webui.routers.user_settings.get_verified_user')
    def test_invalid_language_code(self, mock_user):
        """测试无效的语言代码"""
        mock_user.return_value = MagicMock(id="user-123")
        
        response = client.put(
            "/api/v1/user/settings",
            json={"language": "invalid-lang"},
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 400
        assert "不支持的语言" in response.json()["detail"]
    
    @patch('open_webui.routers.notifications_migrated.get_verified_user')
    @patch('open_webui.routers.notifications_migrated.Notifications.mark_as_read')
    def test_mark_already_read_notification(self, mock_mark, mock_user):
        """测试标记已读的通知"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_mark.return_value = {"already_read": True}
        
        response = client.put(
            "/api/v1/notifications/notif-123/read",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        assert response.json().get("already_read") is True
