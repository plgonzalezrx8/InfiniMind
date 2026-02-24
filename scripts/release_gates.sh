#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
  cat <<'USAGE'
Usage: scripts/release_gates.sh [--check <name>]...

Checks:
  service-tests
  bridge-quality
  openclaw-contract
  secret-scan
  docker-smoke
  openclaw-e2e

If no --check flags are provided, the default release set is:
  service-tests, bridge-quality, openclaw-contract, secret-scan
USAGE
}

run_service_tests() {
  python3 -m pytest services/infinimind-service/tests -q
}

run_bridge_quality() {
  (
    cd "${ROOT_DIR}/plugins/infinimind-openclaw-bridge"
    npm ci --no-audit --no-fund
    npm run typecheck
    npm run test
  )
}

run_openclaw_contract() {
  python3 -m pytest tests/openclaw -q
}

run_secret_scan() {
  "${ROOT_DIR}/scripts/secret_scan.sh"
}

run_docker_smoke() {
  "${ROOT_DIR}/scripts/docker_smoke.sh"
}

run_openclaw_e2e() {
  # Keep E2E pytest opt-in explicit so normal contract test runs stay lightweight.
  RUN_OPENCLAW_E2E=1 python3 -m pytest tests/openclaw/test_openclaw_cli_e2e.py -q
}

checks=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --check)
      checks+=("$2")
      shift 2
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

if [[ "${#checks[@]}" -eq 0 ]]; then
  # Default set mirrors required quality gates except the heavier docker/e2e checks.
  checks=(service-tests bridge-quality openclaw-contract secret-scan)
fi

for check in "${checks[@]}"; do
  # Run checks sequentially so the first failing gate stops the release flow immediately.
  case "${check}" in
    service-tests)
      run_service_tests
      ;;
    bridge-quality)
      run_bridge_quality
      ;;
    openclaw-contract)
      run_openclaw_contract
      ;;
    secret-scan)
      run_secret_scan
      ;;
    docker-smoke)
      run_docker_smoke
      ;;
    openclaw-e2e)
      run_openclaw_e2e
      ;;
    *)
      echo "Unknown check name: ${check}" >&2
      exit 2
      ;;
  esac

done

echo "Selected release gates passed: ${checks[*]}"
