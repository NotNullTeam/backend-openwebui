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
