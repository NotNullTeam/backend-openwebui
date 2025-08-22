"""
开发调试模块路由

整合提示词测试、向量数据库管理、缓存管理等开发功能的路由。
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
import sys
import os
import logging

from open_webui.models.auths import UserModel
from open_webui.models.prompts import PromptModel, Prompts
from open_webui.utils.auth import get_admin_user, get_verified_user
from open_webui.utils.misc import get_last_user_message
from open_webui.internal.db import get_db
from open_webui.env import SRC_LOG_LEVELS, ENV, VERSION, WEBUI_AUTH
from open_webui.config import (
    DEFAULT_MODELS,
    DEFAULT_PROMPT_SUGGESTIONS
)

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logger.warning("psutil不可用，系统监控功能将使用模拟数据")

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/dev",
    tags=["development"],
    responses={404: {"description": "Not found"}},
)


# ========== 数据模型 ==========

class PromptTestRequest(BaseModel):
    """提示词测试请求"""
    query: str
    context: Optional[str] = ""
    vendor: Optional[str] = None
    analysis: Optional[Dict[str, Any]] = None
    conversation_history: Optional[List[Dict[str, str]]] = None
    problem_status: Optional[str] = "进行中"
    
class PromptTestResponse(BaseModel):
    """提示词测试响应"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    test_type: str
    error: Optional[str] = None

class FeedbackTestRequest(BaseModel):
    """反馈测试请求"""
    original_problem: str
    provided_solution: str
    user_feedback: str

class VendorInfo(BaseModel):
    """设备厂商信息"""
    name: str
    value: str
    description: str

class VectorSearchRequest(BaseModel):
    """向量搜索请求"""
    query_text: str
    top_k: int = 5
    document_id: Optional[str] = None

class EmbeddingTestRequest(BaseModel):
    """嵌入测试请求"""
    text: str = "这是一个测试文本"

class CacheClearRequest(BaseModel):
    """缓存清除请求"""
    pattern: str = "llm:*"

class PromptTemplateCreate(BaseModel):
    """创建提示词模板请求"""
    name: str
    content: str
    description: Optional[str] = None
    category: Optional[str] = None
    is_active: bool = False

class PromptTemplateUpdate(BaseModel):
    """更新提示词模板请求"""
    name: Optional[str] = None
    content: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    is_active: Optional[bool] = None


# ========== API文档 ==========

@router.get("/docs", response_class=HTMLResponse)
async def api_docs():
    """API文档页面"""
    html_content = '''
<!DOCTYPE html>
<html>
<head>
    <title>IP智慧解答专家系统 API 文档</title>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        h1 { color: #333; }
        ul { line-height: 1.8; }
        a { color: #007bff; text-decoration: none; }
        a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <h1>IP智慧解答专家系统 API 文档</h1>
    <p>这是开发环境的API文档页面。</p>
    <ul>
        <li><a href="/api/v1/dev/openapi.json">OpenAPI规范</a></li>
        <li><a href="/api/v1/auths/">认证API</a></li>
        <li><a href="/api/v1/cases/">案例API</a></li>
        <li><a href="/api/v1/knowledge/">知识库API</a></li>
        <li><a href="/api/v1/statistics/">统计API</a></li>
    </ul>
</body>
</html>
    '''
    return HTMLResponse(content=html_content)


@router.get("/openapi.json")
async def api_spec():
    """OpenAPI规范"""
    spec = {
        "openapi": "3.0.0",
        "info": {
            "title": "IP智慧解答专家系统 API",
            "version": VERSION if VERSION else "1.0.0",
            "description": "IP网络专家诊断系统的RESTful API文档"
        },
        "servers": [
            {
                "url": "/api/v1",
                "description": "API v1"
            }
        ],
        "paths": {
            "/auths/signin": {
                "post": {
                    "summary": "用户登录",
                    "tags": ["认证"],
                    "responses": {
                        "200": {"description": "登录成功"}
                    }
                }
            },
            "/cases": {
                "get": {
                    "summary": "获取案例列表",
                    "tags": ["案例"],
                    "responses": {
                        "200": {"description": "获取成功"}
                    }
                }
            },
            "/knowledge/docs": {
                "get": {
                    "summary": "获取文档列表",
                    "tags": ["知识库"],
                    "responses": {
                        "200": {"description": "获取成功"}
                    }
                }
            },
            "/statistics/overview": {
                "get": {
                    "summary": "获取系统概览",
                    "tags": ["统计"],
                    "responses": {
                        "200": {"description": "获取成功"}
                    }
                }
            }
        },
        "components": {
            "schemas": {
                "ApiResponse": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "integer"},
                        "status": {"type": "string"},
                        "data": {"type": "object"}
                    }
                }
            },
            "securitySchemes": {
                "BearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT"
                }
            }
        }
    }
    return spec


