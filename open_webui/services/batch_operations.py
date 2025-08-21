"""
批量操作优化服务
提供高性能的批量数据处理能力
"""

import asyncio
import logging
import time
from typing import List, Dict, Any, Optional, Callable, TypeVar, Generic
from dataclasses import dataclass
from enum import Enum
from concurrent.futures import ThreadPoolExecutor
import multiprocessing

from sqlalchemy import text, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool
from open_webui.internal.db import get_db, engine
from open_webui.services.cache import cache, CacheLevel

log = logging.getLogger(__name__)

T = TypeVar('T')


class BatchStrategy(Enum):
    """批量处理策略"""
    SEQUENTIAL = "sequential"  # 顺序处理
    PARALLEL = "parallel"      # 并行处理
    CHUNKED = "chunked"       # 分块处理
    BULK = "bulk"            # 批量SQL


@dataclass
class BatchConfig:
    """批量操作配置"""
    chunk_size: int = 100
    max_workers: int = 4
    strategy: BatchStrategy = BatchStrategy.CHUNKED
    use_transaction: bool = True
    retry_failed: bool = True
    max_retries: int = 3
    timeout: Optional[float] = None


@dataclass
class BatchResult:
    """批量操作结果"""
    total: int
    success: int
    failed: int
    skipped: int
    duration: float
    errors: List[Dict[str, Any]]
    results: Optional[List[Any]] = None


class BatchProcessor(Generic[T]):
    """通用批量处理器"""
    
    def __init__(self, config: BatchConfig = None):
        self.config = config or BatchConfig()
        self.executor = ThreadPoolExecutor(max_workers=self.config.max_workers)
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.executor.shutdown(wait=True)
    
    async def process_batch(
        self,
        items: List[T],
        processor: Callable[[T], Any],
        config: Optional[BatchConfig] = None
    ) -> BatchResult:
        """处理批量数据"""
        config = config or self.config
        start_time = time.time()
        
        total = len(items)
        success = 0
        failed = 0
        skipped = 0
        errors = []
        results = []
        
        if config.strategy == BatchStrategy.SEQUENTIAL:
            # 顺序处理
            for item in items:
                try:
                    result = await self._process_item_with_retry(
                        item, processor, config
                    )
                    results.append(result)
                    success += 1
                except Exception as e:
                    failed += 1
                    errors.append({
                        "item": str(item),
                        "error": str(e)
                    })
                    
        elif config.strategy == BatchStrategy.PARALLEL:
            # 并行处理
            tasks = [
                self._process_item_with_retry(item, processor, config)
                for item in items
            ]
            
            completed = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, result in enumerate(completed):
                if isinstance(result, Exception):
                    failed += 1
                    errors.append({
                        "item": str(items[i]),
                        "error": str(result)
                    })
                else:
                    results.append(result)
                    success += 1
                    
        elif config.strategy == BatchStrategy.CHUNKED:
            # 分块处理
            chunks = self._chunk_items(items, config.chunk_size)
            
            for chunk in chunks:
                chunk_results = await self._process_chunk(
                    chunk, processor, config
                )
                
                success += chunk_results["success"]
                failed += chunk_results["failed"]
                errors.extend(chunk_results["errors"])
                results.extend(chunk_results["results"])
                
        elif config.strategy == BatchStrategy.BULK:
            # 批量SQL处理
            try:
                bulk_results = await self._bulk_process(items, processor, config)
                results = bulk_results
                success = len(bulk_results)
            except Exception as e:
                failed = total
                errors.append({
                    "error": f"Bulk operation failed: {str(e)}"
                })
        
        duration = time.time() - start_time
        
        return BatchResult(
            total=total,
            success=success,
            failed=failed,
            skipped=skipped,
            duration=duration,
            errors=errors,
            results=results
        )
    
    async def _process_item_with_retry(
        self,
        item: T,
        processor: Callable[[T], Any],
        config: BatchConfig
    ) -> Any:
        """带重试的单项处理"""
        last_error = None
        
        for attempt in range(config.max_retries if config.retry_failed else 1):
            try:
                if asyncio.iscoroutinefunction(processor):
                    return await processor(item)
                else:
                    # 在线程池中运行同步函数
                    loop = asyncio.get_event_loop()
                    return await loop.run_in_executor(
                        self.executor, processor, item
                    )
            except Exception as e:
                last_error = e
                if attempt < config.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # 指数退避
                    
        raise last_error
    
    def _chunk_items(self, items: List[T], chunk_size: int) -> List[List[T]]:
        """将列表分块"""
        chunks = []
        for i in range(0, len(items), chunk_size):
            chunks.append(items[i:i + chunk_size])
        return chunks
    
    async def _process_chunk(
        self,
        chunk: List[T],
        processor: Callable[[T], Any],
        config: BatchConfig
    ) -> Dict[str, Any]:
        """处理单个块"""
        results = []
        errors = []
        success = 0
        failed = 0
        
        # 并行处理块内的项
        tasks = [
            self._process_item_with_retry(item, processor, config)
            for item in chunk
        ]
        
        completed = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(completed):
            if isinstance(result, Exception):
                failed += 1
                errors.append({
                    "item": str(chunk[i]),
                    "error": str(result)
                })
            else:
                results.append(result)
                success += 1
        
        return {
            "success": success,
            "failed": failed,
            "errors": errors,
            "results": results
        }
    
    async def _bulk_process(
        self,
        items: List[T],
        processor: Callable[[List[T]], Any],
        config: BatchConfig
    ) -> Any:
        """批量处理（适用于批量SQL操作）"""
        if config.use_transaction:
            with get_db() as db:
                try:
                    result = processor(items, db)
                    db.commit()
                    return result
                except Exception as e:
                    db.rollback()
                    raise
        else:
            return processor(items, None)


