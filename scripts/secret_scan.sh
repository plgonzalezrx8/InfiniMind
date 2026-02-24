#!/usr/bin/env bash
set -euo pipefail

# Scan tracked repository files only, so build artifacts do not affect gate results.
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

PATTERN_PRIMARY='sk-[A-Za-z0-9_-]{20,}'
PATTERN_SECONDARY='(AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-|AIza[0-9A-Za-z\-_]{35})'

primary_hits=()
secondary_hits=()

while IFS= read -r -d '' tracked_file; do
  if grep -qE "${PATTERN_PRIMARY}" "${tracked_file}" 2>/dev/null; then
    primary_hits+=("${tracked_file}")
  fi

  if grep -qE "${PATTERN_SECONDARY}" "${tracked_file}" 2>/dev/null; then
    secondary_hits+=("${tracked_file}")
  fi
done < <(git ls-files -z)

if [[ "${#primary_hits[@]}" -gt 0 || "${#secondary_hits[@]}" -gt 0 ]]; then
  echo "Secret-like patterns detected in tracked files:" >&2

  if [[ "${#primary_hits[@]}" -gt 0 ]]; then
    echo "  pattern=sk-*" >&2
    printf '%s\n' "${primary_hits[@]}" | sort -u >&2
  fi

  if [[ "${#secondary_hits[@]}" -gt 0 ]]; then
    echo "  pattern=cloud/provider tokens" >&2
    printf '%s\n' "${secondary_hits[@]}" | sort -u >&2
  fi

  exit 1
fi

echo "No secret-like patterns detected."
