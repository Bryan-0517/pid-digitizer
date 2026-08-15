from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.database import get_session
from app.documents.repository import DocumentRepository
from app.domain.models import EngineeringConnection, EngineeringEntity, EngineeringGraph
from app.graphs.repository import GraphRepository
from app.graphs.schemas import ConnectionCreate, ConnectionPatch, EntityPatch

router = APIRouter(tags=["engineering-graph"])


@router.get("/documents/{document_id}/graph", response_model=EngineeringGraph)
def get_graph(document_id: str, session: Session = Depends(get_session)) -> EngineeringGraph:
    if DocumentRepository(session).get(document_id) is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return GraphRepository(session).graph(document_id)


@router.patch("/entities/{entity_id}", response_model=EngineeringEntity)
def patch_entity(
    entity_id: str, patch: EntityPatch, session: Session = Depends(get_session)
) -> EngineeringEntity:
    try:
        entity = GraphRepository(session).patch_entity(entity_id, patch)
    except (ValidationError, ValueError) as exc:
        session.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


@router.post(
    "/documents/{document_id}/connections",
    response_model=EngineeringConnection,
    status_code=status.HTTP_201_CREATED,
)
def create_connection(
    document_id: str, request: ConnectionCreate, session: Session = Depends(get_session)
) -> EngineeringConnection:
    if DocumentRepository(session).get(document_id) is None:
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        return GraphRepository(session).create_connection(document_id, request)
    except (ValidationError, ValueError) as exc:
        session.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch("/connections/{connection_id}", response_model=EngineeringConnection)
def patch_connection(
    connection_id: str, patch: ConnectionPatch, session: Session = Depends(get_session)
) -> EngineeringConnection:
    try:
        connection = GraphRepository(session).patch_connection(connection_id, patch)
    except (ValidationError, ValueError) as exc:
        session.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if connection is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    return connection


@router.delete("/connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_connection(
    connection_id: str, session: Session = Depends(get_session)
) -> Response:
    if GraphRepository(session).delete_connection(connection_id) is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
