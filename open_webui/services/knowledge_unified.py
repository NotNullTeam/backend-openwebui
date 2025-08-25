"""
知识模块统一服务实现

整合 knowledge 和 knowledge_migrated 模块的业务逻辑
"""

import os
import uuid
import time
import asyncio
import hashlib
import mimetypes
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func

from open_webui.internal.db import get_db
from open_webui.models.knowledge_unified import (
    KnowledgeBase,
    Document,
    DocumentChunk,
    KnowledgeBaseDocument,
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
    SearchResult,
    SearchSuggestionRequest,
    SearchSuggestionResponse,
    KnowledgeStatsResponse,
    ProcessingStatus,
    SearchType,
    IKnowledgeService,
    IDocumentService,
    ISearchService
)
from open_webui.retrieval.vector.main import get_retrieval_vector_db
from open_webui.retrieval.loaders.main import Loader
from open_webui.services.document_processor import document_processor
from open_webui.storage.provider import Storage
from open_webui.config import DATA_DIR

import logging

logger = logging.getLogger(__name__)


class KnowledgeService(IKnowledgeService):
    """知识库管理服务"""
    
    def __init__(self):
        self.storage = Storage
    
    async def create_knowledge_base(self, user_id: str, data: KnowledgeBaseCreate) -> KnowledgeBaseResponse:
        """创建知识库"""
        with get_db() as db:
            # 检查名称重复
            existing = db.query(KnowledgeBase).filter(
                and_(
                    KnowledgeBase.user_id == user_id,
                    KnowledgeBase.name == data.name
                )
            ).first()
            
            if existing:
                raise ValueError(f"Knowledge base with name '{data.name}' already exists")
            
            # 创建知识库
            kb_id = str(uuid.uuid4())
            now = int(time.time())
            
            knowledge_base = KnowledgeBase(
                id=kb_id,
                user_id=user_id,
                name=data.name,
                description=data.description,
                tags=data.tags or [],
                category=data.category,
                access_control=data.access_control,
                settings=data.settings or {},
                stats={
                    "document_count": 0,
                    "total_size": 0,
                    "chunk_count": 0,
                    "vector_count": 0,
                    "last_activity": now
                },
                created_at=now,
                updated_at=now
            )
            
            db.add(knowledge_base)
            db.commit()
            db.refresh(knowledge_base)
            
            return KnowledgeBaseResponse.from_orm(knowledge_base)
    
    async def get_knowledge_base(self, user_id: str, kb_id: str) -> Optional[KnowledgeBaseResponse]:
        """获取知识库详情"""
        with get_db() as db:
            kb = db.query(KnowledgeBase).filter(
                and_(
                    KnowledgeBase.id == kb_id,
                    KnowledgeBase.user_id == user_id
                )
            ).first()
            
            if not kb:
                return None
            
            return KnowledgeBaseResponse.from_orm(kb)
    
    async def list_knowledge_bases(
        self, 
        user_id: str, 
        page: int = 1, 
        page_size: int = 20,
        search: Optional[str] = None,
        category: Optional[str] = None
    ) -> KnowledgeBaseListResponse:
        """获取知识库列表"""
        with get_db() as db:
            query = db.query(KnowledgeBase).filter(KnowledgeBase.user_id == user_id)
            
            # 搜索过滤
            if search:
                query = query.filter(
                    or_(
                        KnowledgeBase.name.ilike(f"%{search}%"),
                        KnowledgeBase.description.ilike(f"%{search}%")
                    )
                )
            
            # 分类过滤
            if category:
                query = query.filter(KnowledgeBase.category == category)
            
            # 总数
            total = query.count()
            
            # 分页
            offset = (page - 1) * page_size
            items = query.order_by(desc(KnowledgeBase.updated_at)).offset(offset).limit(page_size).all()
            
            return KnowledgeBaseListResponse(
                total=total,
                page=page,
                page_size=page_size,
                has_next=(offset + page_size) < total,
                has_prev=page > 1,
                items=[KnowledgeBaseResponse.from_orm(kb) for kb in items]
            )
    
    async def update_knowledge_base(self, user_id: str, kb_id: str, data: KnowledgeBaseUpdate) -> Optional[KnowledgeBaseResponse]:
        """更新知识库"""
        with get_db() as db:
            kb = db.query(KnowledgeBase).filter(
                and_(
                    KnowledgeBase.id == kb_id,
                    KnowledgeBase.user_id == user_id
                )
            ).first()
            
            if not kb:
                return None
            
            # 更新字段
            update_data = data.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(kb, field, value)
            
            kb.updated_at = int(time.time())
            
            db.commit()
            db.refresh(kb)
            
            return KnowledgeBaseResponse.from_orm(kb)
    
    async def delete_knowledge_base(self, user_id: str, kb_id: str) -> bool:
        """删除知识库"""
        with get_db() as db:
            kb = db.query(KnowledgeBase).filter(
                and_(
                    KnowledgeBase.id == kb_id,
                    KnowledgeBase.user_id == user_id
                )
            ).first()
            
            if not kb:
                return False
            
            # 删除关联关系（文档本身不删除）
            db.query(KnowledgeBaseDocument).filter(
                KnowledgeBaseDocument.knowledge_base_id == kb_id
            ).delete()
            
            # 删除知识库
            db.delete(kb)
            db.commit()
            
            return True
    
    async def add_document_to_knowledge_base(self, user_id: str, kb_id: str, doc_id: str, notes: Optional[str] = None) -> bool:
        """添加文档到知识库"""
        with get_db() as db:
            # 检查知识库和文档是否存在
            kb = db.query(KnowledgeBase).filter(
                and_(
                    KnowledgeBase.id == kb_id,
                    KnowledgeBase.user_id == user_id
                )
            ).first()
            
            if not kb:
                return False
            
            doc = db.query(Document).filter(
                and_(
                    Document.id == doc_id,
                    Document.user_id == user_id
                )
            ).first()
            
            if not doc:
                return False
            
            # 检查是否已经关联
            existing = db.query(KnowledgeBaseDocument).filter(
                and_(
                    KnowledgeBaseDocument.knowledge_base_id == kb_id,
                    KnowledgeBaseDocument.document_id == doc_id
                )
            ).first()
            
            if existing:
                return True  # 已经关联
            
            # 创建关联
            association = KnowledgeBaseDocument(
                knowledge_base_id=kb_id,
                document_id=doc_id,
                added_at=int(time.time()),
                added_by=user_id,
                notes=notes
            )
            
            db.add(association)
            
            # 更新知识库统计
            kb.stats["document_count"] = kb.stats.get("document_count", 0) + 1
            kb.stats["total_size"] = kb.stats.get("total_size", 0) + doc.file_size
            kb.stats["last_activity"] = int(time.time())
            kb.updated_at = int(time.time())
            
            db.commit()
            return True
    
    async def remove_document_from_knowledge_base(self, user_id: str, kb_id: str, doc_id: str) -> bool:
        """从知识库移除文档"""
        with get_db() as db:
            # 检查关联是否存在
            association = db.query(KnowledgeBaseDocument).filter(
                and_(
                    KnowledgeBaseDocument.knowledge_base_id == kb_id,
                    KnowledgeBaseDocument.document_id == doc_id
                )
            ).first()
            
            if not association:
                return False
            
            # 获取文档信息以更新统计
            doc = db.query(Document).filter(Document.id == doc_id).first()
            
            # 删除关联
            db.delete(association)
            
            # 更新知识库统计
            kb = db.query(KnowledgeBase).filter(
                and_(
                    KnowledgeBase.id == kb_id,
                    KnowledgeBase.user_id == user_id
                )
            ).first()
            
            if kb and doc:
                kb.stats["document_count"] = max(0, kb.stats.get("document_count", 0) - 1)
                kb.stats["total_size"] = max(0, kb.stats.get("total_size", 0) - doc.file_size)
                kb.stats["last_activity"] = int(time.time())
                kb.updated_at = int(time.time())
            
            db.commit()
            return True
    
    async def get_stats(self, user_id: str) -> KnowledgeStatsResponse:
        """获取整体统计信息"""
        with get_db() as db:
            # 知识库统计
            kb_count = db.query(KnowledgeBase).filter(KnowledgeBase.user_id == user_id).count()
            
            # 文档统计
            doc_query = db.query(Document).filter(Document.user_id == user_id)
            total_docs = doc_query.count()
            total_size = db.query(func.sum(Document.file_size)).filter(Document.user_id == user_id).scalar() or 0
            
            # 按状态统计
            status_stats = {}
            for status in ProcessingStatus:
                count = doc_query.filter(Document.processing_status == status.value).count()
                if count > 0:
                    status_stats[status.value] = count
            
            # 按类型统计
            type_stats = {}
            type_results = db.query(Document.content_type, func.count(Document.id)).filter(
                Document.user_id == user_id
            ).group_by(Document.content_type).all()
            
            for content_type, count in type_results:
                type_stats[content_type or "unknown"] = count
            
            # 分块和向量统计
            total_chunks = db.query(func.sum(Document.chunk_count)).filter(Document.user_id == user_id).scalar() or 0
            total_vectors = db.query(func.sum(Document.vector_count)).filter(Document.user_id == user_id).scalar() or 0
            
            # 最近上传
            recent_date = datetime.now() - timedelta(days=7)
            recent_uploads = doc_query.filter(Document.created_at >= int(recent_date.timestamp())).count()
            
            return KnowledgeStatsResponse(
                total_knowledge_bases=kb_count,
                total_documents=total_docs,
                total_size=total_size,
                total_chunks=total_chunks,
                total_vectors=total_vectors,
                documents_by_status=status_stats,
                documents_by_type=type_stats,
                recent_uploads=recent_uploads,
                recent_activities=[]  # TODO: 实现活动记录
            )
    
    async def get_knowledge_base_stats(self, user_id: str, kb_id: str) -> Optional[Dict[str, Any]]:
        """获取知识库统计信息"""
        with get_db() as db:
            kb = db.query(KnowledgeBase).filter(
                and_(
                    KnowledgeBase.id == kb_id,
                    KnowledgeBase.user_id == user_id
                )
            ).first()
            
            if not kb:
                return None
            
            # 获取关联文档的详细统计
            doc_ids = db.query(KnowledgeBaseDocument.document_id).filter(
                KnowledgeBaseDocument.knowledge_base_id == kb_id
            ).subquery()
            
            docs = db.query(Document).filter(Document.id.in_(doc_ids)).all()
            
            stats = kb.stats.copy()
            stats.update({
                "documents": len(docs),
                "processing_status": {},
                "content_types": {},
                "recent_activity": []
            })
            
            # 按状态统计
            for doc in docs:
                status = doc.processing_status
                stats["processing_status"][status] = stats["processing_status"].get(status, 0) + 1
                
                content_type = doc.content_type or "unknown"
                stats["content_types"][content_type] = stats["content_types"].get(content_type, 0) + 1
            
            return stats


