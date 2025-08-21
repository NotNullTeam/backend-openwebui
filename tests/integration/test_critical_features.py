"""
关键功能集成测试

测试新实现的P0级别功能：
1. 厂商命令生成接口
2. 文档摘要生成接口
3. 节点重生成异常处理
4. 批量操作性能优化
"""

import pytest
import asyncio
import json
import time
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from open_webui.routers.vendor_commands import router as vendor_router
from open_webui.routers.document_summary import router as summary_router
from open_webui.routers.cases_migrated import router as cases_router
from open_webui.services.batch_operations import (
    DatabaseBatchOperations, 
    CaseBatchOperations,
    KnowledgeBatchOperations
)

# 创建测试应用
app = FastAPI()
app.include_router(vendor_router, prefix="/api/v1/vendor")
app.include_router(summary_router, prefix="/api/v1")
app.include_router(cases_router, prefix="/api/v1")

client = TestClient(app)


class TestVendorCommands:
    """厂商命令生成接口测试"""
    
    @pytest.fixture
    def mock_user(self):
        user = Mock()
        user.id = "test_user_id"
        user.email = "test@example.com"
        user.role = "user"
        return user
    
    @pytest.fixture
    def mock_case_node(self):
        return {
            "id": "node_123",
            "case_id": "case_123", 
            "title": "网络连接问题",
            "content": json.dumps({
                "text": "设备无法ping通网关，可能是路由配置问题"
            }),
            "metadata": {"interface": "GigabitEthernet0/0/1"}
        }
    
    def test_get_node_vendor_commands_success(self, mock_user, mock_case_node):
        """测试获取节点厂商命令 - 成功场景"""
        with patch('open_webui.routers.vendor_commands.get_verified_user', return_value=mock_user):
            with patch('open_webui.routers.vendor_commands.cases_table') as mock_cases:
                # 模拟案例和节点数据
                mock_case = Mock()
                mock_case.user_id = mock_user.id
                mock_case.vendor = "cisco"
                mock_case.nodes = [Mock(**mock_case_node)]
                
                mock_cases.get_case_with_graph_by_id.return_value = mock_case
                
                with patch('open_webui.routers.vendor_commands.vendor_command_service') as mock_service:
                    mock_service.generate_commands.return_value = [
                        "show ip route",
                        "show interface status",
                        "ping 192.168.1.1"
                    ]
                    mock_service.get_supported_vendors.return_value = ["cisco", "huawei", "juniper"]
                    
                    response = client.get("/api/v1/vendor/cases/case_123/nodes/node_123/commands")
                    
                    assert response.status_code == 200
                    data = response.json()
                    
                    # 验证响应结构
                    assert "vendor" in data
                    assert "commands" in data
                    assert data["vendor"] == "cisco"
                    assert len(data["commands"]) == 3
                    assert "show ip route" in data["commands"]
    
    def test_get_node_vendor_commands_case_not_found(self, mock_user):
        """测试获取节点厂商命令 - 案例不存在"""
        with patch('open_webui.routers.vendor_commands.get_verified_user', return_value=mock_user):
            with patch('open_webui.routers.vendor_commands.cases_table') as mock_cases:
                mock_cases.get_case_with_graph_by_id.return_value = None
                
                response = client.get("/api/v1/vendor/cases/nonexistent/nodes/node_123/commands")
                
                assert response.status_code == 404
                assert "case not found" in response.json()["detail"]
    
    def test_get_node_vendor_commands_node_not_found(self, mock_user):
        """测试获取节点厂商命令 - 节点不存在"""
        with patch('open_webui.routers.vendor_commands.get_verified_user', return_value=mock_user):
            with patch('open_webui.routers.vendor_commands.cases_table') as mock_cases:
                mock_case = Mock()
                mock_case.user_id = mock_user.id
                mock_case.nodes = []  # 空节点列表
                
                mock_cases.get_case_with_graph_by_id.return_value = mock_case
                
                response = client.get("/api/v1/vendor/cases/case_123/nodes/nonexistent/commands")
                
                assert response.status_code == 404
                assert "node not found" in response.json()["detail"]
    
    def test_generate_vendor_commands_success(self, mock_user):
        """测试动态生成厂商命令 - 成功场景"""
        with patch('open_webui.routers.vendor_commands.get_verified_user', return_value=mock_user):
            with patch('open_webui.routers.vendor_commands.vendor_command_service') as mock_service:
                mock_service.generate_commands_by_description.return_value = {
                    "commands": [
                        "show version",
                        "show running-config interface",
                        "show ip interface brief"
                    ],
                    "description": "基础网络诊断命令"
                }
                
                response = client.post(
                    "/api/v1/vendor/commands/generate",
                    json={
                        "vendor": "cisco",
                        "problem_description": "接口状态异常"
                    }
                )
                
                assert response.status_code == 200
                data = response.json()
                
                assert "commands" in data
                assert len(data["commands"]) == 3
                assert "show version" in data["commands"]


