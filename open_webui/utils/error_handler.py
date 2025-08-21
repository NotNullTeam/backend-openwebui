"""
统一错误处理机制

提供标准化的错误处理、日志记录和响应格式
"""

import logging
import traceback
from typing import Dict, Any, Optional, Union
from enum import Enum
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class ErrorCode(Enum):
    """标准错误代码"""
    # 通用错误 (1000-1999)
    UNKNOWN_ERROR = 1000
    VALIDATION_ERROR = 1001
    PERMISSION_DENIED = 1002
    RESOURCE_NOT_FOUND = 1003
    RATE_LIMIT_EXCEEDED = 1004
    
    # 认证错误 (2000-2099)
    AUTH_TOKEN_INVALID = 2000
    AUTH_TOKEN_EXPIRED = 2001
    AUTH_CREDENTIALS_INVALID = 2002
    AUTH_USER_NOT_FOUND = 2003
    
    # 业务逻辑错误 (3000-3999)
    CASE_NOT_FOUND = 3000
    CASE_CREATION_FAILED = 3001
    NODE_REGENERATION_FAILED = 3002
    KNOWLEDGE_UPLOAD_FAILED = 3003
    FILE_SCAN_FAILED = 3004
    BATCH_OPERATION_FAILED = 3005
    VECTOR_REBUILD_FAILED = 3006
    
    # 系统错误 (4000-4999)
    DATABASE_ERROR = 4000
    EXTERNAL_SERVICE_ERROR = 4001
    STORAGE_ERROR = 4002
    VECTOR_DB_ERROR = 4003
    CACHE_ERROR = 4004

class ErrorResponse(BaseModel):
    """标准错误响应格式"""
    success: bool = False
    error_code: int
    error_type: str
    message: str
    details: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None
    timestamp: Optional[str] = None

