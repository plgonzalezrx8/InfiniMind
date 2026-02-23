"""Memory-domain schemas used by storage and retrieval layers."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class MemoryScope(StrEnum):
    """Supported visibility scopes for stored memory."""

    GLOBAL = "global"
    USER = "user"
    CHANNEL = "channel"
    SESSION = "session"


class MemorySensitivity(StrEnum):
    """Sensitivity levels used by policy filters."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


MemoryCategory = Literal["preference", "fact", "decision", "entity", "other"]
VerificationStatus = Literal["unverified", "verified", "contradicted"]


class MemoryProvenance(BaseModel):
    """Source attribution stored with each memory row."""

    source_type: Literal["chat", "tool", "file", "web", "user_explicit"] = "chat"
    source_ref: str | None = None


class MemoryQuality(BaseModel):
    """Quality signals used for reranking and conflict handling."""

    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    verification_status: VerificationStatus = "unverified"
    conflict_set: list[str] = Field(default_factory=list)


class MemoryRecord(BaseModel):
    """Canonical memory object persisted in LanceDB."""

    memory_id: str = Field(default_factory=lambda: str(uuid4()))
    schema_version: int = 2
    tenant_id: str = "default"
    user_id: str
    agent_id: str = "main"
    text: str = Field(min_length=1)
    category: MemoryCategory = "other"
    tags: list[str] = Field(default_factory=list)
    importance: float = Field(default=0.7, ge=0.0, le=1.0)
    scope: MemoryScope = MemoryScope.USER
    sensitivity: MemorySensitivity = MemorySensitivity.LOW
    source_channel: str | None = None
    source_session: str | None = None
    source_actor: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    ttl_expires_at: str | None = None
    embedding_model_id: str
    content_hash: str
    dedupe_key: str | None = None
    provenance: MemoryProvenance = Field(default_factory=MemoryProvenance)
    quality: MemoryQuality = Field(default_factory=MemoryQuality)
    vector: list[float]



def compute_content_hash(text: str) -> str:
    """Return a stable SHA-256 digest used for dedupe and traceability."""

    return sha256(text.encode("utf-8")).hexdigest()
