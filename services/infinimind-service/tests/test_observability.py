"""Observability-specific tests for optional tracing setup."""

from __future__ import annotations

import sys
import types

from fastapi import FastAPI

from app.observability import install_optional_tracing
from app.settings import Settings


class _DummyTracerProvider:
    def __init__(self, *, resource):
        self.resource = resource
        self.processors = []

    def add_span_processor(self, processor):
        self.processors.append(processor)


class _DummyBatchSpanProcessor:
    def __init__(self, exporter):
        self.exporter = exporter


class _DummyOTLPSpanExporter:
    def __init__(self, *, endpoint):
        self.endpoint = endpoint


class _DummyConsoleSpanExporter:
    pass


def test_install_optional_tracing_enabled_smoke(monkeypatch):
    """Tracing should initialize when enabled and dependencies are available."""

    set_provider_calls = {}

    trace_mod = types.ModuleType("opentelemetry.trace")
    trace_mod.set_tracer_provider = lambda provider: set_provider_calls.setdefault("provider", provider)

    opentelemetry_mod = types.ModuleType("opentelemetry")
    opentelemetry_mod.trace = trace_mod

    exporter_mod = types.ModuleType("opentelemetry.exporter.otlp.proto.http.trace_exporter")
    exporter_mod.OTLPSpanExporter = _DummyOTLPSpanExporter

    instrumentation_mod = types.ModuleType("opentelemetry.instrumentation.fastapi")

    class _DummyFastAPIInstrumentor:
        @staticmethod
        def instrument_app(app):
            app.state.trace_instrumented = True

    instrumentation_mod.FastAPIInstrumentor = _DummyFastAPIInstrumentor

    resources_mod = types.ModuleType("opentelemetry.sdk.resources")

    class _DummyResource:
        @staticmethod
        def create(attributes):
            return {"attributes": attributes}

    resources_mod.Resource = _DummyResource

    trace_sdk_mod = types.ModuleType("opentelemetry.sdk.trace")
    trace_sdk_mod.TracerProvider = _DummyTracerProvider

    export_sdk_mod = types.ModuleType("opentelemetry.sdk.trace.export")
    export_sdk_mod.BatchSpanProcessor = _DummyBatchSpanProcessor
    export_sdk_mod.ConsoleSpanExporter = _DummyConsoleSpanExporter

    monkeypatch.setitem(sys.modules, "opentelemetry", opentelemetry_mod)
    monkeypatch.setitem(sys.modules, "opentelemetry.trace", trace_mod)
    monkeypatch.setitem(sys.modules, "opentelemetry.exporter.otlp.proto.http.trace_exporter", exporter_mod)
    monkeypatch.setitem(sys.modules, "opentelemetry.instrumentation.fastapi", instrumentation_mod)
    monkeypatch.setitem(sys.modules, "opentelemetry.sdk.resources", resources_mod)
    monkeypatch.setitem(sys.modules, "opentelemetry.sdk.trace", trace_sdk_mod)
    monkeypatch.setitem(sys.modules, "opentelemetry.sdk.trace.export", export_sdk_mod)

    settings = Settings(
        tracing_enabled=True,
        tracing_exporter="otlp",
        tracing_otlp_endpoint="http://collector:4318/v1/traces",
        tracing_service_name="infinimind-test",
    )

    app = FastAPI()
    enabled = install_optional_tracing(app, settings)
    assert enabled is True
    assert app.state.trace_instrumented is True
    provider = set_provider_calls["provider"]
    assert provider.resource["attributes"]["service.name"] == "infinimind-test"
