# InfiniMind — Requirements & Technical Specification (v0.1)

Owner: Pedro / OpenClaw team  
Status: Draft for team review  
Date: 2026-02-23

---

## 1) Executive summary

InfiniMind is a memory quality upgrade for OpenClaw focused on **reliability, safety, and explainability**.

### Core decision
Build InfiniMind as a **memory-plugin evolution** (not a core-breaking rewrite), using a **hybrid retrieval architecture**:
- lexical retrieval (BM25/FTS)
- semantic retrieval (vector)
- metadata-aware filtering and reranking

### Why now
Current vector-centric memory recall is vulnerable to:
- exact-match misses (IDs, names, error codes)
- stale memory dominance
- weak cross-channel safety controls
- poor explainability of why memories were retrieved

---

## 2) Scope

## In scope (v0.1–v0.3)
1. Add enriched memory metadata schema (additive, backward compatible)
2. Introduce filter-first retrieval pipeline
3. Introduce optional hybrid reranking
4. Add scope/sensitivity/TTL policy controls
5. Add provenance/confidence in retrieval outputs
6. Add rollout flags and rollback switches
7. Add observability for memory quality and leakage risk

## Out of scope (initial)
- Full core API breaking changes
- Immediate graph database dependency
- Hard migration away from current memory backend on day one

---

## 3) Architecture constraints and feasibility

### Feasibility verdict
**Feasible with extension** inside current OpenClaw architecture.

### Key constraints
1. Current memory tools are minimal (`memory_store`, `memory_recall`) and do not expose rich filters today.
2. Strict config/schema validation means new settings must be schema-backed.
3. Security-safe rollout requires policy enforcement in plugin/tool layer, not only prompt conventions.

### Compatibility requirement
No breaking change to existing calls:
- `memory_store(text, importance?, category?)`
- `memory_recall(query, limit?)`

New behavior must be additive and flag-gated.

---

## 4) Functional requirements

## FR-1: Backward-compatible memory writes
System shall continue accepting existing `memory_store` calls unchanged.

## FR-2: Enriched memory metadata
System shall support additive metadata fields:
- `memory_id`
- `schema_version`
- `created_at`, `updated_at`
- `source_channel`, `source_session`, `source_actor`
- `scope` (`global|user|channel|session`)
- `sensitivity` (`low|medium|high`)
- `ttl_expires_at`
- `embedding_model_id`
- `content_hash`

## FR-3: Filter-first recall
System shall apply metadata filters prior to ranking when enabled:
- scope/channel/session/actor filters
- time bounds (`since`, `until`)
- category/tag filters
- TTL exclusion by default
- sensitivity gating

## FR-4: Hybrid retrieval
System shall support lexical + semantic candidate generation with fusion/rerank.

## FR-5: Confidence and provenance
Recall results shall include provenance and confidence signals suitable for downstream decisioning/debugging.

## FR-6: Safe fallback behavior
If filtered candidate pool is insufficient, system shall fallback to legacy-compatible retrieval behavior (flag controlled).

## FR-7: Lifecycle controls
System shall support memory lifecycle operations:
- supersession markers
- decay/archival eligibility
- optional expiry handling

## FR-8: Observability
System shall emit quality metrics and policy-enforcement counters.

---

## 5) Non-functional requirements

## NFR-1: Performance
- Target p95 recall latency increase <= 15% during v2 rollout
- Candidate and rerank limits must be configurable

## NFR-2: Reliability
- Feature flags for every major behavior
- Immediate kill-switch rollback to legacy retrieval path

## NFR-3: Security & privacy
- Deny-by-default for sensitive recall in lower-trust contexts
- Scope-aware filtering before ranking
- Treat recalled memory as untrusted data, never executable instruction

## NFR-4: Operability
- Dual-write and canary rollout support
- Metrics for precision/recall proxy and wrong-context incidents

## NFR-5: Maintainability
- Additive schema evolution only in initial phases
- Version fields for data and embeddings

---

## 6) Data model specification (initial)

```json
{
  "memory_id": "uuid",
  "schema_version": 2,
  "text": "string",
  "category": "preference|fact|decision|entity|other",
  "importance": 0.0,
  "scope": "global|user|channel|session",
  "sensitivity": "low|medium|high",
  "source_channel": "string|null",
  "source_session": "string|null",
  "source_actor": "string|null",
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601",
  "ttl_expires_at": "ISO-8601|null",
  "embedding_model_id": "string",
  "content_hash": "sha256",
  "provenance": {
    "source_type": "chat|tool|file|web|user_explicit",
    "source_ref": "string|null"
  },
  "quality": {
    "confidence": 0.0,
    "verification_status": "unverified|verified|contradicted",
    "conflict_set": []
  }
}
```

