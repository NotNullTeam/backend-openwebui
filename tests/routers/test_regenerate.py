"""
节点重生成功能测试用例
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime
import json
import uuid
import time

from open_webui.main import app
from open_webui.models.users import UserModel
from open_webui.models.cases import CaseModel, CaseNode


@pytest.fixture
def client():
    """测试客户端"""
    return TestClient(app)


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


@pytest.fixture
def mock_case():
    """模拟案例"""
    return CaseModel(
        id="case_123",
        user_id="user_123",
        title="网络故障诊断",
        description="网络连接异常",
        created_at=int(time.time()),
        updated_at=int(time.time())
    )


@pytest.fixture
def mock_node():
    """模拟节点"""
    return CaseNode(
        id="node_456",
        case_id="case_123",
        title="初始分析",
        content='{"analysis": "可能是DNS配置问题"}',
        node_type="AI_ANALYSIS",
        status="COMPLETED",
        metadata_={"score": 0.8},
        created_at=int(time.time()),
        updated_at=int(time.time())
    )


class TestNodeRegeneration:
    """节点重生成功能测试"""
    
    def test_regenerate_node_success(self, client: TestClient, auth_headers, verified_user, mock_case, mock_node):
        """测试成功重生成节点"""
        with patch('open_webui.routers.cases_migrated.get_verified_user', return_value=verified_user):
            with patch('open_webui.routers.cases_migrated.cases_table') as mock_cases_table:
                # 设置mock返回值
                mock_cases_table.get_case_by_id.return_value = mock_case
                mock_cases_table.get_node_by_id.return_value = mock_node
                
                # Mock regenerate_with_model
                with patch('open_webui.routers.cases_migrated.regenerate_with_model') as mock_regenerate:
                    mock_regenerate.return_value = json.dumps({
                        "analysis": "经过深入分析，问题确定为DNS解析失败",
                        "causes": ["DNS服务器无响应", "DNS配置错误"],
                        "steps": ["检查DNS配置", "测试DNS解析", "更换DNS服务器"],
                        "commands": ["nslookup example.com", "ipconfig /flushdns"],
                        "summary": "DNS配置问题导致网络连接失败"
                    })
                    
                    # Mock create_task
                    with patch('open_webui.routers.cases_migrated.create_task') as mock_create_task:
                        mock_create_task.return_value = ("task_789", None)
                        
                        response = client.post(
                            f"/api/v1/cases/{mock_case.id}/nodes/{mock_node.id}/regenerate",
                            headers=auth_headers,
                            json={
                                "prompt": "请提供更详细的诊断步骤",
                                "regeneration_strategy": "detailed",
                                "async_mode": True
                            }
                        )
                        
                        assert response.status_code == 200
                        data = response.json()
                        assert data["taskId"] == "task_789"
                        assert data["nodeId"] == mock_node.id
                        assert data["status"] == "submitted"
    
    def test_regenerate_node_sync_mode(self, client: TestClient, auth_headers, verified_user, mock_case, mock_node):
        """测试同步模式重生成节点"""
        with patch('open_webui.routers.cases_migrated.get_verified_user', return_value=verified_user):
            with patch('open_webui.routers.cases_migrated.cases_table') as mock_cases_table:
                mock_cases_table.get_case_by_id.return_value = mock_case
                mock_cases_table.get_node_by_id.return_value = mock_node
                
                with patch('open_webui.routers.cases_migrated.regenerate_with_model') as mock_regenerate:
                    async_mock = AsyncMock(return_value=json.dumps({"analysis": "重新生成的内容"}))
                    mock_regenerate.return_value = async_mock()
                    
                    with patch('open_webui.internal.db.get_db') as mock_get_db:
                        mock_db = MagicMock()
                        mock_get_db.return_value.__enter__.return_value = mock_db
                        mock_db.query.return_value.filter_by.return_value.first.return_value = mock_node
                        
                        response = client.post(
                            f"/api/v1/cases/{mock_case.id}/nodes/{mock_node.id}/regenerate",
                            headers=auth_headers,
                            json={
                                "prompt": "优化分析",
                                "async_mode": False
                            }
                        )
                        
                        assert response.status_code == 200
                        data = response.json()
                        assert data["taskId"] is None
                        assert data["nodeId"] == mock_node.id
                        assert data["status"] == "completed"
    
    def test_regenerate_node_case_not_found(self, client: TestClient, auth_headers, verified_user):
        """测试案例不存在时重生成节点"""
        with patch('open_webui.routers.cases_migrated.get_verified_user', return_value=verified_user):
            with patch('open_webui.routers.cases_migrated.cases_table') as mock_cases_table:
                mock_cases_table.get_case_by_id.return_value = None
                
                response = client.post(
                    "/api/v1/cases/invalid_case/nodes/node_123/regenerate",
                    headers=auth_headers,
                    json={"prompt": "重新生成"}
                )
                
                assert response.status_code == 404
                assert "case not found" in response.json()["detail"].lower()
    
    def test_regenerate_node_not_owner(self, client: TestClient, auth_headers, verified_user, mock_case):
        """测试非案例所有者重生成节点"""
        mock_case.user_id = "other_user"
        
        with patch('open_webui.routers.cases_migrated.get_verified_user', return_value=verified_user):
            with patch('open_webui.routers.cases_migrated.cases_table') as mock_cases_table:
                mock_cases_table.get_case_by_id.return_value = mock_case
                
                response = client.post(
                    f"/api/v1/cases/{mock_case.id}/nodes/node_123/regenerate",
                    headers=auth_headers,
                    json={"prompt": "重新生成"}
                )
                
                assert response.status_code == 404
                assert "case not found" in response.json()["detail"].lower()
    
    def test_regenerate_node_not_found(self, client: TestClient, auth_headers, verified_user, mock_case):
        """测试节点不存在时重生成"""
        with patch('open_webui.routers.cases_migrated.get_verified_user', return_value=verified_user):
            with patch('open_webui.routers.cases_migrated.cases_table') as mock_cases_table:
                mock_cases_table.get_case_by_id.return_value = mock_case
                mock_cases_table.get_node_by_id.return_value = None
                
                response = client.post(
                    f"/api/v1/cases/{mock_case.id}/nodes/invalid_node/regenerate",
                    headers=auth_headers,
                    json={"prompt": "重新生成"}
                )
                
                assert response.status_code == 404
                assert "node not found" in response.json()["detail"].lower()


class TestRegenerationService:
    """重生成服务测试"""
    
    def test_build_regeneration_messages_chinese(self):
        """测试构建中文重生成消息"""
        from open_webui.services.ai.regenerate_service import build_regeneration_messages
        
        messages = build_regeneration_messages(
            original_text="原始分析内容",
            user_prompt="请添加更多细节",
            strategy="detailed",
            language="zh"
        )
        
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert "网络诊断助手" in messages[0]["content"]
        assert messages[1]["role"] == "user"
        assert "[原始内容]" in messages[1]["content"]
        assert "[用户提示]" in messages[1]["content"]
        assert "[生成策略]" in messages[1]["content"]
    
    def test_build_regeneration_messages_english(self):
        """测试构建英文重生成消息"""
        from open_webui.services.ai.regenerate_service import build_regeneration_messages
        
        messages = build_regeneration_messages(
            original_text="Original analysis",
            user_prompt="Add more details",
            strategy="detailed",
            language="en"
        )
        
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert "network troubleshooting assistant" in messages[0]["content"]
        assert messages[1]["role"] == "user"
        assert "[原始内容]" in messages[1]["content"]
    
    @pytest.mark.asyncio
    async def test_regenerate_with_model_success(self, verified_user):
        """测试模型重生成成功"""
        from open_webui.services.ai.regenerate_service import regenerate_with_model
        
        # Mock request
        mock_request = Mock()
        mock_request.app.state.MODELS = {"model1": {}, "model2": {}}
        mock_request.app.state.config.TASK_MODEL = None
        mock_request.app.state.config.TASK_MODEL_EXTERNAL = None
        
        messages = [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "User prompt"}
        ]
        
        with patch('open_webui.services.ai.regenerate_service.get_task_model_id') as mock_get_model:
            mock_get_model.return_value = "model1"
            
            with patch('open_webui.services.ai.regenerate_service.process_pipeline_inlet_filter') as mock_filter:
                mock_filter.return_value = {
                    "model": "model1",
                    "messages": messages,
                    "stream": False,
                    "metadata": {}
                }
                
                with patch('open_webui.services.ai.regenerate_service.generate_chat_completion') as mock_generate:
                    # Mock response
                    mock_response = Mock()
                    mock_response.body = json.dumps({
                        "choices": [{
                            "message": {
                                "content": "Generated content"
                            }
                        }]
                    }).encode('utf-8')
                    mock_generate.return_value = mock_response
                    
                    result = await regenerate_with_model(
                        mock_request,
                        verified_user,
                        messages,
                        model_hint="model1",
                        metadata={"task": "test"}
                    )
                    
                    assert result == "Generated content"
    
    @pytest.mark.asyncio
    async def test_regenerate_with_model_no_models(self, verified_user):
        """测试无可用模型时重生成"""
        from open_webui.services.ai.regenerate_service import regenerate_with_model
        
        mock_request = Mock()
        mock_request.app.state.MODELS = {}
        
        messages = [{"role": "user", "content": "Test"}]
        
        with pytest.raises(RuntimeError, match="No models available"):
            await regenerate_with_model(mock_request, verified_user, messages)
    
    def test_extract_text_from_node_content(self):
        """测试从节点内容提取文本"""
        from open_webui.services.ai.regenerate_service import _extract_text_from_node_content
        
        # 测试JSON格式
        content = '{"text": "这是文本内容", "other": "data"}'
        assert _extract_text_from_node_content(content) == "这是文本内容"
        
        # 测试分析字段
        content = '{"analysis": "分析结果"}'
        assert _extract_text_from_node_content(content) == "分析结果"
        
        # 测试答案字段
        content = '{"answer": "答案内容"}'
        assert _extract_text_from_node_content(content) == "答案内容"
        
        # 测试普通文本
        content = "普通文本内容"
        assert _extract_text_from_node_content(content) == "普通文本内容"
        
        # 测试空内容
        assert _extract_text_from_node_content("") == ""
        assert _extract_text_from_node_content(None) == ""


class TestRegenerationStrategies:
    """重生成策略测试"""
    
    def test_regeneration_strategies(self):
        """测试不同的重生成策略"""
        strategies = [
            "detailed",      # 详细模式
            "concise",       # 简洁模式
            "technical",     # 技术模式
            "step-by-step",  # 分步模式
            "summary"        # 摘要模式
        ]
        
        from open_webui.services.ai.regenerate_service import build_regeneration_messages
        
        for strategy in strategies:
            messages = build_regeneration_messages(
                original_text="测试内容",
                strategy=strategy,
                language="zh"
            )
            assert len(messages) == 2
            assert f"[生成策略]\n{strategy}" in messages[1]["content"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
