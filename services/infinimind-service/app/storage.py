"""LanceDB-backed storage layer for InfiniMind memory records."""

from __future__ import annotations

import importlib
import json
import logging
from pathlib import Path
from typing import Any

from .memory_schema import MemoryRecord

LOGGER = logging.getLogger(__name__)
TABLE_NAME = "memories_v2"


class LanceMemoryStore:
    """Persistence abstraction around a single LanceDB table.

    The store initializes lazily to keep startup robust in constrained
    environments while still exposing explicit readiness checks.
    """

    def __init__(self, db_path: Path, vector_dim: int) -> None:
        self._db_path = Path(db_path)
        self._vector_dim = vector_dim
        self._db = None
        self._table = None

    @property
    def db_path(self) -> Path:
        """Expose the resolved data path for diagnostics."""

        return self._db_path

    def ensure_initialized(self) -> None:
        """Create/open LanceDB table and install indexes if missing."""

        if self._table is not None:
            return

        lancedb = importlib.import_module("lancedb")
        self._db_path.mkdir(parents=True, exist_ok=True)
        self._db = lancedb.connect(str(self._db_path))

        table_names = set(self._db.table_names())
        if TABLE_NAME in table_names:
            self._table = self._db.open_table(TABLE_NAME)
        else:
            # We bootstrap schema with a sentinel row and delete it immediately.
            sentinel = {
                "memory_id": "__schema__",
                "schema_version": 2,
                "tenant_id": "default",
                "user_id": "default",
                "agent_id": "main",
                "text": "",
                "category": "other",
                "tags_json": "[]",
                "importance": 0.0,
                "scope": "user",
                "sensitivity": "low",
                "source_channel": None,
                "source_session": None,
                "source_actor": None,
                "created_at": "1970-01-01T00:00:00+00:00",
                "updated_at": "1970-01-01T00:00:00+00:00",
                "ttl_expires_at": None,
                "embedding_model_id": "bootstrap",
                "content_hash": "bootstrap",
                "dedupe_key": None,
                "provenance_source_type": "chat",
                "provenance_source_ref": None,
                "quality_confidence": 0.0,
                "quality_verification_status": "unverified",
                "quality_conflict_set_json": "[]",
                "vector": [0.0 for _ in range(self._vector_dim)],
            }
            self._table = self._db.create_table(TABLE_NAME, data=[sentinel])
            self._table.delete("memory_id = '__schema__'")

        self._create_indexes()

    def is_ready(self) -> bool:
        """Return true once the underlying table is fully initialized."""

        return self._table is not None

    def _create_indexes(self) -> None:
        """Create scalar/text indexes best-effort to preserve boot reliability."""

        if self._table is None:
            return

        scalar_fields = [
            "tenant_id",
            "user_id",
            "agent_id",
            "scope",
            "sensitivity",
            "category",
            "created_at",
            "ttl_expires_at",
            "content_hash",
            "dedupe_key",
        ]

        create_scalar_index = getattr(self._table, "create_scalar_index", None)
        if callable(create_scalar_index):
            for field in scalar_fields:
                try:
                    create_scalar_index(field)
                except Exception as exc:  # pragma: no cover - backend capability variation
                    LOGGER.debug("Skipping scalar index for %s: %s", field, exc)

        create_fts_index = getattr(self._table, "create_fts_index", None)
        if callable(create_fts_index):
            try:
                create_fts_index("text")
            except Exception as exc:  # pragma: no cover - backend capability variation
                LOGGER.debug("Skipping FTS index creation: %s", exc)

    def store_memory(self, record: MemoryRecord) -> MemoryRecord:
        """Persist one memory record and return the persisted object."""

        self.ensure_initialized()
        assert self._table is not None

        row = {
            "memory_id": record.memory_id,
            "schema_version": record.schema_version,
            "tenant_id": record.tenant_id,
            "user_id": record.user_id,
            "agent_id": record.agent_id,
            "text": record.text,
            "category": record.category,
            "tags_json": json.dumps(record.tags),
            "importance": record.importance,
            "scope": record.scope.value,
            "sensitivity": record.sensitivity.value,
            "source_channel": record.source_channel,
            "source_session": record.source_session,
            "source_actor": record.source_actor,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "ttl_expires_at": record.ttl_expires_at,
            "embedding_model_id": record.embedding_model_id,
            "content_hash": record.content_hash,
            "dedupe_key": record.dedupe_key,
            "provenance_source_type": record.provenance.source_type,
            "provenance_source_ref": record.provenance.source_ref,
            "quality_confidence": record.quality.confidence,
            "quality_verification_status": record.quality.verification_status,
            "quality_conflict_set_json": json.dumps(record.quality.conflict_set),
            "vector": record.vector,
        }
        self._table.add([row])
        return record

    def find_duplicate(
        self,
        *,
        tenant_id: str,
        user_id: str,
        agent_id: str,
        content_hash: str,
        dedupe_key: str | None,
    ) -> dict[str, Any] | None:
        """Find an existing row that matches dedupe constraints."""

        rows = self.list_memories(limit=5000)
        for row in rows:
            if row.get("tenant_id") != tenant_id:
                continue
            if row.get("user_id") != user_id:
                continue
            if row.get("agent_id") != agent_id:
                continue
            if dedupe_key and row.get("dedupe_key") == dedupe_key:
                return row
            if row.get("content_hash") == content_hash:
                return row
        return None

    def list_memories(self, limit: int = 5000) -> list[dict[str, Any]]:
        """Return raw rows for retrieval and maintenance workflows."""

        self.ensure_initialized()
        assert self._table is not None

        # to_list exists on recent LanceDB builds. We keep a fallback path for
        # compatibility with older variants.
        query = self._table.search().limit(limit)
        to_list = getattr(query, "to_list", None)
        if callable(to_list):
            return to_list()

        to_arrow = getattr(query, "to_arrow", None)
        if callable(to_arrow):
            return to_arrow().to_pylist()

        return []

    def vector_search(self, query_vector: list[float], limit: int = 20) -> list[dict[str, Any]]:
        """Run approximate vector similarity search against stored rows."""

        self.ensure_initialized()
        assert self._table is not None

        query = self._table.search(query_vector).limit(limit)
        to_list = getattr(query, "to_list", None)
        if callable(to_list):
            return to_list()

        to_arrow = getattr(query, "to_arrow", None)
        if callable(to_arrow):
            return to_arrow().to_pylist()

        return []
