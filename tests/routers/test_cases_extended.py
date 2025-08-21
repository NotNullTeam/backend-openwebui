"""
案例管理扩展功能测试
测试案例布局管理和知识溯源等功能
"""

import pytest
import json
import time
from unittest.mock import MagicMock, patch, ANY
from fastapi.testclient import TestClient
from typing import Dict, List, Any

from open_webui.models.cases import CaseModel, CaseNodeModel


@pytest.fixture
def mock_user():
    """模拟已验证用户"""
    user = MagicMock()
    user.id = "test_user_123"
    user.email = "test@example.com"
    user.role = "user"
    return user


@pytest.fixture
def mock_case():
    """模拟案例数据"""
    case = MagicMock(spec=CaseModel)
    case.id = "case_test_123"
    case.user_id = "test_user_123"
    case.title = "测试案例"
    case.status = "processing"
    case.metadata = {}
    case.created_at = int(time.time())
    case.updated_at = int(time.time())
    return case


@pytest.fixture
def mock_case_with_graph(mock_case):
    """模拟带图谱的案例数据"""
    # 创建节点
    node1 = MagicMock(spec=CaseNodeModel)
    node1.id = "node_1"
    node1.case_id = mock_case.id
    node1.title = "用户问题"
    node1.content = json.dumps({"text": "IP地址冲突如何解决？"})
    node1.node_type = "USER_QUERY"
    node1.status = "COMPLETED"
    node1.created_at = int(time.time())
    
    node2 = MagicMock(spec=CaseNodeModel)
    node2.id = "node_2"
    node2.case_id = mock_case.id
    node2.title = "AI分析"
    node2.content = json.dumps({"analysis": "检测到IP地址冲突问题，需要重新分配IP"})
    node2.node_type = "AI_ANALYSIS"
    node2.status = "COMPLETED"
    node2.created_at = int(time.time())
    
    mock_case.nodes = [node1, node2]
    mock_case.edges = []
    return mock_case


class TestCaseLayoutAPI:
    """案例布局管理API测试"""
    
    def test_save_canvas_layout_success(self, client: TestClient, mock_user, mock_case):
        """测试保存画布布局成功"""
        layout_data = {
            "nodePositions": [
                {"nodeId": "node_1", "x": 100, "y": 200},
                {"nodeId": "node_2", "x": 300, "y": 200}
            ],
            "viewportState": {
                "zoom": 1.5,
                "centerX": 200,
                "centerY": 200
            }
        }
        
        with patch("open_webui.routers.cases_migrated.get_verified_user", return_value=mock_user):
            with patch("open_webui.routers.cases_migrated.cases_table.get_case_by_id", return_value=mock_case):
                with patch("open_webui.internal.db.get_db") as mock_get_db:
                    mock_db = MagicMock()
                    mock_get_db.return_value.__enter__.return_value = mock_db
                    
                    mock_row = MagicMock()
                    mock_row.metadata_ = {}
                    mock_db.query.return_value.filter_by.return_value.first.return_value = mock_row
                    
                    response = client.put(f"/api/v1/cases/{mock_case.id}/layout", json=layout_data)
                    assert response.status_code == 200
                    data = response.json()
                    assert data["ok"] is True
                    
                    # 验证metadata被更新
                    assert "layout" in mock_row.metadata_
                    assert mock_row.metadata_["layout"]["nodePositions"] == layout_data["nodePositions"]
                    assert mock_row.metadata_["layout"]["viewportState"] == layout_data["viewportState"]
                    assert "lastSaved" in mock_row.metadata_["layout"]
    
    def test_save_canvas_layout_case_not_found(self, client: TestClient, mock_user):
        """测试保存布局时案例不存在"""
        layout_data = {
            "nodePositions": [],
            "viewportState": {"zoom": 1.0, "centerX": 0, "centerY": 0}
        }
        
        with patch("open_webui.routers.cases_migrated.get_verified_user", return_value=mock_user):
            with patch("open_webui.routers.cases_migrated.cases_table.get_case_by_id", return_value=None):
                response = client.put("/api/v1/cases/invalid_case_id/layout", json=layout_data)
                assert response.status_code == 404
                assert "case not found" in response.json()["detail"]
    
    def test_save_canvas_layout_unauthorized(self, client: TestClient, mock_user, mock_case):
        """测试保存布局时用户无权限"""
        mock_case.user_id = "other_user_id"
        layout_data = {
            "nodePositions": [],
            "viewportState": {"zoom": 1.0, "centerX": 0, "centerY": 0}
        }
        
        with patch("open_webui.routers.cases_migrated.get_verified_user", return_value=mock_user):
            with patch("open_webui.routers.cases_migrated.cases_table.get_case_by_id", return_value=mock_case):
                response = client.put(f"/api/v1/cases/{mock_case.id}/layout", json=layout_data)
                assert response.status_code == 404
                assert "case not found" in response.json()["detail"]
    
    def test_get_canvas_layout_success(self, client: TestClient, mock_user, mock_case):
        """测试获取画布布局成功"""
        mock_case.metadata = {
            "layout": {
                "nodePositions": [
                    {"nodeId": "node_1", "x": 100, "y": 200}
                ],
                "viewportState": {"zoom": 2.0, "centerX": 150, "centerY": 150}
            }
        }
        
        with patch("open_webui.routers.cases_migrated.get_verified_user", return_value=mock_user):
            with patch("open_webui.routers.cases_migrated.cases_table.get_case_by_id", return_value=mock_case):
                response = client.get(f"/api/v1/cases/{mock_case.id}/layout")
                assert response.status_code == 200
                data = response.json()
                assert len(data["nodePositions"]) == 1
                assert data["nodePositions"][0]["nodeId"] == "node_1"
                assert data["viewportState"]["zoom"] == 2.0
    
    def test_get_canvas_layout_default(self, client: TestClient, mock_user, mock_case):
        """测试获取画布布局时返回默认值"""
        mock_case.metadata = None
        
        with patch("open_webui.routers.cases_migrated.get_verified_user", return_value=mock_user):
            with patch("open_webui.routers.cases_migrated.cases_table.get_case_by_id", return_value=mock_case):
                response = client.get(f"/api/v1/cases/{mock_case.id}/layout")
                assert response.status_code == 200
                data = response.json()
                assert data["nodePositions"] == []
                assert data["viewportState"]["zoom"] == 1.0
                assert data["viewportState"]["centerX"] == 0
                assert data["viewportState"]["centerY"] == 0


