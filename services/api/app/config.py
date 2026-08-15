import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    database_url: str
    storage_dir: Path
    demo_mock_graph: bool
    ai_provider: str | None = None
    ai_model: str | None = None
    ai_api_key: str | None = field(default=None, repr=False)


def _database_url() -> str:
    url = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/pid_digitizer",
    )
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


settings = Settings(
    database_url=_database_url(),
    storage_dir=Path(os.getenv("STORAGE_DIR", "data")),
    demo_mock_graph=os.getenv("DEMO_MOCK_GRAPH", "false").lower() in {"1", "true", "yes"},
    ai_provider=os.getenv("AI_PROVIDER") or None,
    ai_model=os.getenv("AI_MODEL") or None,
    ai_api_key=os.getenv("AI_API_KEY") or None,
)
