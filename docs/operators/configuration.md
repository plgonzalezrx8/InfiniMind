# Operator Configuration Guide

This guide is the operations runbook for deploying and running InfiniMind in Docker-first environments with OpenClaw bridge integration.

## Scope

This guide covers:

- environment and key setup
- Docker deployment and runtime verification
- OpenClaw bridge rollout configuration
- local/CI parity quality gates
- canary rollout and production hardening checks
- incident troubleshooting for common operator failures

## Deployment Models

### Model A: Local operator validation

- service on host: `http://127.0.0.1:8080`
- OpenClaw uses local plugin path
- profile-isolated bridge validation recommended

### Model B: Docker-first sidecar in shared environments

- service runs via compose stack
- persistent volume mounted for LanceDB data
- OpenClaw process configured with bridge slot ownership

### Model C: CI validation mode

- mock embeddings by default
- synthetic keys only
- automated checks via GitHub workflows and `scripts/release_gates.sh`

## Quick Operator Boot Sequence

From repository root:

```bash
cp .env.example .env
python3 scripts/generate_api_keys.py --write-env
# Set OPENAI_API_KEY in .env if using openai embeddings

docker compose -f deploy/docker-compose.yml up -d --build
```

Verify startup:

```bash
set -a
source .env
set +a

curl -s http://127.0.0.1:8080/v1/health
curl -s -H "Authorization: Bearer ${INFINIMIND_API_KEY}" http://127.0.0.1:8080/v1/ready
curl -s http://127.0.0.1:8080/v1/metrics | head
```

## Environment Variable Matrix

### Core service/auth variables

| Variable | Required | Default | Purpose | Operator notes |
| --- | --- | --- | --- | --- |
| `INFINIMIND_API_KEY` | yes | compose fallback for local dev only | primary bearer auth | must match service, curl, and OpenClaw runtime interpolation |
| `INFINIMIND_ADMIN_API_KEY` | yes for admin endpoint use | compose fallback for local dev only | admin auth for `/v1/admin/reembed` | keep distinct from primary in staging/prod |
| `OPENAI_API_KEY` | required when provider is `openai` | none | OpenAI embedding auth | generated in OpenAI dashboard |

### Runtime/storage variables

| Variable | Required | Default | Purpose | Operator notes |
| --- | --- | --- | --- | --- |
| `INFINIMIND_DATA_DIR` | no | `/var/lib/infinimind` in container | LanceDB storage path | mount persistent volume |
| `INFINIMIND_EMBEDDING_PROVIDER` | no | `openai` | embedding backend | set `mock` for CI/local deterministic tests |
| `INFINIMIND_EMBEDDING_MODEL` | no | `text-embedding-3-large` | embedding model ID | keep pinned for migration consistency |

### Observability variables

| Variable | Required | Default | Purpose | Operator notes |
| --- | --- | --- | --- | --- |
| `INFINIMIND_TRACING_ENABLED` | no | `false` | tracing switch | when false, tracing path disabled |
| `INFINIMIND_TRACING_EXPORTER` | no | `otlp` | tracing exporter | `console` and `otlp` supported |
| `INFINIMIND_TRACING_OTLP_ENDPOINT` | conditional | none | OTLP endpoint | required for `otlp` exporter |
| `INFINIMIND_TRACING_SERVICE_NAME` | no | `infinimind-service` | trace resource label | use env-specific naming if needed |

## Key Setup and Ownership Mapping

Use helper:

```bash
python3 scripts/generate_api_keys.py --write-env
```

Token mapping requirements:

1. service container reads `INFINIMIND_API_KEY`
2. manual calls use `Authorization: Bearer ${INFINIMIND_API_KEY}`
3. OpenClaw bridge config uses `apiKey: "${INFINIMIND_API_KEY}"`

If values diverge, bridge calls fail with `401`.

For shell sessions running manual commands:

```bash
set -a
source .env
set +a
```

OpenAI key source:

