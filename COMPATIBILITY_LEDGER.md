# Compatibility Ledger

This ledger records OpenClaw documentation/source checks performed before each feature commit.

## 2026-02-23 — Feature: `chore(repo): initial scaffold and compatibility ledger`
- Sources consulted:
  - https://github.com/openclaw/openclaw/blob/main/docs/tools/plugin.md
  - https://github.com/openclaw/openclaw/blob/main/extensions/memory-lancedb/index.ts
- Decision:
  - Keep integration external to OpenClaw core and implement a separate bridge plugin with OpenClaw-compatible memory tool naming.
- Impact:
  - Repository scaffold separates service and plugin deliverables from the start.

## 2026-02-23 — Feature: `feat(service): FastAPI skeleton, typed settings, auth middleware, health/ready`
- Sources consulted:
  - https://github.com/openclaw/openclaw/blob/main/docs/gateway/configuration.md
  - https://github.com/openclaw/openclaw/blob/main/extensions/memory-core/index.ts
- Decision:
  - Keep auth simple and token-based to match plugin-to-service call patterns while preserving external integration boundaries.
- Impact:
  - Service can be health-checked and protected before retrieval/storage logic lands.

## 2026-02-23 — Feature: `feat(docker): production Dockerfile, compose stack, persistent volume wiring`
- Sources consulted:
  - https://github.com/openclaw/openclaw/blob/main/docs/tools/plugin.md
  - https://github.com/openclaw/openclaw/blob/main/docs/cli/plugins.md
- Decision:
  - Preserve a sidecar deployment model and keep explicit restart expectations for OpenClaw plugin config changes.
- Impact:
  - Docker-first runtime aligns with operations while keeping OpenClaw plugin behavior predictable.
