"""
案例管理增强功能测试用例
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import json
import uuid

from open_webui.main import app
from open_webui.models.users import UserModel
from open_webui.models.cases import CaseModel


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


class TestCaseLayoutManagement:
    """案例布局管理测试"""
    
    def test_get_case_layout(self, client: TestClient, auth_headers, verified_user):
        """测试获取案例布局"""
        with patch('open_webui.routers.cases_migrated.get_verified_user', return_value=verified_user):
            with patch('open_webui.routers.cases_migrated.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value = mock_db
                
                # 模拟案例
                mock_case = Mock()
                mock_case.id = "case_123"
                mock_case.user_id = verified_user.id
                mock_case.title = "网络故障诊断"
                mock_case.layout = {
                    "nodes": [
                        {
                            "id": "node1",
                            "type": "problem",
                            "position": {"x": 100, "y": 100},
                            "data": {"label": "IP地址冲突"}
                        },
                        {
                            "id": "node2",
                            "type": "analysis",
                            "position": {"x": 300, "y": 100},
                            "data": {"label": "DHCP分析"}
                        }
                    ],
                    "edges": [
                        {
                            "id": "edge1",
                            "source": "node1",
                            "target": "node2",
                            "type": "default"
                        }
                    ],
                    "viewport": {
                        "x": 0,
                        "y": 0,
                        "zoom": 1
                    }
                }
                
                mock_db.query().filter_by().first.return_value = mock_case
                
                response = client.get(
                    "/api/v1/cases/case_123/layout",
                    headers=auth_headers
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "success"
                assert "nodes" in data["data"]
                assert "edges" in data["data"]
                assert len(data["data"]["nodes"]) == 2
                assert len(data["data"]["edges"]) == 1
    
    def test_get_case_layout_not_found(self, client: TestClient, auth_headers, verified_user):
        """测试获取不存在案例的布局"""
        with patch('open_webui.routers.cases_migrated.get_verified_user', return_value=verified_user):
            with patch('open_webui.routers.cases_migrated.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value = mock_db
                
                mock_db.query().filter_by().first.return_value = None
                
                response = client.get(
                    "/api/v1/cases/nonexistent/layout",
                    headers=auth_headers
                )
                
                assert response.status_code == 404
    
    def test_update_case_layout(self, client: TestClient, auth_headers, verified_user):
        """测试更新案例布局"""
        with patch('open_webui.routers.cases_migrated.get_verified_user', return_value=verified_user):
            with patch('open_webui.routers.cases_migrated.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value = mock_db
                
                # 模拟案例
                mock_case = Mock()
                mock_case.id = "case_123"
                mock_case.user_id = verified_user.id
                mock_case.layout = {}
                
                mock_db.query().filter_by().first.return_value = mock_case
                
                new_layout = {
                    "nodes": [
                        {
                            "id": "node1",
                            "type": "problem",
                            "position": {"x": 150, "y": 150},
                            "data": {"label": "网络中断"}
                        },
                        {
                            "id": "node2",
                            "type": "analysis",
                            "position": {"x": 350, "y": 150},
                            "data": {"label": "路由分析"}
                        },
                        {
                            "id": "node3",
                            "type": "solution",
                            "position": {"x": 550, "y": 150},
                            "data": {"label": "重启路由器"}
                        }
                    ],
                    "edges": [
                        {
                            "id": "edge1",
                            "source": "node1",
                            "target": "node2"
                        },
                        {
                            "id": "edge2",
                            "source": "node2",
                            "target": "node3"
                        }
                    ],
                    "viewport": {
                        "x": 50,
                        "y": 50,
                        "zoom": 1.2
                    }
                }
                
                response = client.put(
                    "/api/v1/cases/case_123/layout",
                    headers=auth_headers,
                    json=new_layout
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "success"
                # 验证布局被更新
                assert mock_case.layout["nodes"] == new_layout["nodes"]
                assert mock_case.layout["edges"] == new_layout["edges"]
    
    def test_update_case_layout_unauthorized(self, client: TestClient, auth_headers, verified_user):
        """测试未授权更新案例布局"""
        with patch('open_webui.routers.cases_migrated.get_verified_user', return_value=verified_user):
            with patch('open_webui.routers.cases_migrated.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value = mock_db
                
                # 模拟其他用户的案例
                mock_case = Mock()
                mock_case.id = "case_123"
                mock_case.user_id = "other_user_id"
                
                mock_db.query().filter_by().first.return_value = mock_case
                
                response = client.put(
                    "/api/v1/cases/case_123/layout",
                    headers=auth_headers,
                    json={"nodes": [], "edges": []}
                )
                
                assert response.status_code == 403
    
    def test_auto_layout_case(self, client: TestClient, auth_headers, verified_user):
        """测试自动布局功能"""
        with patch('open_webui.routers.cases_migrated.get_verified_user', return_value=verified_user):
            with patch('open_webui.routers.cases_migrated.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value = mock_db
                
                # 模拟案例
                mock_case = Mock()
                mock_case.id = "case_123"
                mock_case.user_id = verified_user.id
                mock_case.layout = {
                    "nodes": [
                        {"id": "node1", "position": {"x": 0, "y": 0}},
                        {"id": "node2", "position": {"x": 0, "y": 0}},
                        {"id": "node3", "position": {"x": 0, "y": 0}}
                    ],
                    "edges": []
                }
                
                mock_db.query().filter_by().first.return_value = mock_case
                
                response = client.post(
                    "/api/v1/cases/case_123/layout/auto",
                    headers=auth_headers,
                    json={"algorithm": "hierarchical"}
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "success"


class TestNodeKnowledgeTracing:
    """节点知识溯源测试"""
    
    def test_get_node_knowledge_sources(self, client: TestClient, auth_headers, verified_user):
        """测试获取节点知识来源"""
        with patch('open_webui.routers.cases_migrated.get_verified_user', return_value=verified_user):
            with patch('open_webui.routers.cases_migrated.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value = mock_db
                
                # 模拟案例和节点
                mock_case = Mock()
                mock_case.id = "case_123"
                mock_case.user_id = verified_user.id
                
                mock_node = Mock()
                mock_node.id = "node_456"
                mock_node.case_id = "case_123"
                mock_node.content = "IP地址冲突的解决方案"
                mock_node.knowledge_sources = [
                    {
                        "document_id": "doc_001",
                        "document_name": "网络配置手册",
                        "chunk_id": "chunk_123",
                        "content": "当出现IP地址冲突时，首先检查DHCP服务器...",
                        "score": 0.92,
                        "page": 45,
                        "source_type": "manual"
                    },
                    {
                        "document_id": "doc_002",
                        "document_name": "故障排查指南",
                        "chunk_id": "chunk_456",
                        "content": "IP冲突通常由于静态IP配置错误导致...",
                        "score": 0.87,
                        "page": 12,
                        "source_type": "guide"
                    }
                ]
                
                mock_db.query().filter_by().first.side_effect = [mock_case, mock_node]
                
                response = client.get(
                    "/api/v1/cases/case_123/nodes/node_456/knowledge",
                    headers=auth_headers
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "success"
                assert "sources" in data["data"]
                assert len(data["data"]["sources"]) == 2
                assert data["data"]["sources"][0]["document_name"] == "网络配置手册"
                assert data["data"]["sources"][0]["score"] == 0.92
    
    def test_get_node_knowledge_empty(self, client: TestClient, auth_headers, verified_user):
        """测试获取无知识来源的节点"""
        with patch('open_webui.routers.cases_migrated.get_verified_user', return_value=verified_user):
            with patch('open_webui.routers.cases_migrated.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value = mock_db
                
                mock_case = Mock()
                mock_case.id = "case_123"
                mock_case.user_id = verified_user.id
                
                mock_node = Mock()
                mock_node.id = "node_456"
                mock_node.case_id = "case_123"
                mock_node.knowledge_sources = []
                
                mock_db.query().filter_by().first.side_effect = [mock_case, mock_node]
                
                response = client.get(
                    "/api/v1/cases/case_123/nodes/node_456/knowledge",
                    headers=auth_headers
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "success"
                assert len(data["data"]["sources"]) == 0
    
    def test_add_knowledge_source_to_node(self, client: TestClient, auth_headers, verified_user):
        """测试向节点添加知识来源"""
        with patch('open_webui.routers.cases_migrated.get_verified_user', return_value=verified_user):
            with patch('open_webui.routers.cases_migrated.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value = mock_db
                
                mock_case = Mock()
                mock_case.id = "case_123"
                mock_case.user_id = verified_user.id
                
                mock_node = Mock()
                mock_node.id = "node_456"
                mock_node.case_id = "case_123"
                mock_node.knowledge_sources = []
                
                mock_db.query().filter_by().first.side_effect = [mock_case, mock_node]
                
                new_source = {
                    "document_id": "doc_003",
                    "document_name": "RFC文档",
                    "chunk_id": "chunk_789",
                    "content": "根据RFC标准，IP地址分配应遵循...",
                    "score": 0.95,
                    "page": 23,
                    "source_type": "standard"
                }
                
                response = client.post(
                    "/api/v1/cases/case_123/nodes/node_456/knowledge",
                    headers=auth_headers,
                    json=new_source
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "success"
                # 验证知识源被添加
                assert len(mock_node.knowledge_sources) == 1
    
    def test_remove_knowledge_source_from_node(self, client: TestClient, auth_headers, verified_user):
        """测试从节点移除知识来源"""
        with patch('open_webui.routers.cases_migrated.get_verified_user', return_value=verified_user):
            with patch('open_webui.routers.cases_migrated.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value = mock_db
                
                mock_case = Mock()
                mock_case.id = "case_123"
                mock_case.user_id = verified_user.id
                
                mock_node = Mock()
                mock_node.id = "node_456"
                mock_node.case_id = "case_123"
                mock_node.knowledge_sources = [
                    {"chunk_id": "chunk_123", "document_name": "手册1"},
                    {"chunk_id": "chunk_456", "document_name": "手册2"}
                ]
                
                mock_db.query().filter_by().first.side_effect = [mock_case, mock_node]
                
                response = client.delete(
                    "/api/v1/cases/case_123/nodes/node_456/knowledge/chunk_123",
                    headers=auth_headers
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "success"
                # 验证知识源被移除
                assert len(mock_node.knowledge_sources) == 1
                assert mock_node.knowledge_sources[0]["chunk_id"] == "chunk_456"


class TestNodeRegeneration:
    """节点重生成功能测试"""
    
    def test_regenerate_node_content(self, client: TestClient, auth_headers, verified_user):
        """测试重新生成节点内容"""
        with patch('open_webui.routers.cases_migrated.get_verified_user', return_value=verified_user):
            with patch('open_webui.routers.cases_migrated.get_db') as mock_get_db:
                with patch('open_webui.routers.cases_migrated.generate_node_content') as mock_generate:
                    mock_db = MagicMock()
                    mock_get_db.return_value = mock_db
                    
                    # 模拟案例和节点
                    mock_case = Mock()
                    mock_case.id = "case_123"
                    mock_case.user_id = verified_user.id
                    mock_case.issue_description = "网络连接不稳定"
                    
                    mock_node = Mock()
                    mock_node.id = "node_456"
                    mock_node.case_id = "case_123"
                    mock_node.type = "analysis"
                    mock_node.content = "旧的分析内容"
                    mock_node.metadata = {}
                    
                    mock_db.query().filter_by().first.side_effect = [mock_case, mock_node]
                    
                    # 模拟生成新内容
                    mock_generate.return_value = {
                        "content": "基于最新知识库的分析：网络不稳定可能由于...",
                        "knowledge_sources": [
                            {
                                "document_id": "doc_new",
                                "score": 0.93
                            }
                        ],
                        "confidence": 0.88
                    }
                    
                    response = client.post(
                        "/api/v1/cases/case_123/nodes/node_456/regenerate",
                        headers=auth_headers,
                        json={
                            "use_latest_knowledge": True,
                            "model": "gpt-4",
                            "temperature": 0.7
                        }
                    )
                    
                    assert response.status_code == 200
                    data = response.json()
                    assert data["status"] == "success"
                    assert "new_content" in data["data"]
                    assert data["data"]["new_content"] == "基于最新知识库的分析：网络不稳定可能由于..."
    
    def test_regenerate_node_with_custom_prompt(self, client: TestClient, auth_headers, verified_user):
        """测试使用自定义提示词重生成节点"""
        with patch('open_webui.routers.cases_migrated.get_verified_user', return_value=verified_user):
            with patch('open_webui.routers.cases_migrated.get_db') as mock_get_db:
                with patch('open_webui.routers.cases_migrated.generate_node_content') as mock_generate:
                    mock_db = MagicMock()
                    mock_get_db.return_value = mock_db
                    
                    mock_case = Mock()
                    mock_case.id = "case_123"
                    mock_case.user_id = verified_user.id
                    
                    mock_node = Mock()
                    mock_node.id = "node_456"
                    mock_node.case_id = "case_123"
                    mock_node.type = "solution"
                    
                    mock_db.query().filter_by().first.side_effect = [mock_case, mock_node]
                    
                    mock_generate.return_value = {
                        "content": "详细的解决步骤：\n1. 检查网线\n2. 重启设备\n3. 更新固件",
                        "confidence": 0.92
                    }
                    
                    response = client.post(
                        "/api/v1/cases/case_123/nodes/node_456/regenerate",
                        headers=auth_headers,
                        json={
                            "custom_prompt": "请提供详细的解决步骤，包括具体命令",
                            "include_commands": True
                        }
                    )
                    
                    assert response.status_code == 200
                    data = response.json()
                    assert "详细的解决步骤" in data["data"]["new_content"]
    
    def test_batch_regenerate_nodes(self, client: TestClient, auth_headers, verified_user):
        """测试批量重生成节点"""
        with patch('open_webui.routers.cases_migrated.get_verified_user', return_value=verified_user):
            with patch('open_webui.routers.cases_migrated.get_db') as mock_get_db:
                with patch('open_webui.routers.cases_migrated.generate_node_content') as mock_generate:
                    mock_db = MagicMock()
                    mock_get_db.return_value = mock_db
                    
                    mock_case = Mock()
                    mock_case.id = "case_123"
                    mock_case.user_id = verified_user.id
                    
                    mock_nodes = [
                        Mock(id="node1", case_id="case_123", type="analysis"),
                        Mock(id="node2", case_id="case_123", type="solution")
                    ]
                    
                    mock_db.query().filter_by().first.return_value = mock_case
                    mock_db.query().filter().all.return_value = mock_nodes
                    
                    mock_generate.return_value = {
                        "content": "重新生成的内容",
                        "confidence": 0.85
                    }
                    
                    response = client.post(
                        "/api/v1/cases/case_123/nodes/regenerate-batch",
                        headers=auth_headers,
                        json={
                            "node_ids": ["node1", "node2"],
                            "use_latest_knowledge": True
                        }
                    )
                    
                    assert response.status_code == 200
                    data = response.json()
                    assert data["status"] == "success"
                    assert data["data"]["total_regenerated"] == 2