class DocumentService(IDocumentService):
    """文档管理服务"""
    
    def __init__(self):
        self.storage = Storage
        self.upload_dir = Path(DATA_DIR) / "uploads" / "documents"
        self.upload_dir.mkdir(parents=True, exist_ok=True)
    
    async def upload_document(self, user_id: str, file_data: bytes, filename: str, data: DocumentCreate) -> DocumentUploadResponse:
        """上传文档"""
        try:
            # 生成文档ID和文件路径
            doc_id = str(uuid.uuid4())
            file_hash = hashlib.sha256(file_data).hexdigest()
            
            # 确定文件扩展名和MIME类型
            file_ext = Path(filename).suffix.lower()
            content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            
            # 保存文件
            safe_filename = f"{doc_id}{file_ext}"
            file_path = self.upload_dir / safe_filename
            
            with open(file_path, "wb") as f:
                f.write(file_data)
            
            # 创建文档记录
            now = int(time.time())
            
            with get_db() as db:
                document = Document(
                    id=doc_id,
                    user_id=user_id,
                    filename=safe_filename,
                    original_filename=filename,
                    file_path=str(file_path),
                    file_hash=file_hash,
                    file_size=len(file_data),
                    content_type=content_type,
                    processing_status=ProcessingStatus.UPLOADED,
                    processing_progress=0,
                    title=data.title or filename,
                    description=data.description,
                    tags=data.tags or [],
                    metadata=data.metadata or {},
                    access_control=data.access_control,
                    created_at=now,
                    updated_at=now
                )
                
                db.add(document)
                
                # 关联到知识库
                for kb_id in data.knowledge_base_ids:
                    association = KnowledgeBaseDocument(
                        knowledge_base_id=kb_id,
                        document_id=doc_id,
                        added_at=now,
                        added_by=user_id
                    )
                    db.add(association)
                
                db.commit()
            
            # 启动异步处理
            processing_started = False
            try:
                await document_processor.queue_document_for_processing(
                    doc_id, 
                    data.processing_params or {}
                )
                processing_started = True
            except Exception as e:
                logger.warning(f"Failed to start processing for document {doc_id}: {e}")
            
            return DocumentUploadResponse(
                document_id=doc_id,
                status="uploaded",
                message="Document uploaded successfully",
                processing_started=processing_started
            )
            
        except Exception as e:
            logger.error(f"Failed to upload document: {e}")
            raise
    
    async def get_document(self, user_id: str, doc_id: str) -> Optional[DocumentResponse]:
        """获取文档详情"""
        with get_db() as db:
            doc = db.query(Document).filter(
                and_(
                    Document.id == doc_id,
                    Document.user_id == user_id
                )
            ).first()
            
            if not doc:
                return None
            
            # 获取关联的知识库ID
            kb_ids = db.query(KnowledgeBaseDocument.knowledge_base_id).filter(
                KnowledgeBaseDocument.document_id == doc_id
            ).all()
            
            response = DocumentResponse.from_orm(doc)
            response.knowledge_bases = [kb_id[0] for kb_id in kb_ids]
            
            return response
    
    async def list_documents(
        self, 
        user_id: str, 
        kb_id: Optional[str] = None, 
        page: int = 1, 
        page_size: int = 20,
        status_filter: Optional[ProcessingStatus] = None,
        search: Optional[str] = None
    ) -> DocumentListResponse:
        """获取文档列表"""
        with get_db() as db:
            query = db.query(Document).filter(Document.user_id == user_id)
            
            # 知识库过滤
            if kb_id:
                doc_ids = db.query(KnowledgeBaseDocument.document_id).filter(
                    KnowledgeBaseDocument.knowledge_base_id == kb_id
                ).subquery()
                query = query.filter(Document.id.in_(doc_ids))
            
            # 状态过滤
            if status_filter:
                query = query.filter(Document.processing_status == status_filter.value)
            
            # 搜索过滤
            if search:
                query = query.filter(
                    or_(
                        Document.title.ilike(f"%{search}%"),
                        Document.original_filename.ilike(f"%{search}%"),
                        Document.description.ilike(f"%{search}%")
                    )
                )
            
            # 总数
            total = query.count()
            
            # 分页
            offset = (page - 1) * page_size
            items = query.order_by(desc(Document.created_at)).offset(offset).limit(page_size).all()
            
            # 转换为响应对象
            responses = []
            for doc in items:
                # 获取关联的知识库ID
                kb_ids = db.query(KnowledgeBaseDocument.knowledge_base_id).filter(
                    KnowledgeBaseDocument.document_id == doc.id
                ).all()
                
                response = DocumentResponse.from_orm(doc)
                response.knowledge_bases = [kb_id[0] for kb_id in kb_ids]
                responses.append(response)
            
            return DocumentListResponse(
                total=total,
                page=page,
                page_size=page_size,
                has_next=(offset + page_size) < total,
                has_prev=page > 1,
                items=responses
            )
    
    async def update_document(self, user_id: str, doc_id: str, data: DocumentUpdate) -> Optional[DocumentResponse]:
        """更新文档"""
        with get_db() as db:
            doc = db.query(Document).filter(
                and_(
                    Document.id == doc_id,
                    Document.user_id == user_id
                )
            ).first()
            
            if not doc:
                return None
            
            # 更新字段
            update_data = data.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(doc, field, value)
            
            doc.updated_at = int(time.time())
            
            db.commit()
            db.refresh(doc)
            
            return DocumentResponse.from_orm(doc)
    
    async def delete_document(self, user_id: str, doc_id: str) -> bool:
        """删除文档"""
        with get_db() as db:
            doc = db.query(Document).filter(
                and_(
                    Document.id == doc_id,
                    Document.user_id == user_id
                )
            ).first()
            
            if not doc:
                return False
            
            # 删除物理文件
            if doc.file_path and os.path.exists(doc.file_path):
                try:
                    os.remove(doc.file_path)
                except Exception as e:
                    logger.warning(f"Failed to delete file {doc.file_path}: {e}")
            
            # 删除向量数据
            try:
                vector_db = get_retrieval_vector_db()
                if vector_db:
                    # TODO: 实现向量删除
                    pass
            except Exception as e:
                logger.warning(f"Failed to delete vectors for document {doc_id}: {e}")
            
            # 删除关联关系
            db.query(KnowledgeBaseDocument).filter(
                KnowledgeBaseDocument.document_id == doc_id
            ).delete()
            
            # 删除分块
            db.query(DocumentChunk).filter(DocumentChunk.document_id == doc_id).delete()
            
            # 删除文档
            db.delete(doc)
            db.commit()
            
            return True
    
    async def get_processing_status(self, user_id: str, doc_id: str) -> Dict[str, Any]:
        """获取处理状态"""
        with get_db() as db:
            doc = db.query(Document).filter(
                and_(
                    Document.id == doc_id,
                    Document.user_id == user_id
                )
            ).first()
            
            if not doc:
                raise ValueError("Document not found")
            
            return {
                "document_id": doc_id,
                "status": doc.processing_status,
                "progress": doc.processing_progress,
                "error": doc.processing_error,
                "created_at": doc.created_at,
                "updated_at": doc.updated_at,
                "processed_at": doc.processed_at
            }
    
    async def retry_processing(self, user_id: str, doc_id: str) -> bool:
        """重试处理"""
        with get_db() as db:
            doc = db.query(Document).filter(
                and_(
                    Document.id == doc_id,
                    Document.user_id == user_id
                )
            ).first()
            
            if not doc:
                return False
            
            # 只有失败状态才能重试
            if doc.processing_status not in [ProcessingStatus.FAILED, ProcessingStatus.CANCELLED]:
                return False
            
            # 重置状态
            doc.processing_status = ProcessingStatus.QUEUED
            doc.processing_progress = 0
            doc.processing_error = None
            doc.updated_at = int(time.time())
            
            db.commit()
            
            # 重新加入处理队列
            try:
                await document_processor.queue_document_for_processing(doc_id, {})
                return True
            except Exception as e:
                logger.error(f"Failed to retry processing for document {doc_id}: {e}")
                return False
    
    async def cancel_processing(self, user_id: str, doc_id: str) -> bool:
        """取消处理"""
        with get_db() as db:
            doc = db.query(Document).filter(
                and_(
                    Document.id == doc_id,
                    Document.user_id == user_id
                )
            ).first()
            
            if not doc:
                return False
            
            # 只有处理中的状态才能取消
            if doc.processing_status not in [ProcessingStatus.QUEUED, ProcessingStatus.PROCESSING]:
                return False
            
            # 设置为取消状态
            doc.processing_status = ProcessingStatus.CANCELLED
            doc.updated_at = int(time.time())
            
            db.commit()
            
            # 通知处理器取消
            try:
                await document_processor.cancel_document_processing(doc_id)
                return True
            except Exception as e:
                logger.error(f"Failed to cancel processing for document {doc_id}: {e}")
                return False
    
    async def get_file_info(self, user_id: str, doc_id: str) -> Optional[Dict[str, Any]]:
        """获取文件信息"""
        with get_db() as db:
            doc = db.query(Document).filter(
                and_(
                    Document.id == doc_id,
                    Document.user_id == user_id
                )
            ).first()
            
            if not doc:
                return None
            
            return {
                "file_path": doc.file_path,
                "original_filename": doc.original_filename,
                "content_type": doc.content_type,
                "file_size": doc.file_size
            }
    
    async def get_document_stats(self, user_id: str, doc_id: str) -> Optional[Dict[str, Any]]:
        """获取文档统计信息"""
        with get_db() as db:
            doc = db.query(Document).filter(
                and_(
                    Document.id == doc_id,
                    Document.user_id == user_id
                )
            ).first()
            
            if not doc:
                return None
            
            # 获取分块统计
            chunk_count = db.query(DocumentChunk).filter(DocumentChunk.document_id == doc_id).count()
            
            return {
                "document_id": doc_id,
                "file_size": doc.file_size,
                "chunk_count": chunk_count,
                "vector_count": doc.vector_count,
                "page_count": doc.page_count,
                "word_count": doc.word_count,
                "processing_status": doc.processing_status,
                "created_at": doc.created_at,
                "processed_at": doc.processed_at
            }


