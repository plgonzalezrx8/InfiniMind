#!/usr/bin/env bash
set -euo pipefail

# Executable OpenClaw + InfiniMind bridge E2E checks.
# The script runs against an isolated OpenClaw profile so local default state is untouched.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE="infinimind-ci"
BASE_URL="http://127.0.0.1:8080"
PLUGIN_PATH="${ROOT_DIR}/plugins/infinimind-openclaw-bridge"
OPENCLAW_BIN="${OPENCLAW_BIN:-openclaw}"
SKIP_COMPOSE=0
KEEP_STACK=0
SKIP_TOOL_EXEC=0

redact_value() {
  local raw="${1:-}"
  local n="${#raw}"
  if [[ "${n}" -le 8 ]]; then
    printf "***"
    return
  fi
  printf "%s***%s" "${raw:0:4}" "${raw: -4}"
}

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

usage() {
  cat <<'EOF'
Usage: scripts/openclaw_bridge_e2e.sh [options]

Options:
  --profile <name>        OpenClaw profile name (default: infinimind-ci)
  --base-url <url>        InfiniMind service base URL (default: http://127.0.0.1:8080)
  --plugin-path <path>    Local bridge plugin path
  --openclaw-bin <bin>    OpenClaw executable (default: openclaw or OPENCLAW_BIN)
  --skip-compose          Skip docker compose startup/teardown
  --keep-stack            Keep docker compose stack running after checks
  --skip-tool-exec        Skip bridge tool execution assertions
  -h, --help              Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile)
      PROFILE="$2"
      shift 2
      ;;
    --base-url)
      BASE_URL="$2"
      shift 2
      ;;
    --plugin-path)
      PLUGIN_PATH="$2"
      shift 2
      ;;
    --openclaw-bin)
      OPENCLAW_BIN="$2"
      shift 2
      ;;
    --skip-compose)
      SKIP_COMPOSE=1
      shift
      ;;
    --keep-stack)
      KEEP_STACK=1
      shift
      ;;
    --skip-tool-exec)
      SKIP_TOOL_EXEC=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 2
      ;;
  esac
done

if [[ ! -d "${PLUGIN_PATH}" ]]; then
  echo "Plugin path does not exist: ${PLUGIN_PATH}" >&2
  exit 1
fi

if [[ "${SKIP_COMPOSE}" -eq 0 ]]; then
  export INFINIMIND_API_KEY="${INFINIMIND_API_KEY:-infinimind-e2e-token}"
  export INFINIMIND_ADMIN_API_KEY="${INFINIMIND_ADMIN_API_KEY:-infinimind-e2e-admin-token}"
  export INFINIMIND_EMBEDDING_PROVIDER="${INFINIMIND_EMBEDDING_PROVIDER:-mock}"
  export INFINIMIND_EMBEDDING_MODEL="${INFINIMIND_EMBEDDING_MODEL:-text-embedding-3-large}"

  echo "Starting InfiniMind sidecar via Docker Compose..."
  docker compose -f "${ROOT_DIR}/deploy/docker-compose.yml" up -d --build

  if [[ "${KEEP_STACK}" -eq 0 ]]; then
    cleanup() {
      docker compose -f "${ROOT_DIR}/deploy/docker-compose.yml" down -v >/dev/null 2>&1 || true
    }
    trap cleanup EXIT
  fi
fi

if [[ -z "${INFINIMIND_API_KEY:-}" ]]; then
  # Generate an ephemeral token when compose is skipped and no caller token is provided.
  INFINIMIND_API_KEY="$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(24))
PY
)"
fi

if [[ -z "${INFINIMIND_ADMIN_API_KEY:-}" ]]; then
  INFINIMIND_ADMIN_API_KEY="${INFINIMIND_API_KEY}-admin"
fi

