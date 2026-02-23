"""FastAPI application entrypoint for the InfiniMind service."""

import logging
from pathlib import Path

from fastapi import Depends, FastAPI

from .auth import require_api_key
from .models import HealthResponse
from .settings import get_settings
from .storage import LanceMemoryStore

APP_VERSION = "0.1.0"
LOGGER = logging.getLogger(__name__)

app = FastAPI(
    title="InfiniMind Service",
    version=APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)


@app.on_event("startup")
def startup() -> None:
    """Initialize persistent dependencies required by the service."""

    settings = get_settings()
    store = LanceMemoryStore(db_path=settings.lancedb_path, vector_dim=settings.vector_dim)
    store.ensure_initialized()
    app.state.memory_store = store
    LOGGER.info("Initialized LanceDB store at %s", store.db_path)


@app.get("/v1/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness endpoint used by orchestrators and smoke checks."""

    settings = get_settings()
    return HealthResponse(
        status="ok",
        service="infinimind-service",
        version=APP_VERSION,
        environment=settings.app_env,
    )


@app.get("/v1/ready", response_model=HealthResponse)
def ready(_: None = Depends(require_api_key)) -> HealthResponse:
    """Readiness endpoint validating basic runtime dependencies.

    We currently validate that the configured data directory exists and is writable.
    """

    settings = get_settings()
    data_dir = Path(settings.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    probe_file = data_dir / ".ready"
    probe_file.write_text("ok", encoding="utf-8")
    probe_file.unlink(missing_ok=True)

    # Readiness also verifies that storage was initialized during startup.
    if not hasattr(app.state, "memory_store"):
        raise RuntimeError("memory store missing")
    if not app.state.memory_store.is_ready():
        raise RuntimeError("memory store not ready")

    return HealthResponse(
        status="ready",
        service="infinimind-service",
        version=APP_VERSION,
        environment=settings.app_env,
    )
