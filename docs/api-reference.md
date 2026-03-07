# API Reference

## Service API Reference

Base URL (default local): `http://127.0.0.1:8080`

Auth:

- `GET /v1/health` and `GET /v1/metrics` are public
- all other endpoints require `Authorization: Bearer <token>`

### `GET /v1/health`

Returns liveness status.

### `GET /v1/ready`

Returns readiness status for authenticated callers.

### `GET /v1/metrics`

Returns Prometheus exposition format.

### `POST /v1/memory/store`

Stores one memory record.

Core request fields:

- required: `user_id`, `text`
- common: `tenant_id` (default `default`), `agent_id` (default `main`), `category`, `importance`
- optional filters/context: `scope`, `channel_id`, `session_id`, `actor_id`, `tags`, `ttl_hours`, `dedupe_key`
- optional metadata blocks: `metadata`, `provenance`, `quality`

Response:

- `action`: `created` or `duplicate`
- `duplicate` indicates the incoming payload was auto-merged into an existing canonical record
- `memory_id`
- `duplicate_of` when applicable

### `POST /v1/memory/batch-store`

Stores up to 200 records in one call.

Response contains:

- `created_count`
- `duplicate_count`
- `results[]` with per-item outcomes

### `POST /v1/memory/recall`

Retrieves memories with strict hard-filter stage before ranking.

Common request fields:

- required: `user_id`, `query`
- common controls: `limit`, `scope`, `categories`, `tags_any`, `min_importance`
- time filters: `since`, `until` (ISO datetime)
- trust/policy controls: `include_sensitive`, `trust_level`, `fallback_mode`
- ranking/debug: `rerank`, `debug`

Validation details:

- malformed datetimes return `422`
- `since > until` returns `422`

Response:

- `count`
- `memories[]` with `score`, `score_breakdown`, `metadata`, `quality`, provenance fields
- optional `debug` block when requested

### `POST /v1/memory/forget`

Delete behavior:

- by `memory_id`: scoped direct delete (`tenant_id`, `user_id`, `agent_id` boundary)
- by `query`: returns candidate list unless single high-confidence match is auto-deleted

Response `action` values:

- `deleted`
- `candidates`
- `not_found`
- `missing_param`

### `POST /v1/admin/reembed`

Admin-only endpoint for re-embedding safety workflow.

Request:

- `target_model_id`
- `dry_run` (optional)
- `limit` (optional)

Behavior:

- empty dataset: `processed=0`, `shadow_table=null`, status `200`
- non-empty: writes to a shadow table instead of in-place overwrite
