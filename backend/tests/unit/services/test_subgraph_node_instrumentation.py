"""Guard that research/writing subgraph nodes carry node-execution metrics.

The main graph instruments every node with @track_node_execution, but the
research and writing subgraphs were entirely uninstrumented — no
AGENT_NODE_DURATION / AGENT_ERRORS for the subgraph LLM, force-synthesis, or
interrupt nodes, a dashboard blind spot for the actual research/writing work.
These assert the decorator is applied (it wraps via functools.wraps, exposing
__wrapped__) so the instrumentation can't silently regress.
"""

import pytest


@pytest.mark.unit
def test_research_subgraph_nodes_are_instrumented():
    from src.services.agent.subgraphs import research_agent as r

    for fn in (
        r.research_llm_node,
        r.research_force_synthesis_node,
        r.research_interrupt_node,
    ):
        assert hasattr(
            fn, "__wrapped__"
        ), f"{fn.__name__} missing @track_node_execution"


@pytest.mark.unit
def test_writing_subgraph_nodes_are_instrumented():
    from src.services.agent.subgraphs import writing_agent as w

    for fn in (
        w.writing_llm_node,
        w.writing_force_synthesis_node,
        w.writing_interrupt_node,
    ):
        assert hasattr(
            fn, "__wrapped__"
        ), f"{fn.__name__} missing @track_node_execution"
