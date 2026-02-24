# Operator Configuration Guide

## Docker-first deployment

From repository root:

```bash
cp .env.example .env
python3 scripts/generate_api_keys.py --write-env
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
- `INFINIMIND_TRACING_ENABLED`: `true`/`false` (default `false`)
- `INFINIMIND_TRACING_EXPORTER`: `otlp` or `console` (default `otlp`)
- `INFINIMIND_TRACING_OTLP_ENDPOINT`: required when tracing enabled with `otlp`
- `INFINIMIND_TRACING_SERVICE_NAME`: span service name (default `infinimind-service`)

## Key setup (no ambiguity)

`INFINIMIND_API_KEY` is the main bearer token.

You set it in `.env` (or shell env), and the same value must be used by:

1. Service container (`INFINIMIND_API_KEY`)
2. Curl/manual calls (`Authorization: Bearer <value>`)
3. OpenClaw bridge config (`plugins.entries.infinimind-bridge.config.apiKey`)

If any of those values differ, requests fail with `401`.

`INFINIMIND_ADMIN_API_KEY` is only for admin endpoint `/v1/admin/reembed`.

For manual shell calls (`curl`), load `.env` into the active shell:

```bash
set -a
source .env
set +a
```

OpenClaw resolves `${INFINIMIND_API_KEY}` from the environment of the process that starts OpenClaw.

Recommended key generation command:

```bash
python3 scripts/generate_api_keys.py --write-env
```

`OPENAI_API_KEY` must be created in OpenAI dashboard:

- https://platform.openai.com/api-keys

## OpenClaw configuration file changes

Target file: `~/.openclaw/openclaw.json`.

1. Add plugin path under `plugins.load.paths`.
2. Add plugin id to `plugins.allow`.
3. Set `plugins.slots.memory = "infinimind-bridge"`.
4. Configure `plugins.entries.infinimind-bridge.config`.
5. Set `identityFallback: "error"` (recommended). If you use `"configured-default"`, set `defaultUserId`.

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
- Forget workflow: `POST /v1/memory/forget` with `query` then delete via `memory_id`
- Dry-run migration: `POST /v1/admin/reembed` with `dry_run=true`
- Migration completeness: confirm `memories_v3` row count matches legacy `memories_v2` before cutover
