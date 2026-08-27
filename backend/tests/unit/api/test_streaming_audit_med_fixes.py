"""Unit coverage for streaming-audit medium fixes (S-M3, S-L8)."""

from types import SimpleNamespace

from src.api.agent.streaming import (
    _interrupt_confirmation_details,
    _usage_model_label,
)


def _task(*values: object) -> SimpleNamespace:
    return SimpleNamespace(interrupts=[SimpleNamespace(value=v) for v in values])


def test_single_interrupt_keeps_flat_payload() -> None:
    details = _interrupt_confirmation_details([_task({"action": "ingest"})])
    assert details == {"action": "ingest"}


def test_multiple_interrupts_ride_along() -> None:
    details = _interrupt_confirmation_details(
        [_task({"action": "ingest"}), _task({"action": "add_to_project"})]
    )
    assert details["action"] == "ingest"
    assert details["additional_interrupts"] == [{"action": "add_to_project"}]


def test_no_interrupts_yields_empty() -> None:
    assert _interrupt_confirmation_details([SimpleNamespace(interrupts=[])]) == {}


def test_non_dict_interrupt_value_is_wrapped() -> None:
    assert _interrupt_confirmation_details([_task("proceed?")]) == {"value": "proceed?"}


def test_usage_label_prefers_actual_model() -> None:
    event = {"metadata": {"ls_model_name": "gpt-5-mini"}}
    assert _usage_model_label(event, "user-model") == "gpt-5-mini"


def test_usage_label_falls_back_to_request_model() -> None:
    assert _usage_model_label({"metadata": {}}, "user-model") == "user-model"
    assert _usage_model_label({}, "user-model") == "user-model"
