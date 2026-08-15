from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.domain.models import Document, DocumentPage


def _to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class CreateDocumentRequest(BaseModel):
    model_config = ConfigDict(alias_generator=lambda value: _to_camel(value), populate_by_name=True)

    name: str
    source_type: Literal["image", "pdf"]


class DocumentDetail(BaseModel):
    document: Document
    page: DocumentPage | None = None