class TestNodeKnowledgeAPI:
    """节点知识溯源API测试"""
    
    def test_get_node_knowledge_success(self, client: TestClient, mock_user, mock_case_with_graph):
        """测试获取节点知识溯源成功"""
        mock_knowledge_bases = [
            MagicMock(id="kb_1", name="知识库1"),
            MagicMock(id="kb_2", name="知识库2")
        ]
        
        mock_search_result = MagicMock()
        mock_search_result.ids = [["doc_1", "doc_2"]]
        mock_search_result.distances = [[0.8, 0.9]]
        mock_search_result.documents = [["文档内容1", "文档内容2"]]
        mock_search_result.metadatas = [[
            {"title": "IP配置指南", "vendor": "cisco"},
            {"title": "网络故障排查", "vendor": "huawei"}
        ]]
        
        with patch("open_webui.routers.cases_migrated.get_verified_user", return_value=mock_user):
            with patch("open_webui.routers.cases_migrated.cases_table.get_case_with_graph_by_id", return_value=mock_case_with_graph):
                with patch("open_webui.routers.cases_migrated.Knowledges.get_knowledge_bases_by_user_id", return_value=mock_knowledge_bases):
                    with patch("open_webui.routers.cases_migrated.get_ef") as mock_get_ef:
                        with patch("open_webui.routers.cases_migrated.get_embedding_function") as mock_get_embedding:
                            with patch("open_webui.routers.cases_migrated.VECTOR_DB_CLIENT.search", return_value=mock_search_result):
                                mock_embedding_func = MagicMock(return_value=[0.1, 0.2, 0.3])
                                mock_get_embedding.return_value = mock_embedding_func
                                
                                response = client.get(
                                    f"/api/v1/cases/{mock_case_with_graph.id}/nodes/node_2/knowledge",
                                    params={"topK": 5, "retrievalWeight": 0.7}
                                )
                                assert response.status_code == 200
                                data = response.json()
                                assert data["nodeId"] == "node_2"
                                assert "sources" in data
                                assert len(data["sources"]) > 0
                                assert "retrievalMetadata" in data
    
    def test_get_node_knowledge_invalid_params(self, client: TestClient, mock_user, mock_case_with_graph):
        """测试获取节点知识溯源时参数无效"""
        with patch("open_webui.routers.cases_migrated.get_verified_user", return_value=mock_user):
            # topK 超出范围
            response = client.get(
                f"/api/v1/cases/{mock_case_with_graph.id}/nodes/node_1/knowledge",
                params={"topK": 25}
            )
            assert response.status_code == 400
            assert "topK must be between 1 and 20" in response.json()["detail"]
            
            # retrievalWeight 超出范围
            response = client.get(
                f"/api/v1/cases/{mock_case_with_graph.id}/nodes/node_1/knowledge",
                params={"retrievalWeight": 1.5}
            )
            assert response.status_code == 400
            assert "retrievalWeight must be in [0,1]" in response.json()["detail"]
    
    def test_get_node_knowledge_node_not_found(self, client: TestClient, mock_user, mock_case_with_graph):
        """测试获取不存在节点的知识溯源"""
        with patch("open_webui.routers.cases_migrated.get_verified_user", return_value=mock_user):
            with patch("open_webui.routers.cases_migrated.cases_table.get_case_with_graph_by_id", return_value=mock_case_with_graph):
                response = client.get(
                    f"/api/v1/cases/{mock_case_with_graph.id}/nodes/invalid_node_id/knowledge",
                    params={"topK": 5}
                )
                assert response.status_code == 404
                assert "node not found" in response.json()["detail"]
    
    def test_get_node_knowledge_empty_query(self, client: TestClient, mock_user, mock_case_with_graph):
        """测试节点内容为空时的知识溯源"""
        # 修改节点内容为空
        mock_case_with_graph.nodes[0].content = ""
        mock_case_with_graph.nodes[0].title = ""
        
        with patch("open_webui.routers.cases_migrated.get_verified_user", return_value=mock_user):
            with patch("open_webui.routers.cases_migrated.cases_table.get_case_with_graph_by_id", return_value=mock_case_with_graph):
                response = client.get(
                    f"/api/v1/cases/{mock_case_with_graph.id}/nodes/node_1/knowledge",
                    params={"topK": 5}
                )
                assert response.status_code == 200
                data = response.json()
                assert data["nodeId"] == "node_1"
                assert data["sources"] == []
                assert data["retrievalMetadata"]["totalCandidates"] == 0
                assert data["retrievalMetadata"]["strategy"] == "empty_query"
    
    def test_get_node_knowledge_with_vendor_filter(self, client: TestClient, mock_user, mock_case_with_graph):
        """测试带厂商过滤的知识溯源"""
        mock_knowledge_bases = [MagicMock(id="kb_1", name="知识库1")]
        
        mock_search_result = MagicMock()
        mock_search_result.ids = [["doc_1", "doc_2", "doc_3"]]
        mock_search_result.distances = [[0.8, 0.9, 0.7]]
        mock_search_result.documents = [["文档1", "文档2", "文档3"]]
        mock_search_result.metadatas = [[
            {"title": "配置1", "vendor": "cisco"},
            {"title": "配置2", "vendor": "huawei"},
            {"title": "配置3", "vendor": "cisco"}
        ]]
        
        with patch("open_webui.routers.cases_migrated.get_verified_user", return_value=mock_user):
            with patch("open_webui.routers.cases_migrated.cases_table.get_case_with_graph_by_id", return_value=mock_case_with_graph):
                with patch("open_webui.routers.cases_migrated.Knowledges.get_knowledge_bases_by_user_id", return_value=mock_knowledge_bases):
                    with patch("open_webui.routers.cases_migrated.get_ef"):
                        with patch("open_webui.routers.cases_migrated.get_embedding_function") as mock_get_embedding:
                            with patch("open_webui.routers.cases_migrated.VECTOR_DB_CLIENT.search", return_value=mock_search_result):
                                mock_embedding_func = MagicMock(return_value=[0.1, 0.2, 0.3])
                                mock_get_embedding.return_value = mock_embedding_func
                                
                                response = client.get(
                                    f"/api/v1/cases/{mock_case_with_graph.id}/nodes/node_2/knowledge",
                                    params={"topK": 5, "vendor": "cisco"}
                                )
                                assert response.status_code == 200
                                data = response.json()
                                
                                # 验证只返回cisco厂商的结果
                                sources = data.get("sources", [])
                                for source in sources:
                                    if "metadata" in source and source["metadata"]:
                                        assert source["metadata"].get("vendor") == "cisco"


