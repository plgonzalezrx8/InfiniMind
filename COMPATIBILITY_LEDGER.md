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

## 2026-02-23 — Feature: `feat(recall-hybrid): vector+lexical candidate generation and weighted rerank`
- Sources consulted:
  - https://github.com/openclaw/openclaw/blob/main/docs/concepts/memory.md
  - https://github.com/openclaw/openclaw/blob/main/extensions/memory-lancedb/index.ts
- Decision:
  - Implement hybrid fusion using BM25-style lexical scoring + vector similarity with explicit weighting.
- Impact:
  - Recall can now serve both semantic paraphrases and exact-token queries from one API path.

## 2026-02-23 — Feature: `feat(recall-packaging): provenance/confidence + debug score breakdown`
- Sources consulted:
  - https://github.com/openclaw/openclaw/blob/main/extensions/memory-lancedb/index.ts
  - https://github.com/openclaw/openclaw/blob/main/docs/concepts/memory.md
- Decision:
  - Return structured recall details with explicit scoring diagnostics for auditability.
- Impact:
  - OpenClaw bridge can expose explainable memory context without changing core OpenClaw behavior.

## 2026-02-23 — Feature: `feat(policy): trust gates and safe fallback behavior`
- Sources consulted:
  - https://github.com/openclaw/openclaw/blob/main/docs/concepts/memory.md
  - https://github.com/openclaw/openclaw/blob/main/extensions/memory-lancedb/index.ts
- Decision:
  - Enforce high-sensitivity recall only for high-trust callers and apply safe fallback that never bypasses hard boundaries.
- Impact:
  - Retrieval can expand candidate coverage without introducing cross-context or sensitivity leakage.

## 2026-02-23 — Feature: `feat(bridge): OpenClaw plugin manifest/schema and HTTP client bridge`
- Sources consulted:
  - https://github.com/openclaw/openclaw/blob/main/docs/plugins/manifest.md
  - https://github.com/openclaw/openclaw/blob/main/extensions/memory-lancedb/openclaw.plugin.json
  - https://github.com/openclaw/openclaw/blob/main/extensions/memory-lancedb/config.ts
- Decision:
  - Implement strict bridge manifest/config schema with env-var interpolation and bounded timeouts.
- Impact:
  - OpenClaw can validate bridge config at startup without executing plugin code.

## 2026-02-23 — Feature: `feat(bridge-tools): legacy-compatible memory_store/memory_recall tool mapping`
- Sources consulted:
  - https://github.com/openclaw/openclaw/blob/main/extensions/memory-lancedb/index.ts
  - https://github.com/openclaw/openclaw/blob/main/docs/tools/plugin.md
- Decision:
  - Keep OpenClaw tool names and legacy params while forwarding additive fields to InfiniMind.
- Impact:
  - Existing OpenClaw agent behaviors can migrate to external memory service without prompt changes.

## 2026-02-23 — Feature: `feat(observability): metrics, traces, policy counters, latency histograms`
- Sources consulted:
  - https://github.com/openclaw/openclaw/blob/main/extensions/diagnostics-otel/openclaw.plugin.json
  - https://github.com/openclaw/openclaw/blob/main/docs/tools/plugin.md
- Decision:
  - Add explicit service-side Prometheus metrics and policy counters independent of OpenClaw core internals.
- Impact:
  - Operators can monitor recall quality/safety and endpoint latency directly in sidecar deployments.

## 2026-02-23 — Feature: `feat(reembed): admin re-embed endpoint with embedding version safety`
- Sources consulted:
  - https://github.com/openclaw/openclaw/blob/main/docs/concepts/memory.md
  - https://github.com/openclaw/openclaw/blob/main/extensions/memory-lancedb/config.ts
  - https://github.com/openclaw/openclaw/blob/main/extensions/memory-lancedb/index.ts
- Decision:
  - Use shadow-table re-embedding to avoid in-place vector overwrite during model migrations.
- Impact:
  - Operators can validate new embedding versions safely before any retrieval cutover.

## 2026-02-23 — Feature: `test(service): unit/integration coverage for store/recall/policy`
- Sources consulted:
  - https://github.com/openclaw/openclaw/blob/main/extensions/memory-lancedb/index.ts
  - https://github.com/openclaw/openclaw/blob/main/docs/concepts/memory.md
- Decision:
  - Mirror legacy memory tool behavior in API assertions while verifying new policy and fallback controls.
- Impact:
  - Service regressions around compatibility, safety, and recall packaging are now test-addressable.

## 2026-02-23 — Feature: `test(openclaw): plugin config validation + e2e bridge tests with OpenClaw`
- Sources consulted:
  - https://github.com/openclaw/openclaw/blob/main/docs/plugins/manifest.md
  - https://github.com/openclaw/openclaw/blob/main/docs/tools/plugin.md
- Decision:
  - Add repository-local contract tests for bridge manifest strictness and slot wiring, plus an executable E2E run script.
- Impact:
  - OpenClaw integration regressions can be detected before runtime deployment.