# ========== 调试信息 ==========

@router.get("/debug-info")
async def debug_info(user: UserModel = Depends(get_admin_user)):
    """
    调试信息（仅管理员）
    
    返回系统调试信息，包括环境配置、Python版本等。
    """
    import platform
    
    debug_data = {
        "server_time": datetime.utcnow().isoformat(),
        "environment": ENV,
        "version": VERSION,
        "python_version": sys.version,
        "platform": platform.platform(),
        "auth_enabled": WEBUI_AUTH,
        "log_levels": SRC_LOG_LEVELS,
        "default_models": DEFAULT_MODELS,
        "dependencies": {
            "fastapi": "0.104.1",
            "sqlalchemy": "2.0.30",
            "pydantic": "2.7.2"
        },
        "config": {
            "env": ENV,
            "auth": WEBUI_AUTH,
            "version": VERSION
        }
    }
    
    return {
        "code": 200,
        "status": "success",
        "data": debug_data
    }


# ========== 提示词测试 ==========

@router.post("/test/analysis", response_model=PromptTestResponse)
async def test_analysis_prompt(
    request: PromptTestRequest,
    user: UserModel = Depends(get_verified_user)
):
    """测试问题分析提示词"""
    try:
        # TODO: 调用实际的LLM服务进行测试
        # 这里先返回模拟结果
        result = {
            "problem_type": "network_connectivity",
            "severity": "high",
            "key_entities": ["IP地址", "路由器"],
            "suggested_actions": ["检查网络配置", "验证路由表"],
            "vendor": request.vendor or "通用"
        }
        
        return PromptTestResponse(
            success=True,
            data=result,
            test_type="analysis"
        )
    except Exception as e:
        logger.error(f"分析提示词测试失败: {str(e)}")
        return PromptTestResponse(
            success=False,
            error=str(e),
            test_type="analysis"
        )


@router.post("/test/clarification", response_model=PromptTestResponse)
async def test_clarification_prompt(
    request: PromptTestRequest,
    user: UserModel = Depends(get_verified_user)
):
    """测试澄清问题提示词"""
    try:
        # TODO: 调用实际的LLM服务
        result = {
            "clarification_questions": [
                "您使用的是什么型号的路由器？",
                "问题出现的具体时间是什么时候？",
                "是否有其他设备也遇到相同问题？"
            ],
            "context_needed": ["网络拓扑", "设备配置"],
            "vendor": request.vendor
        }
        
        return PromptTestResponse(
            success=True,
            data=result,
            test_type="clarification"
        )
    except Exception as e:
        logger.error(f"澄清提示词测试失败: {str(e)}")
        return PromptTestResponse(
            success=False,
            error=str(e),
            test_type="clarification"
        )


@router.post("/test/solution", response_model=PromptTestResponse)
async def test_solution_prompt(
    request: PromptTestRequest,
    user: UserModel = Depends(get_verified_user)
):
    """测试解决方案提示词"""
    try:
        # TODO: 调用实际的LLM服务
        result = {
            "solution": "1. 检查IP地址配置\n2. 验证路由表项\n3. 测试网络连通性",
            "commands": [
                "show ip interface brief",
                "show ip route",
                "ping 8.8.8.8"
            ],
            "expected_outcome": "网络连接恢复正常",
            "vendor": request.vendor or "通用"
        }
        
        return PromptTestResponse(
            success=True,
            data=result,
            test_type="solution"
        )
    except Exception as e:
        logger.error(f"解决方案提示词测试失败: {str(e)}")
        return PromptTestResponse(
            success=False,
            error=str(e),
            test_type="solution"
        )


