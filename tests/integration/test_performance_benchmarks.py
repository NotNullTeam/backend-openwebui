"""
性能基准测试

验证批量操作和缓存优化的性能提升
"""

import pytest
import time
import asyncio
from unittest.mock import Mock, patch
from typing import List, Dict, Any

from open_webui.services.batch_operations import (
    DatabaseBatchOperations,
    CaseBatchOperations,
    KnowledgeBatchOperations,
    BatchProcessor,
    BatchConfig,
    BatchStrategy
)
from open_webui.services.cache import MultiLevelCache, CacheConfig


class TestBatchOperationPerformance:
    """批量操作性能测试"""
    
    @pytest.fixture
    def db_ops(self):
        return DatabaseBatchOperations()
    
    @pytest.fixture
    def sample_records(self):
        """生成测试记录"""
        return [
            {
                "id": f"record_{i}",
                "name": f"name_{i}",
                "status": "active",
                "created_at": int(time.time()),
                "updated_at": int(time.time())
            }
            for i in range(1000)
        ]
    
    def test_bulk_insert_performance(self, db_ops, sample_records):
        """测试批量插入性能"""
        # 模拟批量插入
        with patch.object(db_ops.batch_engine, 'begin') as mock_begin:
            mock_conn = Mock()
            mock_result = Mock()
            mock_result.rowcount = len(sample_records)
            mock_conn.execute.return_value = mock_result
            mock_begin.return_value.__enter__.return_value = mock_conn
            
            start_time = time.time()
            result = db_ops.bulk_insert("test_table", sample_records)
            duration = time.time() - start_time
            
            # 验证性能指标
            assert result == 1000
            assert duration < 1.0  # 应在1秒内完成
            
            # 验证分批处理（1000条记录应该分成1批）
            assert mock_conn.execute.call_count == 1
    
    def test_bulk_update_case_when_performance(self, db_ops):
        """测试CASE WHEN批量更新性能"""
        # 创建大量更新记录
        updates = [
            {
                "id": f"id_{i}",
                "name": f"updated_name_{i}",
                "status": "updated"
            }
            for i in range(500)
        ]
        
        with patch.object(db_ops.batch_engine, 'begin') as mock_begin:
            mock_conn = Mock()
            mock_result = Mock()
            mock_result.rowcount = len(updates)
            mock_conn.execute.return_value = mock_result
            mock_begin.return_value.__enter__.return_value = mock_conn
            
            start_time = time.time()
            result = db_ops.bulk_update("test_table", updates)
            duration = time.time() - start_time
            
            # 验证使用了CASE WHEN策略（大批量）
            assert result == 500
            assert duration < 0.5  # CASE WHEN应该更快
            
            # 验证只执行了一次SQL（CASE WHEN合并更新）
            assert mock_conn.execute.call_count == 1
    
    def test_bulk_delete_batching_performance(self, db_ops):
        """测试批量删除分批性能"""
        # 创建大量ID（超过1000，会触发分批）
        ids = [f"id_{i}" for i in range(2500)]
        
        with patch.object(db_ops.batch_engine, 'begin') as mock_begin:
            mock_conn = Mock()
            mock_result = Mock()
            mock_result.rowcount = 1000  # 每批1000条
            mock_conn.execute.return_value = mock_result
            mock_begin.return_value.__enter__.return_value = mock_conn
            
            start_time = time.time()
            result = db_ops.bulk_delete("test_table", ids)
            duration = time.time() - start_time
            
            # 验证分批处理
            assert result == 3000  # 3批 × 1000条/批
            assert duration < 1.0
            
            # 验证执行了3次SQL（分3批）
            assert mock_conn.execute.call_count == 3
    
    @pytest.mark.asyncio
    async def test_batch_upsert_caching_performance(self, db_ops):
        """测试批量upsert缓存性能"""
        records = [
            {"id": f"record_{i}", "name": f"name_{i}"}
            for i in range(100)
        ]
        
        with patch('open_webui.services.batch_operations.cache') as mock_cache:
            # 模拟缓存命中
            existing_keys = {("record_1",), ("record_2",)}
            mock_cache.get.return_value = existing_keys
            
            with patch.object(db_ops, 'bulk_insert') as mock_insert:
                with patch.object(db_ops, 'bulk_update') as mock_update:
                    mock_insert.return_value = 98  # 98条新记录
                    mock_update.return_value = 2   # 2条更新记录
                    
                    start_time = time.time()
                    result = await db_ops.bulk_upsert(
                        "test_table", 
                        records, 
                        ["id"], 
                        ["name"]
                    )
                    duration = time.time() - start_time
                    
                    # 验证缓存优化效果
                    assert result["inserted"] == 98
                    assert result["updated"] == 2
                    assert duration < 0.1  # 缓存应该显著提升性能
                    
                    # 验证缓存被使用
                    mock_cache.get.assert_called_once()
                    mock_cache.set.assert_called_once()


