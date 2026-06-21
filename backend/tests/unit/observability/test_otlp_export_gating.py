"""Regression tests for OTLP push-export gating.

rag-dev and CI have no OTLP collector (no jaeger:4317), so the OTLP gRPC
exporter logged an ERROR + retried every few seconds forever. OTLP push
export is now OFF by default (OTEL_EXPORTER_OTLP_ENABLED) — the Prometheus
scrape path stays on regardless. These tests pin that contract.
"""

from unittest.mock import patch

import pytest

from src.observability import metrics as metrics_mod
from src.observability import tracer as tracer_mod
from src.observability.config import ObservabilityConfig


@pytest.mark.unit
def test_otlp_disabled_by_default(monkeypatch: pytest.MonkeyPatch):
    """A fresh config must not enable OTLP push export."""
    # Ambient OTEL_EXPORTER_OTLP_ENABLED (CI/local shell) would override the
    # field default, so clear it before asserting the default.
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENABLED", raising=False)
    assert ObservabilityConfig().otel_exporter_otlp_enabled is False


@pytest.mark.unit
def test_configure_metrics_skips_otlp_when_disabled():
    with (
        patch.object(metrics_mod.config, "otel_exporter_otlp_enabled", False),
        patch.object(metrics_mod, "OTLPMetricExporter") as otlp,
    ):
        metrics_mod.configure_metrics()
    otlp.assert_not_called()


@pytest.mark.unit
def test_configure_metrics_uses_otlp_when_enabled():
    with (
        patch.object(metrics_mod.config, "otel_exporter_otlp_enabled", True),
        patch.object(metrics_mod, "OTLPMetricExporter") as otlp,
        patch.object(metrics_mod, "PeriodicExportingMetricReader"),
    ):
        metrics_mod.configure_metrics()
    otlp.assert_called_once()


@pytest.mark.unit
def test_configure_tracing_skips_otlp_when_disabled():
    with (
        patch.object(tracer_mod.config, "otel_exporter_otlp_enabled", False),
        patch.object(tracer_mod, "OTLPSpanExporter") as otlp,
    ):
        tracer_mod.configure_tracing()
    otlp.assert_not_called()


@pytest.mark.unit
def test_configure_tracing_uses_otlp_when_enabled():
    with (
        patch.object(tracer_mod.config, "otel_exporter_otlp_enabled", True),
        patch.object(tracer_mod, "OTLPSpanExporter") as otlp,
        patch.object(tracer_mod, "BatchSpanProcessor"),
    ):
        tracer_mod.configure_tracing()
    otlp.assert_called_once()
