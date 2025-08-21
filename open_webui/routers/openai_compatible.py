"""
OpenAI兼容层接口

提供与OpenAI API兼容的接口，支持：
- /v1/chat/completions
- /v1/models
- 流式响应
- 工具调用
"""

import json
import time
import uuid
from typing import List, Dict, Any, Optional, AsyncGenerator
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import logging

from open_webui.utils.auth import get_verified_user
from open_webui.services.log_parsing_service import log_parsing_service
from open_webui.routers.knowledge_migrated import search_knowledge
from open_webui.retrieval.vector.main import get_retrieval_vector_db

logger = logging.getLogger(__name__)
router = APIRouter()

# OpenAI兼容的数据模型
class ChatMessage(BaseModel):
    role: str = Field(..., description="消息角色: system, user, assistant, tool")
    content: Optional[str] = Field(None, description="消息内容")
    name: Optional[str] = Field(None, description="消息发送者名称")
    tool_calls: Optional[List[Dict[str, Any]]] = Field(None, description="工具调用")
    tool_call_id: Optional[str] = Field(None, description="工具调用ID")

class ChatCompletionRequest(BaseModel):
    model: str = Field(..., description="模型名称")
    messages: List[ChatMessage] = Field(..., description="对话消息列表")
    temperature: Optional[float] = Field(0.7, description="温度参数")
    max_tokens: Optional[int] = Field(None, description="最大token数")
    stream: Optional[bool] = Field(False, description="是否流式响应")
    tools: Optional[List[Dict[str, Any]]] = Field(None, description="可用工具列表")
    tool_choice: Optional[str] = Field("auto", description="工具选择策略")

class ChatCompletionResponse(BaseModel):
    id: str = Field(..., description="响应ID")
    object: str = Field("chat.completion", description="对象类型")
    created: int = Field(..., description="创建时间戳")
    model: str = Field(..., description="使用的模型")
    choices: List[Dict[str, Any]] = Field(..., description="响应选择列表")
    usage: Dict[str, int] = Field(..., description="token使用统计")

class ModelInfo(BaseModel):
    id: str = Field(..., description="模型ID")
    object: str = Field("model", description="对象类型")
    created: int = Field(..., description="创建时间")
    owned_by: str = Field("open-webui", description="所有者")

# 可用的工具定义
AVAILABLE_TOOLS = {
    "log_parsing": {
        "type": "function",
        "function": {
            "name": "parse_network_log",
            "description": "解析网络设备日志，识别故障和异常",
            "parameters": {
                "type": "object",
                "properties": {
                    "log_content": {
                        "type": "string",
                        "description": "要解析的日志内容"
                    },
                    "log_type": {
                        "type": "string",
                        "description": "日志类型，如：华为交换机、思科路由器等"
                    },
                    "vendor": {
                        "type": "string",
                        "description": "设备厂商：华为、思科、Juniper等"
                    }
                },
                "required": ["log_content", "log_type", "vendor"]
            }
        }
    },
    "knowledge_search": {
        "type": "function",
        "function": {
            "name": "search_knowledge_base",
            "description": "搜索知识库获取相关技术文档和解决方案",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索查询内容"
                    },
                    "vendor": {
                        "type": "string",
                        "description": "设备厂商过滤条件"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "返回结果数量",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        }
    }
}

@router.get("/v1/models")
async def list_models(user=Depends(get_verified_user)):
    """列出可用模型"""
    models = [
        ModelInfo(
            id="network-expert-v1",
            created=int(time.time()),
            owned_by="open-webui"
        ),
        ModelInfo(
            id="log-analyzer-v1", 
            created=int(time.time()),
            owned_by="open-webui"
        )
    ]
    
    return {
        "object": "list",
        "data": [model.dict() for model in models]
    }

