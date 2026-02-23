"""FastAPI application entrypoint for the InfiniMind service."""

from pathlib import Path

from fastapi import Depends, FastAPI

from .auth import require_api_key
from .models import HealthResponse
from .settings import get_settings

APP_VERSION = "0.1.0"

app = FastAPI(
    title="InfiniMind Service",
    version=APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)


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

    return HealthResponse(
        status="ready",
        service="infinimind-service",
        version=APP_VERSION,
        environment=settings.app_env,
    )
