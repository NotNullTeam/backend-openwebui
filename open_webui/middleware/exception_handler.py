"""
知识模块异常处理中间件

提供统一的异常处理和错误响应格式
"""

import logging
import traceback
import time
from typing import Any, Dict
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exception_handlers import http_exception_handler
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import ValidationError

from open_webui.exceptions.knowledge import (
    KnowledgeBaseException,
    KnowledgeBaseNotFoundError,
    KnowledgeBaseAlreadyExistsError,
    KnowledgeBaseAccessDeniedError,
    DocumentException,
    DocumentNotFoundError,
    DocumentAccessDeniedError,
    DocumentUploadError,
    DocumentFormatError,
    DocumentSizeError,
    SearchException,
    SearchQueryError
)

logger = logging.getLogger(__name__)


async def knowledge_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    知识模块异常处理器
    
    处理知识库、文档和搜索相关的异常，返回统一格式的错误响应
    """
    
    # 记录异常信息
    logger.error(f"Exception occurred in {request.url.path}: {exc}")
    logger.error(f"Exception traceback: {traceback.format_exc()}")
    
    # 生成请求ID用于跟踪
    request_id = getattr(request.state, 'request_id', str(int(time.time() * 1000)))
    
    try:
        # 处理自定义知识库相关异常
        if isinstance(exc, (KnowledgeBaseException, DocumentException, SearchException)):
            http_exc = map_to_http_exception(exc)
            
            # 添加额外的调试信息
            if hasattr(http_exc.detail, 'update') and isinstance(http_exc.detail, dict):
                http_exc.detail.update({
                    "request_id": request_id,
                    "timestamp": int(time.time()),
                    "path": str(request.url.path)
                })
            
            return JSONResponse(
                status_code=http_exc.status_code,
                content=http_exc.detail
            )
        
        # 处理Pydantic验证错误
        elif isinstance(exc, ValidationError):
            error_details = []
            for error in exc.errors():
                error_details.append({
                    "field": ".".join(str(x) for x in error["loc"]),
                    "message": error["msg"],
                    "type": error["type"],
                    "input": error.get("input")
                })
            
            return JSONResponse(
                status_code=422,
                content={
                    "error": ErrorCodes.VALIDATION_ERROR,
                    "message": "Validation failed",
                    "details": error_details,
                    "request_id": request_id,
                    "timestamp": int(time.time()),
                    "path": str(request.url.path)
                }
            )
        
        # 处理HTTP异常
        elif isinstance(exc, (HTTPException, StarletteHTTPException)):
            # 如果detail已经是字典格式，添加额外信息
            if isinstance(exc.detail, dict):
                detail = exc.detail.copy()
                detail.update({
                    "request_id": request_id,
                    "timestamp": int(time.time()),
                    "path": str(request.url.path)
                })
            else:
                detail = {
                    "error": "http_exception",
                    "message": exc.detail,
                    "request_id": request_id,
                    "timestamp": int(time.time()),
                    "path": str(request.url.path)
                }
            
            return JSONResponse(
                status_code=exc.status_code,
                content=detail
            )
        
        # 处理其他未预期的异常
        else:
            logger.error(f"Unhandled exception: {type(exc).__name__}: {exc}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            return JSONResponse(
                status_code=500,
                content={
                    "error": ErrorCodes.INTERNAL_SERVER_ERROR,
                    "message": "An unexpected error occurred. Please try again later.",
                    "type": type(exc).__name__,
                    "request_id": request_id,
                    "timestamp": int(time.time()),
                    "path": str(request.url.path)
                }
            )
    
    except Exception as handler_exc:
        # 如果异常处理器本身出错，返回最基本的错误响应
        logger.critical(f"Exception handler failed: {handler_exc}")
        logger.critical(f"Original exception: {exc}")
        
        return JSONResponse(
            status_code=500,
            content={
                "error": "critical_error",
                "message": "A critical error occurred in error handling",
                "request_id": request_id,
                "timestamp": int(time.time())
            }
        )


def setup_exception_handlers(app):
    """
    设置应用的异常处理器
    """
    
    # 添加自定义异常处理器
    app.add_exception_handler(KnowledgeBaseException, knowledge_exception_handler)
    app.add_exception_handler(DocumentException, knowledge_exception_handler)
    app.add_exception_handler(SearchException, knowledge_exception_handler)
    app.add_exception_handler(ValidationError, knowledge_exception_handler)
    app.add_exception_handler(HTTPException, knowledge_exception_handler)
    app.add_exception_handler(StarletteHTTPException, knowledge_exception_handler)
    app.add_exception_handler(Exception, knowledge_exception_handler)


# 装饰器：用于捕获和转换异常
def handle_knowledge_exceptions(func):
    """
    装饰器：自动处理知识模块相关异常
    兼容FastAPI的依赖注入系统
    """
    import functools
    
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            # 处理HTTPException，直接重新抛出
            if isinstance(e, HTTPException):
                raise e
            
            # 处理知识库相关异常
            elif isinstance(e, KnowledgeBaseException):
                if isinstance(e, KnowledgeBaseNotFoundError):
                    raise HTTPException(status_code=404, detail={
                        "error": "knowledge_base_not_found",
                        "message": str(e),
                        "kb_id": getattr(e, 'kb_id', None)
                    })
                elif isinstance(e, KnowledgeBaseAlreadyExistsError):
                    raise HTTPException(status_code=409, detail={
                        "error": "knowledge_base_already_exists",
                        "message": str(e),
                        "name": getattr(e, 'name', None)
                    })
                elif isinstance(e, KnowledgeBaseAccessDeniedError):
                    raise HTTPException(status_code=403, detail={
                        "error": "knowledge_base_access_denied",
                        "message": str(e),
                        "kb_id": getattr(e, 'kb_id', None),
                        "access_type": getattr(e, 'access_type', None)
                    })
                else:
                    raise HTTPException(status_code=400, detail={
                        "error": "knowledge_base_error",
                        "message": str(e)
                    })
            
            # 处理文档相关异常
            elif isinstance(e, DocumentException):
                if "not found" in str(e).lower():
                    raise HTTPException(status_code=404, detail={
                        "error": "document_not_found",
                        "message": str(e)
                    })
                elif "access denied" in str(e).lower():
                    raise HTTPException(status_code=403, detail={
                        "error": "document_access_denied",
                        "message": str(e)
                    })
                elif "upload" in str(e).lower() or "format" in str(e).lower():
                    raise HTTPException(status_code=400, detail={
                        "error": "document_error",
                        "message": str(e)
                    })
                else:
                    raise HTTPException(status_code=400, detail={
                        "error": "document_error",
                        "message": str(e)
                    })
            
            # 处理搜索相关异常
            elif isinstance(e, SearchException):
                raise HTTPException(status_code=400, detail={
                    "error": "search_error",
                    "message": str(e)
                })
            
            # 处理其他未知异常
            else:
                logger.error(f"Unexpected exception in {func.__name__}: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                raise HTTPException(
                    status_code=500,
                    detail={
                        "error": "internal_server_error",
                        "message": f"An error occurred in {func.__name__}",
                        "function": func.__name__
                    }
                )
    return wrapper


# 验证装饰器
def validate_request_data(schema_class):
    """
    装饰器：验证请求数据
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                # 这里可以添加额外的验证逻辑
                return await func(*args, **kwargs)
            except ValidationError as e:
                raise e
            except Exception as e:
                logger.error(f"Validation error in {func.__name__}: {e}")
                raise ValidationError([{
                    "loc": ("request",),
                    "msg": str(e),
                    "type": "value_error"
                }], model=schema_class)
        return wrapper
    return decorator


