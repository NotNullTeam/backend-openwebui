import logging
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional, List

from open_webui.env import SRC_LOG_LEVELS
from open_webui.utils.auth import get_verified_user

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])

router = APIRouter()


class CaseCreateRequest(BaseModel):
    query: str
    attachments: Optional[list[dict]] = None
    useLanggraph: Optional[bool] = False
    vendor: Optional[str] = None


class CaseModel(BaseModel):
    id: str
    title: str
    query: str
    status: str
    vendor: Optional[str] = None
    category: Optional[str] = None
    created_at: Optional[int] = None
    updated_at: Optional[int] = None
    user_id: Optional[str] = None


class PaginatedCases(BaseModel):
    items: List[CaseModel] = []
    total: int = 0
    page: int = 1
    page_size: int = 10


@router.get("/", response_model=PaginatedCases)
async def list_cases(
    page: int = 1,
    page_size: int = 10,
    user=Depends(get_verified_user),
):
    """
    Cases migration skeleton endpoint.
    TODO: wire to SQLAlchemy models and implement filters & pagination.
    """
    return PaginatedCases(items=[], total=0, page=page, page_size=page_size)


@router.post("/", response_model=CaseModel)
async def create_case(body: CaseCreateRequest, user=Depends(get_verified_user)):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="cases create not implemented yet in migrated backend",
    )


@router.get("/{case_id}", response_model=CaseModel)
async def get_case(case_id: str, user=Depends(get_verified_user)):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="cases detail not implemented yet in migrated backend",
    )
