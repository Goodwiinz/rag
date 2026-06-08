"""
Layout algorithms for graph visualization
"""

import asyncio
import logging
import math
import random
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from src.services.models.visualization_models import (
    GraphLayout,
    LayoutAlgorithm,
    NodeShape,
    VisualizationEdge,
    VisualizationNode,
)

logger = logging.getLogger(__name__)


class LayoutAlgorithms:
    """Implements various graph layout algorithms"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def force_directed_layout(
        self,
        nodes: List[VisualizationNode],
        edges: List[VisualizationEdge],
        iterations: int = 1000,
        threshold: float = 1e-4,
        strength: float = 1.0,
        repulsion: float = 100.0,
        gravity: float = 0.1,
    ) -> GraphLayout:
        """Compute force-directed layout using Fruchterman-Reingold algorithm"""
        try:
            if not nodes:
                return self._create_empty_layout(LayoutAlgorithm.FORCE_DIRECTED)

            # Initialize positions randomly
            positions = self._initialize_positions(nodes, width=1000, height=1000)

            # Create adjacency list
            adj_list = self._create_adjacency_list(nodes, edges)

            # Constants
            k = math.sqrt((1000 * 1000) / len(nodes))  # Optimal distance
            temperature = 1000.0
            cooling_factor = 0.95

            # Bound total work: this is O(iterations * n^2). Scale iterations
            # down as the graph grows so a large graph can't pin a CPU for
            # minutes, and yield to the event loop periodically (the method is
            # async but had no await, so it blocked every other request).
            n = len(nodes)
            if n > 600:
                iterations = min(iterations, 60)
            elif n > 250:
                iterations = min(iterations, 150)

            for iteration in range(iterations):
                if iteration % 20 == 0:
                    await asyncio.sleep(0)  # cooperative yield
                max_displacement = 0.0
                forces = {node.id: [0.0, 0.0] for node in nodes}

                # Calculate repulsive forces between all pairs
                for i, node1 in enumerate(nodes):
                    for j, node2 in enumerate(nodes[i + 1 :], i + 1):
                        dx = positions[node2.id][0] - positions[node1.id][0]
                        dy = positions[node2.id][1] - positions[node1.id][1]
                        distance = math.sqrt(dx * dx + dy * dy)

                        if distance > 0:
                            # Fr = k^2 / d
                            force = (k * k) / distance
                            fx = force * (dx / distance)
                            fy = force * (dy / distance)

                            forces[node1.id][0] -= fx * repulsion
                            forces[node1.id][1] -= fy * repulsion
                            forces[node2.id][0] += fx * repulsion
                            forces[node2.id][1] += fy * repulsion

                # Calculate attractive forces for connected nodes
                for edge in edges:
                    source_id = edge.source
                    target_id = edge.target

                    if source_id in positions and target_id in positions:
                        dx = positions[target_id][0] - positions[source_id][0]
                        dy = positions[target_id][1] - positions[source_id][1]
                        distance = math.sqrt(dx * dx + dy * dy)

                        if distance > 0:
                            # Fa = d^2 / k
                            force = (distance * distance) / k
                            weight = edge.weight or 1.0
                            force *= weight

                            fx = force * (dx / distance)
                            fy = force * (dy / distance)

                            forces[source_id][0] += fx * strength
                            forces[source_id][1] += fy * strength
                            forces[target_id][0] -= fx * strength
                            forces[target_id][1] -= fy * strength

                # Apply gravity (pull towards center)
                center_x, center_y = 500, 500
                for node in nodes:
                    dx = center_x - positions[node.id][0]
                    dy = center_y - positions[node.id][1]
                    forces[node.id][0] += dx * gravity
                    forces[node.id][1] += dy * gravity

                # Update positions
                for node in nodes:
                    displacement = math.sqrt(
                        forces[node.id][0] ** 2 + forces[node.id][1] ** 2
                    )

                    # Limit displacement by temperature
                    if displacement > temperature:
                        scale = temperature / displacement
                        forces[node.id][0] *= scale
                        forces[node.id][1] *= scale
                        displacement = temperature

                    # Update position
                    positions[node.id][0] += forces[node.id][0]
                    positions[node.id][1] += forces[node.id][1]

                    # Keep within bounds
                    positions[node.id][0] = max(50, min(950, positions[node.id][0]))
                    positions[node.id][1] = max(50, min(950, positions[node.id][1]))

                    max_displacement = max(max_displacement, displacement)

                # Cool down temperature
                temperature *= cooling_factor

                # Check convergence
                if max_displacement < threshold:
                    break

            # Update node positions
            for node in nodes:
                node.x = positions[node.id][0]
                node.y = positions[node.id][1]

            # Create layout metadata
            bounding_box = self._calculate_bounding_box(positions)
            center = {
                "x": (bounding_box["min_x"] + bounding_box["max_x"]) / 2,
                "y": (bounding_box["min_y"] + bounding_box["max_y"]) / 2,
            }

            return GraphLayout(
                algorithm=LayoutAlgorithm.FORCE_DIRECTED,
                dimensions={"width": 1000, "height": 1000},
                center=center,
                scale=1.0,
                rotation=0.0,
                bounding_box=bounding_box,
                convergence_info={
                    "iterations": iteration + 1,
                    "final_displacement": max_displacement,
                    "converged": max_displacement < threshold,
                },
            )

        except Exception as e:
            logger.error(f"Error in force-directed layout: {e}")
            return await self.random_layout(nodes, edges)

    async def circular_layout(
        self,
        nodes: List[VisualizationNode],
        edges: List[VisualizationEdge],
        radius: float = 400.0,
    ) -> GraphLayout:
        """Compute circular layout"""
        try:
            if not nodes:
                return self._create_empty_layout(LayoutAlgorithm.CIRCULAR)

            center_x, center_y = 500, 500
            angle_step = 2 * math.pi / len(nodes)

            for i, node in enumerate(nodes):
                angle = i * angle_step
                node.x = center_x + radius * math.cos(angle)
                node.y = center_y + radius * math.sin(angle)

            # Sort nodes by degree for better visualization
            if edges:
                node_degrees = self._calculate_node_degrees(nodes, edges)
                nodes.sort(key=lambda n: node_degrees.get(n.id, 0), reverse=True)

                # Reassign positions with sorted order
                for i, node in enumerate(nodes):
                    angle = i * angle_step
                    node.x = center_x + radius * math.cos(angle)
                    node.y = center_y + radius * math.sin(angle)

            bounding_box = {
                "min_x": center_x - radius,
                "min_y": center_y - radius,
                "max_x": center_x + radius,
                "max_y": center_y + radius,
            }

            return GraphLayout(
                algorithm=LayoutAlgorithm.CIRCULAR,
                dimensions={"width": 1000, "height": 1000},
                center={"x": center_x, "y": center_y},
                scale=1.0,
                rotation=0.0,
                bounding_box=bounding_box,
            )

        except Exception as e:
            logger.error(f"Error in circular layout: {e}")
            return await self.random_layout(nodes, edges)

    async def hierarchical_layout(
        self,
        nodes: List[VisualizationNode],
        edges: List[VisualizationEdge],
        direction: str = "TB",  # TB = Top-Bottom, LR = Left-Right
    ) -> GraphLayout:
        """Compute hierarchical layout"""
        try:
            if not nodes:
                return self._create_empty_layout(LayoutAlgorithm.HIERARCHICAL)

            # Build hierarchy levels using topological sort
            levels = self._assign_hierarchy_levels(nodes, edges)

            if not levels:
                return await self.random_layout(nodes, edges)

            # Calculate level positions
            max_level = max(levels.values())
            level_height = 800 / (max_level + 1)
            level_width = 900 / max(len(set(levels.values())), 1)

            # Group nodes by level
            level_nodes = {}
            for node_id, level in levels.items():
                if level not in level_nodes:
                    level_nodes[level] = []
                level_nodes[level].append(node_id)

            # Position nodes within each level
            positions = {}
            for level, node_ids in level_nodes.items():
                x_spacing = level_width / (len(node_ids) + 1)
                for i, node_id in enumerate(node_ids):
                    if direction == "TB":
                        x = 100 + (i + 1) * x_spacing
                        y = 100 + level * level_height
                    else:  # LR
                        x = 100 + level * level_width
                        y = 100 + (i + 1) * x_spacing

                    positions[node_id] = [x, y]

            # Update node positions
            for node in nodes:
                if node.id in positions:
                    node.x = positions[node.id][0]
                    node.y = positions[node.id][1]

            bounding_box = self._calculate_bounding_box(positions)
            center = {
                "x": (bounding_box["min_x"] + bounding_box["max_x"]) / 2,
                "y": (bounding_box["min_y"] + bounding_box["max_y"]) / 2,
            }

            return GraphLayout(
                algorithm=LayoutAlgorithm.HIERARCHICAL,
                dimensions={"width": 1000, "height": 1000},
                center=center,
                scale=1.0,
                rotation=0.0,
                bounding_box=bounding_box,
                metadata={
                    "direction": direction,
                    "max_level": max_level,
                    "levels": len(level_nodes),
                },
            )

        except Exception as e:
            logger.error(f"Error in hierarchical layout: {e}")
            return await self.random_layout(nodes, edges)

    async def grid_layout(
        self,
        nodes: List[VisualizationNode],
        edges: List[VisualizationEdge],
        cols: Optional[int] = None,
    ) -> GraphLayout:
        """Compute grid layout"""
        try:
            if not nodes:
                return self._create_empty_layout(LayoutAlgorithm.GRID)

            if cols is None:
                cols = math.ceil(math.sqrt(len(nodes)))

            rows = math.ceil(len(nodes) / cols)
            cell_width = 900 / cols
            cell_height = 800 / rows

            for i, node in enumerate(nodes):
                row = i // cols
                col = i % cols
                node.x = 50 + col * cell_width + cell_width / 2
                node.y = 50 + row * cell_height + cell_height / 2

            bounding_box = {"min_x": 50, "min_y": 50, "max_x": 950, "max_y": 850}

            return GraphLayout(
                algorithm=LayoutAlgorithm.GRID,
                dimensions={"width": 1000, "height": 1000},
                center={"x": 500, "y": 450},
                scale=1.0,
                rotation=0.0,
                bounding_box=bounding_box,
                metadata={"cols": cols, "rows": rows},
            )

        except Exception as e:
            logger.error(f"Error in grid layout: {e}")
            return await self.random_layout(nodes, edges)

    async def random_layout(
        self,
        nodes: List[VisualizationNode],
        edges: List[VisualizationEdge],
        width: int = 1000,
        height: int = 1000,
    ) -> GraphLayout:
        """Compute random layout"""
        try:
            for node in nodes:
                node.x = random.uniform(50, width - 50)
                node.y = random.uniform(50, height - 50)

            bounding_box = {
                "min_x": 50,
                "min_y": 50,
                "max_x": width - 50,
                "max_y": height - 50,
            }

            return GraphLayout(
                algorithm=LayoutAlgorithm.RANDOM,
                dimensions={"width": width, "height": height},
                center={"x": width / 2, "y": height / 2},
                scale=1.0,
                rotation=0.0,
                bounding_box=bounding_box,
            )

        except Exception as e:
            logger.error(f"Error in random layout: {e}")
            return self._create_empty_layout(LayoutAlgorithm.RANDOM)

    async def spiral_layout(
        self, nodes: List[VisualizationNode], edges: List[VisualizationEdge]
    ) -> GraphLayout:
        """Compute spiral layout"""
        try:
            if not nodes:
                return self._create_empty_layout(LayoutAlgorithm.SPIRAL)

            center_x, center_y = 500, 500
            max_radius = 480  # keep nodes inside the 1000x1000 canvas
            a = 10  # Spiral tightness
            # Scale growth so the last node lands near (not past) the edge —
            # a fixed b sent nodes thousands of px off-canvas for large graphs.
            theta_max = max(1, (len(nodes) - 1)) * 0.5
            b = min(10, (max_radius - a) / theta_max)

            for i, node in enumerate(nodes):
                theta = i * 0.5
                r = min(a + b * theta, max_radius)
                node.x = center_x + r * math.cos(theta)
                node.y = center_y + r * math.sin(theta)

            bounding_box = self._calculate_bounding_box(
                {node.id: [node.x, node.y] for node in nodes}
            )

            return GraphLayout(
                algorithm=LayoutAlgorithm.SPIRAL,
                dimensions={"width": 1000, "height": 1000},
                center={"x": center_x, "y": center_y},
                scale=1.0,
                rotation=0.0,
                bounding_box=bounding_box,
            )

        except Exception as e:
            logger.error(f"Error in spiral layout: {e}")
            return await self.random_layout(nodes, edges)

    async def concentric_layout(
        self, nodes: List[VisualizationNode], edges: List[VisualizationEdge]
    ) -> GraphLayout:
        """Compute concentric layout based on node importance"""
        try:
            if not nodes:
                return self._create_empty_layout(LayoutAlgorithm.CONCENTRIC)

            # Calculate node importance (using degree as proxy)
            node_degrees = self._calculate_node_degrees(nodes, edges)
            sorted_nodes = sorted(
                nodes, key=lambda n: node_degrees.get(n.id, 0), reverse=True
            )

            # Assign nodes to concentric circles
            num_circles = min(5, len(sorted_nodes))
            nodes_per_circle = math.ceil(len(sorted_nodes) / num_circles)

            # Group nodes into circles ONCE (was O(n^2): a slice rebuild +
            # list.index() per node, with a ZeroDivision/off-by-one footgun
            # that silently fell back to random layout).
            center_x, center_y = 500, 500
            circles: dict[int, list] = {}
            for i, node in enumerate(sorted_nodes):
                circles.setdefault(i // nodes_per_circle, []).append(node)

            positions = {}
            for circle, circle_nodes in circles.items():
                radius = 100 + circle * 80
                count = len(circle_nodes)
                angle_step = (2 * math.pi / count) if count else 0
                for idx, node in enumerate(circle_nodes):
                    angle = idx * angle_step
                    positions[node.id] = [
                        center_x + radius * math.cos(angle),
                        center_y + radius * math.sin(angle),
                    ]

            # Update node positions
            for node in nodes:
                if node.id in positions:
                    node.x = positions[node.id][0]
                    node.y = positions[node.id][1]

            bounding_box = self._calculate_bounding_box(positions)
            center = {"x": 500, "y": 500}

            return GraphLayout(
                algorithm=LayoutAlgorithm.CONCENTRIC,
                dimensions={"width": 1000, "height": 1000},
                center=center,
                scale=1.0,
                rotation=0.0,
                bounding_box=bounding_box,
                metadata={
                    "num_circles": num_circles,
                    "nodes_per_circle": nodes_per_circle,
                },
            )

        except Exception as e:
            logger.error(f"Error in concentric layout: {e}")
            return await self.random_layout(nodes, edges)

    # Helper methods
    def _initialize_positions(
        self, nodes: List[VisualizationNode], width: int, height: int
    ) -> Dict[str, List[float]]:
        """Initialize random positions for nodes"""
        positions = {}
        for node in nodes:
            positions[node.id] = [
                random.uniform(50, width - 50),
                random.uniform(50, height - 50),
            ]
        return positions

    def _create_adjacency_list(
        self, nodes: List[VisualizationNode], edges: List[VisualizationEdge]
    ) -> Dict[str, List[str]]:
        """Create adjacency list from edges"""
        adj_list = {node.id: [] for node in nodes}
        for edge in edges:
            if edge.source in adj_list:
                adj_list[edge.source].append(edge.target)
            if edge.target in adj_list:
                adj_list[edge.target].append(edge.source)
        return adj_list

    def _calculate_node_degrees(
        self, nodes: List[VisualizationNode], edges: List[VisualizationEdge]
    ) -> Dict[str, int]:
        """Calculate degree for each node"""
        degrees = {node.id: 0 for node in nodes}
        for edge in edges:
            if edge.source in degrees:
                degrees[edge.source] += 1
            if edge.target in degrees:
                degrees[edge.target] += 1
        return degrees

    def _calculate_bounding_box(
        self, positions: Dict[str, List[float]]
    ) -> Dict[str, float]:
        """Calculate bounding box of positions"""
        if not positions:
            return {"min_x": 0, "min_y": 0, "max_x": 1000, "max_y": 1000}

        x_coords = [pos[0] for pos in positions.values()]
        y_coords = [pos[1] for pos in positions.values()]

        return {
            "min_x": min(x_coords),
            "min_y": min(y_coords),
            "max_x": max(x_coords),
            "max_y": max(y_coords),
        }

    def _assign_hierarchy_levels(
        self, nodes: List[VisualizationNode], edges: List[VisualizationEdge]
    ) -> Dict[str, int]:
        """Assign hierarchy levels using Kahn's topological sort.

        The previous relaxation loop never converged on cycles/self-loops
        (it incremented levels until an arbitrary iteration cap, leaving
        garbage levels). Kahn's sort terminates deterministically: self-loops
        and parallel edges are dropped, and any nodes left in a cycle keep the
        default level 0.
        """
        from collections import deque

        node_ids = {node.id for node in nodes}
        adj: Dict[str, List[str]] = {nid: [] for nid in node_ids}
        indegree: Dict[str, int] = {nid: 0 for nid in node_ids}
        seen: set = set()
        for edge in edges:
            if edge.source == edge.target:  # skip self-loops
                continue
            if edge.source not in node_ids or edge.target not in node_ids:
                continue
            key = (edge.source, edge.target)
            if key in seen:  # dedupe parallel edges
                continue
            seen.add(key)
            adj[edge.source].append(edge.target)
            indegree[edge.target] += 1

        levels = {nid: 0 for nid in node_ids}
        queue = deque(nid for nid, deg in indegree.items() if deg == 0)
        while queue:
            nid = queue.popleft()
            for target in adj[nid]:
                if levels[nid] + 1 > levels[target]:
                    levels[target] = levels[nid] + 1
                indegree[target] -= 1
                if indegree[target] == 0:
                    queue.append(target)

        return levels

    def _create_empty_layout(self, algorithm: LayoutAlgorithm) -> GraphLayout:
        """Create empty layout for empty graph"""
        return GraphLayout(
            algorithm=algorithm,
            dimensions={"width": 1000, "height": 1000},
            center={"x": 500, "y": 500},
            scale=1.0,
            rotation=0.0,
            bounding_box={"min_x": 500, "min_y": 500, "max_x": 500, "max_y": 500},
        )
