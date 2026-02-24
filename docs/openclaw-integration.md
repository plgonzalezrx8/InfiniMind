# OpenClaw Integration

InfiniMind integrates with OpenClaw through a dedicated memory plugin:

- Plugin id: `infinimind-bridge`
- Slot: `plugins.slots.memory`
- Protocol: HTTP JSON
- Service endpoint: `http://infinimind:8080`

This keeps OpenClaw core unchanged while replacing memory tool execution with sidecar calls.

## Integration architecture

1. OpenClaw agent calls `memory_store` or `memory_recall`.
2. `infinimind-bridge` plugin maps params to InfiniMind API payloads.
3. InfiniMind enforces hard policy filters and performs retrieval/rerank.
4. Plugin returns OpenClaw-compatible tool content/details.

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
