"""LanceDB-backed storage layer for InfiniMind memory records."""

from __future__ import annotations

import importlib
import json
import logging
import math
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .memory_schema import MemoryRecord

LOGGER = logging.getLogger(__name__)
TABLE_NAME = "memories_v3"
LEGACY_TABLE_NAME = "memories_v2"
MIGRATION_BATCH_SIZE = 10_000


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
        self._in_memory_mode = False
        self._rows: list[dict[str, Any]] = []
        self._shadow_tables: dict[str, list[dict[str, Any]]] = {}

    @property
    def db_path(self) -> Path:
        """Expose the resolved data path for diagnostics."""

        return self._db_path

    def ensure_initialized(self) -> None:
        """Create/open LanceDB table and install indexes if missing."""

        if self._table is not None or self._in_memory_mode:
            return

        try:
            lancedb = importlib.import_module("lancedb")
        except Exception as exc:  # pragma: no cover - environment specific fallback
            LOGGER.warning("Falling back to in-memory store because LanceDB import failed: %s", exc)
            self._in_memory_mode = True
            return
        self._db_path.mkdir(parents=True, exist_ok=True)
        try:
            self._db = lancedb.connect(str(self._db_path))
        except Exception as exc:  # pragma: no cover - environment specific fallback
            LOGGER.warning("Falling back to in-memory store because LanceDB init failed: %s", exc)
            self._in_memory_mode = True
            return

        table_names = set(self._db.table_names())
        if TABLE_NAME in table_names:
            self._table = self._db.open_table(TABLE_NAME)
        elif LEGACY_TABLE_NAME in table_names:
            self._table = self._migrate_v2_to_v3()
        else:
            # We bootstrap schema with a sentinel row and delete it immediately.
            sentinel = self._bootstrap_row_v3()
            self._table = self._db.create_table(TABLE_NAME, data=[sentinel])
            self._table.delete("memory_id = '__schema__'")

        self._create_indexes()

    def _bootstrap_row_v3(self) -> dict[str, Any]:
        """Return a sentinel row that defines the current schema shape."""

        return {
            "memory_id": "__schema__",
            "schema_version": 3,
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
            "metadata_json": "{}",
            "provenance_source_type": "chat",
            "provenance_source_ref": None,
            "quality_confidence": 0.0,
            "quality_verification_status": "unverified",
            "quality_conflict_set_json": "[]",
            "vector": [0.0 for _ in range(self._vector_dim)],
        }

    def _query_results_to_rows(self, query: Any) -> list[dict[str, Any]]:
        """Convert LanceDB query results into plain row dicts across API versions."""

        to_list = getattr(query, "to_list", None)
        if callable(to_list):
            return self._payload_to_rows(to_list())

        to_arrow = getattr(query, "to_arrow", None)
        if callable(to_arrow):
            return self._payload_to_rows(to_arrow())

        return []

    def _payload_to_rows(self, payload: Any) -> list[dict[str, Any]]:
        """Convert common table/query payload types into row dictionaries.

        LanceDB and its dependencies may return result payloads as list-like
        objects, Arrow tables, or pandas DataFrames depending on version. This
        helper normalizes those variants to a single row-list shape.
        """

        if payload is None:
            return []
        if isinstance(payload, list):
            return [dict(row) for row in payload]

        to_pylist = getattr(payload, "to_pylist", None)
        if callable(to_pylist):
            return [dict(row) for row in to_pylist()]

        to_dict = getattr(payload, "to_dict", None)
        if callable(to_dict):
            try:
                rows = to_dict("records")
            except TypeError:
                rows = to_dict()
            if isinstance(rows, list):
                return [dict(row) for row in rows]

        return []

    def _table_scan_rows(self, table: Any, *, limit: int | None) -> list[dict[str, Any]]:
        """Read rows from a table using version-safe, non-query scan methods.

        We intentionally avoid relying on `search()` for full scans because some
        LanceDB variants require a query vector. The method order below prefers
        stable table-export paths and only uses query APIs as a last resort.
        """

        scan_methods = ("to_arrow", "to_pandas", "to_list")
        for method_name in scan_methods:
            method = getattr(table, method_name, None)
            if not callable(method):
                continue

            payload = None
            try:
                payload = method() if limit is None else method(limit=limit)
            except TypeError:
                # Some builds accept no keyword args; retry without `limit`.
                try:
                    payload = method()
                except Exception as exc:  # pragma: no cover - backend capability variation
                    LOGGER.debug("Skipping table scan method %s: %s", method_name, exc)
                    continue
            except Exception as exc:  # pragma: no cover - backend capability variation
                LOGGER.debug("Skipping table scan method %s: %s", method_name, exc)
                continue

            rows = self._payload_to_rows(payload)
            return rows if limit is None else rows[:limit]

        search = getattr(table, "search", None)
        if callable(search):
            try:
                query = search()
                limiter = getattr(query, "limit", None)
                if callable(limiter) and limit is not None:
                    query = limiter(limit)
                rows = self._query_results_to_rows(query)
                return rows if limit is None else rows[:limit]
            except Exception as exc:  # pragma: no cover - backend capability variation
                LOGGER.debug("Search-based scan fallback failed: %s", exc)

        return []

    def _iter_table_rows(self, table: Any, *, batch_size: int) -> Any:
        """Yield table rows in batches using the most stable available scan path.

        We prefer scanner/batch APIs to avoid materializing large tables in memory
        during migration. If batch APIs are unavailable, we degrade to a full scan
        and slice in Python.
        """

        scanner_factory = getattr(table, "scanner", None)
        if callable(scanner_factory):
            try:
                scanner = scanner_factory(batch_size=batch_size)
            except TypeError:
                scanner = scanner_factory()
            except Exception as exc:  # pragma: no cover - backend capability variation
                LOGGER.debug("Scanner-based row iteration unavailable: %s", exc)
                scanner = None

            if scanner is not None:
                to_batches = getattr(scanner, "to_batches", None)
                if callable(to_batches):
                    try:
                        for batch in to_batches():
                            rows = self._payload_to_rows(batch)
                            if rows:
                                yield rows
                        return
                    except Exception as exc:  # pragma: no cover - backend capability variation
                        LOGGER.debug("Scanner to_batches iteration failed: %s", exc)

        to_arrow = getattr(table, "to_arrow", None)
        if callable(to_arrow):
            try:
                arrow_payload = to_arrow()
                to_batches = getattr(arrow_payload, "to_batches", None)
                if callable(to_batches):
                    try:
                        batches = to_batches(max_chunksize=batch_size)
                    except TypeError:
                        batches = to_batches()
                    for batch in batches:
                        rows = self._payload_to_rows(batch)
                        if rows:
                            yield rows
                    return
            except Exception as exc:  # pragma: no cover - backend capability variation
                LOGGER.debug("Arrow batch iteration failed: %s", exc)

        # Final fallback: materialize once and chunk in Python.
        rows = self._table_scan_rows(table, limit=None)
        for start in range(0, len(rows), batch_size):
            chunk = rows[start : start + batch_size]
            if chunk:
                yield chunk

    def _migrate_v2_to_v3(self):
        """Create a v3 table from v2 rows and keep legacy table untouched.

        Migration is intentionally additive:
        - `memories_v2` remains present for rollback/debug.
        - data is copied in deterministic batches to avoid one giant write.
        - source and destination counts must match before we declare success.
        """

        assert self._db is not None
        legacy_table = self._db.open_table(LEGACY_TABLE_NAME)
        count_rows = getattr(legacy_table, "count_rows", None)
        expected_source_count: int | None = None
        if callable(count_rows):
            try:
                expected_source_count = int(count_rows())
            except Exception:  # pragma: no cover - backend capability variation
                expected_source_count = None

        source_count = 0
        migrated_count = 0
        batch_count = 0
        table = None
        for chunk in self._iter_table_rows(legacy_table, batch_size=MIGRATION_BATCH_SIZE):
            batch_count += 1
            source_count += len(chunk)
            migrated_rows = []
            for row in chunk:
                copied = dict(row)
                copied["schema_version"] = 3
                copied["metadata_json"] = copied.get("metadata_json") or "{}"
                migrated_rows.append(copied)

            if table is None:
                table = self._db.create_table(TABLE_NAME, data=migrated_rows)
            else:
                table.add(migrated_rows)
            migrated_count += len(migrated_rows)

        if source_count == 0:
            table = self._db.create_table(TABLE_NAME, data=[self._bootstrap_row_v3()])
            table.delete("memory_id = '__schema__'")
            LOGGER.info("Migrated %s -> %s with 0 rows (empty legacy table)", LEGACY_TABLE_NAME, TABLE_NAME)
            return table

        if table is None or migrated_count != source_count:
            raise RuntimeError(
                f"v2->v3 migration row-count mismatch: source={source_count} migrated={migrated_count}"
            )
        if expected_source_count is not None and source_count != expected_source_count:
            raise RuntimeError(
                "v2->v3 migration scan mismatch: "
                f"count_rows={expected_source_count} scanned={source_count} migrated={migrated_count}"
            )

        LOGGER.info(
            "Migrated %s -> %s rows: %s across %s batches (batch size: %s)",
            LEGACY_TABLE_NAME,
            TABLE_NAME,
            migrated_count,
            batch_count,
            MIGRATION_BATCH_SIZE,
        )
        return table

    def is_ready(self) -> bool:
        """Return true once the underlying table is fully initialized."""

        return self._table is not None or self._in_memory_mode

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
            "metadata_json": json.dumps(record.metadata),
            "provenance_source_type": record.provenance.source_type,
            "provenance_source_ref": record.provenance.source_ref,
            "quality_confidence": record.quality.confidence,
            "quality_verification_status": record.quality.verification_status,
            "quality_conflict_set_json": json.dumps(record.quality.conflict_set),
            "vector": record.vector,
        }
        if self._in_memory_mode:
            self._rows.append(row)
            return record

        assert self._table is not None
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

        # Dedupe is correctness-critical: scan full scoped data to avoid false negatives.
        rows = self.list_all_memories()
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
        if self._in_memory_mode:
            return self._rows[:limit]

        assert self._table is not None

        # Full-table scans use table-native export methods first for compatibility.
        return self._table_scan_rows(self._table, limit=limit)

    def list_all_memories(self) -> list[dict[str, Any]]:
        """Return all rows for correctness-sensitive operations.

        Use this only when truncation would be a behavioral bug (for example,
        dedupe checks or scoped deletes).
        """

        self.ensure_initialized()
        if self._in_memory_mode:
            return list(self._rows)

        assert self._table is not None
        return self._table_scan_rows(self._table, limit=None)

    def vector_search(self, query_vector: list[float], limit: int = 20) -> list[dict[str, Any]]:
        """Run approximate vector similarity search against stored rows."""

        self.ensure_initialized()
        if self._in_memory_mode:
            scored: list[tuple[float, dict[str, Any]]] = []
            q_norm = math.sqrt(sum(value * value for value in query_vector)) or 1.0
            for row in self._rows:
                row_vec = [float(value) for value in row.get("vector", [])]
                if len(row_vec) != len(query_vector):
                    continue
                dot = sum(a * b for a, b in zip(query_vector, row_vec, strict=False))
                row_norm = math.sqrt(sum(value * value for value in row_vec)) or 1.0
                score = (dot / (q_norm * row_norm) + 1.0) / 2.0
                candidate = dict(row)
                candidate["_distance"] = 1.0 - score
                scored.append((score, candidate))

            scored.sort(key=lambda item: item[0], reverse=True)
            return [row for _, row in scored[:limit]]

        assert self._table is not None

        return self._query_results_to_rows(self._table.search(query_vector).limit(limit))

    def write_shadow_embeddings(
        self,
        *,
        target_model_id: str,
        rows: list[dict[str, Any]],
        vectors: list[list[float]],
    ) -> str | None:
        """Write shadow embeddings to a separate table for safe migrations."""

        self.ensure_initialized()
        safe_model = re.sub(r"[^a-zA-Z0-9]+", "_", target_model_id).strip("_").lower() or "model"
        suffix = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        table_name = f"memories_shadow_{safe_model}_{suffix}"

        shadow_rows: list[dict[str, Any]] = []
        for row, vector in zip(rows, vectors, strict=False):
            copied = dict(row)
            copied["source_embedding_model_id"] = row.get("embedding_model_id")
            copied["embedding_model_id"] = target_model_id
            copied["vector"] = vector
            shadow_rows.append(copied)

        if not shadow_rows:
            return None

        if self._in_memory_mode:
            self._shadow_tables[table_name] = shadow_rows
            return table_name

        assert self._db is not None
        self._db.create_table(table_name, data=shadow_rows)
        return table_name

    def scoped_memories(
        self,
        *,
        tenant_id: str,
        user_id: str,
        agent_id: str,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Return rows constrained to one tenant/user/agent boundary."""

        rows = self.list_all_memories() if limit is None else self.list_memories(limit=limit)
        return [
            row
            for row in rows
            if row.get("tenant_id") == tenant_id
            and row.get("user_id") == user_id
            and row.get("agent_id") == agent_id
        ]

    def find_scoped_memory_by_id(
        self,
        *,
        tenant_id: str,
        user_id: str,
        agent_id: str,
        memory_id: str,
    ) -> dict[str, Any] | None:
        """Find a single memory row within one tenant/user/agent boundary."""

        for row in self.scoped_memories(tenant_id=tenant_id, user_id=user_id, agent_id=agent_id, limit=None):
            if str(row.get("memory_id")) == memory_id:
                return row
        return None

    def delete_memory(self, *, tenant_id: str, user_id: str, agent_id: str, memory_id: str) -> bool:
        """Delete one scoped memory row and return whether a row was removed."""

        self.ensure_initialized()
        match = self.find_scoped_memory_by_id(
            tenant_id=tenant_id,
            user_id=user_id,
            agent_id=agent_id,
            memory_id=memory_id,
        )
        if match is None:
            return False

        if self._in_memory_mode:
            self._rows = [
                row
                for row in self._rows
                if not (
                    str(row.get("memory_id")) == memory_id
                    and row.get("tenant_id") == tenant_id
                    and row.get("user_id") == user_id
                    and row.get("agent_id") == agent_id
                )
            ]
            return True

        assert self._table is not None
        # Escape single quotes to keep filter expression safe for the current SQL-like API.
        safe_memory_id = memory_id.replace("'", "''")
        safe_tenant_id = tenant_id.replace("'", "''")
        safe_user_id = user_id.replace("'", "''")
        safe_agent_id = agent_id.replace("'", "''")
        self._table.delete(
            " and ".join(
                [
                    f"memory_id = '{safe_memory_id}'",
                    f"tenant_id = '{safe_tenant_id}'",
                    f"user_id = '{safe_user_id}'",
                    f"agent_id = '{safe_agent_id}'",
                ]
            )
        )
        return True
