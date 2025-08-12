import time
import uuid
from typing import Optional, List

from pydantic import BaseModel, ConfigDict
from sqlalchemy import Column, String, Text, BigInteger, JSON

from open_webui.internal.db import Base, get_db


class Case(Base):
    __tablename__ = "case"

    id = Column(Text, primary_key=True, unique=True)
    user_id = Column(Text)

    title = Column(Text)
    query = Column(Text)
    status = Column(Text)  # open | solved | closed
    vendor = Column(Text, nullable=True)
    category = Column(Text, nullable=True)

    created_at = Column(BigInteger)
    updated_at = Column(BigInteger)


class CaseNode(Base):
    __tablename__ = "case_node"

    id = Column(Text, primary_key=True, unique=True)
    case_id = Column(Text)

    title = Column(Text)
    content = Column(Text)
    node_type = Column(Text)
    status = Column(Text, nullable=True)
    metadata = Column(JSON, nullable=True)

    created_at = Column(BigInteger)


class CaseEdge(Base):
    __tablename__ = "case_edge"

    id = Column(Text, primary_key=True, unique=True)
    case_id = Column(Text)

    source_node_id = Column(Text)
    target_node_id = Column(Text)
    edge_type = Column(Text)
    metadata = Column(JSON, nullable=True)


class CaseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    title: str
    query: str
    status: str
    vendor: Optional[str] = None
    category: Optional[str] = None
    created_at: Optional[int] = None
    updated_at: Optional[int] = None


class CaseCreateForm(BaseModel):
    query: str
    attachments: Optional[list[dict]] = None
    useLanggraph: Optional[bool] = False
    vendor: Optional[str] = None


class CaseNodeModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_id: str
    title: str
    content: str
    node_type: str
    status: Optional[str] = None
    metadata: Optional[dict] = None
    created_at: Optional[int] = None


class CaseEdgeModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_id: str
    source_node_id: str
    target_node_id: str
    edge_type: str
    metadata: Optional[dict] = None


class CaseWithGraphModel(CaseModel):
    nodes: List[CaseNodeModel] = []
    edges: List[CaseEdgeModel] = []


class CaseListResponse(BaseModel):
    items: List[CaseModel]
    total: int
    page: int
    page_size: int


class CasesTable:
    def insert_new_case(self, user_id: str, form: CaseCreateForm) -> Optional[CaseModel]:
        now = int(time.time())
        title = form.query[:100] + "..." if len(form.query or "") > 100 else form.query
        c = Case(
            id=str(uuid.uuid4()),
            user_id=user_id,
            title=title,
            query=form.query,
            status="open",
            vendor=form.vendor,
            category=None,
            created_at=now,
            updated_at=now,
        )
        with get_db() as db:
            db.add(c)
            db.commit()
            db.refresh(c)
            return CaseModel.model_validate(c)

    def get_case_by_id(self, case_id: str) -> Optional[CaseModel]:
        with get_db() as db:
            c = db.query(Case).filter_by(id=case_id).first()
            return CaseModel.model_validate(c) if c else None

    def get_case_with_graph_by_id(self, case_id: str) -> Optional[CaseWithGraphModel]:
        with get_db() as db:
            c = db.query(Case).filter_by(id=case_id).first()
            if not c:
                return None
            nodes = db.query(CaseNode).filter_by(case_id=case_id).all()
            edges = db.query(CaseEdge).filter_by(case_id=case_id).all()
            return CaseWithGraphModel(
                **CaseModel.model_validate(c).model_dump(),
                nodes=[CaseNodeModel.model_validate(n) for n in nodes],
                edges=[CaseEdgeModel.model_validate(e) for e in edges],
            )

    def list_cases_by_user(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 10,
        status: Optional[str] = None,
        vendor: Optional[str] = None,
        category: Optional[str] = None,
    ) -> CaseListResponse:
        with get_db() as db:
            query = db.query(Case).filter_by(user_id=user_id)
            if status:
                query = query.filter(Case.status == status)
            if vendor:
                query = query.filter(Case.vendor == vendor)
            if category:
                query = query.filter(Case.category == category)

            total = query.count()
            items = (
                query.order_by(Case.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
                .all()
            )
            return CaseListResponse(
                items=[CaseModel.model_validate(i) for i in items],
                total=total,
                page=page,
                page_size=page_size,
            )

