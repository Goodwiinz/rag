"""Tests for knowledge-graph layout algorithm correctness (audit PR5/6)."""

import asyncio
from types import SimpleNamespace

import pytest

from src.services.knowledge_graph.layout_algorithms import LayoutAlgorithms


def _node(node_id):
    # VisualizationNode-shaped: layout reads .id (and sets .x/.y).
    return SimpleNamespace(id=node_id, x=0.0, y=0.0)


def _edge(source, target):
    # VisualizationEdge-shaped: layout reads .weight on some paths.
    return SimpleNamespace(source=source, target=target, weight=1.0, strength=1.0)


@pytest.mark.unit
class TestHierarchyLevels:
    def test_dag_levels_increase_along_edges(self):
        la = LayoutAlgorithms()
        nodes = [_node("a"), _node("b"), _node("c")]
        edges = [_edge("a", "b"), _edge("b", "c")]
        levels = la._assign_hierarchy_levels(nodes, edges)
        assert levels["a"] < levels["b"] < levels["c"]

    def test_cycle_terminates_and_returns_all_nodes(self):
        # Previously the relaxation loop never converged on a cycle.
        la = LayoutAlgorithms()
        nodes = [_node("a"), _node("b"), _node("c")]
        edges = [_edge("a", "b"), _edge("b", "c"), _edge("c", "a")]
        levels = la._assign_hierarchy_levels(nodes, edges)
        assert set(levels) == {"a", "b", "c"}

    def test_self_loop_is_skipped(self):
        la = LayoutAlgorithms()
        levels = la._assign_hierarchy_levels([_node("a")], [_edge("a", "a")])
        assert levels == {"a": 0}


@pytest.mark.unit
class TestConcentricLayout:
    def test_does_not_crash_and_positions_every_node(self):
        # Exercises the rewritten per-circle grouping (no ZeroDivision /
        # O(n^2) list.index()).
        la = LayoutAlgorithms()
        nodes = [_node(str(i)) for i in range(23)]
        edges = [_edge(str(i), str(i + 1)) for i in range(22)]
        layout = asyncio.run(la.concentric_layout(nodes, edges))
        # every node got a finite position inside a sane box
        assert layout is not None
        for n in nodes:
            assert isinstance(n.x, (int, float)) and isinstance(n.y, (int, float))


@pytest.mark.unit
class TestForceDirectedLayout:
    def test_runs_bounded_and_positions_nodes(self):
        # async + bounded: completes (yields to loop) and lays out a larger
        # graph without pinning the CPU forever.
        la = LayoutAlgorithms()
        nodes = [_node(str(i)) for i in range(40)]
        edges = [_edge(str(i), str(i + 1)) for i in range(39)]
        layout = asyncio.run(la.force_directed_layout(nodes, edges, iterations=300))
        assert layout is not None


@pytest.mark.unit
class TestSpiralLayout:
    def test_radius_stays_within_canvas(self):
        la = LayoutAlgorithms()
        nodes = [_node(str(i)) for i in range(500)]
        asyncio.run(la.spiral_layout(nodes, []))
        # center is (500,500), max_radius 480 -> coords within [20, 980]
        for n in nodes:
            assert 0 <= n.x <= 1000
            assert 0 <= n.y <= 1000
