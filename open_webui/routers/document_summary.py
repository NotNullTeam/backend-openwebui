"""
文档摘要生成路由
使用LLM生成文档摘要
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import Dict, Optional
from pydantic import BaseModel
import logging
import asyncio

from open_webui.utils.auth import get_verified_user
from open_webui.models.knowledge import Knowledges
from open_webui.models.files import Files
from open_webui.retrieval.vector.factory import VECTOR_DB_CLIENT
from open_webui.config import TASK_MODEL, TASK_MODEL_EXTERNAL

log = logging.getLogger(__name__)
router = APIRouter()


class SummaryRequest(BaseModel):
    """摘要请求模型"""
    max_length: Optional[int] = 500
    style: Optional[str] = "concise"  # concise, detailed, technical, simple
    language: Optional[str] = "zh"  # zh, en
    include_keywords: Optional[bool] = True


class SummaryResponse(BaseModel):
    """摘要响应模型"""
    document_id: str
    title: str
    summary: str
    keywords: Optional[list] = []
    word_count: int
    generation_time: float


async def generate_summary_with_llm(
    content: str,
    title: str,
    max_length: int = 500,
    style: str = "concise",
    language: str = "zh"
) -> str:
    """使用LLM生成文档摘要"""
    
    # 构建提示词
    style_prompts = {
        "concise": "简洁明了，突出重点",
        "detailed": "详细全面，包含主要细节",
        "technical": "技术性强，保留专业术语",
        "simple": "通俗易懂，避免专业术语"
    }
    
    language_prompts = {
        "zh": "使用中文",
        "en": "Use English"
    }
    
    prompt = f"""
请为以下文档生成摘要：

文档标题：{title}

文档内容：
{content[:3000]}  # 限制输入长度

要求：
1. {language_prompts.get(language, '使用中文')}
2. 摘要风格：{style_prompts.get(style, '简洁明了')}
3. 字数限制：不超过{max_length}字
4. 包含文档的主要观点和关键信息
5. 保持逻辑清晰，结构完整

