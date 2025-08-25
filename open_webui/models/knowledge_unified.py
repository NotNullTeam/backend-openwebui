"""
知识模块整合实施方案

统一 knowledge 和 knowledge_migrated 模块的数据模型、API接口和业务逻辑
"""

from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, Text, JSON, BigInteger, Integer, ForeignKey, Index
from sqlalchemy.orm import relationship
from open_webui.internal.db import Base


# ==================== 枚举定义 ====================

class ProcessingStatus(str, Enum):
    """文档处理状态"""
    UPLOADED = "uploaded"
    QUEUED = "queued"
    PROCESSING = "processing"
    CHUNKING = "chunking"
    VECTORIZING = "vectorizing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


class SearchType(str, Enum):
    """搜索类型"""
    HYBRID = "hybrid"        # 混合搜索（默认）
    VECTOR = "vector"        # 向量搜索
    KEYWORD = "keyword"      # 关键词搜索
    SEMANTIC = "semantic"    # 语义搜索
    FULLTEXT = "fulltext"    # 全文搜索


class ChunkType(str, Enum):
    """分块类型"""
    TEXT = "text"
    TABLE = "table"
    IMAGE = "image"
    FORMULA = "formula"
    HEADER = "header"
    FOOTER = "footer"


# ==================== 数据库模型 ====================

class KnowledgeBase(Base):
    """知识库表 - 整合原 knowledge 表功能"""
    __tablename__ = "knowledge_bases"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text)
    
    # 标签和分类
    tags = Column(JSON, default=lambda: [])
    category = Column(String)
    
    # 访问控制（继承原有细粒度控制）
    access_control = Column(JSON)
    
    # 知识库设置
    settings = Column(JSON, default=lambda: {
        "auto_process": True,
        "chunk_size": 1000,
        "chunk_overlap": 200,
        "enable_ocr": True,
        "enable_formula": True,
        "vector_model": "default"
    })
    
    # 统计信息
    stats = Column(JSON, default=lambda: {
        "document_count": 0,
        "total_size": 0,
        "chunk_count": 0,
        "vector_count": 0,
        "last_activity": None
    })
    
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)
    
    # 关系
    documents = relationship("Document", secondary="knowledge_base_documents", back_populates="knowledge_bases")
    
    # 索引
    __table_args__ = (
        Index('idx_knowledge_bases_user_id', 'user_id'),
        Index('idx_knowledge_bases_name', 'name'),
        Index('idx_knowledge_bases_category', 'category'),
        Index('idx_knowledge_bases_created_at', 'created_at'),
    )


