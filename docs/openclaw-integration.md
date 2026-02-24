# OpenClaw Integration

InfiniMind integrates with OpenClaw through a dedicated memory plugin:

- Plugin id: `infinimind-bridge`
- Slot: `plugins.slots.memory`
- Protocol: HTTP JSON
- Service endpoint: `http://infinimind:8080`

This keeps OpenClaw core unchanged while replacing memory tool execution with sidecar calls.

## Integration architecture

1. OpenClaw agent calls `memory_store`, `memory_recall`, `memory_forget`, or `memory_search`.
2. `infinimind-bridge` plugin maps params to InfiniMind API payloads.
3. InfiniMind enforces hard policy filters and performs retrieval/rerank.
4. Plugin returns OpenClaw-compatible tool content/details.

Tool compatibility:

- Legacy compatibility tools: `memory_store`, `memory_recall`, `memory_forget`
- Alias for newer naming: `memory_search` (mapped to `/v1/memory/recall`)
- Out of scope in this bridge: `memory_get` (file-backed core memory behavior)

## Required OpenClaw config

Update `~/.openclaw/openclaw.json`:

```json5
{
  plugins: {
    enabled: true,
    load: {
      paths: ["/absolute/path/to/infinimind-openclaw-bridge"]
    },
    allow: ["infinimind-bridge"],
    slots: {
      memory: "infinimind-bridge"
    },
    entries: {
      "infinimind-bridge": {
        enabled: true,
        config: {
          baseUrl: "http://infinimind:8080",
          apiKey: "${INFINIMIND_API_KEY}",
          timeoutMs: 4000,
          defaultScope: "user",
          includeSensitiveDefault: false,
          rerankDefault: "hybrid",
          fallbackMode: "legacy-compatible",
          identityFallback: "error"
        }
      }
    }
  }
}
```

`apiKey: "${INFINIMIND_API_KEY}"` means OpenClaw resolves the value from its process environment.

Important:

1. Set `INFINIMIND_API_KEY` in the environment where OpenClaw runs.
2. Set the same value for the InfiniMind service (`INFINIMIND_API_KEY`).
3. If these differ, bridge calls fail with `401`.
4. `identityFallback: "error"` is recommended to avoid accidental user-identity collapse.

If you explicitly choose `identityFallback: "configured-default"`, you must also set:

```json5
defaultUserId: "some-explicit-user-id"
```

Key helper script:

```bash
python3 scripts/generate_api_keys.py --write-env
```

## Validation and restart behavior

- OpenClaw uses strict validation for plugin ids, slots, and config schema.
- `openclaw.plugin.json` must remain strict (`additionalProperties: false`).
- For plugin infrastructure changes, restart the OpenClaw gateway to avoid stale plugin state.

## Verification checklist

1. `openclaw plugins list` includes `infinimind-bridge`.
2. `openclaw plugins doctor` returns no plugin schema errors.
3. `openclaw plugins info infinimind-bridge` shows enabled status.
4. Manual tool invocation confirms:
   - `memory_store` writes return `action: created|duplicate`.
   - `memory_recall` returns structured memory details.
   - `memory_forget` returns `deleted|candidates|not_found|missing_param`.
   - `memory_search` returns the same recall payload shape through the alias path.

## Profile-isolated automation

Use the E2E script to validate plugin loading and slot wiring without touching your default OpenClaw profile:

```bash
scripts/openclaw_bridge_e2e.sh --profile infinimind-ci
```

Useful flags:

- `--base-url http://127.0.0.1:8080`
- `--plugin-path /absolute/path/to/plugins/infinimind-openclaw-bridge`
- `--openclaw-bin /absolute/path/to/openclaw`
- `--skip-compose` (when service is already running)
- `--keep-stack` (for manual post-check inspection)

The script asserts all of the following:

1. Bridge plugin is discoverable in `plugins list`.
2. `plugins doctor` runs cleanly for loaded plugin schema.
3. `plugins info infinimind-bridge` reports expected plugin id.
4. `plugins.slots.memory` resolves to `infinimind-bridge`.

## Troubleshooting plugin load and slot validation

1. Plugin missing from `plugins list`:
   - Check `plugins.load.paths` points to the bridge plugin directory.
   - Confirm bridge dependencies are installed: `cd plugins/infinimind-openclaw-bridge && npm ci --no-audit --no-fund`.
2. `plugins doctor` reports config/manifest issues:
   - Validate OpenClaw entry id matches manifest plugin id: `infinimind-bridge`.
   - Ensure bridge config keys match schema exactly (strict `additionalProperties: false` behavior).
3. Memory slot is not bound:
   - Confirm `plugins.slots.memory` is exactly `"infinimind-bridge"`.
   - Validate with `openclaw --profile infinimind-ci config get plugins.slots.memory`.
4. Calls return `401`:
   - Verify the same `INFINIMIND_API_KEY` value is used by service env, OpenClaw process env, and bridge `config.apiKey`.