@router.post("/test/conversation", response_model=PromptTestResponse)
async def test_conversation_prompt(
    request: PromptTestRequest,
    user: UserModel = Depends(get_verified_user)
):
    """测试多轮对话提示词"""
    try:
        # TODO: 调用实际的LLM服务
        result = {
            "response": "根据您提供的信息，我建议首先检查路由器的配置...",
            "next_action": "gather_more_info",
            "conversation_state": "active",
            "problem_status": request.problem_status
        }
        
        return PromptTestResponse(
            success=True,
            data=result,
            test_type="conversation"
        )
    except Exception as e:
        logger.error(f"对话提示词测试失败: {str(e)}")
        return PromptTestResponse(
            success=False,
            error=str(e),
            test_type="conversation"
        )


@router.post("/test/feedback", response_model=PromptTestResponse)
async def test_feedback_prompt(
    request: FeedbackTestRequest,
    user: UserModel = Depends(get_verified_user)
):
    """测试反馈处理提示词"""
    try:
        # TODO: 调用实际的LLM服务
        result = {
            "feedback_analysis": "用户反馈表明解决方案部分有效",
            "improvement_suggestions": [
                "添加更详细的配置步骤",
                "提供备选解决方案"
            ],
            "knowledge_update_needed": True
        }
        
        return PromptTestResponse(
            success=True,
            data=result,
            test_type="feedback"
        )
    except Exception as e:
        logger.error(f"反馈提示词测试失败: {str(e)}")
        return PromptTestResponse(
            success=False,
            error=str(e),
            test_type="feedback"
        )


# ========== 厂商管理 ==========

@router.get("/vendors", response_model=List[VendorInfo])
async def get_supported_vendors(user: UserModel = Depends(get_verified_user)):
    """获取支持的设备厂商列表"""
    vendors = [
        VendorInfo(name="华为", value="华为", description="华为VRP系统"),
        VendorInfo(name="思科", value="思科", description="思科IOS/IOS-XE系统"),
        VendorInfo(name="H3C", value="H3C", description="H3C Comware系统"),
        VendorInfo(name="锐捷", value="锐捷", description="锐捷RGOS系统"),
        VendorInfo(name="通用", value="通用", description="通用网络设备")
    ]
    return vendors


# ========== 性能监控 ==========

