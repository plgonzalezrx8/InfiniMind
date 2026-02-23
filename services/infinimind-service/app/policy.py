"""Hard policy filters applied before ranking and context packaging."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from dateutil.parser import isoparse

from .api_models import RecallRequest



def _is_expired(ttl_expires_at: str | None) -> bool:
    """Return true when ttl_expires_at is in the past."""

    if not ttl_expires_at:
        return False
    try:
        return isoparse(ttl_expires_at) < datetime.now(UTC)
    except Exception:
        # If an invalid timestamp is found, fail closed by treating it as expired.
        return True



def apply_hard_filters(rows: list[dict[str, Any]], request: RecallRequest) -> list[dict[str, Any]]:
    """Apply mandatory policy constraints before ranking.

    These checks are intentionally strict to minimize wrong-context and
    sensitivity leaks in multi-context environments.
    """

    filtered: list[dict[str, Any]] = []

    since_ts = isoparse(request.since) if request.since else None
    until_ts = isoparse(request.until) if request.until else None

    include_sensitive = request.include_sensitive and request.trust_level == "high"

    for row in rows:
        if row.get("tenant_id") != request.tenant_id:
            continue
        if row.get("user_id") != request.user_id:
            continue
        if row.get("agent_id") != request.agent_id:
            continue

        if request.scope and row.get("scope") != request.scope.value:
            continue

        if request.channel_id and row.get("source_channel") != request.channel_id:
            continue
        if request.session_id and row.get("source_session") != request.session_id:
            continue
        if request.actor_id and row.get("source_actor") != request.actor_id:
            continue

        if not include_sensitive and row.get("sensitivity") == "high":
            continue

        ttl_expires_at = row.get("ttl_expires_at")
        if not request.include_expired and _is_expired(ttl_expires_at):
            continue

        if request.categories and row.get("category") not in request.categories:
            continue

        if request.min_importance is not None:
            importance = float(row.get("importance") or 0.0)
            if importance < request.min_importance:
                continue

        row_tags = []
        try:
            row_tags = json.loads(row.get("tags_json") or "[]")
        except Exception:
            row_tags = []

        if request.tags_any:
            if not any(tag in row_tags for tag in request.tags_any):
                continue

        try:
            created_at = isoparse(str(row.get("created_at")))
        except Exception:
            continue

        if since_ts and created_at < since_ts:
            continue
        if until_ts and created_at > until_ts:
            continue

        filtered.append(row)

    return filtered


def apply_safe_fallback(rows: list[dict[str, Any]], request: RecallRequest) -> list[dict[str, Any]]:
    """Broaden optional filters while preserving hard trust boundaries.

    The fallback mode intentionally keeps tenant/user/agent/sensitivity/ttl checks
    unchanged, and only relaxes optional narrowing constraints.
    """

    relaxed_request = request.model_copy(
        update={
            "scope": None,
            "channel_id": None,
            "session_id": None,
            "actor_id": None,
            "categories": [],
            "tags_any": [],
            "min_importance": None,
            "since": None,
            "until": None,
        }
    )
    return apply_hard_filters(rows, relaxed_request)
