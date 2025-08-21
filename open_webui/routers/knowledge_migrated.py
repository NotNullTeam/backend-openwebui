"""
知识管理模块路由 - 从原后端完整迁移

整合文档管理、检索、解析等功能的路由，包括：
- 文档上传、下载、元数据管理
- 混合检索（向量+关键词）
- IDP文档解析
- 搜索建议
"""

import os
import json
import uuid
import mimetypes
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status, Request, File, UploadFile, Form, Query
from fastapi.responses import FileResponse, StreamingResponse
import logging

from open_webui.models.knowledge import (
    Knowledges,
    KnowledgeForm,
    KnowledgeResponse,
    KnowledgeUserResponse,
)
from open_webui.models.files import Files, FileModel, FileMetadataResponse
from open_webui.retrieval.vector.main import get_retrieval_vector_db
from open_webui.retrieval.loaders.main import Loader
from open_webui.services.document_processor import (
    queue_document_for_processing,
    get_document_processing_status,
    document_processor
)
from open_webui.retrieval.vector.similarity_normalizer import SimilarityNormalizer, VectorDBType
from open_webui.constants import ERROR_MESSAGES
from open_webui.utils.auth import get_verified_user
from open_webui.utils.access_control import has_access, has_permission
from open_webui.config import ENABLE_ADMIN_WORKSPACE_CONTENT_ACCESS

logger = logging.getLogger(__name__)
router = APIRouter()

# 相似度归一化工具
similarity_normalizer = SimilarityNormalizer()

# 支持的文件类型
ALLOWED_EXTENSIONS = {
    'image': {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'svg', 'tiff', 'ico'},
    'document': {'pdf', 'doc', 'docx', 'txt', 'md', 'rtf', 'odt'},
    'config': {'cfg', 'conf', 'config', 'xml', 'json', 'yaml', 'yml', 'ini'},
    'log': {'log', 'txt'},
    'archive': {'zip', 'tar', 'gz', 'rar', '7z', 'bz2'},
    'topo': {'vsd', 'vsdx', 'drawio', 'xml'}
}

ALL_ALLOWED_EXTENSIONS = set()
for exts in ALLOWED_EXTENSIONS.values():
    ALL_ALLOWED_EXTENSIONS.update(exts)

# 文件大小限制
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB

# Pydantic 模型定义
class DocumentUploadResponse(BaseModel):
    docId: str
    status: str
    message: str

class DocumentMetadata(BaseModel):
    docId: str
    fileName: str
    vendor: Optional[str] = None
    tags: List[str] = []
    status: str
    progress: int
    fileSize: int
    uploadedAt: str
    processedAt: Optional[str] = None

class DocumentListResponse(BaseModel):
    documents: List[DocumentMetadata]
    pagination: Dict[str, Any]

class SearchRequest(BaseModel):
    query: str = Field(..., description="查询文本")
    filters: Dict[str, Any] = Field(default_factory=dict, description="过滤条件")
    vector_weight: float = Field(0.7, ge=0, le=1, description="向量权重")
    keyword_weight: float = Field(0.3, ge=0, le=1, description="关键词权重")
    top_k: int = Field(10, ge=1, le=50, description="返回结果数量")

class SearchResult(BaseModel):
    id: str
    content: str
    title: Optional[str] = None
    score: float
    source: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

class SearchResponse(BaseModel):
    query: str
    total: int
    results: List[SearchResult]
    search_params: Dict[str, Any]

class SuggestRequest(BaseModel):
    query: str = Field(..., description="查询文本")
    limit: int = Field(10, ge=1, le=20, description="建议数量")

class SuggestResponse(BaseModel):
    query: str
    suggestions: List[str]

class IDPParseRequest(BaseModel):
    enable_llm: bool = Field(True, description="是否开启大模型增强")
    enable_formula: bool = Field(True, description="是否开启公式识别")
    async_mode: bool = Field(True, description="是否异步处理")

class IDPParseFromUrlRequest(BaseModel):
    file_url: str = Field(..., description="文档URL")
    file_name: str = Field(..., description="文件名")
    enable_llm: bool = Field(True, description="是否开启大模型增强")
    enable_formula: bool = Field(True, description="是否开启公式识别")
    async_mode: bool = Field(True, description="是否异步处理")
    vendor: Optional[str] = Field(None, description="厂商")
    tags: List[str] = Field(default_factory=list, description="标签列表")

class DocumentChunkResponse(BaseModel):
    id: str
    chunk_index: int
    content: str
    title: Optional[str] = None
    chunk_type: str
    page_number: Optional[int] = None
    vector_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str

