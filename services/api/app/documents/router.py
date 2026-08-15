from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_session
from app.documents.repository import DocumentRepository
from app.documents.schemas import CreateDocumentRequest, DocumentDetail
from app.documents.service import (
    SUPPORTED_INPUT_MESSAGE,
    UploadValidationError,
    normalize_upload,
    save_page,
    save_source,
    validate_upload_filename,
)
from app.domain.models import Document, DocumentPage

router = APIRouter(prefix="/documents", tags=["documents"])


def _document(record: object) -> Document:
    return Document(
        id=record.id,
        name=record.name,
        source_type=record.source_type,
        status=record.status,
        created_at=_timestamp(record.created_at),
        updated_at=_timestamp(record.updated_at),
    )


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _page(record: object) -> DocumentPage:
    return DocumentPage(
        id=record.id,
        document_id=record.document_id,
        page_number=record.page_number,
        image_uri=record.image_uri,
        width_px=record.width_px,
        height_px=record.height_px,
    )


@router.post("", response_model=Document, status_code=status.HTTP_201_CREATED)
def create_document(request: CreateDocumentRequest, session: Session = Depends(get_session)) -> Document:
    if request.source_type not in {"image", "pdf"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=SUPPORTED_INPUT_MESSAGE,
        )
    if not request.name.strip():
        raise HTTPException(status_code=422, detail="Document name must not be empty")
    return _document(DocumentRepository(session).create(request.name.strip(), request.source_type))


@router.post("/{document_id}/upload", response_model=DocumentDetail)
async def upload_document(
    document_id: str,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> DocumentDetail:
    repository = DocumentRepository(session)
    record = repository.get(document_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if repository.page(document_id) is not None:
        raise HTTPException(status_code=409, detail="Document already has an uploaded page")
    repository.set_status(record, "processing")
    try:
        validate_upload_filename(file.filename, record.source_type)
        content = await file.read()
        normalized = normalize_upload(content, record.source_type)
        page_id = str(uuid4())
        save_source(content, normalized, settings.storage_dir, record.id)
        image_uri = save_page(normalized, settings.storage_dir, record.id, page_id)
        page_record = repository.save_page(
            record, page_id, image_uri, normalized.image.width, normalized.image.height
        )
    except UploadValidationError as exc:
        repository.set_status(record, "error")
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return DocumentDetail(document=_document(record), page=_page(page_record))


@router.get("/{document_id}", response_model=DocumentDetail)
def get_document(document_id: str, session: Session = Depends(get_session)) -> DocumentDetail:
    repository = DocumentRepository(session)
    record = repository.get(document_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Document not found")
    page_record = repository.page(document_id)
    return DocumentDetail(
        document=_document(record), page=_page(page_record) if page_record is not None else None
    )