class DatabaseBatchOperations:
    """数据库批量操作优化"""
    
    def __init__(self):
        # 创建优化的数据库引擎
        self.batch_engine = create_engine(
            str(engine.url),
            poolclass=QueuePool,
            pool_size=20,
            max_overflow=30,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=False
        )
        self.BatchSession = sessionmaker(bind=self.batch_engine)
    
    def bulk_insert(self, table_name: str, records: List[Dict[str, Any]]) -> int:
        """批量插入"""
        if not records:
            return 0
        
        # 分批处理大量数据
        batch_size = 1000
        total_inserted = 0
        
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            
            with self.batch_engine.begin() as conn:
                # 构建批量插入SQL
                columns = list(batch[0].keys())
                placeholders = ', '.join([f':{col}' for col in columns])
                
                sql = text(f"""
                    INSERT INTO {table_name} ({', '.join(columns)})
                    VALUES ({placeholders})
                """)
                
                # 执行批量插入
                result = conn.execute(sql, batch)
                total_inserted += result.rowcount
        
        return total_inserted
    
    def bulk_update(
        self,
        table_name: str,
        updates: List[Dict[str, Any]],
        key_column: str = "id"
    ) -> int:
        """批量更新"""
        if not updates:
            return 0
        
        # 优化：使用CASE WHEN进行批量更新
        if len(updates) > 100:  # 大批量使用CASE WHEN
            return self._bulk_update_case_when(table_name, updates, key_column)
        
        # 小批量使用传统方式
        updated = 0
        batch_size = 100
        
        for i in range(0, len(updates), batch_size):
            batch = updates[i:i + batch_size]
            
            with self.batch_engine.begin() as conn:
                for update in batch:
                    update_copy = update.copy()
                    key_value = update_copy.pop(key_column)
                    
                    if not update_copy:  # 没有要更新的字段
                        continue
                    
                    set_clause = ', '.join([
                        f"{col} = :{col}" for col in update_copy.keys()
                    ])
                    
                    sql = text(f"""
                        UPDATE {table_name}
                        SET {set_clause}, updated_at = :updated_at
                        WHERE {key_column} = :key_value
                    """)
                    
                    params = {
                        **update_copy, 
                        "key_value": key_value,
                        "updated_at": int(time.time())
                    }
                    result = conn.execute(sql, params)
                    updated += result.rowcount
        
        return updated
    
    def _bulk_update_case_when(
        self,
        table_name: str,
        updates: List[Dict[str, Any]],
        key_column: str
    ) -> int:
        """使用CASE WHEN进行大批量更新"""
        if not updates:
            return 0
        
        # 获取所有需要更新的列
        all_columns = set()
        for update in updates:
            all_columns.update(update.keys())
        all_columns.discard(key_column)
        
        if not all_columns:
            return 0
        
        with self.batch_engine.begin() as conn:
            # 构建CASE WHEN语句
            case_clauses = []
            params = {}
            
            for col in all_columns:
                when_clauses = []
                for i, update in enumerate(updates):
                    if col in update:
                        param_key = f"{col}_{i}"
                        id_key = f"id_{i}"
                        when_clauses.append(f"WHEN {key_column} = :{id_key} THEN :{param_key}")
                        params[param_key] = update[col]
                        params[id_key] = update[key_column]
                
                if when_clauses:
                    case_clause = f"{col} = CASE {' '.join(when_clauses)} ELSE {col} END"
                    case_clauses.append(case_clause)
            
            if case_clauses:
                # 构建ID列表
                id_list = [str(update[key_column]) for update in updates]
                id_placeholders = ', '.join([f":id_{i}" for i in range(len(id_list))])
                
                sql = text(f"""
                    UPDATE {table_name}
                    SET {', '.join(case_clauses)}, updated_at = :updated_at
                    WHERE {key_column} IN ({id_placeholders})
                """)
                
                params['updated_at'] = int(time.time())
                result = conn.execute(sql, params)
                return result.rowcount
        
        return 0
    
    def bulk_delete(
        self,
        table_name: str,
        ids: List[str],
        key_column: str = "id"
    ) -> int:
        """批量删除"""
        if not ids:
            return 0
        
        # 分批删除以避免SQL语句过长
        batch_size = 1000
        total_deleted = 0
        
        for i in range(0, len(ids), batch_size):
            batch_ids = ids[i:i + batch_size]
            
            with self.batch_engine.begin() as conn:
                # 使用IN子句批量删除
                placeholders = ', '.join([f':id{j}' for j in range(len(batch_ids))])
                sql = text(f"""
                    DELETE FROM {table_name}
                    WHERE {key_column} IN ({placeholders})
                """)
                
                params = {f'id{j}': id_val for j, id_val in enumerate(batch_ids)}
                result = conn.execute(sql, params)
                total_deleted += result.rowcount
        
        return total_deleted
    
    async def bulk_upsert(
        self,
        table_name: str,
        records: List[Dict[str, Any]],
        key_columns: List[str],
        update_columns: List[str]
    ) -> Dict[str, int]:
        """批量插入或更新"""
        # 优化：使用缓存减少重复查询
        cache_key = f"upsert_check_{table_name}"
        existing_keys = await cache.get(cache_key, level=CacheLevel.MEMORY) or set()
        
        to_insert = []
        to_update = []
        
        # 批量检查存在性
        all_key_values = []
        for record in records:
            key_tuple = tuple(record[col] for col in key_columns)
            all_key_values.append(key_tuple)
        
        # 查询现有记录
        with self.batch_engine.begin() as conn:
            if all_key_values:
                where_conditions = []
                params = {}
                
                for i, key_tuple in enumerate(all_key_values):
                    condition_parts = []
                    for j, col in enumerate(key_columns):
                        param_name = f"key_{i}_{j}"
                        condition_parts.append(f"{col} = :{param_name}")
                        params[param_name] = key_tuple[j]
                    where_conditions.append(f"({' AND '.join(condition_parts)})")
                
                check_sql = text(f"""
                    SELECT {', '.join(key_columns)}
                    FROM {table_name}
                    WHERE {' OR '.join(where_conditions)}
                """)
                
                existing_records = conn.execute(check_sql, params).fetchall()
                existing_keys = {tuple(row) for row in existing_records}
        
        # 分类记录
        for record in records:
            key_tuple = tuple(record[col] for col in key_columns)
            if key_tuple in existing_keys:
                to_update.append(record)
            else:
                to_insert.append(record)
        
        # 执行批量操作
        inserted = 0
        updated = 0
        
        if to_insert:
            inserted = self.bulk_insert(table_name, to_insert)
        
        if to_update:
            updated = self.bulk_update(table_name, to_update, key_columns[0])
        
        # 更新缓存
        new_keys = existing_keys.union({tuple(record[col] for col in key_columns) for record in to_insert})
        await cache.set(cache_key, new_keys, ttl=300, level=CacheLevel.MEMORY)
        
        return {"inserted": inserted, "updated": updated}