# 错误响应辅助函数
class ErrorResponse:
    """错误响应构建器"""
    
    @staticmethod
    def knowledge_base_not_found(kb_id: str) -> Dict[str, Any]:
        return {
            "error": ErrorCodes.KNOWLEDGE_BASE_NOT_FOUND,
            "message": f"Knowledge base '{kb_id}' not found",
            "kb_id": kb_id
        }
    
    @staticmethod
    def document_not_found(doc_id: str) -> Dict[str, Any]:
        return {
            "error": ErrorCodes.DOCUMENT_NOT_FOUND,
            "message": f"Document '{doc_id}' not found",
            "doc_id": doc_id
        }
    
    @staticmethod
    def access_denied(resource_type: str, resource_id: str, action: str) -> Dict[str, Any]:
        return {
            "error": ErrorCodes.PERMISSION_DENIED,
            "message": f"Access denied: Cannot {action} {resource_type} '{resource_id}'",
            "resource_type": resource_type,
            "resource_id": resource_id,
            "action": action
        }
    
    @staticmethod
    def validation_failed(details: list) -> Dict[str, Any]:
        return {
            "error": ErrorCodes.VALIDATION_ERROR,
            "message": "Request validation failed",
            "details": details
        }
    
    @staticmethod
    def internal_error(message: str = "An unexpected error occurred") -> Dict[str, Any]:
        return {
            "error": ErrorCodes.INTERNAL_SERVER_ERROR,
            "message": message
        }