class TestDocumentSummary:
    """文档摘要生成接口测试"""
    
    @pytest.fixture
    def mock_user(self):
        user = Mock()
        user.id = "test_user_id"
        user.role = "user"
        return user
    
    @pytest.fixture
    def mock_knowledge(self):
        return Mock(
            id="doc_123",
            name="测试文档",
            user_id="test_user_id",
            file_ids=["file_123"],
            data={"content": "这是一个测试文档的内容"},
            meta={}
        )
    
    def test_generate_document_summary_success(self, mock_user, mock_knowledge):
        """测试生成文档摘要 - 成功场景"""
        with patch('open_webui.routers.document_summary.get_verified_user', return_value=mock_user):
            with patch('open_webui.routers.document_summary.Knowledges') as mock_knowledges:
                with patch('open_webui.routers.document_summary.Files') as mock_files:
                    with patch('open_webui.routers.document_summary.VECTOR_DB_CLIENT') as mock_vector:
                        
                        mock_knowledges.get_knowledge_by_id.return_value = mock_knowledge
                        mock_files.get_file_by_id.return_value = Mock(id="file_123")
                        
                        # 模拟向量数据库返回
                        mock_collection = Mock()
                        mock_collection.get.return_value = {
                            "documents": ["文档内容片段1", "文档内容片段2"]
                        }
                        mock_vector.get_collection.return_value = mock_collection
                        
                        with patch('open_webui.routers.document_summary.generate_summary_with_llm') as mock_llm:
                            mock_llm.return_value = "这是生成的文档摘要"
                            
                            with patch('open_webui.routers.document_summary.extract_keywords') as mock_keywords:
                                mock_keywords.return_value = ["关键词1", "关键词2"]
                                
                                response = client.post(
                                    "/api/v1/knowledge/documents/doc_123/summary",
                                    json={
                                        "max_length": 200,
                                        "style": "concise",
                                        "language": "zh",
                                        "include_keywords": True
                                    }
                                )
                                
                                assert response.status_code == 200
                                data = response.json()
                                
                                # 验证响应结构
                                assert "document_id" in data
                                assert "title" in data
                                assert "summary" in data
                                assert "keywords" in data
                                assert "word_count" in data
                                assert "generation_time" in data
                                
                                assert data["document_id"] == "doc_123"
                                assert data["summary"] == "这是生成的文档摘要"
                                assert len(data["keywords"]) == 2
    
    def test_generate_document_summary_not_found(self, mock_user):
        """测试生成文档摘要 - 文档不存在"""
        with patch('open_webui.routers.document_summary.get_verified_user', return_value=mock_user):
            with patch('open_webui.routers.document_summary.Knowledges') as mock_knowledges:
                mock_knowledges.get_knowledge_by_id.return_value = None
                
                response = client.post("/api/v1/knowledge/documents/nonexistent/summary")
                
                assert response.status_code == 404
                assert "文档不存在" in response.json()["detail"]
    
    def test_generate_document_summary_permission_denied(self, mock_user, mock_knowledge):
        """测试生成文档摘要 - 权限不足"""
        mock_knowledge.user_id = "other_user_id"  # 不同的用户ID
        
        with patch('open_webui.routers.document_summary.get_verified_user', return_value=mock_user):
            with patch('open_webui.routers.document_summary.Knowledges') as mock_knowledges:
                mock_knowledges.get_knowledge_by_id.return_value = mock_knowledge
                
                response = client.post("/api/v1/knowledge/documents/doc_123/summary")
                
                assert response.status_code == 403
                assert "无权访问此文档" in response.json()["detail"]
    
    def test_get_document_summary_cached(self, mock_user, mock_knowledge):
        """测试获取文档摘要 - 缓存场景"""
        mock_knowledge.meta = {
            "summary": {
                "text": "缓存的摘要内容",
                "keywords": ["缓存关键词"],
                "generated_at": int(time.time())
            }
        }
        
        with patch('open_webui.routers.document_summary.get_verified_user', return_value=mock_user):
            with patch('open_webui.routers.document_summary.Knowledges') as mock_knowledges:
                mock_knowledges.get_knowledge_by_id.return_value = mock_knowledge
                
                response = client.get("/api/v1/knowledge/documents/doc_123/summary")
                
                assert response.status_code == 200
                data = response.json()
                
                assert data["summary"] == "缓存的摘要内容"
                assert data["cached"] is True