# CI safety: block external-provider-looking secrets unless explicitly overridden.
if [[ "${CI:-}" == "true" && "${INFINIMIND_ALLOW_REAL_KEYS:-0}" != "1" ]]; then
  for candidate in "${INFINIMIND_API_KEY}" "${INFINIMIND_ADMIN_API_KEY}" "${OPENAI_API_KEY:-}"; do
    if [[ -n "${candidate}" ]] && looks_like_external_secret "${candidate}"; then
      echo "Refusing to run with real-looking secrets in CI. Set INFINIMIND_ALLOW_REAL_KEYS=1 to override." >&2
      exit 1
    fi
  done
fi

echo "Using API token: $(redact_value "${INFINIMIND_API_KEY}")"
echo "Using admin token: $(redact_value "${INFINIMIND_ADMIN_API_KEY}")"

echo "Waiting for service health: ${BASE_URL}/v1/health"
for i in $(seq 1 60); do
  if curl -fsS "${BASE_URL}/v1/health" >/dev/null; then
    break
  fi
  if [[ "${i}" -eq 60 ]]; then
    echo "Health check timed out for ${BASE_URL}" >&2
    exit 1
  fi
  sleep 2
done

# Keep E2E config isolated from default ~/.openclaw state.
PROFILE_DIR="${HOME}/.openclaw-${PROFILE}"
CONFIG_PATH="${PROFILE_DIR}/openclaw.json"
mkdir -p "${PROFILE_DIR}"

echo "Writing isolated OpenClaw config: ${CONFIG_PATH}"
python3 - <<'PY' "${CONFIG_PATH}" "${PLUGIN_PATH}" "${BASE_URL}" "${INFINIMIND_API_KEY}"
import json
import pathlib
import sys

config_path = pathlib.Path(sys.argv[1])
plugin_path = str(pathlib.Path(sys.argv[2]).resolve())
base_url = sys.argv[3]
api_key = sys.argv[4]

config = {
    "plugins": {
        "enabled": True,
        "load": {"paths": [plugin_path]},
        "allow": ["infinimind-bridge"],
        "slots": {"memory": "infinimind-bridge"},
        "entries": {
            "infinimind-bridge": {
                "enabled": True,
                "config": {
                    "baseUrl": base_url,
                    "apiKey": api_key,
                    "timeoutMs": 4000,
                    "defaultScope": "user",
                    "includeSensitiveDefault": False,
                    "rerankDefault": "hybrid",
                    "fallbackMode": "legacy-compatible",
                    "identityFallback": "error",
                },
            }
        },
    }
}

config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
PY

echo "Running OpenClaw plugin checks on profile '${PROFILE}'..."
# Assert plugin discovery first so later checks fail for the correct root cause.
LIST_OUTPUT="$("${OPENCLAW_BIN}" --profile "${PROFILE}" plugins list)"
echo "${LIST_OUTPUT}"
if ! grep -q "infinimind-bridge" <<<"${LIST_OUTPUT}"; then
  echo "Bridge plugin was not discovered in plugins list output." >&2
  exit 1
fi

"${OPENCLAW_BIN}" --profile "${PROFILE}" plugins doctor

INFO_OUTPUT="$("${OPENCLAW_BIN}" --profile "${PROFILE}" plugins info infinimind-bridge)"
echo "${INFO_OUTPUT}"
if ! grep -q "infinimind-bridge" <<<"${INFO_OUTPUT}"; then
  echo "Bridge plugin info output did not include expected plugin id." >&2
  exit 1
fi

# Confirm slot ownership explicitly to catch stale config after plugin discovery succeeds.
SLOT_VALUE="$("${OPENCLAW_BIN}" --profile "${PROFILE}" config get plugins.slots.memory || true)"
if ! grep -q "infinimind-bridge" <<<"${SLOT_VALUE}"; then
  echo "Memory slot is not configured for infinimind-bridge in profile ${PROFILE}." >&2
  exit 1
fi

