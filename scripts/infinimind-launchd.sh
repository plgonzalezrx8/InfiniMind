#!/usr/bin/env bash
set -euo pipefail

# Launchd wrapper for the local InfiniMind service.
# - Loads runtime secrets/config from ~/InfiniMind/.env
# - Forces a user-writable data directory default for non-Docker runs
# - Starts uvicorn bound to localhost for local OpenClaw bridge usage

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_DIR="${ROOT_DIR}/services/infinimind-service"
ENV_FILE="${ROOT_DIR}/.env"

# Keep common user binary locations available under launchd's restricted PATH.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"

# Import service configuration and tokens from the project env file.
if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
fi

# Ensure local persistence defaults to a writable path outside /var.
export INFINIMIND_DATA_DIR="${INFINIMIND_DATA_DIR:-${ROOT_DIR}/.data}"
mkdir -p "${INFINIMIND_DATA_DIR}"

cd "${SERVICE_DIR}"

# Launchd can resolve a different python3 than interactive shells.
# Pin the interpreter known to have the InfiniMind runtime dependencies.
PYTHON_BIN_DEFAULT="/Library/Frameworks/Python.framework/Versions/3.14/bin/python3"
if [[ -x "${PYTHON_BIN_DEFAULT}" ]]; then
  PYTHON_BIN="${PYTHON_BIN_DEFAULT}"
else
  PYTHON_BIN="$(command -v python3)"
fi

# Fail fast with a clear error when dependencies are missing from the selected interpreter.
if ! "${PYTHON_BIN}" -c "import uvicorn, fastapi, lancedb" >/dev/null 2>&1; then
  echo "Selected Python interpreter is missing InfiniMind dependencies: ${PYTHON_BIN}" >&2
  exit 1
fi

# Replace shell with the API server process for clean signal handling.
exec "${PYTHON_BIN}" -m uvicorn app.main:app --host 127.0.0.1 --port 8080
