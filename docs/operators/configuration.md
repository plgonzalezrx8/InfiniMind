# Operator Configuration Guide

## Docker-first deployment

From repository root:

```bash
docker compose -f deploy/docker-compose.yml up -d --build
```

Default service endpoint: `http://127.0.0.1:8080`

## Environment variables

Main variables used by the service container:

- `INFINIMIND_API_KEY`: bearer token for bridge/service calls
- `INFINIMIND_ADMIN_API_KEY`: admin token for `/v1/admin/reembed`
- `INFINIMIND_DATA_DIR`: persistent state path (default `/var/lib/infinimind`)
- `INFINIMIND_EMBEDDING_PROVIDER`: `openai` or `mock`
- `INFINIMIND_EMBEDDING_MODEL`: default `text-embedding-3-large`
- `INFINIMIND_OPENAI_API_KEY`: required for OpenAI embeddings

## OpenClaw configuration file changes

Target file: `~/.openclaw/openclaw.json`.

1. Add plugin path under `plugins.load.paths`.
2. Add plugin id to `plugins.allow`.
3. Set `plugins.slots.memory = "infinimind-bridge"`.
4. Configure `plugins.entries.infinimind-bridge.config`.

Reference JSON example: [openclaw-config.example.json](/Users/pedrogonzalez/CascadeProjects/InfiniMind/deploy/openclaw-config.example.json)

## Canary rollout steps

1. Start sidecar with production-equivalent settings.
2. Enable bridge plugin for one canary agent/user context.
3. Keep fallback enabled (`fallbackMode: legacy-compatible`).
4. Monitor:
   - `/v1/metrics`
   - recall fallback counter
   - policy note counter
   - p95 latency trend
5. Expand canary cohort only when safety counters remain stable.

## Operational checks

- Liveness: `GET /v1/health`
- Readiness (auth): `GET /v1/ready`
- Metrics: `GET /v1/metrics`
- Dry-run migration: `POST /v1/admin/reembed` with `dry_run=true`