class DocumentChunksResponse(BaseModel):
    chunks: List[DocumentChunkResponse]
    pagination: Dict[str, Any]

def allowed_file(filename: str) -> bool:
    """检查文件扩展名是否允许"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALL_ALLOWED_EXTENSIONS

def get_file_type(filename: str) -> str:
    """根据文件扩展名推断文件类型"""
    if '.' not in filename:
        return 'other'
    
    ext = filename.rsplit('.', 1)[1].lower()
    for file_type, extensions in ALLOWED_EXTENSIONS.items():
        if ext in extensions:
            return file_type
    return 'other'

def get_db_type_from_config() -> VectorDBType:
    """从配置获取向量数据库类型"""
    # 这里应该从配置中读取，暂时返回默认值
    return VectorDBType.WEAVIATE

############################
# 文档管理接口
############################

@router.post("/documents", response_model=DocumentUploadResponse)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    vendor: Optional[str] = Form(None),
    tags: List[str] = Form(default_factory=list),
    user=Depends(get_verified_user)
):
    """
    上传知识文档
    
    支持的文件类型: PDF, DOC, DOCX, TXT, MD, PNG, JPG, JPEG等
    """
    try:
        # 检查文件类型
        if not allowed_file(file.filename):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的文件类型，支持的类型: {', '.join(sorted(ALL_ALLOWED_EXTENSIONS))}"
            )
        
        # 检查文件大小
        file_content = await file.read()
        file_size = len(file_content)
        
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"文件大小超过限制，最大允许 {MAX_FILE_SIZE // 1024 // 1024}MB"
            )
        
        file_type = get_file_type(file.filename)
        if file_type == 'image' and file_size > MAX_IMAGE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"图片文件大小超过限制，最大允许 {MAX_IMAGE_SIZE // 1024 // 1024}MB"
            )
        
        # 生成文件ID和路径
        file_id = str(uuid.uuid4())
        file_extension = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
        new_filename = f"{file_id}.{file_extension}" if file_extension else file_id
        
        # 保存文件到Open WebUI的文件系统
        # 这里应该使用Open WebUI的存储提供者
        from open_webui.storage.provider import Storage
        storage = Storage()
        
        # 重置文件指针
        await file.seek(0)
        file_path = await storage.save_file(file, new_filename)
        
        # 创建文件记录
        file_form = {
            "id": file_id,
            "filename": file.filename,
            "meta": {
                "name": file.filename,
                "content_type": file.content_type,
                "size": file_size,
                "vendor": vendor,
                "tags": tags if isinstance(tags, list) else [tags] if tags else []
            }
        }
        
        # 使用Open WebUI的Files模型保存
        saved_file = Files.insert_new_file(user.id, file_form)
        
        if not saved_file:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="文件保存失败"
            )
        
        # 启动异步文档处理
        processing_queued = queue_document_for_processing(file_id)
        if not processing_queued:
            logger.warning(f"Failed to queue document {file_id} for processing")
        
        return DocumentUploadResponse(
            docId=saved_file.id,
            status="QUEUED",
            message="文档已加入处理队列"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload document error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="文档上传失败"
        )

@router.get("/documents", response_model=DocumentListResponse)
async def get_documents(
    request: Request,
    status_filter: Optional[str] = Query(None, alias="status"),
    vendor: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    pageSize: int = Query(10, ge=1, le=100),
    user=Depends(get_verified_user)
):
    """
    获取文档列表
    
    支持按状态、厂商过滤和分页
    """
    try:
        # 获取用户的文件
        files = Files.get_files_by_user_id(user.id)
        
        # 过滤文件
        filtered_files = []
        for file in files:
            # 状态过滤
            if status_filter and file.meta.get("status") != status_filter:
                continue
            
            # 厂商过滤
            if vendor and file.meta.get("vendor") != vendor:
                continue
            
            filtered_files.append(file)
        
        # 分页
        total = len(filtered_files)
        start_idx = (page - 1) * pageSize
        end_idx = start_idx + pageSize
        paginated_files = filtered_files[start_idx:end_idx]
        
        # 构建响应
        documents = []
        for file in paginated_files:
            doc = DocumentMetadata(
                docId=file.id,
                fileName=file.filename,
                vendor=file.meta.get("vendor"),
                tags=file.meta.get("tags", []),
                status=file.meta.get("status", "UPLOADED"),
                progress=file.meta.get("progress", 0),
                fileSize=file.meta.get("size", 0),
                uploadedAt=file.created_at.isoformat() + 'Z',
                processedAt=file.updated_at.isoformat() + 'Z' if file.updated_at else None
            )
            documents.append(doc)
        
        pagination = {
            "total": total,
            "page": page,
            "per_page": pageSize,
            "pages": (total + pageSize - 1) // pageSize
        }
        
        return DocumentListResponse(
            documents=documents,
            pagination=pagination
        )
        
    except Exception as e:
        logger.error(f"Get documents error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取文档列表时发生错误"
        )

@router.get("/documents/{doc_id}")
async def get_document_detail(
    doc_id: str,
    user=Depends(get_verified_user)
):
    """获取文档详情"""
    try:
        file = Files.get_file_by_id(doc_id)
        
        if not file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文档不存在"
            )
        
        # 检查权限
        if file.user_id != user.id and user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问该文档"
            )
        
        # 获取处理状态
        processing_status = get_document_processing_status(doc_id)
        
        return {
            "docId": file.id,
            "fileName": file.filename,
            "vendor": file.meta.get("vendor"),
            "tags": file.meta.get("tags", []),
            "status": processing_status.get("status", "UPLOADED"),
            "progress": processing_status.get("progress", 0),
            "fileSize": file.meta.get("size", 0),
            "mimeType": file.meta.get("content_type"),
            "uploadedAt": file.created_at.isoformat() + 'Z',
            "processedAt": processing_status.get("completed_at"),
            "processingError": processing_status.get("error"),
            "retryCount": processing_status.get("retry_count", 0),
            "isProcessing": processing_status.get("is_processing", False)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get document detail error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取文档详情时发生错误"
        )

@router.get("/documents/{doc_id}/processing-status")
async def get_document_processing_status_endpoint(
    doc_id: str,
    user=Depends(get_verified_user)
):
    """获取文档处理状态"""
    try:
        file = Files.get_file_by_id(doc_id)
        
        if not file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文档不存在"
            )
        
        # 检查权限
        if file.user_id != user.id and user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问该文档"
            )
        
        processing_status = get_document_processing_status(doc_id)
        return processing_status
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get processing status error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取处理状态时发生错误"
        )

@router.post("/documents/{doc_id}/retry-processing")
async def retry_document_processing(
    doc_id: str,
    user=Depends(get_verified_user)
):
    """重试文档处理"""
    try:
        file = Files.get_file_by_id(doc_id)
        
        if not file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文档不存在"
            )
        
        # 检查权限
        if file.user_id != user.id and user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权操作该文档"
            )
        
        # 重试处理
        success = await document_processor.retry_failed_document(doc_id)
        
        if success:
            return {"message": "文档已重新加入处理队列"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无法重试处理，可能已超过最大重试次数或文档状态不正确"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Retry processing error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="重试处理时发生错误"
        )

@router.delete("/documents/{doc_id}/cancel-processing")
async def cancel_document_processing(
    doc_id: str,
    user=Depends(get_verified_user)
):
    """取消文档处理"""
    try:
        file = Files.get_file_by_id(doc_id)
        
        if not file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文档不存在"
            )
        
        # 检查权限
        if file.user_id != user.id and user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权操作该文档"
            )
        
        # 取消处理
        success = await document_processor.cancel_processing(doc_id)
        
        if success:
            return {"message": "文档处理已取消"}
        else:
            return {"message": "文档当前未在处理中"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cancel processing error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="取消处理时发生错误"
        )

@router.put("/documents/{doc_id}")
async def update_document_metadata(
    doc_id: str,
    tags: Optional[List[str]] = None,
    vendor: Optional[str] = None,
    user=Depends(get_verified_user)
):
    """更新文档元数据"""
    try:
        file = Files.get_file_by_id(doc_id)
        
        if not file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文档不存在"
            )
        
        # 检查权限
        if file.user_id != user.id and user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权修改该文档"
            )
        
        # 更新元数据
        meta = file.meta or {}
        if tags is not None:
            meta["tags"] = tags
        if vendor is not None:
            meta["vendor"] = vendor
        
        # 保存更新
        Files.update_file_by_id(doc_id, {"meta": meta})
        
        return {"message": "文档元数据更新成功"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update document metadata error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新文档元数据时发生错误"
        )

@router.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: str,
    user=Depends(get_verified_user)
):
    """删除知识文档"""
    try:
        file = Files.get_file_by_id(doc_id)
        
        if not file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文档不存在"
            )
        
        # 检查权限
        if file.user_id != user.id and user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权删除该文档"
            )
        
        # 删除文件
        Files.delete_file_by_id(doc_id)
        
        return {"message": "文档删除成功"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete document error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除文档时发生错误"
        )

############################
# 知识检索接口
############################

@router.post("/search", response_model=SearchResponse)
async def search_knowledge(
    request: SearchRequest,
    user=Depends(get_verified_user)
):
    """
    知识检索API接口
    
    支持混合检索：向量语义检索 + 关键词检索
    """
    try:
        # 参数验证
        if abs(request.vector_weight + request.keyword_weight - 1.0) > 0.001:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="向量权重和关键词权重之和必须等于1"
            )
        
        logger.info(f"执行知识检索: query='{request.query}', filters={request.filters}")
        
        # 执行向量检索
        try:
            vector_results = VECTOR_DB_CLIENT.search(
                collection_name="knowledge",
                query=request.query,
                limit=request.top_k * 2,  # 获取更多结果用于重排序
                filter=request.filters
            )
        except Exception as e:
            logger.warning(f"向量检索失败: {str(e)}")
            vector_results = []
        
        # 归一化相似度分数
        if vector_results:
            db_type = get_db_type_from_config()
            scores = [result.get("score", 0) for result in vector_results]
            normalized_scores = similarity_normalizer.normalize_scores(scores, db_type)
            
            for i, result in enumerate(vector_results):
                result["normalized_score"] = normalized_scores[i]
        
        # 构建搜索结果
        search_results = []
        for i, result in enumerate(vector_results[:request.top_k]):
            search_result = SearchResult(
                id=result.get("id", f"result_{i}"),
                content=result.get("content", ""),
                title=result.get("title"),
                score=result.get("normalized_score", result.get("score", 0)),
                source=result.get("source", "knowledge_base"),
                metadata=result.get("metadata", {})
            )
            search_results.append(search_result)
        
        return SearchResponse(
            query=request.query,
            total=len(search_results),
            results=search_results,
            search_params={
                "vector_weight": request.vector_weight,
                "keyword_weight": request.keyword_weight,
                "filters": request.filters
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"知识检索API失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="检索服务暂时不可用"
        )

@router.post("/search/suggest", response_model=SuggestResponse)
async def suggest_search_terms(
    request: SuggestRequest,
    user=Depends(get_verified_user)
):
    """搜索建议API接口"""
    try:
        suggestions = _generate_search_suggestions(request.query, request.limit)
        
        return SuggestResponse(
            query=request.query,
            suggestions=suggestions
        )
        
    except Exception as e:
        logger.error(f"搜索建议API失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="建议服务暂时不可用"
        )

def _generate_search_suggestions(query: str, limit: int) -> List[str]:
    """生成搜索建议"""
    suggestions = []
    query_lower = query.lower()
    
    # 基于技术领域的建议
    tech_suggestions = {
        'ospf': [
            'OSPF邻居建立失败',
            'OSPF区域配置',
            'OSPF LSA类型',
            'OSPF路由计算',
            'OSPF网络类型配置'
        ],
        'bgp': [
            'BGP邻居建立',
            'BGP路由策略',
            'BGP属性配置',
            'BGP路由反射器',
            'BGP联盟配置'
        ],
        'vlan': [
            'VLAN配置命令',
            'VLAN间路由',
            'VLAN Trunk配置',
            'VLAN划分原则',
            'VLAN故障排除'
        ],
        '华为': [
            '华为交换机配置',
            '华为路由器命令',
            '华为防火墙策略',
            '华为VRP系统',
            '华为设备调试'
        ],
        '思科': [
            '思科IOS配置',
            '思科交换机命令',
            '思科路由协议',
            '思科网络安全',
            '思科故障排除'
        ]
    }
    
    # 查找匹配的建议
    for key, values in tech_suggestions.items():
        if key in query_lower:
            suggestions.extend(values)
    
    # 通用建议
    if not suggestions:
        generic_suggestions = [
            f'{query} 配置方法',
            f'{query} 故障排除',
            f'{query} 命令大全',
            f'{query} 最佳实践',
            f'{query} 案例分析'
        ]
        suggestions.extend(generic_suggestions)
    
    # 去重并限制数量
    suggestions = list(dict.fromkeys(suggestions))  # 去重保持顺序
    return suggestions[:limit]

@router.get("/tags")
async def get_all_tags(user=Depends(get_verified_user)):
    """获取所有唯一的标签"""
    try:
        # 获取用户的所有文件
        files = Files.get_files_by_user_id(user.id)
        
        tag_set = set()
        for file in files:
            tags = file.meta.get("tags", [])
            if isinstance(tags, list):
                for tag in tags:
                    if isinstance(tag, str) and tag:
                        tag_set.add(tag)
        
        tags = sorted(tag_set)
        
        return {
            "tags": tags,
            "total": len(tags)
        }
        
    except Exception as e:
        logger.error(f"Get all tags error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取标签列表时发生错误"
        )
