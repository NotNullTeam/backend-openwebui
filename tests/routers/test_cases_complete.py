"""
案例管理模块完整测试套件
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime
import json

from open_webui.main import app


client = TestClient(app)


class TestCasesEndpoints:
    """案例管理所有端点的完整测试"""
    
    # ===== POST /cases 创建案例 =====
    @patch('open_webui.routers.cases.get_verified_user')
    @patch('open_webui.routers.cases.Cases.insert_new_case')
    def test_create_case_success(self, mock_insert, mock_user):
        """测试成功创建案例"""
        mock_user.return_value = MagicMock(id="user-123", name="Test User")
        mock_insert.return_value = {
            "id": "case-new",
            "user_id": "user-123",
            "title": "网络故障诊断",
            "description": "交换机端口异常",
            "status": "open",
            "created_at": datetime.utcnow().isoformat()
        }
        
        response = client.post(
            "/api/v1/cases",
            json={
                "title": "网络故障诊断",
                "description": "交换机端口异常",
                "category": "network",
                "priority": "high"
            },
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "case-new"
        assert data["title"] == "网络故障诊断"
    
    # ===== GET /cases 获取案例列表 =====
    @patch('open_webui.routers.cases.get_verified_user')
    @patch('open_webui.routers.cases.Cases.get_cases_by_user')
    def test_get_cases_list(self, mock_get_cases, mock_user):
        """测试获取案例列表"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_get_cases.return_value = [
            {
                "id": "case-1",
                "title": "IP冲突问题",
                "status": "resolved",
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            },
            {
                "id": "case-2",
                "title": "路由配置错误",
                "status": "open",
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
        ]
        
        response = client.get(
            "/api/v1/cases?page=1&page_size=10",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["items"][0]["title"] == "IP冲突问题"
    
    # ===== GET /cases/{case_id} 获取案例详情 =====
    @patch('open_webui.routers.cases.get_verified_user')
    @patch('open_webui.routers.cases.Cases.get_case_by_id')
    def test_get_case_detail(self, mock_get_case, mock_user):
        """测试获取案例详情"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_get_case.return_value = {
            "id": "case-123",
            "user_id": "user-123",
            "title": "VLAN配置问题",
            "description": "跨VLAN通信失败",
            "status": "in_progress",
            "nodes": [
                {"id": "node-1", "type": "problem", "content": "无法ping通"},
                {"id": "node-2", "type": "analysis", "content": "VLAN标签错误"}
            ],
            "created_at": datetime.utcnow().isoformat()
        }
        
        response = client.get(
            "/api/v1/cases/case-123",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "VLAN配置问题"
        assert len(data["nodes"]) == 2
    
    # ===== PUT /cases/{case_id} 更新案例 =====
    @patch('open_webui.routers.cases.get_verified_user')
    @patch('open_webui.routers.cases.Cases.get_case_by_id')
    @patch('open_webui.routers.cases.Cases.update_case')
    def test_update_case(self, mock_update, mock_get, mock_user):
        """测试更新案例"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_get.return_value = {"id": "case-123", "user_id": "user-123"}
        mock_update.return_value = {
            "id": "case-123",
            "title": "VLAN配置问题（已解决）",
            "status": "resolved"
        }
        
        response = client.put(
            "/api/v1/cases/case-123",
            json={
                "title": "VLAN配置问题（已解决）",
                "status": "resolved"
            },
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "resolved"
    
    # ===== DELETE /cases/{case_id} 删除案例 =====
    @patch('open_webui.routers.cases.get_verified_user')
    @patch('open_webui.routers.cases.Cases.get_case_by_id')
    @patch('open_webui.routers.cases.Cases.delete_case')
    def test_delete_case(self, mock_delete, mock_get, mock_user):
        """测试删除案例"""
        mock_user.return_value = MagicMock(id="user-123", role="user")
        mock_get.return_value = {"id": "case-123", "user_id": "user-123"}
        mock_delete.return_value = True
        
        response = client.delete(
            "/api/v1/cases/case-123",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        assert response.json()["message"] == "案例已删除"
    
    # ===== POST /cases/{case_id}/interact 多轮交互 =====
    @patch('open_webui.routers.cases.get_verified_user')
    @patch('open_webui.routers.cases.Cases.get_case_by_id')
    @patch('open_webui.routers.cases.process_case_interaction')
    @patch('open_webui.routers.cases.Cases.add_interaction')
    def test_case_interaction(self, mock_add, mock_process, mock_get, mock_user):
        """测试案例多轮交互"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_get.return_value = {"id": "case-123", "user_id": "user-123"}
        mock_process.return_value = {
            "response": "建议检查VLAN配置",
            "suggestions": ["查看trunk配置", "验证VLAN ID"],
            "next_steps": ["执行show vlan命令"]
        }
        mock_add.return_value = True
        
        response = client.post(
            "/api/v1/cases/case-123/interact",
            json={
                "message": "交换机无法识别VLAN标签",
                "context": {"device": "Cisco 3750"}
            },
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "建议" in data["response"]
        assert len(data["suggestions"]) > 0
    
    # ===== POST /cases/{case_id}/feedback 用户反馈 =====
    @patch('open_webui.routers.cases.get_verified_user')
    @patch('open_webui.routers.cases.Cases.get_case_by_id')
    @patch('open_webui.routers.cases.Feedback.insert_feedback')
    def test_submit_feedback(self, mock_insert, mock_get, mock_user):
        """测试提交用户反馈"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_get.return_value = {"id": "case-123", "user_id": "user-123"}
        mock_insert.return_value = {
            "id": "feedback-1",
            "case_id": "case-123",
            "rating": 5,
            "comment": "解决方案很有效"
        }
        
        response = client.post(
            "/api/v1/cases/case-123/feedback",
            json={
                "rating": 5,
                "comment": "解决方案很有效",
                "helpful": True
            },
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["rating"] == 5
    
    # ===== POST /cases/batch 批量创建案例 =====
    @patch('open_webui.routers.cases.get_verified_user')
    @patch('open_webui.routers.cases.Cases.batch_create')
    def test_batch_create_cases(self, mock_batch, mock_user):
        """测试批量创建案例"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_batch.return_value = [
            {"id": f"case-batch-{i}", "title": f"案例{i}"} 
            for i in range(3)
        ]
        
        response = client.post(
            "/api/v1/cases/batch",
            json={
                "cases": [
                    {"title": f"批量案例{i}", "description": f"描述{i}"}
                    for i in range(3)
                ]
            },
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["created"]) == 3
    
    # ===== POST /cases/{case_id}/nodes 添加节点 =====
    @patch('open_webui.routers.cases.get_verified_user')
    @patch('open_webui.routers.cases.Cases.get_case_by_id')
    @patch('open_webui.routers.cases.Nodes.insert_node')
    def test_add_case_node(self, mock_insert, mock_get, mock_user):
        """测试添加案例节点"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_get.return_value = {"id": "case-123", "user_id": "user-123"}
        mock_insert.return_value = {
            "id": "node-new",
            "case_id": "case-123",
            "type": "solution",
            "content": "重启交换机端口",
            "position": {"x": 100, "y": 200}
        }
        
        response = client.post(
            "/api/v1/cases/case-123/nodes",
            json={
                "type": "solution",
                "content": "重启交换机端口",
                "position": {"x": 100, "y": 200}
            },
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "solution"
    
    # ===== POST /cases/{case_id}/export 导出案例 =====
    @patch('open_webui.routers.cases.get_verified_user')
    @patch('open_webui.routers.cases.Cases.get_case_by_id')
    @patch('open_webui.routers.cases.export_case')
    def test_export_case(self, mock_export, mock_get, mock_user):
        """测试导出案例"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_get.return_value = {
            "id": "case-123",
            "user_id": "user-123",
            "title": "网络诊断案例"
        }
        mock_export.return_value = b"PDF content here"
        
        response = client.post(
            "/api/v1/cases/case-123/export?format=pdf",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
    
    # ===== 边界条件和异常测试 =====
    @patch('open_webui.routers.cases.get_verified_user')
    def test_create_case_missing_fields(self, mock_user):
        """测试创建案例缺少必填字段"""
        mock_user.return_value = MagicMock(id="user-123")
        
        response = client.post(
            "/api/v1/cases",
            json={"description": "只有描述没有标题"},
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 422
    
    @patch('open_webui.routers.cases.get_verified_user')
    @patch('open_webui.routers.cases.Cases.get_case_by_id')
    def test_access_other_user_case(self, mock_get, mock_user):
        """测试访问其他用户的案例"""
        mock_user.return_value = MagicMock(id="user-123", role="user")
        mock_get.return_value = {
            "id": "case-456",
            "user_id": "user-456"  # 不同用户
        }
        
        response = client.get(
            "/api/v1/cases/case-456",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 403
    
    @patch('open_webui.routers.cases.get_verified_user')
    @patch('open_webui.routers.cases.Cases.get_case_by_id')
    def test_interact_with_closed_case(self, mock_get, mock_user):
        """测试与已关闭案例交互"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_get.return_value = {
            "id": "case-123",
            "user_id": "user-123",
            "status": "closed"
        }
        
        response = client.post(
            "/api/v1/cases/case-123/interact",
            json={"message": "继续诊断"},
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 400
        assert "案例已关闭" in response.json()["detail"]
    
    @patch('open_webui.routers.cases.get_verified_user')
    @patch('open_webui.routers.cases.Cases.batch_create')
    def test_batch_create_limit_exceeded(self, mock_batch, mock_user):
        """测试批量创建超过限制"""
        mock_user.return_value = MagicMock(id="user-123")
        
        # 假设限制为100个
        response = client.post(
            "/api/v1/cases/batch",
            json={
                "cases": [
                    {"title": f"案例{i}", "description": f"描述{i}"}
                    for i in range(101)
                ]
            },
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 400
        assert "超过批量创建限制" in response.json()["detail"]