class TestCachePerformance:
    """缓存性能测试"""
    
    @pytest.fixture
    def cache_config(self):
        return CacheConfig(
            max_memory_items=1000,
            default_ttl=3600,
            enable_compression=True,
            compression_threshold=1024
        )
    
    @pytest.fixture
    def cache(self, cache_config):
        with patch('open_webui.services.cache.redis.Redis'):
            return MultiLevelCache(cache_config)
    
    @pytest.mark.asyncio
    async def test_memory_cache_performance(self, cache):
        """测试内存缓存性能"""
        # 测试大量小对象缓存
        test_data = {f"key_{i}": f"value_{i}" for i in range(1000)}
        
        # 写入性能测试
        start_time = time.time()
        for key, value in test_data.items():
            await cache.set(key, value, namespace="perf_test")
        write_duration = time.time() - start_time
        
        # 读取性能测试
        start_time = time.time()
        for key in test_data.keys():
            result = await cache.get(key, namespace="perf_test")
            assert result is not None
        read_duration = time.time() - start_time
        
        # 验证性能指标
        assert write_duration < 0.5  # 1000次写入应在0.5秒内完成
        assert read_duration < 0.1   # 1000次读取应在0.1秒内完成
        
        # 验证命中率
        stats = cache.get_statistics()
        assert stats["hit_rate"] > 0.9  # 命中率应该很高
    
    @pytest.mark.asyncio
    async def test_compression_performance(self, cache):
        """测试压缩性能"""
        # 创建大对象（超过压缩阈值）
        large_data = "x" * 2048  # 2KB数据
        
        start_time = time.time()
        await cache.set("large_key", large_data)
        compression_time = time.time() - start_time
        
        start_time = time.time()
        result = await cache.get("large_key")
        decompression_time = time.time() - start_time
        
        # 验证数据正确性
        assert result == large_data
        
        # 验证压缩性能
        assert compression_time < 0.01    # 压缩应该很快
        assert decompression_time < 0.01  # 解压应该很快
    
    @pytest.mark.asyncio
    async def test_cache_pattern_deletion_performance(self, cache):
        """测试模式删除性能"""
        # 设置大量缓存项
        for i in range(500):
            await cache.set(f"pattern_test_{i}", f"value_{i}")
            await cache.set(f"other_key_{i}", f"other_value_{i}")
        
        start_time = time.time()
        deleted_count = await cache.delete("pattern_test_*", pattern=True)
        deletion_time = time.time() - start_time
        
        # 验证删除效果和性能
        assert deleted_count == 500  # 应该删除500个匹配项
        assert deletion_time < 0.5    # 模式删除应该较快
        
        # 验证其他键未被删除
        result = await cache.get("other_key_0")
        assert result == "other_value_0"


