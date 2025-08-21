"""
JWT Token黑名单服务
用于管理已登出的token，防止token在过期前被继续使用
"""

import redis
import json
from typing import Optional
from datetime import datetime, timedelta
import logging
from open_webui.config import REDIS_URL

log = logging.getLogger(__name__)

class TokenBlacklistService:
    """Token黑名单管理服务"""
    
    def __init__(self):
        """初始化Redis连接"""
        try:
            # 解析Redis URL
            if REDIS_URL:
                self.redis_client = redis.from_url(
                    REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
            else:
                # 使用默认本地Redis
                self.redis_client = redis.Redis(
                    host='localhost',
                    port=6379,
                    db=0,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
            
            # 测试连接
            self.redis_client.ping()
            self.enabled = True
            log.info("Token blacklist service initialized successfully")
        except Exception as e:
            log.warning(f"Failed to connect to Redis: {e}. Token blacklist disabled.")
            self.redis_client = None
            self.enabled = False
    
    def add_to_blacklist(self, token: str, exp_timestamp: int) -> bool:
        """
        将token添加到黑名单
        
        Args:
            token: JWT token字符串
            exp_timestamp: token过期时间戳
            
        Returns:
            是否添加成功
        """
        if not self.enabled:
            log.warning("Token blacklist is disabled")
            return False
            
        try:
            # 计算token剩余有效时间
            now = datetime.utcnow()
            exp_time = datetime.fromtimestamp(exp_timestamp)
            
            if exp_time <= now:
                # Token已过期，无需加入黑名单
                return True
            
            # 计算TTL（存活时间）
            ttl = int((exp_time - now).total_seconds())
            
            # 使用token的hash作为key，避免key过长
            import hashlib
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            key = f"token_blacklist:{token_hash}"
            
            # 存储token信息和过期时间
            data = {
                "token": token[:50] + "..." if len(token) > 50 else token,  # 存储部分token用于调试
                "blacklisted_at": now.isoformat(),
                "expires_at": exp_time.isoformat()
            }
            
            # 设置key和过期时间
            self.redis_client.setex(
                key,
                ttl,
                json.dumps(data)
            )
            
            log.info(f"Token added to blacklist, will expire in {ttl} seconds")
            return True
            
        except Exception as e:
            log.error(f"Failed to add token to blacklist: {e}")
            return False
    
    def is_blacklisted(self, token: str) -> bool:
        """
        检查token是否在黑名单中
        
        Args:
            token: JWT token字符串
            
        Returns:
            是否在黑名单中
        """
        if not self.enabled:
            # 如果黑名单服务不可用，默认允许token
            return False
            
        try:
            import hashlib
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            key = f"token_blacklist:{token_hash}"
            
            # 检查key是否存在
            exists = self.redis_client.exists(key)
            
            if exists:
                log.debug(f"Token found in blacklist")
                return True
                
            return False
            
        except Exception as e:
            log.error(f"Failed to check token blacklist: {e}")
            # 出错时默认允许token（避免服务中断）
            return False
    
    def remove_from_blacklist(self, token: str) -> bool:
        """
        从黑名单中移除token（通常不需要，仅用于特殊情况）
        
        Args:
            token: JWT token字符串
            
        Returns:
            是否移除成功
        """
        if not self.enabled:
            return False
            
        try:
            import hashlib
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            key = f"token_blacklist:{token_hash}"
            
            result = self.redis_client.delete(key)
            
            if result:
                log.info("Token removed from blacklist")
                return True
                
            return False
            
        except Exception as e:
            log.error(f"Failed to remove token from blacklist: {e}")
            return False
    
    def clear_expired(self) -> int:
        """
        清理已过期的黑名单记录（Redis会自动过期，此方法用于手动清理）
        
        Returns:
            清理的记录数
        """
        if not self.enabled:
            return 0
            
        try:
            # Redis的过期机制会自动清理，这里只是统计
            pattern = "token_blacklist:*"
            keys = self.redis_client.keys(pattern)
            
            expired_count = 0
            for key in keys:
                ttl = self.redis_client.ttl(key)
                if ttl == -2:  # Key不存在或已过期
                    expired_count += 1
            
            if expired_count > 0:
                log.info(f"Found {expired_count} expired blacklist entries")
                
            return expired_count
            
        except Exception as e:
            log.error(f"Failed to clear expired blacklist entries: {e}")
            return 0
    
    def get_blacklist_stats(self) -> dict:
        """
        获取黑名单统计信息
        
        Returns:
            统计信息字典
        """
        if not self.enabled:
            return {
                "enabled": False,
                "total_entries": 0,
                "redis_connected": False
            }
            
        try:
            pattern = "token_blacklist:*"
            keys = self.redis_client.keys(pattern)
            
            return {
                "enabled": True,
                "total_entries": len(keys),
                "redis_connected": True,
                "redis_info": self.redis_client.info("server")
            }
            
        except Exception as e:
            log.error(f"Failed to get blacklist stats: {e}")
            return {
                "enabled": self.enabled,
                "total_entries": 0,
                "redis_connected": False,
                "error": str(e)
            }


# 创建全局实例
token_blacklist = TokenBlacklistService()
