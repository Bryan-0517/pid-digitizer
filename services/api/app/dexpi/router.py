from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_session
from app.dexpi.schemas import DexpiMappingReport
from app.dexpi.v01_adapter import VersionNeutralDexpiAdapter
from app.documents.repository import DocumentRepository
from app.graphs.repository import GraphRepository


router = APIRouter(prefix="/documents", tags=["dexpi-preflight"])


@router.post("/{document_id}/dexpi/validate", response_model=DexpiMappingReport)
def validate_dexpi(
    document_id: str, session: Session = Depends(get_session)
) -> DexpiMappingReport:
    if DocumentRepository(session).get(document_id) is None:
        raise HTTPException(status_code=404, detail="Document not found")
    graph = GraphRepository(session).graph(document_id)
    return VersionNeutralDexpiAdapter().validate_mappable(graph)