class Document(Base):
    """文档表 - 整合 files 表和 migrated 模块功能"""
    __tablename__ = "documents"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)
    
    # 文件信息
    filename = Column(String, nullable=False)
    original_filename = Column(String, nullable=False)
    file_path = Column(String)
    file_hash = Column(String)
    file_size = Column(BigInteger)
    content_type = Column(String)
    
    # 处理状态
    processing_status = Column(String, default=ProcessingStatus.UPLOADED)
    processing_progress = Column(Integer, default=0)
    processing_error = Column(Text)
    processing_params = Column(JSON, default=lambda: {})
    
    # 文档元数据
    title = Column(String)
    description = Column(Text)
    tags = Column(JSON, default=lambda: [])
    doc_metadata = Column(JSON, default=lambda: {})
    
    # 内容统计
    page_count = Column(Integer)
    word_count = Column(Integer)
    chunk_count = Column(Integer, default=0)
    vector_count = Column(Integer, default=0)
    
    # 访问控制
    access_control = Column(JSON)
    
    # 时间戳
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)
    processed_at = Column(BigInteger)
    
    # 关系
    knowledge_bases = relationship("KnowledgeBase", secondary="knowledge_base_documents", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")
    
    # 索引
    __table_args__ = (
        Index('idx_documents_user_id', 'user_id'),
        Index('idx_documents_filename', 'filename'),
        Index('idx_documents_file_hash', 'file_hash'),
        Index('idx_documents_processing_status', 'processing_status'),
        Index('idx_documents_created_at', 'created_at'),
        Index('idx_documents_content_type', 'content_type'),
    )


class DocumentChunk(Base):
    """文档分块表"""
    __tablename__ = "document_chunks"

    id = Column(String, primary_key=True)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    
    # 分块信息
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    title = Column(String)
    chunk_type = Column(String, default=ChunkType.TEXT)
    
    # 位置信息
    page_number = Column(Integer)
    start_char = Column(Integer)
    end_char = Column(Integer)
    
    # 向量信息
    vector_id = Column(String)
    embedding_model = Column(String)
    
    # 元数据
    doc_metadata = Column(JSON, default=lambda: {})
    
    created_at = Column(BigInteger, nullable=False)
    
    # 关系
    document = relationship("Document", back_populates="chunks")
    
    # 索引
    __table_args__ = (
        Index('idx_document_chunks_document_id', 'document_id'),
        Index('idx_document_chunks_chunk_index', 'document_id', 'chunk_index'),
        Index('idx_document_chunks_vector_id', 'vector_id'),
    )


class KnowledgeBaseDocument(Base):
    """知识库-文档关联表"""
    __tablename__ = "knowledge_base_documents"

    knowledge_base_id = Column(String, ForeignKey("knowledge_bases.id"), primary_key=True)
    document_id = Column(String, ForeignKey("documents.id"), primary_key=True)
    
    # 关联信息
    added_at = Column(BigInteger, nullable=False)
    added_by = Column(String, nullable=False)
    notes = Column(Text)
    
    # 关联特定设置
    settings = Column(JSON, default=lambda: {})
    
    # 索引
    __table_args__ = (
        Index('idx_kb_doc_knowledge_base_id', 'knowledge_base_id'),
        Index('idx_kb_doc_document_id', 'document_id'),
        Index('idx_kb_doc_added_at', 'added_at'),
    )


# ==================== Pydantic 模型 ====================

class KnowledgeBaseBase(BaseModel):
    """知识库基础模型"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    tags: List[str] = Field(default_factory=list)
    category: Optional[str] = None
    access_control: Optional[Dict[str, Any]] = None
    settings: Optional[Dict[str, Any]] = None


class KnowledgeBaseCreate(KnowledgeBaseBase):
    """创建知识库请求"""
    pass


class KnowledgeBaseUpdate(BaseModel):
    """更新知识库请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    tags: Optional[List[str]] = None
    category: Optional[str] = None
    access_control: Optional[Dict[str, Any]] = None
    settings: Optional[Dict[str, Any]] = None


class KnowledgeBaseResponse(KnowledgeBaseBase):
    """知识库响应"""
    id: str
    user_id: str
    stats: Dict[str, Any]
    created_at: int
    updated_at: int
    
    class Config:
        from_attributes = True


class DocumentBase(BaseModel):
    """文档基础模型"""
    title: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    doc_metadata: Dict[str, Any] = Field(default_factory=dict)
    access_control: Optional[Dict[str, Any]] = None


class DocumentCreate(DocumentBase):
    """创建文档请求"""
    knowledge_base_ids: List[str] = Field(default_factory=list)
    processing_params: Dict[str, Any] = Field(default_factory=dict)


class DocumentUpdate(BaseModel):
    """更新文档请求"""
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    doc_metadata: Optional[Dict[str, Any]] = None
    access_control: Optional[Dict[str, Any]] = None


class DocumentResponse(DocumentBase):
    """文档响应"""
    id: str
    user_id: str
    filename: str
    original_filename: str
    file_size: int
    content_type: str
    processing_status: ProcessingStatus
    processing_progress: int
    processing_error: Optional[str] = None
    chunk_count: int
    vector_count: int
    knowledge_bases: List[str] = Field(default_factory=list)  # 知识库ID列表
    created_at: int
    updated_at: int
    processed_at: Optional[int] = None
    
    class Config:
        from_attributes = True


class DocumentUploadResponse(BaseModel):
    """文档上传响应"""
    document_id: str
    status: str
    message: str
    processing_started: bool = False


class SearchRequest(BaseModel):
    """搜索请求"""
    query: str = Field(..., min_length=1, max_length=500)
    search_type: SearchType = SearchType.HYBRID
    knowledge_base_ids: List[str] = Field(default_factory=list)
    document_ids: List[str] = Field(default_factory=list)
    
    # 搜索参数
    top_k: int = Field(10, ge=1, le=50)
    score_threshold: float = Field(0.0, ge=0.0, le=1.0)
    
    # 权重配置（混合搜索）
    vector_weight: float = Field(0.7, ge=0.0, le=1.0)
    keyword_weight: float = Field(0.3, ge=0.0, le=1.0)
    
    # 过滤条件
    filters: Dict[str, Any] = Field(default_factory=dict)
    
    # 返回设置
    include_content: bool = True
    include_metadata: bool = True
    max_content_length: int = Field(500, ge=100, le=2000)


class SearchResult(BaseModel):
    """搜索结果项"""
    id: str
    document_id: str
    chunk_id: Optional[str] = None
    title: Optional[str] = None
    content: str
    score: float
    source: str
    
    # 位置信息
    page_number: Optional[int] = None
    chunk_index: Optional[int] = None
    
    # 元数据
    metadata: Dict[str, Any] = Field(default_factory=dict, alias="doc_metadata")
    
    # 高亮信息
    highlights: List[str] = Field(default_factory=list)


class SearchResponse(BaseModel):
    """搜索响应"""
    query: str
    search_type: SearchType
    total_results: int
    results: List[SearchResult]
    
    # 搜索统计
    search_time: float
    vector_search_time: Optional[float] = None
    keyword_search_time: Optional[float] = None
    
    # 搜索参数
    search_params: Dict[str, Any]
    
    # 建议
    suggestions: List[str] = Field(default_factory=list)


class SearchSuggestionRequest(BaseModel):
    """搜索建议请求"""
    query: str = Field(..., min_length=1, max_length=100)
    knowledge_base_ids: List[str] = Field(default_factory=list)
    limit: int = Field(10, ge=1, le=20)


class SearchSuggestionResponse(BaseModel):
    """搜索建议响应"""
    query: str
    suggestions: List[str]


class KnowledgeStatsResponse(BaseModel):
    """知识库统计响应"""
    total_knowledge_bases: int
    total_documents: int
    total_size: int
    total_chunks: int
    total_vectors: int
    
    # 按状态统计
    documents_by_status: Dict[str, int]
    
    # 按类型统计
    documents_by_type: Dict[str, int]
    
    # 最近活动
    recent_uploads: int
    recent_activities: List[Dict[str, Any]]


# ==================== 响应模型 ====================

class BaseResponse(BaseModel):
    """基础响应模型"""
    success: bool = True
    message: str = ""
    timestamp: int = Field(default_factory=lambda: int(datetime.now().timestamp()))


class ErrorResponse(BaseResponse):
    """错误响应模型"""
    success: bool = False
    error_code: str
    error_details: Optional[Dict[str, Any]] = None


class ListResponse(BaseModel):
    """列表响应基础模型"""
    total: int
    page: int = 1
    page_size: int = 20
    has_next: bool = False
    has_prev: bool = False


class KnowledgeBaseListResponse(ListResponse):
    """知识库列表响应"""
    items: List[KnowledgeBaseResponse]


class DocumentListResponse(ListResponse):
    """文档列表响应"""
    items: List[DocumentResponse]


# ==================== 业务逻辑接口 ====================

class IKnowledgeService:
    """知识管理服务接口"""
    
    async def create_knowledge_base(self, user_id: str, data: KnowledgeBaseCreate) -> KnowledgeBaseResponse:
        """创建知识库"""
        raise NotImplementedError
    
    async def get_knowledge_base(self, user_id: str, kb_id: str) -> Optional[KnowledgeBaseResponse]:
        """获取知识库详情"""
        raise NotImplementedError
    
    async def list_knowledge_bases(self, user_id: str, page: int = 1, page_size: int = 20) -> KnowledgeBaseListResponse:
        """获取知识库列表"""
        raise NotImplementedError
    
    async def update_knowledge_base(self, user_id: str, kb_id: str, data: KnowledgeBaseUpdate) -> Optional[KnowledgeBaseResponse]:
        """更新知识库"""
        raise NotImplementedError
    
    async def delete_knowledge_base(self, user_id: str, kb_id: str) -> bool:
        """删除知识库"""
        raise NotImplementedError


class IDocumentService:
    """文档管理服务接口"""
    
    async def upload_document(self, user_id: str, file_data: bytes, filename: str, data: DocumentCreate) -> DocumentUploadResponse:
        """上传文档"""
        raise NotImplementedError
    
    async def get_document(self, user_id: str, doc_id: str) -> Optional[DocumentResponse]:
        """获取文档详情"""
        raise NotImplementedError
    
    async def list_documents(self, user_id: str, kb_id: Optional[str] = None, page: int = 1, page_size: int = 20) -> DocumentListResponse:
        """获取文档列表"""
        raise NotImplementedError
    
    async def update_document(self, user_id: str, doc_id: str, data: DocumentUpdate) -> Optional[DocumentResponse]:
        """更新文档"""
        raise NotImplementedError
    
    async def delete_document(self, user_id: str, doc_id: str) -> bool:
        """删除文档"""
        raise NotImplementedError
    
    async def get_processing_status(self, user_id: str, doc_id: str) -> Dict[str, Any]:
        """获取处理状态"""
        raise NotImplementedError
    
    async def retry_processing(self, user_id: str, doc_id: str) -> bool:
        """重试处理"""
        raise NotImplementedError


class ISearchService:
    """搜索服务接口"""
    
    async def search(self, user_id: str, request: SearchRequest) -> SearchResponse:
        """执行搜索"""
        raise NotImplementedError
    
    async def get_suggestions(self, user_id: str, request: SearchSuggestionRequest) -> SearchSuggestionResponse:
        """获取搜索建议"""
        raise NotImplementedError
    
    async def get_search_history(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """获取搜索历史"""
        raise NotImplementedError


# ==================== 配置模型 ====================

class KnowledgeConfig(BaseModel):
    """知识模块配置"""
    
    # 文件上传配置
    max_file_size: int = 50 * 1024 * 1024  # 50MB
    max_image_size: int = 10 * 1024 * 1024  # 10MB
    allowed_extensions: List[str] = [
        'pdf', 'doc', 'docx', 'txt', 'md', 'rtf', 'odt',
        'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'svg',
        'zip', 'tar', 'gz', 'rar', '7z'
    ]
    
    # 处理配置
    default_chunk_size: int = 1000
    default_chunk_overlap: int = 200
    max_chunks_per_document: int = 10000
    
    # 搜索配置
    default_search_limit: int = 10
    max_search_limit: int = 50
    search_timeout: int = 30
    
    # 向量配置
    default_vector_model: str = "text-embedding-ada-002"
    vector_dimension: int = 1536
    
    # 缓存配置
    enable_cache: bool = True
    cache_ttl: int = 3600  # 1小时
    
    # 异步处理配置
    processing_queue_size: int = 100
    max_concurrent_processing: int = 5
    processing_timeout: int = 1800  # 30分钟
