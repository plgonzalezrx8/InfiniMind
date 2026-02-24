#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Running Node dependency audit (bridge production deps)..."
(
  cd "${ROOT_DIR}/plugins/infinimind-openclaw-bridge"
  # package-lock-only mode keeps CI deterministic and avoids unnecessary install work.
  npm audit --omit=dev --audit-level=high --package-lock-only
)

echo "Running Python dependency audit (service project)..."
python3 -m pip install --quiet pip-audit
python3 -m pip install --quiet -e "${ROOT_DIR}/services/infinimind-service"
python3 -m pip_audit --progress-spinner off --strict "${ROOT_DIR}/services/infinimind-service"

echo "Dependency hygiene checks passed."
