import logging
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from open_webui.env import SRC_LOG_LEVELS
from open_webui.utils.auth import get_verified_user
from open_webui.models.knowledge import Knowledges
from open_webui.retrieval.utils import get_embedding_function
from open_webui.routers.retrieval import get_ef
from open_webui.retrieval.vector.factory import VECTOR_DB_CLIENT
from open_webui.services.log_parsing_service import log_parsing_service
from open_webui.retrieval.vector.similarity_normalizer import (
    similarity_normalizer,
    get_db_type_from_config
)
from open_webui.config import (
    RAG_EMBEDDING_ENGINE,
    RAG_EMBEDDING_MODEL,
    RAG_EMBEDDING_BATCH_SIZE,
    RAG_OPENAI_API_BASE_URL,
    RAG_OPENAI_API_KEY,
    RAG_AZURE_OPENAI_BASE_URL,
    VECTOR_DB,
)

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])

router = APIRouter()


class LogParsingRequest(BaseModel):
    logType: str
    vendor: str
    logContent: str
    contextInfo: dict | None = None


class LogParsingResponse(BaseModel):
    parsed_data: dict | None = None
    analysis_result: dict | None = None
    severity: str | None = None
    recommendations: list[str] | None = None
    related_knowledge: list[dict] | None = None


@router.post("/log-parsing", response_model=LogParsingResponse)
async def parse_log(req: LogParsingRequest, request: Request, user=Depends(get_verified_user)):
    # 1) 基础校验
    if not req.logType:
        raise HTTPException(status_code=400, detail="logType is required")
    if not req.vendor:
        raise HTTPException(status_code=400, detail="vendor is required")
    if not req.logContent or not req.logContent.strip():
        raise HTTPException(status_code=400, detail="logContent is required")

    try:
        # 2) 使用完整的日志解析服务
        parsed = log_parsing_service.parse_log(
            log_type=req.logType,
            vendor=req.vendor,
            log_content=req.logContent,
            context_info=req.contextInfo
        )

        # 3) 生成相关知识（基于可访问的知识库做向量检索）
        try:
            related = _search_related_knowledge(
                query=_build_query_from_parsed(parsed, req),
                user_id=user.id,
                request=request,
            )
        except Exception as e:
            log.warning(f"related_knowledge search failed: {e}")
            related = []

        # 4) 确定整体严重性
        severity = "low"
        anomalies = parsed.get("anomalies", [])
        if any(a.get("severity") == "high" for a in anomalies):
            severity = "high"
        elif any(a.get("severity") == "medium" for a in anomalies):
            severity = "medium"

        # 5) 汇总结果
        return LogParsingResponse(
            parsed_data=parsed,
            analysis_result={
                "summary": parsed.get("summary"),
                "anomalies": anomalies,
                "keyEvents": parsed.get("keyEvents", []),
                "logMetrics": parsed.get("logMetrics", {})
            },
            severity=severity,
            recommendations=[r.get("action") for r in parsed.get("suggestedActions", [])],
            related_knowledge=related,
        )

    except Exception as e:
        log.error(f"Log parsing failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"日志解析失败: {str(e)}"
        )


# ============ 辅助函数 ============


def _build_query_from_parsed(parsed: Dict[str, Any], req: LogParsingRequest) -> str:
    base = parsed.get("summary", "")
    if not base:
        base = req.logContent[:500]
    # 拼接关键字以增强检索效果
    keywords = [a.get("type", "") for a in parsed.get("anomalies", [])]
    return (base + " " + " ".join(keywords)).strip()


def _search_related_knowledge(query: str, user_id: str, request: Request) -> List[Dict[str, Any]]:
    # 获取可访问的知识库
    if not query:
        return []
    kbs = Knowledges.get_knowledge_bases_by_user_id(user_id, "read")

    # 构建嵌入函数
    ef = get_ef(
        engine=RAG_EMBEDDING_ENGINE.value,
        embedding_model=RAG_EMBEDDING_MODEL.value,
        auto_update=False,
    )
    embedding_function = get_embedding_function(
        embedding_engine=RAG_EMBEDDING_ENGINE.value,
        embedding_model=RAG_EMBEDDING_MODEL.value,
        embedding_function=ef,
        url=(RAG_AZURE_OPENAI_BASE_URL.value or RAG_OPENAI_API_BASE_URL.value),
        key=RAG_OPENAI_API_KEY.value,
        embedding_batch_size=RAG_EMBEDDING_BATCH_SIZE.value,
        azure_api_version=None,
    )

    qvec = embedding_function(query, prefix=None)

    # 针对每个知识库检索Top-3，合并排序取Top-5
    agg: List[Dict[str, Any]] = []
    for kb in kbs:
        try:
            res = VECTOR_DB_CLIENT.search(collection_name=kb.id, vectors=[qvec], limit=3)
            if not res or not res.ids:
                continue
            for i, _id in enumerate(res.ids[0]):
                agg.append(
                    {
                        "knowledge_id": kb.id,
                        "distance": float(res.distances[0][i]) if res.distances else None,
                        "content": res.documents[0][i] if res.documents else "",
                        "metadata": res.metadatas[0][i] if res.metadatas else {},
                    }
                )
        except Exception as e:
            log.debug(f"kb search failed for {kb.id}: {e}")
            continue

    # 使用统一的相似度归一化
    if agg:
        db_type = get_db_type_from_config(str(VECTOR_DB))
        agg_normalized = similarity_normalizer.normalize_search_results(
            agg, db_type, score_key="distance"
        )
        
        # 应用质量阈值过滤
        threshold = similarity_normalizer.get_similarity_threshold(db_type, "medium")
        agg_filtered = similarity_normalizer.filter_by_threshold(
            agg_normalized, threshold, score_key="score"
        )
        
        # 取Top-5
        agg_sorted = agg_filtered[:5]
        
        # 清理输出结构
        for item in agg_sorted:
            if "distance" in item:
                del item["distance"]
            if "raw_distance" in item:
                del item["raw_distance"]
        
        return agg_sorted
    
    return []
