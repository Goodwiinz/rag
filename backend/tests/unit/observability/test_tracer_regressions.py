"""Regression tests for OpenTelemetry tracer configuration."""

from unittest.mock import MagicMock

import pytest


pytestmark = [pytest.mark.unit, pytest.mark.regression]


def test_configure_tracing_uses_supported_propagate_api(monkeypatch):
    """OTel 1.x exposes set_global_textmap from opentelemetry.propagate."""
    pytest.importorskip("opentelemetry")
    import opentelemetry.propagate as propagate

    from src.observability import tracer

    fake_exporter = MagicMock(name="otlp_exporter")
    fake_processor = MagicMock(name="span_processor")
    fake_provider = MagicMock(name="trace_provider")
    fake_tracer = MagicMock(name="tracer")
    fake_provider.get_tracer.return_value = fake_tracer
    set_global_textmap = MagicMock(name="set_global_textmap")

    monkeypatch.setattr(tracer.Resource, "create", MagicMock(return_value=object()))
    monkeypatch.setattr(
        tracer, "OTLPSpanExporter", MagicMock(return_value=fake_exporter)
    )
    monkeypatch.setattr(
        tracer, "BatchSpanProcessor", MagicMock(return_value=fake_processor)
    )
    monkeypatch.setattr(
        tracer, "TracerProvider", MagicMock(return_value=fake_provider)
    )
    monkeypatch.setattr(tracer.trace, "set_tracer_provider", MagicMock())
    monkeypatch.setattr(propagate, "set_global_textmap", set_global_textmap)
    monkeypatch.setattr(tracer, "_tracer", None)

    assert tracer.configure_tracing() is fake_tracer

    tracer.trace.set_tracer_provider.assert_called_once_with(fake_provider)
    fake_provider.add_span_processor.assert_called_once_with(fake_processor)
    set_global_textmap.assert_called_once()