class BusinessError(Exception):
    """业务逻辑错误基类"""
    
    def __init__(
        self, 
        error_code: ErrorCode, 
        message: str, 
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        self.error_code = error_code
        self.message = message
        self.details = details or {}
        self.cause = cause
        super().__init__(message)

class ValidationError(BusinessError):
    """参数验证错误"""
    
    def __init__(self, message: str, field: str = None, details: Dict[str, Any] = None):
        if field:
            details = details or {}
            details['field'] = field
        super().__init__(ErrorCode.VALIDATION_ERROR, message, details)

class AuthenticationError(BusinessError):
    """认证错误"""
    
    def __init__(self, error_code: ErrorCode = ErrorCode.AUTH_TOKEN_INVALID, message: str = "认证失败"):
        super().__init__(error_code, message)

class PermissionError(BusinessError):
    """权限错误"""
    
    def __init__(self, message: str = "权限不足"):
        super().__init__(ErrorCode.PERMISSION_DENIED, message)

class ResourceNotFoundError(BusinessError):
    """资源不存在错误"""
    
    def __init__(self, resource_type: str, resource_id: str):
        message = f"{resource_type} {resource_id} 不存在"
        details = {"resource_type": resource_type, "resource_id": resource_id}
        super().__init__(ErrorCode.RESOURCE_NOT_FOUND, message, details)

class SystemError(BusinessError):
    """系统错误"""
    
    def __init__(self, error_code: ErrorCode, message: str, cause: Exception = None):
        super().__init__(error_code, message, cause=cause)

def create_error_response(
    error_code: ErrorCode,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None
) -> ErrorResponse:
    """创建标准错误响应"""
    from datetime import datetime
    
    return ErrorResponse(
        error_code=error_code.value,
        error_type=error_code.name,
        message=message,
        details=details,
        request_id=request_id,
        timestamp=datetime.now().isoformat()
    )

def log_error(
    error: Exception,
    context: Optional[Dict[str, Any]] = None,
    request: Optional[Request] = None
):
    """记录错误日志"""
    
    # 构建日志上下文
    log_context = {
        "error_type": type(error).__name__,
        "error_message": str(error)
    }
    
    if context:
        log_context.update(context)
    
    if request:
        log_context.update({
            "method": request.method,
            "url": str(request.url),
            "user_agent": request.headers.get("user-agent"),
            "client_ip": request.client.host if request.client else None
        })
    
    # 记录错误详情
    if isinstance(error, BusinessError):
        logger.error(
            f"业务错误: {error.error_code.name} - {error.message}",
            extra={"context": log_context, "details": error.details}
        )
    else:
        logger.error(
            f"系统错误: {str(error)}",
            extra={"context": log_context, "traceback": traceback.format_exc()}
        )

def handle_business_error(error: BusinessError, request: Request = None) -> JSONResponse:
    """处理业务错误"""
    
    # 记录错误日志
    log_error(error, request=request)
    
    # 创建错误响应
    error_response = create_error_response(
        error.error_code,
        error.message,
        error.details,
        getattr(request, 'state', {}).get('request_id') if request else None
    )
    
    # 根据错误类型确定HTTP状态码
    status_code = get_http_status_code(error.error_code)
    
    return JSONResponse(
        status_code=status_code,
        content=error_response.dict()
    )

def handle_system_error(error: Exception, request: Request = None) -> JSONResponse:
    """处理系统错误"""
    
    # 记录错误日志
    log_error(error, request=request)
    
    # 创建通用错误响应
    error_response = create_error_response(
        ErrorCode.UNKNOWN_ERROR,
        "系统内部错误",
        {"original_error": str(error)},
        getattr(request, 'state', {}).get('request_id') if request else None
    )
    
    return JSONResponse(
        status_code=500,
        content=error_response.dict()
    )

def get_http_status_code(error_code: ErrorCode) -> int:
    """根据错误代码获取HTTP状态码"""
    
    status_mapping = {
        # 通用错误
        ErrorCode.UNKNOWN_ERROR: 500,
        ErrorCode.VALIDATION_ERROR: 422,
        ErrorCode.PERMISSION_DENIED: 403,
        ErrorCode.RESOURCE_NOT_FOUND: 404,
        ErrorCode.RATE_LIMIT_EXCEEDED: 429,
        
        # 认证错误
        ErrorCode.AUTH_TOKEN_INVALID: 401,
        ErrorCode.AUTH_TOKEN_EXPIRED: 401,
        ErrorCode.AUTH_CREDENTIALS_INVALID: 401,
        ErrorCode.AUTH_USER_NOT_FOUND: 401,
        
        # 业务逻辑错误
        ErrorCode.CASE_NOT_FOUND: 404,
        ErrorCode.CASE_CREATION_FAILED: 400,
        ErrorCode.NODE_REGENERATION_FAILED: 400,
        ErrorCode.KNOWLEDGE_UPLOAD_FAILED: 400,
        ErrorCode.FILE_SCAN_FAILED: 400,
        ErrorCode.BATCH_OPERATION_FAILED: 400,
        ErrorCode.VECTOR_REBUILD_FAILED: 400,
        
        # 系统错误
        ErrorCode.DATABASE_ERROR: 500,
        ErrorCode.EXTERNAL_SERVICE_ERROR: 502,
        ErrorCode.STORAGE_ERROR: 500,
        ErrorCode.VECTOR_DB_ERROR: 500,
        ErrorCode.CACHE_ERROR: 500,
    }
    
    return status_mapping.get(error_code, 500)

# 装饰器：自动错误处理
def handle_errors(func):
    """自动错误处理装饰器"""
    
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except BusinessError as e:
            request = kwargs.get('request') or (args[0] if args and hasattr(args[0], 'method') else None)
            return handle_business_error(e, request)
        except HTTPException:
            raise  # FastAPI的HTTPException直接抛出
        except Exception as e:
            request = kwargs.get('request') or (args[0] if args and hasattr(args[0], 'method') else None)
            return handle_system_error(e, request)
    
    return wrapper

# 上下文管理器：错误捕获
class ErrorContext:
    """错误处理上下文管理器"""
    
    def __init__(self, operation: str, context: Dict[str, Any] = None):
        self.operation = operation
        self.context = context or {}
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type and exc_val:
            # 添加操作上下文
            self.context['operation'] = self.operation
            log_error(exc_val, self.context)
        
        return False  # 不抑制异常

# 工具函数
def safe_execute(func, *args, error_code: ErrorCode = ErrorCode.UNKNOWN_ERROR, **kwargs):
    """安全执行函数，捕获异常并转换为业务错误"""
    try:
        return func(*args, **kwargs)
    except BusinessError:
        raise  # 业务错误直接抛出
    except Exception as e:
        raise SystemError(error_code, f"执行 {func.__name__} 失败: {str(e)}", e)

async def safe_execute_async(func, *args, error_code: ErrorCode = ErrorCode.UNKNOWN_ERROR, **kwargs):
    """安全执行异步函数"""
    try:
        return await func(*args, **kwargs)
    except BusinessError:
        raise
    except Exception as e:
        raise SystemError(error_code, f"执行 {func.__name__} 失败: {str(e)}", e)
