"""LanceDB-backed storage layer for InfiniMind memory records."""

from __future__ import annotations

import importlib
import json
import logging
import math
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from .memory_schema import MemoryRecord

LOGGER = logging.getLogger(__name__)
TABLE_NAME = "memories_v3"
LEGACY_TABLE_NAME = "memories_v2"
MIGRATION_BATCH_SIZE = 10_000
SCHEMA_FIX_BACKUP_TABLE_NAME = f"{TABLE_NAME}__schema_fix_backup"
SIMILARITY_DEDUPE_THRESHOLD = 0.92

# These fields are semantically optional strings. If the bootstrap row uses
# nulls, Lance/Arrow can infer a `null`-typed column that rejects later strings.
OPTIONAL_STRING_FIELDS = (
    "source_channel",
    "source_session",
    "source_actor",
    "ttl_expires_at",
    "dedupe_key",
    "provenance_source_ref",
)


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

        # Self-heal legacy/null-inferred optional columns before accepting writes.
        self._repair_null_typed_optional_columns()
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
            # Optional text fields intentionally use empty strings in the
            # sentinel row so Arrow infers `string` instead of `null`.
            "source_channel": "",
            "source_session": "",
            "source_actor": "",
            "created_at": "1970-01-01T00:00:00+00:00",
            "updated_at": "1970-01-01T00:00:00+00:00",
            "ttl_expires_at": "",
            "embedding_model_id": "bootstrap",
            "content_hash": "bootstrap",
            "dedupe_key": "",
            "metadata_json": "{}",
            "provenance_source_type": "chat",
            "provenance_source_ref": "",
            "quality_confidence": 0.0,
            "quality_verification_status": "unverified",
            "quality_conflict_set_json": "[]",
            "vector": [0.0 for _ in range(self._vector_dim)],
        }

    def _detect_null_typed_optional_fields(self) -> list[str]:
        """Return optional string fields currently typed as Arrow `null`.

        A `null` column accepts only null values, which causes runtime 500s when
        callers provide valid strings (for example channel_id on memory_store).
        """

        if self._table is None:
            return []
        schema = getattr(self._table, "schema", None)
        if schema is None:
            return []

        null_typed: list[str] = []
        for field in schema:
            if field.name in OPTIONAL_STRING_FIELDS and str(field.type) == "null":
                null_typed.append(field.name)
        return null_typed

    def _repair_null_typed_optional_columns(self) -> None:
        """Rebuild table schema when optional string columns were inferred as null.

        The repair is deterministic and preserves rows:
        1) snapshot current rows into a backup table,
        2) recreate the active table with corrected inferred types,
        3) reinsert rows in deterministic batches.
        """

        if self._table is None or self._db is None:
            return
        null_typed_fields = self._detect_null_typed_optional_fields()
        if len(null_typed_fields) == 0:
            return

        LOGGER.warning(
            "Repairing null-typed optional columns in %s: %s",
            TABLE_NAME,
            ", ".join(sorted(null_typed_fields)),
        )

        source_rows = self._table_scan_rows(self._table, limit=None)
        self._db.drop_table(SCHEMA_FIX_BACKUP_TABLE_NAME, ignore_missing=True)

        # Persist a full backup snapshot before replacing the active table.
        if len(source_rows) > 0:
            self._db.create_table(SCHEMA_FIX_BACKUP_TABLE_NAME, data=source_rows, mode="overwrite")

        try:
            # Recreate the active table with corrected inferred types.
            repaired_table = self._db.create_table(TABLE_NAME, data=[self._bootstrap_row_v3()], mode="overwrite")
            repaired_table.delete("memory_id = '__schema__'")
            if len(source_rows) > 0:
                for start in range(0, len(source_rows), MIGRATION_BATCH_SIZE):
                    batch = source_rows[start : start + MIGRATION_BATCH_SIZE]
                    repaired_table.add(batch)
        except Exception:
            # If rebuild fails, restore original rows so service availability wins.
            if len(source_rows) > 0:
                self._db.create_table(TABLE_NAME, data=source_rows, mode="overwrite")
            raise

        self._table = self._db.open_table(TABLE_NAME)
        LOGGER.info(
            "Schema repair complete for %s; backup preserved as %s",
            TABLE_NAME,
            SCHEMA_FIX_BACKUP_TABLE_NAME,
        )

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
                # When available, use backend-reported counts to detect partial scans.
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

    def _record_to_row(self, record: MemoryRecord) -> dict[str, Any]:
        """Convert a validated memory model into the Lance row payload."""

        return {
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

    def _coerce_vector(self, vector_obj: Any) -> list[float]:
        """Normalize vector payloads from DB backends into plain float lists."""

        if vector_obj is None:
            return []
        if isinstance(vector_obj, list):
            return [float(value) for value in vector_obj]
        if hasattr(vector_obj, "tolist"):
            return [float(value) for value in vector_obj.tolist()]
        try:
            return [float(value) for value in vector_obj]
        except TypeError:
            return []

    def _safe_parse_json_list(self, value: Any, *, memory_id: str, field_name: str) -> list[str]:
        """Parse list-like JSON fields safely so malformed legacy rows do not break writes."""

        try:
            payload = json.loads(value or "[]")
        except Exception:
            LOGGER.warning("Invalid %s for memory_id=%s; defaulting to empty list", field_name, memory_id)
            return []
        if isinstance(payload, list):
            return [str(item) for item in payload]
        LOGGER.warning("Invalid %s type for memory_id=%s; defaulting to empty list", field_name, memory_id)
        return []

    def _safe_parse_json_object(self, value: Any, *, memory_id: str, field_name: str) -> dict[str, Any]:
        """Parse object-like JSON fields safely so malformed legacy rows do not break writes."""

        try:
            payload = json.loads(value or "{}")
        except Exception:
            LOGGER.warning("Invalid %s for memory_id=%s; defaulting to empty object", field_name, memory_id)
            return {}
        if isinstance(payload, dict):
            return dict(payload)
        LOGGER.warning("Invalid %s type for memory_id=%s; defaulting to empty object", field_name, memory_id)
        return {}

    def _parse_iso_timestamp(self, value: str | None) -> datetime | None:
        """Parse ISO timestamps for merge precedence decisions."""

        if not value:
            return None
        normalized = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            return None

    def _latest_non_null_timestamp(self, left: str | None, right: str | None) -> str | None:
        """Return the later timestamp when both are parseable, else favor incoming non-null values."""

        if left is None:
            return right
        if right is None:
            return left

        left_dt = self._parse_iso_timestamp(left)
        right_dt = self._parse_iso_timestamp(right)
        if left_dt is not None and right_dt is not None:
            return left if left_dt >= right_dt else right
        # When parsing fails, prefer the incoming value to keep last-write-wins behavior.
        return right

    def _scoped_row_filter(self, *, tenant_id: str, user_id: str, agent_id: str, memory_id: str) -> str:
        """Build a safe scoped row filter expression for LanceDB delete/replace paths."""

        safe_memory_id = memory_id.replace("'", "''")
        safe_tenant_id = tenant_id.replace("'", "''")
        safe_user_id = user_id.replace("'", "''")
        safe_agent_id = agent_id.replace("'", "''")
        return " and ".join(
            [
                f"memory_id = '{safe_memory_id}'",
                f"tenant_id = '{safe_tenant_id}'",
                f"user_id = '{safe_user_id}'",
                f"agent_id = '{safe_agent_id}'",
            ]
        )

    def _cosine_similarity(self, left: list[float], right: list[float]) -> float | None:
        """Compute cosine similarity for same-length vectors, or return None when invalid."""

        if len(left) == 0 or len(left) != len(right):
            return None

        left_norm = math.sqrt(sum(value * value for value in left))
        right_norm = math.sqrt(sum(value * value for value in right))
        if left_norm == 0.0 or right_norm == 0.0:
            return None

        dot = sum(a * b for a, b in zip(left, right, strict=False))
        return dot / (left_norm * right_norm)

    def store_memory(self, record: MemoryRecord) -> MemoryRecord:
        """Persist one memory record and return the persisted object."""

        self.ensure_initialized()
        row = self._record_to_row(record)
        if self._in_memory_mode:
            self._rows.append(row)
            return record

        assert self._table is not None
        self._table.add([row])
        return record

    def find_exact_duplicate(
        self,
        *,
        tenant_id: str,
        user_id: str,
        agent_id: str,
        content_hash: str,
        dedupe_key: str | None,
    ) -> dict[str, Any] | None:
        """Find scoped exact duplicates by dedupe key or content hash."""

        # Exact dedupe is correctness-critical: scan full scope to avoid false negatives.
        rows = self.scoped_memories(tenant_id=tenant_id, user_id=user_id, agent_id=agent_id, limit=None)
        for row in rows:
            if dedupe_key and row.get("dedupe_key") == dedupe_key:
                return row
            if row.get("content_hash") == content_hash:
                return row
        return None

    def find_similarity_duplicate(
        self,
        *,
        tenant_id: str,
        user_id: str,
        agent_id: str,
        query_vector: list[float],
        cosine_threshold: float = SIMILARITY_DEDUPE_THRESHOLD,
    ) -> tuple[dict[str, Any] | None, float | None]:
        """Find the highest-scoring scoped cosine match above the dedupe threshold."""

        best_row: dict[str, Any] | None = None
        best_score = cosine_threshold
        best_memory_id = ""

        for row in self.scoped_memories(tenant_id=tenant_id, user_id=user_id, agent_id=agent_id, limit=None):
            row_vector = self._coerce_vector(row.get("vector"))
            cosine = self._cosine_similarity(query_vector, row_vector)
            if cosine is None or cosine <= cosine_threshold:
                continue

            row_memory_id = str(row.get("memory_id") or "")
            if cosine > best_score:
                best_row = row
                best_score = cosine
                best_memory_id = row_memory_id
                continue

            # Tie-breaking keeps behavior deterministic across backend row-order variants.
            if math.isclose(cosine, best_score, abs_tol=1e-9) and row_memory_id < best_memory_id:
                best_row = row
                best_score = cosine
                best_memory_id = row_memory_id

        return best_row, (best_score if best_row is not None else None)

    def find_merge_candidate(
        self,
        *,
        tenant_id: str,
        user_id: str,
        agent_id: str,
        content_hash: str,
        dedupe_key: str | None,
        query_vector: list[float] | None = None,
        cosine_threshold: float = SIMILARITY_DEDUPE_THRESHOLD,
    ) -> tuple[dict[str, Any] | None, Literal["exact", "similarity"] | None, float | None]:
        """Find merge candidates with exact-match precedence over semantic similarity."""

        exact_match = self.find_exact_duplicate(
            tenant_id=tenant_id,
            user_id=user_id,
            agent_id=agent_id,
            content_hash=content_hash,
            dedupe_key=dedupe_key,
        )
        if exact_match is not None:
            return exact_match, "exact", 1.0

        if query_vector:
            similarity_match, cosine = self.find_similarity_duplicate(
                tenant_id=tenant_id,
                user_id=user_id,
                agent_id=agent_id,
                query_vector=query_vector,
                cosine_threshold=cosine_threshold,
            )
            if similarity_match is not None:
                return similarity_match, "similarity", cosine

        return None, None, None

    def merge_memory(self, *, existing_row: dict[str, Any], incoming_record: MemoryRecord) -> dict[str, Any]:
        """Merge incoming data into an existing canonical row and persist replacement."""

        self.ensure_initialized()
        existing_memory_id = str(existing_row.get("memory_id") or incoming_record.memory_id)
        existing_tags = self._safe_parse_json_list(
            existing_row.get("tags_json"),
            memory_id=existing_memory_id,
            field_name="tags_json",
        )
        existing_metadata = self._safe_parse_json_object(
            existing_row.get("metadata_json"),
            memory_id=existing_memory_id,
            field_name="metadata_json",
        )

        # Merge policy is explicit so dedupe behavior remains deterministic over time.
        merged_tags: list[str] = []
        seen_tags: set[str] = set()
        for tag in existing_tags + [str(tag) for tag in incoming_record.tags]:
            if tag in seen_tags:
                continue
            seen_tags.add(tag)
            merged_tags.append(tag)

        merged_metadata = dict(existing_metadata)
        merged_metadata.update(incoming_record.metadata)

        try:
            existing_importance = float(existing_row.get("importance") or 0.0)
        except (TypeError, ValueError):
            existing_importance = 0.0

        existing_schema_version = incoming_record.schema_version
        try:
            existing_schema_version = int(existing_row.get("schema_version"))
        except (TypeError, ValueError):
            existing_schema_version = incoming_record.schema_version

        merged_row = dict(existing_row)
        merged_row.update(
            {
                "memory_id": existing_memory_id,
                "schema_version": existing_schema_version,
                "tenant_id": str(existing_row.get("tenant_id") or incoming_record.tenant_id),
                "user_id": str(existing_row.get("user_id") or incoming_record.user_id),
                "agent_id": str(existing_row.get("agent_id") or incoming_record.agent_id),
                "text": incoming_record.text,
                "category": incoming_record.category,
                "tags_json": json.dumps(merged_tags),
                "importance": max(existing_importance, float(incoming_record.importance)),
                "scope": incoming_record.scope.value,
                "sensitivity": incoming_record.sensitivity.value,
                "source_channel": incoming_record.source_channel,
                "source_session": incoming_record.source_session,
                "source_actor": incoming_record.source_actor,
                "created_at": str(existing_row.get("created_at") or incoming_record.created_at),
                "updated_at": incoming_record.updated_at,
                "ttl_expires_at": self._latest_non_null_timestamp(
                    existing_row.get("ttl_expires_at"),
                    incoming_record.ttl_expires_at,
                ),
                "embedding_model_id": incoming_record.embedding_model_id,
                "content_hash": incoming_record.content_hash,
                "dedupe_key": incoming_record.dedupe_key or existing_row.get("dedupe_key"),
                "metadata_json": json.dumps(merged_metadata),
                "provenance_source_type": incoming_record.provenance.source_type,
                "provenance_source_ref": incoming_record.provenance.source_ref,
                "quality_confidence": incoming_record.quality.confidence,
                "quality_verification_status": incoming_record.quality.verification_status,
                "quality_conflict_set_json": json.dumps(incoming_record.quality.conflict_set),
                "vector": incoming_record.vector,
            }
        )

        tenant_id = str(merged_row.get("tenant_id") or incoming_record.tenant_id)
        user_id = str(merged_row.get("user_id") or incoming_record.user_id)
        agent_id = str(merged_row.get("agent_id") or incoming_record.agent_id)

        if self._in_memory_mode:
            for index, row in enumerate(self._rows):
                if (
                    str(row.get("memory_id")) == existing_memory_id
                    and row.get("tenant_id") == tenant_id
                    and row.get("user_id") == user_id
                    and row.get("agent_id") == agent_id
                ):
                    self._rows[index] = merged_row
                    return merged_row
            # If row lookup fails in-memory, append replacement to avoid data loss.
            self._rows.append(merged_row)
            return merged_row

        assert self._table is not None
        self._table.delete(
            self._scoped_row_filter(
                tenant_id=tenant_id,
                user_id=user_id,
                agent_id=agent_id,
                memory_id=existing_memory_id,
            )
        )
        self._table.add([merged_row])
        return merged_row

    def find_duplicate(
        self,
        *,
        tenant_id: str,
        user_id: str,
        agent_id: str,
        content_hash: str,
        dedupe_key: str | None,
    ) -> dict[str, Any] | None:
        """Backward-compatible exact dedupe helper retained for compatibility tests."""

        return self.find_exact_duplicate(
            tenant_id=tenant_id,
            user_id=user_id,
            agent_id=agent_id,
            content_hash=content_hash,
            dedupe_key=dedupe_key,
        )

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
        self._table.delete(
            self._scoped_row_filter(
                tenant_id=tenant_id,
                user_id=user_id,
                agent_id=agent_id,
                memory_id=memory_id,
            )
        )
        return True
