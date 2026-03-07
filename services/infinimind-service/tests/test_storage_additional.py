"""Additional storage coverage for compatibility helpers and in-memory paths."""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime

import pytest

from app.memory_schema import MemoryRecord
from app.storage import LanceMemoryStore


class _DictPayload:
    """Simple dataframe-like payload with `to_dict` support."""

    def __init__(self, rows):
        self._rows = rows

    def to_dict(self, orient=None):
        if orient == "records":
            return self._rows
        return {"records": self._rows}


class _ArrowPayload:
    """Arrow-like payload exposing `to_pylist` used by storage converters."""

    def __init__(self, rows):
        self._rows = rows

    def to_pylist(self):
        return self._rows


class _QueryToArrow:
    def __init__(self, rows):
        self._rows = rows

    def to_arrow(self):
        return _ArrowPayload(self._rows)


class _SearchOnlyTable:
    """Table with search-only scan support to exercise fallback paths."""

    def __init__(self, rows):
        self._rows = rows
        self.deleted = None

    def search(self, *_args, **_kwargs):
        return _QueryWithLimit(self._rows)

    def delete(self, expression: str):
        self.deleted = expression


class _QueryWithLimit:
    def __init__(self, rows):
        self._rows = rows
        self._limit = len(rows)

    def limit(self, limit):
        self._limit = limit
        return self

    def to_list(self):
        return self._rows[: self._limit]


class _VectorTable:
    def __init__(self, rows):
        self._rows = rows
        self.added = []

    def search(self, _query_vector):
        return _QueryWithLimit(self._rows)

    def add(self, rows):
        self.added.extend(rows)

    def delete(self, expression):
        # Keep tests deterministic without parsing expression semantics.
        self._rows = [row for row in self._rows if "memory_id = " not in expression or row.get("memory_id") not in expression]


class _DbRecorder:
    def __init__(self):
        self.created = {}

    def create_table(self, name, data):
        self.created[name] = list(data)


def _memory_record(**overrides):
    now = datetime.now(UTC).isoformat()
    payload = {
        "tenant_id": "default",
        "user_id": "user-1",
        "agent_id": "main",
        "text": "remember this",
        "category": "fact",
        "importance": 0.7,
        "scope": "user",
        "sensitivity": "low",
        "created_at": now,
        "updated_at": now,
        "ttl_expires_at": None,
        "embedding_model_id": "text-embedding-3-large",
        "content_hash": "hash-1",
        "vector": [0.1, 0.2, 0.3, 0.4],
        "tags": ["ops"],
        "metadata": {"source": "test"},
    }
    payload.update(overrides)
    return MemoryRecord(**payload)


def test_payload_and_query_conversion_helpers(tmp_path):
    """Storage helper conversions should handle list/arrow/dataframe variants."""

    store = LanceMemoryStore(db_path=tmp_path / "lancedb", vector_dim=4)
    rows = [{"memory_id": "m1"}]

    assert store._payload_to_rows(None) == []
    assert store._payload_to_rows(rows) == rows
    assert store._payload_to_rows(_ArrowPayload(rows)) == rows
    assert store._payload_to_rows(_DictPayload(rows)) == rows
    assert store._query_results_to_rows(_QueryToArrow(rows)) == rows


def test_table_scan_falls_back_to_search_and_scoped_delete_escapes_quotes(tmp_path):
    """Fallback table scan and scoped deletion should remain compatible and safe."""

    rows = [
        {"memory_id": "quoted'id", "tenant_id": "default", "user_id": "user-1", "agent_id": "main"},
        {"memory_id": "m2", "tenant_id": "default", "user_id": "other", "agent_id": "main"},
    ]
    store = LanceMemoryStore(db_path=tmp_path / "lancedb", vector_dim=4)
    store._table = _SearchOnlyTable(rows)
    scanned = store.list_memories(limit=1)
    assert scanned[0]["memory_id"] == "quoted'id"

    deleted = store.delete_memory(
        tenant_id="default",
        user_id="user-1",
        agent_id="main",
        memory_id="quoted'id",
    )
    assert deleted is True
    # Verify single-quote escaping in generated filter expression.
    assert "quoted''id" in store._table.deleted


