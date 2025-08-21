"""
API限流中间件
使用滑动窗口算法实现请求频率限制
"""

import time
import redis
import json
from typing import Optional, Dict, Tuple
from datetime import datetime, timedelta
import logging
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from open_webui.config import REDIS_URL

log = logging.getLogger(__name__)

class RateLimiter:
    """基于Redis的限流器"""
    
    def __init__(self):
        """初始化Redis连接"""
        try:
            if REDIS_URL:
                self.redis_client = redis.from_url(
                    REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
            else:
                self.redis_client = redis.Redis(
                    host='localhost',
                    port=6379,
                    db=1,  # 使用不同的DB避免冲突
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
            
            self.redis_client.ping()
            self.enabled = True
            log.info("Rate limiter initialized successfully")
        except Exception as e:
            log.warning(f"Failed to connect to Redis for rate limiting: {e}")
            self.redis_client = None
            self.enabled = False
    
    def check_rate_limit(
        self,
        key: str,
        limit: int,
        window: int,
        cost: int = 1
    ) -> Tuple[bool, Dict]:
        """
        检查是否超过速率限制
        
        Args:
            key: 限流key（如用户ID或IP）
            limit: 时间窗口内的最大请求数
            window: 时间窗口大小（秒）
            cost: 本次请求的消耗（默认1）
            
        Returns:
            (是否允许, 限流信息字典)
        """
        if not self.enabled:
            return True, {"enabled": False}
        
        try:
            now = time.time()
            pipeline = self.redis_client.pipeline()
            
            # 移除过期的请求记录
            pipeline.zremrangebyscore(key, 0, now - window)
            
            # 获取当前窗口内的请求数
            pipeline.zcard(key)
            
            # 执行pipeline
            results = pipeline.execute()
            current_requests = results[1]
            
            # 检查是否超限
            if current_requests + cost > limit:
                # 计算重置时间
                pipeline = self.redis_client.pipeline()
                pipeline.zrange(key, 0, 0, withscores=True)
                oldest = pipeline.execute()[0]
                
                if oldest:
                    reset_time = oldest[0][1] + window
                else:
                    reset_time = now + window
                
                return False, {
                    "limit": limit,
                    "remaining": max(0, limit - current_requests),
                    "reset": int(reset_time),
                    "retry_after": int(reset_time - now)
                }
            
            # 添加当前请求
            for _ in range(cost):
                self.redis_client.zadd(key, {f"{now}:{time.time_ns()}": now})
            
            # 设置过期时间
            self.redis_client.expire(key, window)
            
            return True, {
                "limit": limit,
                "remaining": limit - current_requests - cost,
                "reset": int(now + window)
            }
            
        except Exception as e:
            log.error(f"Rate limit check failed: {e}")
            # 出错时默认允许请求
            return True, {"error": str(e)}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """API限流中间件"""
    
    def __init__(self, app, config: Optional[Dict] = None):
        super().__init__(app)
        self.limiter = RateLimiter()
        
        # 默认配置
        self.config = config or {}
        
        # 全局限制
        self.global_limit = self.config.get("global_limit", 1000)
        self.global_window = self.config.get("global_window", 60)
        
        # 用户限制
        self.user_limit = self.config.get("user_limit", 100)
        self.user_window = self.config.get("user_window", 60)
        
        # IP限制
        self.ip_limit = self.config.get("ip_limit", 50)
        self.ip_window = self.config.get("ip_window", 60)
        
        # 特定路径限制
        self.path_limits = self.config.get("path_limits", {
            "/api/v1/analysis": {"limit": 10, "window": 60},  # AI分析限制
            "/api/v1/knowledge/documents/upload": {"limit": 20, "window": 60},  # 文件上传限制
            "/api/v1/cases/batch": {"limit": 5, "window": 60},  # 批量操作限制
        })
        
        # 豁免路径
        self.exempt_paths = self.config.get("exempt_paths", [
            "/health",
            "/api/v1/system/health",
            "/api/v1/auth/signin",
            "/api/v1/auth/signup"
        ])
    
    async def dispatch(self, request: Request, call_next):
        """处理请求"""
        
        # 检查是否为豁免路径
        path = request.url.path
        if any(path.startswith(exempt) for exempt in self.exempt_paths):
            return await call_next(request)
        
        # 获取客户端IP
        client_ip = request.client.host if request.client else "unknown"
        
        # 获取用户ID（如果已认证）
        user_id = None
        try:
            if hasattr(request.state, "user") and request.state.user:
                user_id = request.state.user.id
        except:
            pass
        
        # 检查特定路径限制
        for path_pattern, limits in self.path_limits.items():
            if path.startswith(path_pattern):
                key = f"rate_limit:path:{path_pattern}:{user_id or client_ip}"
                allowed, info = self.limiter.check_rate_limit(
                    key,
                    limits["limit"],
                    limits["window"]
                )
                
                if not allowed:
                    return self._rate_limit_exceeded_response(info)
        
        # 检查用户限制（如果已认证）
        if user_id:
            key = f"rate_limit:user:{user_id}"
            allowed, info = self.limiter.check_rate_limit(
                key,
                self.user_limit,
                self.user_window
            )
            
            if not allowed:
                return self._rate_limit_exceeded_response(info)
        
        # 检查IP限制
        if client_ip != "unknown":
            key = f"rate_limit:ip:{client_ip}"
            allowed, info = self.limiter.check_rate_limit(
                key,
                self.ip_limit,
                self.ip_window
            )
            
            if not allowed:
                return self._rate_limit_exceeded_response(info)
        
        # 检查全局限制
        key = "rate_limit:global"
        allowed, info = self.limiter.check_rate_limit(
            key,
            self.global_limit,
            self.global_window
        )
        
        if not allowed:
            return self._rate_limit_exceeded_response(info)
        
        # 处理请求并添加限流头
        response = await call_next(request)
        
        # 添加限流信息到响应头
        if info and "limit" in info:
            response.headers["X-RateLimit-Limit"] = str(info["limit"])
            response.headers["X-RateLimit-Remaining"] = str(info.get("remaining", 0))
            response.headers["X-RateLimit-Reset"] = str(info.get("reset", 0))
        
        return response
    
    def _rate_limit_exceeded_response(self, info: Dict) -> JSONResponse:
        """返回限流响应"""
        content = {
            "detail": "Rate limit exceeded",
            "retry_after": info.get("retry_after", 60)
        }
        
        headers = {
            "Retry-After": str(info.get("retry_after", 60)),
            "X-RateLimit-Limit": str(info.get("limit", 0)),
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": str(info.get("reset", 0))
        }
        
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content=content,
            headers=headers
        )


def create_rate_limiter(config: Optional[Dict] = None) -> RateLimitMiddleware:
    """
    创建限流中间件实例
    
    Args:
        config: 限流配置
        
    Returns:
        RateLimitMiddleware实例
    """
    return lambda app: RateLimitMiddleware(app, config)
