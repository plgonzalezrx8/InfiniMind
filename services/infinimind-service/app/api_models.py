"""HTTP request/response models for memory APIs."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, Field

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