def test_in_memory_store_vector_search_shadow_and_scoped_helpers(tmp_path):
    """In-memory mode should support core CRUD/search/shadow helper paths."""

    store = LanceMemoryStore(db_path=tmp_path / "lancedb", vector_dim=4)
    store._in_memory_mode = True
    one = store.store_memory(_memory_record(memory_id="m1", vector=[1.0, 0.0, 0.0, 0.0]))
    two = store.store_memory(_memory_record(memory_id="m2", vector=[0.0, 1.0, 0.0, 0.0], user_id="user-2"))
    assert one.memory_id == "m1"
    assert two.memory_id == "m2"

    all_rows = store.list_all_memories()
    assert len(all_rows) == 2
    assert store.find_duplicate(
        tenant_id="default",
        user_id="user-1",
        agent_id="main",
        content_hash="hash-1",
        dedupe_key=None,
    )

    scoped = store.scoped_memories(tenant_id="default", user_id="user-1", agent_id="main", limit=None)
    assert [row["memory_id"] for row in scoped] == ["m1"]
    assert store.find_scoped_memory_by_id(
        tenant_id="default",
        user_id="user-1",
        agent_id="main",
        memory_id="m1",
    )
    assert store.delete_memory(tenant_id="default", user_id="user-1", agent_id="main", memory_id="m1") is True
    assert store.delete_memory(tenant_id="default", user_id="user-1", agent_id="main", memory_id="missing") is False

    ranked = store.vector_search([0.0, 1.0, 0.0, 0.0], limit=1)
    assert len(ranked) == 1
    assert ranked[0]["memory_id"] == "m2"

    shadow_name = store.write_shadow_embeddings(
        target_model_id="text-embedding-3-small",
        rows=store.list_all_memories(),
        vectors=[[0.9, 0.8, 0.7, 0.6]],
    )
    assert shadow_name is not None
    assert shadow_name in store._shadow_tables
    assert store.write_shadow_embeddings(target_model_id="text-embedding-3-small", rows=[], vectors=[]) is None


def test_find_merge_candidate_supports_exact_similarity_and_boundary(tmp_path):
    """Merge candidate resolution should prefer exact, then similarity above strict threshold."""

    store = LanceMemoryStore(db_path=tmp_path / "lancedb", vector_dim=2)
    store._in_memory_mode = True
    store._rows = [
        {
            "memory_id": "exact-target",
            "tenant_id": "default",
            "user_id": "user-1",
            "agent_id": "main",
            "content_hash": "hash-1",
            "dedupe_key": "dedupe-key-1",
            "vector": [0.0, 1.0],
        },
        {
            "memory_id": "sim-b",
            "tenant_id": "default",
            "user_id": "user-1",
            "agent_id": "main",
            "content_hash": "hash-2",
            "dedupe_key": None,
            "vector": [1.0, 0.0],
        },
        {
            "memory_id": "sim-a",
            "tenant_id": "default",
            "user_id": "user-1",
            "agent_id": "main",
            "content_hash": "hash-3",
            "dedupe_key": None,
            "vector": [1.0, 0.0],
        },
        {
            # Same vector but different user should never participate in dedupe.
            "memory_id": "foreign",
            "tenant_id": "default",
            "user_id": "other-user",
            "agent_id": "main",
            "content_hash": "hash-foreign",
            "dedupe_key": None,
            "vector": [1.0, 0.0],
        },
    ]

    exact_row, exact_reason, exact_score = store.find_merge_candidate(
        tenant_id="default",
        user_id="user-1",
        agent_id="main",
        content_hash="hash-1",
        dedupe_key=None,
        query_vector=[0.93, math.sqrt(1 - 0.93**2)],
    )
    assert exact_row is not None
    assert exact_row["memory_id"] == "exact-target"
    assert exact_reason == "exact"
    assert exact_score == 1.0

    similarity_row, similarity_reason, similarity_score = store.find_merge_candidate(
        tenant_id="default",
        user_id="user-1",
        agent_id="main",
        content_hash="missing-hash",
        dedupe_key=None,
        query_vector=[0.93, math.sqrt(1 - 0.93**2)],
    )
    assert similarity_row is not None
    # Tie-breaking should pick lexical-lowest memory id among equal scores.
    assert similarity_row["memory_id"] == "sim-a"
    assert similarity_reason == "similarity"
    assert similarity_score is not None
    assert similarity_score > 0.92

    below_threshold_row, below_threshold_reason, below_threshold_score = store.find_merge_candidate(
        tenant_id="default",
        user_id="user-1",
        agent_id="main",
        content_hash="missing-hash",
        dedupe_key=None,
        query_vector=[0.92, math.sqrt(1 - 0.92**2)],
    )
    assert below_threshold_row is None
    assert below_threshold_reason is None
    assert below_threshold_score is None


