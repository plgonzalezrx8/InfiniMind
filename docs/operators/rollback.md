# Operator Rollback Guide

## Immediate rollback objective

Restore known-safe memory behavior quickly without destructive schema changes.

## Rollback path (OpenClaw side)

1. Switch memory slot away from bridge:

```json5
{
  plugins: {
    slots: {
      memory: "memory-core"
    }
  }
}
```

2. Optionally disable bridge entry:

```json5
{
  plugins: {
    entries: {
      "infinimind-bridge": {
        enabled: false
      }
    }
  }
}
```

3. Restart OpenClaw gateway after plugin slot/infrastructure changes.

## Rollback path (InfiniMind side)

1. Keep data volumes intact (no destructive deletes).
2. Keep service running for post-incident forensics.
3. If needed, stop service traffic by revoking bridge API key.

## Post-rollback validation

1. `openclaw plugins doctor` reports healthy state.
2. `plugins.slots.memory` resolves to fallback plugin.
3. Memory tool calls complete using fallback plugin path.

## Incident notes template

Capture at minimum:

- Trigger timestamp
- Failing feature or endpoint
- Observed blast radius
- Rollback timestamp
- Recovery confirmation evidence
