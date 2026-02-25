# OpenClaw Integration Fix Log (2026-02-24 to 2026-02-25)

## Purpose

This document records all integration and stabilization work completed for InfiniMind + OpenClaw during the Feb 24-25, 2026 rollout window, including:

- bridge/plugin configuration fixes
- local service orchestration fixes
- end-to-end validation hardening
- runtime write-path bug fix in InfiniMind storage
- post-cutover `memory_recall` 404 remediation caused by local port conflict

This is intended to be commit-ready audit documentation for GitHub.

## Environment

- Host: macOS user workstation
- OpenClaw config path: `~/.openclaw/openclaw.json` (external to this repo)
- InfiniMind project root: `/Users/pedrogonzalez/InfiniMind`
- InfiniMind service endpoint (current): `http://127.0.0.1:8090`
- InfiniMind service endpoint (pre-fix): `http://127.0.0.1:8080`

## Incident Summary

### Primary observed symptoms

1. OpenClaw memory calls intermittently failed (`fetch failed`) during service instability windows.
2. `memory_recall`/`memory_search` failed when identity fields were omitted.
3. E2E script produced false-negative plugin discovery failure because `plugins list` output truncates the plugin ID in table format.
4. `memory_store` returned `HTTP 500` while `memory_recall` could still succeed.
5. `memory_recall` returned `InfiniMind HTTP 404: 404 page not found` at `2026-02-25T03:01:25Z`.

### Root causes

1. **Identity strictness mismatch at runtime**
   - Bridge was configured with `identityFallback: "error"` in OpenClaw production config.
   - Tool calls without explicit identity failed as designed.

2. **E2E script brittle plugin assertion**
   - Script asserted `grep infinimind-bridge` on `plugins list` table output.
   - OpenClaw table layout can split/truncate the ID column, causing false failure.

3. **Token mismatch risk in `--skip-compose` E2E runs**
   - E2E script generated ephemeral keys when compose was skipped.
   - Live local service was often running with `.env` keys, producing `401 invalid token`.

4. **Storage schema inference bug (product defect)**
   - Existing `memories_v3` table had several optional fields inferred as Arrow `null` type.
   - Any non-null write to those fields (for example `channel_id`) raised:
     - `pyarrow.lib.ArrowInvalid: Invalid null value`
   - This caused `memory_store` to fail with HTTP 500.

5. **Local port collision on 8080 (deployment/runtime issue)**
   - Docker process `com.docke` was already listening on `127.0.0.1:8080`.
   - InfiniMind launchd service repeatedly failed to bind `8080` with:
     - `[Errno 48] error while attempting to bind on address ('127.0.0.1', 8080): address already in use`
   - OpenClaw bridge requests to `http://127.0.0.1:8080/v1/memory/recall` reached a non-InfiniMind process and returned HTTP 404.
   - This was not a recall endpoint implementation bug in InfiniMind; it was a host-level routing mismatch.

## Changes Applied

## A) Bridge package metadata alignment

### Files changed

- `plugins/infinimind-openclaw-bridge/package.json`
- `plugins/infinimind-openclaw-bridge/package-lock.json`

### What changed

- package name changed from `@infinimind/openclaw-bridge` to `@infinimind/infinimind-bridge`.

### Why

- Removed plugin-id hint mismatch warnings in OpenClaw plugin diagnostics.

## B) E2E script hardening

### File changed

- `scripts/openclaw_bridge_e2e.sh`

### What changed

1. Added `.env` sourcing for `--skip-compose` runs.
2. Updated generated profile config to:
   - `identityFallback: "configured-default"`
   - `defaultUserId: "e2e-default-user"`
3. Removed fragile `plugins list` grep assertion.
4. Kept strict plugin validation via:
   - `openclaw plugins info infinimind-bridge`
5. Updated embedded tool-exec config block to mirror fallback identity behavior.

### Why

- Prevent false-negative E2E failures.
- Ensure E2E uses real local keys when testing against already-running local service.
- Keep identity behavior deterministic for tests.

## C) Service write-path reliability fix (schema self-heal)

### Files changed

- `services/infinimind-service/app/storage.py`
- `services/infinimind-service/tests/test_storage_additional.py`

### What changed in storage

1. Added optional-field schema guard constants:
   - `OPTIONAL_STRING_FIELDS`
2. Added startup repair path:
   - `_detect_null_typed_optional_fields()`
   - `_repair_null_typed_optional_columns()`
3. Added initialization call:
   - `ensure_initialized()` now invokes schema repair before index creation.
4. Fixed sentinel bootstrap row typing:
   - optional string fields now use empty string `""` in sentinel instead of `None`
   - avoids Arrow inferring `null`-typed columns.
5. Added backup table preservation during repair:
   - `memories_v3__schema_fix_backup`

### What changed in tests

