import logging
import json
import time
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

from open_webui.env import SRC_LOG_LEVELS
from open_webui.utils.auth import get_verified_user
from open_webui.models.cases import (
    CasesTable,
    CaseCreateForm,
    CaseListResponse,
    CaseModel,
    CaseWithGraphModel,
)
from open_webui.models.feedbacks import Feedbacks, FeedbackForm
from open_webui.models.knowledge import Knowledges
from open_webui.retrieval.utils import get_embedding_function
from open_webui.routers.retrieval import get_ef
from open_webui.retrieval.vector.factory import VECTOR_DB_CLIENT
from open_webui.services.vendor_command_service import vendor_command_service
from open_webui.services.ai.regenerate_service import (
    build_regeneration_messages,
    regenerate_with_model,
)
from open_webui.tasks import create_task, list_task_ids_by_item_id, stop_item_tasks
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


cases_table = CasesTable()


@router.get("/", response_model=CaseListResponse)
async def list_cases(
    page: int = 1,
    page_size: int = 10,
    status: Optional[str] = None,
    vendor: Optional[str] = None,
    category: Optional[str] = None,
    user=Depends(get_verified_user),
):
    return cases_table.list_cases_by_user(
        user_id=user.id,
        page=page,
        page_size=page_size,
        status=status,
        vendor=vendor,
        category=category,
    )


@router.post("/")
async def create_case(body: CaseCreateForm, user=Depends(get_verified_user)):
    """
    创建新案例并初始化图谱：
    - 创建 USER_QUERY 节点（包含原始问题与附件）
    - 创建 AI_ANALYSIS 处理节点（初始为 PROCESSING）
    - 创建两者之间的边

    返回结构对齐 backend：case 基本信息 + 初始化的 nodes/edges
    """
    if not body.query or not body.query.strip():
        raise HTTPException(status_code=400, detail="query is required")

    # 先创建案例
    case = cases_table.insert_new_case(user_id=user.id, form=body)

    # 再创建初始化节点与边
    from open_webui.internal.db import get_db
    from open_webui.models.cases import CaseNode, CaseEdge, Case
    now = int(time.time())

    # 验证 title 长度
    if body.title and len(body.title) > 200:
        raise HTTPException(status_code=400, detail="title too long (<=200)")

    user_node_id = None
    ai_node_id = None
    edge_id = None
    with get_db() as db:
        # 更新 title 和 category（如有）
        if body.title or body.category:
            row = db.query(Case).filter_by(id=case.id).first()
            if row:
                if body.title:
                    row.title = body.title
                if body.category:
                    row.category = body.category
                row.updated_at = now
                db.commit()

        # USER_QUERY 节点
        user_node = CaseNode(
            id=str(uuid4()),
            case_id=case.id,
            title="用户问题",
            content=json_dumps_safe({
                "text": body.query,
                "attachments": getattr(body, "attachments", []) or [],
            }),
            node_type="USER_QUERY",
            status="COMPLETED",
            metadata_={"timestamp": now},
            created_at=now,
        )
        db.add(user_node)
        db.flush()
        user_node_id = user_node.id

        # AI_ANALYSIS 节点
        ai_node = CaseNode(
            id=str(uuid4()),
            case_id=case.id,
            title="AI分析中...",
            content="",
            node_type="AI_ANALYSIS",
            status="PROCESSING",
            metadata_={"timestamp": now},
            created_at=now,
        )
        db.add(ai_node)
        db.flush()
        ai_node_id = ai_node.id

        # 边：USER_QUERY -> AI_ANALYSIS
        e = CaseEdge(
            id=str(uuid4()),
            case_id=case.id,
            source_node_id=user_node_id,
            target_node_id=ai_node_id,
            edge_type="INITIAL",
            metadata_={},
        )
        db.add(e)
        db.flush()
        edge_id = e.id

        db.commit()

    # 查询刚创建的节点，按 created_at 升序返回
    from open_webui.models.cases import CaseNode as CN
    with get_db() as db:
        recents = (
            db.query(CN)
            .filter(CN.case_id == case.id)
            .order_by(CN.created_at.asc())
            .all()
        )
        nodes_out = [
            {
                "id": n.id,
                "case_id": n.case_id,
                "title": n.title,
                "content": n.content,
                "node_type": n.node_type,
                "status": n.status,
                "metadata": n.metadata_ or {},
                "created_at": n.created_at,
            }
            for n in recents
        ]

    return {
        "caseId": case.id,
        "title": body.title or case.title,
        "status": case.status,
        "vendor": case.vendor,
        "nodes": nodes_out,
        "edges": [
            {
                "id": edge_id,
                "case_id": case.id,
                "source_node_id": user_node_id,
                "target_node_id": ai_node_id,
                "edge_type": "INITIAL",
                "metadata": {},
            }
        ],
        "createdAt": now,
        "updatedAt": now,
    }


@router.get("/{case_id}", response_model=CaseWithGraphModel)
async def get_case(case_id: str, user=Depends(get_verified_user)):
    c = cases_table.get_case_with_graph_by_id(case_id)
    if not c or c.user_id != user.id:
        raise HTTPException(status_code=404, detail="case not found")
    return c


@router.delete("/{case_id}")
async def delete_case(case_id: str, user=Depends(get_verified_user)):
    c = cases_table.get_case_by_id(case_id)
    if not c or c.user_id != user.id:
        raise HTTPException(status_code=404, detail="case not found")
    ok = cases_table.delete_case(case_id)
    if not ok:
        raise HTTPException(status_code=500, detail="delete failed")
    return {"ok": True}


