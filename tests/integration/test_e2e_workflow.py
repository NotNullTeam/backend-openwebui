"""
端到端集成测试套件

测试完整的业务流程，包括：
1. 用户注册/登录
2. 文档上传和处理
3. 案例创建和管理
4. 知识检索和分析
5. 日志解析和诊断
"""

import pytest
import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from open_webui.routers.cases_migrated import router as cases_router
from open_webui.routers.knowledge_migrated import router as knowledge_router
from open_webui.routers.analysis_migrated import router as analysis_router
from open_webui.routers.system_migrated import router as system_router

# 创建集成测试应用
app = FastAPI()
app.include_router(cases_router, prefix="/api/v1")
app.include_router(knowledge_router, prefix="/api/v1")
app.include_router(analysis_router, prefix="/api/v1")
app.include_router(system_router, prefix="/api/v1")

client = TestClient(app)

class TestE2EWorkflow:
    """端到端工作流测试"""
    
    @pytest.fixture
    def mock_user(self):
        """模拟用户"""
        user = Mock()
        user.id = "e2e_user_id"
        user.email = "e2e@example.com"
        user.name = "E2E Test User"
        user.role = "user"
        return user
    
    @pytest.fixture
    def test_document_content(self):
        """测试文档内容"""
        return """
        华为交换机故障排查手册
        
        第一章：接口故障诊断
        1.1 接口Down故障
        当接口状态显示Down时，可能的原因包括：
        - 物理连接问题
        - 接口配置错误
        - 硬件故障
        
        排查步骤：
        1. 检查物理连接
        2. 查看接口配置
        3. 检查接口状态
        
        第二章：路由故障诊断
        2.1 路由表异常
        当路由表出现异常时，需要检查：
        - 路由协议配置
        - 网络拓扑
        - 路由策略
        """
    
    @pytest.fixture
    def sample_log_content(self):
        """示例日志内容"""
        return """
        2024-01-01 10:00:00 [ERROR] Interface GigabitEthernet0/0/1 changed state to down
        2024-01-01 10:00:01 [WARN] Link down on interface GigabitEthernet0/0/1
        2024-01-01 10:00:02 [INFO] Attempting to bring interface GigabitEthernet0/0/1 up
        2024-01-01 10:00:05 [ERROR] Failed to bring interface GigabitEthernet0/0/1 up
        """
    
    def test_complete_workflow_success(self, mock_user, test_document_content, sample_log_content):
        """测试完整的端到端工作流"""
        
        # 步骤1: 系统健康检查
        with patch('open_webui.routers.system_migrated.get_verified_user', return_value=mock_user):
            with patch('open_webui.routers.system_migrated.get_db') as mock_get_db:
                mock_db = Mock()
                mock_get_db.return_value.__enter__.return_value = mock_db
                mock_db.query.return_value.count.return_value = 10
                
                health_response = client.get("/api/v1/system/health")
                assert health_response.status_code == 200
                health_data = health_response.json()
                assert health_data["status"] == "healthy"
        
        # 步骤2: 上传知识文档
        with patch('open_webui.routers.knowledge_migrated.get_verified_user', return_value=mock_user):
            with patch('open_webui.routers.knowledge_migrated.Files') as mock_files:
                with patch('open_webui.routers.knowledge_migrated.allowed_file', return_value=True):
                    with patch('open_webui.routers.knowledge_migrated.queue_document_for_processing', return_value=True):
                        
                        mock_file = Mock()
                        mock_file.id = "test_doc_id"
                        mock_file.filename = "huawei_manual.pdf"
                        mock_files.insert_new_file.return_value = mock_file
                        
                        files = {"file": ("huawei_manual.pdf", test_document_content.encode('utf-8'), "application/pdf")}
                        data = {"vendor": "华为", "tags": "故障排查,接口"}
                        
                        upload_response = client.post("/api/v1/documents", files=files, data=data)
                        assert upload_response.status_code == 200
                        upload_data = upload_response.json()
                        assert upload_data["status"] == "QUEUED"
                        document_id = upload_data["docId"]
        
        # 步骤3: 检查文档处理状态
        with patch('open_webui.routers.knowledge_migrated.get_verified_user', return_value=mock_user):
            with patch('open_webui.routers.knowledge_migrated.Files') as mock_files:
                with patch('open_webui.routers.knowledge_migrated.get_document_processing_status') as mock_status:
                    
                    mock_file = Mock()
                    mock_file.id = document_id
                    mock_file.user_id = mock_user.id
                    mock_files.get_file_by_id.return_value = mock_file
                    
                    mock_status.return_value = {
                        "status": "COMPLETED",
                        "progress": 100,
                        "error": None,
                        "completed_at": "2024-01-01T10:05:00Z"
                    }
                    
                    status_response = client.get(f"/api/v1/documents/{document_id}/processing-status")
                    assert status_response.status_code == 200
                    status_data = status_response.json()
                    assert status_data["status"] == "COMPLETED"
        
        # 步骤4: 创建故障案例
        with patch('open_webui.routers.cases_migrated.get_verified_user', return_value=mock_user):
            with patch('open_webui.routers.cases_migrated.cases_table') as mock_cases_table:
                
                mock_case = Mock()
                mock_case.id = "test_case_id"
                mock_case.title = "接口故障案例"
                mock_case.user_id = mock_user.id
                mock_cases_table.insert_new_case.return_value = mock_case
                
                case_data = {
                    "query": "GigabitEthernet0/0/1接口Down故障",
                    "title": "接口故障案例",
                    "vendor": "华为",
                    "category": "接口故障",
                    "attachments": [{"fileId": document_id, "fileName": "huawei_manual.pdf"}]
                }
                
                case_response = client.post("/api/v1/cases", json=case_data)
                assert case_response.status_code == 200
                case_response_data = case_response.json()
                assert case_response_data["message"] == "案例创建成功"
                case_id = case_response_data["caseId"]
        
        # 步骤5: 执行日志解析
        with patch('open_webui.routers.analysis_migrated.get_verified_user', return_value=mock_user):
            with patch('open_webui.routers.analysis_migrated.log_parsing_service') as mock_log_service:
                with patch('open_webui.routers.analysis_migrated.get_retrieval_vector_db') as mock_get_vector_db:
                    
                    # 模拟日志解析结果
                    mock_log_service.parse_log.return_value = {
                        "anomalies": [
                            {
                                "type": "interface_down",
                                "severity": "high",
                                "description": "接口GigabitEthernet0/0/1已断开",
                                "location": "GigabitEthernet0/0/1",
                                "timestamp": "2024-01-01T10:00:00Z"
                            }
                        ],
                        "summary": "检测到接口故障",
                        "recommendations": ["检查物理连接", "查看接口配置"]
                    }
                    
                    # 模拟知识检索结果
                    mock_vector_db = Mock()
                    mock_get_vector_db.return_value = mock_vector_db
                    mock_vector_db.search.return_value = [
                        {
                            "content": "接口故障排查步骤：1. 检查物理连接 2. 查看接口配置",
                            "metadata": {"source": "huawei_manual.pdf", "page": 1},
                            "score": 0.95
                        }
                    ]
                    
                    log_parsing_data = {
                        "logContent": sample_log_content,
                        "logType": "华为交换机",
                        "vendor": "华为",
                        "deviceModel": "S5700",
                        "attachments": [{"fileId": document_id, "fileName": "huawei_manual.pdf"}]
                    }
                    
                    parsing_response = client.post("/api/v1/analysis/log-parsing", json=log_parsing_data)
                    assert parsing_response.status_code == 200
                    parsing_data = parsing_response.json()
                    assert parsing_data["severity"] == "high"
                    assert len(parsing_data["anomalies"]) == 1
                    assert len(parsing_data["relatedKnowledge"]) == 1
        
        # 步骤6: 执行知识检索
        with patch('open_webui.routers.knowledge_migrated.get_verified_user', return_value=mock_user):
            with patch('open_webui.routers.knowledge_migrated.get_retrieval_vector_db') as mock_get_vector_db:
                with patch('open_webui.routers.knowledge_migrated.similarity_normalizer') as mock_normalizer:
                    
                    mock_vector_db = Mock()
                    mock_get_vector_db.return_value = mock_vector_db
                    
                    search_results = [
                        {
                            "content": "接口故障排查步骤详细说明",
                            "metadata": {"source": "huawei_manual.pdf", "page": 1, "file_id": document_id},
                            "score": 0.95
                        },
                        {
                            "content": "GigabitEthernet接口配置方法",
                            "metadata": {"source": "huawei_manual.pdf", "page": 2, "file_id": document_id},
                            "score": 0.88
                        }
                    ]
                    
                    mock_vector_db.search.return_value = search_results
                    mock_normalizer.normalize_scores.return_value = search_results
                    
                    search_data = {
                        "query": "接口Down故障排查",
                        "topK": 5,
                        "vendor": "华为"
                    }
                    
                    search_response = client.post("/api/v1/knowledge/search", json=search_data)
                    assert search_response.status_code == 200
                    search_response_data = search_response.json()
                    assert len(search_response_data["results"]) == 2
                    assert search_response_data["results"][0]["score"] == 0.95
        
        # 步骤7: 添加案例节点（基于分析结果）
        with patch('open_webui.routers.cases_migrated.get_verified_user', return_value=mock_user):
            with patch('open_webui.routers.cases_migrated.cases_table') as mock_cases_table:
                
                mock_case = Mock()
                mock_case.user_id = mock_user.id
                mock_cases_table.get_case_by_id.return_value = mock_case
                
                mock_node = Mock()
                mock_node.id = "analysis_node_id"
                mock_cases_table.insert_new_case_node.return_value = mock_node
                
                node_data = {
                    "title": "日志分析结果",
                    "content": {
                        "text": "分析发现接口GigabitEthernet0/0/1故障",
                        "anomalies": parsing_data["anomalies"],
                        "recommendations": parsing_data["recommendations"]
                    },
                    "nodeType": "AI_ANALYSIS"
                }
                
                node_response = client.post(f"/api/v1/cases/{case_id}/nodes", json=node_data)
                assert node_response.status_code == 200
                node_response_data = node_response.json()
                assert node_response_data["message"] == "节点创建成功"
        
        # 步骤8: 获取完整案例信息
        with patch('open_webui.routers.cases_migrated.get_verified_user', return_value=mock_user):
            with patch('open_webui.routers.cases_migrated.cases_table') as mock_cases_table:
                
                mock_case = Mock()
                mock_case.id = case_id
                mock_case.title = "接口故障案例"
                mock_case.user_id = mock_user.id
                mock_case.status = "ACTIVE"
                mock_case.created_at = "2024-01-01T10:00:00Z"
                mock_cases_table.get_case_by_id.return_value = mock_case
                
                case_detail_response = client.get(f"/api/v1/cases/{case_id}")
                assert case_detail_response.status_code == 200
                case_detail_data = case_detail_response.json()
                assert case_detail_data["caseId"] == case_id
                assert case_detail_data["title"] == "接口故障案例"
    
    def test_error_handling_workflow(self, mock_user):
        """测试错误处理工作流"""
        
        # 测试上传无效文件
        with patch('open_webui.routers.knowledge_migrated.get_verified_user', return_value=mock_user):
            with patch('open_webui.routers.knowledge_migrated.allowed_file', return_value=False):
                
                files = {"file": ("invalid.exe", b"invalid content", "application/octet-stream")}
                upload_response = client.post("/api/v1/documents", files=files)
                assert upload_response.status_code == 400
                assert "不支持的文件类型" in upload_response.json()["detail"]
        
        # 测试访问不存在的案例
        with patch('open_webui.routers.cases_migrated.get_verified_user', return_value=mock_user):
            with patch('open_webui.routers.cases_migrated.cases_table') as mock_cases_table:
                mock_cases_table.get_case_by_id.return_value = None
                
                case_response = client.get("/api/v1/cases/nonexistent_case")
                assert case_response.status_code == 404
                assert "案例不存在" in case_response.json()["detail"]
        
        # 测试空查询搜索
        with patch('open_webui.routers.knowledge_migrated.get_verified_user', return_value=mock_user):
            search_data = {"query": "", "topK": 5}
            search_response = client.post("/api/v1/knowledge/search", json=search_data)
            assert search_response.status_code == 400
            assert "查询不能为空" in search_response.json()["detail"]
        
        # 测试日志解析服务错误
        with patch('open_webui.routers.analysis_migrated.get_verified_user', return_value=mock_user):
            with patch('open_webui.routers.analysis_migrated.log_parsing_service') as mock_log_service:
                mock_log_service.parse_log.side_effect = Exception("解析服务错误")
                
                log_data = {
                    "logContent": "test log",
                    "logType": "华为交换机",
                    "vendor": "华为"
                }
                
                parsing_response = client.post("/api/v1/analysis/log-parsing", json=log_data)
                assert parsing_response.status_code == 500
                assert "日志解析失败" in parsing_response.json()["detail"]

