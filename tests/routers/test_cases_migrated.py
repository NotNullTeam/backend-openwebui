"""
案例管理模块单元测试
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from open_webui.routers.cases_migrated import router
from open_webui.models.cases import Case, CaseNode, CaseEdge

# 创建测试应用
app = FastAPI()
app.include_router(router, prefix="/api/v1")
client = TestClient(app)

class TestCasesRouter:
    """案例路由测试类"""
    
    @pytest.fixture
    def mock_user(self):
        """模拟用户"""
        user = Mock()
        user.id = "test_user_id"
        user.email = "test@example.com"
        user.role = "user"
        return user
    
    @pytest.fixture
    def mock_admin_user(self):
        """模拟管理员用户"""
        user = Mock()
        user.id = "admin_user_id"
        user.email = "admin@example.com"
        user.role = "admin"
        return user
    
    @pytest.fixture
    def sample_case_data(self):
        """示例案例数据"""
        return {
            "query": "网络连接问题",
            "title": "测试案例",
            "vendor": "华为",
            "category": "网络故障",
            "attachments": []
        }
    
    @pytest.fixture
    def mock_case(self):
        """模拟案例对象"""
        case = Mock(spec=Case)
        case.id = "test_case_id"
        case.title = "测试案例"
        case.query = "网络连接问题"
        case.status = "ACTIVE"
        case.vendor = "华为"
        case.category = "网络故障"
        case.user_id = "test_user_id"
        case.created_at = "2024-01-01T00:00:00Z"
        case.updated_at = "2024-01-01T00:00:00Z"
        case.metadata = {}
        return case
    
    @patch('open_webui.routers.cases_migrated.get_verified_user')
    @patch('open_webui.routers.cases_migrated.cases_table')
    def test_get_cases_success(self, mock_cases_table, mock_get_user, mock_user):
        """测试获取案例列表成功"""
        # 设置模拟
        mock_get_user.return_value = mock_user
        mock_cases_table.get_cases_by_user_id.return_value = [self.mock_case()]
        
        # 发送请求
        response = client.get("/api/v1/cases")
        
        # 验证结果
        assert response.status_code == 200
        data = response.json()
        assert "cases" in data
        assert len(data["cases"]) == 1
        
        # 验证调用
        mock_cases_table.get_cases_by_user_id.assert_called_once_with(mock_user.id)
    
    @patch('open_webui.routers.cases_migrated.get_verified_user')
    @patch('open_webui.routers.cases_migrated.cases_table')
    def test_get_cases_with_pagination(self, mock_cases_table, mock_get_user, mock_user):
        """测试分页获取案例列表"""
        # 设置模拟
        mock_get_user.return_value = mock_user
        mock_cases_table.get_cases_by_user_id.return_value = []
        
        # 发送请求
        response = client.get("/api/v1/cases?page=2&pageSize=5")
        
        # 验证结果
        assert response.status_code == 200
        data = response.json()
        assert "pagination" in data
        assert data["pagination"]["page"] == 2
        assert data["pagination"]["per_page"] == 5
    
    @patch('open_webui.routers.cases_migrated.get_verified_user')
    @patch('open_webui.routers.cases_migrated.cases_table')
    def test_create_case_success(self, mock_cases_table, mock_get_user, mock_user, sample_case_data):
        """测试创建案例成功"""
        # 设置模拟
        mock_get_user.return_value = mock_user
        mock_case = self.mock_case()
        mock_cases_table.insert_new_case.return_value = mock_case
        
        # 发送请求
        response = client.post("/api/v1/cases", json=sample_case_data)
        
        # 验证结果
        assert response.status_code == 200
        data = response.json()
        assert data["caseId"] == mock_case.id
        assert data["message"] == "案例创建成功"
        
        # 验证调用
        mock_cases_table.insert_new_case.assert_called_once()
    
    @patch('open_webui.routers.cases_migrated.get_verified_user')
    @patch('open_webui.routers.cases_migrated.cases_table')
    def test_create_case_validation_error(self, mock_cases_table, mock_get_user, mock_user):
        """测试创建案例验证错误"""
        # 设置模拟
        mock_get_user.return_value = mock_user
        
        # 发送无效数据
        invalid_data = {"query": ""}  # 缺少必要字段
        response = client.post("/api/v1/cases", json=invalid_data)
        
        # 验证结果
        assert response.status_code == 422  # 验证错误
    
    @patch('open_webui.routers.cases_migrated.get_verified_user')
    @patch('open_webui.routers.cases_migrated.cases_table')
    def test_get_case_detail_success(self, mock_cases_table, mock_get_user, mock_user):
        """测试获取案例详情成功"""
        # 设置模拟
        mock_get_user.return_value = mock_user
        mock_case = self.mock_case()
        mock_cases_table.get_case_by_id.return_value = mock_case
        
        # 发送请求
        response = client.get(f"/api/v1/cases/{mock_case.id}")
        
        # 验证结果
        assert response.status_code == 200
        data = response.json()
        assert data["caseId"] == mock_case.id
        assert data["title"] == mock_case.title
    
    @patch('open_webui.routers.cases_migrated.get_verified_user')
    @patch('open_webui.routers.cases_migrated.cases_table')
    def test_get_case_detail_not_found(self, mock_cases_table, mock_get_user, mock_user):
        """测试获取不存在的案例详情"""
        # 设置模拟
        mock_get_user.return_value = mock_user
        mock_cases_table.get_case_by_id.return_value = None
        
        # 发送请求
        response = client.get("/api/v1/cases/nonexistent_id")
        
        # 验证结果
        assert response.status_code == 404
        assert "案例不存在" in response.json()["detail"]
    
    @patch('open_webui.routers.cases_migrated.get_verified_user')
    @patch('open_webui.routers.cases_migrated.cases_table')
    def test_get_case_detail_permission_denied(self, mock_cases_table, mock_get_user, mock_user):
        """测试无权限访问案例详情"""
        # 设置模拟
        mock_get_user.return_value = mock_user
        mock_case = self.mock_case()
        mock_case.user_id = "other_user_id"  # 不同用户
        mock_cases_table.get_case_by_id.return_value = mock_case
        
        # 发送请求
        response = client.get(f"/api/v1/cases/{mock_case.id}")
        
        # 验证结果
        assert response.status_code == 403
        assert "无权访问" in response.json()["detail"]
    
    @patch('open_webui.routers.cases_migrated.get_verified_user')
    @patch('open_webui.routers.cases_migrated.cases_table')
    def test_admin_can_access_any_case(self, mock_cases_table, mock_get_user, mock_admin_user):
        """测试管理员可以访问任何案例"""
        # 设置模拟
        mock_get_user.return_value = mock_admin_user
        mock_case = self.mock_case()
        mock_case.user_id = "other_user_id"  # 不同用户
        mock_cases_table.get_case_by_id.return_value = mock_case
        
        # 发送请求
        response = client.get(f"/api/v1/cases/{mock_case.id}")
        
        # 验证结果
        assert response.status_code == 200
    
    @patch('open_webui.routers.cases_migrated.get_verified_user')
    @patch('open_webui.routers.cases_migrated.cases_table')
    def test_update_case_success(self, mock_cases_table, mock_get_user, mock_user):
        """测试更新案例成功"""
        # 设置模拟
        mock_get_user.return_value = mock_user
        mock_case = self.mock_case()
        mock_cases_table.get_case_by_id.return_value = mock_case
        mock_cases_table.update_case_by_id.return_value = mock_case
        
        # 发送请求
        update_data = {"title": "更新的标题", "status": "COMPLETED"}
        response = client.put(f"/api/v1/cases/{mock_case.id}", json=update_data)
        
        # 验证结果
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "案例更新成功"
        
        # 验证调用
        mock_cases_table.update_case_by_id.assert_called_once()
    
    @patch('open_webui.routers.cases_migrated.get_verified_user')
    @patch('open_webui.routers.cases_migrated.cases_table')
    def test_delete_case_success(self, mock_cases_table, mock_get_user, mock_user):
        """测试删除案例成功"""
        # 设置模拟
        mock_get_user.return_value = mock_user
        mock_case = self.mock_case()
        mock_cases_table.get_case_by_id.return_value = mock_case
        mock_cases_table.delete_case_by_id.return_value = True
        
        # 发送请求
        response = client.delete(f"/api/v1/cases/{mock_case.id}")
        
        # 验证结果
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "案例删除成功"
        
        # 验证调用
        mock_cases_table.delete_case_by_id.assert_called_once_with(mock_case.id)

class TestCaseNodesRouter:
    """案例节点路由测试类"""
    
    @pytest.fixture
    def mock_node(self):
        """模拟节点对象"""
        node = Mock(spec=CaseNode)
        node.id = "test_node_id"
        node.case_id = "test_case_id"
        node.title = "测试节点"
        node.content = {"text": "节点内容"}
        node.node_type = "USER_QUERY"
        node.status = "COMPLETED"
        node.created_at = "2024-01-01T00:00:00Z"
        node.metadata = {}
        return node
    
    @patch('open_webui.routers.cases_migrated.get_verified_user')
    @patch('open_webui.routers.cases_migrated.cases_table')
    def test_get_case_nodes_success(self, mock_cases_table, mock_get_user, mock_user):
        """测试获取案例节点成功"""
        # 设置模拟
        mock_get_user.return_value = mock_user
        mock_case = Mock()
        mock_case.user_id = mock_user.id
        mock_cases_table.get_case_by_id.return_value = mock_case
        mock_cases_table.get_case_nodes.return_value = [self.mock_node()]
        
        # 发送请求
        response = client.get("/api/v1/cases/test_case_id/nodes")
        
        # 验证结果
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert len(data["nodes"]) == 1
    
    @patch('open_webui.routers.cases_migrated.get_verified_user')
    @patch('open_webui.routers.cases_migrated.cases_table')
    def test_create_case_node_success(self, mock_cases_table, mock_get_user, mock_user):
        """测试创建案例节点成功"""
        # 设置模拟
        mock_get_user.return_value = mock_user
        mock_case = Mock()
        mock_case.user_id = mock_user.id
        mock_cases_table.get_case_by_id.return_value = mock_case
        mock_node = self.mock_node()
        mock_cases_table.insert_new_case_node.return_value = mock_node
        
        # 发送请求
        node_data = {
            "title": "新节点",
            "content": {"text": "节点内容"},
            "nodeType": "AI_RESPONSE"
        }
        response = client.post("/api/v1/cases/test_case_id/nodes", json=node_data)
        
        # 验证结果
        assert response.status_code == 200
        data = response.json()
        assert data["nodeId"] == mock_node.id
        assert data["message"] == "节点创建成功"

class TestCaseEdgesRouter:
    """案例边路由测试类"""
    
    @pytest.fixture
    def mock_edge(self):
        """模拟边对象"""
        edge = Mock(spec=CaseEdge)
        edge.id = "test_edge_id"
        edge.case_id = "test_case_id"
        edge.source_node_id = "source_node_id"
        edge.target_node_id = "target_node_id"
        edge.edge_type = "FLOW"
        edge.created_at = "2024-01-01T00:00:00Z"
        edge.metadata = {}
        return edge
    
    @patch('open_webui.routers.cases_migrated.get_verified_user')
    @patch('open_webui.routers.cases_migrated.cases_table')
    def test_get_case_edges_success(self, mock_cases_table, mock_get_user, mock_user):
        """测试获取案例边成功"""
        # 设置模拟
        mock_get_user.return_value = mock_user
        mock_case = Mock()
        mock_case.user_id = mock_user.id
        mock_cases_table.get_case_by_id.return_value = mock_case
        mock_cases_table.get_case_edges.return_value = [self.mock_edge()]
        
        # 发送请求
        response = client.get("/api/v1/cases/test_case_id/edges")
        
        # 验证结果
        assert response.status_code == 200
        data = response.json()
        assert "edges" in data
        assert len(data["edges"]) == 1
    
    @patch('open_webui.routers.cases_migrated.get_verified_user')
    @patch('open_webui.routers.cases_migrated.cases_table')
    def test_create_case_edge_success(self, mock_cases_table, mock_get_user, mock_user):
        """测试创建案例边成功"""
        # 设置模拟
        mock_get_user.return_value = mock_user
        mock_case = Mock()
        mock_case.user_id = mock_user.id
        mock_cases_table.get_case_by_id.return_value = mock_case
        mock_edge = self.mock_edge()
        mock_cases_table.insert_new_case_edge.return_value = mock_edge
        
        # 发送请求
        edge_data = {
            "sourceNodeId": "source_node_id",
            "targetNodeId": "target_node_id",
            "edgeType": "FLOW"
        }
        response = client.post("/api/v1/cases/test_case_id/edges", json=edge_data)
        
        # 验证结果
        assert response.status_code == 200
        data = response.json()
        assert data["edgeId"] == mock_edge.id
        assert data["message"] == "边创建成功"

if __name__ == "__main__":
    pytest.main([__file__])
