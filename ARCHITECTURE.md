# InfiniMind — Memory Architecture Draft (Subagent A)

Status: Draft (from first swarm result)

## Core conclusion
Vector-only memory is not enough for agent-grade recall. We should move to a **tiered hybrid architecture**.

## Recommended architecture

### Canonical store
- Append-only local document store for memory objects + provenance.
- Candidate backends: SQLite/Postgres-lite.

### Retrieval indices
1. Lexical index (BM25 / FTS5) for exact terms, IDs, names.
2. Vector index for semantic retrieval.
3. Optional graph index (derived, not primary) for relational/multi-hop reasoning.

### Memory classes
- episodic
- semantic
- procedural
- preference/profile
- task_state

### Query planner
- Detect query intent (exact / semantic / relational).
- Run lexical + vector retrieval in parallel.
- Apply graph expansion for relation-heavy queries.
- Fuse + rerank by relevance, recency, confidence, and source trust.

### Trust model
Every memory object should include:
- confidence
- provenance
- verification status
- decay/TTL policy
- supersession/conflict links

## Lifecycle
1. Capture
2. Distill
3. Retrieve
4. Verify
5. Archive

## Key risks
- Embedding drift after model changes
- Memory poisoning from low-trust writes
- Over-retrieval/context flooding
- Entity resolution errors
- Privacy leakage across contexts
- Staleness/superseded facts

## Immediate implementation sequence
1. Define schema + memory taxonomy
2. Stand up canonical store + BM25 + vector indices
3. Add ingestion write-gates
4. Add distillation jobs
5. Build hybrid retrieval orchestrator
6. Add verification/conflict engine
7. Add decay/archive/re-embed operations
