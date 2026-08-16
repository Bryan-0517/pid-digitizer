from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.database import get_session
from app.dexpi.schemas import DexpiMappingReport
from app.dexpi.export_schemas import ExportAvailability
from app.dexpi.export_service import DexpiExportService
from app.dexpi.pydexpi_v1_2_adapter import (
    PYDEXPI_VERSION,
    TARGET_DEXPI_VERSION,
    PydexpiCompatibilityError,
    installed_pydexpi_version,
    package_is_compatible,
)
from app.config import settings
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


@router.get("/{document_id}/dexpi/export/availability", response_model=ExportAvailability)
def export_availability(
    document_id: str, session: Session = Depends(get_session)
) -> ExportAvailability:
    if DocumentRepository(session).get(document_id) is None:
        raise HTTPException(status_code=404, detail="Document not found")
    compatible = package_is_compatible()
    if not settings.pydexpi_export_enabled:
        reason = "pyDEXPI export compatibility spike is disabled."
    elif not compatible:
        reason = f"pydexpi=={PYDEXPI_VERSION} is required; found {installed_pydexpi_version()}."
    else:
        reason = None
    return ExportAvailability(
        enabled=settings.pydexpi_export_enabled,
        available=settings.pydexpi_export_enabled and compatible,
        reason=reason,
    )


@router.post("/{document_id}/dexpi/export")
def export_dexpi(document_id: str, session: Session = Depends(get_session)) -> Response:
    if DocumentRepository(session).get(document_id) is None:
        raise HTTPException(status_code=404, detail="Document not found")
    availability = export_availability(document_id, session)
    if not availability.available:
        raise HTTPException(status_code=503, detail={
            "code": "pydexpi_export_unavailable", "message": availability.reason
        })
    graph = GraphRepository(session).graph(document_id)
    service = DexpiExportService()
    plan = service.plan(graph)
    if plan.status != "ready":
        raise HTTPException(status_code=409, detail=plan.model_dump(by_alias=True))
    try:
        artifact = service.pydexpi_adapter.export(graph, plan)
    except PydexpiCompatibilityError as exc:
        raise HTTPException(status_code=502, detail={
            "code": "pydexpi_compatibility_failure", "message": str(exc)
        }) from exc
    filename = f"{document_id}.dexpi-{TARGET_DEXPI_VERSION}.pydexpi.json"
    return Response(
        content=artifact.content,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-DEXPI-Conformance-Validated": "false",
            "X-DEXPI-Target-Version": TARGET_DEXPI_VERSION,
            "X-PyDEXPI-Version": PYDEXPI_VERSION,
        },
    )
