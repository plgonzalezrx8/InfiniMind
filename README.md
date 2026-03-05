# InfiniMind

InfiniMind is a standalone, Docker-first memory sidecar for OpenClaw.

It adds a dedicated memory service + bridge plugin so memory behavior can be improved without modifying OpenClaw core.

<p align="center">
  <img src="docs/assets/infinimind-logo.svg" alt="InfiniMind logo" width="760" />
</p>

## What it does

- memory storage + recall with policy filtering
- OpenClaw bridge compatibility (`memory_store`, `memory_recall`, `memory_forget`, `memory_search`)
- LanceDB-backed persistence and migration safeguards
- CI/release gates and operator runbooks

## Visual overview

![InfiniMind end-to-end request flow](docs/assets/flow-end-to-end.svg)

## 5-minute quick start

```bash
cp .env.example .env
python3 scripts/generate_api_keys.py --write-env
# add OPENAI_API_KEY to .env

set -a
source .env
set +a

docker compose -f deploy/docker-compose.yml up -d --build

curl -s http://127.0.0.1:8080/v1/health
curl -s -H "Authorization: Bearer ${INFINIMIND_API_KEY}" http://127.0.0.1:8080/v1/ready
```

## Documentation

Full docs are split by topic in [`docs/README.md`](docs/README.md):

- [Overview](docs/overview.md)
- [Architecture](docs/architecture.md)
- [Getting Started](docs/getting-started.md)
- [API Reference](docs/api-reference.md)
- [OpenClaw Integration](docs/openclaw-integration.md)
- [Branching Model](docs/branching-model.md)
- [Testing & Release](docs/testing-and-release.md)
- [Operations](docs/operations.md)
- [Operator Runbooks](docs/operators/)

## Repository layout

- `services/infinimind-service`: FastAPI service
- `plugins/infinimind-openclaw-bridge`: OpenClaw plugin
- `deploy/docker-compose.yml`: primary runtime path
- `scripts/`: helper, smoke, and release scripts
- `docs/`: split documentation

## License

MIT (see [LICENSE](LICENSE)).
