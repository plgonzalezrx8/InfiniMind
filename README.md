# InfiniMind

InfiniMind is a standalone, Docker-first memory sidecar for OpenClaw.

## Deliverables in this repository

- `services/infinimind-service`: FastAPI memory service (store/recall/hybrid/policy)
- `plugins/infinimind-openclaw-bridge`: OpenClaw memory plugin bridge
- `deploy/docker-compose.yml`: default sidecar runtime path
- `docs/`: integration, configuration, rollback, and release runbooks
- `COMPATIBILITY_LEDGER.md`: per-feature OpenClaw docs/source consultation log

## Quick start

1. Start the service:

```bash
docker compose -f deploy/docker-compose.yml up -d --build
```

2. Validate OpenClaw bridge contract tests:

```bash
python3 -m pytest tests/openclaw -q
```

3. Configure OpenClaw memory slot to `infinimind-bridge`.

See:

- [OpenClaw Integration](/Users/pedrogonzalez/CascadeProjects/InfiniMind/docs/openclaw-integration.md)
- [Operator Configuration](/Users/pedrogonzalez/CascadeProjects/InfiniMind/docs/operators/configuration.md)
- [Rollback Guide](/Users/pedrogonzalez/CascadeProjects/InfiniMind/docs/operators/rollback.md)
- [Release Checklist](/Users/pedrogonzalez/CascadeProjects/InfiniMind/docs/operators/release-checklist.md)
