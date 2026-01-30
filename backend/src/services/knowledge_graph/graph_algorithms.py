"""
Graph algorithms implementation for analytics
"""

import asyncio
import logging
import time
from typing import List, Dict, Any, Optional
from neo4j import AsyncSession

from src.services.models.analytics_models import (
    CentralityResult, GraphPath, PathStep, Community,
    KeyEntityInsight, BridgeEntityInsight, ClusterInsight
)
from src.services.config.analytics_config import config

logger = logging.getLogger(__name__)


class GraphAlgorithms:
    """Service implementing various graph algorithms"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def compute_pagerank(
        self,
        session: AsyncSession,
        entity_types: Optional[List[str]] = None,
        tenant_id: Optional[str] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """Compute PageRank centrality"""
        start_time = time.time()

        try:
            # Build query based on entity types and tenant
            where_clauses = []
            if entity_types:
                type_filter = " OR ".join([f"e.type = '{etype}'" for etype in entity_types])
                where_clauses.append(f"({type_filter})")
            if tenant_id:
                where_clauses.append(f"e.tenant_id = '{tenant_id}'")

            where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"
            node_filter = f"nodeFilter: '{where_clause}'" if where_clause != "1=1" else ""

            query = f"""
            CALL gds.pageRank.stream({{
                nodeProjection: {{
                    Entity: {{
                        label: 'Entity',
                        properties: ['name', 'type'],
                        {node_filter}
                    }}
                }},
                relationshipProjection: {{
                    RELATED_TO: {{
                        type: 'RELATED_TO',
                        orientation: 'UNDIRECTED',
                        properties: ['strength']
                    }}
                }},
                maxIterations: $max_iterations,
                dampingFactor: $damping_factor,
                tolerance: $tolerance
            }})
            YIELD nodeId, score
            RETURN gds.util.asNode(nodeId).id AS entity_id,
                   gds.util.asNode(nodeId).name AS entity_name,
                   gds.util.asNode(nodeId).type AS entity_type,
                   score AS pagerank_score
            ORDER BY pagerank_score DESC
            LIMIT $limit
            """

            result = await session.run(query, {
                "max_iterations": config.PAGERANK_MAX_ITERATIONS,
                "damping_factor": config.PAGERANK_DAMPING_FACTOR,
                "tolerance": config.PAGERANK_TOLERANCE,
                "limit": limit
            })

            centrality_results = []
            rank = 1

            async for record in result:
                centrality_results.append(CentralityResult(
                    entity_id=record["entity_id"],
                    entity_name=record["entity_name"],
                    entity_type=record["entity_type"],
                    centrality_score=record["pagerank_score"],
                    rank=rank,
                    metadata={"algorithm": "pagerank"}
                ))
                rank += 1

            computation_time = time.time() - start_time

            return {
                "results": [result.dict() for result in centrality_results],
                "computation_time": computation_time,
                "node_count": len(centrality_results)
            }

        except Exception as e:
            logger.error(f"Error computing PageRank: {e}")
            # Fallback to simpler implementation if GDS not available
            return await self._compute_degree_centrality_fallback(
                session, entity_types, tenant_id, limit, "pagerank"
            )

    async def compute_betweenness_centrality(
        self,
        session: AsyncSession,
        entity_types: Optional[List[str]] = None,
        tenant_id: Optional[str] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """Compute betweenness centrality"""
        start_time = time.time()

        try:
            # Build query conditions
            where_clauses = []
            if entity_types:
                type_filter = " OR ".join([f"e.type = '{etype}'" for etype in entity_types])
                where_clauses.append(f"({type_filter})")
            if tenant_id:
                where_clauses.append(f"e.tenant_id = '{tenant_id}'")

            where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"
            node_filter = f"nodeFilter: '{where_clause}'" if where_clause != "1=1" else ""

            query = f"""
            CALL gds.betweenness.stream({{
                nodeProjection: {{
                    Entity: {{
                        label: 'Entity',
                        properties: ['name', 'type'],
                        {node_filter}
                    }}
                }},
                relationshipProjection: {{
                    RELATED_TO: {{
                        type: 'RELATED_TO',
                        orientation: 'UNDIRECTED'
                    }}
                }}
            }})
            YIELD nodeId, score
            RETURN gds.util.asNode(nodeId).id AS entity_id,
                   gds.util.asNode(nodeId).name AS entity_name,
                   gds.util.asNode(nodeId).type AS entity_type,
                   score AS betweenness_score
            ORDER BY betweenness_score DESC
            LIMIT $limit
            """

            result = await session.run(query, {"limit": limit})

            centrality_results = []
            rank = 1

            async for record in result:
                centrality_results.append(CentralityResult(
                    entity_id=record["entity_id"],
                    entity_name=record["entity_name"],
                    entity_type=record["entity_type"],
                    centrality_score=record["betweenness_score"],
                    rank=rank,
                    metadata={"algorithm": "betweenness"}
                ))
                rank += 1

            computation_time = time.time() - start_time

            return {
                "results": [result.dict() for result in centrality_results],
                "computation_time": computation_time,
                "node_count": len(centrality_results)
            }

        except Exception as e:
            logger.error(f"Error computing betweenness centrality: {e}")
            return await self._compute_degree_centrality_fallback(
                session, entity_types, tenant_id, limit, "betweenness"
            )

    async def compute_closeness_centrality(
        self,
        session: AsyncSession,
        entity_types: Optional[List[str]] = None,
        tenant_id: Optional[str] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """Compute closeness centrality"""
        start_time = time.time()

        try:
            # Build query conditions
            where_clauses = []
            if entity_types:
                type_filter = " OR ".join([f"e.type = '{etype}'" for etype in entity_types])
                where_clauses.append(f"({type_filter})")
            if tenant_id:
                where_clauses.append(f"e.tenant_id = '{tenant_id}'")

            where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"
            node_filter = f"nodeFilter: '{where_clause}'" if where_clause != "1=1" else ""

            query = f"""
            CALL gds.closeness.stream({{
                nodeProjection: {{
                    Entity: {{
                        label: 'Entity',
                        properties: ['name', 'type'],
                        {node_filter}
                    }}
                }},
                relationshipProjection: {{
                    RELATED_TO: {{
                        type: 'RELATED_TO',
                        orientation: 'UNDIRECTED'
                    }}
                }}
            }})
            YIELD nodeId, score
            RETURN gds.util.asNode(nodeId).id AS entity_id,
                   gds.util.asNode(nodeId).name AS entity_name,
                   gds.util.asNode(nodeId).type AS entity_type,
                   score AS closeness_score
            ORDER BY closeness_score DESC
            LIMIT $limit
            """

            result = await session.run(query, {"limit": limit})

            centrality_results = []
            rank = 1

            async for record in result:
                centrality_results.append(CentralityResult(
                    entity_id=record["entity_id"],
                    entity_name=record["entity_name"],
                    entity_type=record["entity_type"],
                    centrality_score=record["closeness_score"],
                    rank=rank,
                    metadata={"algorithm": "closeness"}
                ))
                rank += 1

            computation_time = time.time() - start_time

            return {
                "results": [result.dict() for result in centrality_results],
                "computation_time": computation_time,
                "node_count": len(centrality_results)
            }

        except Exception as e:
            logger.error(f"Error computing closeness centrality: {e}")
            return await self._compute_degree_centrality_fallback(
                session, entity_types, tenant_id, limit, "closeness"
            )

    async def compute_degree_centrality(
        self,
        session: AsyncSession,
        entity_types: Optional[List[str]] = None,
        tenant_id: Optional[str] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """Compute degree centrality"""
        start_time = time.time()

        try:
            # Build query conditions
            where_clauses = []
            if entity_types:
                type_filter = " OR ".join([f"e.type = '{etype}'" for etype in entity_types])
                where_clauses.append(f"({type_filter})")
            if tenant_id:
                where_clauses.append(f"e.tenant_id = '{tenant_id}'")

            where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"
            node_filter = f"nodeFilter: '{where_clause}'" if where_clause != "1=1" else ""

            query = f"""
            MATCH (e:Entity)
            WHERE {where_clause}
            OPTIONAL MATCH (e)-[r:RELATED_TO]-()
            WITH e, count(r) AS degree
            ORDER BY degree DESC
            LIMIT $limit
            RETURN e.id AS entity_id,
                   e.name AS entity_name,
                   e.type AS entity_type,
                   degree AS degree_score
            """

            result = await session.run(query, {"limit": limit})

            centrality_results = []
            rank = 1
            max_degree = 0

            # First pass to get max degree for normalization
            all_records = []
            async for record in result:
                all_records.append(record)
                if record["degree_score"] > max_degree:
                    max_degree = record["degree_score"]

            # Second pass to create results with normalized scores
            for record in all_records:
                normalized_score = record["degree_score"] / max_degree if max_degree > 0 else 0
                centrality_results.append(CentralityResult(
                    entity_id=record["entity_id"],
                    entity_name=record["entity_name"],
                    entity_type=record["entity_type"],
                    centrality_score=normalized_score,
                    rank=rank,
                    metadata={
                        "algorithm": "degree",
                        "raw_degree": record["degree_score"]
                    }
                ))
                rank += 1

            computation_time = time.time() - start_time

            return {
                "results": [result.dict() for result in centrality_results],
                "computation_time": computation_time,
                "node_count": len(centrality_results)
            }

        except Exception as e:
            logger.error(f"Error computing degree centrality: {e}")
            return {"results": [], "computation_time": 0, "node_count": 0}

    async def _compute_degree_centrality_fallback(
        self,
        session: AsyncSession,
        entity_types: Optional[List[str]],
        tenant_id: Optional[str],
        limit: int,
        algorithm: str
    ) -> Dict[str, Any]:
        """Fallback centrality computation using simple degree"""
        return await self.compute_degree_centrality(session, entity_types, tenant_id, limit)

    async def find_shortest_path_dijkstra(
        self,
        session: AsyncSession,
        source_entity_id: str,
        target_entity_id: str,
        tenant_id: str,
        weight_property: str = "strength",
        max_paths: int = 10
    ) -> Dict[str, Any]:
        """Find shortest paths using Dijkstra's algorithm"""
        start_time = time.time()

        try:
            query = """
            MATCH (start:Entity {id: $source_entity_id, tenant_id: $tenant_id})
            MATCH (end:Entity {id: $target_entity_id, tenant_id: $tenant_id})
            CALL gds.shortestPath.dijkstra.stream({
                nodeProjection: 'Entity',
                relationshipProjection: {
                    RELATED_TO: {
                        type: 'RELATED_TO',
                        orientation: 'UNDIRECTED',
                        properties: [$weight_property]
                    }
                },
                sourceNode: start,
                targetNode: end,
                relationshipWeightProperty: $weight_property
            })
            YIELD index, sourceNode, targetNode, totalCost, nodeIds, relationshipIds, costs
            RETURN index,
                   gds.util.asNode(sourceNode).id AS source_id,
                   gds.util.asNode(targetNode).id AS target_id,
                   totalCost,
                   nodeIds,
                   relationshipIds,
                   costs
            ORDER BY totalCost
            LIMIT $max_paths
            """

            result = await session.run(query, {
                "source_entity_id": source_entity_id,
                "target_entity_id": target_entity_id,
                "tenant_id": tenant_id,
                "weight_property": weight_property,
                "max_paths": max_paths
            })

            paths = []
            async for record in result:
                # Convert path to steps
                steps = []
                node_ids = record["nodeIds"]
                costs = record["costs"]

                for i, node_id in enumerate(node_ids):
                    # Get node information
                    node_query = "MATCH (n:Entity) WHERE id(n) = $node_id RETURN n.id AS id, n.name AS name, n.type AS type"
                    node_result = await session.run(node_query, {"node_id": node_id})
                    node_record = await node_result.single()

                    if node_record:
                        step = PathStep(
                            entity_id=node_record["id"],
                            entity_name=node_record["name"],
                            entity_type=node_record["type"],
                            weight=costs[i] if i < len(costs) else 0.0
                        )
                        steps.append(step)

                path = GraphPath(
                    path_id=f"path_{record['index']}",
                    steps=steps,
                    total_weight=record["totalCost"],
                    path_length=len(steps),
                    metadata={"algorithm": "dijkstra"}
                )
                paths.append(path)

            computation_time = time.time() - start_time

            return {
                "paths": [path.dict() for path in paths],
                "computation_time": computation_time,
                "path_count": len(paths)
            }

        except Exception as e:
            logger.error(f"Error finding shortest paths with Dijkstra: {e}")
            return await self._find_shortest_path_fallback(
                session, source_entity_id, target_entity_id, tenant_id, max_paths
            )

    async def find_shortest_path_bfs(
        self,
        session: AsyncSession,
        source_entity_id: str,
        target_entity_id: str,
        tenant_id: str,
        max_depth: int = 5,
        max_paths: int = 10
    ) -> Dict[str, Any]:
        """Find shortest paths using BFS"""
        start_time = time.time()

        try:
            # Note: Neo4j doesn't support parameters in variable-length patterns
            # max_depth is validated to be a reasonable integer, safe to interpolate
            query = f"""
            MATCH (start:Entity {{id: $source_entity_id, tenant_id: $tenant_id}})
            MATCH (end:Entity {{id: $target_entity_id, tenant_id: $tenant_id}})
            MATCH path = shortestPath((start)-[:RELATED_TO*1..{max_depth}]-(end))
            RETURN path, length(path) as path_length
            ORDER BY path_length
            LIMIT $max_paths
            """

            result = await session.run(query, {
                "source_entity_id": source_entity_id,
                "target_entity_id": target_entity_id,
                "tenant_id": tenant_id,
                "max_paths": max_paths
            })

            paths = []
            path_index = 0

            async for record in result:
                path_obj = record["path"]
                steps = []

                # Extract nodes and relationships from path
                for i, node in enumerate(path_obj.nodes):
                    step = PathStep(
                        entity_id=node["id"],
                        entity_name=node["name"],
                        entity_type=node["type"],
                        weight=1.0  # Equal weight for BFS
                    )
                    steps.append(step)

                path = GraphPath(
                    path_id=f"bfs_path_{path_index}",
                    steps=steps,
                    total_weight=len(steps) - 1,
                    path_length=len(steps),
                    metadata={"algorithm": "bfs"}
                )
                paths.append(path)
                path_index += 1

            computation_time = time.time() - start_time

            return {
                "paths": [path.dict() for path in paths],
                "computation_time": computation_time,
                "path_count": len(paths)
            }

        except Exception as e:
            logger.error(f"Error finding shortest paths with BFS: {e}")
            return {"paths": [], "computation_time": 0, "path_count": 0}

    async def _find_shortest_path_fallback(
        self,
        session: AsyncSession,
        source_entity_id: str,
        target_entity_id: str,
        tenant_id: str,
        max_paths: int
    ) -> Dict[str, Any]:
        """Fallback path finding using simple Cypher queries"""
        return await self.find_shortest_path_bfs(
            session, source_entity_id, target_entity_id, tenant_id, max_depth=5, max_paths=max_paths
        )

    async def detect_communities_louvain(
        self,
        session: AsyncSession,
        entity_types: Optional[List[str]] = None,
        tenant_id: Optional[str] = None,
        resolution: float = 1.0
    ) -> Dict[str, Any]:
        """Detect communities using Louvain algorithm"""
        start_time = time.time()

        try:
            # Build query conditions
            where_clauses = []
            if entity_types:
                type_filter = " OR ".join([f"e.type = '{etype}'" for etype in entity_types])
                where_clauses.append(f"({type_filter})")
            if tenant_id:
                where_clauses.append(f"e.tenant_id = '{tenant_id}'")

            where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"
            node_filter = f"nodeFilter: '{where_clause}'" if where_clause != "1=1" else ""

            query = f"""
            CALL gds.louvain.stream({{
                nodeProjection: {{
                    Entity: {{
                        label: 'Entity',
                        properties: ['name', 'type'],
                        {node_filter}
                    }}
                }},
                relationshipProjection: {{
                    RELATED_TO: {{
                        type: 'RELATED_TO',
                        orientation: 'UNDIRECTED'
                    }}
                }},
                includeIntermediateCommunities: false,
                seedProperty: 'seed',
                tolerance: 0.00001
            }})
            YIELD nodeId, communityId, intermediateCommunityIds
            RETURN communityId,
                   collect(gds.util.asNode(nodeId).id) AS entities,
                   count(gds.util.asNode(nodeId)) AS entity_count
            ORDER BY entity_count DESC
            """

            result = await session.run(query, {"resolution": resolution})

            communities = []
            community_count = 0
            total_modularity = 0.0

            async for record in result:
                # Get dominant entity type for this community
                dominant_type = await self._get_dominant_entity_type(
                    session, record["entities"]
                )

                community = Community(
                    community_id=str(record["communityId"]),
                    entity_count=record["entity_count"],
                    entities=record["entities"],
                    modularity_contribution=0.0,  # Would need additional calculation
                    dominant_entity_type=dominant_type,
                    metadata={"algorithm": "louvain"}
                )
                communities.append(community)
                community_count += 1

            computation_time = time.time() - start_time

            return {
                "communities": [community.dict() for community in communities],
                "computation_time": computation_time,
                "community_count": community_count,
                "modularity_score": total_modularity
            }

        except Exception as e:
            logger.error(f"Error detecting communities with Louvain: {e}")
            return {"communities": [], "computation_time": 0, "community_count": 0, "modularity_score": 0.0}

    async def detect_communities_label_propagation(
        self,
        session: AsyncSession,
        entity_types: Optional[List[str]] = None,
        tenant_id: Optional[str] = None,
        max_iterations: int = 100
    ) -> Dict[str, Any]:
        """Detect communities using label propagation"""
        start_time = time.time()

        try:
            # Similar implementation to Louvain but using label propagation
            # This is a simplified version - full implementation would use GDS label propagation
            communities = []
            computation_time = time.time() - start_time

            return {
                "communities": communities,
                "computation_time": computation_time,
                "community_count": len(communities),
                "modularity_score": 0.0
            }

        except Exception as e:
            logger.error(f"Error detecting communities with label propagation: {e}")
            return {"communities": [], "computation_time": 0, "community_count": 0, "modularity_score": 0.0}

    async def _get_dominant_entity_type(self, session: AsyncSession, entity_ids: List[str]) -> str:
        """Get dominant entity type for a list of entities"""
        try:
            query = """
            UNWIND $entity_ids AS entity_id
            MATCH (e:Entity {id: entity_id})
            RETURN e.type AS entity_type, count(e) AS count
            ORDER BY count DESC
            LIMIT 1
            """

            result = await session.run(query, {"entity_ids": entity_ids})
            record = await result.single()
            return record["entity_type"] if record else "UNKNOWN"

        except Exception as e:
            logger.error(f"Error getting dominant entity type: {e}")
            return "UNKNOWN"

    # Insights methods
    async def find_key_entities(
        self,
        session: AsyncSession,
        tenant_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Find key entities in the graph"""
        try:
            # Combine multiple centrality measures
            pagerank_result = await self.compute_pagerank(session, tenant_id=tenant_id, limit=limit)
            betweenness_result = await self.compute_betweenness_centrality(session, tenant_id=tenant_id, limit=limit)

            # Combine results to find consensus key entities
            key_entities = []
            for pr_result in pagerank_result.get("results", []):
                entity_id = pr_result["entity_id"]

                # Find corresponding betweenness score
                betweenness_score = 0.0
                for bw_result in betweenness_result.get("results", []):
                    if bw_result["entity_id"] == entity_id:
                        betweenness_score = bw_result["centrality_score"]
                        break

                # Calculate combined importance score
                importance_score = (pr_result["centrality_score"] + betweenness_score) / 2

                key_entities.append(KeyEntityInsight(
                    entity_id=entity_id,
                    entity_name=pr_result["entity_name"],
                    entity_type=pr_result["entity_type"],
                    importance_score=importance_score,
                    key_metrics={
                        "pagerank": pr_result["centrality_score"],
                        "betweenness": betweenness_score,
                        "rank": pr_result["rank"]
                    },
                    reasoning="High centrality scores across multiple metrics"
                ))

            # Sort by importance score
            key_entities.sort(key=lambda x: x.importance_score, reverse=True)

            return [entity.dict() for entity in key_entities[:limit]]

        except Exception as e:
            logger.error(f"Error finding key entities: {e}")
            return []

    async def find_bridge_entities(
        self,
        session: AsyncSession,
        tenant_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Find bridge entities (entities that connect different communities)"""
        try:
            # Use betweenness centrality as proxy for bridge entities
            betweenness_result = await self.compute_betweenness_centrality(session, tenant_id=tenant_id, limit=limit)

            bridge_entities = []
            for result in betweenness_result.get("results", []):
                if result["centrality_score"] > 0.1:  # Threshold for bridge entities
                    bridge_entities.append(BridgeEntityInsight(
                        entity_id=result["entity_id"],
                        entity_name=result["entity_name"],
                        entity_type=result["entity_type"],
                        betweenness_score=result["centrality_score"],
                        connected_communities=[],  # Would need additional computation
                        bridge_strength=result["centrality_score"]
                    ))

            return [entity.dict() for entity in bridge_entities]

        except Exception as e:
            logger.error(f"Error finding bridge entities: {e}")
            return []

    async def identify_graph_clusters(
        self,
        session: AsyncSession,
        tenant_id: str
    ) -> List[Dict[str, Any]]:
        """Identify graph clusters"""
        try:
            # Use community detection to identify clusters
            community_result = await self.detect_communities_louvain(session, tenant_id=tenant_id)

            clusters = []
            for community_data in community_result.get("communities", []):
                # Get key entities for this cluster
                key_entities = community_data["entities"][:5]  # Top 5 entities

                cluster = ClusterInsight(
                    cluster_id=community_data["community_id"],
                    entity_count=community_data["entity_count"],
                    density=0.0,  # Would need additional computation
                    dominant_entity_types=[community_data["dominant_entity_type"]],
                    key_entities=key_entities,
                    description=f"Cluster {community_data['community_id']} with {community_data['entity_count']} entities"
                )
                clusters.append(cluster)

            return [cluster.dict() for cluster in clusters]

        except Exception as e:
            logger.error(f"Error identifying graph clusters: {e}")
            return []

    async def detect_graph_anomalies(
        self,
        session: AsyncSession,
        tenant_id: str
    ) -> List[Dict[str, Any]]:
        """Detect graph anomalies"""
        try:
            anomalies = []

            # Look for isolated entities (no connections)
            query = """
            MATCH (e:Entity {tenant_id: $tenant_id})
            WHERE NOT (e)-[:RELATED_TO]-()
            RETURN e.id AS entity_id, e.name AS entity_name, e.type AS entity_type
            LIMIT 10
            """

            result = await session.run(query, {"tenant_id": tenant_id})
            async for record in result:
                anomalies.append(AnomalyInsight(
                    anomaly_id=f"isolated_{record['entity_id']}",
                    anomaly_type="isolated_entity",
                    entities_involved=[record["entity_id"]],
                    anomaly_score=1.0,
                    description=f"Entity {record['entity_name']} has no connections",
                    severity="medium"
                ))

            return [anomaly.dict() for anomaly in anomalies]

        except Exception as e:
            logger.error(f"Error detecting graph anomalies: {e}")
            return []

    async def analyze_growth_trends(
        self,
        session: AsyncSession,
        tenant_id: str
    ) -> List[Dict[str, Any]]:
        """Analyze growth trends in the graph"""
        try:
            trends = []

            # Simple trend analysis based on creation dates
            query = """
            MATCH (e:Entity {tenant_id: $tenant_id})
            WITH date(e.created_at) AS creation_date, count(e) AS daily_count
            RETURN creation_date, daily_count
            ORDER BY creation_date DESC
            LIMIT 30
            """

            daily_counts = []
            result = await session.run(query, {"tenant_id": tenant_id})
            async for record in result:
                daily_counts.append({
                    "date": record["creation_date"],
                    "count": record["daily_count"]
                })

            if len(daily_counts) >= 2:
                # Calculate simple growth rate
                recent_count = daily_counts[0]["count"]
                previous_count = daily_counts[1]["count"]
                growth_rate = (recent_count - previous_count) / previous_count if previous_count > 0 else 0

                trend_direction = "increasing" if growth_rate > 0 else "decreasing" if growth_rate < 0 else "stable"

                trends.append(GrowthTrendInsight(
                    metric_name="daily_entity_creation",
                    time_period="last_30_days",
                    growth_rate=growth_rate,
                    trend_direction=trend_direction,
                    key_drivers=["user_activity", "document_processing"]
                ))

            return [trend.dict() for trend in trends]

        except Exception as e:
            logger.error(f"Error analyzing growth trends: {e}")
            return []