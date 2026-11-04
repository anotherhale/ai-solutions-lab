"""Host traces stay local unless an OTLP endpoint is configured."""

from __future__ import annotations

import socket
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

from wasatch_api.main import create_app
from wasatch_api.observability import build_tracer_provider, otlp_endpoint

_EXPORTER_MODULE = "opentelemetry.exporter.otlp.proto.http.trace_exporter"
_SRC = Path(__file__).resolve().parents[2] / "src" / "wasatch_api"


def _processor_count(provider: TracerProvider) -> int:
    active = provider._active_span_processor
    return len(active._span_processors)


@pytest.fixture
def refuse_network(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[object]]:
    """Fail the test if startup or the health request opens a socket."""

    attempts: list[object] = []

    def refuse(*args: object, **kwargs: object) -> None:
        attempts.append((args, kwargs))
        raise AssertionError(f"network connect: args={args!r} kwargs={kwargs!r}")

    class GuardedSocket(socket.socket):
        def connect(self, address: object) -> None:  # type: ignore[override]
            attempts.append(address)
            raise AssertionError(f"socket connect: {address!r}")

        def connect_ex(self, address: object) -> int:  # type: ignore[override]
            attempts.append(address)
            raise AssertionError(f"socket connect_ex: {address!r}")

    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket, "socket", GuardedSocket)
    yield attempts
    assert attempts == []


def test_blank_and_missing_endpoints_stay_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    assert otlp_endpoint() is None
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "   ")
    assert otlp_endpoint() is None


def test_app_starts_and_health_is_unchanged_without_exporter(
    monkeypatch: pytest.MonkeyPatch,
    refuse_network: list[object],
) -> None:
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
    loaded_before = _EXPORTER_MODULE in sys.modules

    provider = build_tracer_provider(otlp_endpoint())
    try:
        assert otlp_endpoint() is None
        assert _processor_count(provider) == 0
        assert (_EXPORTER_MODULE in sys.modules) is loaded_before
    finally:
        provider.shutdown()

    app = create_app()
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "wasatch-api"}
    assert "password" not in response.text.lower()
    assert "replace-me" not in response.text
    assert refuse_network == []


def test_endpoint_attaches_exporter_without_connecting(
    monkeypatch: pytest.MonkeyPatch,
    refuse_network: list[object],
) -> None:
    endpoint = "http://collector.example:4318"
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", endpoint)
    constructed: list[str] = []

    class FakeExporter(SpanExporter):
        def __init__(self, *args: object, **kwargs: object) -> None:
            super().__init__()
            constructed.append(str(kwargs.get("endpoint")))

        def export(self, spans: object) -> SpanExportResult:
            return SpanExportResult.SUCCESS

        def shutdown(self) -> None:
            return None

        def force_flush(self, timeout_millis: int = 30000) -> bool:
            return True

    exporter_module = __import__(
        _EXPORTER_MODULE,
        fromlist=["OTLPSpanExporter"],
    )
    monkeypatch.setattr(exporter_module, "OTLPSpanExporter", FakeExporter)

    provider = build_tracer_provider(otlp_endpoint())
    try:
        assert constructed == [f"{endpoint}/v1/traces"]
        assert _processor_count(provider) == 1
    finally:
        provider.shutdown()
    assert refuse_network == []


def test_sdk_imports_stay_in_the_composition_root() -> None:
    offenders: list[str] = []
    for path in _SRC.rglob("*.py"):
        if path.name == "observability.py":
            continue
        if "opentelemetry" in path.read_text(encoding="utf-8"):
            offenders.append(path.relative_to(_SRC).as_posix())
    assert offenders == []
