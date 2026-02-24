# Release Checklist

Use this checklist before merging `codex/infinimind-mvp` into `main`.

## 1. Branch integrity

- Confirm linear feature commit history (`git log --oneline`).
- Confirm each feature commit has a compatibility ledger entry.

## 2. Service verification

- Build and run sidecar:
  - `docker compose -f deploy/docker-compose.yml up -d --build`
- Verify endpoints:
  - `GET /v1/health`
  - `GET /v1/ready` (with bearer token)
  - `GET /v1/metrics`
- Verify core APIs:
  - `POST /v1/memory/store`
  - `POST /v1/memory/recall`
  - `POST /v1/memory/forget`
  - `POST /v1/admin/reembed` dry-run
  - `POST /v1/admin/reembed` on empty dataset returns `processed=0`
- Verify metadata persistence:
  - Store with `metadata` and confirm recall returns the same `metadata` payload.
- Verify migration bootstrap:
  - Existing `memories_v2` data is promoted to `memories_v3` without deleting legacy table.

## 3. OpenClaw integration verification

- Validate manifest contract tests:
  - `python3 -m pytest tests/openclaw -q`
- Validate bridge package checks:
  - `npm install --no-audit --no-fund` (inside `plugins/infinimind-openclaw-bridge`)
  - `npm run typecheck` (inside `plugins/infinimind-openclaw-bridge`)
  - `npm run test` (inside `plugins/infinimind-openclaw-bridge`)
- Verify tool compatibility exposure:
  - `memory_store`, `memory_recall`, `memory_forget`
  - `memory_search` alias mapped to recall behavior
- Ensure OpenClaw config references only discoverable plugin ids.
- Run `openclaw plugins doctor` after enabling `infinimind-bridge`.
- Ensure bridge config uses `identityFallback: "error"` unless a deliberate `defaultUserId` is configured.

## 4. Safety checks

- Validate sensitivity gating behavior (`include_sensitive` + `trust_level`).
- Validate fallback does not bypass user/tenant constraints.
- Confirm no destructive migration steps are required (`memories_v2` retained during v3 bootstrap).
- Run secret scan:
  - `rg -l "sk-[A-Za-z0-9_-]{20,}"`
  - `rg -l "(AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-)"`
- Optional tracing verification (if enabled):
  - Set tracing env vars and confirm request spans are exported.

## 5. Rollback readiness

- Confirm rollback steps in [rollback.md](rollback.md).
- Confirm fallback memory slot target (`memory-core`) is available.

## 6. Merge readiness

- Open PR from `codex/infinimind-mvp` to `main`.
- Include benchmark output from `scripts/benchmark_recall.py`.
- Include canary plan and rollback owner.
