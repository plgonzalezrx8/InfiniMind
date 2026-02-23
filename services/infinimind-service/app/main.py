"""FastAPI application entrypoint for the InfiniMind service."""

import json
import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from fastapi import Depends, FastAPI

from .api_models import (
    BatchStoreRequest,
    BatchStoreResponse,
    ReembedRequest,
    ReembedResponse,
    RecallDebug,
    RecallItem,
    RecallRequest,
    RecallResponse,
    StoreMemoryRequest,
    StoreMemoryResult,
)
from .auth import require_admin_api_key, require_api_key
from .embeddings import build_embedding_client, build_embedding_client_for_model
from .memory_schema import MemoryRecord, compute_content_hash
from .models import HealthResponse
from .observability import (
    POLICY_NOTES_TOTAL,
    RECALL_FALLBACK_TOTAL,
    STORE_RESULTS_TOTAL,
    install_metrics_middleware,
    metrics_response,
)
from .policy import apply_hard_filters, apply_safe_fallback
from .retrieval import hybrid_rank
from .settings import get_settings
from .storage import LanceMemoryStore

APP_VERSION = "0.1.0"
LOGGER = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(_: FastAPI):
    """Initialize and tear down shared runtime dependencies."""

    settings = get_settings()
    store = LanceMemoryStore(db_path=settings.lancedb_path, vector_dim=settings.vector_dim)
    store.ensure_initialized()
    app.state.memory_store = store
    app.state.embedding_client = build_embedding_client(settings)
    LOGGER.info("Initialized LanceDB store at %s", store.db_path)
    yield


app = FastAPI(
    title="InfiniMind Service",
    version=APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=_lifespan,
)
install_metrics_middleware(app)


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


@app.get("/v1/metrics")
def metrics():
    """Expose Prometheus metrics for scraping."""

    return metrics_response()


@app.post(
    "/v1/admin/reembed",
    response_model=ReembedResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def reembed(payload: ReembedRequest) -> ReembedResponse:
    """Re-embed existing rows into a new shadow table without overwriting primary vectors."""

    settings = get_settings()
    rows = app.state.memory_store.list_memories(limit=payload.limit)
    if payload.dry_run:
        return ReembedResponse(
            target_model_id=payload.target_model_id,
            processed=len(rows),
            dry_run=True,
            shadow_table=None,
        )

    embedder = build_embedding_client_for_model(settings, payload.target_model_id)
    vectors = [embedder.embed(str(row.get("text") or "")) for row in rows]
    shadow_table = app.state.memory_store.write_shadow_embeddings(
        target_model_id=payload.target_model_id,
        rows=rows,
        vectors=vectors,
    )
    return ReembedResponse(
        target_model_id=payload.target_model_id,
        processed=len(rows),
        dry_run=False,
        shadow_table=shadow_table,
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
        STORE_RESULTS_TOTAL.labels(action="duplicate").inc()
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
    STORE_RESULTS_TOTAL.labels(action="created").inc()
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


def _row_to_recall_item(
    row: dict,
    score: float,
    score_breakdown: dict[str, float] | None = None,
) -> RecallItem:
    """Convert a raw storage row into the public recall response shape."""

    tags = json.loads(row.get("tags_json") or "[]")
    conflict_set = json.loads(row.get("quality_conflict_set_json") or "[]")
    return RecallItem(
        memory_id=str(row.get("memory_id")),
        text=str(row.get("text") or ""),
        category=str(row.get("category") or "other"),
        tags=tags,
        score=score,
        importance=float(row.get("importance") or 0.0),
        scope=str(row.get("scope") or "user"),
        sensitivity=str(row.get("sensitivity") or "low"),
        created_at=str(row.get("created_at") or ""),
        updated_at=str(row.get("updated_at") or ""),
        ttl_expires_at=row.get("ttl_expires_at"),
        provenance={
            "source_type": row.get("provenance_source_type"),
            "source_ref": row.get("provenance_source_ref"),
        },
        quality={
            "confidence": float(row.get("quality_confidence") or 0.0),
            "verification_status": row.get("quality_verification_status"),
            "conflict_set": conflict_set,
        },
        embedding_model_id=str(row.get("embedding_model_id") or ""),
        score_breakdown=score_breakdown,
    )


@app.post("/v1/memory/recall", response_model=RecallResponse, dependencies=[Depends(require_api_key)])
def recall(payload: RecallRequest) -> RecallResponse:
    """Recall memories using strict pre-ranking policy filters."""

    rows = app.state.memory_store.list_memories(limit=5000)
    filtered_rows = apply_hard_filters(rows, payload)
    fallback_applied = False
    policy_notes: list[str] = []

    if payload.include_sensitive and payload.trust_level != "high":
        policy_notes.append("include_sensitive requested without high trust; high sensitivity excluded")

    if (
        payload.fallback_mode == "legacy-compatible"
        and len(filtered_rows) < payload.limit
        and (payload.categories or payload.tags_any or payload.since or payload.until or payload.scope)
    ):
        filtered_rows = apply_safe_fallback(rows, payload)
        fallback_applied = True
        policy_notes.append("safe fallback relaxed optional filters")
        RECALL_FALLBACK_TOTAL.inc()

    for note in policy_notes:
        POLICY_NOTES_TOTAL.labels(note=note).inc()
    items: list[RecallItem]

    if payload.rerank == "hybrid":
        query_vector = app.state.embedding_client.embed(payload.query)
        ranked = hybrid_rank(
            filtered_rows,
            query=payload.query,
            query_vector=query_vector,
            limit=payload.limit,
        )
        items = [
            _row_to_recall_item(
                item["row"],
                score=float(item["score"]),
                score_breakdown=item.get("score_breakdown"),
            )
            for item in ranked
        ]
    else:
        query_terms = [token for token in payload.query.lower().split() if token]
        scored: list[tuple[float, dict]] = []
        for row in filtered_rows:
            text = str(row.get("text") or "").lower()
            term_hits = sum(1 for term in query_terms if term in text)
            lexical_score = term_hits / max(len(query_terms), 1)
            importance = float(row.get("importance") or 0.0)
            score = (0.65 * lexical_score) + (0.35 * importance)
            scored.append((score, row, lexical_score, importance))

        scored.sort(key=lambda item: item[0], reverse=True)
        top_rows = scored[: payload.limit]
        items = [
            _row_to_recall_item(
                row,
                score=score,
                score_breakdown={"lexical": lexical_score, "importance": importance},
            )
            for score, row, lexical_score, importance in top_rows
        ]

    debug = None
    if payload.debug:
        debug = RecallDebug(
            total_rows=len(rows),
            filtered_rows=len(filtered_rows),
            returned_rows=len(items),
            fallback_applied=fallback_applied,
            policy_notes=policy_notes,
        )

    return RecallResponse(count=len(items), memories=items, debug=debug)