def test_merge_memory_applies_bounded_field_policy(tmp_path):
    """Canonical merge should preserve identity while applying deterministic field precedence."""

    store = LanceMemoryStore(db_path=tmp_path / "lancedb", vector_dim=4)
    store._in_memory_mode = True
    store.store_memory(
        _memory_record(
            memory_id="canonical-1",
            text="Old memory text",
            tags=["ops"],
            metadata={"owner": "alice", "source": "legacy"},
            importance=0.4,
            ttl_expires_at="2026-01-01T00:00:00+00:00",
            dedupe_key="old-key",
            created_at="2026-01-01T00:00:00+00:00",
            updated_at="2026-01-02T00:00:00+00:00",
            vector=[1.0, 0.0, 0.0, 0.0],
        )
    )
    existing_row = store.list_all_memories()[0]

    incoming_record = _memory_record(
        memory_id="incoming-id",
        text="New memory text",
        category="decision",
        tags=["ops", "engineering"],
        metadata={"owner": "bob", "ticket": "INC-42"},
        importance=0.9,
        ttl_expires_at="2026-02-01T00:00:00+00:00",
        dedupe_key="new-key",
        created_at="2026-03-01T00:00:00+00:00",
        updated_at="2026-03-02T00:00:00+00:00",
        vector=[0.0, 1.0, 0.0, 0.0],
    )

    merged_row = store.merge_memory(existing_row=existing_row, incoming_record=incoming_record)

    assert merged_row["memory_id"] == "canonical-1"
    assert merged_row["created_at"] == "2026-01-01T00:00:00+00:00"
    assert merged_row["updated_at"] == "2026-03-02T00:00:00+00:00"
    assert merged_row["text"] == "New memory text"
    assert merged_row["category"] == "decision"
    assert json.loads(merged_row["tags_json"]) == ["ops", "engineering"]
    assert json.loads(merged_row["metadata_json"]) == {
        "owner": "bob",
        "source": "legacy",
        "ticket": "INC-42",
    }
    assert merged_row["importance"] == 0.9
    assert merged_row["ttl_expires_at"] == "2026-02-01T00:00:00+00:00"
    assert merged_row["dedupe_key"] == "new-key"
    assert merged_row["vector"] == [0.0, 1.0, 0.0, 0.0]

    # In-memory merge should replace canonical row in-place rather than append a new row.
    assert len(store._rows) == 1
    assert store._rows[0]["memory_id"] == "canonical-1"


def test_vector_and_shadow_paths_for_db_mode(tmp_path):
    """DB mode should route vector search and shadow writes through table/db adapters."""

    store = LanceMemoryStore(db_path=tmp_path / "lancedb", vector_dim=4)
    table = _VectorTable([{"memory_id": "db-1"}])
    store._table = table
    store._db = _DbRecorder()

    ranked = store.vector_search([0.1, 0.2, 0.3, 0.4], limit=1)
    assert ranked[0]["memory_id"] == "db-1"

    shadow = store.write_shadow_embeddings(
        target_model_id="text-embedding-3-small",
        rows=[{"memory_id": "db-1", "embedding_model_id": "text-embedding-3-large"}],
        vectors=[[0.5, 0.6, 0.7, 0.8]],
    )
    assert shadow is not None
    assert shadow in store._db.created


def test_schema_repair_fixes_null_typed_optional_columns(tmp_path):
    """Store bootstrap should repair null-typed optional columns before writes."""

    lancedb = pytest.importorskip("lancedb")

    db_path = tmp_path / "lancedb"
    db = lancedb.connect(str(db_path))

    # Recreate the historical bad bootstrap shape where optional columns were
    # inferred as Arrow `null`, which rejects later non-null inserts.
    db.create_table(
        "memories_v3",
        data=[
            {
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
                "vector": [0.0, 0.0, 0.0, 0.0],
            }
        ],
    ).delete("memory_id = '__schema__'")

    store = LanceMemoryStore(db_path=db_path, vector_dim=4)
    store.ensure_initialized()

    schema_types = {field.name: str(field.type) for field in store._table.schema}
    assert schema_types["source_channel"] == "string"
    assert schema_types["source_session"] == "string"
    assert schema_types["source_actor"] == "string"
    assert schema_types["ttl_expires_at"] == "string"
    assert schema_types["dedupe_key"] == "string"
    assert schema_types["provenance_source_ref"] == "string"

    stored = store.store_memory(
        _memory_record(
            memory_id="post-repair",
            source_channel="telegram:1387887369",
            source_session="session-1",
            source_actor="actor-1",
            dedupe_key="dedupe-1",
        )
    )
    assert stored.memory_id == "post-repair"

    rows = store.list_all_memories()
    match = next(row for row in rows if row.get("memory_id") == "post-repair")
    assert match["source_channel"] == "telegram:1387887369"
    assert match["source_session"] == "session-1"
    assert match["source_actor"] == "actor-1"
    assert match["dedupe_key"] == "dedupe-1"
