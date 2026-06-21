"""Regression tests for the agent node-execution tracking decorator.

GraphInterrupt (HITL confirm for destructive tools) and other langgraph
bubble-up signals are control flow, not failures. The node wrapper must
re-raise them WITHOUT logging an ERROR or incrementing the error counter,
while still logging genuine exceptions. See
src/services/agent/observability.py::track_node_execution.
"""

from unittest.mock import patch

import pytest
from langgraph.errors import GraphInterrupt
from langgraph.types import Interrupt

from src.services.agent.observability import track_node_execution


@pytest.mark.unit
@pytest.mark.asyncio
async def test_graph_interrupt_is_not_logged_as_error():
    """HITL interrupt must propagate without an ERROR log."""

    @track_node_execution("interrupt_node")
    async def node():
        raise GraphInterrupt((Interrupt(value={"message": "confirm"}, id="x"),))

    with patch("src.services.agent.observability.logger") as mock_logger:
        with pytest.raises(GraphInterrupt):
            await node()

    mock_logger.error.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_real_exception_is_still_logged_as_error():
    """Genuine node failures must still be logged and re-raised."""

    @track_node_execution("boom_node")
    async def node():
        raise ValueError("boom")

    with patch("src.services.agent.observability.logger") as mock_logger:
        with pytest.raises(ValueError, match="boom"):
            await node()

    mock_logger.error.assert_called_once()
