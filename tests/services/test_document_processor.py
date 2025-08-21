"""
文档处理服务单元测试
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from pathlib import Path

from open_webui.services.document_processor import (
    DocumentProcessor,
    ProcessingStatus,
    document_processor,
    queue_document_for_processing,
    get_document_processing_status
)

class TestDocumentProcessor:
    """文档处理器测试类"""
    
    @pytest.fixture
    def processor(self):
        """创建测试用的文档处理器"""
        return DocumentProcessor()
    
    @pytest.fixture
    def mock_file(self):
        """模拟文件对象"""
        file = Mock()
        file.id = "test_file_id"
        file.filename = "test_document.pdf"
        file.user_id = "test_user_id"
        file.meta = {
            "size": 1024,
            "content_type": "application/pdf"
        }
        return file
    
    @pytest.fixture
    def sample_chunks(self):
        """示例文档分块"""
        return [
            {
                "content": "这是第一个分块的内容",
                "metadata": {
                    "source": "test_document.pdf",
                    "page": 1,
                    "chunk_index": 0
                }
            },
            {
                "content": "这是第二个分块的内容",
                "metadata": {
                    "source": "test_document.pdf",
                    "page": 2,
                    "chunk_index": 1
                }
            }
        ]
    
    @pytest.mark.asyncio
    async def test_queue_document_success(self, processor):
        """测试文档加入队列成功"""
        with patch.object(processor, '_update_processing_status') as mock_update:
            mock_update.return_value = None
            
            result = await processor.queue_document("test_file_id")
            
            assert result is True
            mock_update.assert_called_with("test_file_id", ProcessingStatus.QUEUED, 0)
    
    @pytest.mark.asyncio
    async def test_queue_document_failure(self, processor):
        """测试文档加入队列失败"""
        with patch.object(processor, '_update_processing_status') as mock_update:
            mock_update.side_effect = Exception("Update failed")
            
            result = await processor.queue_document("test_file_id")
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_get_processing_status_success(self, processor, mock_file):
        """测试获取处理状态成功"""
        mock_file.meta = {
            "processing_status": ProcessingStatus.PROCESSING,
            "processing_progress": 50,
            "processing_started_at": "2024-01-01T10:00:00Z"
        }
        
        with patch('open_webui.services.document_processor.Files') as mock_files:
            mock_files.get_file_by_id.return_value = mock_file
            
            status = await processor.get_processing_status("test_file_id")
            
            assert status["status"] == ProcessingStatus.PROCESSING
            assert status["progress"] == 50
            assert status["started_at"] == "2024-01-01T10:00:00Z"
            assert status["retry_count"] == 0
            assert status["is_processing"] is False
    
    @pytest.mark.asyncio
    async def test_get_processing_status_file_not_found(self, processor):
        """测试文件不存在时的状态"""
        with patch('open_webui.services.document_processor.Files') as mock_files:
            mock_files.get_file_by_id.return_value = None
            
            status = await processor.get_processing_status("nonexistent_file")
            
            assert status["status"] == "NOT_FOUND"
            assert status["progress"] == 0
    
    @pytest.mark.asyncio
    async def test_cancel_processing_success(self, processor):
        """测试取消处理成功"""
        # 模拟正在处理的任务
        mock_task = Mock()
        processor.processing_tasks["test_file_id"] = mock_task
        
        with patch.object(processor, '_update_processing_status') as mock_update:
            mock_update.return_value = None
            
            result = await processor.cancel_processing("test_file_id")
            
            assert result is True
            mock_task.cancel.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cancel_processing_not_processing(self, processor):
        """测试取消未在处理的文档"""
        result = await processor.cancel_processing("test_file_id")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_retry_failed_document_success(self, processor):
        """测试重试失败文档成功"""
        with patch.object(processor, 'get_processing_status') as mock_get_status:
            mock_get_status.return_value = {"status": ProcessingStatus.FAILED}
            
            with patch.object(processor, 'queue_document') as mock_queue:
                mock_queue.return_value = True
                
                result = await processor.retry_failed_document("test_file_id")
                
                assert result is True
                assert processor.retry_counts["test_file_id"] == 1
    
    @pytest.mark.asyncio
    async def test_retry_failed_document_max_retries_exceeded(self, processor):
        """测试超过最大重试次数"""
        processor.retry_counts["test_file_id"] = processor.max_retries
        
        with patch.object(processor, 'get_processing_status') as mock_get_status:
            mock_get_status.return_value = {"status": ProcessingStatus.FAILED}
            
            result = await processor.retry_failed_document("test_file_id")
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_retry_failed_document_not_failed(self, processor):
        """测试重试非失败状态的文档"""
        with patch.object(processor, 'get_processing_status') as mock_get_status:
            mock_get_status.return_value = {"status": ProcessingStatus.COMPLETED}
            
            result = await processor.retry_failed_document("test_file_id")
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_extract_and_chunk_document_success(self, processor, sample_chunks):
        """测试文档提取和分块成功"""
        file_path = Path("test_document.pdf")
        file_meta = {"loader_config": {}}
        
        # 模拟文档对象
        mock_doc1 = Mock()
        mock_doc1.text = "这是第一个分块的内容"
        mock_doc1.metadata = {"page": 1}
        
        mock_doc2 = Mock()
        mock_doc2.text = "这是第二个分块的内容"
        mock_doc2.metadata = {"page": 2}
        
        with patch('open_webui.services.document_processor.Loader') as mock_loader_class:
            mock_loader = Mock()
            mock_loader_class.return_value = mock_loader
            mock_loader.load_data.return_value = [mock_doc1, mock_doc2]
            
            chunks = await processor._extract_and_chunk_document(file_path, file_meta)
            
            assert len(chunks) == 2
            assert chunks[0]["content"] == "这是第一个分块的内容"
            assert chunks[1]["content"] == "这是第二个分块的内容"
            assert chunks[0]["metadata"]["page"] == 1
            assert chunks[1]["metadata"]["page"] == 2
    
    @pytest.mark.asyncio
    async def test_extract_and_chunk_document_failure(self, processor):
        """测试文档提取失败"""
        file_path = Path("test_document.pdf")
        file_meta = {}
        
        with patch('open_webui.services.document_processor.Loader') as mock_loader_class:
            mock_loader = Mock()
            mock_loader_class.return_value = mock_loader
            mock_loader.load_data.side_effect = Exception("Loading failed")
            
            with pytest.raises(Exception, match="Loading failed"):
                await processor._extract_and_chunk_document(file_path, file_meta)
    
    @pytest.mark.asyncio
    async def test_vectorize_chunks_success(self, processor, sample_chunks):
        """测试向量化分块成功"""
        with patch('open_webui.services.document_processor.get_retrieval_vector_db') as mock_get_db:
            mock_vector_db = Mock()
            mock_get_db.return_value = mock_vector_db
            
            await processor._vectorize_chunks("test_file_id", sample_chunks)
            
            # 验证向量数据库调用
            mock_vector_db.add_texts.assert_called_once()
            call_args = mock_vector_db.add_texts.call_args
            texts = call_args[0][0]
            metadatas = call_args[0][1]
            
            assert len(texts) == 2
            assert texts[0] == "这是第一个分块的内容"
            assert texts[1] == "这是第二个分块的内容"
            assert all(meta["file_id"] == "test_file_id" for meta in metadatas)
    
    @pytest.mark.asyncio
    async def test_vectorize_chunks_no_vector_db(self, processor, sample_chunks):
        """测试向量数据库不可用"""
        with patch('open_webui.services.document_processor.get_retrieval_vector_db') as mock_get_db:
            mock_get_db.return_value = None
            
            with pytest.raises(Exception, match="Vector database not available"):
                await processor._vectorize_chunks("test_file_id", sample_chunks)
    
    @pytest.mark.asyncio
    async def test_save_knowledge_entries_success(self, processor, sample_chunks, mock_file):
        """测试保存知识条目成功"""
        with patch('open_webui.services.document_processor.Files') as mock_files:
            mock_files.get_file_by_id.return_value = mock_file
            
            with patch('open_webui.services.document_processor.Knowledges') as mock_knowledges:
                mock_knowledge = Mock()
                mock_knowledge.id = "knowledge_id"
                mock_knowledges.insert_new_knowledge.return_value = mock_knowledge
                
                await processor._save_knowledge_entries("test_file_id", sample_chunks, "test_user_id")
                
                # 验证知识条目创建
                mock_knowledges.insert_new_knowledge.assert_called_once()
                call_args = mock_knowledges.insert_new_knowledge.call_args
                user_id = call_args[0][0]
                knowledge_data = call_args[0][1]
                
                assert user_id == "test_user_id"
                assert knowledge_data["name"] == "test_document.pdf"
                assert knowledge_data["data"]["chunks_count"] == 2
    
    @pytest.mark.asyncio
    async def test_save_knowledge_entries_file_not_found(self, processor, sample_chunks):
        """测试文件不存在时保存知识条目"""
        with patch('open_webui.services.document_processor.Files') as mock_files:
            mock_files.get_file_by_id.return_value = None
            
            # 不应该抛出异常，只是记录错误
            await processor._save_knowledge_entries("test_file_id", sample_chunks, "test_user_id")
    
    @pytest.mark.asyncio
    async def test_update_processing_status_success(self, processor, mock_file):
        """测试更新处理状态成功"""
        with patch('open_webui.services.document_processor.Files') as mock_files:
            mock_files.get_file_by_id.return_value = mock_file
            mock_files.update_file_metadata_by_id.return_value = True
            
            await processor._update_processing_status(
                "test_file_id", 
                ProcessingStatus.PROCESSING, 
                50, 
                None
            )
            
            # 验证更新调用
            mock_files.update_file_metadata_by_id.assert_called_once()
            call_args = mock_files.update_file_metadata_by_id.call_args
            file_id = call_args[0][0]
            meta = call_args[0][1]
            
            assert file_id == "test_file_id"
            assert meta["processing_status"] == ProcessingStatus.PROCESSING
            assert meta["processing_progress"] == 50
    
    @pytest.mark.asyncio
    async def test_update_processing_status_with_error(self, processor, mock_file):
        """测试更新处理状态包含错误信息"""
        with patch('open_webui.services.document_processor.Files') as mock_files:
            mock_files.get_file_by_id.return_value = mock_file
            mock_files.update_file_metadata_by_id.return_value = True
            
            await processor._update_processing_status(
                "test_file_id", 
                ProcessingStatus.FAILED, 
                0, 
                "Processing error"
            )
            
            # 验证错误信息被保存
            call_args = mock_files.update_file_metadata_by_id.call_args
            meta = call_args[0][1]
            
            assert meta["processing_status"] == ProcessingStatus.FAILED
            assert meta["processing_error"] == "Processing error"
    
    @pytest.mark.asyncio
    async def test_process_document_success(self, processor, mock_file, sample_chunks):
        """测试完整文档处理流程成功"""
        # 设置模拟
        with patch('open_webui.services.document_processor.Files') as mock_files:
            mock_files.get_file_by_id.return_value = mock_file
            
            with patch('open_webui.services.document_processor.DATA_DIR', "/test/data"):
                with patch('pathlib.Path.exists', return_value=True):
                    with patch.object(processor, '_extract_and_chunk_document') as mock_extract:
                        mock_extract.return_value = sample_chunks
                        
                        with patch.object(processor, '_vectorize_chunks') as mock_vectorize:
                            mock_vectorize.return_value = None
                            
                            with patch.object(processor, '_save_knowledge_entries') as mock_save:
                                mock_save.return_value = None
                                
                                with patch.object(processor, '_update_processing_status') as mock_update:
                                    mock_update.return_value = None
                                    
                                    await processor._process_document("test_file_id")
                                    
                                    # 验证所有步骤都被调用
                                    mock_extract.assert_called_once()
                                    mock_vectorize.assert_called_once()
                                    mock_save.assert_called_once()
                                    
                                    # 验证状态更新调用
                                    assert mock_update.call_count >= 4  # 至少4次状态更新
    
    @pytest.mark.asyncio
    async def test_process_document_file_not_found(self, processor):
        """测试处理不存在的文件"""
        with patch('open_webui.services.document_processor.Files') as mock_files:
            mock_files.get_file_by_id.return_value = None
            
            with patch.object(processor, '_update_processing_status') as mock_update:
                mock_update.return_value = None
                
                await processor._process_document("nonexistent_file")
                
                # 验证失败状态被设置
                mock_update.assert_called_with(
                    "nonexistent_file", 
                    ProcessingStatus.FAILED, 
                    0, 
                    "Processing failed: File nonexistent_file not found"
                )
    
    @pytest.mark.asyncio
    async def test_process_document_with_retry(self, processor, mock_file):
        """测试文档处理失败后重试"""
        processor.retry_counts["test_file_id"] = 1  # 已重试1次
        
        with patch('open_webui.services.document_processor.Files') as mock_files:
            mock_files.get_file_by_id.return_value = mock_file
            
            with patch('pathlib.Path.exists', return_value=False):  # 文件不存在，触发异常
                with patch.object(processor, '_update_processing_status') as mock_update:
                    mock_update.return_value = None
                    
                    with patch.object(processor, 'retry_failed_document') as mock_retry:
                        mock_retry.return_value = True
                        
                        with patch('asyncio.sleep'):  # 避免实际等待
                            await processor._process_document("test_file_id")
                            
                            # 验证重试被调用
                            mock_retry.assert_called_once_with("test_file_id")

class TestDocumentProcessorGlobalFunctions:
    """文档处理器全局函数测试"""
    
    def test_queue_document_for_processing_sync(self):
        """测试同步队列文档接口"""
        with patch('open_webui.services.document_processor.document_processor') as mock_processor:
            mock_processor.queue_document = AsyncMock(return_value=True)
            
            result = queue_document_for_processing("test_file_id")
            
            assert result is True
    
    def test_get_document_processing_status_sync(self):
        """测试同步获取状态接口"""
        expected_status = {
            "status": ProcessingStatus.COMPLETED,
            "progress": 100
        }
        
        with patch('open_webui.services.document_processor.document_processor') as mock_processor:
            mock_processor.get_processing_status = AsyncMock(return_value=expected_status)
            
            result = get_document_processing_status("test_file_id")
            
            assert result == expected_status

if __name__ == "__main__":
    pytest.main([__file__])
