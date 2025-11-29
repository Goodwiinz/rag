"""
Performance optimization service for graph visualization
"""

import logging
from typing import Dict, Any, List, Optional
from ..models.visualization_models import GraphSizeCategory

logger = logging.getLogger(__name__)


class PerformanceOptimizer:
    """Optimizes graph visualization performance based on graph size"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def get_optimizations(self, size_category: GraphSizeCategory) -> Dict[str, Any]:
        """Get performance optimizations based on graph size"""
        optimizations = {}

        if size_category == GraphSizeCategory.SMALL:
            # Small graphs (< 100 nodes)
            optimizations = {
                "sample_nodes": None,
                "filter_edges": None,
                "simple_layout": False,
                "enable_animations": True,
                "real_time_updates": True,
                "cache_layout": True,
                "progressive_loading": False
            }

        elif size_category == GraphSizeCategory.MEDIUM:
            # Medium graphs (100-1000 nodes)
            optimizations = {
                "sample_nodes": None,
                "filter_edges": {
                    "min_strength": 0.1
                },
                "simple_layout": False,
                "enable_animations": True,
                "real_time_updates": True,
                "cache_layout": True,
                "progressive_loading": False
            }

        elif size_category == GraphSizeCategory.LARGE:
            # Large graphs (1000-10000 nodes)
            optimizations = {
                "sample_nodes": 1000,
                "filter_edges": {
                    "min_strength": 0.2,
                    "remove_weak_edges": True
                },
                "simple_layout": True,
                "enable_animations": False,
                "real_time_updates": False,
                "cache_layout": True,
                "progressive_loading": True,
                "preprocessing_options": {
                    "remove_isolated_nodes": True,
                    "min_degree": 2,
                    "sample_similar_nodes": True,
                    "max_similar_nodes": 10
                }
            }

        elif size_category == GraphSizeCategory.EXTRA_LARGE:
            # Extra large graphs (> 10000 nodes)
            optimizations = {
                "sample_nodes": 500,
                "filter_edges": {
                    "min_strength": 0.3,
                    "remove_weak_edges": True,
                    "max_edges_per_node": 50
                },
                "simple_layout": True,
                "enable_animations": False,
                "real_time_updates": False,
                "cache_layout": True,
                "progressive_loading": True,
                "preprocessing_options": {
                    "remove_isolated_nodes": True,
                    "min_degree": 3,
                    "sample_similar_nodes": True,
                    "max_similar_nodes": 5,
                    "collapse_clusters": True
                },
                "rendering_options": {
                    "simplify_rendering": True,
                    "level_of_detail": True,
                    "occlusion_culling": True,
                    "viewport_culling": True
                }
            }

        return optimizations

    def get_layout_recommendations(self, size_category: GraphSizeCategory) -> List[str]:
        """Get recommended layout algorithms based on graph size"""
        recommendations = []

        if size_category == GraphSizeCategory.SMALL:
            recommendations = [
                "force_directed",
                "circular",
                "hierarchical",
                "grid",
                "spiral",
                "concentric"
            ]
        elif size_category == GraphSizeCategory.MEDIUM:
            recommendations = [
                "force_directed",
                "hierarchical",
                "circular",
                "grid"
            ]
        elif size_category == GraphSizeCategory.LARGE:
            recommendations = [
                "grid",
                "hierarchical",
                "circular"
            ]
        elif size_category == GraphSizeCategory.EXTRA_LARGE:
            recommendations = [
                "grid",
                "random"  # Fastest for very large graphs
            ]

        return recommendations

    def get_rendering_settings(self, size_category: GraphSizeCategory) -> Dict[str, Any]:
        """Get optimized rendering settings"""
        settings = {}

        if size_category == GraphSizeCategory.SMALL:
            settings = {
                "show_labels": True,
                "label_threshold": 0,
                "font_size": 12,
                "edge_width_range": [1, 5],
                "node_size_range": [5, 20],
                "enable_transitions": True,
                "enable_interactions": True
            }

        elif size_category == GraphSizeCategory.MEDIUM:
            settings = {
                "show_labels": True,
                "label_threshold": 1,
                "font_size": 10,
                "edge_width_range": [1, 4],
                "node_size_range": [4, 15],
                "enable_transitions": True,
                "enable_interactions": True
            }

        elif size_category == GraphSizeCategory.LARGE:
            settings = {
                "show_labels": False,
                "label_threshold": 5,
                "font_size": 8,
                "edge_width_range": [1, 3],
                "node_size_range": [3, 10],
                "enable_transitions": False,
                "enable_interactions": False,
                "simplify_edges": True
            }

        elif size_category == GraphSizeCategory.EXTRA_LARGE:
            settings = {
                "show_labels": False,
                "label_threshold": 10,
                "font_size": 6,
                "edge_width_range": [1, 2],
                "node_size_range": [2, 8],
                "enable_transitions": False,
                "enable_interactions": False,
                "simplify_edges": True,
                "level_of_detail": True
            }

        return settings

    def estimate_memory_usage(
        self,
        node_count: int,
        edge_count: int,
        include_layout: bool = True,
        include_style: bool = True
    ) -> Dict[str, float]:
        """Estimate memory usage for visualization"""
        # Base memory per node/edge (in bytes)
        base_node_memory = 200  # ID, label, type, basic properties
        base_edge_memory = 150  # ID, source, target, type, basic properties

        # Additional memory for layout
        layout_memory_per_node = 16 if include_layout else 0  # x, y coordinates

        # Additional memory for styling
        style_memory_per_node = 32 if include_style else 0  # color, size, shape
        style_memory_per_edge = 16 if include_style else 0  # color, width

        # Calculate total memory
        node_memory = node_count * (base_node_memory + layout_memory_per_node + style_memory_per_node)
        edge_memory = edge_count * (base_edge_memory + style_memory_per_edge)

        # Add overhead for data structures (approximately 20%)
        overhead = (node_memory + edge_memory) * 0.2

        total_memory = node_memory + edge_memory + overhead

        return {
            "node_memory_mb": node_memory / (1024 * 1024),
            "edge_memory_mb": edge_memory / (1024 * 1024),
            "layout_memory_mb": (node_count * layout_memory_per_node) / (1024 * 1024),
            "style_memory_mb": ((node_count * style_memory_per_node) + (edge_count * style_memory_per_edge)) / (1024 * 1024),
            "overhead_mb": overhead / (1024 * 1024),
            "total_memory_mb": total_memory / (1024 * 1024)
        }

    def estimate_rendering_time(
        self,
        node_count: int,
        edge_count: int,
        layout_algorithm: str = "force_directed",
        hardware_tier: str = "medium"  # low, medium, high
    ) -> Dict[str, float]:
        """Estimate rendering and layout computation time"""
        # Base rendering times (in seconds)
        base_times = {
            "low": {
                "nodes_per_second": 1000,
                "edges_per_second": 5000,
                "layout_multiplier": 10.0
            },
            "medium": {
                "nodes_per_second": 5000,
                "edges_per_second": 20000,
                "layout_multiplier": 3.0
            },
            "high": {
                "nodes_per_second": 10000,
                "edges_per_second": 50000,
                "layout_multiplier": 1.0
            }
        }

        base = base_times.get(hardware_tier, base_times["medium"])

        # Layout algorithm complexity multipliers
        layout_multipliers = {
            "force_directed": 5.0,
            "circular": 1.0,
            "hierarchical": 2.0,
            "grid": 0.5,
            "random": 0.1,
            "spiral": 1.5,
            "concentric": 2.5
        }

        # Calculate times
        node_render_time = node_count / base["nodes_per_second"]
        edge_render_time = edge_count / base["edges_per_second"]

        layout_multiplier = layout_multipliers.get(layout_algorithm, 1.0)
        layout_time = (
            (node_count * layout_multiplier / base["nodes_per_second"]) *
            base["layout_multiplier"]
        )

        total_time = node_render_time + edge_render_time + layout_time

        return {
            "node_render_time_seconds": node_render_time,
            "edge_render_time_seconds": edge_render_time,
            "layout_time_seconds": layout_time,
            "total_time_seconds": total_time,
            "hardware_tier": hardware_tier
        }

    def get_cache_strategy(self, size_category: GraphSizeCategory) -> Dict[str, Any]:
        """Get caching strategy based on graph size"""
        strategies = {
            GraphSizeCategory.SMALL: {
                "cache_layout": True,
                "cache_style": True,
                "cache_data": False,
                "ttl_seconds": 1800,  # 30 minutes
                "max_cache_size": 100
            },
            GraphSizeCategory.MEDIUM: {
                "cache_layout": True,
                "cache_style": True,
                "cache_data": True,
                "ttl_seconds": 3600,  # 1 hour
                "max_cache_size": 50
            },
            GraphSizeCategory.LARGE: {
                "cache_layout": True,
                "cache_style": True,
                "cache_data": True,
                "ttl_seconds": 7200,  # 2 hours
                "max_cache_size": 20
            },
            GraphSizeCategory.EXTRA_LARGE: {
                "cache_layout": True,
                "cache_style": False,  # Recompute for large graphs
                "cache_data": True,
                "ttl_seconds": 14400,  # 4 hours
                "max_cache_size": 10
            }
        }

        return strategies.get(size_category, strategies[GraphSizeCategory.MEDIUM])

    def optimize_for_device(self, size_category: GraphSizeCategory, device_info: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize based on device capabilities"""
        optimizations = self.get_optimizations(size_category)

        # Device-specific adjustments
        if device_info.get("is_mobile", False):
            # Mobile optimizations
            optimizations.update({
                "simple_layout": True,
                "enable_animations": False,
                "progressive_loading": True,
                "batch_size": 200,  # Smaller batches for mobile
                "touch_optimized": True,
                "simplify_interactions": True
            })

        # Adjust based on device memory
        device_memory_gb = device_info.get("memory_gb", 4)
        if device_memory_gb < 4:
            # Low memory device
            optimizations.update({
                "sample_nodes": min(optimizations.get("sample_nodes", 1000), 300),
                "simple_layout": True,
                "cache_layout": False
            })

        # Adjust based on device performance
        performance_score = device_info.get("performance_score", 0.5)  # 0-1 scale
        if performance_score < 0.3:
            # Low performance device
            optimizations.update({
                "simple_layout": True,
                "enable_animations": False,
                "progressive_loading": True,
                "reduce_quality": True
            })

        return optimizations

    def get_progressive_loading_config(self, size_category: GraphSizeCategory) -> Dict[str, Any]:
        """Get progressive loading configuration"""
        configs = {
            GraphSizeCategory.SMALL: {
                "enabled": False,
                "batch_size": 0,
                "max_batches": 1
            },
            GraphSizeCategory.MEDIUM: {
                "enabled": False,
                "batch_size": 0,
                "max_batches": 1
            },
            GraphSizeCategory.LARGE: {
                "enabled": True,
                "batch_size": 500,
                "max_batches": 10,
                "initial_batch_size": 200,
                "load_priority": "centrality"  # Load important nodes first
            },
            GraphSizeCategory.EXTRA_LARGE: {
                "enabled": True,
                "batch_size": 200,
                "max_batches": 20,
                "initial_batch_size": 100,
                "load_priority": "centrality",
                "adaptive_batch_size": True,
                "quality_levels": ["low", "medium", "high"]
            }
        }

        return configs.get(size_category, configs[GraphSizeCategory.MEDIUM])

    def monitor_performance(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Monitor performance and suggest optimizations"""
        suggestions = []

        # Check memory usage
        if metrics.get("memory_usage_mb", 0) > 1000:  # > 1GB
            suggestions.append({
                "type": "memory",
                "severity": "high",
                "message": "High memory usage detected",
                "recommendations": [
                    "Reduce node count",
                    "Enable progressive loading",
                    "Use simpler layout algorithm"
                ]
            })

        # Check rendering time
        if metrics.get("rendering_time_seconds", 0) > 5:
            suggestions.append({
                "type": "performance",
                "severity": "medium",
                "message": "Slow rendering detected",
                "recommendations": [
                    "Use grid layout for large graphs",
                    "Reduce edge count",
                    "Disable animations"
                ]
            })

        # Check cache efficiency
        cache_hit_rate = metrics.get("cache_hit_rate", 0)
        if cache_hit_rate < 0.3:
            suggestions.append({
                "type": "cache",
                "severity": "low",
                "message": "Low cache hit rate",
                "recommendations": [
                    "Increase cache TTL",
                    "Optimize cache keys",
                    "Cache more aggressively"
                ]
            })

        return {
            "suggestions": suggestions,
            "overall_health": "good" if not suggestions else "needs_attention",
            "metrics": metrics
        }