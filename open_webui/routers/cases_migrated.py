import logging
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional, List

from open_webui.env import SRC_LOG_LEVELS
from open_webui.utils.auth import get_verified_user
from open_webui.models.cases import (
    CasesTable,
    CaseCreateForm,
    CaseListResponse,
    CaseModel,
    CaseWithGraphModel,
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
