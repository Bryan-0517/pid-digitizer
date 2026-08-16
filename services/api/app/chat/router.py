from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.chat.schemas import ChatRequest, ChatResponse
from app.chat.service import ChatService
from app.database import get_session
from app.documents.repository import DocumentRepository
from app.graphs.repository import GraphRepository


router = APIRouter(prefix="/documents", tags=["graph-chat"])


@router.post("/{document_id}/chat", response_model=ChatResponse)
async def chat(
    document_id: str,
    request: ChatRequest,
    session: Session = Depends(get_session),
) -> ChatResponse:
    if DocumentRepository(session).get(document_id) is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return await ChatService().respond(GraphRepository(session).graph(document_id), request)