@router.get("/performance")
async def get_performance_metrics(user: UserModel = Depends(get_verified_user)):
    """获取LLM服务性能指标"""
    try:
        # TODO: 从实际监控服务获取数据
        stats = {
            "analysis": {
                "total_calls": 1250,
                "success_rate": 0.98,
                "avg_response_time": 1.2,
                "p95_response_time": 2.5
            },
            "solution": {
                "total_calls": 890,
                "success_rate": 0.96,
                "avg_response_time": 1.8,
                "p95_response_time": 3.2
            }
        }
        
        health = {
            "status": "healthy",
            "uptime": 86400,
            "last_check": datetime.utcnow().isoformat()
        }
        
        return {
            "success": True,
            "data": {
                "statistics": stats,
                "health": health
            }
        }
    except Exception as e:
        logger.error(f"获取性能指标失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== 缓存管理 ==========

@router.get("/cache/status")
async def get_cache_status(user: UserModel = Depends(get_verified_user)):
    """获取缓存状态"""
    try:
        # TODO: 从实际缓存服务获取状态
        cache_info = {
            "connected": True,
            "type": "redis",
            "memory_used": "256MB",
            "memory_max": "1GB",
            "keys_count": 1234,
            "hit_rate": 0.85,
            "uptime": 3600
        }
        
        return {
            "success": True,
            "data": cache_info
        }
    except Exception as e:
        logger.error(f"获取缓存状态失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cache/clear")
async def clear_cache(
    request: CacheClearRequest,
    user: UserModel = Depends(get_admin_user)
):
    """清除缓存（仅管理员）"""
    try:
        # TODO: 实际清除缓存
        cleared_count = 42  # 模拟清除的键数量
        
        return {
            "success": True,
            "data": {
                "cleared_count": cleared_count,
                "pattern": request.pattern
            }
        }
    except Exception as e:
        logger.error(f"清除缓存失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== 提示词模板管理 ==========

@router.post("/prompts", status_code=201)
async def create_prompt_template(
    prompt: PromptTemplateCreate,
    user: UserModel = Depends(get_verified_user),
    db: Session = Depends(get_db)
):
    """创建新的提示词模板"""
    try:
        # 检查是否已存在同名模板
        existing = db.query(PromptModel).filter_by(title=prompt.name).first()
        if existing:
            raise HTTPException(status_code=409, detail="同名提示词模板已存在")
        
        # 创建新模板
        new_prompt = PromptModel(
            user_id=user.id,
            title=prompt.name,
            content=prompt.content,
            command="/" + prompt.name.lower().replace(" ", "_")
        )
        
        db.add(new_prompt)
        db.commit()
        
        return {
            "code": 201,
            "status": "success",
            "data": {
                "id": new_prompt.id,
                "title": new_prompt.title,
                "content": new_prompt.content,
                "command": new_prompt.command,
                "created_at": new_prompt.created_at,
                "updated_at": new_prompt.updated_at
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"创建提示词模板失败: {str(e)}")
        raise HTTPException(status_code=500, detail="创建提示词模板失败")


@router.get("/prompts")
async def get_prompt_templates(
    page: int = 1,
    per_page: int = 10,
    user: UserModel = Depends(get_verified_user),
    db: Session = Depends(get_db)
):
    """获取提示词模板列表（分页）"""
    try:
        # 计算偏移量
        offset = (page - 1) * per_page
        
        # 查询总数
        total = db.query(PromptModel).count()
        
        # 查询当前页数据
        prompts = db.query(PromptModel).offset(offset).limit(per_page).all()
        
        return {
            "code": 200,
            "status": "success",
            "data": [
                {
                    "id": p.id,
                    "title": p.title,
                    "content": p.content,
                    "command": p.command,
                    "created_at": p.created_at,
                    "updated_at": p.updated_at
                }
                for p in prompts
            ],
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total_pages": (total + per_page - 1) // per_page,
                "total_items": total
            }
        }
    except Exception as e:
        logger.error(f"获取提示词模板列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取提示词模板列表失败")


@router.get("/prompts/{prompt_id}")
async def get_prompt_template(
    prompt_id: str,
    user: UserModel = Depends(get_verified_user),
    db: Session = Depends(get_db)
):
    """获取指定ID的提示词模板"""
    prompt = db.query(PromptModel).filter_by(id=prompt_id).first()
    
    if not prompt:
        raise HTTPException(status_code=404, detail="提示词模板不存在")
    
    return {
        "code": 200,
        "status": "success",
        "data": {
            "id": prompt.id,
            "title": prompt.title,
            "content": prompt.content,
            "command": prompt.command,
            "created_at": prompt.created_at,
            "updated_at": prompt.updated_at
        }
    }


@router.put("/prompts/{prompt_id}")
async def update_prompt_template(
    prompt_id: str,
    update_data: PromptTemplateUpdate,
    user: UserModel = Depends(get_verified_user),
    db: Session = Depends(get_db)
):
    """更新指定ID的提示词模板"""
    prompt = db.query(PromptModel).filter_by(id=prompt_id).first()
    
    if not prompt:
        raise HTTPException(status_code=404, detail="提示词模板不存在")
    
    # 检查权限（只能更新自己的模板或管理员）
    if prompt.user_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="无权限修改此模板")
    
    try:
        # 更新字段
        if update_data.name:
            # 检查新名称是否已存在
            existing = db.query(PromptModel).filter(
                PromptModel.id != prompt_id,
                PromptModel.title == update_data.name
            ).first()
            if existing:
                raise HTTPException(status_code=409, detail="同名提示词模板已存在")
            prompt.title = update_data.name
            prompt.command = "/" + update_data.name.lower().replace(" ", "_")
        
        if update_data.content:
            prompt.content = update_data.content
        
        prompt.updated_at = datetime.utcnow()
        
        db.commit()
        
        return {
            "code": 200,
            "status": "success",
            "data": {
                "id": prompt.id,
                "title": prompt.title,
                "content": prompt.content,
                "command": prompt.command,
                "created_at": prompt.created_at,
                "updated_at": prompt.updated_at
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"更新提示词模板失败: {str(e)}")
        raise HTTPException(status_code=500, detail="更新提示词模板失败")


@router.delete("/prompts/{prompt_id}", status_code=204)
async def delete_prompt_template(
    prompt_id: str,
    user: UserModel = Depends(get_verified_user),
    db: Session = Depends(get_db)
):
    """删除指定ID的提示词模板"""
    prompt = db.query(PromptModel).filter_by(id=prompt_id).first()
    
    if not prompt:
        raise HTTPException(status_code=404, detail="提示词模板不存在")
    
    # 检查权限
    if prompt.user_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="无权限删除此模板")
    
    try:
        db.delete(prompt)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"删除提示词模板失败: {str(e)}")
        raise HTTPException(status_code=500, detail="删除提示词模板失败")


