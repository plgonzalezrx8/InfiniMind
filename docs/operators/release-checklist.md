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
  - `POST /v1/admin/reembed` dry-run

## 3. OpenClaw integration verification

- Validate manifest contract tests:
  - `python3 -m pytest tests/openclaw -q`
- Ensure OpenClaw config references only discoverable plugin ids.
- Run `openclaw plugins doctor` after enabling `infinimind-bridge`.

## 4. Safety checks

- Validate sensitivity gating behavior (`include_sensitive` + `trust_level`).
- Validate fallback does not bypass user/tenant constraints.
- Confirm no destructive migration steps are required.

## 5. Rollback readiness

- Confirm rollback steps in [rollback.md](/Users/pedrogonzalez/CascadeProjects/InfiniMind/docs/operators/rollback.md).
- Confirm fallback memory slot target (`memory-core`) is available.

## 6. Merge readiness

- Open PR from `codex/infinimind-mvp` to `main`.
- Include benchmark output from `scripts/benchmark_recall.py`.
- Include canary plan and rollback owner.
