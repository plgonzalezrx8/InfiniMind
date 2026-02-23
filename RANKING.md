# InfiniMind — Retrieval & Ranking Draft (Subagent B)

Status: Draft

## Retrieval pipeline (multi-stage)

1. **Query understanding**
- Build semantic query embedding and lexical query terms.
- Classify intent: preference/fact/decision/entity recall.
- Extract constraints: time window, scope, actor/channel.

2. **Candidate generation (parallel)**
- Vector ANN top-K (semantic)
- BM25/FTS top-K (lexical exactness)
- Metadata-filter candidates (type/scope/time)

3. **Hard filtering**
- Remove expired/out-of-scope/blocked-sensitive memories.

4. **Reranking**
- Hybrid score combining relevance + operational priors.
- Keep top N for context injection.

5. **Diversity + conflict check**
- Reduce redundant memories (MMR/cluster).
- Preserve conflicting high-confidence memories with conflict marker.

6. **Context packaging**
- Provide snippet + memory_id + type + timestamp + confidence + provenance.

## Hybrid scoring formula

S(m,q) =
  ws*semantic + wl*lexical + wr*recency + wi*importance + wsr*source_reliability + wt*type_prior

Suggested default weights:
- ws = 0.38
- wl = 0.18
- wr = 0.12
- wi = 0.14
- wsr = 0.10
- wt = 0.08

## Evaluation plan

### Offline
- Build labeled set from historical queries (300–1000 examples).
- Metrics:
  - Recall@k
  - Precision@k
  - NDCG@k
  - MRR
  - Wrong-context rate
  - Conflict detection rate

### Online
- Latency p50/p95
- User correction rate
- Hallucination-with-memory citation rate
- Scope-leak incidents

## Guardrails

- Require scope filtering before ranking in multi-channel contexts.
- Sensitive memories excluded by default unless explicitly allowed.
- If confidence is low/conflicting, respond with uncertainty and request verification.
- Apply fallback expansion only when candidate pool is too small.

## Notes for implementation

- This design is compatible with current QMD direction (BM25 + vector sidecar).
- Keep reranking feature-flagged for incremental rollout.