class SearchService(ISearchService):
    """搜索服务"""
    
    def __init__(self):
        self.vector_db = get_retrieval_vector_db()
    
    async def search(self, user_id: str, request: SearchRequest) -> SearchResponse:
        """执行搜索"""
        start_time = time.time()
        
        try:
            # 权限过滤：只搜索用户有权限的文档
            with get_db() as db:
                accessible_docs = db.query(Document.id).filter(Document.user_id == user_id)
                
                # 知识库过滤
                if request.knowledge_base_ids:
                    kb_doc_ids = db.query(KnowledgeBaseDocument.document_id).filter(
                        KnowledgeBaseDocument.knowledge_base_id.in_(request.knowledge_base_ids)
                    ).subquery()
                    # 修复SQLAlchemy警告：显式使用select()
                    accessible_docs = accessible_docs.filter(Document.id.in_(
                        db.query(KnowledgeBaseDocument.document_id).filter(
                            KnowledgeBaseDocument.knowledge_base_id.in_(request.knowledge_base_ids)
                        ).scalar_subquery()
                    ))
                
                # 文档过滤
                if request.document_ids:
                    accessible_docs = accessible_docs.filter(Document.id.in_(request.document_ids))
                
                doc_ids = [doc[0] for doc in accessible_docs.all()]
            
            if not doc_ids:
                return SearchResponse(
                    query=request.query,
                    search_type=request.search_type,
                    total_results=0,
                    results=[],
                    search_time=time.time() - start_time,
                    search_params=request.dict()
                )
            
            # 执行搜索
            results = []
            
            if request.search_type == SearchType.VECTOR:
                results = await self._vector_search(request, doc_ids)
            elif request.search_type == SearchType.KEYWORD:
                results = await self._keyword_search(request, doc_ids)
            elif request.search_type == SearchType.HYBRID:
                results = await self._hybrid_search(request, doc_ids)
            else:
                results = await self._hybrid_search(request, doc_ids)
            
            # 过滤和排序
            results = [r for r in results if r.score >= request.score_threshold]
            results = sorted(results, key=lambda x: x.score, reverse=True)
            results = results[:request.top_k]
            
            return SearchResponse(
                query=request.query,
                search_type=request.search_type,
                total_results=len(results),
                results=results,
                search_time=time.time() - start_time,
                search_params=request.dict()
            )
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise
    
    async def _vector_search(self, request: SearchRequest, doc_ids: List[str]) -> List[SearchResult]:
        """向量搜索"""
        # TODO: 实现向量搜索逻辑
        return []
    
    async def _keyword_search(self, request: SearchRequest, doc_ids: List[str]) -> List[SearchResult]:
        """关键词搜索"""
        # TODO: 实现关键词搜索逻辑
        return []
    
    async def _hybrid_search(self, request: SearchRequest, doc_ids: List[str]) -> List[SearchResult]:
        """混合搜索"""
        # TODO: 实现混合搜索逻辑
        return []
    
    async def get_suggestions(self, user_id: str, request: SearchSuggestionRequest) -> SearchSuggestionResponse:
        """获取搜索建议"""
        # TODO: 实现搜索建议逻辑
        return SearchSuggestionResponse(
            query=request.query,
            suggestions=[]
        )
    
    async def get_search_history(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """获取搜索历史"""
        # TODO: 实现搜索历史逻辑
        return []
