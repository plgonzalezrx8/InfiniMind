# InfiniMind

InfiniMind is a standalone, Docker-first memory sidecar for OpenClaw.

It provides a dedicated memory service and bridge plugin so OpenClaw memory behavior can be enhanced without modifying OpenClaw core.

## Table of Contents

- [What This Project Is](#what-this-project-is)
- [What This Project Is Not](#what-this-project-is-not)
- [Current Status](#current-status)
- [Architecture](#architecture)
- [Repository Layout](#repository-layout)
- [Prerequisites](#prerequisites)
- [Quick Start (Docker-First)](#quick-start-docker-first)
- [Detailed Key and Environment Setup](#detailed-key-and-environment-setup)
- [Service API Reference](#service-api-reference)
- [OpenClaw Bridge Integration (Detailed)](#openclaw-bridge-integration-detailed)
- [Testing, CI Gates, and Release Flow](#testing-ci-gates-and-release-flow)
- [Observability](#observability)
- [Storage and Migration Semantics](#storage-and-migration-semantics)
- [Security and Safety Defaults](#security-and-safety-defaults)
- [Beta Testing Checklist](#beta-testing-checklist)
- [Troubleshooting](#troubleshooting)
- [Rollback](#rollback)
- [License](#license)

## What This Project Is

InfiniMind consists of two independent artifacts in this repository:

1. `infinimind-service`:
   - Python FastAPI service with authenticated memory APIs.
   - Docker-first runtime model.
   - LanceDB-backed persistence with migration safeguards.
2. `infinimind-openclaw-bridge`:
   - Separate OpenClaw plugin package.
   - Owns the OpenClaw `plugins.slots.memory` slot when enabled.
   - Translates OpenClaw memory tool calls into InfiniMind HTTP API calls.

Key capabilities:

- enriched memory storage
- strict policy filtering (scope/sensitivity/TTL/time)
- hybrid recall ranking
- forget workflow with explicit delete/candidate semantics
- metrics and optional tracing
- CI-gated release automation

## What This Project Is Not

- It is not a fork of OpenClaw core.
- It does not patch OpenClaw internals.
- It does not implement OpenClaw `memory_get` semantics (intentionally out of scope).
- It is not a graph-memory system in current MVP.

## Current Status

Working MVP on branch `codex/infinimind-mvp` with:

- service and bridge test coverage
- executable OpenClaw bridge E2E script
- GitHub Actions quality gates
- Docker-first smoke flow
- operator runbooks for rollout and rollback

## Architecture

High-level flow:

1. OpenClaw invokes memory tools (`memory_store`, `memory_recall`, `memory_forget`, `memory_search`).
2. `infinimind-bridge` plugin resolves identity, validates config, and forwards calls over HTTP.
3. InfiniMind service enforces policy, applies retrieval/ranking, and persists data.
4. Bridge returns OpenClaw-compatible response content/details.

Data-path summary:

- storage: LanceDB `memories_v3`
- migration: non-destructive `memories_v2 -> memories_v3` on startup when needed
- embedding: `openai` (default) or `mock` for CI/local deterministic tests

## Repository Layout

- `services/infinimind-service`: FastAPI service
- `plugins/infinimind-openclaw-bridge`: OpenClaw memory plugin
- `deploy/docker-compose.yml`: primary runtime path
- `deploy/openclaw-config.example.json`: OpenClaw config example
- `scripts/generate_api_keys.py`: key-generation helper
- `scripts/release_gates.sh`: unified local/CI release checks
- `scripts/docker_smoke.sh`: docker-first smoke gate
- `scripts/openclaw_bridge_e2e.sh`: profile-isolated OpenClaw E2E checks
- `docs/openclaw-integration.md`: deeper OpenClaw integration details
- `docs/operators/configuration.md`: operator config guide
- `docs/operators/release-checklist.md`: release gating checklist
- `docs/operators/rollback.md`: rollback runbook
- `COMPATIBILITY_LEDGER.md`: feature-level OpenClaw docs/source validation log

## Prerequisites

Required:

- Docker + Docker Compose
- Python 3.11+ (for local testing and scripts)
- Node.js 22+ (for bridge typecheck/tests)
- OpenClaw runtime/CLI (for bridge integration checks)

Optional but recommended:

- `jq` for shell JSON inspection
- Prometheus/Grafana for metric scraping/visualization
- OTLP collector if tracing is enabled

## Quick Start (Docker-First)

### 1. Create `.env`

```bash
cp .env.example .env
```

### 2. Generate service and admin tokens

```bash
python3 scripts/generate_api_keys.py --write-env
```

This writes or updates:

- `INFINIMIND_API_KEY`
- `INFINIMIND_ADMIN_API_KEY`

### 3. Add your OpenAI key

Create key in OpenAI dashboard:

- [https://platform.openai.com/api-keys](https://platform.openai.com/api-keys)

Set in `.env`:

```dotenv
OPENAI_API_KEY=your-openai-key
```

### 4. Export `.env` into current shell

```bash
set -a
source .env
set +a
```

### 5. Start service

```bash
docker compose -f deploy/docker-compose.yml up -d --build
```

### 6. Verify health/readiness/metrics

```bash
curl -s http://127.0.0.1:8080/v1/health
curl -s -H "Authorization: Bearer ${INFINIMIND_API_KEY}" http://127.0.0.1:8080/v1/ready
curl -s http://127.0.0.1:8080/v1/metrics | head
```

### 7. Verify store -> recall -> forget flow

Store:

```bash
STORE_RESPONSE="$(curl -s \
  -H "Authorization: Bearer ${INFINIMIND_API_KEY}" \
  -H "Content-Type: application/json" \
  -X POST http://127.0.0.1:8080/v1/memory/store \
  -d '{
    "tenant_id": "default",
    "user_id": "user-1",
    "agent_id": "main",
    "text": "Remember that user prefers concise summaries.",
    "category": "preference",
    "metadata": {"source": "quickstart"}
  }')"

echo "${STORE_RESPONSE}"
```

Extract `memory_id`:

```bash
MEMORY_ID="$(python3 - <<'PY' <<<"${STORE_RESPONSE}"
import json,sys
print(json.load(sys.stdin)["memory_id"])
PY
)"

echo "memory_id=${MEMORY_ID}"
```

Recall:

```bash
curl -s \
  -H "Authorization: Bearer ${INFINIMIND_API_KEY}" \
  -H "Content-Type: application/json" \
  -X POST http://127.0.0.1:8080/v1/memory/recall \
  -d '{
    "tenant_id": "default",
    "user_id": "user-1",
    "agent_id": "main",
    "query": "concise summaries",
    "limit": 5,
    "rerank": "hybrid",
    "fallback_mode": "legacy-compatible",
    "debug": true
  }'
```

Forget by `memory_id`:

```bash
curl -s \
  -H "Authorization: Bearer ${INFINIMIND_API_KEY}" \
  -H "Content-Type: application/json" \
  -X POST http://127.0.0.1:8080/v1/memory/forget \
  -d "{\"tenant_id\":\"default\",\"user_id\":\"user-1\",\"agent_id\":\"main\",\"memory_id\":\"${MEMORY_ID}\"}"
```

## Detailed Key and Environment Setup

### Environment contexts

InfiniMind uses three environment contexts. Keep them consistent.

1. Docker Compose context:
   - `.env` is read automatically for container interpolation.
2. Manual shell context:
   - `curl` commands read `${INFINIMIND_API_KEY}` from your active shell.
3. OpenClaw runtime context:
   - `apiKey: "${INFINIMIND_API_KEY}"` in OpenClaw config resolves from OpenClaw process environment.

If these contexts do not share the same token values, bridge calls fail with `401`.

### Variable matrix

| Variable | Required | Default | Used by | Notes |
| --- | --- | --- | --- | --- |
| `INFINIMIND_API_KEY` | Yes | `change-me-now` in compose fallback | service auth, bridge calls, curl | Must match across service, shell, and OpenClaw process env |
| `INFINIMIND_ADMIN_API_KEY` | Yes for admin endpoint | `change-me-now-admin` in compose fallback | `/v1/admin/reembed` auth | Keep separate from primary key in shared/prod |
| `OPENAI_API_KEY` | Yes when provider is OpenAI | none | embedding provider | Set in `.env` |
| `INFINIMIND_EMBEDDING_PROVIDER` | No | `openai` | service embedding backend | use `mock` for CI/local deterministic tests |
| `INFINIMIND_EMBEDDING_MODEL` | No | `text-embedding-3-large` | embedding generation | keep pinned for migration consistency |
| `INFINIMIND_DATA_DIR` | No | `/var/lib/infinimind` (container) | LanceDB storage | mount persistent volume in Docker |
| `INFINIMIND_TRACING_ENABLED` | No | `false` | tracing toggle | when `false`, tracing code path is disabled |
| `INFINIMIND_TRACING_EXPORTER` | No | `otlp` | tracing export | allowed: `otlp`, `console` |
| `INFINIMIND_TRACING_OTLP_ENDPOINT` | Conditionally | none | OTLP exporter | required if tracing enabled and exporter=`otlp` |
| `INFINIMIND_TRACING_SERVICE_NAME` | No | `infinimind-service` | tracing resource label | useful for multi-service observability |

### What token values should you use?

- local-only dev: any non-empty random token
- shared/staging/prod: randomly generated 32+ character secrets
- recommended helper:

```bash
python3 scripts/generate_api_keys.py --write-env
```

### Tracing quick examples

Console exporter:

```bash
export INFINIMIND_TRACING_ENABLED=true
export INFINIMIND_TRACING_EXPORTER=console
```

OTLP exporter:

```bash
export INFINIMIND_TRACING_ENABLED=true
export INFINIMIND_TRACING_EXPORTER=otlp
export INFINIMIND_TRACING_OTLP_ENDPOINT=http://otel-collector:4318/v1/traces
```

## Service API Reference

Base URL (default local): `http://127.0.0.1:8080`

Auth:

- `GET /v1/health` and `GET /v1/metrics` are public
- all other endpoints require `Authorization: Bearer <token>`

### `GET /v1/health`

Returns liveness status.

### `GET /v1/ready`

Returns readiness status for authenticated callers.

### `GET /v1/metrics`

Returns Prometheus exposition format.

### `POST /v1/memory/store`

Stores one memory record.

Core request fields:

- required: `user_id`, `text`
- common: `tenant_id` (default `default`), `agent_id` (default `main`), `category`, `importance`
- optional filters/context: `scope`, `channel_id`, `session_id`, `actor_id`, `tags`, `ttl_hours`, `dedupe_key`
- optional metadata blocks: `metadata`, `provenance`, `quality`

Response:

- `action`: `created` or `duplicate`
- `memory_id`
- `duplicate_of` when applicable

### `POST /v1/memory/batch-store`

Stores up to 200 records in one call.

Response contains:

- `created_count`
- `duplicate_count`
- `results[]` with per-item outcomes

### `POST /v1/memory/recall`

Retrieves memories with strict hard-filter stage before ranking.

Common request fields:

- required: `user_id`, `query`
- common controls: `limit`, `scope`, `categories`, `tags_any`, `min_importance`
- time filters: `since`, `until` (ISO datetime)
- trust/policy controls: `include_sensitive`, `trust_level`, `fallback_mode`
- ranking/debug: `rerank`, `debug`

Validation details:

- malformed datetimes return `422`
- `since > until` returns `422`

Response:

- `count`
- `memories[]` with `score`, `score_breakdown`, `metadata`, `quality`, provenance fields
- optional `debug` block when requested

### `POST /v1/memory/forget`

Delete behavior:

- by `memory_id`: scoped direct delete (`tenant_id`, `user_id`, `agent_id` boundary)
- by `query`: returns candidate list unless single high-confidence match is auto-deleted

Response `action` values:

- `deleted`
- `candidates`
- `not_found`
- `missing_param`

### `POST /v1/admin/reembed`

Admin-only endpoint for re-embedding safety workflow.

Request:

- `target_model_id`
- `dry_run` (optional)
- `limit` (optional)

Behavior:

- empty dataset: `processed=0`, `shadow_table=null`, status `200`
- non-empty: writes to a shadow table instead of in-place overwrite

## OpenClaw Bridge Integration (Detailed)

See detailed runbook: [docs/openclaw-integration.md](docs/openclaw-integration.md)

### Tool compatibility

- legacy-compatible tools:
  - `memory_store`
  - `memory_recall`
  - `memory_forget`
- dual-compat alias:
  - `memory_search` (maps to `/v1/memory/recall`)
- intentionally out of scope:
  - `memory_get`

### Bridge identity behavior

Identity resolution precedence in plugin:

1. `userId`
2. `actorId`
3. `sessionId`
4. `channelId`

Config behavior:

- default and recommended: `identityFallback: "error"`
- optional: `identityFallback: "configured-default"` with required `defaultUserId`

### Canonical OpenClaw config snippet

Target file: `~/.openclaw/openclaw.json` (JSON5)

```json5
{
  plugins: {
    enabled: true,
    load: {
      paths: ["/absolute/path/to/infinimind-openclaw-bridge"]
    },
    allow: ["infinimind-bridge"],
    slots: {
      memory: "infinimind-bridge"
    },
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
          fallbackMode: "legacy-compatible",
          identityFallback: "error"
          // If identityFallback is "configured-default":
          // defaultUserId: "explicit-fallback-user"
        }
      }
    }
  }
}
```

Validation notes aligned with OpenClaw docs:

- unknown plugin ids in `entries`, `allow`, `deny`, `slots` are validation errors
- plugin `configSchema` is validated without executing plugin code
- plugin infra/config changes should be followed by gateway restart for deterministic behavior

Source references:

- [OpenClaw plugin docs](https://raw.githubusercontent.com/openclaw/openclaw/main/docs/tools/plugin.md)
- [OpenClaw config overview](https://raw.githubusercontent.com/openclaw/openclaw/main/docs/gateway/configuration.md)
- [OpenClaw manifest rules](https://raw.githubusercontent.com/openclaw/openclaw/main/docs/plugins/manifest.md)

### Profile-isolated validation

Run isolated bridge E2E (does not touch default OpenClaw profile):

```bash
scripts/openclaw_bridge_e2e.sh --profile infinimind-ci
```

Useful flags:

```bash
scripts/openclaw_bridge_e2e.sh \
  --profile infinimind-ci \
  --base-url http://127.0.0.1:8080 \
  --plugin-path /absolute/path/to/plugins/infinimind-openclaw-bridge \
  --openclaw-bin /absolute/path/to/openclaw
```

## Testing, CI Gates, and Release Flow

### Local gate runner (single entrypoint)

Default gate set:

```bash
scripts/release_gates.sh
```

Runs:

- `service-tests`
- `bridge-quality`
- `openclaw-contract`
- `secret-scan`

Optional heavier gates:

```bash
OPENAI_API_KEY="" scripts/release_gates.sh --check docker-smoke
OPENCLAW_BIN="$(pwd)/plugins/infinimind-openclaw-bridge/node_modules/.bin/openclaw" \
scripts/release_gates.sh --check openclaw-e2e
```

### Hosted required checks (GitHub Actions)

- `service-tests`
- `bridge-quality`
- `openclaw-contract`
- `secret-scan`
- `docker-smoke`
- `openclaw-e2e`

Workflow files:

- `.github/workflows/quality-gates.yml`
- `.github/workflows/docker-smoke.yml`
- `.github/workflows/openclaw-e2e.yml`

### Release runbook

Use [docs/operators/release-checklist.md](docs/operators/release-checklist.md)

## Observability

### Metrics

Prometheus endpoint:

- `GET /v1/metrics`

Important metric series:

- `infinimind_http_requests_total`
- `infinimind_http_request_latency_seconds`
- `infinimind_recall_fallback_total`
- `infinimind_policy_note_total`
- `infinimind_store_results_total`

### Tracing

Tracing is optional and disabled by default.

Supported exporters:

- `console`
- `otlp` (requires `INFINIMIND_TRACING_OTLP_ENDPOINT`)

## Storage and Migration Semantics

Storage table:

- active: `memories_v3`
- legacy: `memories_v2`

Migration behavior:

- startup migrates from `v2` to `v3` only when `v2` exists and `v3` does not
- migration is forward-only and non-destructive
- `memories_v2` is retained for rollback/debug
- migration includes scanned/migrated count integrity checks

Metadata behavior:

- metadata stored as JSON (`metadata_json`)
- recall fails safe for malformed JSON and normalizes to safe defaults

## Security and Safety Defaults

- API auth is required for mutating/recall/admin routes
- admin operations require `INFINIMIND_ADMIN_API_KEY`
- strict identity default in bridge (`identityFallback: "error"`)
- sensitivity gates enforce trust requirements
- fallback behavior is safe and scoped
- CI and scripts redact tokens and block real-looking secrets by default

Secret scanning:

```bash
scripts/secret_scan.sh
```

## Beta Testing Checklist

Minimum beta entry criteria:

1. Service tests pass.
2. Bridge typecheck/tests pass.
3. OpenClaw contract tests pass.
4. Secret scan passes.
5. Docker smoke gate passes in CI.
6. OpenClaw E2E gate passes with isolated profile.
7. OpenClaw slot points to `infinimind-bridge`.
8. Store/recall/forget manual sanity checks pass in target environment.

Recommended beta canary sequence:

1. Enable bridge for limited canary users/agents.
2. Keep `fallbackMode: "legacy-compatible"` during first canary.
3. Monitor recall fallback and policy note counters.
4. Monitor p95 latency and error rates.
5. Expand only after 24h stable canary metrics.

## Troubleshooting

### `401` from bridge/service

Cause:

- token mismatch between service, shell calls, and OpenClaw runtime interpolation

Fix:

1. verify `INFINIMIND_API_KEY` in `.env`
2. verify shell export with `set -a; source .env; set +a`
3. verify OpenClaw process env contains same value
4. verify bridge config `apiKey` matches interpolation key

### `openclaw plugins list` does not show `infinimind-bridge`

Fix:

1. check `plugins.load.paths`
2. verify plugin directory path is correct
3. run `npm ci --no-audit --no-fund` in `plugins/infinimind-openclaw-bridge`

### `openclaw plugins doctor` shows plugin warning about id hint mismatch

Observed warning shape:

- manifest id is `infinimind-bridge`
- entry hint may show `openclaw-bridge`

Interpretation:

- this warning is non-fatal when plugin id is discovered and loaded correctly
- verify final resolved plugin id from `openclaw plugins info infinimind-bridge`

### Docker smoke fails with daemon error

Cause:

- Docker daemon not running or unavailable socket

Fix:

1. start Docker Desktop / daemon
2. validate with `docker ps`
3. rerun `scripts/release_gates.sh --check docker-smoke`

### Docker smoke fails with port conflict on `127.0.0.1:8080`

Cause:

- another service already bound to port `8080`

Fix options:

1. stop conflicting service
2. rerun smoke in CI where environment is clean
3. run OpenClaw E2E with `--skip-compose` against an alternate local port

### Recall request returns `422`

Likely causes:

- invalid datetime format in `since` or `until`
- `since` later than `until`

Fix:

- use ISO datetimes and valid chronological ranges

## Rollback

Primary rollback action:

1. set `plugins.slots.memory` back to `memory-core`
2. optionally disable `infinimind-bridge`
3. restart OpenClaw gateway

Full runbook:

- [docs/operators/rollback.md](docs/operators/rollback.md)

## Additional Documentation

- [OpenClaw Integration](docs/openclaw-integration.md)
- [Operator Configuration](docs/operators/configuration.md)
- [Release Checklist](docs/operators/release-checklist.md)
- [Compatibility Ledger](COMPATIBILITY_LEDGER.md)

## License

MIT License. See [LICENSE](LICENSE).
