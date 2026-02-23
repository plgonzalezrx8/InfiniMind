"""Shared pytest fixtures for InfiniMind service tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.settings import get_settings


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Return a test client with isolated storage and deterministic embeddings."""

    monkeypatch.setenv("INFINIMIND_APP_ENV", "test")
    monkeypatch.setenv("INFINIMIND_API_KEY", "test-api-key")
    monkeypatch.setenv("INFINIMIND_ADMIN_API_KEY", "test-admin-key")
    monkeypatch.setenv("INFINIMIND_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("INFINIMIND_EMBEDDING_PROVIDER", "mock")

    # Clear cached settings so env overrides are applied for each test.
    get_settings.cache_clear()

    with TestClient(app) as test_client:
        yield test_client

    get_settings.cache_clear()


@pytest.fixture()
def auth_headers() -> dict[str, str]:
    """Headers for normal API calls."""

    return {"Authorization": "Bearer test-api-key"}


@pytest.fixture()
def admin_headers() -> dict[str, str]:
    """Headers for admin-only routes."""

    return {"Authorization": "Bearer test-admin-key"}
