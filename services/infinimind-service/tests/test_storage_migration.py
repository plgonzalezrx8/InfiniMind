"""Storage migration coverage for legacy LanceDB schema upgrades."""

from __future__ import annotations

from app.storage import LanceMemoryStore


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows
        self._limit = len(rows)

    def limit(self, limit: int):
        self._limit = limit
        return self

    def to_list(self):
        return [dict(row) for row in self._rows[: self._limit]]


class _FakeTable:
    def __init__(self, rows):
        self.rows = [dict(row) for row in rows]

    def search(self, *_args, **_kwargs):
        return _FakeQuery(self.rows)

    def delete(self, expression: str):
        if "memory_id = '__schema__'" in expression:
            self.rows = [row for row in self.rows if row.get("memory_id") != "__schema__"]


class _FakeDb:
    def __init__(self, tables):
        self.tables = tables

    def table_names(self):
        return list(self.tables.keys())

    def open_table(self, name: str):
        return self.tables[name]

    def create_table(self, name: str, data):
        table = _FakeTable(data)
        self.tables[name] = table
        return table


class _FakeLanceModule:
    def __init__(self, db):
        self._db = db

    def connect(self, _path: str):
        return self._db


def test_boot_migrates_v2_rows_to_v3_table(tmp_path, monkeypatch):
    """Store bootstrap should migrate legacy v2 rows into the v3 schema table."""

    legacy_row = {
        "memory_id": "legacy-1",
        "schema_version": 2,
        "tenant_id": "default",
        "user_id": "legacy-user",
        "agent_id": "main",
        "text": "legacy row",
        "category": "fact",
        "tags_json": "[]",
        "importance": 0.7,
        "scope": "user",
        "sensitivity": "low",
        "source_channel": None,
        "source_session": None,
        "source_actor": None,
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "ttl_expires_at": None,
        "embedding_model_id": "text-embedding-3-large",
        "content_hash": "abc",
        "dedupe_key": None,
        "provenance_source_type": "chat",
        "provenance_source_ref": None,
        "quality_confidence": 0.5,
        "quality_verification_status": "unverified",
        "quality_conflict_set_json": "[]",
        "vector": [0.0, 0.0, 0.0, 0.0],
    }

    fake_db = _FakeDb({"memories_v2": _FakeTable([legacy_row])})

    from app import storage as storage_module

    monkeypatch.setattr(
        storage_module.importlib,
        "import_module",
        lambda name: _FakeLanceModule(fake_db) if name == "lancedb" else None,
    )

    store = LanceMemoryStore(db_path=tmp_path / "lancedb", vector_dim=4)
    store.ensure_initialized()

    assert "memories_v2" in fake_db.tables
    assert "memories_v3" in fake_db.tables

    migrated_rows = fake_db.tables["memories_v3"].rows
    assert len(migrated_rows) == 1
    assert migrated_rows[0]["schema_version"] == 3
    assert migrated_rows[0]["metadata_json"] == "{}"