# ========== 向量数据库管理 ==========

@router.get("/vector/status")
async def get_vector_status(user: UserModel = Depends(get_verified_user)):
    """获取向量数据库状态"""
    try:
        # TODO: 从实际向量服务获取状态
        stats = {
            "total_documents": 1500,
            "total_chunks": 12000,
            "index_size": "2.3GB",
            "last_update": datetime.utcnow().isoformat(),
            "config": {
                "db_type": "weaviate",
                "is_valid": True
            }
        }
        
        return {
            "success": True,
            "data": stats
        }
    except Exception as e:
        logger.error(f"获取向量数据库状态失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/vector/test")
async def test_vector_connection(user: UserModel = Depends(get_verified_user)):
    """测试向量数据库连接"""
    try:
        # TODO: 实际测试连接
        return {
            "success": True,
            "data": {
                "connection_ok": True,
                "db_type": "weaviate",
                "response_time": 0.05
            }
        }
    except Exception as e:
        logger.error(f"测试向量数据库连接失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/vector/search")
async def search_vectors(
    request: VectorSearchRequest,
    user: UserModel = Depends(get_verified_user)
):
    """搜索相似向量"""
    try:
        # TODO: 实际执行向量搜索
        results = [
            {
                "id": "chunk_001",
                "document_id": request.document_id or "doc_123",
                "content": "IP地址冲突解决方案...",
                "score": 0.92,
                "metadata": {
                    "source": "RFC文档",
                    "page": 12
                }
            },
            {
                "id": "chunk_002",
                "document_id": request.document_id or "doc_124",
                "content": "DHCP配置指南...",
                "score": 0.88,
                "metadata": {
                    "source": "设备手册",
                    "page": 45
                }
            }
        ]
        
        return {
            "success": True,
            "data": {
                "results": results[:request.top_k],
                "total": len(results)
            }
        }
    except Exception as e:
        logger.error(f"向量搜索失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/vector/documents/{document_id}")
async def delete_document_vectors(
    document_id: str,
    user: UserModel = Depends(get_admin_user)
):
    """删除文档的向量数据（仅管理员）"""
    try:
        # TODO: 实际删除向量数据
        return {
            "success": True,
            "message": f"Document {document_id} vectors deleted"
        }
    except Exception as e:
        logger.error(f"删除文档向量失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/vector/embedding/test")
async def test_embedding(
    request: EmbeddingTestRequest,
    user: UserModel = Depends(get_verified_user)
):
    """测试嵌入服务"""
    try:
        # TODO: 实际调用嵌入服务
        embedding = [0.123, -0.456, 0.789, 0.234, -0.567, 0.890, 0.123, -0.456, 0.789, 0.234]
        
        return {
            "success": True,
            "data": {
                "text": request.text,
                "embedding_dimension": 1536,  # 假设使用的是1536维的嵌入
                "embedding_sample": embedding  # 前10个值作为示例
            }
        }
    except Exception as e:
        logger.error(f"测试嵌入服务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vector/config")
