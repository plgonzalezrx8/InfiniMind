# OpenClaw Integration

## OpenClaw Bridge Integration (Detailed)

This document covers bridge behavior, config, and validation steps for connecting OpenClaw to InfiniMind.

### Tool compatibility

- legacy-compatible tools:
  - `memory_store`
  - `memory_recall`
  - `memory_forget`
- dual-compat alias:
  - `memory_search` (maps to `/v1/memory/recall`)
- intentionally out of scope:
  - `memory_get`

### Bridge identity behavior

Identity resolution precedence in plugin:

1. `userId`
2. `actorId`
3. `sessionId`
4. `channelId`

Config behavior:

- default and recommended: `identityFallback: "error"`
- optional: `identityFallback: "configured-default"` with required `defaultUserId`

### Canonical OpenClaw config snippet

Target file: `~/.openclaw/openclaw.json` (JSON5)

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
          // If identityFallback is "configured-default":
          // defaultUserId: "explicit-fallback-user"
        }
      }
    }
  }
}
```

Validation notes aligned with OpenClaw docs:

- unknown plugin ids in `entries`, `allow`, `deny`, `slots` are validation errors
- plugin `configSchema` is validated without executing plugin code
- plugin infra/config changes should be followed by gateway restart for deterministic behavior

Source references:

- [OpenClaw plugin docs](https://raw.githubusercontent.com/openclaw/openclaw/main/docs/tools/plugin.md)
- [OpenClaw config overview](https://raw.githubusercontent.com/openclaw/openclaw/main/docs/gateway/configuration.md)
- [OpenClaw manifest rules](https://raw.githubusercontent.com/openclaw/openclaw/main/docs/plugins/manifest.md)

### Profile-isolated validation

Run isolated bridge E2E (does not touch default OpenClaw profile):

```bash
scripts/openclaw_bridge_e2e.sh --profile infinimind-ci
```

Useful flags:

```bash
scripts/openclaw_bridge_e2e.sh \
  --profile infinimind-ci \
  --base-url http://127.0.0.1:8080 \
  --plugin-path /absolute/path/to/plugins/infinimind-openclaw-bridge \
  --openclaw-bin /absolute/path/to/openclaw
```
