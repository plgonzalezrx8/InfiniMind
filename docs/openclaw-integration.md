# OpenClaw Integration

## OpenClaw Bridge Integration (Detailed)

This document covers bridge behavior, plugin config, lifecycle hook enrichment, and validation for integrating OpenClaw with InfiniMind.

### Tool compatibility

- legacy-compatible tools:
  - `memory_store`
  - `memory_recall`
  - `memory_forget`
- dual-compat alias:
  - `memory_search` (maps to `/v1/memory/recall`)
- intentionally out of scope:
  - `memory_get` (file-backed semantics in `memory-core`)

### Hook enrichment compatibility

Bridge-managed lifecycle hooks:

- auto-recall:
  - preferred: `before_prompt_build`
  - optional legacy mode: `before_agent_start`
- auto-capture:
  - `agent_end`

Behavior notes:

- hook failures are fail-open (conversation continues)
- plugin-managed hooks show in `openclaw hooks list` as `plugin:infinimind-bridge`
- plugin-managed hooks are controlled by plugin config/enable state, not `openclaw hooks enable|disable`

### Bridge identity behavior

Identity resolution precedence for tool calls:

1. `userId`
2. `actorId`
3. `sessionId`
4. `channelId`

Hook identity behavior:

- hook paths derive deterministic namespaced identity from session context:
  - `hook:<sessionKey>` when available
  - fallback `hook-session:<sessionId>` when available
- if session context is unavailable:
  - uses `defaultUserId` only when `identityFallback=configured-default`
  - otherwise skips hook operation with warning

Recommended config behavior:

- default and recommended: `identityFallback: "error"`
- optional: `identityFallback: "configured-default"` with required `defaultUserId`

### Canonical OpenClaw config snippet

Target file: `~/.openclaw/openclaw.json` (JSON5).

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
          identityFallback: "error",
          autoRecall: {
            enabled: true,
            hook: "before_prompt_build",
            limit: 3,
            minScore: 0.3,
            timeoutMs: 1500,
            maxInjectedChars: 2500,
            includeSensitive: false
          },
          autoCapture: {
            enabled: true,
            maxPerTurn: 3,
            minChars: 20,
            maxChars: 800,
            dedupeThreshold: 0.92,
            defaultCategory: "other",
            sensitivityDefault: "low"
            // Optional:
            // ttlHoursDefault: 168
          }
          // Optional only when identityFallback is "configured-default":
          // defaultUserId: "explicit-fallback-user"
        }
      }
    }
  }
}
```

### Hook config reference

`autoRecall`:

- `enabled`: enable/disable auto context injection
- `hook`: `before_prompt_build` (recommended) or `before_agent_start` (legacy)
- `limit`: recall result cap used for injected context
- `minScore`: score floor for injected memories
- `timeoutMs`: per-hook recall timeout budget
- `maxInjectedChars`: cap to prevent oversized injected prompt context
- `includeSensitive`: if `true`, hook requests high-trust recall path

`autoCapture`:

- `enabled`: enable/disable auto capture at `agent_end`
- `maxPerTurn`: max writes per successful run
- `minChars` / `maxChars`: capture bounds
- `dedupeThreshold`: top-hit similarity threshold to skip near-duplicate capture (default `0.92`)
- `defaultCategory`: category for auto-captured records
- `sensitivityDefault`: default sensitivity for auto-captured records
- `ttlHoursDefault`: optional expiry for auto-captured records (`null` means no TTL)

Validation notes aligned with OpenClaw docs:

- unknown plugin ids in `entries`, `allow`, `deny`, `slots` are validation errors
- plugin `configSchema` is validated without executing plugin code
- plugin infra/config changes should be followed by gateway restart for deterministic behavior

### Profile-isolated validation

Run isolated bridge E2E (does not touch default profile):

```bash
scripts/openclaw_bridge_e2e.sh --profile infinimind-ci
```

Manual validation commands:

```bash
openclaw --profile infinimind-ci plugins list
openclaw --profile infinimind-ci plugins info infinimind-bridge
openclaw --profile infinimind-ci plugins doctor
openclaw --profile infinimind-ci config get plugins.slots.memory
openclaw --profile infinimind-ci hooks list
```

Expected:

1. plugin is discoverable as `infinimind-bridge`
2. memory slot resolves to `infinimind-bridge`
3. no blocking config/plugin diagnostics
4. hook rows for `plugin:infinimind-bridge` appear when auto hooks are enabled

Useful E2E flags:

```bash
scripts/openclaw_bridge_e2e.sh \
  --profile infinimind-ci \
  --base-url http://127.0.0.1:8080 \
  --plugin-path /absolute/path/to/plugins/infinimind-openclaw-bridge \
  --openclaw-bin /absolute/path/to/openclaw
```

### Troubleshooting quick map

- `Identity is required...`
  - missing identity fields with strict fallback mode
  - fix: pass identity fields or configure `identityFallback=configured-default` + `defaultUserId`
- `InfiniMind HTTP 401`
  - service key and OpenClaw env interpolation mismatch
  - fix: align `INFINIMIND_API_KEY` in service env and OpenClaw runtime env
- no auto-enrichment observed
  - hook flags disabled or plugin not reloaded
  - fix: set `autoRecall.enabled` / `autoCapture.enabled`, restart gateway, verify `openclaw hooks list`

## Source references

- [OpenClaw plugin docs](https://raw.githubusercontent.com/openclaw/openclaw/main/docs/tools/plugin.md)
- [OpenClaw config overview](https://raw.githubusercontent.com/openclaw/openclaw/main/docs/gateway/configuration.md)
- [OpenClaw manifest rules](https://raw.githubusercontent.com/openclaw/openclaw/main/docs/plugins/manifest.md)
- [OpenClaw agent loop hooks](https://raw.githubusercontent.com/openclaw/openclaw/main/docs/concepts/agent-loop.md)
- [OpenClaw memory concept](https://raw.githubusercontent.com/openclaw/openclaw/main/docs/concepts/memory.md)
- [OpenClaw memory-lancedb reference](https://raw.githubusercontent.com/openclaw/openclaw/main/extensions/memory-lancedb/index.ts)