## 2026-02-23 — Feature: `test(perf): latency and quality benchmark harness`
- Sources consulted:
  - https://github.com/openclaw/openclaw/blob/main/docs/concepts/memory.md
  - https://github.com/openclaw/openclaw/blob/main/extensions/memory-lancedb/index.ts
- Decision:
  - Add a standalone benchmark harness comparing rerank modes with p50/p95 and top-1 hit-rate proxies.
- Impact:
  - Teams can quantify recall quality and latency tradeoffs during canaries and regressions.

## 2026-02-23 — Feature: `docs(ops): OpenClaw config guide, rollout/canary, rollback runbook`
- Sources consulted:
  - https://github.com/openclaw/openclaw/blob/main/docs/gateway/configuration.md
  - https://github.com/openclaw/openclaw/blob/main/docs/tools/plugin.md
  - https://github.com/openclaw/openclaw/blob/main/docs/plugins/manifest.md
- Decision:
  - Document exact config keys and operational sequences for plugin slot cutover and rollback.
- Impact:
  - Operators can deploy and rollback InfiniMind integration with predictable, validated steps.

## 2026-02-23 — Feature: `chore(release): final hardening and merge checklist`
- Sources consulted:
  - https://github.com/openclaw/openclaw/blob/main/docs/gateway/configuration.md
  - https://github.com/openclaw/openclaw/blob/main/docs/tools/plugin.md
- Decision:
  - Add release checklist, tighten operator docs, and harden runtime with graceful LanceDB fallback for unsupported environments.
- Impact:
  - Branch is merge-ready with documented verification and rollback controls.

## 2026-02-23 — Feature: `chore(deploy): remove obsolete docker compose version field`
- Sources consulted:
  - https://github.com/openclaw/openclaw/blob/main/docs/gateway/configuration.md
- Decision:
  - Remove obsolete compose `version` key to avoid noisy deploy-time warnings.
- Impact:
  - Cleaner operator output during sidecar startup and validation.

## 2026-02-23 — Feature: `docs(readme): complete run instructions + MIT license`
- Sources consulted:
  - https://github.com/openclaw/openclaw/blob/main/docs/gateway/configuration.md
  - https://github.com/openclaw/openclaw/blob/main/docs/tools/plugin.md
- Decision:
  - Consolidate all operator/developer run instructions into root README and add explicit MIT licensing.
- Impact:
  - Repository now has a single comprehensive setup/run reference and clear open-source licensing.

## 2026-02-23 — Feature: `docs(clarity): explicit token setup and usage guidance`
- Sources consulted:
  - https://github.com/openclaw/openclaw/blob/main/docs/gateway/configuration.md
  - https://github.com/openclaw/openclaw/blob/main/docs/tools/plugin.md
- Decision:
  - Document exact key ownership and mapping across service env, curl auth headers, and OpenClaw bridge config.
- Impact:
  - Operators now have unambiguous setup steps for `INFINIMIND_API_KEY` and `INFINIMIND_ADMIN_API_KEY`.

## 2026-02-23 — Feature: `docs+tooling: API key generation script and key sourcing guidance`
- Sources consulted:
  - https://github.com/openclaw/openclaw/blob/main/docs/gateway/configuration.md
  - https://github.com/openclaw/openclaw/blob/main/docs/tools/plugin.md
- Decision:
  - Add a local script to generate InfiniMind service/admin bearer keys and document OpenAI key acquisition explicitly.
- Impact:
  - Setup instructions now clearly answer where each key comes from and how to keep values aligned across service, curl, and OpenClaw bridge config.

## 2026-02-24 — Feature: `fix(bridge): correct package dependency wiring for installable bridge plugin`
- Sources consulted:
  - https://github.com/openclaw/openclaw/blob/main/docs/tools/plugin.md
  - https://github.com/openclaw/openclaw/blob/main/extensions/memory-lancedb/package.json
- Decision:
  - Align bridge package metadata with OpenClaw extension packaging conventions and add explicit typecheck tooling.
- Impact:
  - Bridge package now installs successfully and can be validated deterministically before integration.

## 2026-02-24 — Feature: `fix(bridge): enforce explicit identity resolution and remove implicit default-user`
- Sources consulted:
  - https://github.com/openclaw/openclaw/blob/main/docs/tools/plugin.md
  - https://github.com/openclaw/openclaw/blob/main/extensions/memory-lancedb/config.ts
- Decision:
  - Keep strict plugin config validation while requiring explicit identity resolution with optional configured fallback.
- Impact:
  - Bridge no longer silently collapses requests into a shared default user namespace.

## 2026-02-24 — Feature: `feat(service): add memory forget endpoint and scoped delete behavior`
- Sources consulted:
  - https://github.com/openclaw/openclaw/blob/main/extensions/memory-lancedb/index.ts
  - https://github.com/openclaw/openclaw/blob/main/docs/concepts/memory.md
- Decision:
  - Add service-side forget semantics aligned with memory-lancedb behavior while enforcing tenant/user/agent boundaries.
- Impact:
  - Bridge can now support delete and candidate-forget workflows without modifying OpenClaw core.