1. Added regression test:
   - `test_schema_repair_fixes_null_typed_optional_columns`
2. Test simulates bad legacy/null-inferred table and verifies:
   - optional fields become `string` type after startup repair
   - subsequent `store_memory` with non-null optional fields succeeds

### Why

- Fixes production HTTP 500 on `memory_store` writes that include optional scoped fields.
- Prevents recurrence for future deployments.

## D) External host-level integration changes (not in this repo)

These changes were required for local integration but are outside project git tracking:

1. `~/.openclaw/openclaw.json`
   - added bridge env vars:
     - `INFINIMIND_API_KEY`
     - `INFINIMIND_ADMIN_API_KEY`
   - routed memory slot to `infinimind-bridge`
   - configured bridge entry with:
     - `baseUrl`, `apiKey`, timeout/options
     - `identityFallback: "configured-default"`
     - `defaultUserId: "pedro"`
2. Launchd service install
   - plist: `~/Library/LaunchAgents/ai.infinimind.service.plist`
   - launcher script: `scripts/infinimind-launchd.sh`
   - launcher now supports env-configured bind values:
     - `INFINIMIND_HOST` (default `127.0.0.1`)
     - `INFINIMIND_PORT` (default `8080`)
   - local runtime override in `.env`:
     - `INFINIMIND_PORT=8090`
   - service currently bound to `127.0.0.1:8090`
3. OpenClaw gateway restart and plugin validation executed after config updates.
4. OpenClaw bridge base URL moved to `http://127.0.0.1:8090` in `~/.openclaw/openclaw.json`.

## E) 404 Incident Timeline (2026-02-25)

1. `03:01:25Z`: OpenClaw logged `memory_recall failed: InfiniMind HTTP 404: 404 page not found`.
2. Investigation confirmed InfiniMind path contract remained `POST /v1/memory/recall`.
3. Host checks found:
   - Docker bound to `127.0.0.1:8080`.
   - InfiniMind service bind failures on `8080`.
4. Remediation applied:
   - Set InfiniMind runtime port to `8090`.
   - Updated OpenClaw bridge `baseUrl` to `http://127.0.0.1:8090`.
   - Restarted InfiniMind launchd service and OpenClaw gateway.
5. Post-fix validation:
   - `GET /v1/health` on `8090` => `200`
   - `POST /v1/memory/recall` on `8090` => `200`
   - bridge E2E (`store/recall/search/forget`) => pass
   - no new `InfiniMind HTTP 404` entries after the fix window

## Validation Completed

## Automated tests

Executed in `services/infinimind-service`:

```bash
pytest -q tests/test_storage_additional.py tests/test_storage_migration.py
```

Result: passing.

## Integration checks

1. Plugin diagnostics:
   - `openclaw plugins doctor` reports no bridge issues.
2. E2E script:
   - `scripts/openclaw_bridge_e2e.sh --skip-compose ...` passes
   - validates store/recall/search/forget via bridge.
3. Live API checks after schema repair:
   - `POST /v1/memory/store` with `channel_id` returns 200
   - `POST /v1/memory/recall` returns stored entries
4. Live API + bridge checks after 8080->8090 cutover:
   - `GET /v1/health` on `http://127.0.0.1:8090` returns 200
   - direct store/recall smoke tests return 200
   - `scripts/openclaw_bridge_e2e.sh --base-url http://127.0.0.1:8090 --skip-compose` passes

## Current Repo Status (relevant files)

- `plugins/infinimind-openclaw-bridge/package.json`
- `plugins/infinimind-openclaw-bridge/package-lock.json`
- `scripts/openclaw_bridge_e2e.sh`
- `services/infinimind-service/app/storage.py`
- `services/infinimind-service/tests/test_storage_additional.py`
- `docs/operators/openclaw-integration-fixes-2026-02-25.md` (this file)

Untracked local artifacts to review before commit:

- `.data/` (runtime data; do not commit)
- `scripts/infinimind-launchd.sh` (currently modified to support configurable host/port; commit if you want launchd helper versioned)

## Recommended Commit Plan

## Option 1: Single commit

```bash
git add \
  plugins/infinimind-openclaw-bridge/package.json \
  plugins/infinimind-openclaw-bridge/package-lock.json \
  scripts/openclaw_bridge_e2e.sh \
  services/infinimind-service/app/storage.py \
  services/infinimind-service/tests/test_storage_additional.py \
  docs/operators/openclaw-integration-fixes-2026-02-25.md
git commit -m "fix(openclaw): harden bridge integration and repair null-typed storage schema"
```

## Option 2: Two commits (cleaner history)

1. Bridge/integration hardening
2. Storage schema self-heal + regression test + incident log

## Notes

- If you decide to version the launchd helper, add `scripts/infinimind-launchd.sh` in a separate ops commit.
- Keep secrets out of git; this log intentionally uses no plaintext tokens.
