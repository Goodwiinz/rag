"""Regression tests for extract_interrupt_confirmation.

langgraph's GraphInterrupt stores its Sequence[Interrupt] in ``args[0]``
(via ``super().__init__(interrupts)``); it has no ``.interrupts`` attribute.
The old ``getattr(exc, "interrupts", [])`` therefore always returned ``[]``
and every HITL confirmation surfaced empty. These tests pin the args[0]
contract so the bug cannot silently return.
"""

import pytest

from src.services.agent._errors import extract_interrupt_confirmation


class _FakeInterrupt:
    def __init__(self, value):
        self.value = value


@pytest.mark.unit
def test_extracts_value_from_args0():
    payload = {"tools": [{"name": "create_note"}], "message": "confirm"}
    exc = Exception([_FakeInterrupt(payload)])
    assert extract_interrupt_confirmation(exc) == payload


@pytest.mark.unit
def test_empty_when_no_interrupts():
    assert extract_interrupt_confirmation(Exception([])) == {}
    assert extract_interrupt_confirmation(Exception()) == {}


@pytest.mark.unit
def test_real_graph_interrupt_roundtrip():
    """The real langgraph types must satisfy the args[0] contract."""
    from langgraph.errors import GraphInterrupt
    from langgraph.types import Interrupt

    payload = {"message": "confirm", "tools": [{"name": "ingest"}]}
    exc = GraphInterrupt((Interrupt(value=payload, id="x"),))
    assert extract_interrupt_confirmation(exc) == payload
