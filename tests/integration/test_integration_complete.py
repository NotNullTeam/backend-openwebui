"""
完整集成测试套件 - 覆盖跨模块工作流和端到端场景
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, Mock, AsyncMock, call
from datetime import datetime, timedelta
import json
import io

from open_webui.main import app


client = TestClient(app)


class TestEndToEndWorkflows:
    """端到端工作流集成测试"""
    
    # ===== 用户注册到首次使用完整流程 =====
    @patch('open_webui.routers.auth.Users.insert_new_user')
    @patch('open_webui.routers.auth.Auths.insert_new_auth')
    @patch('open_webui.routers.auth.create_access_token')
    @patch('open_webui.routers.cases_migrated.get_verified_user')
    @patch('open_webui.routers.cases_migrated.Cases.insert_new_case')
    def test_user_onboarding_flow(self, mock_insert_case, mock_get_user, 
                                  mock_token, mock_auth, mock_user):
        """测试用户入门完整流程：注册->登录->创建首个案例"""
        # Step 1: 用户注册
        mock_user.return_value = MagicMock(id="new-user-123", email="newuser@test.com")
        mock_auth.return_value = True
        mock_token.return_value = "jwt-token-123"
        
        register_response = client.post(
            "/api/v1/auth/register",
            json={
                "name": "新用户",
                "email": "newuser@test.com",
                "password": "SecurePass123!"
            }
        )
        assert register_response.status_code == 200
        token = register_response.json()["access_token"]
        
        # Step 2: 创建第一个案例
        mock_get_user.return_value = MagicMock(id="new-user-123")
        mock_insert_case.return_value = MagicMock(
            id="case-001",
            title="网络连接问题",
            user_id="new-user-123"
        )
        
        case_response = client.post(
            "/api/v1/cases",
            json={
                "title": "网络连接问题",
                "description": "无法连接到内网服务器"
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        assert case_response.status_code == 200
        assert case_response.json()["title"] == "网络连接问题"
    
    # ===== 知识文档上传到检索完整流程 =====
    @patch('open_webui.routers.knowledge_migrated.get_verified_user')
    @patch('open_webui.routers.knowledge_migrated.save_file')
    @patch('open_webui.routers.knowledge_migrated.Files.insert_new_file')
    @patch('open_webui.routers.knowledge_migrated.process_file_async')
    @patch('open_webui.routers.knowledge_migrated.hybrid_search')
    def test_knowledge_upload_and_search_flow(self, mock_search, mock_process, 
                                              mock_insert, mock_save, mock_user):
        """测试知识管理流程：上传->处理->检索"""
        mock_user.return_value = MagicMock(id="user-123")
        
        # Step 1: 上传文档
        mock_save.return_value = "/storage/doc-123.pdf"
        mock_insert.return_value = MagicMock(
            id="doc-123",
            filename="network-guide.pdf",
            status="uploaded"
        )
        mock_process.return_value = {"task_id": "task-456"}
        
        file_content = b"PDF content here"
        upload_response = client.post(
            "/api/v1/knowledge/upload",
            files={"file": ("network-guide.pdf", file_content, "application/pdf")},
            headers={"Authorization": "Bearer test-token"}
        )
        assert upload_response.status_code == 200
        doc_id = upload_response.json()["id"]
        
        # Step 2: 检索文档内容
        mock_search.return_value = {
            "results": [
                {
                    "doc_id": doc_id,
                    "content": "OSPF配置步骤...",
                    "score": 0.95,
                    "metadata": {"page": 10}
                }
            ],
            "total": 1
        }
        
        search_response = client.post(
            "/api/v1/knowledge/search",
            json={"query": "OSPF配置", "top_k": 10},
            headers={"Authorization": "Bearer test-token"}
        )
        assert search_response.status_code == 200
        assert len(search_response.json()["results"]) > 0
    
    # ===== 案例创建到智能分析完整流程 =====
    @patch('open_webui.routers.cases_migrated.get_verified_user')
    @patch('open_webui.routers.cases_migrated.Cases.insert_new_case')
    @patch('open_webui.routers.cases_migrated.process_interaction')
    @patch('open_webui.routers.analysis_migrated.get_verified_user')
    @patch('open_webui.routers.analysis_migrated.analyze_network_issue')
    @patch('open_webui.routers.analysis_migrated.get_recommendations')
    def test_case_with_analysis_flow(self, mock_rec, mock_analyze, mock_ana_user,
                                     mock_interact, mock_insert, mock_case_user):
        """测试案例与分析流程：创建案例->交互->分析->获取推荐"""
        user_mock = MagicMock(id="user-123")
        mock_case_user.return_value = user_mock
        mock_ana_user.return_value = user_mock
        
        # Step 1: 创建案例
        mock_insert.return_value = MagicMock(
            id="case-789",
            title="路由故障",
            status="open"
        )
        
        case_response = client.post(
            "/api/v1/cases",
            json={"title": "路由故障", "description": "OSPF邻居无法建立"},
            headers={"Authorization": "Bearer test-token"}
        )
        assert case_response.status_code == 200
        case_id = case_response.json()["id"]
        
        # Step 2: 添加交互
        mock_interact.return_value = {
            "response": "请检查OSPF区域配置",
            "suggestions": ["检查MTU", "验证认证"]
        }
        
        interact_response = client.post(
            f"/api/v1/cases/{case_id}/interact",
            json={"message": "OSPF邻居一直在Init状态"},
            headers={"Authorization": "Bearer test-token"}
        )
        assert interact_response.status_code == 200
        
        # Step 3: 执行网络分析
        mock_analyze.return_value = {
            "diagnosis": {"problem": "MTU不匹配", "confidence": 0.88},
            "solution": {"steps": ["调整接口MTU为1500"]}
        }
        
        analysis_response = client.post(
            "/api/v1/analysis/network",
            json={"description": "OSPF邻居无法建立", "case_id": case_id},
            headers={"Authorization": "Bearer test-token"}
        )
        assert analysis_response.status_code == 200
        
        # Step 4: 获取推荐
        mock_rec.return_value = {
            "case_based": [{"title": "类似OSPF问题", "case_id": "old-case"}],
            "action_items": ["检查接口MTU设置"]
        }
        
        rec_response = client.get(
            f"/api/v1/analysis/recommendations?case_id={case_id}",
            headers={"Authorization": "Bearer test-token"}
        )
        assert rec_response.status_code == 200
        assert len(rec_response.json()["action_items"]) > 0
    
    # ===== 文件上传到病毒扫描完整流程 =====
    @patch('open_webui.routers.files_migrated.get_verified_user')
    @patch('open_webui.routers.files_migrated.save_file')
    @patch('open_webui.routers.files_migrated.Files.insert_new_file')
    @patch('open_webui.routers.files_migrated.scan_file_for_virus')
    @patch('open_webui.routers.files_migrated.Files.update_file_status')
    def test_file_upload_with_scanning(self, mock_update, mock_scan, 
                                       mock_insert, mock_save, mock_user):
        """测试文件上传与安全扫描流程"""
        mock_user.return_value = MagicMock(id="user-123")
        
        # Step 1: 上传文件
        mock_save.return_value = "/storage/file-123.exe"
        mock_insert.return_value = MagicMock(
            id="file-123",
            filename="tool.exe",
            status="uploaded"
        )
        
        file_content = b"executable content"
        upload_response = client.post(
            "/api/v1/files/upload",
            files={"file": ("tool.exe", file_content, "application/x-executable")},
            headers={"Authorization": "Bearer test-token"}
        )
        assert upload_response.status_code == 200
        file_id = upload_response.json()["id"]
        
        # Step 2: 触发安全扫描
        mock_scan.return_value = {"safe": True, "threats": []}
        mock_update.return_value = True
        
        scan_response = client.post(
            f"/api/v1/files/{file_id}/scan",
            headers={"Authorization": "Bearer test-token"}
        )
        assert scan_response.status_code == 200
        assert scan_response.json()["safe"] is True
    
    # ===== 管理员系统维护完整流程 =====
    @patch('open_webui.routers.system_migrated.get_admin_user')
    @patch('open_webui.routers.system_migrated.get_system_health')
    @patch('open_webui.routers.system_migrated.set_maintenance_mode')
    @patch('open_webui.routers.system_migrated.perform_backup')
    @patch('open_webui.routers.system_migrated.clear_system_cache')
    def test_admin_maintenance_workflow(self, mock_clear, mock_backup, 
                                       mock_maintenance, mock_health, mock_admin):
        """测试管理员系统维护流程：健康检查->维护模式->备份->清理缓存"""
        mock_admin.return_value = MagicMock(role="admin")
        
        # Step 1: 检查系统健康
        mock_health.return_value = {
            "status": "degraded",
            "services": {"database": "healthy", "cache": "unhealthy"}
        }
        
        health_response = client.get(
            "/api/v1/system/health",
            headers={"Authorization": "Bearer admin-token"}
        )
        assert health_response.status_code == 200
        assert health_response.json()["status"] == "degraded"
        
        # Step 2: 启用维护模式
        mock_maintenance.return_value = {"enabled": True, "message": "系统维护中"}
        
        maintenance_response = client.post(
            "/api/v1/system/maintenance",
            json={"enabled": True, "message": "系统维护中"},
            headers={"Authorization": "Bearer admin-token"}
        )
        assert maintenance_response.status_code == 200
        
        # Step 3: 执行备份
        mock_backup.return_value = {
            "backup_id": "backup-20240120",
            "size": 1000000000,
            "status": "completed"
        }
        
        backup_response = client.post(
            "/api/v1/system/backup",
            json={"type": "full"},
            headers={"Authorization": "Bearer admin-token"}
        )
        assert backup_response.status_code == 200
        
        # Step 4: 清理缓存
        mock_clear.return_value = {"cleared": True, "freed_memory": 500000000}
        
        clear_response = client.post(
            "/api/v1/system/cache/clear",
            headers={"Authorization": "Bearer admin-token"}
        )
        assert clear_response.status_code == 200
        assert clear_response.json()["freed_memory"] > 0
    
    # ===== 批量操作集成测试 =====
    @patch('open_webui.routers.cases_migrated.get_verified_user')
    @patch('open_webui.routers.cases_migrated.Cases.batch_create')
    @patch('open_webui.routers.cases_migrated.Cases.batch_update')
    @patch('open_webui.routers.cases_migrated.Cases.batch_delete')
    def test_batch_operations_workflow(self, mock_delete, mock_update, 
                                      mock_create, mock_user):
        """测试批量操作工作流：批量创建->批量更新->批量删除"""
        mock_user.return_value = MagicMock(id="user-123")
        
        # Step 1: 批量创建案例
        mock_create.return_value = [
            MagicMock(id=f"case-{i}", title=f"案例{i}") 
            for i in range(1, 4)
        ]
        
        batch_create_response = client.post(
            "/api/v1/cases/batch",
            json={
                "cases": [
                    {"title": f"案例{i}", "description": f"描述{i}"}
                    for i in range(1, 4)
                ]
            },
            headers={"Authorization": "Bearer test-token"}
        )
        assert batch_create_response.status_code == 200
        created_ids = [c["id"] for c in batch_create_response.json()["created"]]
        
        # Step 2: 批量更新状态
        mock_update.return_value = {"updated": 3}
        
        batch_update_response = client.put(
            "/api/v1/cases/batch",
            json={
                "case_ids": created_ids,
                "updates": {"status": "resolved"}
            },
            headers={"Authorization": "Bearer test-token"}
        )
        assert batch_update_response.status_code == 200
        assert batch_update_response.json()["updated"] == 3
        
        # Step 3: 批量删除
        mock_delete.return_value = {"deleted": 3}
        
        batch_delete_response = client.delete(
            "/api/v1/cases/batch",
            json={"case_ids": created_ids},
            headers={"Authorization": "Bearer test-token"}
        )
        assert batch_delete_response.status_code == 200
        assert batch_delete_response.json()["deleted"] == 3
    
    # ===== WebSocket实时通知集成测试 =====
    @patch('open_webui.routers.notifications_migrated.get_verified_user')
    @patch('open_webui.routers.notifications_migrated.Notifications.create')
    @patch('open_webui.routers.notifications_migrated.send_websocket_notification')
    def test_realtime_notification_flow(self, mock_ws, mock_create, mock_user):
        """测试实时通知流程：创建通知->WebSocket推送"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_create.return_value = MagicMock(
            id="notif-123",
            type="case_update",
            message="您的案例已更新"
        )
        mock_ws.return_value = True
        
        # 创建通知并触发WebSocket推送
        notification_response = client.post(
            "/api/v1/notifications",
            json={
                "type": "case_update",
                "message": "您的案例已更新",
                "data": {"case_id": "case-123"}
            },
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert notification_response.status_code == 200
        assert mock_ws.called
    
    # ===== 性能监控与优化流程 =====
    @patch('open_webui.routers.dev.get_admin_user')
    @patch('open_webui.routers.dev.get_performance_metrics')
    @patch('open_webui.routers.dev.optimize_performance')
    @patch('open_webui.routers.dev.rebuild_vector_index_async')
    def test_performance_monitoring_and_optimization(self, mock_rebuild, mock_optimize,
                                                    mock_metrics, mock_admin):
        """测试性能监控与优化流程"""
        mock_admin.return_value = MagicMock(role="admin")
        
        # Step 1: 获取性能指标
        mock_metrics.return_value = {
            "api_latency": {"avg": 2000, "p99": 5000},
            "vector_search": {"avg_search_time": 500},
            "warnings": ["API响应缓慢", "向量搜索延迟高"]
        }
        
        metrics_response = client.get(
            "/api/v1/dev/performance",
            headers={"Authorization": "Bearer admin-token"}
        )
        assert metrics_response.status_code == 200
        assert len(metrics_response.json()["warnings"]) > 0
        
        # Step 2: 执行性能优化
        mock_optimize.return_value = {
            "optimized": True,
            "improvements": ["缓存已优化", "查询已优化"]
        }
        
        optimize_response = client.post(
            "/api/v1/dev/performance/optimize",
            json={"target": "all"},
            headers={"Authorization": "Bearer admin-token"}
        )
        assert optimize_response.status_code == 200
        
        # Step 3: 重建向量索引以提高搜索性能
        mock_rebuild.return_value = {"task_id": "rebuild-123", "status": "started"}
        
        rebuild_response = client.post(
            "/api/v1/dev/index/rebuild",
            json={"force": True},
            headers={"Authorization": "Bearer admin-token"}
        )
        assert rebuild_response.status_code == 200


class TestCrossModuleIntegration:
    """跨模块功能集成测试"""
    
    @patch('open_webui.routers.cases_migrated.get_verified_user')
    @patch('open_webui.routers.knowledge_migrated.get_verified_user')
    @patch('open_webui.routers.cases_migrated.Cases.get_case_by_id')
    @patch('open_webui.routers.knowledge_migrated.hybrid_search')
    @patch('open_webui.routers.cases_migrated.link_knowledge_to_case')
    def test_case_knowledge_integration(self, mock_link, mock_search, 
                                       mock_get_case, mock_know_user, mock_case_user):
        """测试案例与知识库的集成"""
        user_mock = MagicMock(id="user-123")
        mock_case_user.return_value = user_mock
        mock_know_user.return_value = user_mock
        
        mock_get_case.return_value = MagicMock(
            id="case-123",
            title="网络故障",
            description="VLAN配置问题"
        )
        
        mock_search.return_value = {
            "results": [
                {"doc_id": "doc-456", "content": "VLAN配置指南", "score": 0.92}
            ]
        }
        
        mock_link.return_value = {"linked": True, "knowledge_items": 1}
        
        # 基于案例内容搜索相关知识并关联
        response = client.post(
            "/api/v1/cases/case-123/link-knowledge",
            json={"auto_search": True},
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        assert response.json()["knowledge_items"] > 0
    
    @patch('open_webui.routers.auth.get_verified_user')
    @patch('open_webui.routers.user_settings.get_verified_user')
    @patch('open_webui.routers.user_settings.UserSettings.update_settings')
    @patch('open_webui.routers.notifications_migrated.get_verified_user')
    @patch('open_webui.routers.notifications_migrated.Notifications.get_user_preferences')
    def test_user_preferences_propagation(self, mock_notif_pref, mock_notif_user,
                                         mock_update, mock_settings_user, mock_auth_user):
        """测试用户偏好设置在各模块间的传播"""
        user_mock = MagicMock(id="user-123")
        mock_auth_user.return_value = user_mock
        mock_settings_user.return_value = user_mock
        mock_notif_user.return_value = user_mock
        
        # 更新用户设置
        mock_update.return_value = {
            "language": "zh-CN",
            "notification_enabled": False
        }
        
        settings_response = client.put(
            "/api/v1/user/settings",
            json={"language": "zh-CN", "notification_enabled": False},
            headers={"Authorization": "Bearer test-token"}
        )
        assert settings_response.status_code == 200
        
        # 验证通知偏好已同步更新
        mock_notif_pref.return_value = {"email": {"enabled": False}}
        
        pref_response = client.get(
            "/api/v1/notifications/preferences",
            headers={"Authorization": "Bearer test-token"}
        )
        assert pref_response.status_code == 200
        assert pref_response.json()["email"]["enabled"] is False
