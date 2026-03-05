# Release Checklist

Use this checklist before promoting `development` into `master`.

## 1. Branch integrity

- Confirm linear feature commit history (`git log --oneline`).
- Confirm each feature commit has a compatibility ledger entry.

## 2. Automated gate run (local parity with CI)

Run default release checks:

```bash
scripts/release_gates.sh
```

Run dependency hygiene gate:

```bash
scripts/release_gates.sh --check dependency-hygiene
```

Run Docker-first smoke checks with synthetic keys:

```bash
scripts/release_gates.sh --check docker-smoke
```

Run OpenClaw bridge E2E checks with an isolated profile:

```bash
OPENCLAW_BIN="$(pwd)/plugins/infinimind-openclaw-bridge/node_modules/.bin/openclaw" \
scripts/release_gates.sh --check openclaw-e2e
```

## 3. Required hosted checks

Confirm all required GitHub checks are green:

- `service-tests`
- `bridge-quality`
- `openclaw-contract`
- `secret-scan`
- `dependency-hygiene`
- `docker-smoke`
- `openclaw-e2e`

## 4. Service and migration verification

- Verify core APIs in smoke/manual checks:
  - `POST /v1/memory/store`
  - `POST /v1/memory/recall`
  - `POST /v1/memory/forget`
- Verify metadata persistence:
  - Store with `metadata` and confirm recall returns the same `metadata` payload.
- Verify re-embed behavior:
  - `POST /v1/admin/reembed` dry-run works.
  - empty dataset returns `processed=0`.
- Verify migration bootstrap:
  - Existing `memories_v2` data is promoted to `memories_v3` without deleting legacy table.

## 5. OpenClaw integration verification

- Ensure OpenClaw config references only discoverable plugin ids.
- Ensure bridge config uses `identityFallback: "error"` unless a deliberate `defaultUserId` is configured.
- Ensure hook enrichment settings match rollout intent (`autoRecall.enabled`, `autoCapture.enabled`).
- Verify plugin and slot state in isolated profile:
  - `openclaw --profile infinimind-ci plugins list`
  - `openclaw --profile infinimind-ci plugins doctor`
  - `openclaw --profile infinimind-ci config get plugins.slots.memory`
  - `openclaw --profile infinimind-ci hooks list`

## 6. Safety checks

- Validate sensitivity gating behavior (`include_sensitive` + `trust_level`).
- Validate fallback does not bypass user/tenant constraints.
- Confirm no destructive migration steps are required (`memories_v2` retained during v3 bootstrap).
- Run secret scan gate:
  - `scripts/release_gates.sh --check secret-scan`
- Optional tracing verification (if enabled):
  - Set tracing env vars and confirm request spans are exported.

## 7. Rollback readiness

- Confirm rollback steps in [rollback.md](rollback.md).
- Confirm fallback memory slot target (`memory-core`) is available.

## 8. Merge readiness

- Ensure release PR is `development -> master`.
- Include benchmark output from `scripts/benchmark_recall.py`.
- Include canary plan and rollback owner.

## 9. Beta go/no-go evidence

Attach all of the following to the release PR:

1. latest hosted `quality-gates` workflow URL (green).
2. terminal output for local `scripts/release_gates.sh` and `--check dependency-hygiene`.
3. profile-isolated OpenClaw E2E output showing tool execution success.
4. canary metrics snapshot (`latency`, `error ratio`, `fallback`, `policy notes`) with owner sign-off.
5. explicit rollback owner acknowledgment and tested rollback command transcript.
