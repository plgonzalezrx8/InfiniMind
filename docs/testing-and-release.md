# Testing and Release

## Testing, CI Gates, and Release Flow

## Branching and Promotion Model

Long-lived branches:

- `master`: production-ready branch
- `development`: beta/release-candidate branch

Short-lived work branches:

- `feature/<name>`
- `sprint/<name>`

Promotion flow:

1. branch from `development`
2. merge feature/sprint branch into `development` after required gates pass
3. validate RC on `development`
4. merge `development` into `master` for production promotion
5. delete merged feature/sprint branches locally and remotely

Reference:

- [docs/branching-model.md](branching-model.md)

### Local gate runner (single entrypoint)

Default gate set:

```bash
scripts/release_gates.sh
```

Runs:

- `service-tests`
- `bridge-quality`
- `openclaw-contract`
- `secret-scan`
- `dependency-hygiene`

Optional heavier gates:

```bash
# Default smoke mode is deterministic synthetic keys:
scripts/release_gates.sh --check docker-smoke

# Optional: intentionally test with caller-provided env keys
INFINIMIND_SMOKE_KEY_MODE=environment INFINIMIND_ALLOW_REAL_KEYS=1 \
scripts/release_gates.sh --check docker-smoke

OPENCLAW_BIN="$(pwd)/plugins/infinimind-openclaw-bridge/node_modules/.bin/openclaw" \
scripts/release_gates.sh --check openclaw-e2e
```

### Hosted required checks (GitHub Actions)

- `service-tests`
- `bridge-quality`
- `openclaw-contract`
- `secret-scan`
- `dependency-hygiene`
- `docker-smoke`
- `openclaw-e2e`

Workflow files:

- `.github/workflows/quality-gates.yml`

### Release runbook

Use [docs/operators/release-checklist.md](docs/operators/release-checklist.md)

## Beta Go/No-Go Runbook

### 1. Preflight (must pass before any live traffic)

Run:

```bash
scripts/release_gates.sh
scripts/release_gates.sh --check docker-smoke
OPENCLAW_BIN="$(pwd)/plugins/infinimind-openclaw-bridge/node_modules/.bin/openclaw" \
scripts/release_gates.sh --check openclaw-e2e
```

Verify:

1. `plugins.slots.memory` resolves to `infinimind-bridge`.
2. `scripts/openclaw_bridge_e2e.sh` reports bridge tool execution success.
3. hosted `quality-gates` workflow is green on the target commit.

### 2. Canary rollout (single-host Compose first)

1. Deploy sidecar with production-equivalent `.env` and persistent volume.
2. Route a limited cohort (one tenant/user/agent group) through bridge slot.
3. Keep `fallbackMode: "legacy-compatible"` during first 24h.
4. Capture baseline metrics every 15m:
   - `infinimind_http_request_latency_seconds` (p95)
   - `infinimind_http_requests_total` (error ratio)
   - `infinimind_recall_fallback_total`
   - `infinimind_policy_note_total`
5. Promote only if latency/error/policy counters stay within your acceptance budget.

### 3. Incident response during beta

Trigger rollback immediately if any of the following occurs:

1. sustained `401`/`5xx` from bridge calls
2. repeated plugin discovery/slot drift in OpenClaw
3. policy leakage risk (unexpected sensitive recalls)
4. migration integrity mismatch indicators

Immediate actions:

1. set `plugins.slots.memory` back to `memory-core`
2. restart OpenClaw
3. collect logs/metrics/evidence for postmortem

### 4. Go/No-Go evidence package

Before declaring beta-ready, archive:

1. latest `quality-gates` workflow run URL
2. output summary for `scripts/release_gates.sh` checks
3. OpenClaw profile-isolated validation output
4. canary metric snapshots and owner sign-off
5. rollback owner confirmation

## Beta Testing Checklist

Minimum beta entry criteria:

1. Service tests pass.
2. Bridge typecheck/tests pass.
3. OpenClaw contract tests pass.
4. Secret scan passes.
5. Dependency hygiene gate passes.
6. Docker smoke gate passes in CI.
7. OpenClaw E2E gate passes with isolated profile.
8. OpenClaw slot points to `infinimind-bridge`.
9. Store/recall/forget manual sanity checks pass in target environment.

Recommended beta canary sequence:

1. Enable bridge for limited canary users/agents.
2. Keep `fallbackMode: "legacy-compatible"` during first canary.
3. Monitor recall fallback and policy note counters.
4. Monitor p95 latency and error rates.
5. Expand only after 24h stable canary metrics.
