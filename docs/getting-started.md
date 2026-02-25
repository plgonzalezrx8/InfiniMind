# Getting Started

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
