"""Prometheus instrumentation primitives for the InfiniMind service."""

from __future__ import annotations

import logging
from time import perf_counter

from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from .settings import Settings

LOGGER = logging.getLogger(__name__)

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
STORE_MERGES_TOTAL = Counter(
    "infinimind_store_merges_total",
    "Count of store merges by dedupe reason",
    ["reason"],
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


def install_optional_tracing(app: FastAPI, settings: Settings) -> bool:
    """Enable OpenTelemetry tracing when explicitly requested via settings."""

    if not settings.tracing_enabled:
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    except Exception as exc:  # pragma: no cover - optional dependency/runtime path
        LOGGER.warning("Tracing requested but OpenTelemetry dependencies are unavailable: %s", exc)
        return False

    resource = Resource.create({"service.name": settings.tracing_service_name})
    tracer_provider = TracerProvider(resource=resource)

    exporter = settings.tracing_exporter.lower().strip()
    if exporter == "console":
        span_exporter = ConsoleSpanExporter()
    else:
        endpoint = settings.tracing_otlp_endpoint
        if not endpoint:
            LOGGER.warning("Tracing requested but INFINIMIND_TRACING_OTLP_ENDPOINT is not set")
            return False
        span_exporter = OTLPSpanExporter(endpoint=endpoint)

    tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
    trace.set_tracer_provider(tracer_provider)
    FastAPIInstrumentor.instrument_app(app)
    LOGGER.info("OpenTelemetry tracing enabled (exporter=%s)", exporter)
    return True



def metrics_response() -> Response:
    """Return the current Prometheus metrics payload."""

    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