class CaseUpdateForm(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None
    vendor: Optional[str] = None
    category: Optional[str] = None


@router.put("/{case_id}", response_model=CaseModel)
async def update_case(case_id: str, body: CaseUpdateForm, user=Depends(get_verified_user)):
    c = cases_table.get_case_with_graph_by_id(case_id)
    if not c or c.user_id != user.id:
        raise HTTPException(status_code=404, detail="case not found")
    updated = cases_table.update_case(case_id, body.model_dump())
    if not updated:
        raise HTTPException(status_code=500, detail="update failed")
    return updated


class NodeCreateForm(BaseModel):
    title: str
    content: str
    node_type: str
    status: Optional[str] = None
    metadata: Optional[dict] = None


@router.post("/{case_id}/nodes")
async def create_node(case_id: str, body: NodeCreateForm, user=Depends(get_verified_user)):
    c = cases_table.get_case_with_graph_by_id(case_id)
    if not c or c.user_id != user.id:
        raise HTTPException(status_code=404, detail="case not found")
    n = cases_table.create_node(
        case_id=case_id,
        title=body.title,
        content=body.content,
        node_type=body.node_type,
        status=body.status,
        metadata=body.metadata,
    )
    return {"node": n}


class EdgeCreateForm(BaseModel):
    source_node_id: str
    target_node_id: str
    edge_type: str
    metadata: Optional[dict] = None


@router.post("/{case_id}/edges")
async def create_edge(case_id: str, body: EdgeCreateForm, user=Depends(get_verified_user)):
    c = cases_table.get_case_with_graph_by_id(case_id)
    if not c or c.user_id != user.id:
        raise HTTPException(status_code=404, detail="case not found")
    e = cases_table.create_edge(
        case_id=case_id,
        source_node_id=body.source_node_id,
        target_node_id=body.target_node_id,
        edge_type=body.edge_type,
        metadata=body.metadata,
    )
    return {"edge": e}


@router.delete("/nodes/{node_id}")
async def delete_node(node_id: str, user=Depends(get_verified_user)):
    # Note: 权限校验简化为只要节点隶属当前用户的 case 即可
    # 先拿到节点所属 case
    c = None
    from open_webui.internal.db import get_db
    from open_webui.models.cases import CaseNode, Case

    with get_db() as db:
        n = db.query(CaseNode).filter_by(id=node_id).first()
        if n:
            c = db.query(Case).filter_by(id=n.case_id).first()
    if not c or c.user_id != user.id:
        raise HTTPException(status_code=404, detail="node not found")

    ok = cases_table.delete_node(node_id)
    if not ok:
        raise HTTPException(status_code=500, detail="delete failed")
    return {"ok": True}


@router.delete("/edges/{edge_id}")
async def delete_edge(edge_id: str, user=Depends(get_verified_user)):
    # 权限校验同上
    c = None
    from open_webui.internal.db import get_db
    from open_webui.models.cases import CaseEdge, Case

    with get_db() as db:
        e = db.query(CaseEdge).filter_by(id=edge_id).first()
        if e:
            c = db.query(Case).filter_by(id=e.case_id).first()
    if not c or c.user_id != user.id:
        raise HTTPException(status_code=404, detail="edge not found")

    ok = cases_table.delete_edge(edge_id)
    if not ok:
        raise HTTPException(status_code=500, detail="delete failed")
    return {"ok": True}


class RateNodeForm(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = None


@router.post("/{case_id}/nodes/{node_id}/rate")
async def rate_node(case_id: str, node_id: str, body: RateNodeForm, user=Depends(get_verified_user)):
    # Ensure case belongs to user and node under case
    c = cases_table.get_case_with_graph_by_id(case_id)
    if not c or c.user_id != user.id:
        raise HTTPException(status_code=404, detail="case not found")
    if not any(n.id == node_id for n in c.nodes):
        raise HTTPException(status_code=404, detail="node not found")
    updated = cases_table.update_node_metadata(
        node_id,
        {
            "rating": {
                "value": body.rating,
                "comment": body.comment or "",
            }
        },
    )
    if not updated:
        raise HTTPException(status_code=500, detail="rate failed")
    return {"rating": updated.metadata.get("rating") if hasattr(updated, "metadata") else None}


class NodeUpdateForm(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None  # COMPLETED | AWAITING_USER_INPUT | PROCESSING
    content: Optional[Any] = None
    metadata: Optional[dict] = None


@router.put("/{case_id}/nodes/{node_id}")
async def update_node(case_id: str, node_id: str, body: NodeUpdateForm, user=Depends(get_verified_user)):
    c = cases_table.get_case_with_graph_by_id(case_id)
    if not c or c.user_id != user.id:
        raise HTTPException(status_code=404, detail="case not found")
    node = next((n for n in c.nodes if n.id == node_id), None)
    if not node:
        raise HTTPException(status_code=404, detail="node not found")

    from open_webui.internal.db import get_db
    from open_webui.models.cases import CaseNode, Case as CaseRow
    now = int(time.time())
    with get_db() as db:
        n = db.query(CaseNode).filter_by(id=node_id, case_id=case_id).first()
        if not n:
            raise HTTPException(status_code=404, detail="node not found")
        if body.title is not None:
            n.title = body.title
        if body.status is not None:
            if body.status not in ["COMPLETED", "AWAITING_USER_INPUT", "PROCESSING"]:
                raise HTTPException(status_code=400, detail="invalid node status")
            n.status = body.status
        if body.content is not None:
            # 允许任意结构，统一存为字符串或JSON字符串
            n.content = json_dumps_safe(body.content)
        if body.metadata is not None:
            cur = n.metadata_ or {}
            cur.update(body.metadata)
            n.metadata_ = cur
        # 更新案例 updated_at
        db.query(CaseRow).filter_by(id=case_id).update({"updated_at": now})
        db.commit()
        db.refresh(n)
        return {
            "id": n.id,
            "case_id": n.case_id,
            "title": n.title,
            "content": n.content,
            "node_type": n.node_type,
            "status": n.status,
            "metadata": n.metadata_ or {},
            "created_at": n.created_at,
        }


class InteractionForm(BaseModel):
    parent_node_id: str
    response_data: Dict[str, Any]
    retrieval_weight: Optional[float] = 0.7
    filter_tags: Optional[List[str]] = None


@router.post("/{case_id}/interactions")
async def create_interaction(case_id: str, body: InteractionForm, user=Depends(get_verified_user)):
    c = cases_table.get_case_with_graph_by_id(case_id)
    if not c or c.user_id != user.id:
        raise HTTPException(status_code=404, detail="case not found")

    # create USER_RESPONSE node
    user_node = cases_table.create_node(
        case_id=case_id,
        title="用户补充信息",
        content=json_dumps_safe(body.response_data),
        node_type="USER_RESPONSE",
        status="COMPLETED",
        metadata={
            "retrieval_weight": body.retrieval_weight,
            "filter_tags": body.filter_tags,
        },
    )

    # create AI_ANALYSIS processing node
    ai_node = cases_table.create_node(
        case_id=case_id,
        title="AI分析中...",
        content="",
        node_type="AI_ANALYSIS",
        status="PROCESSING",
        metadata={"parent_response_id": user_node.id},
    )

    # link: parent -> user_response -> ai_processing
    cases_table.create_edge(
        case_id=case_id,
        source_node_id=body.parent_node_id,
        target_node_id=user_node.id,
        edge_type="FOLLOW_UP",
    )
    cases_table.create_edge(
        case_id=case_id,
        source_node_id=user_node.id,
        target_node_id=ai_node.id,
        edge_type="PROCESS",
    )

    return {
        "newNodes": [user_node.model_dump(), ai_node.model_dump()],
        "newEdges": [],
        "processingNodeId": ai_node.id,
    }


class CaseFeedbackForm(BaseModel):
    outcome: str  # solved | unsolved | partially_solved
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    comment: Optional[str] = None
    corrected_solution: Optional[str] = None
    knowledge_contribution: Optional[dict] = None
    additional_context: Optional[dict] = None


@router.put("/{case_id}/feedback")
async def upsert_case_feedback(case_id: str, body: CaseFeedbackForm, user=Depends(get_verified_user)):
    c = cases_table.get_case_by_id(case_id)
    if not c or c.user_id != user.id:
        raise HTTPException(status_code=404, detail="case not found")

    # Store in generic Feedbacks with type 'case-feedback' and meta.case_id
    # Check if an existing feedback exists for this case by current user
    from open_webui.internal.db import get_db
    from open_webui.models.feedbacks import Feedback as FeedbackRow
    existing = None
    with get_db() as db:
        rows = (
            db.query(FeedbackRow)
            .filter(FeedbackRow.user_id == user.id)
            .filter(FeedbackRow.type == "case-feedback")
            .all()
        )
        for r in rows:
            try:
                if (r.meta or {}).get("case_id") == case_id:
                    existing = r
                    break
            except Exception:
                continue

    form = FeedbackForm(
        type="case-feedback",
        data={
            "outcome": body.outcome,
            "rating": body.rating,
            "comment": body.comment,
            "corrected_solution": body.corrected_solution,
            "knowledge_contribution": body.knowledge_contribution,
            "additional_context": body.additional_context,
        },
        meta={"case_id": case_id},
    )

    if existing:
        updated = Feedbacks.update_feedback_by_id_and_user_id(existing.id, user.id, form)
        if not updated:
            raise HTTPException(status_code=500, detail="update feedback failed")
        return updated
    else:
        created = Feedbacks.insert_new_feedback(user.id, form)
        if not created:
            raise HTTPException(status_code=500, detail="create feedback failed")
        return created


@router.get("/{case_id}/feedback")
async def get_case_feedback(case_id: str, user=Depends(get_verified_user)):
    c = cases_table.get_case_by_id(case_id)
    if not c or c.user_id != user.id:
        raise HTTPException(status_code=404, detail="case not found")
    from open_webui.internal.db import get_db
    from open_webui.models.feedbacks import Feedback as FeedbackRow
    with get_db() as db:
        rows = (
            db.query(FeedbackRow)
            .filter(FeedbackRow.user_id == user.id)
            .filter(FeedbackRow.type == "case-feedback")
            .all()
        )
        for r in rows:
            meta = r.meta or {}
            if meta.get("case_id") == case_id:
                return Feedbacks.get_feedback_by_id(r.id)
        raise HTTPException(status_code=404, detail="feedback not found")


@router.get("/{case_id}/status")
async def get_case_status(case_id: str, user=Depends(get_verified_user)):
    """返回案例状态与处理中的节点，用于前端轮询。"""
    c = cases_table.get_case_with_graph_by_id(case_id)
    if not c or c.user_id != user.id:
        raise HTTPException(status_code=404, detail="case not found")
    processing = [n.model_dump() for n in c.nodes if n.status == "PROCESSING"]
    awaiting = [n.model_dump() for n in c.nodes if n.status == "AWAITING_USER_INPUT"]
    return {
        "caseId": c.id,
        "status": c.status,
        "processingNodes": processing,
        "awaitingUserInputNodes": awaiting,
        "updatedAt": c.updated_at,
    }


# ---------- helpers ----------
def json_dumps_safe(data: Any) -> str:
    try:
        return json.dumps(data, ensure_ascii=False)
    except Exception:
        return str(data)


# --- 节点/边列表 + 节点详情 ---


@router.get("/{case_id}/nodes")
async def list_case_nodes(case_id: str, user=Depends(get_verified_user)):
    c = cases_table.get_case_with_graph_by_id(case_id)
    if not c or c.user_id != user.id:
        raise HTTPException(status_code=404, detail="case not found")
    # 排序按 created_at 升序
    nodes = sorted(c.nodes, key=lambda n: n.created_at or 0)
    return {"nodes": [n.model_dump() for n in nodes]}


@router.get("/{case_id}/edges")
async def list_case_edges(case_id: str, user=Depends(get_verified_user)):
    c = cases_table.get_case_with_graph_by_id(case_id)
    if not c or c.user_id != user.id:
        raise HTTPException(status_code=404, detail="case not found")
    return {"edges": [e.model_dump() for e in c.edges]}


@router.get("/{case_id}/nodes/{node_id}")
async def get_node_detail(case_id: str, node_id: str, user=Depends(get_verified_user)):
    c = cases_table.get_case_with_graph_by_id(case_id)
    if not c or c.user_id != user.id:
        raise HTTPException(status_code=404, detail="case not found")
    node = next((n for n in c.nodes if n.id == node_id), None)
    if not node:
        raise HTTPException(status_code=404, detail="node not found")
    return node


# --- 节点知识溯源 ---


@router.get("/{case_id}/nodes/{node_id}/knowledge")
async def get_node_knowledge(
    request: Request,
    case_id: str,
    node_id: str,
    topK: int = 5,
    vendor: Optional[str] = None,
    retrievalWeight: float = 0.7,
    user=Depends(get_verified_user),
):
    if topK < 1 or topK > 20:
        raise HTTPException(status_code=400, detail="topK must be between 1 and 20")
    if retrievalWeight < 0 or retrievalWeight > 1:
        raise HTTPException(status_code=400, detail="retrievalWeight must be in [0,1]")

    c = cases_table.get_case_with_graph_by_id(case_id)
    if not c or c.user_id != user.id:
        raise HTTPException(status_code=404, detail="case not found")
    node = next((n for n in c.nodes if n.id == node_id), None)
    if not node:
        raise HTTPException(status_code=404, detail="node not found")

    # 构建查询文本
    query_text = None
    raw = node.content or ""
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            query_text = obj.get("text") or obj.get("analysis") or obj.get("answer")
    except Exception:
        pass
    if not query_text:
        query_text = raw or node.title
    if not query_text or not str(query_text).strip():
        return {
            "nodeId": node_id,
            "sources": [],
            "retrievalMetadata": {
                "totalCandidates": 0,
                "retrievalTime": 0,
                "rerankTime": 0,
                "strategy": "empty_query",
            },
        }

    # 检索可访问的知识库
    kbs = Knowledges.get_knowledge_bases_by_user_id(user.id, "read")

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

    start = time.time()
    qvec = embedding_function(query_text, prefix=None)
    agg: List[Dict[str, Any]] = []
    for kb in kbs:
        try:
            res = VECTOR_DB_CLIENT.search(collection_name=kb.id, vectors=[qvec], limit=topK)
            if not res or not res.ids:
                continue
            for i, _id in enumerate(res.ids[0]):
                item = {
                    "knowledge_id": kb.id,
                    "distance": float(res.distances[0][i]) if res.distances else None,
                    "content": res.documents[0][i] if res.documents else "",
                    "metadata": res.metadatas[0][i] if res.metadatas else {},
                }
                agg.append(item)
        except Exception as e:
            log.debug(f"knowledge search failed for {kb.id}: {e}")
            continue

    # 归一化评分并可选按 vendor 过滤
    for it in agg:
        d = it.get("distance")
        if d is None:
            it["score"] = 0.0
        else:
            if str(VECTOR_DB).lower() == "weaviate":
                it["score"] = 1.0 / (1.0 + float(d))
            else:
                it["score"] = float(d)
    if vendor:
        agg = [x for x in agg if isinstance(x.get("metadata"), dict) and (x["metadata"].get("vendor") == vendor)]

    agg_sorted = sorted(agg, key=lambda x: x.get("score", 0), reverse=True)[:topK]
    for it in agg_sorted:
        it.pop("distance", None)

    elapsed_ms = int((time.time() - start) * 1000)
    return {
        "nodeId": node_id,
        "sources": agg_sorted,
        "retrievalMetadata": {
            "totalCandidates": len(agg_sorted),
            "retrievalTime": elapsed_ms,
            "rerankTime": 0,
            "strategy": "vector_search",
        },
    }


@router.get("/{case_id}/nodes/{node_id}/commands")
async def get_node_commands(case_id: str, node_id: str, vendor: Optional[str] = None, user=Depends(get_verified_user)):
    """
    厂商命令建议：
    - 校验案例与节点归属
    - 分析节点文本（content/title）推断问题类型
    - 根据厂商模板返回命令清单，支持 context 占位替换
    """
    c = cases_table.get_case_with_graph_by_id(case_id)
    if not c or c.user_id != user.id:
        raise HTTPException(status_code=404, detail="case not found")
    node = next((n for n in c.nodes if n.id == node_id), None)
    if not node:
        raise HTTPException(status_code=404, detail="node not found")

    use_vendor = vendor or c.vendor
    if not use_vendor:
        return {"vendor": None, "commands": [], "supportedVendors": vendor_command_service.get_supported_vendors()}

    # 解析 content
    text = ""
    raw = node.content or ""
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            text = str(obj.get("text") or obj.get("analysis") or obj.get("answer") or "")
        else:
            text = str(obj)
    except Exception:
        text = str(raw)

    ctx = node.metadata or {}
    cmds = vendor_command_service.generate_commands(text, node.title or "", use_vendor, ctx)
    return {"vendor": use_vendor, "commands": cmds}


class RegenerateForm(BaseModel):
    prompt: Optional[str] = None
    regeneration_strategy: Optional[str] = Field(
        default=None,
        description="重生成策略: detailed, concise, technical, step-by-step, summary"
    )
    model: Optional[str] = None  # 可选模型ID提示，默认使用任务模型选择逻辑
    async_mode: Optional[bool] = True
    max_retries: Optional[int] = Field(default=3, ge=1, le=5)
    temperature: Optional[float] = Field(default=0.7, ge=0, le=2)


@router.post("/{case_id}/nodes/{node_id}/regenerate")
async def regenerate_node(case_id: str, node_id: str, body: RegenerateForm, request: Request, user=Depends(get_verified_user)):
    """
    重新生成节点内容：
    - 复用 Open WebUI 通用模型接口 `generate_chat_completion`
    - 完整的重试机制和异常处理
    - 异步任务处理
    - 数据库状态同步和回滚机制
    - 详细的错误分类和日志记录
    """
    import traceback
    from open_webui.internal.db import get_db
    from open_webui.models.cases import CaseNode
    
    # 验证重生成策略
    valid_strategies = ["detailed", "concise", "technical", "step-by-step", "summary"]
    if body.regeneration_strategy and body.regeneration_strategy not in valid_strategies:
        raise HTTPException(status_code=400, detail=f"Invalid regeneration strategy. Valid options: {valid_strategies}")
    
    # 验证上下文参数
    if body.context and not isinstance(body.context, dict):
        raise HTTPException(status_code=400, detail="Context must be a dictionary")
    
    now = int(time.time())
    
    # 内部任务逻辑
    async def _regenerate_task():
        from open_webui.internal.db import get_db as _get_db
        from open_webui.models.cases import CaseNode as _CN
        import asyncio
        
        db2 = next(_get_db())
        original_status = None
        original_metadata = None
        
        try:
            n2 = db2.query(_CN).filter(_CN.id == node_id).first()
            if not n2:
                error_msg = f"Node {node_id} not found during regeneration task"
                log.error(error_msg)
                raise ValueError(error_msg)
            
            # 保存原始状态用于回滚
            original_status = n2.status
            original_metadata = n2.metadata_.copy() if n2.metadata_ else {}
            
            case = Cases.get_case_by_id_and_user_id(case_id, user.id)
            if not case:
                error_msg = f"Case {case_id} not found for user {user.id}"
                log.error(error_msg)
                n2.status = "FAILED"
                n2.metadata_ = {
                    **(n2.metadata_ or {}),
                    "error": "Case not found",
                    "error_time": int(time.time())
                }
                db2.commit()
                raise PermissionError(error_msg)
            
            # 准备消息
            try:
                messages = build_regeneration_messages(
                    case_content=case["content"],
                    node_content=n2.content,
                    regeneration_strategy=body.regeneration_strategy,
                    user_prompt=body.prompt,
                    context=body.context,
                )
            except Exception as e:
                error_msg = f"Failed to build regeneration messages: {str(e)}"
                log.error(error_msg)
                n2.status = "FAILED"
                n2.metadata_ = {
                    **(n2.metadata_ or {}),
                    "error": "Message preparation failed",
                    "error_details": str(e),
                    "error_time": int(time.time())
                }
                db2.commit()
                raise ValueError(error_msg)
            
            original_content = n2.content
            
            # 带重试的生成逻辑
            last_error = None
            error_types = []
            
            for attempt in range(body.max_retries):
                try:
                    log.info(f"Starting regeneration attempt {attempt+1}/{body.max_retries} for node {node_id}")
                    
                    content = await regenerate_with_model(
                        request,
                        user,
                        messages,
                        model_hint=body.model,
                        metadata={
                            "task": "case_node_regenerate",
                            "case_id": case_id,
                            "node_id": node_id,
                            "attempt": attempt + 1,
                            "max_retries": body.max_retries,
                        },
                        temperature=body.temperature
                    )
                    
                    # 验证生成的内容
                    if not content or len(content.strip()) < 10:
                        raise ValueError("Generated content is too short or empty")
                    
                    n2.content = content
                    log.info(f"Successfully generated content for node {node_id} on attempt {attempt+1}")
                    break
                    
                except asyncio.TimeoutError as e:
                    last_error = e
                    error_types.append("timeout")
                    log.warning(f"Regeneration attempt {attempt+1} timed out for node {node_id}")
                    if attempt < body.max_retries - 1:
                        await asyncio.sleep(min(2 ** attempt, 30))  # 指数退避，最多30秒
                    
                except HTTPException as e:
                    last_error = e
                    error_types.append("http")
                    log.warning(f"HTTP error on attempt {attempt+1} for node {node_id}: {e.status_code} - {e.detail}")
                    
                    # 如果是认证或权限错误，不重试
                    if e.status_code in [401, 403]:
                        raise e
                    
                    if attempt < body.max_retries - 1:
                        await asyncio.sleep(min(2 ** attempt, 30))
                    
                except ValueError as e:
                    last_error = e
                    error_types.append("validation")
                    log.warning(f"Validation error on attempt {attempt+1} for node {node_id}: {str(e)}")
                    
                    # 对于验证错误，尝试调整参数后重试
                    if attempt < body.max_retries - 1:
                        body.temperature = min(body.temperature * 0.9, 0.1)  # 降低温度
                        await asyncio.sleep(2)
                    
                except Exception as e:
                    last_error = e
                    error_types.append("unknown")
                    log.error(f"Unexpected error on attempt {attempt+1} for node {node_id}: {str(e)}\n{traceback.format_exc()}")
                    
                    if attempt < body.max_retries - 1:
                        await asyncio.sleep(min(2 ** attempt, 30))
            
            # 如果所有重试都失败
            if last_error:
                raise last_error
            
        except Exception as e:
            error_msg = f"Regeneration task failed for node {node_id}: {str(e)}"
            log.error(f"{error_msg}\n{traceback.format_exc()}")
            
            # 尝试回滚到原始状态
            try:
                if n2:
                    n2.status = "FAILED"
                    n2.metadata_ = {
                        **(n2.metadata_ or {}),
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "error_types_encountered": error_types if error_types else [],
                        "error_time": int(time.time()),
                        "original_status": original_status,
                        "attempted_retries": body.max_retries,
                        "regeneration_strategy": body.regeneration_strategy,
                    }
                    n2.updated_at = int(time.time())
                    db2.commit()
                    log.info(f"Updated node {node_id} status to FAILED with error details")
            except Exception as rollback_error:
                log.error(f"Failed to update node status after error: {str(rollback_error)}")
            
            raise
            
        else:
            # 成功完成，更新状态
            try:
                n2.status = "COMPLETED"
                n2.metadata_ = {
                    **(n2.metadata_ or {}), 
                    "regenerated": True, 
                    "regenerated_at": int(time.time()),
                    "regeneration_strategy": body.regeneration_strategy,
                    "original_content": original_content,
                    "user_prompt": body.prompt,
                    "model_used": body.model,
                    "temperature": body.temperature,
                    "retries_needed": len(error_types) if error_types else 0,
                }
                n2.updated_at = int(time.time())
                db2.commit()
                log.info(f"Successfully regenerated node {node_id} with {len(error_types) if error_types else 0} retries")
            except Exception as commit_error:
                log.error(f"Failed to commit successful regeneration: {str(commit_error)}")
                raise
        
        finally:
            # 确保数据库连接关闭
            try:
                db2.close()
            except:
                pass
    
    # 提交任务前验证节点并标记为 PROCESSING
    db = next(get_db())
    try:
        n = db.query(CaseNode).filter(CaseNode.id == node_id).first()
        if not n:
            raise HTTPException(status_code=404, detail="Node not found")
        
        # 检查节点是否已在处理中
        if n.status == "PROCESSING":
            # 检查是否是卡住的任务（超过5分钟）
            if n.metadata_ and "processing_started_at" in n.metadata_:
                processing_time = int(time.time()) - n.metadata_["processing_started_at"]
                if processing_time > 300:  # 5分钟
                    log.warning(f"Node {node_id} stuck in PROCESSING for {processing_time}s, allowing new regeneration")
                else:
                    raise HTTPException(
                        status_code=409, 
                        detail=f"Node is already being regenerated (started {processing_time}s ago)"
                    )
        
        # 记录开始处理
        n.status = "PROCESSING"
        n.metadata_ = {
            **(n.metadata_ or {}),
            "processing_started_at": now,
            "processing_user_id": user.id,
            "processing_request_id": request.headers.get("X-Request-Id", "unknown"),
        }
        n.updated_at = now
        db.commit()
        log.info(f"Node {node_id} marked as PROCESSING for regeneration by user {user.id}")
    except Exception as e:
        log.error(f"Failed to mark node {node_id} as PROCESSING: {str(e)}")
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=f"Failed to start regeneration: {str(e)}")
    finally:
        db.close()
    
    # 根据async_mode执行任务
    if body.async_mode is not False:
        # 创建后台任务并返回任务ID
        try:
            task_id, _ = await create_task(request.app.state.redis, _regenerate_task(), id=node_id)
            log.info(f"Created async regeneration task {task_id} for node {node_id}")
            return {
                "taskId": task_id, 
                "nodeId": node_id, 
                "status": "submitted",
                "message": "Regeneration task submitted successfully"
            }
        except Exception as e:
            # 如果任务创建失败，恢复节点状态
            log.error(f"Failed to create regeneration task for node {node_id}: {str(e)}")
            db = next(get_db())
            try:
                n = db.query(CaseNode).filter(CaseNode.id == node_id).first()
                if n:
                    n.status = "DRAFT"
                    n.metadata_ = {
                        **(n.metadata_ or {}),
                        "task_creation_failed": True,
                        "task_error": str(e),
                        "task_error_time": int(time.time())
                    }
                    db.commit()
            finally:
                db.close()
            raise HTTPException(status_code=500, detail=f"Failed to create regeneration task: {str(e)}")
    else:
        # 同步执行（不推荐，仅用于测试）
        try:
            log.warning(f"Running synchronous regeneration for node {node_id} (not recommended for production)")
            await _regenerate_task()
            return {
                "taskId": None, 
                "nodeId": node_id, 
                "status": "completed",
                "message": "Regeneration completed synchronously"
            }
        except Exception as e:
            log.error(f"Synchronous regeneration failed for node {node_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Regeneration failed: {str(e)}")


@router.get("/{case_id}/nodes/{node_id}/tasks")
async def list_node_tasks(case_id: str, node_id: str, request: Request, user=Depends(get_verified_user)):
    c = cases_table.get_case_with_graph_by_id(case_id)
    if not c or c.user_id != user.id or not any(n.id == node_id for n in c.nodes):
        raise HTTPException(status_code=404, detail="node not found")
    task_ids = await list_task_ids_by_item_id(request.app.state.redis, node_id)
    return {"task_ids": task_ids}


@router.post("/{case_id}/nodes/{node_id}/tasks/stop")
async def stop_node_tasks(case_id: str, node_id: str, request: Request, user=Depends(get_verified_user)):
    c = cases_table.get_case_with_graph_by_id(case_id)
    if not c or c.user_id != user.id or not any(n.id == node_id for n in c.nodes):
        raise HTTPException(status_code=404, detail="node not found")
    res = await stop_item_tasks(request.app.state.redis, node_id)
    return res


@router.get("/{case_id}/stats")
async def get_case_stats(case_id: str, user=Depends(get_verified_user)):
    """节点/边统计信息接口。"""
    c = cases_table.get_case_with_graph_by_id(case_id)
    if not c or c.user_id != user.id:
        raise HTTPException(status_code=404, detail="case not found")
    node_count = len(c.nodes)
    edge_count = len(c.edges)
    types: Dict[str, int] = {}
    for n in c.nodes:
        types[n.node_type] = types.get(n.node_type, 0) + 1
    return {"nodeCount": node_count, "edgeCount": edge_count, "nodeTypeDistribution": types}


# --- 画布布局 保存/获取 ---


class CanvasLayoutForm(BaseModel):
    nodePositions: List[Dict[str, Any]]
    viewportState: Optional[Dict[str, Any]] = None


@router.put("/{case_id}/layout")
async def save_canvas_layout(case_id: str, body: CanvasLayoutForm, user=Depends(get_verified_user)):
    # 验证案例归属
    c = cases_table.get_case_by_id(case_id)
    if not c or c.user_id != user.id:
        raise HTTPException(status_code=404, detail="case not found")

    from open_webui.internal.db import get_db
    from open_webui.models.cases import Case as CaseRow
    with get_db() as db:
        row = db.query(CaseRow).filter_by(id=case_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="case not found")
        md = row.metadata_ or {}
        md["layout"] = {
            "nodePositions": body.nodePositions,
            "viewportState": body.viewportState or {},
            "lastSaved": int(time.time()),
        }
        row.metadata_ = md
        row.updated_at = int(time.time())
        db.commit()
    return {"ok": True}


@router.get("/{case_id}/layout")
async def get_canvas_layout(case_id: str, user=Depends(get_verified_user)):
    c = cases_table.get_case_by_id(case_id)
    if not c or c.user_id != user.id:
        raise HTTPException(status_code=404, detail="case not found")
    layout = (c.metadata or {}).get("layout") if c.metadata else None
    if not layout:
        return {
            "nodePositions": [],
            "viewportState": {"zoom": 1.0, "centerX": 0, "centerY": 0},
        }
    return {
        "nodePositions": layout.get("nodePositions", []),
        "viewportState": layout.get("viewportState", {"zoom": 1.0, "centerX": 0, "centerY": 0}),
    }


# --- 知识溯源 ---
@router.get("/{case_id}/nodes/{node_id}/knowledge")
async def get_node_knowledge(
    case_id: str, 
    node_id: str,
    topK: int = 5,
    vendor: Optional[str] = None,
    retrievalWeight: float = 0.7,
    user=Depends(get_verified_user)
):
    """
    获取节点知识溯源
    
    查询参数:
    - topK: 返回的文档片段数量 (可选，默认5，范围1-20)
    - vendor: 按指定厂商过滤 (可选)
    - retrievalWeight: 检索权重 (可选，默认0.7，范围0-1)
    """
    # 验证案例存在且属于当前用户
    c = cases_table.get_case_by_id(case_id)
    if not c or c.user_id != user.id:
        raise HTTPException(status_code=404, detail="案例不存在")
    
    # 查找节点
    node = cases_table.get_node_by_id(node_id)
    if not node or node.case_id != case_id:
        raise HTTPException(status_code=404, detail="节点不存在")
    
    # 验证参数
    if topK < 1 or topK > 20:
        raise HTTPException(status_code=400, detail="topK参数必须在1-20之间")
    
    if retrievalWeight < 0 or retrievalWeight > 1:
        raise HTTPException(status_code=400, detail="retrievalWeight参数必须在0-1之间")
    
    try:
        # 构建查询文本
        query_text = ""
        if node.content:
            if isinstance(node.content, dict):
                query_text = (
                    node.content.get('text', '') or 
                    node.content.get('analysis', '') or 
                    node.content.get('answer', '')
                )
            else:
                query_text = str(node.content)
        
        if not query_text and node.title:
            query_text = node.title
        
        # 如果没有有效的查询文本，返回空结果
        if not query_text:
            return {
                "nodeId": node_id,
                "sources": [],
                "retrievalMetadata": {
                    "totalCandidates": 0,
                    "retrievalTime": 0,
                    "rerankTime": 0,
                    "strategy": "no_query_text"
                }
            }
        
        # 调用知识检索服务
        from open_webui.routers.knowledge_migrated import hybrid_search_documents
        
        # 执行混合检索
        search_results = await hybrid_search_documents(
            query=query_text,
            top_k=topK,
            vendor_filter=vendor,
            retrieval_weight=retrievalWeight,
            user=user
        )
        
        # 转换为知识溯源格式
        sources = []
        for result in search_results.get("results", []):
            sources.append({
                "documentId": result.get("documentId"),
                "title": result.get("title"),
                "content": result.get("content"),
                "score": result.get("score"),
                "vendor": result.get("vendor"),
                "metadata": result.get("metadata", {})
            })
        
        return {
            "nodeId": node_id,
            "sources": sources,
            "retrievalMetadata": {
                "totalCandidates": len(sources),
                "retrievalTime": search_results.get("retrievalTime", 0),
                "rerankTime": search_results.get("rerankTime", 0),
                "strategy": "hybrid_search"
            }
        }
        
    except Exception as e:
        logger.error(f"Knowledge retrieval error: {str(e)}")
        # 如果服务失败，返回空结果
        return {
            "nodeId": node_id,
            "sources": [],
            "retrievalMetadata": {
                "totalCandidates": 0,
                "retrievalTime": 0,
                "rerankTime": 0,
                "strategy": "service_error"
            }
        }


# ========== 批量操作 ==========

class BatchCaseCreateRequest(BaseModel):
    """批量创建案例请求"""
    cases: List[CaseCreateForm]
    
class BatchCaseDeleteRequest(BaseModel):
    """批量删除案例请求"""
    case_ids: List[str]
    
class BatchCaseUpdateRequest(BaseModel):
    """批量更新案例请求"""
    case_ids: List[str]
    updates: Dict[str, Any]
    
class BatchOperationResult(BaseModel):
    """批量操作结果"""
    success_count: int
    failed_count: int
    total_count: int
    success_ids: List[str]
    failed_items: List[Dict[str, Any]]
    

@router.post("/batch/create", response_model=BatchOperationResult)
async def batch_create_cases(
    request: BatchCaseCreateRequest,
    user=Depends(get_verified_user)
):
    """批量创建案例 - 性能优化版本"""
    from open_webui.services.batch_processor import process_items_batch, BatchConfig
    
    # 配置批量处理参数
    config = BatchConfig(
        chunk_size=50,  # 每批50个案例
        max_workers=4,  # 4个并发工作线程
        timeout=300,    # 5分钟超时
        retry_attempts=2
    )
    
    def process_case_chunk(case_chunk: List[CaseForm]) -> List[str]:
        """处理一批案例"""
        success_ids = []
        current_time = int(time.time())
        
        # 准备批量插入数据
        case_data_list = []
        for case_data in case_chunk:
            case_id = str(uuid4())
            case_record = {
                "id": case_id,
                "user_id": user.id,
                "title": case_data.title,
                "description": case_data.description,
                "problem_type": case_data.problem_type,
                "vendor": case_data.vendor,
                "status": "active",
                "created_at": current_time,
                "updated_at": current_time
            }
            case_data_list.append(case_record)
            success_ids.append(case_id)
        
        # 批量插入数据库
        try:
            from open_webui.internal.db import get_db
            from open_webui.models.cases import Cases
            
            with get_db() as db:
                # 使用批量插入
                db.bulk_insert_mappings(Cases, case_data_list)
                db.commit()
                
            return success_ids
            
        except Exception as e:
            log.error(f"批量插入案例失败: {e}")
            raise e
    
    def error_handler(case_data: CaseForm, error: Exception) -> Dict[str, Any]:
        """错误处理函数"""
        return {
            "title": case_data.title,
            "error": str(error),
            "problem_type": getattr(case_data, 'problem_type', 'unknown')
        }
    
    # 执行批量处理
    result = await process_items_batch(
        items=request.cases,
        processor_func=process_case_chunk,
        config=config
    )
    
    return BatchOperationResult(
        success_count=result.success_count,
        failed_count=result.failed_count,
        total_count=result.total_count,
        success_ids=[item for sublist in result.success_items for item in sublist],  # 展平列表
        failed_items=result.failed_items
    )


@router.delete("/batch/delete", response_model=BatchOperationResult)
async def batch_delete_cases(
    request: BatchCaseDeleteRequest,
    user=Depends(get_verified_user)
):
    """批量删除案例"""
    success_ids = []
    failed_items = []
    
    for case_id in request.case_ids:
        try:
            # 检查案例是否存在且用户有权限
            case = cases_table.get_case_by_id(case_id)
            if not case:
                failed_items.append({
                    "case_id": case_id,
                    "error": "案例不存在"
                })
                continue
                
            if case.user_id != user.id and user.role != "admin":
                failed_items.append({
                    "case_id": case_id,
                    "error": "无权限删除此案例"
                })
                continue
            
            # 停止相关任务
            try:
                stop_item_tasks(case_id)
            except Exception as e:
                log.warning(f"停止案例任务失败 {case_id}: {str(e)}")
            
            # 删除案例
            result = cases_table.delete_case_by_id(case_id)
            if result:
                success_ids.append(case_id)
            else:
                failed_items.append({
                    "case_id": case_id,
                    "error": "数据库删除失败"
                })
                
        except Exception as e:
            log.error(f"批量删除案例失败 {case_id}: {str(e)}")
            failed_items.append({
                "case_id": case_id,
                "error": str(e)
            })
    
    return BatchOperationResult(
        success_count=len(success_ids),
        failed_count=len(failed_items),
        total_count=len(request.case_ids),
        success_ids=success_ids,
        failed_items=failed_items
    )


@router.put("/batch/update", response_model=BatchOperationResult)
async def batch_update_cases(
    request: BatchCaseUpdateRequest,
    user=Depends(get_verified_user)
):
    """批量更新案例"""
    success_ids = []
    failed_items = []
    
    # 验证更新字段
    allowed_fields = {"title", "description", "status", "problem_type", "vendor"}
    update_fields = set(request.updates.keys())
    if not update_fields.issubset(allowed_fields):
        invalid_fields = update_fields - allowed_fields
        raise HTTPException(
            status_code=400,
            detail=f"不允许更新的字段: {', '.join(invalid_fields)}"
        )
    
    for case_id in request.case_ids:
        try:
            # 检查案例是否存在且用户有权限
            case = cases_table.get_case_by_id(case_id)
            if not case:
                failed_items.append({
                    "case_id": case_id,
                    "error": "案例不存在"
                })
                continue
                
            if case.user_id != user.id and user.role != "admin":
                failed_items.append({
                    "case_id": case_id,
                    "error": "无权限更新此案例"
                })
                continue
            
            # 准备更新数据
            update_data = request.updates.copy()
            update_data["updated_at"] = int(time.time())
            
            # 更新案例
            result = cases_table.update_case_by_id(case_id, update_data)
            if result:
                success_ids.append(case_id)
            else:
                failed_items.append({
                    "case_id": case_id,
                    "error": "数据库更新失败"
                })
                
        except Exception as e:
            log.error(f"批量更新案例失败 {case_id}: {str(e)}")
            failed_items.append({
                "case_id": case_id,
                "error": str(e)
            })
    
    return BatchOperationResult(
        success_count=len(success_ids),
        failed_count=len(failed_items),
        total_count=len(request.case_ids),
        success_ids=success_ids,
        failed_items=failed_items
    )


@router.post("/batch/export")
async def batch_export_cases(
    case_ids: List[str],
    format: str = "json",
    user=Depends(get_verified_user)
):
    """批量导出案例"""
    try:
        cases = []
        for case_id in case_ids:
            case = cases_table.get_case_by_id(case_id)
            if case and (case.user_id == user.id or user.role == "admin"):
                cases.append({
                    "id": case.id,
                    "title": case.title,
                    "description": case.description,
                    "problem_type": case.problem_type,
                    "vendor": case.vendor,
                    "status": case.status,
                    "created_at": case.created_at,
                    "updated_at": case.updated_at
                })
        
        if format == "json":
            return {
                "success": True,
                "data": cases,
                "format": "json",
                "count": len(cases)
            }
        else:
            raise HTTPException(
                status_code=400,
                detail="暂不支持的导出格式"
            )
            
    except Exception as e:
        log.error(f"批量导出案例失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
