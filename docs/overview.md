# Overview

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
- hook-based auto enrichment (`before_prompt_build` / `agent_end`)
- metrics and optional tracing
- CI-gated release automation

## What This Project Is Not

- It is not a fork of OpenClaw core.
- It does not patch OpenClaw internals.
- It does not implement OpenClaw `memory_get` semantics (intentionally out of scope).
- It is not a graph-memory system in current MVP.

## Current Status

Working MVP with:

- service and bridge test coverage
- executable OpenClaw bridge E2E script
- GitHub Actions quality gates
- Docker-first smoke flow
- operator runbooks for rollout and rollback

Release flow uses:

- `development` as beta/release-candidate branch
- `master` as production branch

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
