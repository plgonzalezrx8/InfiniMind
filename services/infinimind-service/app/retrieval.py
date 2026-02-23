"""Hybrid retrieval and ranking helpers for InfiniMind recall."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any

import numpy as np
from dateutil.parser import isoparse
from rank_bm25 import BM25Okapi

# Default weights from the v0.1 ranking specification.
HYBRID_WEIGHTS = {
    "semantic": 0.38,
    "lexical": 0.18,
    "recency": 0.12,
    "importance": 0.14,
    "source_reliability": 0.10,
    "type_prior": 0.08,
}

_SOURCE_RELIABILITY = {
    "user_explicit": 1.0,
    "chat": 0.9,
    "tool": 0.8,
    "file": 0.7,
    "web": 0.6,
}

_TYPE_PRIOR = {
    "preference": 1.0,
    "decision": 0.95,
    "fact": 0.9,
    "entity": 0.85,
    "other": 0.7,
}



def _tokenize(text: str) -> list[str]:
    """Tokenize text using whitespace normalization suitable for BM25."""

    return [token for token in text.lower().split() if token]



def _coerce_vector(vector_obj: Any) -> list[float]:
    """Convert LanceDB vector payloads into plain Python float lists."""

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



def _semantic_scores(rows: list[dict[str, Any]], query_vector: list[float]) -> dict[str, float]:
    """Compute cosine similarities against candidate row vectors."""

    if not query_vector:
        return {str(row.get("memory_id")): 0.0 for row in rows}

    q = np.array(query_vector, dtype=np.float32)
    q_norm = np.linalg.norm(q)
    if q_norm == 0.0:
        return {str(row.get("memory_id")): 0.0 for row in rows}

    scores: dict[str, float] = {}
    for row in rows:
        vec = np.array(_coerce_vector(row.get("vector")), dtype=np.float32)
        if vec.size == 0 or vec.shape != q.shape:
            scores[str(row.get("memory_id"))] = 0.0
            continue
        denom = (np.linalg.norm(vec) * q_norm) or 1.0
        cosine = float(np.dot(vec, q) / denom)
        # Normalize cosine (-1..1) into 0..1 for weighted fusion.
        scores[str(row.get("memory_id"))] = (cosine + 1.0) / 2.0
    return scores



def _lexical_scores(rows: list[dict[str, Any]], query: str) -> dict[str, float]:
    """Compute BM25 scores and normalize them to a stable 0..1 range."""

    docs = [_tokenize(str(row.get("text") or "")) for row in rows]
    query_tokens = _tokenize(query)
    if not docs or not query_tokens:
        return {str(row.get("memory_id")): 0.0 for row in rows}

    bm25 = BM25Okapi(docs)
    raw_scores = bm25.get_scores(query_tokens)
    if len(raw_scores) == 0:
        return {str(row.get("memory_id")): 0.0 for row in rows}

    max_score = float(np.max(raw_scores)) or 1.0
    return {
        str(row.get("memory_id")): max(0.0, float(raw_scores[idx]) / max_score)
        for idx, row in enumerate(rows)
    }



def _recency_score(created_at: str | None) -> float:
    """Apply gentle temporal decay so fresher memories are prioritized."""

    if not created_at:
        return 0.0
    try:
        created = isoparse(created_at)
    except Exception:
        return 0.0

    age_seconds = max(0.0, (datetime.now(UTC) - created).total_seconds())
    age_days = age_seconds / 86_400.0
    return 1.0 / (1.0 + age_days)



def hybrid_rank(
    rows: list[dict[str, Any]],
    *,
    query: str,
    query_vector: list[float],
    limit: int,
) -> list[dict[str, Any]]:
    """Fuse lexical and semantic candidates with operational priors.

    The return format includes a per-row score breakdown that later stages can
    expose in debug payloads.
    """

    if not rows:
        return []

    with ThreadPoolExecutor(max_workers=2) as pool:
        semantic_future = pool.submit(_semantic_scores, rows, query_vector)
        lexical_future = pool.submit(_lexical_scores, rows, query)
        semantic = semantic_future.result()
        lexical = lexical_future.result()

    ranked: list[dict[str, Any]] = []
    for row in rows:
        memory_id = str(row.get("memory_id"))

        semantic_score = semantic.get(memory_id, 0.0)
        lexical_score = lexical.get(memory_id, 0.0)
        recency = _recency_score(row.get("created_at"))
        importance = float(row.get("importance") or 0.0)
        source_reliability = _SOURCE_RELIABILITY.get(str(row.get("provenance_source_type")), 0.5)
        type_prior = _TYPE_PRIOR.get(str(row.get("category")), 0.7)

        total_score = (
            HYBRID_WEIGHTS["semantic"] * semantic_score
            + HYBRID_WEIGHTS["lexical"] * lexical_score
            + HYBRID_WEIGHTS["recency"] * recency
            + HYBRID_WEIGHTS["importance"] * importance
            + HYBRID_WEIGHTS["source_reliability"] * source_reliability
            + HYBRID_WEIGHTS["type_prior"] * type_prior
        )

        ranked.append(
            {
                "row": row,
                "score": total_score,
                "score_breakdown": {
                    "semantic": semantic_score,
                    "lexical": lexical_score,
                    "recency": recency,
                    "importance": importance,
                    "source_reliability": source_reliability,
                    "type_prior": type_prior,
                },
            }
        )

    ranked.sort(key=lambda item: item["score"], reverse=True)
    return ranked[:limit]