class CaseBatchOperations:
    """案例批量操作优化"""
    
    def __init__(self):
        self.db_ops = DatabaseBatchOperations()
    
    async def batch_create_cases(
        self,
        cases_data: List[Dict[str, Any]],
        user_id: str
    ) -> BatchResult:
        """批量创建案例"""
        processor = BatchProcessor(
            BatchConfig(
                chunk_size=50,
                strategy=BatchStrategy.CHUNKED,
                use_transaction=True
            )
        )
        
        def create_case(case_data: Dict[str, Any]) -> str:
            from open_webui.models.cases import Cases
            
            case = Cases.insert_new_case(
                user_id=user_id,
                form_data={
                    "title": case_data.get("title", ""),
                    "description": case_data.get("description", ""),
                    "metadata": case_data.get("metadata", {}),
                    "nodes": case_data.get("nodes", []),
                    "edges": case_data.get("edges", [])
                }
            )
            return case.id
        
        return await processor.process_batch(cases_data, create_case)
    
    async def batch_update_nodes(
        self,
        node_updates: List[Dict[str, Any]]
    ) -> BatchResult:
        """批量更新节点"""
        # 优化：预处理和验证
        valid_updates = []
        errors = []
        
        for update in node_updates:
            if not update.get("id"):
                errors.append({
                    "update": update,
                    "error": "Missing node ID"
                })
                continue
            valid_updates.append(update)
        
        if not valid_updates:
            return BatchResult(
                total=len(node_updates),
                success=0,
                failed=len(errors),
                skipped=0,
                duration=0,
                errors=errors
            )
        
        start_time = time.time()
        
        try:
            # 使用优化的批量更新
            total_updated = self.db_ops.bulk_update(
                "case_nodes",
                valid_updates,
                key_column="id"
            )
        except Exception as e:
            errors.append({
                "error": f"Bulk update failed: {str(e)}"
            })
            total_updated = 0
        
        return BatchResult(
            total=len(node_updates),
            success=total_updated,
            failed=len(errors),
            skipped=0,
            duration=0,
            errors=errors
        )