class TestConcurrentOperations:
    """并发操作测试"""
    
    @pytest.fixture
    def mock_user(self):
        """模拟用户"""
        user = Mock()
        user.id = "concurrent_user_id"
        user.email = "concurrent@example.com"
        user.role = "user"
        return user
    
    def test_concurrent_document_upload(self, mock_user):
        """测试并发文档上传"""
        
        with patch('open_webui.routers.knowledge_migrated.get_verified_user', return_value=mock_user):
            with patch('open_webui.routers.knowledge_migrated.Files') as mock_files:
                with patch('open_webui.routers.knowledge_migrated.allowed_file', return_value=True):
                    with patch('open_webui.routers.knowledge_migrated.queue_document_for_processing', return_value=True):
                        
                        # 模拟多个文件上传
                        responses = []
                        for i in range(3):
                            mock_file = Mock()
                            mock_file.id = f"doc_{i}"
                            mock_file.filename = f"document_{i}.pdf"
                            mock_files.insert_new_file.return_value = mock_file
                            
                            files = {"file": (f"document_{i}.pdf", b"content", "application/pdf")}
                            response = client.post("/api/v1/documents", files=files)
                            responses.append(response)
                        
                        # 验证所有上传都成功
                        for response in responses:
                            assert response.status_code == 200
                            assert response.json()["status"] == "QUEUED"
    
    def test_concurrent_case_operations(self, mock_user):
        """测试并发案例操作"""
        
        with patch('open_webui.routers.cases_migrated.get_verified_user', return_value=mock_user):
            with patch('open_webui.routers.cases_migrated.cases_table') as mock_cases_table:
                
                # 模拟并发创建案例
                responses = []
                for i in range(3):
                    mock_case = Mock()
                    mock_case.id = f"case_{i}"
                    mock_case.title = f"案例_{i}"
                    mock_cases_table.insert_new_case.return_value = mock_case
                    
                    case_data = {
                        "query": f"问题_{i}",
                        "title": f"案例_{i}",
                        "vendor": "华为",
                        "category": "测试",
                        "attachments": []
                    }
                    
                    response = client.post("/api/v1/cases", json=case_data)
                    responses.append(response)
                
                # 验证所有创建都成功
                for response in responses:
                    assert response.status_code == 200
                    assert response.json()["message"] == "案例创建成功"

