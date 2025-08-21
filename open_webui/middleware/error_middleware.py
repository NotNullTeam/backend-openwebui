"""
全局错误处理中间件

统一处理所有未捕获的异常，提供标准化的错误响应
"""

import logging
import uuid
from typing import Callable
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from open_webui.utils.error_handler import (
    BusinessError, 
    handle_business_error, 
    handle_system_error,
    log_error
)

logger = logging.getLogger(__name__)

class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """全局错误处理中间件"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 为每个请求生成唯一ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        try:
            # 执行请求处理
            response = await call_next(request)
            return response
            
        except BusinessError as e:
            # 处理业务错误
            return handle_business_error(e, request)
            
        except Exception as e:
            # 处理系统错误
            return handle_system_error(e, request)

def setup_error_handling(app):
    """设置全局错误处理"""
    
    # 添加错误处理中间件
    app.add_middleware(ErrorHandlingMiddleware)
    
    # 设置异常处理器
    @app.exception_handler(BusinessError)
    async def business_error_handler(request: Request, exc: BusinessError):
        return handle_business_error(exc, request)
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        return handle_system_error(exc, request)
