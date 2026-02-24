"""Unit coverage for auth and dependency helpers."""

from __future__ import annotations

from fastapi import HTTPException

from app import dependencies as dependencies_module
from app.auth import (
    _extract_bearer_token,
    require_admin_api_key,
    require_api_key,
)
from app.settings import Settings


def test_extract_bearer_token_validates_header_shape() -> None:
    """Auth parser should reject missing/invalid headers and accept bearer tokens."""

    try:
        _extract_bearer_token(None)
    except HTTPException as exc:
        assert exc.status_code == 401
        assert exc.detail == "missing auth header"
    else:  # pragma: no cover - defensive assertion pattern
        raise AssertionError("expected HTTPException for missing header")

    try:
        _extract_bearer_token("Basic abc123")
    except HTTPException as exc:
        assert exc.status_code == 401
        assert exc.detail == "invalid auth scheme"
    else:  # pragma: no cover - defensive assertion pattern
        raise AssertionError("expected HTTPException for invalid scheme")

    assert _extract_bearer_token("Bearer token-123") == "token-123"


def test_require_api_key_accepts_matching_token_and_rejects_invalid() -> None:
    """Standard API dependency should enforce hmac token comparison."""

    settings = Settings(api_key="service-token", app_env="test", embedding_provider="mock")
    require_api_key(authorization="Bearer service-token", settings=settings)

    try:
        require_api_key(authorization="Bearer bad-token", settings=settings)
    except HTTPException as exc:
        assert exc.status_code == 401
        assert exc.detail == "invalid token"
    else:  # pragma: no cover - defensive assertion pattern
        raise AssertionError("expected HTTPException for invalid token")


def test_require_admin_api_key_uses_admin_key_or_primary_fallback() -> None:
    """Admin dependency should support explicit admin key and fallback to API key."""

    with_admin = Settings(
        api_key="service-token",
        admin_api_key="admin-token",
        app_env="test",
        embedding_provider="mock",
    )
    require_admin_api_key(authorization="Bearer admin-token", settings=with_admin)

    fallback = Settings(api_key="service-token", admin_api_key=None, app_env="test", embedding_provider="mock")
    require_admin_api_key(authorization="Bearer service-token", settings=fallback)

    try:
        require_admin_api_key(authorization="Bearer wrong", settings=with_admin)
    except HTTPException as exc:
        assert exc.status_code == 401
        assert exc.detail == "invalid admin token"
    else:  # pragma: no cover - defensive assertion pattern
        raise AssertionError("expected HTTPException for invalid admin token")


def test_dependency_helpers_return_expected_runtime_objects(client, monkeypatch) -> None:
    """Dependency wrappers should surface settings and app-state storage directly."""

    expected = Settings(api_key="settings-token", app_env="test", embedding_provider="mock")
    monkeypatch.setattr(dependencies_module, "get_settings", lambda: expected)
    assert dependencies_module.get_runtime_settings() is expected

    class _DummyRequest:
        def __init__(self, app):
            self.app = app

    request = _DummyRequest(client.app)
    assert dependencies_module.get_memory_store(request) is client.app.state.memory_store
