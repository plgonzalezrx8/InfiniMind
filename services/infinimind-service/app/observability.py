"""Prometheus instrumentation primitives for the InfiniMind service."""

from __future__ import annotations

from time import perf_counter

from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

HTTP_REQUESTS_TOTAL = Counter(
    "infinimind_http_requests_total",
    "Total HTTP requests handled by InfiniMind",
    ["method", "path", "status"],
)
HTTP_REQUEST_LATENCY_SECONDS = Histogram(
    "infinimind_http_request_latency_seconds",
    "HTTP request latency in seconds",
    ["method", "path"],
)
RECALL_FALLBACK_TOTAL = Counter(
    "infinimind_recall_fallback_total",
    "Number of recall requests that required safe fallback expansion",
)
POLICY_NOTES_TOTAL = Counter(
    "infinimind_policy_note_total",
    "Count of policy events emitted by recall",
    ["note"],
)
STORE_RESULTS_TOTAL = Counter(
    "infinimind_store_results_total",
    "Count of store outcomes",
    ["action"],
)



def install_metrics_middleware(app: FastAPI) -> None:
    """Install request-level latency and throughput instrumentation."""

    @app.middleware("http")
    async def _metrics_middleware(request: Request, call_next):
        start = perf_counter()
        response = await call_next(request)
        elapsed = perf_counter() - start

        method = request.method
        path = request.url.path
        status = str(response.status_code)

        HTTP_REQUESTS_TOTAL.labels(method=method, path=path, status=status).inc()
        HTTP_REQUEST_LATENCY_SECONDS.labels(method=method, path=path).observe(elapsed)
        return response



def metrics_response() -> Response:
    """Return the current Prometheus metrics payload."""

    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
