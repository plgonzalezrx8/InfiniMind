# Beta Readiness Audit Matrix

Last updated: 2026-02-24

This document is the baseline audit snapshot for Iteration 5.

Scope:

- deployment target: single-host Docker Compose
- OpenClaw compatibility pin: `2026.2.22-2`
- launch threshold: no unresolved P1/P2 findings

## Gate Ownership

| Gate | Required for beta | Owner | Enforcement point |
| --- | --- | --- | --- |
| `service-tests` | yes | service team | `scripts/release_gates.sh --check service-tests` + `quality-gates` workflow |
| `bridge-quality` | yes | bridge/plugin team | `scripts/release_gates.sh --check bridge-quality` + `quality-gates` workflow |
| `openclaw-contract` | yes | integration team | `scripts/release_gates.sh --check openclaw-contract` + `quality-gates` workflow |
| `secret-scan` | yes | release/security owner | `scripts/release_gates.sh --check secret-scan` + `quality-gates` workflow |
| `docker-smoke` | yes | operators/release owner | `scripts/release_gates.sh --check docker-smoke` + `quality-gates` workflow |
| `openclaw-e2e` | yes | integration/release owner | `scripts/release_gates.sh --check openclaw-e2e` + `quality-gates` workflow |

## Baseline Evidence Snapshot

Collected on 2026-02-24 from local branch `codex/infinimind-mvp`.

| Check | Local status | Evidence summary |
| --- | --- | --- |
| `service-tests` | pass | service pytest suite passes |
| `bridge-quality` | pass | bridge `npm ci`, typecheck, and test suite pass |
| `openclaw-contract` | pass | contract tests for manifest/config/slot wiring pass |
| `secret-scan` | pass | no committed secrets detected by regex gate |
| `docker-smoke` | conditional fail | blocked when inherited env includes real-looking external keys and override is not set |
| `openclaw-e2e` | environment-blocked | requires Docker daemon and local runtime prerequisites; hosted CI job is authoritative for merge |

## Baseline Risk Notes (Iteration 5 Inputs)

1. E2E path validates plugin discovery/slot wiring but must also assert executable memory tool behavior end-to-end.
2. Service coverage is below the target threshold for beta hardening and has module-level weak spots.
3. Bridge runtime failure-path coverage should be expanded for timeout/upstream error determinism.
4. Operator docs are detailed, but beta runbook sequencing needs tighter command-by-command guidance.

## Beta Exit Criteria (Audit-Controlled)

All criteria must be true simultaneously:

1. All required gates above are green in hosted CI.
2. OpenClaw compatibility is validated against pin `2026.2.22-2`.
3. No unresolved P1 or P2 findings remain open.
4. Service + bridge coverage thresholds are met and enforced by CI.
5. Docs include executable plugin cookbook and beta runbook with deterministic commands.
