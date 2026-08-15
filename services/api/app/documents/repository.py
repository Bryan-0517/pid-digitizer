from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.documents.db_models import DocumentPageRecord, DocumentRecord


class DocumentRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, name: str, source_type: str) -> DocumentRecord:
        now = datetime.now(UTC)
        record = DocumentRecord(
            id=str(uuid4()),
            name=name,
            source_type=source_type,
            status="uploaded",
            created_at=now,
            updated_at=now,
        )
        self.session.add(record)
        self.session.commit()
        return record

    def get(self, document_id: str) -> DocumentRecord | None:
        return self.session.get(DocumentRecord, document_id)

    def page(self, document_id: str) -> DocumentPageRecord | None:
        return self.session.scalar(
            select(DocumentPageRecord).where(DocumentPageRecord.document_id == document_id)
        )

    def set_status(self, record: DocumentRecord, status: str) -> None:
        record.status = status
        record.updated_at = datetime.now(UTC)
        self.session.commit()

    def save_page(
        self,
        record: DocumentRecord,
        page_id: str,
        image_uri: str,
        width_px: int,
        height_px: int,
    ) -> DocumentPageRecord:
        page = DocumentPageRecord(
            id=page_id,
            document_id=record.id,
            page_number=1,
            image_uri=image_uri,
            width_px=width_px,
            height_px=height_px,
        )
        record.status = "ready"
        record.updated_at = datetime.now(UTC)
        self.session.add(page)
        self.session.commit()
        return page
