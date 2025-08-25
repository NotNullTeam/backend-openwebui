"""
知识模块统一API路由

整合 knowledge 和 knowledge_migrated 模块，提供统一的RESTful API接口
"""

import os
import uuid
import time
import mimetypes
import json
from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status, Request, File, UploadFile, Form, Query
from fastapi.responses import FileResponse, StreamingResponse
import logging

from open_webui.models.knowledge_unified import (
    KnowledgeBaseCreate,
    KnowledgeBaseUpdate,
    KnowledgeBaseResponse,
    KnowledgeBaseListResponse,
    DocumentCreate,
    DocumentUpdate,
    DocumentResponse,
    DocumentListResponse,
    DocumentUploadResponse,
    SearchRequest,
    SearchResponse,
    SearchSuggestionRequest,
    SearchSuggestionResponse,
    KnowledgeStatsResponse,
    ProcessingStatus
)
from open_webui.services.knowledge_unified import (
    KnowledgeService,
    DocumentService,
    SearchService
)
from open_webui.utils.auth import get_verified_user, get_admin_user
from open_webui.utils.access_control import get_permissions, has_access, has_permission
from open_webui.constants import ERROR_MESSAGES
from open_webui.exceptions.knowledge import (
    KnowledgeBaseNotFoundError,
    KnowledgeBaseAlreadyExistsError,
    KnowledgeBaseAccessDeniedError,
    DocumentNotFoundError,
    DocumentUploadError,
    DocumentAccessDeniedError,
    DocumentFormatError,
    DocumentSizeError,
    SearchQueryError
)
from open_webui.middleware.exception_handler import handle_knowledge_exceptions

logger = logging.getLogger(__name__)

# ==================== API版本配置 ====================

# API版本常量
API_VERSION_V1 = "v1"
API_VERSION_V2 = "v2"  # 为未来版本预留
CURRENT_API_VERSION = API_VERSION_V1

# 创建版本化路由的工厂函数
def create_versioned_router(version: str) -> APIRouter:
    """创建指定版本的路由器"""
    return APIRouter(
        prefix=f"/api/{version}/knowledge",
        tags=[f"Knowledge Management {version.upper()}"],
        responses={
            404: {"description": "Not found"},
            422: {"description": "Validation Error"},
        }
    )

# 创建版本化的路由器
router_v1 = create_versioned_router(API_VERSION_V1)
router_v2 = create_versioned_router(API_VERSION_V2)

# 主路由器（当前版本的别名）
router = APIRouter(prefix="/api/knowledge", tags=["Knowledge Management"])

# 服务实例
knowledge_service = KnowledgeService()
document_service = DocumentService()
search_service = SearchService()


# ==================== API版本管理 ====================

class APIVersionInfo:
    """API版本信息"""
    def __init__(self, version: str, status: str, release_date: str, deprecation_date: str = None):
        self.version = version
        self.status = status  # active, deprecated, sunset
        self.release_date = release_date
        self.deprecation_date = deprecation_date
        self.endpoints = []


# 版本信息注册
API_VERSIONS = {
    API_VERSION_V1: APIVersionInfo(
        version=API_VERSION_V1,
        status="active",
        release_date="2025-08-25",
        deprecation_date=None
    ),
    API_VERSION_V2: APIVersionInfo(
        version=API_VERSION_V2,
        status="planned",
        release_date="2025-12-01",
        deprecation_date=None
    )
}


@router.get("/versions")
async def get_api_versions():
    """获取API版本信息"""
    return {
        "current_version": CURRENT_API_VERSION,
        "versions": {
            version: {
                "version": info.version,
                "status": info.status,
                "release_date": info.release_date,
                "deprecation_date": info.deprecation_date
            }
            for version, info in API_VERSIONS.items()
        },
        "endpoints": [
            f"/api/{CURRENT_API_VERSION}/knowledge",
            f"/api/knowledge"  # 当前版本别名
        ]
    }