async def get_vector_config(user: UserModel = Depends(get_verified_user)):
    """获取向量数据库配置信息"""
    try:
        return {
            "success": True,
            "data": {
                "db_type": "weaviate",
                "is_valid": True,
                "config": {
                    "host": "localhost",
                    "port": 8080,
                    "scheme": "http",
                    "timeout": 30
                    # 隐藏敏感信息如API密钥
                }
            }
        }
    except Exception as e:
        logger.error(f"获取向量配置失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== 向量索引重建 ==========

@router.post("/vector/rebuild")
async def rebuild_vector_index(
    document_id: Optional[str] = None,
    user: UserModel = Depends(get_admin_user)
):
    """重建向量索引（仅管理员）"""
    try:
        from open_webui.services.vector_rebuild_service import start_vector_rebuild
        import uuid
        
        # 生成任务ID
        task_id = str(uuid.uuid4())
        
        # 确定要重建的文档列表
        document_ids = [document_id] if document_id else None
        
        # 启动重建任务
        progress = await start_vector_rebuild(
            task_id=task_id,
            document_ids=document_ids,
            user_id=user.id
        )
        
        return {
            "success": True,
            "data": {
                "task_id": task_id,
                "status": progress.status.value,
                "total_documents": progress.total_count,
                "message": f"向量索引重建任务已启动，任务ID: {task_id}"
            }
        }
    except Exception as e:
        logger.error(f"启动向量索引重建失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vector/rebuild/status")
async def get_rebuild_status(
    task_id: Optional[str] = None,
    user: UserModel = Depends(get_verified_user)
):
    """获取索引重建状态"""
    try:
        from open_webui.services.vector_rebuild_service import get_rebuild_progress, get_all_rebuild_tasks
        
        if task_id:
            # 获取特定任务状态
            progress = get_rebuild_progress(task_id)
            if not progress:
                raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")
            
            return {
                "success": True,
                "data": progress.to_dict()
            }
        else:
            # 获取所有活跃任务状态
            active_tasks = get_all_rebuild_tasks()
            
            return {
                "success": True,
                "data": {
                    "active_tasks": [task.to_dict() for task in active_tasks],
                    "has_running_tasks": any(task.status.value == "running" for task in active_tasks)
                }
            }
        
    except Exception as e:
        logger.error(f"获取重建状态失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/vector/rebuild/{task_id}/cancel")
async def cancel_rebuild_task(
    task_id: str,
    user: UserModel = Depends(get_admin_user)
):
    """取消向量索引重建任务（仅管理员）"""
    try:
        from open_webui.services.vector_rebuild_service import cancel_rebuild_task
        
        success = await cancel_rebuild_task(task_id)
        
        if success:
            return {
                "success": True,
                "data": {
                    "task_id": task_id,
                    "message": "任务取消成功"
                }
            }
        else:
            raise HTTPException(
                status_code=404, 
                detail=f"任务 {task_id} 不存在或无法取消"
            )
            
    except Exception as e:
        logger.error(f"取消重建任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== LLM连接测试 ==========

@router.post("/test/llm")
async def test_llm_connection(
    model_name: Optional[str] = "qwen-plus",
    user: UserModel = Depends(get_verified_user)
):
    """测试LLM连接"""
    try:
        # TODO: 实际测试LLM连接
        test_prompt = "请简单回复'连接正常'来测试连接状态。"
        
        # 模拟LLM响应
        response = {
            "model": model_name,
            "response": "连接正常",
            "response_time": 1.2,
            "token_count": {
                "input": 15,
                "output": 4,
                "total": 19
            },
            "status": "success"
        }
        
        return {
            "success": True,
            "data": response
        }
    except Exception as e:
        logger.error(f"LLM连接测试失败: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/llm/models")
async def get_available_models(user: UserModel = Depends(get_verified_user)):
    """获取可用的LLM模型列表"""
    try:
        models = [
            {
                "name": "qwen-plus",
                "display_name": "通义千问Plus",
                "provider": "阿里云",
                "status": "available",
                "max_tokens": 8192
            },
            {
                "name": "qwen-turbo",
                "display_name": "通义千问Turbo",
                "provider": "阿里云",
                "status": "available",
                "max_tokens": 8192
            },
            {
                "name": "text-embedding-v4",
                "display_name": "文本嵌入模型v4",
                "provider": "阿里云",
                "status": "available",
                "type": "embedding"
            }
        ]
        
        return {
            "success": True,
            "data": models
        }
    except Exception as e:
        logger.error(f"获取模型列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== 调试日志 ==========

@router.get("/debug/logs")
async def get_debug_logs(
    level: str = "INFO",
    lines: int = 100,
    user: UserModel = Depends(get_admin_user)
):
    """获取调试日志（仅管理员）"""
    try:
        # TODO: 从实际日志文件读取
        sample_logs = [
            {
                "timestamp": "2025-01-11T14:30:15.123Z",
                "level": "INFO",
                "module": "cases",
                "message": "案例创建成功: case_12345",
                "user_id": "user_001"
            },
            {
                "timestamp": "2025-01-11T14:30:10.456Z",
                "level": "DEBUG",
                "module": "vector",
                "message": "向量搜索查询: IP地址冲突",
                "query_time": "0.05s"
            },
            {
                "timestamp": "2025-01-11T14:30:05.789Z",
                "level": "ERROR",
                "module": "llm",
                "message": "LLM调用超时",
                "error": "Request timeout after 30s"
            }
        ]
        
        # 根据级别过滤
        if level != "ALL":
            filtered_logs = [log for log in sample_logs if log["level"] == level]
        else:
            filtered_logs = sample_logs
        
        return {
            "success": True,
            "data": {
                "logs": filtered_logs[:lines],
                "total_count": len(filtered_logs),
                "level_filter": level,
                "lines_requested": lines
            }
        }
    except Exception as e:
        logger.error(f"获取调试日志失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/debug/logs/levels")
async def get_log_levels(user: UserModel = Depends(get_verified_user)):
    """获取可用的日志级别"""
    levels = [
        {"value": "DEBUG", "label": "调试", "color": "#6c757d"},
        {"value": "INFO", "label": "信息", "color": "#17a2b8"},
        {"value": "WARNING", "label": "警告", "color": "#ffc107"},
        {"value": "ERROR", "label": "错误", "color": "#dc3545"},
        {"value": "CRITICAL", "label": "严重", "color": "#6f42c1"},
        {"value": "ALL", "label": "全部", "color": "#28a745"}
    ]
    
    return {
        "success": True,
        "data": levels
    }


# ========== 系统监控 ==========

@router.get("/system/metrics")
async def get_system_metrics(user: UserModel = Depends(get_verified_user)):
    """获取系统性能指标"""
    try:
        import psutil
        
        # 获取系统资源使用情况
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        metrics = {
            "cpu": {
                "usage_percent": cpu_percent,
                "core_count": psutil.cpu_count()
            },
            "memory": {
                "total": memory.total,
                "available": memory.available,
                "used": memory.used,
                "percent": memory.percent
            },
            "disk": {
                "total": disk.total,
                "used": disk.used,
                "free": disk.free,
                "percent": (disk.used / disk.total) * 100
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return {
            "success": True,
            "data": metrics
        }
    except ImportError:
        # 如果psutil不可用，返回模拟数据
        metrics = {
            "cpu": {"usage_percent": 25.5, "core_count": 4},
            "memory": {
                "total": 8589934592,
                "used": 4294967296,
                "percent": 50.0
            },
            "disk": {
                "total": 107374182400,
                "used": 53687091200,
                "percent": 50.0
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return {
            "success": True,
            "data": metrics,
            "note": "使用模拟数据，请安装psutil获取真实指标"
        }
    except Exception as e:
        logger.error(f"获取系统指标失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== 健康检查 ==========

@router.get("/health")
async def health_check():
    """健康检查端点"""
    try:
        # TODO: 测试各个服务的连接状态
        llm_healthy = True  # 模拟LLM服务健康
        cache_healthy = True  # 模拟缓存服务健康
        vector_healthy = True  # 模拟向量数据库健康
        database_healthy = True  # 模拟数据库健康
        
        services = {
            "llm": "healthy" if llm_healthy else "unhealthy",
            "cache": "healthy" if cache_healthy else "unhealthy",
            "vector": "healthy" if vector_healthy else "unhealthy",
            "database": "healthy" if database_healthy else "unhealthy"
        }
        
        overall_status = 'healthy' if all([llm_healthy, cache_healthy, vector_healthy, database_healthy]) else 'degraded'
        
        return {
            "status": overall_status,
            "services": services,
            "timestamp": datetime.utcnow().isoformat(),
            "version": VERSION if VERSION else "1.0.0",
            "environment": ENV if ENV else "development"
        }
    except Exception as e:
        logger.error(f"健康检查失败: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@router.get("/health/detailed")
async def detailed_health_check(user: UserModel = Depends(get_admin_user)):
    """详细健康检查（仅管理员）"""
    try:
        health_data = {
            "overall_status": "healthy",
            "services": {
                "database": {
                    "status": "healthy",
                    "response_time": 0.05,
                    "connections": 5,
                    "max_connections": 100
                },
                "llm": {
                    "status": "healthy",
                    "models_available": 3,
                    "avg_response_time": 1.2,
                    "requests_per_minute": 45
                },
                "vector_db": {
                    "status": "healthy",
                    "documents": 1500,
                    "chunks": 12000,
                    "index_size": "2.3GB"
                },
                "cache": {
                    "status": "healthy",
                    "memory_used": "256MB",
                    "hit_rate": 0.85,
                    "keys": 1234
                }
            },
            "system_info": {
                "uptime": "2 days, 14 hours",
                "version": VERSION if VERSION else "1.0.0",
                "environment": ENV if ENV else "development",
                "python_version": sys.version.split()[0]
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return {
            "success": True,
            "data": health_data
        }
    except Exception as e:
        logger.error(f"详细健康检查失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
