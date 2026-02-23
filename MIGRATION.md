# InfiniMind — OpenClaw Integration & Migration Draft (Subagent C)

Status: Draft

## Objective
Improve memory quality/control with minimal disruption to current LanceDB workflows.

## Integration blueprint

- Keep existing memory tools backward compatible.
- Add enriched metadata + filter index + optional hybrid rank path.
- Roll out behind feature flags; preserve immediate rollback.

## Phase plan

### Phase 0 — Prepare (no behavior change)
- Add additive metadata fields:
  - schema_version, memory_id
  - created_at, updated_at
  - source_channel, source_session, source_actor
  - scope (global/user/channel/session)
  - sensitivity (low/medium/high)
  - ttl_expires_at
  - embedding_model_id
  - content_hash
- Add telemetry and feature flags.

### Phase 1 — Dual-write metadata
- Continue normal recall path.
- Write enriched records for new memory events.
- Backfill historical records best-effort.

### Phase 2 — Filter-first + optional hybrid ranking
- Apply metadata filter prefetch before vector similarity.
- Optionally enable hybrid score reranker.
- Fallback to legacy vector-only when candidate count too low.

### Phase 3 — Policy enforcement default
- Enforce scope and TTL.
- Sensitivity-aware recall constraints.
- Keep kill-switch to revert to legacy path.

## Proposed optional API extensions

### memory_store (optional fields)
- scope
- channelId
- sessionId
- actorId
- tags[]
- sensitivity
- ttlHours
- dedupeKey
- metadata

### memory_recall (optional fields)
- scope
- channelId
- sessionId
- actorId
- categories[]
- tagsAny[]
- minImportance
- since/until
- includeExpired
- includeSensitive
- rerank (off|hybrid)
- debug

## Rollback plan

1. Disable all memory.v2 flags.
2. Route reads to legacy path.
3. Keep additive schema untouched (no destructive rollback needed).
4. Keep metadata index idle if disabled.

## Key risks

- Mixed embedding versions during transition.
- Backfill ambiguity for old records.
- Increased latency if reranker is unbounded.
- Over-filtering causing misses.

## Mitigations

- Store embedding_model_id + rolling re-embed jobs.
- Candidate-threshold fallback to broader retrieval.
- Strict observability and debug traces.
- Time-box legacy coexistence to avoid long-term complexity.