def api_version(version: str = CURRENT_API_VERSION):
    """API版本装饰器"""
    def decorator(func):
        # 为函数添加版本信息
        func.__api_version__ = version
        
        # 直接返回原函数，不使用wrapper
        # 避免参数传递问题
        return func
    return decorator


def version_header_check(required_version: str = None):
    """API版本检查装饰器"""
    def decorator(func):
        async def wrapper(request: Request, *args, **kwargs):
            # 检查Accept-Version头部
            requested_version = request.headers.get("Accept-Version", CURRENT_API_VERSION)
            
            if required_version and requested_version != required_version:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "version_mismatch",
                        "message": f"API version {requested_version} not supported for this endpoint",
                        "supported_version": required_version,
                        "current_version": CURRENT_API_VERSION
                    }
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


# ==================== 权限检查助手函数 ====================

async def check_knowledge_base_access(user_id: str, kb_id: str, access_type: str = "read") -> bool:
    """检查用户对知识库的访问权限"""
    # 临时创建一个service实例来获取知识库信息
    # 这里需要特殊处理，避免循环依赖
    from open_webui.internal.db import get_db
    from open_webui.models.knowledge_unified import KnowledgeBase
    from sqlalchemy import and_
    
    with get_db() as db:
        kb = db.query(KnowledgeBase).filter(
            and_(
                KnowledgeBase.id == kb_id,
                KnowledgeBase.user_id == user_id
            )
        ).first()
        
        if not kb:
            return False
        
        # 如果是知识库所有者，直接允许
        if kb.user_id == user_id:
            return True
        
        # 检查访问控制列表
        if kb.access_control:
            return has_access(user_id, access_type, kb.access_control)
        
        # 默认只允许读取公开的知识库
        return access_type == "read" and kb.access_control and kb.access_control.get("public", False)


async def check_document_access(user_id: str, doc_id: str, access_type: str = "read") -> bool:
    """检查用户对文档的访问权限"""
    # 临时创建一个service实例来获取文档信息
    from open_webui.internal.db import get_db
    from open_webui.models.knowledge_unified import Document
    from sqlalchemy import and_
    
    with get_db() as db:
        doc = db.query(Document).filter(
            and_(
                Document.id == doc_id,
                Document.user_id == user_id
            )
        ).first()
        
        if not doc:
            return False
        
        # 如果是文档所有者，直接允许
        if doc.user_id == user_id:
            return True
        
        # 检查访问控制列表
        if doc.access_control:
            return has_access(user_id, access_type, doc.access_control)
        
        # 默认只允许读取公开的文档
        return access_type == "read" and doc.access_control and doc.access_control.get("public", False)


def register_routers(app):
    """注册所有版本的路由到主应用"""
    # 注册版本化路由
    app.include_router(router_v1)
    # app.include_router(router_v2)  # 未来版本，暂时注释
    
    # 注册当前版本别名路由
    app.include_router(router)
    
    # 添加版本相关的中间件
    @app.middleware("http")
    async def add_version_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-API-Version"] = CURRENT_API_VERSION
        response.headers["X-API-Supported-Versions"] = ",".join(API_VERSIONS.keys())
        return response