class TestCaseNodesAPI:
    """案例节点相关API测试"""
    
    def test_list_case_nodes(self, client: TestClient, mock_user, mock_case_with_graph):
        """测试获取案例节点列表"""
        with patch("open_webui.routers.cases_migrated.get_verified_user", return_value=mock_user):
            with patch("open_webui.routers.cases_migrated.cases_table.get_case_with_graph_by_id", return_value=mock_case_with_graph):
                response = client.get(f"/api/v1/cases/{mock_case_with_graph.id}/nodes")
                assert response.status_code == 200
                data = response.json()
                assert "nodes" in data
                assert len(data["nodes"]) == 2
                
                # 验证节点按创建时间排序
                nodes = data["nodes"]
                for i in range(len(nodes) - 1):
                    assert nodes[i]["created_at"] <= nodes[i + 1]["created_at"]
    
    def test_get_node_detail(self, client: TestClient, mock_user, mock_case_with_graph):
        """测试获取节点详情"""
        with patch("open_webui.routers.cases_migrated.get_verified_user", return_value=mock_user):
            with patch("open_webui.routers.cases_migrated.cases_table.get_case_with_graph_by_id", return_value=mock_case_with_graph):
                # 为节点添加model_dump方法
                mock_case_with_graph.nodes[0].model_dump = MagicMock(return_value={
                    "id": "node_1",
                    "title": "用户问题",
                    "content": json.dumps({"text": "IP地址冲突如何解决？"}),
                    "node_type": "USER_QUERY",
                    "status": "COMPLETED"
                })
                
                response = client.get(f"/api/v1/cases/{mock_case_with_graph.id}/nodes/node_1")
                assert response.status_code == 200
                data = response.json()
                assert data["id"] == "node_1"
                assert data["title"] == "用户问题"
                assert data["node_type"] == "USER_QUERY"
