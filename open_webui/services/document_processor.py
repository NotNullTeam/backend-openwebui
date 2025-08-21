"""
文档异步处理服务

提供文档解析、向量化、状态跟踪等异步处理功能
"""

import asyncio
import json
import logging
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum
from pathlib import Path

from open_webui.models.files import Files
from open_webui.models.knowledge import Knowledges
from open_webui.retrieval.loaders.main import Loader
from open_webui.retrieval.vector.main import get_retrieval_vector_db
from open_webui.config import CONTENT_EXTRACTION_ENGINE, DATA_DIR

logger = logging.getLogger(__name__)

class ProcessingStatus(str, Enum):
    """文档处理状态"""
    UPLOADED = "UPLOADED"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    CHUNKING = "CHUNKING"
    VECTORIZING = "VECTORIZING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"

class DocumentProcessor:
    """文档异步处理器"""
    
    def __init__(self):
        self.processing_queue = asyncio.Queue()
        self.processing_tasks = {}
        self.retry_counts = {}
        self.max_retries = 3
        self.retry_delay = 60  # 秒
        
    async def start_processing_worker(self):
        """启动处理工作线程"""
        while True:
            try:
                file_id = await self.processing_queue.get()
                if file_id in self.processing_tasks:
                    continue
                
                # 创建处理任务
                task = asyncio.create_task(self._process_document(file_id))
                self.processing_tasks[file_id] = task
                
                # 等待任务完成并清理
                try:
                    await task
                finally:
                    self.processing_tasks.pop(file_id, None)
                    
            except Exception as e:
                logger.error(f"Processing worker error: {e}")
                await asyncio.sleep(5)
    
    async def queue_document(self, file_id: str) -> bool:
        """将文档加入处理队列"""
        try:
            # 更新状态为排队
            await self._update_processing_status(file_id, ProcessingStatus.QUEUED, 0)
            
            # 加入队列
            await self.processing_queue.put(file_id)
            logger.info(f"Document {file_id} queued for processing")
            return True
            
        except Exception as e:
            logger.error(f"Failed to queue document {file_id}: {e}")
            await self._update_processing_status(file_id, ProcessingStatus.FAILED, 0, str(e))
            return False
    
    async def get_processing_status(self, file_id: str) -> Dict[str, Any]:
        """获取文档处理状态"""
        try:
            file = Files.get_file_by_id(file_id)
            if not file:
                return {"status": "NOT_FOUND", "progress": 0}
            
            meta = file.meta or {}
            return {
                "status": meta.get("processing_status", ProcessingStatus.UPLOADED),
                "progress": meta.get("processing_progress", 0),
                "error": meta.get("processing_error"),
                "started_at": meta.get("processing_started_at"),
                "completed_at": meta.get("processing_completed_at"),
                "retry_count": self.retry_counts.get(file_id, 0),
                "is_processing": file_id in self.processing_tasks
            }
            
        except Exception as e:
            logger.error(f"Failed to get processing status for {file_id}: {e}")
            return {"status": "ERROR", "progress": 0, "error": str(e)}
    
    async def cancel_processing(self, file_id: str) -> bool:
        """取消文档处理"""
        try:
            if file_id in self.processing_tasks:
                task = self.processing_tasks[file_id]
                task.cancel()
                await self._update_processing_status(file_id, ProcessingStatus.FAILED, 0, "Processing cancelled")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Failed to cancel processing for {file_id}: {e}")
            return False
    
    async def retry_failed_document(self, file_id: str) -> bool:
        """重试失败的文档处理"""
        try:
            status_info = await self.get_processing_status(file_id)
            if status_info["status"] != ProcessingStatus.FAILED:
                return False
            
            retry_count = self.retry_counts.get(file_id, 0)
            if retry_count >= self.max_retries:
                logger.warning(f"Document {file_id} has exceeded max retries")
                return False
            
            self.retry_counts[file_id] = retry_count + 1
            await self.queue_document(file_id)
            return True
            
        except Exception as e:
            logger.error(f"Failed to retry document {file_id}: {e}")
            return False
    
    async def _process_document(self, file_id: str):
        """处理单个文档"""
        try:
            logger.info(f"Starting processing for document {file_id}")
            
            # 更新状态为处理中
            await self._update_processing_status(file_id, ProcessingStatus.PROCESSING, 10)
            
            # 获取文件信息
            file = Files.get_file_by_id(file_id)
            if not file:
                raise Exception(f"File {file_id} not found")
            
            file_path = Path(DATA_DIR) / "uploads" / file.filename
            if not file_path.exists():
                raise Exception(f"File {file_path} does not exist")
            
            # 阶段1: 文档解析和分块
            await self._update_processing_status(file_id, ProcessingStatus.CHUNKING, 30)
            chunks = await self._extract_and_chunk_document(file_path, file.meta)
            
            if not chunks:
                raise Exception("No content extracted from document")
            
            # 阶段2: 向量化
            await self._update_processing_status(file_id, ProcessingStatus.VECTORIZING, 60)
            await self._vectorize_chunks(file_id, chunks)
            
            # 阶段3: 保存知识条目
            await self._update_processing_status(file_id, ProcessingStatus.VECTORIZING, 80)
            await self._save_knowledge_entries(file_id, chunks, file.user_id)
            
            # 完成处理
            await self._update_processing_status(file_id, ProcessingStatus.COMPLETED, 100)
            logger.info(f"Document {file_id} processed successfully")
            
            # 清理重试计数
            self.retry_counts.pop(file_id, None)
            
        except asyncio.CancelledError:
            logger.info(f"Processing cancelled for document {file_id}")
            await self._update_processing_status(file_id, ProcessingStatus.FAILED, 0, "Processing cancelled")
            
        except Exception as e:
            error_msg = f"Processing failed: {str(e)}"
            logger.error(f"Document {file_id} processing error: {error_msg}")
            logger.error(traceback.format_exc())
            
            # 检查是否需要重试
            retry_count = self.retry_counts.get(file_id, 0)
            if retry_count < self.max_retries:
                await self._update_processing_status(file_id, ProcessingStatus.RETRYING, 0, error_msg)
                # 延迟重试
                await asyncio.sleep(self.retry_delay * (retry_count + 1))
                await self.retry_failed_document(file_id)
            else:
                await self._update_processing_status(file_id, ProcessingStatus.FAILED, 0, error_msg)
    
    async def _extract_and_chunk_document(self, file_path: Path, file_meta: Dict) -> List[Dict]:
        """提取和分块文档内容"""
        try:
            # 使用现有的Loader进行文档解析
            loader = Loader(
                engine=CONTENT_EXTRACTION_ENGINE,
                **file_meta.get("loader_config", {})
            )
            
            # 异步执行文档加载
            loop = asyncio.get_event_loop()
            docs = await loop.run_in_executor(None, loader.load_data, [str(file_path)])
            
            chunks = []
            for doc in docs:
                # 构建分块数据
                chunk = {
                    "content": doc.text,
                    "metadata": {
                        "source": str(file_path),
                        "page": doc.metadata.get("page", 0),
                        "chunk_index": len(chunks),
                        **doc.metadata
                    }
                }
                chunks.append(chunk)
            
            logger.info(f"Extracted {len(chunks)} chunks from {file_path}")
            return chunks
            
        except Exception as e:
            logger.error(f"Failed to extract content from {file_path}: {e}")
            raise
    
    async def _vectorize_chunks(self, file_id: str, chunks: List[Dict]):
        """向量化文档分块"""
        try:
            vector_db = get_retrieval_vector_db()
            if not vector_db:
                raise Exception("Vector database not available")
            
            # 准备向量化数据
            texts = [chunk["content"] for chunk in chunks]
            metadatas = [chunk["metadata"] for chunk in chunks]
            
            # 添加文件ID到元数据
            for metadata in metadatas:
                metadata["file_id"] = file_id
            
            # 异步执行向量化
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, vector_db.add_texts, texts, metadatas)
            
            logger.info(f"Vectorized {len(chunks)} chunks for file {file_id}")
            
        except Exception as e:
            logger.error(f"Failed to vectorize chunks for file {file_id}: {e}")
            raise
    
    async def _save_knowledge_entries(self, file_id: str, chunks: List[Dict], user_id: str):
        """保存知识条目到数据库"""
        try:
            file = Files.get_file_by_id(file_id)
            if not file:
                raise Exception(f"File {file_id} not found")
            
            # 创建知识条目
            knowledge_data = {
                "name": file.filename,
                "description": f"从文档 {file.filename} 提取的知识",
                "data": {
                    "file_id": file_id,
                    "chunks_count": len(chunks),
                    "total_content_length": sum(len(chunk["content"]) for chunk in chunks)
                }
            }
            
            knowledge = Knowledges.insert_new_knowledge(user_id, knowledge_data)
            if knowledge:
                logger.info(f"Created knowledge entry {knowledge.id} for file {file_id}")
            
        except Exception as e:
            logger.error(f"Failed to save knowledge entries for file {file_id}: {e}")
            # 这个错误不应该导致整个处理失败
    
    async def _update_processing_status(self, file_id: str, status: ProcessingStatus, 
                                      progress: int, error: Optional[str] = None):
        """更新文档处理状态"""
        try:
            file = Files.get_file_by_id(file_id)
            if not file:
                return
            
            meta = file.meta or {}
            meta["processing_status"] = status
            meta["processing_progress"] = progress
            
            if error:
                meta["processing_error"] = error
            elif "processing_error" in meta:
                del meta["processing_error"]
            
            if status == ProcessingStatus.PROCESSING and "processing_started_at" not in meta:
                meta["processing_started_at"] = datetime.now().isoformat()
            
            if status in [ProcessingStatus.COMPLETED, ProcessingStatus.FAILED]:
                meta["processing_completed_at"] = datetime.now().isoformat()
            
            # 更新文件元数据
            Files.update_file_metadata_by_id(file_id, meta)
            
        except Exception as e:
            logger.error(f"Failed to update processing status for {file_id}: {e}")

# 全局处理器实例
document_processor = DocumentProcessor()

async def start_document_processor():
    """启动文档处理器"""
    await document_processor.start_processing_worker()

def queue_document_for_processing(file_id: str) -> bool:
    """将文档加入处理队列（同步接口）"""
    try:
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(document_processor.queue_document(file_id))
    except:
        # 如果没有运行的事件循环，创建新的
        return asyncio.run(document_processor.queue_document(file_id))

def get_document_processing_status(file_id: str) -> Dict[str, Any]:
    """获取文档处理状态（同步接口）"""
    try:
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(document_processor.get_processing_status(file_id))
    except:
        return asyncio.run(document_processor.get_processing_status(file_id))
