# InfiniMind — Master Plan v0.1

## Current stance
- We already shifted toward QMD-style hybrid retrieval direction (BM25 + vector sidecar).
- InfiniMind should formalize this into a robust memory operating system, not just better similarity search.

## Design principles
1. Hybrid by default (lexical + semantic)
2. Memory typing (episodic/procedural/preference/etc.)
3. Provenance + confidence first
4. Scope safety (channel/session/user boundaries)
5. Lifecycle management (distill, verify, decay, archive)
6. Incremental migration with kill-switches

## MVP scope (build now)

### Data model
- Enriched memory schema (additive fields only)
- Mandatory: id, type, timestamps, provenance, confidence, scope

### Retrieval v2
- Candidate generation: BM25 + vector + metadata filters
- Hybrid rerank formula (feature flag)
- Top-k context packaging with confidence/provenance

### Policy layer
- Scope-aware retrieval enforcement
- Sensitivity labels + safe defaults
- TTL support for ephemeral memory

### Observability
- recall precision/latency dashboards
- wrong-context leakage counter
- confidence distribution monitoring

## Phase roadmap
- **Phase A (1 week):** schema + dual write + telemetry
- **Phase B (1 week):** filter-first retrieval + fallback
- **Phase C (1 week):** hybrid reranker + eval harness
- **Phase D (1 week):** policy enforcement + decay/archive jobs

## Success criteria
- +20% precision@5 on preference/fact recall tasks
- -40% wrong-context retrieval incidents
- <=15% p95 recall latency increase
- explicit provenance shown for memory-backed answers

## Open questions
- Graph index in MVP or Phase E?
- How strict should default scope isolation be in DM/group mixes?
- Which embedding model/version should be pinned for stability?

## Immediate next action
Implement Phase A with flags:
- memory.v2.write_enriched
- memory.v2.filter_prefetch
- memory.v2.hybrid_rank
- memory.v2.enforce_scope
- memory.v2.enforce_ttl
