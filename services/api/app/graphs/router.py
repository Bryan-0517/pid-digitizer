from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.database import get_session
from app.documents.repository import DocumentRepository
from app.domain.models import EngineeringEntity, EngineeringGraph
from app.graphs.repository import GraphRepository
from app.graphs.schemas import EntityPatch

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
