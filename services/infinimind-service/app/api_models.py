"""HTTP request/response models for memory APIs."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from .memory_schema import MemoryCategory, MemoryScope, MemorySensitivity, MemoryProvenance, MemoryQuality


class StoreMemoryRequest(BaseModel):
    """Payload for storing one memory item."""

    tenant_id: str = "default"
    user_id: str
    agent_id: str = "main"
    text: str = Field(min_length=1)
    importance: float = Field(default=0.7, ge=0.0, le=1.0)
    category: MemoryCategory = "other"
    scope: MemoryScope = MemoryScope.USER
    channel_id: str | None = None
    session_id: str | None = None
    actor_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    sensitivity: MemorySensitivity = MemorySensitivity.LOW
    ttl_hours: int | None = Field(default=None, ge=1, le=24 * 365)
    dedupe_key: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    provenance: MemoryProvenance = Field(default_factory=MemoryProvenance)
    quality: MemoryQuality = Field(default_factory=MemoryQuality)

    def ttl_expires_at(self) -> str | None:
        """Compute expiry timestamp from ttl_hours when configured."""

        if self.ttl_hours is None:
            return None
        return (datetime.now(UTC) + timedelta(hours=self.ttl_hours)).isoformat()


class StoreMemoryResult(BaseModel):
    """Outcome item returned for store operations."""

    action: Literal["created", "duplicate"]
    memory_id: str
    duplicate_of: str | None = None


class BatchStoreRequest(BaseModel):
    """Payload for storing multiple memory items in one request."""

    items: list[StoreMemoryRequest] = Field(min_length=1, max_length=200)


class BatchStoreResponse(BaseModel):
    """Batch store summary and per-item outcomes."""

    created_count: int
    duplicate_count: int
    results: list[StoreMemoryResult]


class RecallRequest(BaseModel):
    """Payload for memory retrieval with optional hard filters."""

    tenant_id: str = "default"
    user_id: str
    agent_id: str = "main"
    query: str = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=100)
    scope: MemoryScope | None = None
    channel_id: str | None = None
    session_id: str | None = None
    actor_id: str | None = None
    categories: list[MemoryCategory] = Field(default_factory=list)
    tags_any: list[str] = Field(default_factory=list)
    min_importance: float | None = Field(default=None, ge=0.0, le=1.0)
    since: datetime | None = None
    until: datetime | None = None
    include_expired: bool = False
    include_sensitive: bool = False
    trust_level: Literal["low", "medium", "high"] = "medium"
    fallback_mode: Literal["off", "legacy-compatible"] = "legacy-compatible"
    rerank: Literal["off", "hybrid"] = "off"
    debug: bool = False

    @model_validator(mode="after")
    def validate_time_range(self) -> "RecallRequest":
        """Ensure recall time windows are chronologically valid when provided."""

        if self.since and self.until and self.since > self.until:
            raise ValueError("since must be less than or equal to until")
        return self


class RecallItem(BaseModel):
    """Memory snippet returned to OpenClaw bridge callers."""

    memory_id: str
    text: str
    category: str
    tags: list[str]
    score: float
    importance: float
    scope: str
    sensitivity: str
    created_at: str
    updated_at: str
    ttl_expires_at: str | None
    provenance: dict[str, Any]
    quality: dict[str, Any]
    embedding_model_id: str
    score_breakdown: dict[str, float] | None = None


class RecallDebug(BaseModel):
    """Optional debug details for retrieval-stage diagnostics."""

    total_rows: int
    filtered_rows: int
    returned_rows: int
    fallback_applied: bool
    policy_notes: list[str]


class RecallResponse(BaseModel):
    """Final recall response payload."""

    count: int
    memories: list[RecallItem]
    debug: RecallDebug | None = None


class ForgetRequest(BaseModel):
    """Payload for deleting a memory directly or resolving candidates from a query."""

    tenant_id: str = "default"
    user_id: str
    agent_id: str = "main"
    memory_id: str | None = None
    query: str | None = None
    limit: int = Field(default=5, ge=1, le=20)


class ForgetCandidate(BaseModel):
    """Candidate memory row returned when delete intent is ambiguous."""

    memory_id: str
    text: str
    category: str
    score: float


class ForgetResponse(BaseModel):
    """Response payload for memory forget operations."""

    action: Literal["deleted", "candidates", "not_found", "missing_param"]
    memory_id: str | None = None
    found: int | None = None
    candidates: list[ForgetCandidate] = Field(default_factory=list)


class ReembedRequest(BaseModel):
    """Admin request payload for shadow re-embedding operations."""

    target_model_id: str
    dry_run: bool = False
    limit: int = Field(default=10000, ge=1, le=100000)


class ReembedResponse(BaseModel):
    """Admin response payload for re-embedding operations."""

    target_model_id: str
    processed: int
    dry_run: bool
    shadow_table: str | None = None