def require_knowledge_permission(permission: str):
    """装饰器：要求特定的知识管理权限"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            user = kwargs.get('user')
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            if not has_permission(user.id, f"knowledge.{permission}"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Missing permission: knowledge.{permission}"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


# 导出用于应用注册的路由器列表
__all__ = ["router", "router_v1", "router_v2", "register_routers"]


# ==================== 知识库管理 V1 ====================

@router_v1.get("/collections", response_model=KnowledgeBaseListResponse)
async def get_knowledge_bases_v1(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    user=Depends(get_verified_user)
):
    """获取知识库列表 (v1)"""
    try:
        return await knowledge_service.list_knowledge_bases(
            user_id=user.id,
            page=page,
            page_size=page_size,
            search=search,
            category=category
        )
    except Exception as e:
        logger.error(f"Failed to get knowledge bases: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve knowledge bases"
        )


# ==================== 知识库管理（当前版本别名） ====================

@router.get("/collections", response_model=KnowledgeBaseListResponse)
@api_version(API_VERSION_V1)
async def get_knowledge_bases(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    user=Depends(get_verified_user)
):
    """获取知识库列表"""
    try:
        return await knowledge_service.list_knowledge_bases(
            user_id=user.id,
            page=page,
            page_size=page_size,
            search=search,
            category=category
        )
    except Exception as e:
        logger.error(f"Failed to get knowledge bases: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve knowledge bases"
        )


@router.post("/collections", response_model=KnowledgeBaseResponse)
@api_version(API_VERSION_V1)
@handle_knowledge_exceptions
async def create_knowledge_base(
    data: KnowledgeBaseCreate,
    user=Depends(get_verified_user)
):
    """创建知识库"""
    # 检查创建知识库权限
    if not has_permission(user.id, "knowledge.create"):
        raise KnowledgeBaseAccessDeniedError(
            kb_id="new",
            access_type="create",
            user_id=user.id
        )
    
    try:
        return await knowledge_service.create_knowledge_base(user.id, data)
    except ValueError as e:
        if "already exists" in str(e):
            raise KnowledgeBaseAlreadyExistsError(data.name, user.id)
        else:
            raise DocumentUploadError(data.name, str(e))


@router.get("/collections/{kb_id}", response_model=KnowledgeBaseResponse)
@api_version(API_VERSION_V1)
@handle_knowledge_exceptions
async def get_knowledge_base(
    kb_id: str,
    user=Depends(get_verified_user)
):
    """获取知识库详情"""
    # 检查访问权限
    if not await check_knowledge_base_access(user.id, kb_id, "read"):
        raise KnowledgeBaseAccessDeniedError(
            kb_id=kb_id,
            access_type="read",
            user_id=user.id
        )
    
    kb = await knowledge_service.get_knowledge_base(user.id, kb_id)
    if not kb:
        raise KnowledgeBaseNotFoundError(kb_id)
    
    return kb


@router.put("/collections/{kb_id}", response_model=KnowledgeBaseResponse)
@handle_knowledge_exceptions
async def update_knowledge_base(
    kb_id: str,
    data: KnowledgeBaseUpdate,
    user=Depends(get_verified_user)
):
    """更新知识库"""
    # 检查编辑权限
    if not await check_knowledge_base_access(user.id, kb_id, "write"):
        raise KnowledgeBaseAccessDeniedError(
            kb_id=kb_id,
            access_type="write",
            user_id=user.id
        )
    
    kb = await knowledge_service.update_knowledge_base(user.id, kb_id, data)
    if not kb:
        raise KnowledgeBaseNotFoundError(kb_id)
    
    return kb


@router.delete("/collections/{kb_id}")
@handle_knowledge_exceptions
async def delete_knowledge_base(
    kb_id: str,
    user=Depends(get_verified_user)
):
    """删除知识库"""
    # 检查删除权限（通常需要管理员权限或所有者权限）
    if not await check_knowledge_base_access(user.id, kb_id, "admin"):
        raise KnowledgeBaseAccessDeniedError(
            kb_id=kb_id,
            access_type="admin",
            user_id=user.id
        )
    
    success = await knowledge_service.delete_knowledge_base(user.id, kb_id)
    if not success:
        raise KnowledgeBaseNotFoundError(kb_id)
    
    return {"message": "Knowledge base deleted successfully"}


# ==================== 文档管理 ====================

@router.get("/documents", response_model=DocumentListResponse)
async def get_documents(
    kb_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[ProcessingStatus] = Query(None),
    search: Optional[str] = Query(None),
    user=Depends(get_verified_user)
):
    """获取文档列表"""
    try:
        return await document_service.list_documents(
            user_id=user.id,
            kb_id=kb_id,
            page=page,
            page_size=page_size,
            status_filter=status_filter,
            search=search
        )
    except Exception as e:
        logger.error(f"Failed to get documents: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve documents"
        )


@router.post("/documents", response_model=DocumentUploadResponse)
@handle_knowledge_exceptions
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    tags: str = Form("[]"),
    knowledge_base_ids: str = Form("[]"),
    processing_params: str = Form("{}"),
    user=Depends(get_verified_user)
):
    """上传文档"""
    # 检查文档上传权限
    if not has_permission(user.id, "knowledge.upload"):
        raise DocumentAccessDeniedError(
            doc_id="new",
            access_type="upload",
            user_id=user.id
        )
    
    # 检查文件大小和格式
    max_size = 50 * 1024 * 1024  # 50MB
    supported_formats = ['.pdf', '.docx', '.txt', '.md', '.html']
    
    if not file.filename:
        raise DocumentUploadError("", "No filename provided")
    
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in supported_formats:
        raise DocumentFormatError(file.filename, supported_formats)
    
    # 读取文件内容检查大小
    file_content = await file.read()
    if len(file_content) > max_size:
        raise DocumentSizeError(file.filename, len(file_content), max_size)
    
    try:
        # 解析JSON字符串
        tags_list = json.loads(tags) if tags else []
        kb_ids = json.loads(knowledge_base_ids) if knowledge_base_ids else []
        proc_params = json.loads(processing_params) if processing_params else {}
    except json.JSONDecodeError as e:
        raise DocumentUploadError(file.filename, f"Invalid JSON in form data: {e}")
    
    # 检查对目标知识库的写入权限
    for kb_id in kb_ids:
        if not await check_knowledge_base_access(user.id, kb_id, "write"):
            raise KnowledgeBaseAccessDeniedError(
                kb_id=kb_id,
                access_type="write",
                user_id=user.id
            )
    
    # 创建文档数据
    doc_data = DocumentCreate(
        title=title,
        description=description,
        tags=tags_list,
        knowledge_base_ids=kb_ids,
        processing_params=proc_params
    )
    
    return await document_service.upload_document(
        user_id=user.id,
        file_data=file_content,
        filename=file.filename,
        data=doc_data
    )


@router.get("/documents/{doc_id}", response_model=DocumentResponse)
async def get_document(
    doc_id: str,
    user=Depends(get_verified_user)
):
    """获取文档详情"""
    try:
        doc = await document_service.get_document(user.id, doc_id)
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        return doc
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document {doc_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve document"
        )


@router.put("/documents/{doc_id}", response_model=DocumentResponse)
@api_version(API_VERSION_V1)
@handle_knowledge_exceptions
async def update_document(
    doc_id: str,
    data: DocumentUpdate,
    user=Depends(get_verified_user)
):
    """更新文档"""
    # 检查文档编辑权限
    if not await check_document_access(user.id, doc_id, "write"):
        raise DocumentAccessDeniedError(
            doc_id=doc_id,
            access_type="write",
            user_id=user.id
        )
    
    doc = await document_service.update_document(user.id, doc_id, data)
    if not doc:
        raise DocumentNotFoundError(doc_id)
    
    return doc


@router.delete("/documents/{doc_id}")
@api_version(API_VERSION_V1)
@handle_knowledge_exceptions
async def delete_document(
    doc_id: str,
    user=Depends(get_verified_user)
):
    """删除文档"""
    # 检查文档删除权限
    if not await check_document_access(user.id, doc_id, "admin"):
        raise DocumentAccessDeniedError(
            doc_id=doc_id,
            access_type="admin",
            user_id=user.id
        )
    
    success = await document_service.delete_document(user.id, doc_id)
    if not success:
        raise DocumentNotFoundError(doc_id)
    
    return {"message": "Document deleted successfully"}


# ==================== 知识库文档关联管理 ====================

@router.post("/collections/{kb_id}/documents/{doc_id}")
@api_version(API_VERSION_V1)
@handle_knowledge_exceptions
async def add_document_to_knowledge_base(
    kb_id: str,
    doc_id: str,
    notes: Optional[str] = None,
    user=Depends(get_verified_user)
):
    """将文档添加到知识库"""
    # 检查知识库写入权限
    if not await check_knowledge_base_access(user.id, kb_id, "write"):
        raise KnowledgeBaseAccessDeniedError(
            kb_id=kb_id,
            access_type="write",
            user_id=user.id
        )
    
    # 检查文档读取权限
    if not await check_document_access(user.id, doc_id, "read"):
        raise DocumentAccessDeniedError(
            doc_id=doc_id,
            access_type="read",
            user_id=user.id
        )
    
    success = await knowledge_service.add_document_to_knowledge_base(
        user_id=user.id,
        kb_id=kb_id,
        doc_id=doc_id,
        notes=notes
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to add document to knowledge base"
        )
    
    return {"message": "Document added to knowledge base successfully"}


@router.delete("/collections/{kb_id}/documents/{doc_id}")
@api_version(API_VERSION_V1)
@handle_knowledge_exceptions
async def remove_document_from_knowledge_base(
    kb_id: str,
    doc_id: str,
    user=Depends(get_verified_user)
):
    """从知识库移除文档"""
    # 检查知识库写入权限
    if not await check_knowledge_base_access(user.id, kb_id, "write"):
        raise KnowledgeBaseAccessDeniedError(
            kb_id=kb_id,
            access_type="write",
            user_id=user.id
        )
    
    success = await knowledge_service.remove_document_from_knowledge_base(
        user_id=user.id,
        kb_id=kb_id,
        doc_id=doc_id
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document association not found"
        )
    
    return {"message": "Document removed from knowledge base successfully"}


# ==================== 批量操作 ====================

@router.post("/collections/{kb_id}/documents/batch")
@api_version(API_VERSION_V1)
@handle_knowledge_exceptions
async def batch_add_documents_to_knowledge_base(
    kb_id: str,
    document_ids: List[str],
    user=Depends(get_verified_user)
):
    """批量将文档添加到知识库"""
    # 检查知识库写入权限
    if not await check_knowledge_base_access(user.id, kb_id, "write"):
        raise KnowledgeBaseAccessDeniedError(
            kb_id=kb_id,
            access_type="write",
            user_id=user.id
        )
    
    results = []
    for doc_id in document_ids:
        try:
            # 检查文档权限
            if not await check_document_access(user.id, doc_id, "read"):
                results.append({
                    "doc_id": doc_id,
                    "success": False,
                    "error": "Access denied"
                })
                continue
            
            success = await knowledge_service.add_document_to_knowledge_base(
                user_id=user.id,
                kb_id=kb_id,
                doc_id=doc_id
            )
            
            results.append({
                "doc_id": doc_id,
                "success": success,
                "error": None if success else "Failed to add"
            })
            
        except Exception as e:
            results.append({
                "doc_id": doc_id,
                "success": False,
                "error": str(e)
            })
    
    return {
        "message": "Batch operation completed",
        "results": results,
        "successful": len([r for r in results if r["success"]]),
        "failed": len([r for r in results if not r["success"]])
    }


@router.delete("/collections/{kb_id}/documents/batch")
@api_version(API_VERSION_V1)
@handle_knowledge_exceptions
async def batch_remove_documents_from_knowledge_base(
    kb_id: str,
    document_ids: List[str],
    user=Depends(get_verified_user)
):
    """批量从知识库移除文档"""
    # 检查知识库写入权限
    if not await check_knowledge_base_access(user.id, kb_id, "write"):
        raise KnowledgeBaseAccessDeniedError(
            kb_id=kb_id,
            access_type="write",
            user_id=user.id
        )
    
    results = []
    for doc_id in document_ids:
        try:
            success = await knowledge_service.remove_document_from_knowledge_base(
                user_id=user.id,
                kb_id=kb_id,
                doc_id=doc_id
            )
            
            results.append({
                "doc_id": doc_id,
                "success": success,
                "error": None if success else "Not found or already removed"
            })
            
        except Exception as e:
            results.append({
                "doc_id": doc_id,
                "success": False,
                "error": str(e)
            })
    
    return {
        "message": "Batch operation completed",
        "results": results,
        "successful": len([r for r in results if r["success"]]),
        "failed": len([r for r in results if not r["success"]])
    }


# ==================== 统计和状态 ====================

@router.get("/stats", response_model=KnowledgeStatsResponse)
@api_version(API_VERSION_V1)
@handle_knowledge_exceptions
async def get_knowledge_stats(
    user=Depends(get_verified_user)
):
    """获取用户的知识管理统计信息"""
    return await knowledge_service.get_stats(user.id)


@router.get("/collections/{kb_id}/stats")
@api_version(API_VERSION_V1)
@handle_knowledge_exceptions
async def get_knowledge_base_stats(
    kb_id: str,
    user=Depends(get_verified_user)
):
    """获取指定知识库的统计信息"""
    # 检查知识库读取权限
    if not await check_knowledge_base_access(user.id, kb_id, "read"):
        raise KnowledgeBaseAccessDeniedError(
            kb_id=kb_id,
            access_type="read",
            user_id=user.id
        )
    
    stats = await knowledge_service.get_knowledge_base_stats(user.id, kb_id)
    if not stats:
        raise KnowledgeBaseNotFoundError(kb_id)
    
    return stats


@router.get("/documents/{doc_id}/status")
@api_version(API_VERSION_V1)
@handle_knowledge_exceptions
async def get_document_processing_status(
    doc_id: str,
    user=Depends(get_verified_user)
):
    """获取文档处理状态"""
    # 检查文档读取权限
    if not await check_document_access(user.id, doc_id, "read"):
        raise DocumentAccessDeniedError(
            doc_id=doc_id,
            access_type="read",
            user_id=user.id
        )
    
    status_info = await document_service.get_processing_status(user.id, doc_id)
    if not status_info:
        raise DocumentNotFoundError(doc_id)
    
    return status_info


@router.post("/documents/{doc_id}/retry")
@api_version(API_VERSION_V1)
@handle_knowledge_exceptions
async def retry_document_processing(
    doc_id: str,
    user=Depends(get_verified_user)
):
    """重试文档处理"""
    # 检查文档访问权限
    if not await check_document_access(user.id, doc_id, "write"):
        raise DocumentAccessDeniedError(
            doc_id=doc_id,
            access_type="write",
            user_id=user.id
        )
    
    try:
        success = await document_service.retry_processing(user.id, doc_id)
        if not success:
            raise DocumentNotFoundError(doc_id)
        
        return {"message": "Document processing retry initiated"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retry processing for {doc_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retry document processing"
        )


@router.delete("/documents/{doc_id}/cancel")
async def cancel_document_processing(
    doc_id: str,
    user=Depends(get_verified_user)
):
    """取消文档处理"""
    try:
        success = await document_service.cancel_processing(user.id, doc_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found or cannot be cancelled"
            )
        return {"message": "Document processing cancelled"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel processing for {doc_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel document processing"
        )


# ==================== 搜索功能 ====================

@router.post("/search", response_model=SearchResponse)
async def search_knowledge(
    request: SearchRequest,
    user=Depends(get_verified_user)
):
    """搜索知识库"""
    try:
        return await search_service.search(user.id, request)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search operation failed"
        )


@router.post("/search/suggestions", response_model=SearchSuggestionResponse)
async def get_search_suggestions(
    request: SearchSuggestionRequest,
    user=Depends(get_verified_user)
):
    """获取搜索建议"""
    try:
        return await search_service.get_suggestions(user.id, request)
    except Exception as e:
        logger.error(f"Failed to get search suggestions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get search suggestions"
        )


@router.get("/search/history")
async def get_search_history(
    limit: int = Query(10, ge=1, le=50),
    user=Depends(get_verified_user)
):
    """获取搜索历史"""
    try:
        history = await search_service.get_search_history(user.id, limit)
        return {"history": history}
    except Exception as e:
        logger.error(f"Failed to get search history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve search history"
        )


# ==================== 统计信息 ====================

@router.get("/stats", response_model=KnowledgeStatsResponse)
async def get_knowledge_stats(
    user=Depends(get_verified_user)
):
    """获取知识库整体统计信息"""
    try:
        return await knowledge_service.get_stats(user.id)
    except Exception as e:
        logger.error(f"Failed to get knowledge stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve statistics"
        )


@router.get("/collections/{kb_id}/stats")
async def get_knowledge_base_stats(
    kb_id: str,
    user=Depends(get_verified_user)
):
    """获取特定知识库统计信息"""
    try:
        stats = await knowledge_service.get_knowledge_base_stats(user.id, kb_id)
        if not stats:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Knowledge base not found"
            )
        return stats
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get knowledge base stats for {kb_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve knowledge base statistics"
        )


@router.get("/documents/{doc_id}/stats")
async def get_document_stats(
    doc_id: str,
    user=Depends(get_verified_user)
):
    """获取文档统计信息"""
    try:
        stats = await document_service.get_document_stats(user.id, doc_id)
        if not stats:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        return stats
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document stats for {doc_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve document statistics"
        )


# ==================== 文档下载 ====================

@router.get("/documents/{doc_id}/download")
async def download_document(
    doc_id: str,
    user=Depends(get_verified_user)
):
    """下载文档"""
    try:
        file_info = await document_service.get_file_info(user.id, doc_id)
        if not file_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        file_path = file_info.get("file_path")
        if not file_path or not os.path.exists(file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document file not found"
            )
        
        return FileResponse(
            path=file_path,
            filename=file_info.get("original_filename", "download"),
            media_type=file_info.get("content_type", "application/octet-stream")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download document {doc_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to download document"
        )


# ==================== 批量操作 ====================

@router.post("/documents/batch")
async def batch_upload_documents(
    files: List[UploadFile] = File(...),
    knowledge_base_ids: str = Form("[]"),
    processing_params: str = Form("{}"),
    user=Depends(get_verified_user)
):
    """批量上传文档"""
    try:
        import json
        kb_ids = json.loads(knowledge_base_ids) if knowledge_base_ids else []
        proc_params = json.loads(processing_params) if processing_params else {}
        
        results = []
        for file in files:
            try:
                file_content = await file.read()
                doc_data = DocumentCreate(
                    knowledge_base_ids=kb_ids,
                    processing_params=proc_params
                )
                
                result = await document_service.upload_document(
                    user_id=user.id,
                    file_data=file_content,
                    filename=file.filename,
                    data=doc_data
                )
                results.append({
                    "filename": file.filename,
                    "success": True,
                    "document_id": result.document_id
                })
            except Exception as e:
                results.append({
                    "filename": file.filename,
                    "success": False,
                    "error": str(e)
                })
        
        return {"results": results}
        
    except Exception as e:
        logger.error(f"Batch upload failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Batch upload operation failed"
        )


@router.delete("/documents/batch")
async def batch_delete_documents(
    document_ids: List[str],
    user=Depends(get_verified_user)
):
    """批量删除文档"""
    try:
        results = []
        for doc_id in document_ids:
            try:
                success = await document_service.delete_document(user.id, doc_id)
                results.append({
                    "document_id": doc_id,
                    "success": success
                })
            except Exception as e:
                results.append({
                    "document_id": doc_id,
                    "success": False,
                    "error": str(e)
                })
        
        return {"results": results}
        
    except Exception as e:
        logger.error(f"Batch delete failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Batch delete operation failed"
        )


# ==================== 健康检查 ====================

@router.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }
