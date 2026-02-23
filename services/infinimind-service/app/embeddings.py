"""Embedding adapters for InfiniMind retrieval and storage."""

from __future__ import annotations

import hashlib
import random
from typing import Protocol

from openai import OpenAI

from .settings import Settings


class EmbeddingClient(Protocol):
    """Protocol implemented by embedding providers."""

    def embed(self, text: str) -> list[float]:
        """Return a deterministic embedding vector for the input text."""


class OpenAIEmbeddingClient:
    """OpenAI embeddings adapter with pinned model selection."""

    def __init__(self, api_key: str, model: str) -> None:
        self._client = OpenAI(api_key=api_key)
        self._model = model

    def embed(self, text: str) -> list[float]:
        response = self._client.embeddings.create(model=self._model, input=text)
        return list(response.data[0].embedding)


class MockEmbeddingClient:
    """Deterministic pseudo-embedding provider used in tests/local smoke runs."""

    def __init__(self, dim: int) -> None:
        self._dim = dim

    def embed(self, text: str) -> list[float]:
        seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)
        rng = random.Random(seed)
        return [rng.uniform(-1.0, 1.0) for _ in range(self._dim)]



def build_embedding_client(settings: Settings) -> EmbeddingClient:
    """Build an embedding client from runtime settings.

    We default to OpenAI in production and allow a deterministic mock provider
    for tests and local development without API keys.
    """

    provider = settings.embedding_provider.lower().strip()
    if provider == "mock":
        return MockEmbeddingClient(dim=settings.vector_dim)

    if provider == "openai":
        if not settings.openai_api_key:
            # Dev/test fallback keeps local workflows and CI deterministic.
            if settings.app_env in {"dev", "test"}:
                return MockEmbeddingClient(dim=settings.vector_dim)
            raise ValueError("INFINIMIND_OPENAI_API_KEY is required when provider is openai")
        return OpenAIEmbeddingClient(api_key=settings.openai_api_key, model=settings.embedding_model)

    raise ValueError(f"Unsupported embedding provider: {settings.embedding_provider}")
