from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_session
from app.documents.repository import DocumentRepository
from app.graph_queries.schemas import GraphQueryRequest, GraphQueryResult
from app.graph_queries.service import GraphQueryService
from app.graphs.repository import GraphRepository


router = APIRouter(tags=["graph-query"])


@router.post("/documents/{document_id}/graph/query", response_model=GraphQueryResult)
def query_graph(
    document_id: str,
    request: Annotated[GraphQueryRequest, Body()],
    session: Session = Depends(get_session),
) -> GraphQueryResult:
    if DocumentRepository(session).get(document_id) is None:
        raise HTTPException(status_code=404, detail="Document not found")
    graph = GraphRepository(session).graph(document_id)
    return GraphQueryService().query(graph, request)
