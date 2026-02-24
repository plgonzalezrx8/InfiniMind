#!/usr/bin/env bash
set -euo pipefail

# Docker-first smoke gate for authenticated service lifecycle + memory core paths.
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-${ROOT_DIR}/deploy/docker-compose.yml}"
BASE_URL="${INFINIMIND_BASE_URL:-http://127.0.0.1:8080}"
KEEP_STACK="${KEEP_STACK:-0}"

looks_like_external_secret() {
  local value="${1:-}"
  [[ "${value}" =~ ^sk- ]] && return 0
  [[ "${value}" =~ ^ghp_ ]] && return 0
  [[ "${value}" =~ ^github_pat_ ]] && return 0
  [[ "${value}" =~ ^AKIA[0-9A-Z]{16}$ ]] && return 0
  [[ "${value}" =~ ^ASIA[0-9A-Z]{16}$ ]] && return 0
  [[ "${value}" =~ ^xox[baprs]- ]] && return 0
  [[ "${value}" =~ ^AIza[0-9A-Za-z_-]{35}$ ]] && return 0
  return 1
}

export INFINIMIND_API_KEY="${INFINIMIND_API_KEY:-ci-dev-token}"
export INFINIMIND_ADMIN_API_KEY="${INFINIMIND_ADMIN_API_KEY:-ci-admin-token}"
export INFINIMIND_EMBEDDING_PROVIDER="${INFINIMIND_EMBEDDING_PROVIDER:-mock}"
export INFINIMIND_EMBEDDING_MODEL="${INFINIMIND_EMBEDDING_MODEL:-text-embedding-3-large}"
export OPENAI_API_KEY="${OPENAI_API_KEY:-}"
ALLOW_REAL_KEYS="${INFINIMIND_ALLOW_REAL_KEYS:-0}"

# CI and local smoke checks must avoid real provider credentials by default.
if [[ "${ALLOW_REAL_KEYS}" != "1" ]]; then
  for candidate in "${INFINIMIND_API_KEY}" "${INFINIMIND_ADMIN_API_KEY}" "${OPENAI_API_KEY}"; do
    if [[ -n "${candidate}" ]] && looks_like_external_secret "${candidate}"; then
      echo "Refusing docker smoke run with real-looking API keys. Use synthetic test tokens." >&2
      echo "Set INFINIMIND_ALLOW_REAL_KEYS=1 only when intentionally testing with live credentials." >&2
      exit 1
    fi
  done
fi

if [[ "${KEEP_STACK}" -eq 0 ]]; then
  cleanup() {
    docker compose -f "${COMPOSE_FILE}" down -v >/dev/null 2>&1 || true
  }
  trap cleanup EXIT
fi

docker compose -f "${COMPOSE_FILE}" up -d --build

for i in $(seq 1 60); do
  if curl -fsS "${BASE_URL}/v1/health" >/dev/null; then
    break
  fi

  if [[ "${i}" -eq 60 ]]; then
    docker logs infinimind-service || true
    echo "Service health check timed out." >&2
    exit 1
  fi

  sleep 2
done

curl -fsS -H "Authorization: Bearer ${INFINIMIND_API_KEY}" "${BASE_URL}/v1/ready" >/dev/null
curl -fsS "${BASE_URL}/v1/metrics" >/dev/null

store_response="$(curl -fsS \
  -H "Authorization: Bearer ${INFINIMIND_API_KEY}" \
  -H "Content-Type: application/json" \
  -X POST "${BASE_URL}/v1/memory/store" \
  -d '{"tenant_id":"default","user_id":"ci-user","agent_id":"main","text":"CI smoke memory record for store/recall/forget.","category":"fact"}')"

memory_id="$(python3 - <<'PY' <<<"${store_response}"
import json
import sys

payload = json.load(sys.stdin)
memory_id = payload.get("memory_id")
if not memory_id:
    raise SystemExit("store response missing memory_id")
print(memory_id)
PY
)"

recall_response="$(curl -fsS \
  -H "Authorization: Bearer ${INFINIMIND_API_KEY}" \
  -H "Content-Type: application/json" \
  -X POST "${BASE_URL}/v1/memory/recall" \
  -d '{"tenant_id":"default","user_id":"ci-user","agent_id":"main","query":"CI smoke memory record","limit":3,"rerank":"hybrid"}')"

python3 - <<'PY' <<<"${recall_response}"
import json
import sys

payload = json.load(sys.stdin)
if int(payload.get("count", 0)) < 1:
    raise SystemExit("recall response count < 1")
PY

forget_response="$(curl -fsS \
  -H "Authorization: Bearer ${INFINIMIND_API_KEY}" \
  -H "Content-Type: application/json" \
  -X POST "${BASE_URL}/v1/memory/forget" \
  -d "{\"tenant_id\":\"default\",\"user_id\":\"ci-user\",\"agent_id\":\"main\",\"memory_id\":\"${memory_id}\"}")"

python3 - <<'PY' <<<"${forget_response}"
import json
import sys

payload = json.load(sys.stdin)
if payload.get("action") != "deleted":
    raise SystemExit(f"forget action was not deleted: {payload}")
PY

echo "Docker smoke checks passed."
