from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.ai.errors import (
    AIProviderError,
    ProviderConfigurationError,
    ProviderNotConfiguredError,
    ProviderTimeoutError,
)
from app.ai.factory import create_ai_provider
from app.ai.provider import AIProvider
from app.config import settings
from app.database import get_session
from app.digitization.schemas import DigitizationProposalResponse
from app.digitization.service import extract_page_proposal
from app.documents.repository import DocumentRepository

router = APIRouter(prefix="/documents", tags=["digitization"])


def get_ai_provider() -> AIProvider:
    try:
        return create_ai_provider(settings)
    except (ProviderNotConfiguredError, ProviderConfigurationError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _page_image_path(image_uri: str) -> Path:
    relative = image_uri.removeprefix("/files/")
    storage_root = settings.storage_dir.resolve()
    path = (storage_root / relative).resolve()
    if not path.is_relative_to(storage_root):
        raise HTTPException(status_code=500, detail="Document page storage path is invalid")
    return path


@router.post("/{document_id}/digitize", response_model=DigitizationProposalResponse)
async def digitize_document(
    document_id: str,
    session: Session = Depends(get_session),
    provider: AIProvider = Depends(get_ai_provider),
) -> DigitizationProposalResponse:
    repository = DocumentRepository(session)
    document = repository.get(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    page = repository.page(document_id)
    if page is None:
        raise HTTPException(status_code=409, detail="Document has no uploaded page")
    image_path = _page_image_path(page.image_uri)
    if not image_path.is_file():
        raise HTTPException(status_code=500, detail="Document page image is unavailable")
    try:
        return await extract_page_proposal(
            provider=provider,
            document_id=document_id,
            page_id=page.id,
            image_path=image_path,
            width_px=page.width_px,
            height_px=page.height_px,
        )
    except ProviderNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ProviderTimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except AIProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI topology proposal failed validation",
        ) from exc
