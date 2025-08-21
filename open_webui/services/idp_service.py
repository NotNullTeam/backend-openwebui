"""
阿里云IDP文档智能解析服务集成
提供文档解析、版面分析、公式识别等功能
"""

import logging
import json
import uuid
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime
import aiohttp
import hashlib
import hmac
import base64
from urllib.parse import quote

from open_webui.env import SRC_LOG_LEVELS

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])


class IDPConfig:
    """IDP配置"""
    def __init__(self):
        # 从环境变量或配置文件读取
        self.access_key_id = ""  # 需要配置
        self.access_key_secret = ""  # 需要配置
        self.endpoint = "docmind-api.cn-hangzhou.aliyuncs.com"
        self.region = "cn-hangzhou"
        self.version = "2022-07-11"
        self.timeout = 60


class IDPDocument:
    """IDP文档对象"""
    def __init__(self, doc_id: str, status: str = "pending"):
        self.doc_id = doc_id
        self.status = status
        self.pages = []
        self.metadata = {}
        self.created_at = datetime.utcnow()
        self.processed_at = None
        self.error_message = None


class IDPService:
    """IDP文档解析服务"""
    
    def __init__(self, config: Optional[IDPConfig] = None):
        self.config = config or IDPConfig()
        self._documents = {}  # 内存中的文档存储
        
    def _sign_request(self, method: str, params: Dict[str, str]) -> str:
        """生成请求签名"""
        # 阿里云签名算法
        sorted_params = sorted(params.items())
        canonicalized_query = "&".join([f"{quote(k)}={quote(str(v))}" for k, v in sorted_params])
        
        string_to_sign = f"{method}&{quote('/')}&{quote(canonicalized_query)}"
        
        h = hmac.new(
            (self.config.access_key_secret + "&").encode('utf-8'),
            string_to_sign.encode('utf-8'),
            hashlib.sha1
        )
        
        signature = base64.b64encode(h.digest()).decode('utf-8')
        return signature
    
    async def parse_document(
        self,
        file_url: str,
        file_name: str,
        enable_llm: bool = True,
        enable_formula: bool = True,
        async_mode: bool = True
    ) -> Dict[str, Any]:
        """
        解析文档
        
        Args:
            file_url: 文档URL
            file_name: 文件名
            enable_llm: 是否启用大模型增强
            enable_formula: 是否启用公式识别
            async_mode: 是否异步处理
        
        Returns:
            解析结果
        """
        doc_id = str(uuid.uuid4())
        
        # 创建文档记录
        doc = IDPDocument(doc_id)
        self._documents[doc_id] = doc
        
        try:
            if not self.config.access_key_id or not self.config.access_key_secret:
                # 如果没有配置IDP，返回模拟结果
                return await self._mock_parse_document(doc_id, file_name)
            
            # 构建请求参数
            params = {
                "Action": "SubmitDocumentExtractJob",
                "Version": self.config.version,
                "FileUrl": file_url,
                "FileName": file_name,
                "FileType": self._get_file_type(file_name),
                "EnableLLM": str(enable_llm).lower(),
                "EnableFormula": str(enable_formula).lower(),
                "Format": "json",
                "AccessKeyId": self.config.access_key_id,
                "SignatureMethod": "HMAC-SHA1",
                "SignatureVersion": "1.0",
                "SignatureNonce": str(uuid.uuid4()),
                "Timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
            
            # 生成签名
            params["Signature"] = self._sign_request("GET", params)
            
            # 发送请求
            async with aiohttp.ClientSession() as session:
                url = f"https://{self.config.endpoint}"
                async with session.get(url, params=params, timeout=self.config.timeout) as response:
                    if response.status == 200:
                        result = await response.json()
                        
                        if result.get("Code") == "Success":
                            doc.status = "processing"
                            job_id = result.get("JobId")
                            
                            if async_mode:
                                # 异步模式，返回任务ID
                                asyncio.create_task(self._poll_job_status(doc_id, job_id))
                                return {
                                    "doc_id": doc_id,
                                    "status": "processing",
                                    "job_id": job_id,
                                    "message": "文档已提交解析"
                                }
                            else:
                                # 同步模式，等待结果
                                return await self._wait_for_result(doc_id, job_id)
                        else:
                            raise Exception(result.get("Message", "解析失败"))
                    else:
                        raise Exception(f"HTTP {response.status}: {await response.text()}")
                        
        except Exception as e:
            log.error(f"IDP parse document failed: {str(e)}")
            doc.status = "failed"
            doc.error_message = str(e)
            self._documents[doc_id] = doc
            raise
    
    async def _mock_parse_document(self, doc_id: str, file_name: str) -> Dict[str, Any]:
        """模拟文档解析（用于测试）"""
        doc = self._documents[doc_id]
        
        # 模拟处理延迟
        await asyncio.sleep(2)
        
        # 生成模拟结果
        doc.status = "completed"
        doc.processed_at = datetime.utcnow()
        
        # 模拟页面和内容
        doc.pages = [
            {
                "page_number": 1,
                "width": 595,
                "height": 842,
                "blocks": [
                    {
                        "type": "title",
                        "content": f"Document: {file_name}",
                        "bbox": [50, 50, 545, 100],
                        "confidence": 0.98
                    },
                    {
                        "type": "paragraph",
                        "content": "这是一个模拟的文档解析结果。实际使用时需要配置阿里云IDP服务。",
                        "bbox": [50, 120, 545, 200],
                        "confidence": 0.95
                    },
                    {
                        "type": "table",
                        "content": {
                            "rows": 3,
                            "cols": 3,
                            "cells": [
                                ["Header 1", "Header 2", "Header 3"],
                                ["Data 1", "Data 2", "Data 3"],
                                ["Data 4", "Data 5", "Data 6"]
                            ]
                        },
                        "bbox": [50, 220, 545, 400],
                        "confidence": 0.92
                    }
                ]
            }
        ]
        
        doc.metadata = {
            "total_pages": 1,
            "file_type": self._get_file_type(file_name),
            "language": "zh-CN",
            "has_tables": True,
            "has_images": False,
            "has_formulas": False
        }
        
        return {
            "doc_id": doc_id,
            "status": "completed",
            "pages": doc.pages,
            "metadata": doc.metadata,
            "processed_at": doc.processed_at.isoformat()
        }
    
    async def _poll_job_status(self, doc_id: str, job_id: str):
        """轮询任务状态"""
        max_retries = 60  # 最多重试60次
        retry_interval = 5  # 每5秒重试一次
        
        for _ in range(max_retries):
            try:
                result = await self._get_job_result(job_id)
                if result["status"] == "completed":
                    doc = self._documents[doc_id]
                    doc.status = "completed"
                    doc.processed_at = datetime.utcnow()
                    doc.pages = result.get("pages", [])
                    doc.metadata = result.get("metadata", {})
                    return
                elif result["status"] == "failed":
                    doc = self._documents[doc_id]
                    doc.status = "failed"
                    doc.error_message = result.get("error", "解析失败")
                    return
            except Exception as e:
                log.error(f"Poll job status failed: {str(e)}")
            
            await asyncio.sleep(retry_interval)
        
        # 超时
        doc = self._documents[doc_id]
        doc.status = "timeout"
        doc.error_message = "解析超时"
    
    async def _wait_for_result(self, doc_id: str, job_id: str) -> Dict[str, Any]:
        """等待解析结果"""
        await self._poll_job_status(doc_id, job_id)
        doc = self._documents[doc_id]
        
        return {
            "doc_id": doc_id,
            "status": doc.status,
            "pages": doc.pages,
            "metadata": doc.metadata,
            "processed_at": doc.processed_at.isoformat() if doc.processed_at else None,
            "error_message": doc.error_message
        }
    
    async def _get_job_result(self, job_id: str) -> Dict[str, Any]:
        """获取任务结果"""
        # 这里应该调用阿里云API获取任务结果
        # 现在返回模拟结果
        return {
            "status": "completed",
            "pages": [],
            "metadata": {}
        }
    
    def _get_file_type(self, file_name: str) -> str:
        """根据文件名获取文件类型"""
        ext = file_name.rsplit('.', 1)[-1].lower() if '.' in file_name else ''
        
        file_type_map = {
            'pdf': 'pdf',
            'doc': 'word',
            'docx': 'word',
            'xls': 'excel',
            'xlsx': 'excel',
            'ppt': 'ppt',
            'pptx': 'ppt',
            'png': 'image',
            'jpg': 'image',
            'jpeg': 'image',
            'gif': 'image',
            'bmp': 'image',
            'txt': 'text',
            'md': 'markdown'
        }
        
        return file_type_map.get(ext, 'unknown')
    
    async def get_document_status(self, doc_id: str) -> Dict[str, Any]:
        """获取文档状态"""
        if doc_id not in self._documents:
            return {
                "doc_id": doc_id,
                "status": "not_found",
                "error_message": "文档不存在"
            }
        
        doc = self._documents[doc_id]
        return {
            "doc_id": doc_id,
            "status": doc.status,
            "created_at": doc.created_at.isoformat(),
            "processed_at": doc.processed_at.isoformat() if doc.processed_at else None,
            "error_message": doc.error_message
        }
    
    async def get_document_content(self, doc_id: str) -> Dict[str, Any]:
        """获取文档内容"""
        if doc_id not in self._documents:
            raise ValueError(f"Document {doc_id} not found")
        
        doc = self._documents[doc_id]
        if doc.status != "completed":
            raise ValueError(f"Document {doc_id} is not ready, status: {doc.status}")
        
        return {
            "doc_id": doc_id,
            "pages": doc.pages,
            "metadata": doc.metadata
        }
    
    def extract_text_from_document(self, doc_id: str) -> str:
        """从文档中提取纯文本"""
        if doc_id not in self._documents:
            raise ValueError(f"Document {doc_id} not found")
        
        doc = self._documents[doc_id]
        if doc.status != "completed":
            raise ValueError(f"Document {doc_id} is not ready")
        
        text_parts = []
        for page in doc.pages:
            for block in page.get("blocks", []):
                if block["type"] in ["title", "paragraph", "text"]:
                    text_parts.append(block["content"])
                elif block["type"] == "table":
                    # 将表格转换为文本
                    table_data = block["content"]
                    for row in table_data.get("cells", []):
                        text_parts.append(" | ".join(row))
        
        return "\n\n".join(text_parts)
    
    def extract_tables_from_document(self, doc_id: str) -> List[Dict[str, Any]]:
        """从文档中提取表格"""
        if doc_id not in self._documents:
            raise ValueError(f"Document {doc_id} not found")
        
        doc = self._documents[doc_id]
        if doc.status != "completed":
            raise ValueError(f"Document {doc_id} is not ready")
        
        tables = []
        for page_num, page in enumerate(doc.pages):
            for block in page.get("blocks", []):
                if block["type"] == "table":
                    tables.append({
                        "page": page_num + 1,
                        "data": block["content"],
                        "bbox": block.get("bbox"),
                        "confidence": block.get("confidence")
                    })
        
        return tables
    
    def convert_to_markdown(self, doc_id: str) -> str:
        """将文档转换为Markdown格式"""
        if doc_id not in self._documents:
            raise ValueError(f"Document {doc_id} not found")
        
        doc = self._documents[doc_id]
        if doc.status != "completed":
            raise ValueError(f"Document {doc_id} is not ready")
        
        markdown_parts = []
        
        for page_num, page in enumerate(doc.pages):
            if len(doc.pages) > 1:
                markdown_parts.append(f"\n---\n# Page {page_num + 1}\n")
            
            for block in page.get("blocks", []):
                if block["type"] == "title":
                    level = block.get("level", 1)
                    markdown_parts.append(f"{'#' * level} {block['content']}\n")
                elif block["type"] == "paragraph":
                    markdown_parts.append(f"{block['content']}\n")
                elif block["type"] == "text":
                    markdown_parts.append(f"{block['content']}\n")
                elif block["type"] == "table":
                    table_data = block["content"]
                    cells = table_data.get("cells", [])
                    if cells:
                        # 表头
                        markdown_parts.append("| " + " | ".join(cells[0]) + " |")
                        markdown_parts.append("|" + " --- |" * len(cells[0]))
                        # 数据行
                        for row in cells[1:]:
                            markdown_parts.append("| " + " | ".join(row) + " |")
                        markdown_parts.append("")
                elif block["type"] == "list":
                    items = block.get("items", [])
                    for item in items:
                        markdown_parts.append(f"- {item}")
                    markdown_parts.append("")
                elif block["type"] == "formula":
                    markdown_parts.append(f"$${block['content']}$$\n")
        
        return "\n".join(markdown_parts)


# 全局IDP服务实例
idp_service = IDPService()