请直接输出摘要内容，不需要其他说明。
"""
    
    try:
        # TODO: 调用实际的LLM API
        # 这里需要集成实际的LLM服务
        # response = await llm_service.generate(prompt)
        
        # 临时返回模拟摘要
        summary = f"这是关于《{title}》的文档摘要。文档主要内容包括：{content[:200]}..."
        
        # 确保摘要长度符合要求
        if len(summary) > max_length:
            summary = summary[:max_length-3] + "..."
            
        return summary
        
    except Exception as e:
        log.error(f"LLM生成摘要失败: {str(e)}")
        # 降级到简单的文本截取
        return f"{content[:max_length-3]}..." if len(content) > max_length else content


async def extract_keywords(content: str, top_k: int = 10) -> list:
    """从文档中提取关键词"""
    try:
        # 使用jieba进行关键词提取
        import jieba.analyse
        
        # TF-IDF提取关键词
        keywords = jieba.analyse.extract_tags(
            content,
            topK=top_k,
            withWeight=False,
            allowPOS=('n', 'nr', 'ns', 'nt', 'nw', 'nz', 'v', 'vn')
        )
        
        return keywords
        
    except ImportError:
        # 如果jieba未安装，使用简单的词频统计
        import re
        from collections import Counter
        
        # 简单分词
        words = re.findall(r'\w+', content.lower())
        
        # 过滤停用词
        stop_words = {'的', '是', '在', '和', '了', '有', '我', '你', '他', 'the', 'is', 'at', 'and', 'of', 'a', 'to', 'in'}
        words = [w for w in words if w not in stop_words and len(w) > 1]
        
        # 统计词频
        word_freq = Counter(words)
        
        # 返回高频词
        return [word for word, freq in word_freq.most_common(top_k)]
    except Exception as e:
        log.error(f"关键词提取失败: {str(e)}")
        return []


@router.post("/knowledge/documents/{document_id}/summary")
async def generate_document_summary(
    document_id: str,
    request: SummaryRequest = SummaryRequest(),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    user=Depends(get_verified_user)
) -> SummaryResponse:
    """
    生成文档摘要
    
    使用LLM对文档内容生成智能摘要，支持多种风格和语言
    """
    import time
    start_time = time.time()
    
    try:
        # 获取文档信息
        knowledge = Knowledges.get_knowledge_by_id(document_id)
        if not knowledge:
            raise HTTPException(status_code=404, detail="文档不存在")
        
        # 检查权限
        if knowledge.user_id != user.id and user.role != "admin":
            raise HTTPException(status_code=403, detail="无权访问此文档")
        
        # 获取文档内容
        file_id = knowledge.file_ids[0] if knowledge.file_ids else None
        if not file_id:
            raise HTTPException(status_code=400, detail="文档没有关联文件")
        
        file_info = Files.get_file_by_id(file_id)
        if not file_info:
            raise HTTPException(status_code=404, detail="文件不存在")
        
        # 从向量数据库获取文档块
        try:
            collection = VECTOR_DB_CLIENT.get_collection(name=f"knowledge_{document_id}")
            results = collection.get()
            
            # 合并文档块内容
            content_parts = []
            if results and results.get("documents"):
                content_parts = results["documents"]
            
            full_content = "\n".join(content_parts)
            
        except Exception as e:
            log.warning(f"从向量数据库获取内容失败: {str(e)}")
            # 降级：尝试从文件直接读取
            full_content = knowledge.data.get("content", "")
        
        if not full_content:
            raise HTTPException(status_code=400, detail="文档内容为空")
        
        # 生成摘要
        summary = await generate_summary_with_llm(
            content=full_content,
            title=knowledge.name,
            max_length=request.max_length,
            style=request.style,
            language=request.language
        )
        
        # 提取关键词（如果需要）
        keywords = []
        if request.include_keywords:
            keywords = await extract_keywords(full_content, top_k=10)
        
        # 计算生成时间
        generation_time = time.time() - start_time
        
        # 保存摘要到知识库元数据（后台任务）
        async def save_summary():
            try:
                if not knowledge.meta:
                    knowledge.meta = {}
                knowledge.meta["summary"] = {
                    "text": summary,
                    "keywords": keywords,
                    "generated_at": time.time(),
                    "style": request.style,
                    "language": request.language
                }
                Knowledges.update_knowledge_by_id(
                    document_id,
                    {"meta": knowledge.meta}
                )
            except Exception as e:
                log.error(f"保存摘要失败: {str(e)}")
        
        background_tasks.add_task(save_summary)
        
        return SummaryResponse(
            document_id=document_id,
            title=knowledge.name,
            summary=summary,
            keywords=keywords,
            word_count=len(summary),
            generation_time=generation_time
        )
        
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"生成文档摘要失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"生成摘要失败: {str(e)}")


@router.get("/knowledge/documents/{document_id}/summary")
async def get_document_summary(
    document_id: str,
    regenerate: bool = False,
    user=Depends(get_verified_user)
) -> Dict:
    """
    获取文档摘要
    
    如果摘要已存在则直接返回，否则生成新摘要
    """
    try:
        # 获取文档信息
        knowledge = Knowledges.get_knowledge_by_id(document_id)
        if not knowledge:
            raise HTTPException(status_code=404, detail="文档不存在")
        
        # 检查权限
        if knowledge.user_id != user.id and user.role != "admin":
            raise HTTPException(status_code=403, detail="无权访问此文档")
        
        # 检查是否已有摘要
        if not regenerate and knowledge.meta and "summary" in knowledge.meta:
            summary_data = knowledge.meta["summary"]
            return {
                "document_id": document_id,
                "title": knowledge.name,
                "summary": summary_data.get("text", ""),
                "keywords": summary_data.get("keywords", []),
                "generated_at": summary_data.get("generated_at"),
                "cached": True
            }
        
        # 生成新摘要
        summary_request = SummaryRequest()
        response = await generate_document_summary(
            document_id=document_id,
            request=summary_request,
            user=user
        )
        
        return {
            "document_id": response.document_id,
            "title": response.title,
            "summary": response.summary,
            "keywords": response.keywords,
            "generated_at": None,
            "cached": False
        }
        
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"获取文档摘要失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取摘要失败: {str(e)}")


@router.post("/knowledge/batch-summary")
async def generate_batch_summaries(
    document_ids: list[str],
    request: SummaryRequest = SummaryRequest(),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    user=Depends(get_verified_user)
) -> Dict:
    """
    批量生成文档摘要
    
    异步批量处理多个文档的摘要生成
    """
    try:
        if len(document_ids) > 10:
            raise HTTPException(status_code=400, detail="批量处理最多支持10个文档")
        
        # 创建批量任务
        task_id = f"batch_summary_{user.id}_{int(time.time())}"
        
        async def process_batch():
            results = []
            for doc_id in document_ids:
                try:
                    response = await generate_document_summary(
                        document_id=doc_id,
                        request=request,
                        user=user
                    )
                    results.append({
                        "document_id": doc_id,
                        "status": "success",
                        "summary": response.summary
                    })
                except Exception as e:
                    results.append({
                        "document_id": doc_id,
                        "status": "failed",
                        "error": str(e)
                    })
            
            # TODO: 保存结果到缓存或数据库
            log.info(f"批量摘要任务 {task_id} 完成: {len(results)} 个文档")
        
        background_tasks.add_task(process_batch)
        
        return {
            "task_id": task_id,
            "document_count": len(document_ids),
            "status": "processing",
            "message": "批量摘要生成任务已启动"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"批量生成摘要失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"批量生成失败: {str(e)}")