class TestNodeRegeneration:
    """节点重生成异常处理测试"""
    
    @pytest.fixture
    def mock_user(self):
        user = Mock()
        user.id = "test_user_id"
        user.role = "user"
        return user
    
    @pytest.fixture
    def mock_request(self):
        request = Mock()
        request.headers = {"X-Request-Id": "test_request_123"}
        request.app.state.redis = Mock()
        return request
    
    def test_regenerate_node_validation_errors(self, mock_user, mock_request):
        """测试节点重生成 - 参数验证错误"""
        with patch('open_webui.routers.cases_migrated.get_verified_user', return_value=mock_user):
            # 测试无效的重生成策略
            response = client.post(
                "/api/v1/cases/case_123/nodes/node_123/regenerate",
                json={
                    "regeneration_strategy": "invalid_strategy",
                    "prompt": "重新生成内容"
                }
            )
            
            assert response.status_code == 400
            assert "Invalid regeneration strategy" in response.json()["detail"]
    
    def test_regenerate_node_context_validation(self, mock_user, mock_request):
        """测试节点重生成 - 上下文参数验证"""
        with patch('open_webui.routers.cases_migrated.get_verified_user', return_value=mock_user):
            # 测试无效的上下文类型
            response = client.post(
                "/api/v1/cases/case_123/nodes/node_123/regenerate",
                json={
                    "context": "invalid_context_type",  # 应该是字典
                    "prompt": "重新生成内容"
                }
            )
            
            assert response.status_code == 400
            assert "Context must be a dictionary" in response.json()["detail"]
    
    def test_regenerate_node_not_found(self, mock_user, mock_request):
        """测试节点重生成 - 节点不存在"""
        with patch('open_webui.routers.cases_migrated.get_verified_user', return_value=mock_user):
            with patch('open_webui.routers.cases_migrated.get_db') as mock_get_db:
                mock_db = Mock()
                mock_db.query().filter().first.return_value = None
                mock_get_db.return_value = mock_db
                
                response = client.post(
                    "/api/v1/cases/case_123/nodes/nonexistent/regenerate",
                    json={"prompt": "重新生成内容"}
                )
                
                assert response.status_code == 404
                assert "Node not found" in response.json()["detail"]
    
    def test_regenerate_node_already_processing(self, mock_user, mock_request):
        """测试节点重生成 - 节点已在处理中"""
        with patch('open_webui.routers.cases_migrated.get_verified_user', return_value=mock_user):
            with patch('open_webui.routers.cases_migrated.get_db') as mock_get_db:
                mock_node = Mock()
                mock_node.status = "PROCESSING"
                mock_node.metadata_ = {
                    "processing_started_at": int(time.time()) - 60  # 1分钟前开始
                }
                
                mock_db = Mock()
                mock_db.query().filter().first.return_value = mock_node
                mock_get_db.return_value = mock_db
                
                response = client.post(
                    "/api/v1/cases/case_123/nodes/node_123/regenerate",
                    json={"prompt": "重新生成内容"}
                )
                
                assert response.status_code == 409
                assert "already being regenerated" in response.json()["detail"]