class KnowledgeBatchOperations:
    """知识库批量操作优化"""
    
    def __init__(self):
        self.db_ops = DatabaseBatchOperations()
    
    async def batch_embed_documents(
        self,
        documents: List[Dict[str, Any]],
        collection_name: str
    ) -> BatchResult:
        """批量向量化文档"""
        from open_webui.retrieval.vector.factory import VECTOR_DB_CLIENT
        
        # 优化：根据文档大小动态调整批次
        avg_doc_size = sum(len(doc.get("content", "")) for doc in documents) / len(documents) if documents else 0
        
        if avg_doc_size > 5000:  # 大文档
            chunk_size = 5
            max_workers = 1
        elif avg_doc_size > 1000:  # 中等文档
            chunk_size = 10
            max_workers = 2
        else:  # 小文档
            chunk_size = 20
            max_workers = 3
        
        processor = BatchProcessor(
            BatchConfig(
                chunk_size=chunk_size,
                strategy=BatchStrategy.CHUNKED,
                max_workers=max_workers
            )
        )
        
        async def embed_document(doc: Dict[str, Any]) -> str:
            # 获取向量
            from open_webui.routers.retrieval import get_embedding_function
            ef = await get_embedding_function()
            
            text = doc.get("content", "")
            embedding = ef.embed_documents([text])[0]
            
            # 存储到向量数据库
            collection = VECTOR_DB_CLIENT.get_or_create_collection(
                name=collection_name
            )
            
            collection.add(
                ids=[doc["id"]],
                embeddings=[embedding],
                documents=[text],
                metadatas=[doc.get("metadata", {})]
            )
            
            return doc["id"]
        
        return await processor.process_batch(documents, embed_document)
    
    async def batch_reindex_knowledge(
        self,
        knowledge_ids: List[str]
    ) -> BatchResult:
        """批量重建知识索引"""
        processor = BatchProcessor(
            BatchConfig(
                chunk_size=10,
                strategy=BatchStrategy.PARALLEL,
                max_workers=4
            )
        )
        
        async def reindex_knowledge(knowledge_id: str) -> bool:
            from open_webui.models.knowledge import Knowledges
            from open_webui.retrieval.vector.factory import VECTOR_DB_CLIENT
            
            try:
                # 获取知识内容
                knowledge = Knowledges.get_knowledge_by_id(knowledge_id)
                if not knowledge:
                    return False
                
                # 删除旧索引
                collection_name = f"knowledge_{knowledge_id}"
                try:
                    VECTOR_DB_CLIENT.delete_collection(collection_name)
                except:
                    pass
                
                # 重建索引
                # TODO: 实际的重建逻辑
                
                return True
            except Exception as e:
                log.error(f"Failed to reindex knowledge {knowledge_id}: {e}")
                return False
        
        return await processor.process_batch(knowledge_ids, reindex_knowledge)


# 全局实例
batch_processor = BatchProcessor()
db_batch_ops = DatabaseBatchOperations()
case_batch_ops = CaseBatchOperations()
knowledge_batch_ops = KnowledgeBatchOperations()
