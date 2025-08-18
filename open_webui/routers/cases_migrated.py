import logging
from fastapi import APIRouter, Depends, HTTPException, status
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


@router.post("/", response_model=CaseModel)
async def create_case(body: CaseCreateForm, user=Depends(get_verified_user)):
    if not body.query or not body.query.strip():
        raise HTTPException(status_code=400, detail="query is required")
    return cases_table.insert_new_case(user_id=user.id, form=body)


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


# ---------- helpers ----------
def json_dumps_safe(data: Any) -> str:
    try:
        import json

        return json.dumps(data, ensure_ascii=False)
    except Exception:
        return str(data)
