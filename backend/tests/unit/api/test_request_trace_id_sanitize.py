"""x-request-id header must not be echoed verbatim as trace_id (audit S-L1)."""

from types import SimpleNamespace

from src.api.agent.streaming import _request_trace_id


def _request(
    header_value: str | None = None, state_request_id: str | None = None
) -> SimpleNamespace:
    headers = {}
    if header_value is not None:
        headers["x-request-id"] = header_value
    return SimpleNamespace(
        state=SimpleNamespace(request_id=state_request_id), headers=headers
    )


def test_clean_header_is_preserved() -> None:
    assert _request_trace_id(_request("req-abc.123:x_y")) == "req-abc.123:x_y"


def test_header_with_unsafe_chars_is_replaced() -> None:
    value = _request_trace_id(_request("evil\nheader injection<script>"))
    assert "\n" not in value
    assert "<" not in value
    assert len(value) == 36  # uuid4 fallback


def test_missing_header_gets_uuid() -> None:
    assert len(_request_trace_id(_request())) == 36


def test_oversized_header_replaced_not_truncated() -> None:
    # Truncation would collapse distinct oversized ids sharing a prefix into
    # one trace id — replace with a fresh UUID instead.
    value = _request_trace_id(_request("a" * 129))
    assert len(value) == 36
    assert value != "a" * 128
