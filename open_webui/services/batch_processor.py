"""
批量操作性能优化服务

提供高性能的批量处理功能：
- 并行处理
- 分块处理
- 连接池优化
- 内存管理
"""

import asyncio
import logging
from typing import List, Dict, Any, Callable, Optional, TypeVar, Generic
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
import time

logger = logging.getLogger(__name__)

T = TypeVar('T')
R = TypeVar('R')

@dataclass
class BatchConfig:
    """批量处理配置"""
    chunk_size: int = 100  # 每批处理数量
    max_workers: int = 4   # 最大并发数
    timeout: int = 300     # 超时时间（秒）
    retry_attempts: int = 3 # 重试次数
    retry_delay: float = 1.0 # 重试延迟（秒）

@dataclass
class BatchResult(Generic[T, R]):
    """批量处理结果"""
    success_items: List[R]
    failed_items: List[Dict[str, Any]]
    total_count: int
    success_count: int
    failed_count: int
    processing_time: float

class OptimizedBatchProcessor:
    """优化的批量处理器"""
    
    def __init__(self, config: BatchConfig = None):
        self.config = config or BatchConfig()
        self.executor = ThreadPoolExecutor(max_workers=self.config.max_workers)
        
    async def process_batch_async(
        self,
        items: List[T],
        processor_func: Callable[[List[T]], List[R]],
        error_handler: Optional[Callable[[T, Exception], Dict[str, Any]]] = None
    ) -> BatchResult[T, R]:
        """
        异步批量处理
        
        Args:
            items: 待处理项目列表
            processor_func: 处理函数
            error_handler: 错误处理函数
            
        Returns:
            BatchResult: 批量处理结果
        """
        start_time = time.time()
        success_items = []
        failed_items = []
        
        # 分块处理
        chunks = [
            items[i:i + self.config.chunk_size] 
            for i in range(0, len(items), self.config.chunk_size)
        ]
        
        # 并行处理每个块
        tasks = []
        for chunk in chunks:
            task = asyncio.create_task(
                self._process_chunk_with_retry(chunk, processor_func, error_handler)
            )
            tasks.append(task)
        
        # 等待所有任务完成
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=self.config.timeout
            )
            
            # 合并结果
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"批量处理块失败: {result}")
                    continue
                    
                chunk_success, chunk_failed = result
                success_items.extend(chunk_success)
                failed_items.extend(chunk_failed)
                
        except asyncio.TimeoutError:
            logger.error(f"批量处理超时 ({self.config.timeout}秒)")
            failed_items.extend([
                {"error": "处理超时", "item": str(item)} 
                for item in items[len(success_items):]
            ])
        
        processing_time = time.time() - start_time
        
        return BatchResult(
            success_items=success_items,
            failed_items=failed_items,
            total_count=len(items),
            success_count=len(success_items),
            failed_count=len(failed_items),
            processing_time=processing_time
        )
    
    async def _process_chunk_with_retry(
        self,
        chunk: List[T],
        processor_func: Callable[[List[T]], List[R]],
        error_handler: Optional[Callable[[T, Exception], Dict[str, Any]]]
    ) -> tuple[List[R], List[Dict[str, Any]]]:
        """带重试的块处理"""
        
        for attempt in range(self.config.retry_attempts):
            try:
                # 在线程池中执行处理函数
                loop = asyncio.get_event_loop()
                results = await loop.run_in_executor(
                    self.executor, processor_func, chunk
                )
                return results, []
                
            except Exception as e:
                logger.warning(f"块处理失败 (尝试 {attempt + 1}/{self.config.retry_attempts}): {e}")
                
                if attempt < self.config.retry_attempts - 1:
                    await asyncio.sleep(self.config.retry_delay * (2 ** attempt))
                else:
                    # 最后一次尝试失败，记录错误
                    failed_items = []
                    for item in chunk:
                        if error_handler:
                            failed_items.append(error_handler(item, e))
                        else:
                            failed_items.append({
                                "error": str(e),
                                "item": str(item)
                            })
                    return [], failed_items
        
        return [], []

class DatabaseBatchProcessor:
    """数据库批量处理器"""
    
    def __init__(self, database_url: str, config: BatchConfig = None):
        self.config = config or BatchConfig()
        self.engine = create_engine(
            database_url,
            pool_size=20,
            max_overflow=30,
            pool_pre_ping=True,
            pool_recycle=3600
        )
        self.SessionLocal = sessionmaker(bind=self.engine)
    
    @contextmanager
    def get_batch_session(self):
        """获取批量处理专用会话"""
        session = self.SessionLocal()
        try:
            # 优化批量操作的会话设置
            session.execute("SET SESSION sql_mode = 'NO_AUTO_VALUE_ON_ZERO'")
            session.execute("SET SESSION autocommit = 0")
            session.execute("SET SESSION unique_checks = 0")
            session.execute("SET SESSION foreign_key_checks = 0")
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            # 恢复默认设置
            session.execute("SET SESSION unique_checks = 1")
            session.execute("SET SESSION foreign_key_checks = 1")
            session.close()
    
    def batch_insert(self, model_class, data_list: List[Dict[str, Any]]) -> int:
        """批量插入数据"""
        if not data_list:
            return 0
            
        with self.get_batch_session() as session:
            try:
                # 使用bulk_insert_mappings进行高性能批量插入
                session.bulk_insert_mappings(model_class, data_list)
                return len(data_list)
            except Exception as e:
                logger.error(f"批量插入失败: {e}")
                raise
    
    def batch_update(self, model_class, data_list: List[Dict[str, Any]], key_field: str = 'id') -> int:
        """批量更新数据"""
        if not data_list:
            return 0
            
        with self.get_batch_session() as session:
            try:
                # 使用bulk_update_mappings进行高性能批量更新
                session.bulk_update_mappings(model_class, data_list)
                return len(data_list)
            except Exception as e:
                logger.error(f"批量更新失败: {e}")
                raise
    
    def batch_delete(self, model_class, ids: List[str]) -> int:
        """批量删除数据"""
        if not ids:
            return 0
            
        with self.get_batch_session() as session:
            try:
                # 分块删除以避免SQL语句过长
                deleted_count = 0
                chunk_size = 1000
                
                for i in range(0, len(ids), chunk_size):
                    chunk_ids = ids[i:i + chunk_size]
                    result = session.query(model_class).filter(
                        model_class.id.in_(chunk_ids)
                    ).delete(synchronize_session=False)
                    deleted_count += result
                
                return deleted_count
            except Exception as e:
                logger.error(f"批量删除失败: {e}")
                raise

# 全局批量处理器实例
batch_processor = OptimizedBatchProcessor()
db_batch_processor = None  # 需要在应用启动时初始化

def init_db_batch_processor(database_url: str):
    """初始化数据库批量处理器"""
    global db_batch_processor
    db_batch_processor = DatabaseBatchProcessor(database_url)

async def process_items_batch(
    items: List[T],
    processor_func: Callable[[List[T]], List[R]],
    config: BatchConfig = None
) -> BatchResult[T, R]:
    """便捷的批量处理函数"""
    processor = OptimizedBatchProcessor(config)
    return await processor.process_batch_async(items, processor_func)
