"""Route-bounded SLI accounting for the agent SSE lifecycle."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from src.services.agent import observability
from src.shared.enums import AgentStreamEvent


@dataclass
class _Metric:
    labels_seen: list[dict[str, str]] = field(default_factory=list)
    observations: list[float] = field(default_factory=list)
    increments: int = 0

    def labels(self, **labels: str) -> "_Metric":
        self.labels_seen.append(labels)
        return self

    def observe(self, value: float) -> None:
        self.observations.append(value)

    def inc(self) -> None:
        self.increments += 1


def _install_metrics(monkeypatch: pytest.MonkeyPatch) -> dict[str, _Metric]:
    metrics = {
        "accepted": _Metric(),
        "first_token": _Metric(),
        "completion": _Metric(),
        "turns": _Metric(),
        "routes": _Metric(),
    }
    monkeypatch.setattr(observability, "_METRICS_AVAILABLE", True)
    monkeypatch.setattr(
        observability, "AGENT_STREAM_ACCEPTED_DURATION", metrics["accepted"]
    )
    monkeypatch.setattr(
        observability, "AGENT_STREAM_FIRST_TOKEN_DURATION", metrics["first_token"]
    )
    monkeypatch.setattr(
        observability, "AGENT_STREAM_COMPLETION_DURATION", metrics["completion"]
    )
    monkeypatch.setattr(observability, "AGENT_STREAM_TURNS", metrics["turns"])
    monkeypatch.setattr(observability, "AGENT_STREAM_ROUTES", metrics["routes"])
    return metrics


def test_tracker_records_accepted_first_token_once_and_one_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    metrics = _install_metrics(monkeypatch)
    times = iter([100.0, 100.1, 101.0, 101.2, 101.5, 102.0])
    tracker = observability.AgentStreamSLOTracker(clock=lambda: next(times))

    tracker.record(AgentStreamEvent.STATUS, {"phase": "accepted"})
    tracker.set_route("luna")
    tracker.record(AgentStreamEvent.TOKEN, {"content": "a"})
    tracker.record(AgentStreamEvent.TOKEN, {"content": "b"})
    tracker.record(AgentStreamEvent.DONE, {"status": "complete"})
    tracker.record(AgentStreamEvent.ERROR, {"error": "late duplicate"})

    assert metrics["accepted"].observations == pytest.approx([0.1])
    assert metrics["first_token"].observations == pytest.approx([1.0])
    assert metrics["completion"].observations == pytest.approx([1.2])
    assert metrics["turns"].labels_seen == [{"route": "luna", "status": "done"}]
    assert metrics["turns"].increments == 1
    assert metrics["routes"].labels_seen == [{"route": "luna"}]
    assert metrics["routes"].increments == 1


def test_tracker_normalizes_unbounded_route_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    metrics = _install_metrics(monkeypatch)
    tracker = observability.AgentStreamSLOTracker(clock=lambda: 10.0)

    tracker.set_route("organization-123-secret-route")
    tracker.record(AgentStreamEvent.ERROR, {"error": "boom"})

    assert tracker.route == "unknown"
    assert metrics["routes"].labels_seen == [{"route": "unknown"}]
    assert metrics["turns"].labels_seen == [{"route": "unknown", "status": "error"}]


def test_tracker_is_a_noop_when_prometheus_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(observability, "_METRICS_AVAILABLE", False)
    tracker = observability.AgentStreamSLOTracker(clock=lambda: 1.0)

    tracker.set_route("graph")
    tracker.record(AgentStreamEvent.STATUS, {"phase": "accepted"})
    tracker.record(AgentStreamEvent.TOKEN, {})
    tracker.record(AgentStreamEvent.DONE, {})
