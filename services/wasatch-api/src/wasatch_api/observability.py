"""Host traces for the Wasatch API.

``create_app`` is the only caller. Domain and application modules do not
import this module. Spans export only when ``OTEL_EXPORTER_OTLP_ENDPOINT``
is a non-empty URL. Otherwise startup does not construct an exporter and
does not open a collector socket.
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider

# A non-empty list stops the instrumentation from reading
# OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_*. This name is not a Wasatch
# header, so request and response headers are not copied onto spans.
_UNMATCHED_HEADER = "x-wasatch-otel-no-header-capture"

_CONFIGURED = False


def otlp_endpoint() -> str | None:
    """Return the OTLP base URL, or None when export stays off."""

    value = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    return value or None


def _service_name() -> str:
    configured = os.environ.get("OTEL_SERVICE_NAME", "").strip()
    return configured or "wasatch-api"


def _traces_url(endpoint: str) -> str:
    trimmed = endpoint.strip().rstrip("/")
    if trimmed.endswith("/v1/traces"):
        return trimmed
    return f"{trimmed}/v1/traces"


def build_tracer_provider(endpoint: str | None) -> TracerProvider:
    """Build a provider. The OTLP exporter exists only when ``endpoint`` is set."""

    provider = TracerProvider(
        resource=Resource.create({"service.name": _service_name()})
    )
    if not endpoint:
        return provider
    # Imported here so an unset endpoint never constructs an exporter client.
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
        OTLPSpanExporter,
    )
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=_traces_url(endpoint)))
    )
    return provider


def configure_telemetry(app: FastAPI) -> None:
    """Instrument ``app``. The process reads the endpoint on the first call."""

    global _CONFIGURED
    if not _CONFIGURED:
        trace.set_tracer_provider(build_tracer_provider(otlp_endpoint()))
        _CONFIGURED = True
    FastAPIInstrumentor.instrument_app(
        app,
        http_capture_headers_server_request=[_UNMATCHED_HEADER],
        http_capture_headers_server_response=[_UNMATCHED_HEADER],
    )