Notes:
- Keep fields additive and nullable where needed for historical records.
- Historical rows default to safe fallback semantics.

---

## 7) Retrieval pipeline specification

## Stage A: Query understanding
- Parse intent and constraints.

## Stage B: Candidate generation (parallel)
- Vector ANN candidates
- Lexical BM25/FTS candidates
- Metadata prefiltered candidates

## Stage C: Hard policy filtering
- Exclude out-of-scope, expired, and disallowed-sensitive records.

## Stage D: Reranking
Hybrid score:

`S = ws*semantic + wl*lexical + wr*recency + wi*importance + wsr*sourceReliability + wt*typePrior`

Suggested defaults:
- `ws=0.38`
- `wl=0.18`
- `wr=0.12`
- `wi=0.14`
- `wsr=0.10`
- `wt=0.08`

## Stage E: Diversity/conflict pass
- Deduplicate and mark conflicts.

## Stage F: Context packaging
- Return top-N with provenance/confidence metadata.

---

## 8) API extension specification (additive)

## memory_store (proposed optional fields)
- `scope`
- `channelId`
- `sessionId`
- `actorId`
- `tags`
- `sensitivity`
- `ttlHours`
- `dedupeKey`
- `metadata`

## memory_recall (proposed optional fields)
- `scope`
- `channelId`
- `sessionId`
- `actorId`
- `categories`
- `tagsAny`
- `minImportance`
- `since`
- `until`
- `includeExpired`
- `includeSensitive`
- `rerank` (`off|hybrid`)
- `debug`

Compatibility rule: if omitted, behavior remains legacy-equivalent.

---

## 9) Security and privacy specification

## Baseline controls (must-have before broad rollout)
1. Channel group policy hardening (allowlist-first)
2. Scope filtering before ranking
3. Sensitivity-aware recall defaults
4. Auto-capture conservative defaults
5. Cross-context send restrictions maintained/tightened
6. Prompt guardrail: memory content is untrusted context

## Threats addressed
- cross-channel leakage
- memory poisoning/prompt injection
- sensitive data resurfacing in low-trust contexts
- opaque memory decisions without auditability

---

## 10) Storage/indexing specification

### Preferred rollout option
**Option 1:** Lance-native hybrid retrieval (vector + FTS + metadata filters)

### Optional escalation
**Option 2:** SQLite FTS5 lexical sidecar if additional lexical control is needed.

### Embedding migration rule
Never overwrite old embeddings in place.
- Use `embedding_model_id`
- Use new vector column/version during migration
- Use canary/shadow validation before cutover

---

## 11) Rollout plan

## Phase 0 — Preparation (no behavior change)
- Add schema fields and telemetry
- Add feature flags (all disabled)

## Phase 1 — Dual-write metadata
- Write enriched records
- Keep recall behavior unchanged
- Backfill historical metadata best-effort

## Phase 2 — Filter-first + optional hybrid rerank
- Enable filtered recall path for canary cohorts
- Add fallback to legacy path when candidate pool is too small

## Phase 3 — Policy enforcement defaults
- Enforce scope/TTL/sensitivity defaults
- Activate lifecycle jobs gradually

---

## 12) Feature flags (proposed)

- `memory.v2.write_enriched`
- `memory.v2.filter_prefetch`
- `memory.v2.hybrid_rank`
- `memory.v2.enforce_scope`
- `memory.v2.enforce_ttl`

Note: These are proposed plugin-backed controls and must be schema-supported before enablement.

---

## 13) Rollback strategy

1. Disable all `memory.v2.*` flags
2. Route reads to legacy retrieval path
3. Keep additive schema in place (no destructive rollback)
4. Keep index assets idle if needed

---

## 14) Acceptance criteria

1. Quality
- +20% precision@5 on preference/fact recall tests
- measurable reduction in wrong-context recalls

2. Safety
- no verified cross-channel memory leakage in test suite
- sensitivity and scope policies enforced in recall path

3. Performance
- p95 recall latency increase within agreed budget

4. Operability
- successful canary + rollback drills
- observability dashboards operational

---

## 15) Open questions for team review

1. Should graph memory remain Phase 4+ only?
2. What default strictness should scope enforcement use in mixed DM/group environments?
3. Which embedding model/version should be pinned for migration baseline?
4. Do we standardize on Lance-native FTS first, or start with SQLite sidecar immediately?

---

## 16) Recommended next step

Approve this spec as **v0.1 Requirements Baseline**, then produce:
- implementation task breakdown (engineering tickets)
- test plan document
- rollout checklist and incident playbook

---

## Appendix A — Related working docs

- `InfiniMind/ARCHITECTURE.md`
- `InfiniMind/RANKING.md`
- `InfiniMind/MIGRATION.md`
- `InfiniMind/MASTERPLAN.md`
- `InfiniMind/BRAINSTORM.md`
