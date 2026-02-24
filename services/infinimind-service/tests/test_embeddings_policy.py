"""Unit tests for embedding/provider and policy filter edge cases."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.api_models import RecallRequest
from app.embeddings import (
    MockEmbeddingClient,
    OpenAIEmbeddingClient,
    build_embedding_client,
    build_embedding_client_for_model,
)
from app.policy import _as_utc, _is_expired, apply_hard_filters, apply_safe_fallback
from app.settings import Settings


def test_openai_embedding_client_wraps_openai_response(monkeypatch) -> None:
    """OpenAI adapter should return raw embedding vectors from SDK responses."""

    class _FakeEmbeddings:
        def create(self, *, model: str, input: str):
            assert model == "text-embedding-3-large"
            assert input == "hello"
            return SimpleNamespace(data=[SimpleNamespace(embedding=[0.1, 0.2, 0.3])])

    class _FakeOpenAI:
        def __init__(self, *, api_key: str):
            assert api_key == "openai-test-key"
            self.embeddings = _FakeEmbeddings()

    monkeypatch.setattr("app.embeddings.OpenAI", _FakeOpenAI)
    client = OpenAIEmbeddingClient(api_key="openai-test-key", model="text-embedding-3-large")
    assert client.embed("hello") == [0.1, 0.2, 0.3]


def test_build_embedding_client_modes_and_validation(monkeypatch) -> None:
    """Factory should pick mock/openai backends and fail fast on invalid configuration."""

    class _FakeOpenAI:
        def __init__(self, *, api_key: str):
            self.embeddings = SimpleNamespace(create=lambda **_: SimpleNamespace(data=[SimpleNamespace(embedding=[1.0])]))

    monkeypatch.setattr("app.embeddings.OpenAI", _FakeOpenAI)

    mock_settings = Settings(api_key="service-token", app_env="test", embedding_provider="mock")
    mock_client = build_embedding_client(mock_settings)
    assert isinstance(mock_client, MockEmbeddingClient)
    assert len(mock_client.embed("deterministic")) == mock_settings.vector_dim

    dev_fallback = Settings(api_key="service-token", app_env="dev", embedding_provider="openai", openai_api_key=None)
    assert isinstance(build_embedding_client(dev_fallback), MockEmbeddingClient)

    explicit_openai = Settings(
        api_key="service-token",
        app_env="prod",
        embedding_provider="openai",
        openai_api_key="openai-test-key",
    )
    assert isinstance(build_embedding_client(explicit_openai), OpenAIEmbeddingClient)

    prod_missing_key = Settings(api_key="service-token", app_env="prod", embedding_provider="openai", openai_api_key=None)
    with pytest.raises(ValueError, match="INFINIMIND_OPENAI_API_KEY is required"):
        build_embedding_client(prod_missing_key)

    unsupported = Settings(api_key="service-token", app_env="prod", embedding_provider="invalid-provider")
    with pytest.raises(ValueError, match="Unsupported embedding provider"):
        build_embedding_client(unsupported)


def test_build_embedding_client_for_model_supports_mock_and_openai(monkeypatch) -> None:
    """Re-embed helper should enforce key requirements in openai mode."""

    class _FakeOpenAI:
        def __init__(self, *, api_key: str):
            self.embeddings = SimpleNamespace(create=lambda **_: SimpleNamespace(data=[SimpleNamespace(embedding=[1.0])]))

    monkeypatch.setattr("app.embeddings.OpenAI", _FakeOpenAI)

    mock_settings = Settings(api_key="service-token", app_env="test", embedding_provider="mock")
    assert isinstance(
        build_embedding_client_for_model(mock_settings, "text-embedding-3-large"),
        MockEmbeddingClient,
    )

    openai_settings = Settings(
        api_key="service-token",
        app_env="prod",
        embedding_provider="openai",
        openai_api_key="openai-test-key",
    )
    assert isinstance(
        build_embedding_client_for_model(openai_settings, "text-embedding-3-small"),
        OpenAIEmbeddingClient,
    )

    missing_key = Settings(api_key="service-token", app_env="prod", embedding_provider="openai", openai_api_key=None)
    with pytest.raises(ValueError, match="INFINIMIND_OPENAI_API_KEY is required"):
        build_embedding_client_for_model(missing_key, "text-embedding-3-small")


def test_policy_filters_handle_dates_tags_and_sensitivity_rules() -> None:
    """Hard filters should enforce trust gates and tolerate malformed row payloads."""

    now = datetime.now(UTC)
    base_row = {
        "memory_id": "m1",
        "tenant_id": "default",
        "user_id": "user-1",
        "agent_id": "main",
        "scope": "user",
        "source_channel": "c1",
        "source_session": "s1",
        "source_actor": "a1",
        "sensitivity": "low",
        "ttl_expires_at": (now + timedelta(hours=1)).isoformat(),
        "category": "fact",
        "importance": 0.8,
        "tags_json": "[\"ops\", \"prod\"]",
        "created_at": now.isoformat(),
    }
    high_sensitivity = dict(base_row, memory_id="m2", sensitivity="high")
    bad_tags = dict(base_row, memory_id="m3", tags_json="{invalid", category="decision")
    expired = dict(base_row, memory_id="m4", ttl_expires_at=(now - timedelta(hours=1)).isoformat())
    invalid_created = dict(base_row, memory_id="m5", created_at="not-a-date")

    request = RecallRequest(
        tenant_id="default",
        user_id="user-1",
        agent_id="main",
        query="ops",
        scope="user",
        channel_id="c1",
        session_id="s1",
        actor_id="a1",
        categories=["fact", "decision"],
        tags_any=["ops"],
        min_importance=0.7,
        since=now - timedelta(days=1),
        until=now + timedelta(days=1),
        include_sensitive=False,
        trust_level="medium",
    )
    filtered = apply_hard_filters(
        [base_row, high_sensitivity, bad_tags, expired, invalid_created],
        request,
    )
    # m1 passes; m3 fails tags_any because malformed tags normalize to [].
    assert [row["memory_id"] for row in filtered] == ["m1"]


def test_policy_safe_fallback_relaxes_optional_filters_only() -> None:
    """Fallback should broaden optional filters while preserving core boundaries."""

    now = datetime.now(UTC)
    row = {
        "memory_id": "m10",
        "tenant_id": "default",
        "user_id": "user-1",
        "agent_id": "main",
        "scope": "channel",
        "source_channel": "chan-1",
        "source_session": "sess-1",
        "source_actor": "actor-1",
        "sensitivity": "low",
        "ttl_expires_at": None,
        "category": "fact",
        "importance": 0.2,
        "tags_json": "[\"release\"]",
        "created_at": now.isoformat(),
    }

    request = RecallRequest(
        tenant_id="default",
        user_id="user-1",
        agent_id="main",
        query="release",
        scope="session",
        categories=["preference"],
        tags_any=["missing"],
        min_importance=0.9,
        since=now + timedelta(days=1),
        until=now + timedelta(days=2),
        include_sensitive=False,
    )
    assert apply_hard_filters([row], request) == []
    relaxed = apply_safe_fallback([row], request)
    assert [item["memory_id"] for item in relaxed] == ["m10"]


def test_policy_time_helpers_are_fail_safe() -> None:
    """Time helpers should normalize UTC values and fail closed on invalid expiry."""

    naive = datetime(2026, 2, 24, 12, 0, 0)
    aware = datetime(2026, 2, 24, 12, 0, 0, tzinfo=UTC)
    assert _as_utc(naive).tzinfo == UTC
    assert _as_utc(aware) == aware
    assert _as_utc(None) is None

    assert _is_expired((datetime.now(UTC) - timedelta(minutes=1)).isoformat()) is True
    assert _is_expired((datetime.now(UTC) + timedelta(minutes=1)).isoformat()) is False
    assert _is_expired("not-a-time") is True
    assert _is_expired(None) is False
