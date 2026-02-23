"""FastAPI application entrypoint for the InfiniMind service."""

import logging
from datetime import UTC, datetime
from pathlib import Path

from fastapi import Depends, FastAPI

from .api_models import BatchStoreRequest, BatchStoreResponse, StoreMemoryRequest, StoreMemoryResult
from .auth import require_api_key
from .embeddings import build_embedding_client
from .memory_schema import MemoryRecord, compute_content_hash
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
    app.state.embedding_client = build_embedding_client(settings)
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


def _store_one(payload: StoreMemoryRequest) -> StoreMemoryResult:
    """Store one memory item with duplicate detection."""

    settings = get_settings()
    content_hash = compute_content_hash(payload.text)

    duplicate = app.state.memory_store.find_duplicate(
        tenant_id=payload.tenant_id,
        user_id=payload.user_id,
        agent_id=payload.agent_id,
        content_hash=content_hash,
        dedupe_key=payload.dedupe_key,
    )
    if duplicate:
        return StoreMemoryResult(
            action="duplicate",
            memory_id=str(duplicate.get("memory_id")),
            duplicate_of=str(duplicate.get("memory_id")),
        )

    now_iso = datetime.now(UTC).isoformat()
    vector = app.state.embedding_client.embed(payload.text)
    record = MemoryRecord(
        tenant_id=payload.tenant_id,
        user_id=payload.user_id,
        agent_id=payload.agent_id,
        text=payload.text,
        category=payload.category,
        tags=payload.tags,
        importance=payload.importance,
        scope=payload.scope,
        sensitivity=payload.sensitivity,
        source_channel=payload.channel_id,
        source_session=payload.session_id,
        source_actor=payload.actor_id,
        created_at=now_iso,
        updated_at=now_iso,
        ttl_expires_at=payload.ttl_expires_at(),
        embedding_model_id=settings.embedding_model,
        content_hash=content_hash,
        dedupe_key=payload.dedupe_key,
        provenance=payload.provenance,
        quality=payload.quality,
        vector=vector,
    )
    app.state.memory_store.store_memory(record)
    return StoreMemoryResult(action="created", memory_id=record.memory_id)


@app.post("/v1/memory/store", response_model=StoreMemoryResult, dependencies=[Depends(require_api_key)])
def store_memory(payload: StoreMemoryRequest) -> StoreMemoryResult:
    """Store a single enriched memory object."""

    return _store_one(payload)


@app.post(
    "/v1/memory/batch-store",
    response_model=BatchStoreResponse,
    dependencies=[Depends(require_api_key)],
)
def batch_store(payload: BatchStoreRequest) -> BatchStoreResponse:
    """Store memory records in batch while preserving per-item outcomes."""

    results = [_store_one(item) for item in payload.items]
    created_count = len([item for item in results if item.action == "created"])
    duplicate_count = len(results) - created_count
    return BatchStoreResponse(
        created_count=created_count,
        duplicate_count=duplicate_count,
        results=results,
    )
