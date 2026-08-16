from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.config import settings
from app.chat.router import router as chat_router
from app.database import create_schema
from app.digitization.router import router as digitization_router
from app.documents.router import router as documents_router
from app.graphs.router import router as graphs_router
from app.graph_queries.router import router as graph_queries_router


class HealthResponse(BaseModel):
    status: str
    service: str



@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    create_schema()
    yield


app = FastAPI(title="P&ID Digitizer API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
)
app.mount("/files", StaticFiles(directory=settings.storage_dir, check_dir=False), name="files")
app.include_router(documents_router)
app.include_router(digitization_router)
app.include_router(graphs_router)
app.include_router(graph_queries_router)
app.include_router(chat_router)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="api")
