"""
节点重生成服务
提供增强的异常处理和错误恢复机制
"""

import asyncio
import json
import logging
import time
from typing import Dict, Optional, List, Any
from enum import Enum
from contextlib import asynccontextmanager

from sqlalchemy.orm import Session
from open_webui.internal.db import get_db
from open_webui.models.cases import CaseNode

log = logging.getLogger(__name__)


class RegenerationStatus(Enum):
    """重生成状态枚举"""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
    CANCELLED = "CANCELLED"


class RegenerationError(Exception):
    """重生成错误基类"""
    def __init__(self, message: str, node_id: str, recoverable: bool = True):
        super().__init__(message)
        self.node_id = node_id
        self.recoverable = recoverable


class ModelUnavailableError(RegenerationError):
    """模型不可用错误"""
    pass


class ContentParsingError(RegenerationError):
    """内容解析错误"""
    pass


class RateLimitError(RegenerationError):
    """速率限制错误"""
    pass


class NodeRegenerationService:
    """节点重生成服务"""
    
    def __init__(self):
        self.active_tasks: Dict[str, asyncio.Task] = {}
        self.retry_policies = {
            ModelUnavailableError: {"max_retries": 5, "backoff": 2.0, "max_delay": 60},
            RateLimitError: {"max_retries": 3, "backoff": 3.0, "max_delay": 120},
            ContentParsingError: {"max_retries": 2, "backoff": 1.0, "max_delay": 10},
        }
        
    @asynccontextmanager
    async def node_lock(self, node_id: str, timeout: int = 300):
        """节点锁机制，防止并发重生成"""
        lock_key = f"node_regeneration:{node_id}"
        acquired = False
        
        try:
            # 尝试获取锁
            from open_webui.apps.rag.vector.redis import REDIS_CLIENT
            if REDIS_CLIENT:
                acquired = await REDIS_CLIENT.set(
                    lock_key, 
                    "locked", 
                    nx=True, 
                    ex=timeout
                )
                if not acquired:
                    raise RegenerationError(
                        f"Node {node_id} is already being regenerated",
                        node_id=node_id,
                        recoverable=False
                    )
            yield
        finally:
            # 释放锁
            if acquired and REDIS_CLIENT:
                await REDIS_CLIENT.delete(lock_key)
    
    async def validate_node(self, case_id: str, node_id: str, user_id: str) -> CaseNode:
        """验证节点是否存在且用户有权限"""
        with get_db() as db:
            node = db.query(CaseNode).filter_by(
                id=node_id, 
                case_id=case_id
            ).first()
            
            if not node:
                raise RegenerationError(
                    f"Node {node_id} not found",
                    node_id=node_id,
                    recoverable=False
                )
            
            # 验证用户权限
            from open_webui.models.cases import Cases
            case = Cases.get_case_by_id(case_id)
            if not case or case.user_id != user_id:
                raise RegenerationError(
                    f"User {user_id} has no permission to regenerate node {node_id}",
                    node_id=node_id,
                    recoverable=False
                )
            
            return node
    
    async def save_checkpoint(
        self, 
        node_id: str, 
        content: str, 
        metadata: Dict[str, Any]
    ):
        """保存检查点，用于错误恢复"""
        checkpoint_key = f"regeneration_checkpoint:{node_id}"
        checkpoint_data = {
            "content": content,
            "metadata": metadata,
            "timestamp": time.time()
        }
        
        try:
            from open_webui.apps.rag.vector.redis import REDIS_CLIENT
            if REDIS_CLIENT:
                await REDIS_CLIENT.set(
                    checkpoint_key,
                    json.dumps(checkpoint_data),
                    ex=3600  # 1小时过期
                )
        except Exception as e:
            log.warning(f"Failed to save checkpoint for node {node_id}: {e}")
    
    async def load_checkpoint(self, node_id: str) -> Optional[Dict[str, Any]]:
        """加载检查点"""
        checkpoint_key = f"regeneration_checkpoint:{node_id}"
        
        try:
            from open_webui.apps.rag.vector.redis import REDIS_CLIENT
            if REDIS_CLIENT:
                data = await REDIS_CLIENT.get(checkpoint_key)
                if data:
                    return json.loads(data)
        except Exception as e:
            log.warning(f"Failed to load checkpoint for node {node_id}: {e}")
        
        return None
    
    def get_retry_policy(self, error: Exception) -> Dict[str, Any]:
        """获取错误对应的重试策略"""
        for error_type, policy in self.retry_policies.items():
            if isinstance(error, error_type):
                return policy
        
        # 默认策略
        return {"max_retries": 3, "backoff": 2.0, "max_delay": 30}
    
    async def execute_with_retry(
        self,
        func,
        node_id: str,
        **kwargs
    ) -> Any:
        """带重试机制的执行器"""
        last_error = None
        
        for attempt in range(1, 4):  # 最多3次尝试
            try:
                # 执行函数
                result = await func(**kwargs)
                
                # 成功后清理检查点
                checkpoint_key = f"regeneration_checkpoint:{node_id}"
                try:
                    from open_webui.apps.rag.vector.redis import REDIS_CLIENT
                    if REDIS_CLIENT:
                        await REDIS_CLIENT.delete(checkpoint_key)
                except:
                    pass
                
                return result
                
            except Exception as e:
                last_error = e
                log.warning(f"Attempt {attempt} failed for node {node_id}: {e}")
                
                # 检查是否可恢复
                if isinstance(e, RegenerationError) and not e.recoverable:
                    raise
                
                # 获取重试策略
                policy = self.get_retry_policy(e)
                
                if attempt >= policy["max_retries"]:
                    break
                
                # 计算延迟时间
                delay = min(
                    policy["backoff"] ** attempt,
                    policy["max_delay"]
                )
                
                log.info(f"Retrying node {node_id} after {delay} seconds...")
                await asyncio.sleep(delay)
        
        # 所有尝试都失败
        raise RegenerationError(
            f"All retry attempts failed: {last_error}",
            node_id=node_id,
            recoverable=False
        )
    
    async def update_node_status(
        self,
        node_id: str,
        status: RegenerationStatus,
        metadata: Optional[Dict[str, Any]] = None,
        content: Optional[str] = None
    ):
        """更新节点状态"""
        with get_db() as db:
            node = db.query(CaseNode).filter_by(id=node_id).first()
            if node:
                node.status = status.value
                
                if metadata:
                    node.metadata_ = {
                        **(node.metadata_ or {}),
                        **metadata
                    }
                
                if content is not None:
                    node.content = content
                
                node.updated_at = int(time.time())
                db.commit()
    
    async def regenerate_node(
        self,
        case_id: str,
        node_id: str,
        user_id: str,
        prompt: Optional[str] = None,
        strategy: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        **kwargs
    ) -> Dict[str, Any]:
        """重生成节点内容"""
        
        async with self.node_lock(node_id):
            # 验证节点
            node = await self.validate_node(case_id, node_id, user_id)
            
            # 标记为处理中
            await self.update_node_status(
                node_id,
                RegenerationStatus.PROCESSING,
                metadata={
                    "regeneration_started_at": time.time(),
                    "regeneration_user_id": user_id,
                }
            )
            
            try:
                # 检查是否有检查点可恢复
                checkpoint = await self.load_checkpoint(node_id)
                if checkpoint:
                    log.info(f"Recovering from checkpoint for node {node_id}")
                    content = checkpoint["content"]
                    metadata = checkpoint["metadata"]
                else:
                    # 执行重生成
                    from open_webui.routers.cases_migrated import (
                        build_regeneration_messages,
                        regenerate_with_model
                    )
                    
                    # 解析原始内容
                    try:
                        original_content = json.loads(node.content or "{}")
                        if isinstance(original_content, dict):
                            base_text = (
                                original_content.get("text") or
                                original_content.get("analysis") or
                                original_content.get("answer") or
                                ""
                            )
                        else:
                            base_text = str(original_content)
                    except:
                        base_text = node.content or ""
                    
                    # 构建消息
                    messages = build_regeneration_messages(
                        original_text=base_text,
                        user_prompt=prompt,
                        strategy=strategy,
                        language="zh"
                    )
                    
                    # 使用重试机制执行
                    content = await self.execute_with_retry(
                        regenerate_with_model,
                        node_id=node_id,
                        request=kwargs.get("request"),
                        user=kwargs.get("user"),
                        messages=messages,
                        model_hint=model,
                        metadata={
                            "task": "case_node_regenerate",
                            "case_id": case_id,
                            "node_id": node_id,
                            "strategy": strategy,
                            "temperature": temperature,
                        }
                    )
                    
                    metadata = {
                        "regenerated": True,
                        "regenerated_at": time.time(),
                        "regeneration_strategy": strategy,
                        "original_content": node.content,
                        "user_prompt": prompt,
                    }
                    
                    # 保存检查点
                    await self.save_checkpoint(node_id, content, metadata)
                
                # 更新节点
                await self.update_node_status(
                    node_id,
                    RegenerationStatus.COMPLETED,
                    metadata=metadata,
                    content=content
                )
                
                return {
                    "status": "success",
                    "node_id": node_id,
                    "content": content,
                    "metadata": metadata
                }
                
            except Exception as e:
                log.error(f"Failed to regenerate node {node_id}: {e}")
                
                # 更新失败状态
                await self.update_node_status(
                    node_id,
                    RegenerationStatus.FAILED,
                    metadata={
                        "regeneration_failed": True,
                        "error": str(e),
                        "failed_at": time.time()
                    }
                )
                
                raise
    
    async def cancel_regeneration(self, node_id: str) -> bool:
        """取消正在进行的重生成"""
        if node_id in self.active_tasks:
            task = self.active_tasks[node_id]
            if not task.done():
                task.cancel()
                
                # 更新状态
                await self.update_node_status(
                    node_id,
                    RegenerationStatus.CANCELLED,
                    metadata={
                        "cancelled_at": time.time()
                    }
                )
                
                del self.active_tasks[node_id]
                return True
        
        return False
    
    async def get_regeneration_status(self, node_id: str) -> Dict[str, Any]:
        """获取重生成状态"""
        with get_db() as db:
            node = db.query(CaseNode).filter_by(id=node_id).first()
            if not node:
                return {"status": "not_found"}
            
            metadata = node.metadata_ or {}
            
            # 检查是否在活动任务中
            is_active = node_id in self.active_tasks and not self.active_tasks[node_id].done()
            
            return {
                "status": node.status,
                "is_active": is_active,
                "started_at": metadata.get("regeneration_started_at"),
                "completed_at": metadata.get("regenerated_at"),
                "failed_at": metadata.get("failed_at"),
                "error": metadata.get("error"),
                "strategy": metadata.get("regeneration_strategy"),
            }


# 全局服务实例
node_regeneration_service = NodeRegenerationService()
