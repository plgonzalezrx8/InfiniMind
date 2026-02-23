# InfiniMind Brainstorm (Kickoff)

## Problem statement
Current memory quality is limited by vector-only recall behavior. We need higher precision, better freshness handling, and task-aware retrieval.

## Initial hypotheses
- Hybrid retrieval (semantic + lexical) will outperform embedding-only recall.
- Memory type separation (preferences, decisions, procedural fixes, episodic logs) will reduce noise.
- Multi-stage reranking with provenance/confidence will cut hallucinations.
- Lifecycle controls (promote, decay, archive) are mandatory for long-term quality.

## Design constraints
- Keep backward compatibility with existing memory_store/memory_recall flows.
- Keep latency practical for chat use.
- Keep privacy boundaries across channels/sessions.
- Ensure easy rollback and feature-flag control.

## Working docs
- README.md (project overview)
- THIS FILE (brainstorm)
- ARCHITECTURE.md (to be drafted)
- RANKING.md (to be drafted)
- MIGRATION.md (to be drafted)

## Next step
Consolidate subagent findings into concrete docs + implementation plan.
