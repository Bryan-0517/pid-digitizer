from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.documents.router as document_router
from app.config import Settings
from app.database import Base, get_session
from app.documents import db_models as document_db_models  # noqa: F401
from app.graphs import db_models as graph_db_models  # noqa: F401
from app.main import app


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(test_engine)
    test_sessions = sessionmaker(bind=test_engine, expire_on_commit=False)

    def session_override() -> Generator[Session, None, None]:
        with test_sessions() as session:
            yield session

    monkeypatch.setattr(
        document_router,
        "settings",
        Settings(database_url="sqlite://", storage_dir=tmp_path, demo_mock_graph=False),
    )
    app.dependency_overrides[get_session] = session_override
    yield TestClient(app)
    app.dependency_overrides.clear()
    Base.metadata.drop_all(test_engine)
