"""
Test cases for openai_compatible router endpoints - comprehensive coverage for all 4 endpoints
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from httpx import AsyncClient
import json
from datetime import datetime


@pytest.fixture
def mock_verified_user():
    return MagicMock(
        id="user123",
        name="Test User",
        email="user@example.com",
        role="user"
    )


@pytest.fixture
def mock_chat_request():
    return {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello, how are you?"}
        ],
        "temperature": 0.7,
        "max_tokens": 150,
        "stream": False
    }


@pytest.fixture
def mock_models_list():
    return [
        {
            "id": "gpt-3.5-turbo",
            "object": "model",
            "created": 1677610602,
            "owned_by": "openai"
        },
        {
            "id": "gpt-4",
            "object": "model",
            "created": 1677610602,
            "owned_by": "openai"
        },
        {
            "id": "claude-3-sonnet",
            "object": "model",
            "created": 1677610602,
            "owned_by": "anthropic"
        }
    ]


class TestListModels:
    """Test list models endpoint"""
    
    async def test_list_models(self, async_client: AsyncClient, mock_verified_user, mock_models_list):
        """Test GET /v1/models endpoint"""
        with patch("open_webui.routers.openai_compatible.get_verified_user", return_value=mock_verified_user):
            response = await async_client.get("/api/v1/openai/v1/models")
            assert response.status_code == 200
            data = response.json()
            assert data["object"] == "list"
            assert "data" in data
            assert len(data["data"]) >= 3
            # Check if default models are present
            model_ids = [model["id"] for model in data["data"]]
            assert "gpt-3.5-turbo" in model_ids
            assert "gpt-4" in model_ids
    
    async def test_list_models_unauthorized(self, async_client: AsyncClient):
        """Test GET /v1/models endpoint without authentication"""
        with patch("open_webui.routers.openai_compatible.get_verified_user", side_effect=Exception("Unauthorized")):
            response = await async_client.get("/api/v1/openai/v1/models")
            assert response.status_code in [401, 403, 500]


class TestChatCompletions:
    """Test chat completions endpoint"""
    
    async def test_create_chat_completion_non_streaming(self, async_client: AsyncClient, mock_verified_user, mock_chat_request):
        """Test POST /v1/chat/completions endpoint (non-streaming)"""
        with patch("open_webui.routers.openai_compatible.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.openai_compatible.generate_openai_response") as mock_generate:
                mock_generate.return_value = "I'm doing well, thank you for asking!"
                
                response = await async_client.post(
                    "/api/v1/openai/v1/chat/completions",
                    json=mock_chat_request
                )
                assert response.status_code == 200
                data = response.json()
                assert data["object"] == "chat.completion"
                assert "id" in data
                assert "choices" in data
                assert len(data["choices"]) == 1
                assert data["choices"][0]["message"]["role"] == "assistant"
                assert data["choices"][0]["message"]["content"] == "I'm doing well, thank you for asking!"
                assert data["model"] == "gpt-3.5-turbo"
    
    async def test_create_chat_completion_with_tools(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /v1/chat/completions with tool calls"""
        request_with_tools = {
            "model": "gpt-4",
            "messages": [
                {"role": "user", "content": "Search for information about Python"}
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "search_knowledge",
                        "description": "Search knowledge base",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string"}
                            }
                        }
                    }
                }
            ],
            "stream": False
        }
        
        with patch("open_webui.routers.openai_compatible.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.openai_compatible.should_use_tool", return_value=True):
                with patch("open_webui.routers.openai_compatible.execute_tool_call") as mock_execute:
                    mock_execute.return_value = {"result": "Python is a programming language"}
                    with patch("open_webui.routers.openai_compatible.generate_openai_response") as mock_generate:
                        mock_generate.return_value = "Python is a high-level programming language."
                        
                        response = await async_client.post(
                            "/api/v1/openai/v1/chat/completions",
                            json=request_with_tools
                        )
                        assert response.status_code == 200
                        data = response.json()
                        assert "choices" in data
    
    async def test_create_chat_completion_streaming(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /v1/chat/completions endpoint (streaming)"""
        streaming_request = {
            "model": "gpt-3.5-turbo",
            "messages": [{"role": "user", "content": "Tell me a story"}],
            "stream": True
        }
        
        with patch("open_webui.routers.openai_compatible.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.openai_compatible.generate_openai_stream_response") as mock_stream:
                async def mock_generator():
                    yield "Once upon a time"
                    yield " there was a"
                    yield " brave knight."
                
                mock_stream.return_value = mock_generator()
                
                response = await async_client.post(
                    "/api/v1/openai/v1/chat/completions",
                    json=streaming_request
                )
                assert response.status_code == 200
                # For streaming responses, we get SSE format
                assert response.headers.get("content-type") == "text/event-stream"
    
    async def test_create_chat_completion_invalid_model(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /v1/chat/completions with invalid model"""
        invalid_request = {
            "model": "invalid-model",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": False
        }
        
        with patch("open_webui.routers.openai_compatible.get_verified_user", return_value=mock_verified_user):
            response = await async_client.post(
                "/api/v1/openai/v1/chat/completions",
                json=invalid_request
            )
            # Should still work as we handle any model name
            assert response.status_code in [200, 400]
    
    async def test_create_chat_completion_empty_messages(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /v1/chat/completions with empty messages"""
        empty_request = {
            "model": "gpt-3.5-turbo",
            "messages": [],
            "stream": False
        }
        
        with patch("open_webui.routers.openai_compatible.get_verified_user", return_value=mock_verified_user):
            response = await async_client.post(
                "/api/v1/openai/v1/chat/completions",
                json=empty_request
            )
            assert response.status_code in [400, 422]


class TestToolExecution:
    """Test tool execution endpoints"""
    
    async def test_execute_tool_call(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /v1/chat/completions/tools endpoint"""
        with patch("open_webui.routers.openai_compatible.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.openai_compatible.search_knowledge_base") as mock_search:
                mock_search.return_value = [
                    {"content": "Python is a programming language", "score": 0.95},
                    {"content": "Python was created by Guido van Rossum", "score": 0.88}
                ]
                
                response = await async_client.post(
                    "/api/v1/openai/v1/chat/completions/tools",
                    params={
                        "tool_name": "search_knowledge",
                        "arguments": {"query": "Python programming"}
                    }
                )
                assert response.status_code == 200
                data = response.json()
                assert "results" in data
                assert len(data["results"]) == 2
    
    async def test_execute_tool_call_analyze_log(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /v1/chat/completions/tools for log analysis"""
        with patch("open_webui.routers.openai_compatible.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.openai_compatible.analyze_log_content") as mock_analyze:
                mock_analyze.return_value = {
                    "error_count": 5,
                    "warning_count": 12,
                    "issues": ["Connection timeout", "Memory leak detected"]
                }
                
                response = await async_client.post(
                    "/api/v1/openai/v1/chat/completions/tools",
                    params={
                        "tool_name": "analyze_log",
                        "arguments": {"log_content": "2024-01-01 ERROR: Connection failed"}
                    }
                )
                assert response.status_code == 200
                data = response.json()
                assert "error_count" in data
    
    async def test_execute_tool_call_unsupported_tool(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /v1/chat/completions/tools with unsupported tool"""
        with patch("open_webui.routers.openai_compatible.get_verified_user", return_value=mock_verified_user):
            response = await async_client.post(
                "/api/v1/openai/v1/chat/completions/tools",
                params={
                    "tool_name": "unsupported_tool",
                    "arguments": {}
                }
            )
            assert response.status_code == 400
            assert "不支持的工具" in response.json()["error"]
    
    async def test_list_available_tools(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /v1/chat/completions/tools endpoint"""
        with patch("open_webui.routers.openai_compatible.get_verified_user", return_value=mock_verified_user):
            response = await async_client.get("/api/v1/openai/v1/chat/completions/tools")
            assert response.status_code == 200
            data = response.json()
            assert "tools" in data
            assert len(data["tools"]) > 0
            
            # Check for expected tools
            tool_names = [tool["name"] for tool in data["tools"]]
            assert "search_knowledge" in tool_names
            assert "analyze_log" in tool_names
            assert "get_vendor_commands" in tool_names
            
            # Check tool structure
            for tool in data["tools"]:
                assert "name" in tool
                assert "description" in tool
                assert "parameters" in tool


class TestErrorHandling:
    """Test error handling for OpenAI compatible endpoints"""
    
    async def test_chat_completion_llm_error(self, async_client: AsyncClient, mock_verified_user, mock_chat_request):
        """Test POST /v1/chat/completions with LLM error"""
        with patch("open_webui.routers.openai_compatible.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.openai_compatible.generate_openai_response", side_effect=Exception("LLM service error")):
                response = await async_client.post(
                    "/api/v1/openai/v1/chat/completions",
                    json=mock_chat_request
                )
                assert response.status_code == 500
                data = response.json()
                assert "error" in data
                assert "message" in data["error"]
    
    async def test_tool_execution_error(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /v1/chat/completions/tools with execution error"""
        with patch("open_webui.routers.openai_compatible.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.openai_compatible.search_knowledge_base", side_effect=Exception("Search failed")):
                response = await async_client.post(
                    "/api/v1/openai/v1/chat/completions/tools",
                    params={
                        "tool_name": "search_knowledge",
                        "arguments": {"query": "test"}
                    }
                )
                assert response.status_code in [400, 500]
                data = response.json()
                assert "error" in data
