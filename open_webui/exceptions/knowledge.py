"""
知识模块自定义异常类

定义知识库和文档管理相关的异常类型
"""

from typing import Optional, Dict, Any
from fastapi import HTTPException, status


class KnowledgeBaseException(Exception):
    """知识库基础异常类"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class KnowledgeBaseNotFoundError(KnowledgeBaseException):
    """知识库未找到异常"""
    def __init__(self, kb_id: str):
        super().__init__(f"Knowledge base with ID '{kb_id}' not found")
        self.kb_id = kb_id


class KnowledgeBaseAlreadyExistsError(KnowledgeBaseException):
    """知识库已存在异常"""
    def __init__(self, name: str, user_id: str):
        super().__init__(f"Knowledge base with name '{name}' already exists for user {user_id}")
        self.name = name
        self.user_id = user_id


class KnowledgeBaseAccessDeniedError(KnowledgeBaseException):
    """知识库访问被拒绝异常"""
    def __init__(self, kb_id: str, access_type: str, user_id: str):
        super().__init__(f"Access denied: User {user_id} cannot {access_type} knowledge base {kb_id}")
        self.kb_id = kb_id
        self.access_type = access_type
        self.user_id = user_id


class DocumentException(Exception):
    """文档基础异常类"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class DocumentNotFoundError(DocumentException):
    """文档未找到异常"""
    def __init__(self, doc_id: str):
        super().__init__(f"Document with ID '{doc_id}' not found")
        self.doc_id = doc_id


class DocumentUploadError(DocumentException):
    """文档上传异常"""
    def __init__(self, filename: str, reason: str):
        super().__init__(f"Failed to upload document '{filename}': {reason}")
        self.filename = filename
        self.reason = reason


class DocumentProcessingError(DocumentException):
    """文档处理异常"""
    def __init__(self, doc_id: str, stage: str, reason: str):
        super().__init__(f"Document processing failed at {stage} for document {doc_id}: {reason}")
        self.doc_id = doc_id
        self.stage = stage
        self.reason = reason


class DocumentAccessDeniedError(DocumentException):
    """文档访问被拒绝异常"""
    def __init__(self, doc_id: str, access_type: str, user_id: str):
        super().__init__(f"Access denied: User {user_id} cannot {access_type} document {doc_id}")
        self.doc_id = doc_id
        self.access_type = access_type
        self.user_id = user_id


class DocumentFormatError(DocumentException):
    """文档格式异常"""
    def __init__(self, filename: str, supported_formats: list):
        super().__init__(f"Unsupported document format for '{filename}'. Supported formats: {', '.join(supported_formats)}")
        self.filename = filename
        self.supported_formats = supported_formats


class DocumentSizeError(DocumentException):
    """文档大小异常"""
    def __init__(self, filename: str, size: int, max_size: int):
        super().__init__(f"Document '{filename}' size ({size} bytes) exceeds maximum allowed size ({max_size} bytes)")
        self.filename = filename
        self.size = size
        self.max_size = max_size


class SearchException(Exception):
    """搜索基础异常类"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class SearchQueryError(SearchException):
    """搜索查询异常"""
    def __init__(self, query: str, reason: str):
        super().__init__(f"Invalid search query '{query}': {reason}")
        self.query = query
        self.reason = reason


class SearchIndexError(SearchException):
    """搜索索引异常"""
    def __init__(self, index_name: str, reason: str):
        super().__init__(f"Search index error for '{index_name}': {reason}")
        self.index_name = index_name
        self.reason = reason


class VectorStoreError(SearchException):
    """向量存储异常"""
    def __init__(self, operation: str, reason: str):
        super().__init__(f"Vector store operation '{operation}' failed: {reason}")
        self.operation = operation
        self.reason = reason


# HTTP异常映射
def map_to_http_exception(exc: Exception) -> HTTPException:
    """将自定义异常映射到HTTP异常"""
    
    if isinstance(exc, KnowledgeBaseNotFoundError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "knowledge_base_not_found",
                "message": exc.message,
                "kb_id": exc.kb_id
            }
        )
    
    elif isinstance(exc, KnowledgeBaseAlreadyExistsError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "knowledge_base_already_exists",
                "message": exc.message,
                "name": exc.name,
                "user_id": exc.user_id
            }
        )
    
    elif isinstance(exc, KnowledgeBaseAccessDeniedError):
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "knowledge_base_access_denied",
                "message": exc.message,
                "kb_id": exc.kb_id,
                "access_type": exc.access_type
            }
        )
    
    elif isinstance(exc, DocumentNotFoundError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "document_not_found",
                "message": exc.message,
                "doc_id": exc.doc_id
            }
        )
    
    elif isinstance(exc, DocumentUploadError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "document_upload_failed",
                "message": exc.message,
                "filename": exc.filename,
                "reason": exc.reason
            }
        )
    
    elif isinstance(exc, DocumentProcessingError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "document_processing_failed",
                "message": exc.message,
                "doc_id": exc.doc_id,
                "stage": exc.stage,
                "reason": exc.reason
            }
        )
    
    elif isinstance(exc, DocumentAccessDeniedError):
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "document_access_denied",
                "message": exc.message,
                "doc_id": exc.doc_id,
                "access_type": exc.access_type
            }
        )
    
    elif isinstance(exc, DocumentFormatError):
        return HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail={
                "error": "unsupported_document_format",
                "message": exc.message,
                "filename": exc.filename,
                "supported_formats": exc.supported_formats
            }
        )
    
    elif isinstance(exc, DocumentSizeError):
        return HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={
                "error": "document_too_large",
                "message": exc.message,
                "filename": exc.filename,
                "size": exc.size,
                "max_size": exc.max_size
            }
        )
    
    elif isinstance(exc, SearchQueryError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_search_query",
                "message": exc.message,
                "query": exc.query,
                "reason": exc.reason
            }
        )
    
    elif isinstance(exc, SearchIndexError):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "search_index_error",
                "message": exc.message,
                "index_name": exc.index_name,
                "reason": exc.reason
            }
        )
    
    elif isinstance(exc, VectorStoreError):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "vector_store_error",
                "message": exc.message,
                "operation": exc.operation,
                "reason": exc.reason
            }
        )
    
    else:
        # 通用异常处理
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "internal_server_error",
                "message": "An unexpected error occurred",
                "type": type(exc).__name__
            }
        )


# 错误码常量
class ErrorCodes:
    # 知识库错误
    KNOWLEDGE_BASE_NOT_FOUND = "knowledge_base_not_found"
    KNOWLEDGE_BASE_ALREADY_EXISTS = "knowledge_base_already_exists"
    KNOWLEDGE_BASE_ACCESS_DENIED = "knowledge_base_access_denied"
    
    # 文档错误
    DOCUMENT_NOT_FOUND = "document_not_found"
    DOCUMENT_UPLOAD_FAILED = "document_upload_failed"
    DOCUMENT_PROCESSING_FAILED = "document_processing_failed"
    DOCUMENT_ACCESS_DENIED = "document_access_denied"
    UNSUPPORTED_DOCUMENT_FORMAT = "unsupported_document_format"
    DOCUMENT_TOO_LARGE = "document_too_large"
    
    # 搜索错误
    INVALID_SEARCH_QUERY = "invalid_search_query"
    SEARCH_INDEX_ERROR = "search_index_error"
    VECTOR_STORE_ERROR = "vector_store_error"
    
    # 通用错误
    INTERNAL_SERVER_ERROR = "internal_server_error"
    VALIDATION_ERROR = "validation_error"
    PERMISSION_DENIED = "permission_denied"
