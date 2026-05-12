"""OpenTelemetry tracing setup.

Disabled by default — set ``REST_API_OTEL_ENABLED=1`` to turn on. When
enabled, configures a console exporter so spans appear in stdout without
requiring an OTLP collector. Production deployments override the exporter
via env vars consumed by the standard OTel SDK.
"""

from __future__ import annotations

from fastapi import FastAPI

from api.config import Settings


def configure_telemetry(app: FastAPI, settings: Settings) -> None:
    if not settings.otel_enabled:
        return
    # Lazy imports so the dependency is optional at runtime.
    from opentelemetry import trace
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import (
        BatchSpanProcessor,
        ConsoleSpanExporter,
    )

    resource = Resource.create({"service.name": settings.otel_service_name})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app)
    try:
        from api.db.session import get_engine

        SQLAlchemyInstrumentor().instrument(engine=get_engine())
    except Exception:  # noqa: BLE001
        pass
