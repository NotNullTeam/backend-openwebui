import logging
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from open_webui.env import SRC_LOG_LEVELS
from open_webui.utils.auth import get_verified_user

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
async def parse_log(req: LogParsingRequest, user=Depends(get_verified_user)):
    """
    Analysis migration skeleton endpoint.
    TODO: integrate Ali IDP/log parsing service and RAG retrieval.
    """
    # 保持接口存在但提示未实现，方便后续逐步替换实现
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="analysis/log-parsing not implemented yet in migrated backend",
    )
