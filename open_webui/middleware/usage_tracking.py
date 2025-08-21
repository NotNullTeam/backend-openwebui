"""
使用跟踪中间件
自动记录所有API调用的使用情况
"""

import logging
import time
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from open_webui.services.usage_tracker import UsageTracker

log = logging.getLogger(__name__)


class UsageTrackingMiddleware(BaseHTTPMiddleware):
    """使用跟踪中间件"""
    
    def __init__(self, app, exclude_paths: list = None):
        super().__init__(app)
        self.exclude_paths = exclude_paths or [
            "/health",
            "/static",
            "/favicon.ico",
            "/docs",
            "/openapi.json",
            "/redoc"
        ]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求并记录使用情况"""
        
        # 跳过不需要跟踪的路径
        path = request.url.path
        if any(path.startswith(excluded) for excluded in self.exclude_paths):
            return await call_next(request)
        
        # 记录开始时间
        start_time = time.time()
        
        # 获取用户ID（如果有）
        user_id = None
        if hasattr(request.state, "user") and request.state.user:
            user_id = request.state.user.id
        
        # 处理请求
        response = None
        error = None
        try:
            response = await call_next(request)
            return response
            
        except Exception as e:
            error = str(e)
            raise
            
        finally:
            # 计算响应时间
            response_time = time.time() - start_time
            
            # 记录API调用
            if user_id:
                try:
                    status_code = response.status_code if response else 500
                    
                    UsageTracker.log_api_call(
                        user_id=user_id,
                        endpoint=path,
                        method=request.method,
                        response_time=response_time,
                        status_code=status_code,
                        error=error
                    )
                except Exception as e:
                    log.error(f"Failed to track API usage: {e}")
