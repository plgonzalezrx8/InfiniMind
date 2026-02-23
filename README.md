# InfiniMind

InfiniMind is a standalone, Docker-first memory sidecar for OpenClaw.

It provides:

- enriched memory storage
- filter-first and hybrid retrieval
- policy enforcement (scope, sensitivity, TTL)
- observability metrics
- a dedicated OpenClaw bridge plugin (`infinimind-bridge`)

## Status

This repository contains a working MVP implementation on branch `codex/infinimind-mvp`.

## Architecture

1. OpenClaw calls `memory_store` / `memory_recall`.
2. `infinimind-bridge` plugin forwards calls over HTTP.
3. InfiniMind service enforces policy and performs retrieval/ranking.
4. Bridge returns OpenClaw-compatible tool content/details.

## Repository layout

- `services/infinimind-service`: FastAPI service
- `plugins/infinimind-openclaw-bridge`: OpenClaw memory plugin
- `deploy/docker-compose.yml`: default runtime path
- `docs/openclaw-integration.md`: OpenClaw integration details
- `docs/operators/configuration.md`: operator deployment config
- `docs/operators/rollback.md`: rollback runbook
- `docs/operators/release-checklist.md`: merge/release checklist
- `deploy/openclaw-config.example.json`: example OpenClaw config snippet
- `COMPATIBILITY_LEDGER.md`: per-feature OpenClaw docs/source consultation log

## Prerequisites

- Docker + Docker Compose
- OpenClaw runtime (for bridge integration)
- Python 3.11+ (for local tests/benchmarks)

## Quick start (Docker-first)

1. Start service:

```bash
docker compose -f deploy/docker-compose.yml up -d --build
```

2. Verify liveness:

```bash
curl -s http://127.0.0.1:8080/v1/health
```

3. Verify readiness (auth required):

```bash
curl -s -H "Authorization: Bearer change-me-now" http://127.0.0.1:8080/v1/ready
```

4. Verify metrics endpoint:

```bash
curl -s http://127.0.0.1:8080/v1/metrics | head
```

## Environment variables

Main service settings:

- `INFINIMIND_API_KEY`: bearer token for service calls
- `INFINIMIND_ADMIN_API_KEY`: admin token for re-embed endpoint
- `INFINIMIND_DATA_DIR`: persistent data path (`/var/lib/infinimind` in Docker)
- `INFINIMIND_EMBEDDING_PROVIDER`: `openai` or `mock`
- `INFINIMIND_EMBEDDING_MODEL`: default `text-embedding-3-large`
- `INFINIMIND_OPENAI_API_KEY`: required when provider is `openai`

## API endpoints

- `GET /v1/health`
- `GET /v1/ready`
- `GET /v1/metrics`
- `POST /v1/memory/store`
- `POST /v1/memory/batch-store`
- `POST /v1/memory/recall`
- `POST /v1/admin/reembed`

### Minimal store example

```bash
curl -s \
  -H "Authorization: Bearer change-me-now" \
  -H "Content-Type: application/json" \
  -X POST http://127.0.0.1:8080/v1/memory/store \
  -d '{
    "tenant_id": "default",
    "user_id": "user-1",
    "agent_id": "main",
    "text": "Remember: user prefers concise summaries.",
    "category": "preference"
  }'
```

### Minimal recall example

```bash
curl -s \
  -H "Authorization: Bearer change-me-now" \
  -H "Content-Type: application/json" \
  -X POST http://127.0.0.1:8080/v1/memory/recall \
  -d '{
    "tenant_id": "default",
    "user_id": "user-1",
    "agent_id": "main",
    "query": "concise summaries",
    "limit": 5,
    "rerank": "hybrid",
    "fallback_mode": "legacy-compatible"
  }'
```

## OpenClaw integration (bridge plugin)

1. Ensure plugin path is discoverable:

```json5
plugins: {
  load: { paths: ["/absolute/path/to/infinimind-openclaw-bridge"] }
}
```

2. Allow and enable bridge plugin:

```json5
plugins: {
  allow: ["infinimind-bridge"],
  entries: {
    "infinimind-bridge": {
      enabled: true,
      config: {
        baseUrl: "http://infinimind:8080",
        apiKey: "${INFINIMIND_API_KEY}",
        timeoutMs: 4000,
        defaultScope: "user",
        includeSensitiveDefault: false,
        rerankDefault: "hybrid",
        fallbackMode: "legacy-compatible"
      }
    }
  }
}
```

3. Switch memory slot:

```json5
plugins: {
  slots: {
    memory: "infinimind-bridge"
  }
}
```

4. Validate and restart OpenClaw gateway for plugin infra changes:

```bash
openclaw plugins doctor
openclaw plugins list
openclaw plugins info infinimind-bridge
```

Full guidance:

- [OpenClaw Integration](/Users/pedrogonzalez/CascadeProjects/InfiniMind/docs/openclaw-integration.md)
- [Operator Configuration](/Users/pedrogonzalez/CascadeProjects/InfiniMind/docs/operators/configuration.md)

## Testing

Run service tests:

```bash
python3 -m pytest services/infinimind-service/tests -q
```

Run OpenClaw contract tests:

```bash
python3 -m pytest tests/openclaw -q
```

## Benchmarking

Use the recall benchmark harness:

```bash
python3 scripts/benchmark_recall.py --base-url http://127.0.0.1:8080 --api-key change-me-now --loops 100
```

This reports latency (`mean/p50/p95`) and a top-1 hit-rate proxy for `rerank=off` vs `rerank=hybrid`.

## Rollback

Primary rollback action is switching `plugins.slots.memory` back to `memory-core` and optionally disabling `infinimind-bridge`.

See full runbook:

- [Rollback Guide](/Users/pedrogonzalez/CascadeProjects/InfiniMind/docs/operators/rollback.md)

## Release and merge

Use:

- [Release Checklist](/Users/pedrogonzalez/CascadeProjects/InfiniMind/docs/operators/release-checklist.md)

## License

MIT License. See [LICENSE](/Users/pedrogonzalez/CascadeProjects/InfiniMind/LICENSE).