@router.post("/v1/chat/completions")
async def create_chat_completion(
    request: ChatCompletionRequest,
    http_request: Request,
    user=Depends(get_verified_user)
):
    """创建聊天完成"""
    try:
        # 验证模型
        if request.model not in ["network-expert-v1", "log-analyzer-v1"]:
            raise HTTPException(status_code=400, detail=f"Model {request.model} not found")
        
        # 处理对话
        if request.stream:
            return StreamingResponse(
                stream_chat_completion(request, user),
                media_type="text/plain"
            )
        else:
            return await generate_chat_completion(request, user)
            
    except Exception as e:
        logger.error(f"Chat completion error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def generate_chat_completion(request: ChatCompletionRequest, user) -> ChatCompletionResponse:
    """生成聊天完成响应"""
    
    # 获取最后一条用户消息
    user_message = None
    for msg in reversed(request.messages):
        if msg.role == "user":
            user_message = msg
            break
    
    if not user_message or not user_message.content:
        raise HTTPException(status_code=400, detail="No user message found")
    
    # 分析用户意图并决定是否使用工具
    response_content = ""
    tool_calls = []
    
    # 检查是否需要日志解析
    if any(keyword in user_message.content.lower() for keyword in ["日志", "log", "错误", "error", "故障"]):
        # 尝试提取日志内容进行解析
        if request.tools and any(tool.get("function", {}).get("name") == "parse_network_log" for tool in request.tools):
            tool_call_id = f"call_{uuid.uuid4().hex[:8]}"
            tool_calls.append({
                "id": tool_call_id,
                "type": "function",
                "function": {
                    "name": "parse_network_log",
                    "arguments": json.dumps({
                        "log_content": user_message.content,
                        "log_type": "系统日志",
                        "vendor": "通用"
                    })
                }
            })
    
    # 检查是否需要知识搜索
    elif any(keyword in user_message.content.lower() for keyword in ["如何", "怎么", "配置", "解决", "排查"]):
        if request.tools and any(tool.get("function", {}).get("name") == "search_knowledge_base" for tool in request.tools):
            tool_call_id = f"call_{uuid.uuid4().hex[:8]}"
            tool_calls.append({
                "id": tool_call_id,
                "type": "function", 
                "function": {
                    "name": "search_knowledge_base",
                    "arguments": json.dumps({
                        "query": user_message.content,
                        "top_k": 3
                    })
                }
            })
    
    # 如果没有工具调用，生成普通响应
    if not tool_calls:
        if request.model == "log-analyzer-v1":
            response_content = "我是网络日志分析专家，可以帮您分析网络设备日志、识别故障和提供解决方案。请提供需要分析的日志内容。"
        else:
            response_content = "我是网络运维专家，可以帮您解决网络配置、故障排查、设备管理等问题。请告诉我您遇到的具体问题。"
    
    # 构建响应
    choice = {
        "index": 0,
        "message": {
            "role": "assistant",
            "content": response_content
        },
        "finish_reason": "tool_calls" if tool_calls else "stop"
    }
    
    if tool_calls:
        choice["message"]["tool_calls"] = tool_calls
    
    return ChatCompletionResponse(
        id=f"chatcmpl-{uuid.uuid4().hex[:8]}",
        created=int(time.time()),
        model=request.model,
        choices=[choice],
        usage={
            "prompt_tokens": len(user_message.content) // 4,  # 粗略估算
            "completion_tokens": len(response_content) // 4,
            "total_tokens": (len(user_message.content) + len(response_content)) // 4
        }
    )

async def stream_chat_completion(request: ChatCompletionRequest, user) -> AsyncGenerator[str, None]:
    """流式聊天完成响应"""
    
    # 获取完整响应
    full_response = await generate_chat_completion(request, user)
    
    # 转换为流式格式
    chunk_id = full_response.id
    
    # 发送开始chunk
    start_chunk = {
        "id": chunk_id,
        "object": "chat.completion.chunk",
        "created": full_response.created,
        "model": full_response.model,
        "choices": [{
            "index": 0,
            "delta": {"role": "assistant"},
            "finish_reason": None
        }]
    }
    yield f"data: {json.dumps(start_chunk)}\n\n"
    
    # 如果有工具调用，发送工具调用chunk
    if full_response.choices[0].get("message", {}).get("tool_calls"):
        tool_calls = full_response.choices[0]["message"]["tool_calls"]
        tool_chunk = {
            "id": chunk_id,
            "object": "chat.completion.chunk", 
            "created": full_response.created,
            "model": full_response.model,
            "choices": [{
                "index": 0,
                "delta": {"tool_calls": tool_calls},
                "finish_reason": None
            }]
        }
        yield f"data: {json.dumps(tool_chunk)}\n\n"
    
    # 发送内容chunk（如果有）
    content = full_response.choices[0]["message"].get("content", "")
    if content:
        # 分块发送内容
        chunk_size = 10
        for i in range(0, len(content), chunk_size):
            chunk_content = content[i:i + chunk_size]
            content_chunk = {
                "id": chunk_id,
                "object": "chat.completion.chunk",
                "created": full_response.created,
                "model": full_response.model,
                "choices": [{
                    "index": 0,
                    "delta": {"content": chunk_content},
                    "finish_reason": None
                }]
            }
            yield f"data: {json.dumps(content_chunk)}\n\n"
    
    # 发送结束chunk
    end_chunk = {
        "id": chunk_id,
        "object": "chat.completion.chunk",
        "created": full_response.created,
        "model": full_response.model,
        "choices": [{
            "index": 0,
            "delta": {},
            "finish_reason": full_response.choices[0]["finish_reason"]
        }]
    }
    yield f"data: {json.dumps(end_chunk)}\n\n"
    yield "data: [DONE]\n\n"

@router.post("/v1/chat/completions/tools")
async def execute_tool_call(
    tool_name: str,
    arguments: Dict[str, Any],
    user=Depends(get_verified_user)
):
    """执行工具调用"""
    try:
        if tool_name == "parse_network_log":
            return await execute_log_parsing_tool(arguments, user)
        elif tool_name == "search_knowledge_base":
            return await execute_knowledge_search_tool(arguments, user)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown tool: {tool_name}")
            
    except Exception as e:
        logger.error(f"Tool execution error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def execute_log_parsing_tool(arguments: Dict[str, Any], user) -> Dict[str, Any]:
    """执行日志解析工具"""
    log_content = arguments.get("log_content", "")
    log_type = arguments.get("log_type", "系统日志")
    vendor = arguments.get("vendor", "通用")
    
    if not log_content:
        return {"error": "日志内容不能为空"}
    
    try:
        # 调用日志解析服务
        result = log_parsing_service.parse_log(
            log_type=log_type,
            vendor=vendor,
            log_content=log_content
        )
        
        # 格式化结果
        formatted_result = {
            "summary": result.get("summary", ""),
            "anomalies_count": len(result.get("anomalies", [])),
            "high_severity_issues": len([a for a in result.get("anomalies", []) if a.get("severity") == "high"]),
            "suggested_actions": result.get("suggestedActions", []),
            "key_findings": [
                f"检测到 {len(result.get('anomalies', []))} 个异常",
                f"日志总行数: {result.get('logMetrics', {}).get('totalLines', 0)}",
                f"时间范围: {result.get('logMetrics', {}).get('timeRange', {}).get('start', '未知')} - {result.get('logMetrics', {}).get('timeRange', {}).get('end', '未知')}"
            ]
        }
        
        return formatted_result
        
    except Exception as e:
        return {"error": f"日志解析失败: {str(e)}"}

async def execute_knowledge_search_tool(arguments: Dict[str, Any], user) -> Dict[str, Any]:
    """执行知识搜索工具"""
    query = arguments.get("query", "")
    vendor = arguments.get("vendor")
    top_k = arguments.get("top_k", 5)
    
    if not query:
        return {"error": "搜索查询不能为空"}
    
    try:
        # 获取向量数据库
        vector_db = get_retrieval_vector_db()
        if not vector_db:
            return {"error": "知识库暂时不可用"}
        
        # 构建搜索过滤器
        filters = {}
        if vendor:
            filters["vendor"] = vendor
        
        # 执行搜索
        search_results = vector_db.search(
            query=query,
            limit=top_k,
            filters=filters
        )
        
        # 格式化结果
        formatted_results = []
        for result in search_results:
            formatted_results.append({
                "content": result.get("content", "")[:200] + "..." if len(result.get("content", "")) > 200 else result.get("content", ""),
                "source": result.get("metadata", {}).get("source", "未知"),
                "relevance_score": round(result.get("score", 0), 3)
            })
        
        return {
            "results": formatted_results,
            "total_found": len(search_results),
            "query": query,
            "search_filters": filters
        }
        
    except Exception as e:
        return {"error": f"知识搜索失败: {str(e)}"}

@router.get("/v1/chat/completions/tools")
async def list_available_tools(user=Depends(get_verified_user)):
    """列出可用工具"""
    return {
        "tools": list(AVAILABLE_TOOLS.values()),
        "total_count": len(AVAILABLE_TOOLS)
    }
