"""
Data preprocessing service for graph visualization
"""

import asyncio
import logging
from typing import List, Dict, Any, Tuple, Optional
from collections import defaultdict

from ..models.visualization_models import VisualizationNode, VisualizationEdge

logger = logging.getLogger(__name__)


class DataPreprocessor:
    """Preprocesses graph data for visualization"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def process(
        self,
        raw_nodes: List[Dict[str, Any]],
        raw_edges: List[Dict[str, Any]],
        options: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Process raw graph data"""
        try:
            options = options or {}

            # Apply preprocessing steps
            processed_nodes = raw_nodes.copy()
            processed_edges = raw_edges.copy()

            # Remove isolated nodes if requested
            if options.get("remove_isolated_nodes", False):
                processed_nodes, processed_edges = self._remove_isolated_nodes(
                    processed_nodes, processed_edges
                )

            # Filter by degree if requested
            if "min_degree" in options:
                processed_nodes, processed_edges = self._filter_by_degree(
                    processed_nodes, processed_edges, options["min_degree"]
                )

            # Filter by edge strength if requested
            if "min_strength" in options:
                processed_edges = self._filter_edges_by_strength(
                    processed_edges, options["min_strength"]
                )

            # Sample similar nodes if requested
            if options.get("sample_similar_nodes", False):
                processed_nodes, processed_edges = self._sample_similar_nodes(
                    processed_nodes, processed_edges, options.get("max_similar_nodes", 10)
                )

            # Collapse clusters if requested
            if options.get("collapse_clusters", False):
                processed_nodes, processed_edges = self._collapse_clusters(
                    processed_nodes, processed_edges
                )

            # Add computed properties
            processed_nodes = self._add_computed_properties(processed_nodes, processed_edges)
            processed_edges = self._add_edge_properties(processed_edges)

            return processed_nodes, processed_edges

        except Exception as e:
            logger.error(f"Error preprocessing data: {e}")
            return raw_nodes, raw_edges

    def _remove_isolated_nodes(
        self,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Remove nodes with no connections"""
        # Get connected node IDs
        connected_nodes = set()
        for edge in edges:
            connected_nodes.add(edge["source"])
            connected_nodes.add(edge["target"])

        # Filter nodes
        filtered_nodes = [
            node for node in nodes
            if node["id"] in connected_nodes
        ]

        return filtered_nodes, edges

    def _filter_by_degree(
        self,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
        min_degree: int
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Filter nodes by minimum degree"""
        # Calculate degrees
        node_degrees = defaultdict(int)
        for edge in edges:
            node_degrees[edge["source"]] += 1
            node_degrees[edge["target"]] += 1

        # Filter nodes
        filtered_nodes = [
            node for node in nodes
            if node_degrees[node["id"]] >= min_degree
        ]

        # Get filtered node IDs
        filtered_node_ids = {node["id"] for node in filtered_nodes}

        # Filter edges
        filtered_edges = [
            edge for edge in edges
            if edge["source"] in filtered_node_ids and edge["target"] in filtered_node_ids
        ]

        return filtered_nodes, filtered_edges

    def _filter_edges_by_strength(
        self,
        edges: List[Dict[str, Any]],
        min_strength: float
    ) -> List[Dict[str, Any]]:
        """Filter edges by minimum strength"""
        filtered_edges = []
        for edge in edges:
            strength = edge.get("properties", {}).get("strength", 1.0)
            if strength >= min_strength:
                filtered_edges.append(edge)

        return filtered_edges

    def _sample_similar_nodes(
        self,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
        max_per_type: int = 10
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Sample similar nodes to reduce visual clutter"""
        # Group nodes by type and properties
        node_groups = defaultdict(list)
        for node in nodes:
            # Create grouping key based on type and major properties
            key = node["type"]
            if "properties" in node:
                # Add some key properties to grouping
                props = node["properties"]
                if "category" in props:
                    key += f"_{props['category']}"
                if "level" in props:
                    key += f"_{props['level']}"

            node_groups[key].append(node)

        # Sample nodes from each group
        sampled_nodes = []
        for group_nodes in node_groups.values():
            if len(group_nodes) > max_per_type:
                # Sort by degree or importance if available
                if "degree" in group_nodes[0]:
                    group_nodes.sort(key=lambda n: n.get("degree", 0), reverse=True)
                else:
                    # Random sampling
                    import random
                    random.shuffle(group_nodes)

                sampled_nodes.extend(group_nodes[:max_per_type])
            else:
                sampled_nodes.extend(group_nodes)

        # Get sampled node IDs
        sampled_node_ids = {node["id"] for node in sampled_nodes}

        # Filter edges
        filtered_edges = [
            edge for edge in edges
            if edge["source"] in sampled_node_ids and edge["target"] in sampled_node_ids
        ]

        return sampled_nodes, filtered_edges

    def _collapse_clusters(
        self,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
        cluster_threshold: float = 0.8
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Collapse densely connected clusters into single nodes"""
        # This is a simplified implementation
        # In practice, you'd use a proper community detection algorithm

        # For now, just group by type and create cluster nodes
        type_groups = defaultdict(list)
        for node in nodes:
            type_groups[node["type"]].append(node)

        collapsed_nodes = []
        collapsed_edges = []

        # Create cluster nodes
        for node_type, group_nodes in type_groups.items():
            if len(group_nodes) > 1:  # Only collapse if multiple nodes
                cluster_id = f"cluster_{node_type}"
                collapsed_node = {
                    "id": cluster_id,
                    "label": f"{node_type} Cluster ({len(group_nodes)} nodes)",
                    "type": "cluster",
                    "properties": {
                        "original_type": node_type,
                        "node_count": len(group_nodes),
                        "member_ids": [n["id"] for n in group_nodes]
                    },
                    "degree": sum(n.get("degree", 0) for n in group_nodes)
                }
                collapsed_nodes.append(collapsed_node)
            else:
                collapsed_nodes.extend(group_nodes)

        # Create edges between clusters
        cluster_nodes = {n["id"]: n for n in collapsed_nodes if n["type"] == "cluster"}
        regular_nodes = {n["id"]: n for n in collapsed_nodes if n["type"] != "cluster"}

        for edge in edges:
            source_cluster = self._find_cluster_for_node(edge["source"], cluster_nodes, regular_nodes)
            target_cluster = self._find_cluster_for_node(edge["target"], cluster_nodes, regular_nodes)

            if source_cluster and target_cluster and source_cluster != target_cluster:
                collapsed_edge = {
                    "id": f"edge_{source_cluster}_{target_cluster}",
                    "source": source_cluster,
                    "target": target_cluster,
                    "type": edge["type"],
                    "properties": {
                        "original_edges": 1,
                        "total_strength": edge.get("properties", {}).get("strength", 1.0)
                    }
                }
                collapsed_edges.append(collapsed_edge)

        return collapsed_nodes, collapsed_edges

    def _find_cluster_for_node(
        self,
        node_id: str,
        cluster_nodes: Dict[str, Dict[str, Any]],
        regular_nodes: Dict[str, Dict[str, Any]]
    ) -> Optional[str]:
        """Find which cluster a node belongs to"""
        # Check if it's a regular node that belongs to a cluster
        if node_id in regular_nodes:
            node = regular_nodes[node_id]
            # Look for a cluster that contains this node
            for cluster_id, cluster in cluster_nodes.items():
                member_ids = cluster.get("properties", {}).get("member_ids", [])
                if node_id in member_ids:
                    return cluster_id

        # Check if it's already a cluster node
        if node_id in cluster_nodes:
            return node_id

        return None

    def _add_computed_properties(
        self,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Add computed properties to nodes"""
        # Calculate degrees
        node_degrees = defaultdict(int)
        node_strength = defaultdict(float)

        for edge in edges:
            strength = edge.get("properties", {}).get("strength", 1.0)
            node_degrees[edge["source"]] += 1
            node_degrees[edge["target"]] += 1
            node_strength[edge["source"]] += strength
            node_strength[edge["target"]] += strength

        # Add properties to nodes
        for node in nodes:
            node_id = node["id"]
            node["degree"] = node_degrees.get(node_id, 0)
            node["total_strength"] = node_strength.get(node_id, 0.0)
            node["avg_strength"] = (
                node["total_strength"] / node["degree"]
                if node["degree"] > 0 else 0.0
            )

            # Add normalized degree (0-1)
            if node_degrees:
                max_degree = max(node_degrees.values())
                node["normalized_degree"] = node["degree"] / max_degree if max_degree > 0 else 0.0

        return nodes

    def _add_edge_properties(
        self,
        edges: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Add computed properties to edges"""
        for edge in edges:
            # Ensure strength property exists
            if "properties" not in edge:
                edge["properties"] = {}

            if "strength" not in edge["properties"]:
                edge["properties"]["strength"] = edge.get("weight", 1.0)

            # Add edge type classification
            edge_type = edge.get("type", "RELATED_TO")
            edge["properties"]["edge_category"] = self._categorize_edge_type(edge_type)

        return edges

    def _categorize_edge_type(self, edge_type: str) -> str:
        """Categorize edge type for styling"""
        edge_type = edge_type.lower()

        if any(keyword in edge_type for keyword in ["work", "employ", "manage", "report"]):
            return "organizational"
        elif any(keyword in edge_type for keyword in ["know", "friend", "colleague", "relate"]):
            return "social"
        elif any(keyword in edge_type for keyword in ["located", "based", "place"]):
            return "geographic"
        elif any(keyword in edge_type for keyword in ["part", "member", "belong"]):
            return "membership"
        elif any(keyword in edge_type for keyword in ["create", "author", "produce"]):
            return "creation"
        else:
            return "general"

    async def apply_dynamic_filtering(
        self,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
        filters: Dict[str, Any]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Apply dynamic filtering based on user input"""
        try:
            filtered_nodes = nodes.copy()
            filtered_edges = edges.copy()

            # Filter by node types
            if "node_types" in filters and filters["node_types"]:
                allowed_types = set(filters["node_types"])
                filtered_nodes = [
                    node for node in filtered_nodes
                    if node["type"] in allowed_types
                ]

            # Filter by edge types
            if "edge_types" in filters and filters["edge_types"]:
                allowed_types = set(filters["edge_types"])
                filtered_edges = [
                    edge for edge in filtered_edges
                    if edge["type"] in allowed_types
                ]

            # Filter by degree range
            if "degree_range" in filters:
                min_degree, max_degree = filters["degree_range"]
                filtered_nodes = [
                    node for node in filtered_nodes
                    if min_degree <= node.get("degree", 0) <= max_degree
                ]

            # Filter by strength range
            if "strength_range" in filters:
                min_strength, max_strength = filters["strength_range"]
                filtered_edges = [
                    edge for edge in filtered_edges
                    if min_strength <= edge.get("properties", {}).get("strength", 1.0) <= max_strength
                ]

            # Filter by date range
            if "date_range" in filters:
                start_date, end_date = filters["date_range"]
                filtered_nodes = [
                    node for node in filtered_nodes
                    if self._is_in_date_range(node, start_date, end_date)
                ]

            # Rebuild edges to match filtered nodes
            filtered_node_ids = {node["id"] for node in filtered_nodes}
            filtered_edges = [
                edge for edge in filtered_edges
                if edge["source"] in filtered_node_ids and edge["target"] in filtered_node_ids
            ]

            return filtered_nodes, filtered_edges

        except Exception as e:
            logger.error(f"Error applying dynamic filtering: {e}")
            return nodes, edges

    def _is_in_date_range(
        self,
        node: Dict[str, Any],
        start_date: Any,
        end_date: Any
    ) -> bool:
        """Check if node is within date range"""
        # This would need proper date handling based on the actual date format
        # For now, return True as a placeholder
        return True