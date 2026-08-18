"""Time-to-first-token measured for persistence (chat_messages.ttft_ms).

The reading is taken against the caller's stream-start clock rather than the
SLO tracker's own (earlier) origin, so it stays a subset of the ``latency_ms``
written to the same row and the two subtract into an honest split.
"""

from __future__ import annotations

from types import SimpleNamespace

from src.api.agent.streaming import _ttft_ms


def _emitter(first_token_at: float | None) -> SimpleNamespace:
    return SimpleNamespace(slo_tracker=SimpleNamespace(first_token_at=first_token_at))


def test_measures_from_the_callers_stream_start() -> None:
    # Truncating rather than rounding, matching the int() the sibling
    # latency_ms is built with — a sub-millisecond is not worth diverging over.
    assert _ttft_ms(_emitter(124.5), 100.0) == 24_500


def test_none_when_no_token_was_streamed() -> None:
    # An error raised before generation, or a stop during the tool phase:
    # the column stays NULL rather than recording a misleading zero.
    assert _ttft_ms(_emitter(None), 100.0) is None


def test_clamps_a_reading_that_precedes_the_stream_clock() -> None:
    # The confirm/resume generator builds its emitter before stamping
    # stream_started_at. No token can be emitted in that window today, but a
    # negative duration would be worse than a zero if one ever were.
    assert _ttft_ms(_emitter(99.0), 100.0) == 0


def test_tolerates_an_emitter_without_a_tracker() -> None:
    assert _ttft_ms(SimpleNamespace(), 100.0) is None
