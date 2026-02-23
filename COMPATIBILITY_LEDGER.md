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

## 2026-02-23 — Feature: `feat(storage): LanceDB schema v2 and metadata index creation`
- Sources consulted:
  - https://github.com/openclaw/openclaw/blob/main/extensions/memory-lancedb/config.ts
  - https://github.com/openclaw/openclaw/blob/main/extensions/memory-lancedb/index.ts
- Decision:
  - Reuse the same OpenAI embedding model dimension mapping strategy and keep a LanceDB-first storage shape.
- Impact:
  - Storage schema is ready for additive metadata and hybrid retrieval phases.

## 2026-02-23 — Feature: `feat(store): /v1/memory/store + /v1/memory/batch-store with additive metadata`
- Sources consulted:
  - https://github.com/openclaw/openclaw/blob/main/extensions/memory-lancedb/index.ts
  - https://github.com/openclaw/openclaw/blob/main/extensions/memory-lancedb/openclaw.plugin.json
  - https://github.com/openclaw/openclaw/blob/main/docs/plugins/manifest.md
- Decision:
  - Preserve backward-compatible `text/importance/category` behavior while extending payloads additively.
- Impact:
  - OpenClaw bridge can map legacy and enriched store calls without breaking existing tool semantics.

## 2026-02-23 — Feature: `feat(recall-filters): hard filter stage (scope/sensitivity/ttl/time/category/tags)`
- Sources consulted:
  - https://github.com/openclaw/openclaw/blob/main/extensions/memory-lancedb/index.ts
  - https://github.com/openclaw/openclaw/blob/main/docs/concepts/memory.md
- Decision:
  - Apply mandatory policy checks before ranking, including sensitivity and context boundaries.
- Impact:
  - Recall path can be integrated safely with OpenClaw without relying on prompt-only isolation.