- [https://platform.openai.com/api-keys](https://platform.openai.com/api-keys)

## Docker Runtime Operations

### Start

```bash
docker compose -f deploy/docker-compose.yml up -d --build
```

### Stop

```bash
docker compose -f deploy/docker-compose.yml down
```

### Stop and remove volume (destructive)

```bash
docker compose -f deploy/docker-compose.yml down -v
```

Use `down -v` only when intentionally resetting local data.

### Logs

```bash
docker logs infinimind-service --tail 200
```

### Health/ready checks

```bash
curl -s http://127.0.0.1:8080/v1/health
curl -s -H "Authorization: Bearer ${INFINIMIND_API_KEY}" http://127.0.0.1:8080/v1/ready
```

## OpenClaw Bridge Rollout Configuration

Primary integration reference:

- [../openclaw-integration.md](../openclaw-integration.md)

Target file:

- `~/.openclaw/openclaw.json`

Required changes:

1. add bridge path under `plugins.load.paths`
2. add bridge id to `plugins.allow`
3. set `plugins.slots.memory = "infinimind-bridge"`
4. configure `plugins.entries.infinimind-bridge.config`
5. prefer `identityFallback: "error"`

If using `identityFallback: "configured-default"`, you must set `defaultUserId`.

Reference example:

- [../../deploy/openclaw-config.example.json](../../deploy/openclaw-config.example.json)

## Validation Workflows

### Local/CI parity gates

Run same scripted checks used by CI:

```bash
scripts/release_gates.sh
scripts/release_gates.sh --check dependency-hygiene
scripts/release_gates.sh --check docker-smoke
OPENCLAW_BIN="$(pwd)/plugins/infinimind-openclaw-bridge/node_modules/.bin/openclaw" \
scripts/release_gates.sh --check openclaw-e2e
```

Notes:

- `docker-smoke` blocks real-looking external secrets by default.
- default smoke mode is synthetic (`INFINIMIND_SMOKE_KEY_MODE=synthetic`).
- use `INFINIMIND_SMOKE_KEY_MODE=environment INFINIMIND_ALLOW_REAL_KEYS=1` only for intentional live-key smoke runs.
- `openclaw-e2e` uses isolated profile and should not mutate default OpenClaw profile state.

### Manual OpenClaw checks

```bash
openclaw --profile infinimind-ci plugins list
openclaw --profile infinimind-ci plugins doctor
openclaw --profile infinimind-ci plugins info infinimind-bridge
openclaw --profile infinimind-ci config get plugins.slots.memory
```

### Bridge E2E script

```bash
scripts/openclaw_bridge_e2e.sh --profile infinimind-ci
```

## Operational Verification Matrix

### API/function checks

- `GET /v1/health` returns `status=ok`
- `GET /v1/ready` (auth) returns `status=ready`
- `GET /v1/metrics` returns Prometheus payload
- `POST /v1/memory/store` creates/dedupes as expected
- `POST /v1/memory/recall` returns scoped/policy-compliant memories
- `POST /v1/memory/forget` supports delete and candidate flows
- `POST /v1/admin/reembed` dry-run and empty-store behavior verified

### Migration checks

- `memories_v2` retained (non-destructive)
- `memories_v3` exists and is active
- row-count integrity holds when migration path is exercised

### OpenClaw checks

- plugin discovered: `infinimind-bridge`
- memory slot bound to bridge
- identity fallback mode explicitly configured
- tool compatibility present: `memory_store`, `memory_recall`, `memory_forget`, `memory_search`

## Canary Rollout Steps

1. deploy sidecar with production-equivalent settings
2. enable bridge for limited tenant/user/agent cohort
3. keep `fallbackMode: "legacy-compatible"` in initial canary
4. monitor metrics and latency
5. expand cohort only after stable safety/latency windows

Monitor minimum metrics:

- `infinimind_http_requests_total`
- `infinimind_http_request_latency_seconds`
- `infinimind_recall_fallback_total`
- `infinimind_policy_note_total`
- `infinimind_store_results_total`

## Beta Go/No-Go Procedure

### Preflight

1. run all required checks:
   - `scripts/release_gates.sh`
   - `scripts/release_gates.sh --check dependency-hygiene`
   - `scripts/release_gates.sh --check docker-smoke`
   - `scripts/release_gates.sh --check openclaw-e2e`
2. verify OpenClaw slot state:
   - `openclaw --profile infinimind-ci config get plugins.slots.memory`
3. verify bridge tool execution path:
   - `scripts/openclaw_bridge_e2e.sh --profile infinimind-ci`

### Live beta rollout

1. start with one controlled cohort.
2. run for at least 24h with `fallbackMode: "legacy-compatible"`.
3. track latency/error/policy metrics every 15m.
4. promote only when no P1/P2 findings appear in logs, metrics, or gates.

### Incident rollback trigger

Rollback immediately when one of these occurs:

1. sustained auth failures (`401`) or server errors (`5xx`) from bridge traffic.
2. plugin/slot drift where memory slot no longer resolves to `infinimind-bridge`.
3. any policy leakage signal involving sensitive data.

Rollback action path:

1. set `plugins.slots.memory` back to `memory-core`.
2. restart OpenClaw.
3. capture logs + metrics + failing commands for incident record.

## Incident Troubleshooting

### `401` authentication failures

Checks:

1. validate service `INFINIMIND_API_KEY`
2. validate OpenClaw process env interpolation source
3. validate bridge `config.apiKey` value resolution

### Docker daemon unavailable

Symptom:

- `Cannot connect to the Docker daemon ...`

Actions:

1. start Docker daemon/Desktop
2. run `docker ps`
3. rerun docker smoke gate

### Port 8080 already in use

Symptom:

- bind failure for `127.0.0.1:8080`

Actions:

1. stop conflicting process/container
2. or run bridge E2E with `--skip-compose` against alternate service port
3. rely on hosted CI docker-smoke for clean isolated validation

### Bridge not loaded

Actions:

1. verify plugin path exists
2. run `npm ci` in bridge directory
3. verify `allow` list and entry id use `infinimind-bridge`

### Slot misrouted

Actions:

1. verify `plugins.slots.memory` setting
2. rerun `openclaw plugins doctor`
3. restart OpenClaw after config updates

### Non-blocking plugin id hint warning

A warning about entry hint `openclaw-bridge` vs manifest `infinimind-bridge` can appear. Treat as advisory if `plugins info infinimind-bridge` and slot checks pass.

## Security Hardening Defaults

- use long random secrets for API/admin keys
- avoid printing raw tokens in automation logs
- keep bridge config strict (no unknown keys)
- keep `identityFallback: "error"` unless explicitly justified
- run `scripts/secret_scan.sh` before release

## Release Gate and Merge Guidance

Use full release checklist:

- [release-checklist.md](release-checklist.md)

Before merge:

1. local gate parity complete
2. hosted checks green
3. canary owner and rollback owner identified
4. rollback plan validated

## Related Documentation

- [README](../../README.md)
- [OpenClaw Integration](../openclaw-integration.md)
- [Beta Readiness Audit](beta-readiness-audit.md)
- [Beta Readiness Report](beta-readiness-report.md)
- [Release Checklist](release-checklist.md)
- [Rollback Guide](rollback.md)
