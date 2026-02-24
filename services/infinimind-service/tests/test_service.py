"""Integration-style API tests for core memory flows."""

from __future__ import annotations


def test_health_and_ready(client, auth_headers):
    """Health is public; readiness requires authentication."""

    health = client.get("/v1/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    ready_unauth = client.get("/v1/ready")
    assert ready_unauth.status_code == 401

    ready_auth = client.get("/v1/ready", headers=auth_headers)
    assert ready_auth.status_code == 200
    assert ready_auth.json()["status"] == "ready"


def test_store_duplicate_and_recall(client, auth_headers):
    """Store endpoint should dedupe identical content and recall it."""

    payload = {
        "tenant_id": "default",
        "user_id": "user-1",
        "agent_id": "main",
        "text": "Remember that I prefer concise commit messages.",
        "category": "preference",
    }

    first = client.post("/v1/memory/store", json=payload, headers=auth_headers)
    assert first.status_code == 200
    assert first.json()["action"] == "created"

    duplicate = client.post("/v1/memory/store", json=payload, headers=auth_headers)
    assert duplicate.status_code == 200
    assert duplicate.json()["action"] == "duplicate"

    recall = client.post(
        "/v1/memory/recall",
        json={
            "tenant_id": "default",
            "user_id": "user-1",
            "agent_id": "main",
            "query": "concise commit messages",
            "limit": 5,
            "rerank": "hybrid",
        },
        headers=auth_headers,
    )
    assert recall.status_code == 200
    body = recall.json()
    assert body["count"] >= 1
    assert "score_breakdown" in body["memories"][0]


def test_policy_sensitive_gate_and_fallback(client, auth_headers):
    """Sensitive gating and safe fallback should behave deterministically."""

    store = client.post(
        "/v1/memory/store",
        json={
            "tenant_id": "default",
            "user_id": "user-2",
            "agent_id": "main",
            "text": "Production credentials rotated on Fridays.",
            "category": "fact",
            "sensitivity": "high",
            "tags": ["ops"],
        },
        headers=auth_headers,
    )
    assert store.status_code == 200

    blocked = client.post(
        "/v1/memory/recall",
        json={
            "tenant_id": "default",
            "user_id": "user-2",
            "agent_id": "main",
            "query": "credentials",
            "include_sensitive": True,
            "trust_level": "medium",
            "debug": True,
        },
        headers=auth_headers,
    )
    assert blocked.status_code == 200
    blocked_body = blocked.json()
    assert blocked_body["count"] == 0
    assert any("high trust" in note for note in blocked_body["debug"]["policy_notes"])

    allowed = client.post(
        "/v1/memory/recall",
        json={
            "tenant_id": "default",
            "user_id": "user-2",
            "agent_id": "main",
            "query": "credentials",
            "include_sensitive": True,
            "trust_level": "high",
            "categories": ["decision"],
            "fallback_mode": "legacy-compatible",
            "debug": True,
        },
        headers=auth_headers,
    )
    assert allowed.status_code == 200
    allowed_body = allowed.json()
    assert allowed_body["count"] >= 1
    assert allowed_body["debug"]["fallback_applied"] is True


def test_admin_reembed_dry_run(client, auth_headers, admin_headers):
    """Admin re-embed dry-run returns processed count without writing shadow tables."""

    client.post(
        "/v1/memory/store",
        json={
            "tenant_id": "default",
            "user_id": "user-3",
            "agent_id": "main",
            "text": "Shadow reembed test row.",
        },
        headers=auth_headers,
    )

    response = client.post(
        "/v1/admin/reembed",
        json={"target_model_id": "text-embedding-3-large", "dry_run": True},
        headers=admin_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["dry_run"] is True
    assert body["processed"] >= 1


def test_admin_reembed_empty_store_noop(client, admin_headers):
    """Re-embed should no-op cleanly when no rows exist."""

    response = client.post(
        "/v1/admin/reembed",
        json={"target_model_id": "text-embedding-3-large", "dry_run": False},
        headers=admin_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["dry_run"] is False
    assert body["processed"] == 0
    assert body["shadow_table"] is None


def test_metrics_endpoint(client):
    """Prometheus endpoint should expose InfiniMind metric series."""

    metrics = client.get("/v1/metrics")
    assert metrics.status_code == 200
    assert "infinimind_http_requests_total" in metrics.text


def test_forget_endpoint_paths(client, auth_headers):
    """Forget endpoint should cover missing params, candidates, delete, and not-found paths."""

    first = client.post(
        "/v1/memory/store",
        json={
            "tenant_id": "default",
            "user_id": "forget-user",
            "agent_id": "main",
            "text": "Remember deployment playbook owner is Alice.",
            "category": "fact",
        },
        headers=auth_headers,
    )
    second = client.post(
        "/v1/memory/store",
        json={
            "tenant_id": "default",
            "user_id": "forget-user",
            "agent_id": "main",
            "text": "Remember deployment playbook owner is Bob.",
            "category": "fact",
        },
        headers=auth_headers,
    )
    assert first.status_code == 200
    assert second.status_code == 200
    first_id = first.json()["memory_id"]

    missing = client.post(
        "/v1/memory/forget",
        json={"tenant_id": "default", "user_id": "forget-user", "agent_id": "main"},
        headers=auth_headers,
    )
    assert missing.status_code == 200
    assert missing.json()["action"] == "missing_param"

    candidates = client.post(
        "/v1/memory/forget",
        json={
            "tenant_id": "default",
            "user_id": "forget-user",
            "agent_id": "main",
            "query": "deployment playbook owner",
        },
        headers=auth_headers,
    )
    assert candidates.status_code == 200
    candidates_body = candidates.json()
    assert candidates_body["action"] == "candidates"
    assert candidates_body["found"] >= 2

    deleted = client.post(
        "/v1/memory/forget",
        json={
            "tenant_id": "default",
            "user_id": "forget-user",
            "agent_id": "main",
            "memory_id": first_id,
        },
        headers=auth_headers,
    )
    assert deleted.status_code == 200
    assert deleted.json()["action"] == "deleted"

    not_found = client.post(
        "/v1/memory/forget",
        json={
            "tenant_id": "default",
            "user_id": "forget-user",
            "agent_id": "main",
            "memory_id": first_id,
        },
        headers=auth_headers,
    )
    assert not_found.status_code == 200
    assert not_found.json()["action"] == "not_found"


def test_recall_invalid_date_filters_return_422(client, auth_headers):
    """Malformed or inverted date filters should fail validation before policy logic."""

    malformed = client.post(
        "/v1/memory/recall",
        json={
            "tenant_id": "default",
            "user_id": "user-1",
            "agent_id": "main",
            "query": "any",
            "since": "not-a-date",
        },
        headers=auth_headers,
    )
    assert malformed.status_code == 422

    inverted = client.post(
        "/v1/memory/recall",
        json={
            "tenant_id": "default",
            "user_id": "user-1",
            "agent_id": "main",
            "query": "any",
            "since": "2026-01-10T00:00:00Z",
            "until": "2026-01-09T00:00:00Z",
        },
        headers=auth_headers,
    )
    assert inverted.status_code == 422


def test_metadata_roundtrip_on_store_and_recall(client, auth_headers):
    """Stored metadata should persist and be returned on recall responses."""

    store = client.post(
        "/v1/memory/store",
        json={
            "tenant_id": "default",
            "user_id": "metadata-user",
            "agent_id": "main",
            "text": "Ticket INC-42 assigned to platform team.",
            "category": "fact",
            "metadata": {"ticket": "INC-42", "priority": 2, "source": "ops"},
        },
        headers=auth_headers,
    )
    assert store.status_code == 200

    recall = client.post(
        "/v1/memory/recall",
        json={
            "tenant_id": "default",
            "user_id": "metadata-user",
            "agent_id": "main",
            "query": "INC-42",
            "limit": 3,
            "rerank": "hybrid",
        },
        headers=auth_headers,
    )
    assert recall.status_code == 200
    body = recall.json()
    assert body["count"] >= 1
    assert body["memories"][0]["metadata"]["ticket"] == "INC-42"


def test_recall_handles_invalid_metadata_json(client, auth_headers):
    """Corrupt metadata payloads should fail-safe to empty metadata instead of 500."""

    store = client.post(
        "/v1/memory/store",
        json={
            "tenant_id": "default",
            "user_id": "corrupt-metadata-user",
            "agent_id": "main",
            "text": "Corrupt metadata guard test.",
            "category": "fact",
            "metadata": {"healthy": True},
        },
        headers=auth_headers,
    )
    assert store.status_code == 200
    memory_id = store.json()["memory_id"]

    # Tests run in in-memory mode; mutate raw row payload to emulate corrupted stored JSON.
    for row in client.app.state.memory_store._rows:
        if row.get("memory_id") == memory_id:
            row["metadata_json"] = "{bad-json"
            break

    recall = client.post(
        "/v1/memory/recall",
        json={
            "tenant_id": "default",
            "user_id": "corrupt-metadata-user",
            "agent_id": "main",
            "query": "Corrupt metadata",
            "limit": 3,
            "rerank": "hybrid",
        },
        headers=auth_headers,
    )
    assert recall.status_code == 200
    body = recall.json()
    assert body["count"] >= 1
    assert body["memories"][0]["metadata"] == {}


def test_recall_handles_invalid_tags_and_conflict_json(client, auth_headers):
    """Corrupt tags/conflict-set payloads should normalize to empty lists."""

    store = client.post(
        "/v1/memory/store",
        json={
            "tenant_id": "default",
            "user_id": "corrupt-lists-user",
            "agent_id": "main",
            "text": "Corrupt list JSON guard test.",
            "category": "fact",
            "tags": ["ops"],
            "quality": {"confidence": 0.8, "verification_status": "unverified", "conflict_set": ["a"]},
        },
        headers=auth_headers,
    )
    assert store.status_code == 200
    memory_id = store.json()["memory_id"]

    # Tests run in in-memory mode; mutate raw row payload to emulate corrupted stored JSON.
    for row in client.app.state.memory_store._rows:
        if row.get("memory_id") == memory_id:
            row["tags_json"] = "{bad-json"
            row["quality_conflict_set_json"] = "{bad-json"
            break

    recall = client.post(
        "/v1/memory/recall",
        json={
            "tenant_id": "default",
            "user_id": "corrupt-lists-user",
            "agent_id": "main",
            "query": "Corrupt list JSON",
            "limit": 3,
            "rerank": "hybrid",
        },
        headers=auth_headers,
    )
    assert recall.status_code == 200
    body = recall.json()
    assert body["count"] >= 1
    assert body["memories"][0]["tags"] == []
    assert body["memories"][0]["quality"]["conflict_set"] == []