class TestBatchProcessorPerformance:
    """批量处理器性能测试"""
    
    @pytest.mark.asyncio
    async def test_parallel_processing_performance(self):
        """测试并行处理性能"""
        # 模拟耗时操作
        async def slow_processor(item):
            await asyncio.sleep(0.01)  # 模拟10ms处理时间
            return f"processed_{item}"
        
        items = list(range(100))
        
        # 测试并行处理
        config = BatchConfig(
            strategy=BatchStrategy.PARALLEL,
            max_workers=10
        )
        
        processor = BatchProcessor(config)
        
        start_time = time.time()
        result = await processor.process_batch(items, slow_processor)
        parallel_duration = time.time() - start_time
        
        # 验证并行处理效果
        assert result.success == 100
        assert result.failed == 0
        # 并行处理应该显著快于顺序处理
        # 100个10ms的任务，并行10个worker，理论上约100ms
        assert parallel_duration < 0.5
    
    @pytest.mark.asyncio
    async def test_chunked_processing_performance(self):
        """测试分块处理性能"""
        async def batch_processor(item):
            # 模拟批量处理
            await asyncio.sleep(0.001)
            return f"batch_processed_{item}"
        
        items = list(range(1000))
        
        config = BatchConfig(
            strategy=BatchStrategy.CHUNKED,
            chunk_size=100,
            max_workers=5
        )
        
        processor = BatchProcessor(config)
        
        start_time = time.time()
        result = await processor.process_batch(items, batch_processor)
        chunked_duration = time.time() - start_time
        
        # 验证分块处理效果
        assert result.success == 1000
        assert result.failed == 0
        assert chunked_duration < 1.0  # 应该在1秒内完成
    
    @pytest.mark.asyncio
    async def test_retry_mechanism_performance(self):
        """测试重试机制性能"""
        call_count = 0
        
        async def flaky_processor(item):
            nonlocal call_count
            call_count += 1
            
            # 前两次调用失败，第三次成功
            if call_count <= 2:
                raise Exception("Temporary failure")
            
            return f"retry_success_{item}"
        
        config = BatchConfig(
            max_retries=3,
            retry_failed=True
        )
        
        processor = BatchProcessor(config)
        
        start_time = time.time()
        result = await processor.process_batch([1], flaky_processor)
        retry_duration = time.time() - start_time
        
        # 验证重试成功
        assert result.success == 1
        assert result.failed == 0
        assert call_count == 3  # 重试了3次
        
        # 验证指数退避不会过度延迟
        assert retry_duration < 5.0  # 重试总时间应合理


class TestRealWorldScenarios:
    """真实场景性能测试"""
    
    @pytest.mark.asyncio
    async def test_case_batch_creation_performance(self):
        """测试案例批量创建性能"""
        case_ops = CaseBatchOperations()
        
        # 模拟100个案例数据
        cases_data = [
            {
                "title": f"测试案例 {i}",
                "description": f"这是第{i}个测试案例",
                "metadata": {"priority": "normal"},
                "nodes": [{"title": f"节点{j}", "content": f"内容{j}"} for j in range(5)],
                "edges": []
            }
            for i in range(100)
        ]
        
        with patch('open_webui.models.cases.Cases.insert_new_case') as mock_insert:
            mock_insert.return_value = Mock(id=lambda: f"case_{time.time()}")
            
            start_time = time.time()
            result = await case_ops.batch_create_cases(cases_data, "test_user")
            duration = time.time() - start_time
            
            # 验证批量创建性能
            assert result.success == 100
            assert result.failed == 0
            assert duration < 2.0  # 100个案例应在2秒内创建完成
    
    @pytest.mark.asyncio
    async def test_knowledge_batch_embedding_performance(self):
        """测试知识库批量向量化性能"""
        knowledge_ops = KnowledgeBatchOperations()
        
        # 模拟不同大小的文档
        documents = []
        
        # 小文档（50个）
        for i in range(50):
            documents.append({
                "id": f"small_doc_{i}",
                "content": "这是一个小文档。" * 10,  # ~150字符
                "metadata": {"type": "small"}
            })
        
        # 中等文档（30个）
        for i in range(30):
            documents.append({
                "id": f"medium_doc_{i}",
                "content": "这是一个中等大小的文档。" * 100,  # ~1500字符
                "metadata": {"type": "medium"}
            })
        
        # 大文档（10个）
        for i in range(10):
            documents.append({
                "id": f"large_doc_{i}",
                "content": "这是一个大文档。" * 1000,  # ~15000字符
                "metadata": {"type": "large"}
            })
        
        with patch('open_webui.services.batch_operations.VECTOR_DB_CLIENT') as mock_vector:
            with patch('open_webui.routers.retrieval.get_embedding_function') as mock_ef:
                # 模拟向量化
                mock_ef.return_value = AsyncMock()
                mock_ef.return_value.embed_documents.return_value = [[0.1] * 768]
                
                mock_collection = Mock()
                mock_vector.get_or_create_collection.return_value = mock_collection
                
                start_time = time.time()
                result = await knowledge_ops.batch_embed_documents(
                    documents, 
                    "test_collection"
                )
                duration = time.time() - start_time
                
                # 验证动态批次调整效果
                assert result.success == 90  # 90个文档
                assert result.failed == 0
                
                # 不同大小文档应该用不同批次大小，总体性能应该合理
                assert duration < 5.0  # 90个文档向量化应在5秒内完成


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
