# Operations

## Observability

### Metrics

Prometheus endpoint:

- `GET /v1/metrics`

Important metric series:

- `infinimind_http_requests_total`
- `infinimind_http_request_latency_seconds`
- `infinimind_recall_fallback_total`
- `infinimind_policy_note_total`
- `infinimind_store_results_total`

### Tracing

Tracing is optional and disabled by default.

Supported exporters:

- `console`
- `otlp` (requires `INFINIMIND_TRACING_OTLP_ENDPOINT`)

## Security and Safety Defaults

- API auth is required for mutating/recall/admin routes
- admin operations require `INFINIMIND_ADMIN_API_KEY`
- strict identity default in bridge (`identityFallback: "error"`)
- sensitivity gates enforce trust requirements
- fallback behavior is safe and scoped
- CI and scripts redact tokens and block real-looking secrets by default

Secret scanning:

```bash
scripts/secret_scan.sh
```

## Troubleshooting

### `401` from bridge/service

Cause:

- token mismatch between service, shell calls, and OpenClaw runtime interpolation

Fix:

1. verify `INFINIMIND_API_KEY` in `.env`
2. verify shell export with `set -a; source .env; set +a`
3. verify OpenClaw process env contains same value
4. verify bridge config `apiKey` matches interpolation key

### `openclaw plugins list` does not show `infinimind-bridge`

Fix:

1. check `plugins.load.paths`
2. verify plugin directory path is correct
3. run `npm ci --no-audit --no-fund` in `plugins/infinimind-openclaw-bridge`

### `openclaw plugins doctor` shows plugin warning about id hint mismatch

Observed warning shape:

- manifest id is `infinimind-bridge`
- entry hint may show `openclaw-bridge`

Interpretation:

- this warning is non-fatal when plugin id is discovered and loaded correctly
- verify final resolved plugin id from `openclaw plugins info infinimind-bridge`

### Docker smoke fails with daemon error

Cause:

- Docker daemon not running or unavailable socket

Fix:

1. start Docker Desktop / daemon
2. validate with `docker ps`
3. rerun `scripts/release_gates.sh --check docker-smoke`

### Docker smoke fails with port conflict on `127.0.0.1:8080`

Cause:

- another service already bound to port `8080`

Fix options:

1. stop conflicting service
2. rerun smoke in CI where environment is clean
3. run OpenClaw E2E with `--skip-compose` against an alternate local port

### Recall request returns `422`

Likely causes:

- invalid datetime format in `since` or `until`
- `since` later than `until`

Fix:

- use ISO datetimes and valid chronological ranges

## Rollback

Primary rollback action:

1. set `plugins.slots.memory` back to `memory-core`
2. optionally disable `infinimind-bridge`
3. restart OpenClaw gateway

Full runbook:

- [docs/operators/rollback.md](docs/operators/rollback.md)