if [[ "${SKIP_TOOL_EXEC}" -eq 0 ]]; then
  TSX_BIN="${PLUGIN_PATH}/node_modules/.bin/tsx"
  if [[ ! -x "${TSX_BIN}" ]]; then
    echo "Bridge tool execution requires tsx at ${TSX_BIN}. Run npm ci in plugin directory." >&2
    exit 1
  fi

  echo "Executing bridge tool calls (store/recall/search/forget) against live service..."
  INFINIMIND_PLUGIN_PATH="${PLUGIN_PATH}" \
  INFINIMIND_BASE_URL="${BASE_URL}" \
  INFINIMIND_TOOL_API_KEY="${INFINIMIND_API_KEY}" \
  "${TSX_BIN}" <<'TS'
import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import path from "node:path";
import { pathToFileURL } from "node:url";

type ToolDef = {
  name: string;
  execute: (toolCallId: string, params: Record<string, unknown>) => Promise<Record<string, unknown>>;
};

class FakePluginApi {
  pluginConfig: Record<string, unknown>;
  logger = {
    info: (..._args: unknown[]) => {
      // Keep E2E output concise.
    },
  };
  tools: Record<string, ToolDef> = {};

  constructor(config: Record<string, unknown>) {
    this.pluginConfig = config;
  }

  registerTool(tool: ToolDef): void {
    this.tools[tool.name] = tool;
  }

  registerService(): void {
    // Service lifecycle is not required for request assertions.
  }
}

const pluginPath = process.env.INFINIMIND_PLUGIN_PATH;
const baseUrl = process.env.INFINIMIND_BASE_URL;
const apiKey = process.env.INFINIMIND_TOOL_API_KEY;
if (!pluginPath || !baseUrl || !apiKey) {
  throw new Error("Missing required env vars for bridge tool execution");
}

const pluginModule = await import(pathToFileURL(path.join(pluginPath, "index.ts")).href);
const bridgePlugin = pluginModule.default;
if (!bridgePlugin || typeof bridgePlugin.register !== "function") {
  throw new Error("Failed to load bridge plugin register function");
}

const api = new FakePluginApi({
  baseUrl,
  apiKey,
  timeoutMs: 4000,
  defaultScope: "user",
  includeSensitiveDefault: false,
  rerankDefault: "hybrid",
  fallbackMode: "legacy-compatible",
  identityFallback: "error",
});
bridgePlugin.register(api as never);

for (const toolName of ["memory_store", "memory_recall", "memory_search", "memory_forget"]) {
  if (!api.tools[toolName]) {
    throw new Error(`Bridge did not register expected tool: ${toolName}`);
  }
}

const suffix = randomUUID().slice(0, 8);
const userId = `e2e-user-${suffix}`;
const uniquePhrase = `e2e-remember-${suffix}`;

const storeResult = (await api.tools.memory_store.execute("tc-store", {
  userId,
  tenantId: "default",
  agentId: "main",
  category: "fact",
  text: `Bridge E2E memory ${uniquePhrase}`,
  tags: ["e2e", suffix],
})) as any;
assert.equal(storeResult.details.action, "created");
const memoryId = String(storeResult.details.id);
assert.ok(memoryId.length > 0, "store result missing memory id");

const recallResult = (await api.tools.memory_recall.execute("tc-recall", {
  userId,
  tenantId: "default",
  agentId: "main",
  query: uniquePhrase,
  limit: 5,
})) as any;
assert.ok(Number(recallResult.details.count) >= 1, "recall returned no memories");

const searchResult = (await api.tools.memory_search.execute("tc-search", {
  userId,
  tenantId: "default",
  agentId: "main",
  query: uniquePhrase,
  limit: 5,
})) as any;
assert.ok(Number(searchResult.details.count) >= 1, "memory_search returned no memories");

const forgetResult = (await api.tools.memory_forget.execute("tc-forget", {
  userId,
  tenantId: "default",
  agentId: "main",
  memoryId,
})) as any;
assert.equal(forgetResult.details.action, "deleted");
assert.equal(String(forgetResult.details.id), memoryId);

console.log("Bridge tool execution checks completed successfully.");
TS
fi

echo "OpenClaw bridge E2E checks completed successfully."