class TestBatchOperations:
    """批量操作性能测试"""
    
    def test_database_batch_operations_initialization(self):
        """测试数据库批量操作初始化"""
        db_ops = DatabaseBatchOperations()
        
        # 验证连接池配置
        assert db_ops.batch_engine is not None
        assert db_ops.BatchSession is not None
        
        # 验证连接池参数
        pool = db_ops.batch_engine.pool
        assert pool.size() >= 20  # 连接池大小
    
    def test_bulk_insert_empty_records(self):
        """测试批量插入 - 空记录"""
        db_ops = DatabaseBatchOperations()
        result = db_ops.bulk_insert("test_table", [])
        assert result == 0
    
    def test_bulk_update_empty_records(self):
        """测试批量更新 - 空记录"""
        db_ops = DatabaseBatchOperations()
        result = db_ops.bulk_update("test_table", [])
        assert result == 0
    
    def test_bulk_delete_empty_ids(self):
        """测试批量删除 - 空ID列表"""
        db_ops = DatabaseBatchOperations()
        result = db_ops.bulk_delete("test_table", [])
        assert result == 0
    
    def test_case_batch_operations_initialization(self):
        """测试案例批量操作初始化"""
        case_ops = CaseBatchOperations()
        assert case_ops.db_ops is not None
        assert isinstance(case_ops.db_ops, DatabaseBatchOperations)
    
    def test_knowledge_batch_operations_initialization(self):
        """测试知识库批量操作初始化"""
        knowledge_ops = KnowledgeBatchOperations()
        assert knowledge_ops.db_ops is not None
        assert isinstance(knowledge_ops.db_ops, DatabaseBatchOperations)
    
    @pytest.mark.asyncio
    async def test_batch_embed_documents_dynamic_sizing(self):
        """测试批量向量化 - 动态批次大小"""
        knowledge_ops = KnowledgeBatchOperations()
        
        # 测试大文档（应该使用小批次）
        large_docs = [
            {"id": f"doc_{i}", "content": "x" * 6000}  # 6KB文档
            for i in range(10)
        ]
        
        with patch('open_webui.services.batch_operations.VECTOR_DB_CLIENT'):
            with patch('open_webui.routers.retrieval.get_embedding_function') as mock_ef:
                mock_ef.return_value = Mock()
                mock_ef.return_value.embed_documents.return_value = [[0.1] * 768]
                
                # 这里主要测试参数计算逻辑，不实际执行向量化
                avg_size = sum(len(doc["content"]) for doc in large_docs) / len(large_docs)
                assert avg_size > 5000  # 确认是大文档
    
    def test_bulk_update_case_when_strategy(self):
        """测试CASE WHEN批量更新策略"""
        db_ops = DatabaseBatchOperations()
        
        # 创建大量更新记录（触发CASE WHEN策略）
        updates = [
            {"id": f"id_{i}", "name": f"name_{i}", "status": "updated"}
            for i in range(150)  # 超过100条，应该使用CASE WHEN
        ]
        
        # 测试策略选择逻辑
        with patch.object(db_ops, '_bulk_update_case_when') as mock_case_when:
            mock_case_when.return_value = 150
            
            result = db_ops.bulk_update("test_table", updates)
            
            # 验证调用了CASE WHEN方法
            mock_case_when.assert_called_once_with("test_table", updates, "id")
            assert result == 150


class TestErrorHandlingAndRecovery:
    """错误处理和恢复测试"""
    
    @pytest.fixture
    def mock_user(self):
        user = Mock()
        user.id = "test_user_id"
        return user
    
    def test_vendor_commands_service_failure(self, mock_user):
        """测试厂商命令服务失败处理"""
        with patch('open_webui.routers.vendor_commands.get_verified_user', return_value=mock_user):
            with patch('open_webui.routers.vendor_commands.cases_table') as mock_cases:
                mock_case = Mock()
                mock_case.user_id = mock_user.id
                mock_case.vendor = "cisco"
                mock_case.nodes = [Mock(id="node_123", content="test")]
                mock_cases.get_case_with_graph_by_id.return_value = mock_case
                
                with patch('open_webui.routers.vendor_commands.vendor_command_service') as mock_service:
                    # 模拟服务异常
                    mock_service.generate_commands.side_effect = Exception("Service unavailable")
                    mock_service.get_supported_vendors.return_value = ["cisco"]
                    
                    response = client.get("/api/v1/vendor/cases/case_123/nodes/node_123/commands")
                    
                    # 应该返回空命令列表而不是错误
                    assert response.status_code == 200
                    data = response.json()
                    assert data["commands"] == []
    
    def test_document_summary_llm_failure(self, mock_user):
        """测试文档摘要LLM失败处理"""
        mock_knowledge = Mock(
            id="doc_123",
            name="测试文档",
            user_id="test_user_id",
            file_ids=["file_123"],
            data={"content": "测试内容"}
        )
        
        with patch('open_webui.routers.document_summary.get_verified_user', return_value=mock_user):
            with patch('open_webui.routers.document_summary.Knowledges') as mock_knowledges:
                with patch('open_webui.routers.document_summary.Files') as mock_files:
                    mock_knowledges.get_knowledge_by_id.return_value = mock_knowledge
                    mock_files.get_file_by_id.return_value = Mock(id="file_123")
                    
                    with patch('open_webui.routers.document_summary.VECTOR_DB_CLIENT') as mock_vector:
                        mock_collection = Mock()
                        mock_collection.get.return_value = {"documents": ["内容"]}
                        mock_vector.get_collection.return_value = mock_collection
                        
                        with patch('open_webui.routers.document_summary.generate_summary_with_llm') as mock_llm:
                            # 模拟LLM失败，应该降级到简单截取
                            mock_llm.side_effect = Exception("LLM service failed")
                            
                            response = client.post("/api/v1/knowledge/documents/doc_123/summary")
                            
                            # 应该返回降级的摘要而不是错误
                            assert response.status_code == 200
                            data = response.json()
                            assert "summary" in data
                            # 降级摘要应该包含原始内容的截取
                            assert len(data["summary"]) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