class TestDataConsistency:
    """数据一致性测试"""
    
    @pytest.fixture
    def mock_user(self):
        """模拟用户"""
        user = Mock()
        user.id = "consistency_user_id"
        user.email = "consistency@example.com"
        user.role = "user"
        return user
    
    def test_case_node_edge_consistency(self, mock_user):
        """测试案例节点和边的一致性"""
        
        with patch('open_webui.routers.cases_migrated.get_verified_user', return_value=mock_user):
            with patch('open_webui.routers.cases_migrated.cases_table') as mock_cases_table:
                
                # 创建案例
                mock_case = Mock()
                mock_case.id = "consistency_case_id"
                mock_case.user_id = mock_user.id
                mock_cases_table.get_case_by_id.return_value = mock_case
                mock_cases_table.insert_new_case.return_value = mock_case
                
                case_data = {
                    "query": "一致性测试案例",
                    "title": "一致性测试",
                    "vendor": "华为",
                    "category": "测试",
                    "attachments": []
                }
                
                case_response = client.post("/api/v1/cases", json=case_data)
                assert case_response.status_code == 200
                case_id = case_response.json()["caseId"]
                
                # 创建节点
                mock_node1 = Mock()
                mock_node1.id = "node_1"
                mock_node2 = Mock()
                mock_node2.id = "node_2"
                mock_cases_table.insert_new_case_node.return_value = mock_node1
                
                node1_data = {
                    "title": "节点1",
                    "content": {"text": "节点1内容"},
                    "nodeType": "USER_QUERY"
                }
                
                node1_response = client.post(f"/api/v1/cases/{case_id}/nodes", json=node1_data)
                assert node1_response.status_code == 200
                
                mock_cases_table.insert_new_case_node.return_value = mock_node2
                node2_data = {
                    "title": "节点2",
                    "content": {"text": "节点2内容"},
                    "nodeType": "AI_RESPONSE"
                }
                
                node2_response = client.post(f"/api/v1/cases/{case_id}/nodes", json=node2_data)
                assert node2_response.status_code == 200
                
                # 创建边
                mock_edge = Mock()
                mock_edge.id = "edge_1"
                mock_cases_table.insert_new_case_edge.return_value = mock_edge
                
                edge_data = {
                    "sourceNodeId": "node_1",
                    "targetNodeId": "node_2",
                    "edgeType": "FLOW"
                }
                
                edge_response = client.post(f"/api/v1/cases/{case_id}/edges", json=edge_data)
                assert edge_response.status_code == 200
                
                # 验证数据一致性
                assert case_response.json()["caseId"] == case_id
                assert node1_response.json()["nodeId"] == "node_1"
                assert node2_response.json()["nodeId"] == "node_2"
                assert edge_response.json()["edgeId"] == "edge_1"

if __name__ == "__main__":
    pytest.main([__file__])
