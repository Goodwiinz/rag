"""
Graph Analytics Service with Neo4j algorithms
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Union, Tuple
from contextlib import asynccontextmanager

from neo4j import AsyncGraphDatabase, AsyncDriver, AsyncSession
from neo4j.exceptions import ServiceUnavailable, TransientError
from sqlalchemy.ext.asyncio import AsyncSession as SQLAsyncSession
from sqlalchemy import select, update, delete, and_, or_, func
from sqlalchemy.orm import selectinload

from ...core.config import settings
from ...core.database import get_async_session
from ...models.analytics.graph_analytics import (
    GraphAnalyticsResult, NodeMetrics, EdgeMetrics, CommunityMetrics, PathAnalytics,
    GraphAlgorithmType, NodeType, EdgeType,
    GraphAnalysisRequest, GraphAnalysisResponse, PathAnalysisRequest, PathAnalysisResponse,
    GraphStatistics, CentralityRanking, CentralityAnalysis
)
from ...models.base import GUID

logger = logging.getLogger(__name__)


class GraphAnalyticsService:
    """Graph analytics service using Neo4j algorithms"""

    def __init__(self):
        self.driver: Optional[AsyncDriver] = None
        self.connection_pool_size = 50
        self.max_connection_lifetime = 3600
        self.max_connection_acquisition_time = 60
        self.initialized = False

    async def initialize(self):
        """Initialize Neo4j connection"""
        try:
            self.driver = AsyncGraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
                max_connection_lifetime=self.max_connection_lifetime,
                max_connection_pool_size=self.connection_pool_size,
                connection_acquisition_timeout=self.max_connection_acquisition_time,
                max_transaction_retry_time=30
            )

            # Test connection
            await self._verify_connectivity()
            self.initialized = True
            logger.info("Graph analytics service initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize graph analytics service: {e}")
            raise

    async def shutdown(self):
        """Shutdown Neo4j connection"""
        if self.driver:
            await self.driver.close()
            self.initialized = False
            logger.info("Graph analytics service shut down")

    @asynccontextmanager
    async def get_session(self, database: str = "neo4j") -> AsyncSession:
        """Get Neo4j session"""
        if not self.initialized:
            raise RuntimeError("Graph analytics service not initialized")

        session = self.driver.session(database=database)
        try:
            yield session
        finally:
            await session.close()

    async def _verify_connectivity(self):
        """Verify Neo4j connectivity"""
        try:
            async with self.get_session() as session:
                result = await session.run("RETURN 1 as test")
                record = await result.single()
                if record["test"] != 1:
                    raise Exception("Neo4j connectivity test failed")
        except Exception as e:
            logger.error(f"Neo4j connectivity verification failed: {e}")
            raise

    async def run_graph_analysis(self, request: GraphAnalysisRequest, user_id: uuid.UUID) -> GraphAnalysisResponse:
        """Run graph analysis with specified algorithm"""
        if not self.initialized:
            raise RuntimeError("Graph analytics service not initialized")

        start_time = time.time()
        analysis_result = None

        try:
            # Create analysis record
            async with get_async_session() as db:
                db_result = GraphAnalyticsResult(
                    analysis_type=request.algorithm,
                    analysis_name=request.name,
                    description=request.description,
                    query_config={
                        "algorithm": request.algorithm,
                        "node_filters": request.node_filters,
                        "edge_filters": request.edge_filters,
                        "parameters": request.parameters
                    },
                    status="running"
                )
                db.add(db_result)
                await db.commit()
                await db.refresh(db_result)

            # Run the specific algorithm
            if request.algorithm == GraphAlgorithmType.PAGERANK:
                analysis_result = await self._run_pagerank(db_result.id, request)
            elif request.algorithm == GraphAlgorithmType.BETWEENNESS_CENTRALITY:
                analysis_result = await self._run_betweenness_centrality(db_result.id, request)
            elif request.algorithm == GraphAlgorithmType.COMMUNITY_DETECTION:
                analysis_result = await self._run_community_detection(db_result.id, request)
            elif request.algorithm == GraphAlgorithmType.CONNECTED_COMPONENTS:
                analysis_result = await self._run_connected_components(db_result.id, request)
            elif request.algorithm == GraphAlgorithmType.SHORTEST_PATH:
                analysis_result = await self._run_shortest_path_analysis(db_result.id, request)
            elif request.algorithm == GraphAlgorithmType.TRIANGLE_COUNT:
                analysis_result = await self._run_triangle_count(db_result.id, request)
            elif request.algorithm == GraphAlgorithmType.CLUSTERING_COEFFICIENT:
                analysis_result = await self._run_clustering_coefficient(db_result.id, request)
            else:
                raise ValueError(f"Unsupported algorithm: {request.algorithm}")

            execution_time = int((time.time() - start_time) * 1000)

            # Update analysis record
            async with get_async_session() as db:
                await db.execute(
                    update(GraphAnalyticsResult)
                    .where(GraphAnalyticsResult.id == db_result.id)
                    .values(
                        status="completed",
                        execution_time_ms=execution_time,
                        node_count=analysis_result.get("node_count", 0),
                        edge_count=analysis_result.get("edge_count", 0),
                        component_count=analysis_result.get("component_count"),
                        density=analysis_result.get("density"),
                        results=analysis_result.get("results", {})
                    )
                )
                await db.commit()

            # Get complete analysis with metrics
            response = await self._get_analysis_response(db_result.id)
            return response

        except Exception as e:
            execution_time = int((time.time() - start_time) * 1000)
            logger.error(f"Graph analysis failed: {e}")

            # Update analysis record with error
            if db_result:
                async with get_async_session() as db:
                    await db.execute(
                        update(GraphAnalyticsResult)
                        .where(GraphAnalyticsResult.id == db_result.id)
                        .values(
                            status="failed",
                            execution_time_ms=execution_time,
                            error_message=str(e)
                        )
                    )
                    await db.commit()

            raise

    async def _run_pagerank(self, analysis_id: uuid.UUID, request: GraphAnalysisRequest) -> Dict[str, Any]:
        """Run PageRank algorithm"""
        damping_factor = request.parameters.get("damping_factor", 0.85) if request.parameters else 0.85
        max_iterations = request.parameters.get("max_iterations", 20) if request.parameters else 20

        # Build Cypher query with filters
        node_filter = self._build_node_filter(request.node_filters)
        edge_filter = self._build_edge_filter(request.edge_filters)

        query = f"""
        CALL apoc.algo.pageRank([{{
            node_filter: '{node_filter}',
            edge_filter: '{edge_filter}'
        }}]) YIELD node, score
        RETURN count(DISTINCT node) as node_count,
               sum(size((node)-[]->())) as edge_count,
               collect({{node_id: toString(id(node)), score: score}}) as rankings
        """

        async with self.get_session() as session:
            result = await session.run(query, {
                "damping_factor": damping_factor,
                "max_iterations": max_iterations
            })
            record = await result.single()

            node_count = record["node_count"]
            edge_count = record["edge_count"]
            rankings = record["rankings"]

            # Store node metrics
            await self._store_node_metrics(analysis_id, rankings, "pagerank_score")

            # Calculate graph density
            density = (2 * edge_count) / (node_count * (node_count - 1)) if node_count > 1 else 0

            return {
                "node_count": node_count,
                "edge_count": edge_count,
                "density": density,
                "results": {
                    "rankings": rankings[:request.max_results] if request.max_results else rankings
                }
            }

    async def _run_betweenness_centrality(self, analysis_id: uuid.UUID, request: GraphAnalysisRequest) -> Dict[str, Any]:
        """Run betweenness centrality algorithm"""
        # Build Cypher query
        node_filter = self._build_node_filter(request.node_filters)
        edge_filter = self._build_edge_filter(request.edge_filters)

        query = f"""
        MATCH (n) {node_filter}
        WITH collect(n) as nodes
        CALL apoc.algo.betweenness(nodes) YIELD node, score
        RETURN count(DISTINCT node) as node_count,
               collect({{node_id: toString(id(node)), score: score}}) as rankings
        """

        async with self.get_session() as session:
            result = await session.run(query)
            record = await result.single()

            node_count = record["node_count"]
            rankings = record["rankings"]

            # Store node metrics
            await self._store_node_metrics(analysis_id, rankings, "betweenness_centrality")

            return {
                "node_count": node_count,
                "edge_count": 0,  # Not calculated in this implementation
                "results": {
                    "rankings": rankings[:request.max_results] if request.max_results else rankings
                }
            }

    async def _run_community_detection(self, analysis_id: uuid.UUID, request: GraphAnalysisRequest) -> Dict[str, Any]:
        """Run community detection algorithm (Louvain)"""
        resolution = request.parameters.get("resolution", 1.0) if request.parameters else 1.0

        node_filter = self._build_node_filter(request.node_filters)
        edge_filter = self._build_edge_filter(request.edge_filters)

        query = f"""
        MATCH (n) {node_filter}
        OPTIONAL MATCH (n)-[r] {edge_filter}-(m)
        WITH n, collect(r) as relationships
        CALL apoc.algo.community(n, relationships, 'louvain', {{resolution: $resolution}})
        YIELD community, node
        RETURN count(DISTINCT node) as node_count,
               count(DISTINCT community) as community_count,
               collect({{node_id: toString(id(node)), community_id: toString(community)}}) as assignments
        """

        async with self.get_session() as session:
            result = await session.run(query, {"resolution": resolution})
            record = await result.single()

            node_count = record["node_count"]
            community_count = record["community_count"]
            assignments = record["assignments"]

            # Store community metrics
            await self._store_community_metrics(analysis_id, assignments)

            return {
                "node_count": node_count,
                "edge_count": 0,
                "component_count": community_count,
                "results": {
                    "community_count": community_count,
                    "assignments": assignments
                }
            }

    async def _run_connected_components(self, analysis_id: uuid.UUID, request: GraphAnalysisRequest) -> Dict[str, Any]:
        """Run connected components algorithm"""
        node_filter = self._build_node_filter(request.node_filters)
        edge_filter = self._build_edge_filter(request.edge_filters)

        query = f"""
        MATCH (n) {node_filter}
        CALL apoc.algo.connectedComponents(n, {edge_filter}) YIELD component
        RETURN count(DISTINCT n) as node_count,
               count(DISTINCT component) as component_count,
               collect({{node_id: toString(id(n)), component_id: toString(component)}}) as assignments
        """

        async with self.get_session() as session:
            result = await session.run(query)
            record = await result.single()

            node_count = record["node_count"]
            component_count = record["component_count"]
            assignments = record["assignments"]

            return {
                "node_count": node_count,
                "edge_count": 0,
                "component_count": component_count,
                "results": {
                    "component_count": component_count,
                    "assignments": assignments
                }
            }

    async def _run_shortest_path_analysis(self, analysis_id: uuid.UUID, request: GraphAnalysisRequest) -> Dict[str, Any]:
        """Run shortest path analysis"""
        source_id = request.parameters.get("source_node_id") if request.parameters else None
        target_id = request.parameters.get("target_node_id") if request.parameters else None

        if not source_id or not target_id:
            raise ValueError("source_node_id and target_id are required for shortest path analysis")

        query = """
        MATCH (start), (end)
        WHERE id(start) = $source_id AND id(end) = $target_id
        CALL apoc.algo.shortestPath(start, end, 'BOTH') YIELD path, weight
        RETURN length(path) as path_length,
               [node in nodes(path) | toString(id(node))] as path_nodes,
               [rel in relationships(path) | toString(id(rel))] as path_edges,
               weight as total_weight
        """

        async with self.get_session() as session:
            result = await session.run(query, {
                "source_id": int(source_id),
                "target_id": int(target_id)
            })
            record = await result.single()

            if record:
                return {
                    "node_count": len(record["path_nodes"]),
                    "edge_count": len(record["path_edges"]),
                    "results": {
                        "path_length": record["path_length"],
                        "path_nodes": record["path_nodes"],
                        "path_edges": record["path_edges"],
                        "total_weight": record["total_weight"]
                    }
                }
            else:
                return {
                    "node_count": 0,
                    "edge_count": 0,
                    "results": {"error": "No path found"}
                }

    async def _run_triangle_count(self, analysis_id: uuid.UUID, request: GraphAnalysisRequest) -> Dict[str, Any]:
        """Run triangle counting algorithm"""
        node_filter = self._build_node_filter(request.node_filters)
        edge_filter = self._build_edge_filter(request.edge_filters)

        query = f"""
        MATCH (a) {node_filter}
        MATCH (a)-[r1] {edge_filter}-(b)
        MATCH (b)-[r2] {edge_filter}-(c)
        MATCH (c)-[r3] {edge_filter}-(a)
        WHERE id(a) < id(b) AND id(b) < id(c)
        RETURN count(DISTINCT a) as node_count,
               count(*) as triangle_count,
               collect({{nodes: [toString(id(a)), toString(id(b)), toString(id(c))]}}) as triangles
        """

        async with self.get_session() as session:
            result = await session.run(query)
            record = await result.single()

            node_count = record["node_count"]
            triangle_count = record["triangle_count"]
            triangles = record["triangles"]

            return {
                "node_count": node_count,
                "edge_count": triangle_count * 3,  # Approximate
                "results": {
                    "triangle_count": triangle_count,
                    "triangles": triangles[:request.max_results] if request.max_results else triangles
                }
            }

    async def _run_clustering_coefficient(self, analysis_id: uuid.UUID, request: GraphAnalysisRequest) -> Dict[str, Any]:
        """Run clustering coefficient calculation"""
        node_filter = self._build_node_filter(request.node_filters)
        edge_filter = self._build_edge_filter(request.edge_filters)

        query = f"""
        MATCH (n) {node_filter}
        OPTIONAL MATCH (n)-[r1] {edge_filter}-(a)
        OPTIONAL MATCH (a)-[r2] {edge_filter}-(b)
        OPTIONAL MATCH (b)-[r3] {edge_filter}-(n)
        WHERE id(a) > id(n) AND id(b) > id(a)
        WITH n, count(DISTINCT a) as neighbors, count(DISTINCT b) as triangles
        WITH n, neighbors, triangles,
             CASE WHEN neighbors > 1
                  THEN (2.0 * triangles) / (neighbors * (neighbors - 1))
                  ELSE 0.0
             END as clustering_coefficient
        RETURN count(DISTINCT n) as node_count,
               avg(clustering_coefficient) as avg_clustering,
               collect({{node_id: toString(id(n)), coefficient: clustering_coefficient}}) as coefficients
        """

        async with self.get_session() as session:
            result = await session.run(query)
            record = await result.single()

            node_count = record["node_count"]
            avg_clustering = record["avg_clustering"]
            coefficients = record["coefficients"]

            # Store node metrics
            node_metrics = [
                {"node_id": coeff["node_id"], "score": coeff["coefficient"]}
                for coeff in coefficients
            ]
            await self._store_node_metrics(analysis_id, node_metrics, "clustering_coefficient")

            return {
                "node_count": node_count,
                "edge_count": 0,
                "results": {
                    "average_clustering_coefficient": avg_clustering,
                    "coefficients": coefficients[:request.max_results] if request.max_results else coefficients
                }
            }

    async def run_path_analysis(self, request: PathAnalysisRequest, user_id: uuid.UUID) -> PathAnalysisResponse:
        """Run path analysis between nodes"""
        if not self.initialized:
            raise RuntimeError("Graph analytics service not initialized")

        start_time = time.time()

        try:
            # Create path analysis record
            async with get_async_session() as db:
                db_result = PathAnalytics(
                    analysis_type=request.analysis_type,
                    source_node_id=request.source_node_id,
                    target_node_id=request.target_node_id,
                    max_depth=request.max_depth,
                    path_count_limit=request.path_count_limit,
                    weight_property=request.weight_property,
                    status="running"
                )
                db.add(db_result)
                await db.commit()
                await db.refresh(db_result)

            # Run path analysis based on type
            if request.analysis_type == "shortest":
                paths = await self._find_shortest_paths(request)
            elif request.analysis_type == "all":
                paths = await self._find_all_paths(request)
            elif request.analysis_type == "k_shortest":
                paths = await self._find_k_shortest_paths(request)
            else:
                raise ValueError(f"Unsupported path analysis type: {request.analysis_type}")

            execution_time = int((time.time() - start_time) * 1000)

            # Calculate metrics
            total_paths = len(paths)
            path_lengths = [len(path["nodes"]) - 1 for path in paths if path["nodes"]]
            avg_path_length = sum(path_lengths) / len(path_lengths) if path_lengths else 0
            shortest_length = min(path_lengths) if path_lengths else None
            longest_length = max(path_lengths) if path_lengths else None

            # Update record
            async with get_async_session() as db:
                await db.execute(
                    update(PathAnalytics)
                    .where(PathAnalytics.id == db_result.id)
                    .values(
                        status="completed",
                        execution_time_ms=execution_time,
                        total_paths_found=total_paths,
                        average_path_length=avg_path_length,
                        shortest_path_length=shortest_length,
                        longest_path_length=longest_length,
                        paths=paths
                    )
                )
                await db.commit()

            return PathAnalysisResponse(
                id=db_result.id,
                analysis_type=request.analysis_type,
                source_node_id=request.source_node_id,
                target_node_id=request.target_node_id,
                total_paths_found=total_paths,
                average_path_length=avg_path_length,
                shortest_path_length=shortest_length,
                longest_path_length=longest_length,
                paths=[
                    {
                        "path_id": str(i),
                        "nodes": path["nodes"],
                        "edges": path["edges"],
                        "length": len(path["nodes"]) - 1,
                        "weight": path.get("weight")
                    }
                    for i, path in enumerate(paths)
                ],
                execution_time_ms=execution_time,
                status="completed",
                created_at=db_result.created_at
            )

        except Exception as e:
            execution_time = int((time.time() - start_time) * 1000)
            logger.error(f"Path analysis failed: {e}")

            # Update record with error
            if db_result:
                async with get_async_session() as db:
                    await db.execute(
                        update(PathAnalytics)
                        .where(PathAnalytics.id == db_result.id)
                        .values(
                            status="failed",
                            execution_time_ms=execution_time,
                            error_message=str(e)
                        )
                    )
                    await db.commit()

            raise

    async def _find_shortest_paths(self, request: PathAnalysisRequest) -> List[Dict[str, Any]]:
        """Find shortest paths between nodes"""
        weight_clause = f"weight: r.{request.weight_property}" if request.weight_property else "weight: 1"

        query = f"""
        MATCH (start), (end)
        WHERE id(start) = $source_id AND id(end) = $target_id
        CALL apoc.algo.shortestPath(start, end, 'BOTH', $weight_property) YIELD path, weight
        RETURN [node in nodes(path) | toString(id(node))] as nodes,
               [rel in relationships(path) | toString(id(rel))] as edges,
               weight as weight
        LIMIT $limit
        """

        async with self.get_session() as session:
            result = await session.run(query, {
                "source_id": int(request.source_node_id),
                "target_id": int(request.target_node_id),
                "weight_property": request.weight_property,
                "limit": request.path_count_limit or 10
            })

            paths = []
            async for record in result:
                paths.append({
                    "nodes": record["nodes"],
                    "edges": record["edges"],
                    "weight": record["weight"]
                })

            return paths

    async def _find_all_paths(self, request: PathAnalysisRequest) -> List[Dict[str, Any]]:
        """Find all paths between nodes"""
        max_depth = request.max_depth or 5

        query = """
        MATCH (start), (end)
        WHERE id(start) = $source_id AND id(end) = $target_id
        MATCH path = (start)-[*1..$max_depth]-(end)
        RETURN [node in nodes(path) | toString(id(node))] as nodes,
               [rel in relationships(path) | toString(id(rel))] as edges
        LIMIT $limit
        """

        async with self.get_session() as session:
            result = await session.run(query, {
                "source_id": int(request.source_node_id),
                "target_id": int(request.target_node_id),
                "max_depth": max_depth,
                "limit": request.path_count_limit or 100
            })

            paths = []
            async for record in result:
                paths.append({
                    "nodes": record["nodes"],
                    "edges": record["edges"]
                })

            return paths

    async def _find_k_shortest_paths(self, request: PathAnalysisRequest) -> List[Dict[str, Any]]:
        """Find k shortest paths between nodes"""
        k = request.path_count_limit or 5

        query = """
        MATCH (start), (end)
        WHERE id(start) = $source_id AND id(end) = $target_id
        CALL apoc.algo.kShortestPaths(start, end, $k, 'BOTH', $weight_property) YIELD path, weight
        RETURN [node in nodes(path) | toString(id(node))] as nodes,
               [rel in relationships(path) | toString(id(rel))] as edges,
               weight as weight
        """

        async with self.get_session() as session:
            result = await session.run(query, {
                "source_id": int(request.source_node_id),
                "target_id": int(request.target_node_id),
                "k": k,
                "weight_property": request.weight_property
            })

            paths = []
            async for record in result:
                paths.append({
                    "nodes": record["nodes"],
                    "edges": record["edges"],
                    "weight": record["weight"]
                })

            return paths

    async def get_graph_statistics(self) -> GraphStatistics:
        """Get overall graph statistics"""
        if not self.initialized:
            raise RuntimeError("Graph analytics service not initialized")

        try:
            async with self.get_session() as session:
                # Get node and edge counts
                node_count_query = "MATCH (n) RETURN count(n) as total_nodes"
                edge_count_query = "MATCH ()-[r]->() RETURN count(r) as total_edges"

                node_result = await session.run(node_count_query)
                node_record = await node_result.single()
                total_nodes = node_record["total_nodes"]

                edge_result = await session.run(edge_count_query)
                edge_record = await edge_result.single()
                total_edges = edge_record["total_edges"]

                # Get node types distribution
                node_types_query = """
                MATCH (n)
                RETURN labels(n)[0] as node_type, count(n) as count
                """
                node_types_result = await session.run(node_types_query)
                node_types = {}
                async for record in node_types_result:
                    node_type = record["node_type"] or "Unknown"
                    node_types[node_type] = record["count"]

                # Get edge types distribution
                edge_types_query = """
                MATCH ()-[r]->()
                RETURN type(r) as edge_type, count(r) as count
                """
                edge_types_result = await session.run(edge_types_query)
                edge_types = {}
                async for record in edge_types_result:
                    edge_type = record["edge_type"] or "Unknown"
                    edge_types[edge_type] = record["count"]

                # Calculate density
                density = (2 * total_edges) / (total_nodes * (total_nodes - 1)) if total_nodes > 1 else 0

                # Get connected components (simplified)
                components_query = """
                CALL apoc.algo.connectedComponents() Yield component
                RETURN count(DISTINCT component) as connected_components
                """
                components_result = await session.run(components_query)
                components_record = await components_result.single()
                connected_components = components_record["connected_components"] if components_record else 0

                # Calculate average degree
                avg_degree = (2 * total_edges) / total_nodes if total_nodes > 0 else 0

                return GraphStatistics(
                    total_nodes=total_nodes,
                    total_edges=total_edges,
                    node_types=node_types,
                    edge_types=edge_types,
                    density=density,
                    connected_components=connected_components,
                    largest_component_size=None,  # Would require additional query
                    average_degree=avg_degree,
                    last_updated=datetime.utcnow()
                )

        except Exception as e:
            logger.error(f"Error getting graph statistics: {e}")
            raise

    async def get_centrality_analysis(self, algorithm: str, top_k: int = 100) -> CentralityAnalysis:
        """Get centrality analysis for the graph"""
        if not self.initialized:
            raise RuntimeError("Graph analytics service not initialized")

        try:
            if algorithm == "pagerank":
                rankings = await self._get_pagerank_rankings(top_k)
            elif algorithm == "betweenness":
                rankings = await self._get_betweenness_rankings(top_k)
            elif algorithm == "degree":
                rankings = await self._get_degree_rankings(top_k)
            else:
                raise ValueError(f"Unsupported centrality algorithm: {algorithm}")

            # Calculate statistics
            scores = [r.score for r in rankings]
            if scores:
                avg_score = sum(scores) / len(scores)
                max_score = max(scores)
                min_score = min(scores)
            else:
                avg_score = max_score = min_score = 0.0

            # Create distribution buckets
            distribution = self._create_score_distribution(scores)

            return CentralityAnalysis(
                algorithm=algorithm,
                rankings=rankings,
                top_nodes=[r.node_id for r in rankings[:10]],
                statistics={
                    "average_score": avg_score,
                    "max_score": max_score,
                    "min_score": min_score,
                    "total_nodes": len(rankings)
                },
                distribution=distribution
            )

        except Exception as e:
            logger.error(f"Error getting centrality analysis: {e}")
            raise

    async def _get_pagerank_rankings(self, top_k: int) -> List[CentralityRanking]:
        """Get PageRank rankings"""
        query = """
        CALL apoc.algo.pageRank() YIELD node, score
        RETURN toString(id(node)) as node_id, labels(node)[0] as node_label, score
        ORDER BY score DESC
        LIMIT $limit
        """

        async with self.get_session() as session:
            result = await session.run(query, {"limit": top_k})

            rankings = []
            rank = 1
            scores = []

            async for record in result:
                scores.append(record["score"])

            if scores:
                max_score = max(scores)
                min_score = min(scores)

                # Reset result cursor
                result = await session.run(query, {"limit": top_k})

                async for record in result:
                    percentile = (record["score"] - min_score) / (max_score - min_score) if max_score > min_score else 0

                    rankings.append(CentralityRanking(
                        node_id=record["node_id"],
                        node_label=record["node_label"],
                        node_type=NodeType.ENTITY,  # Default, would need proper mapping
                        score=record["score"],
                        rank=rank,
                        percentile=percentile
                    ))
                    rank += 1

            return rankings

    async def _get_betweenness_rankings(self, top_k: int) -> List[CentralityRanking]:
        """Get betweenness centrality rankings"""
        query = """
        MATCH (n)
        CALL apoc.algo.betweenness([n]) YIELD node, score
        RETURN toString(id(node)) as node_id, labels(node)[0] as node_label, score
        ORDER BY score DESC
        LIMIT $limit
        """

        async with self.get_session() as session:
            result = await session.run(query, {"limit": top_k})

            rankings = []
            rank = 1
            scores = []

            async for record in result:
                scores.append(record["score"])

            if scores:
                max_score = max(scores)
                min_score = min(scores)

                # Reset result cursor
                result = await session.run(query, {"limit": top_k})

                async for record in result:
                    percentile = (record["score"] - min_score) / (max_score - min_score) if max_score > min_score else 0

                    rankings.append(CentralityRanking(
                        node_id=record["node_id"],
                        node_label=record["node_label"],
                        node_type=NodeType.ENTITY,
                        score=record["score"],
                        rank=rank,
                        percentile=percentile
                    ))
                    rank += 1

            return rankings

    async def _get_degree_rankings(self, top_k: int) -> List[CentralityRanking]:
        """Get degree centrality rankings"""
        query = """
        MATCH (n)
        OPTIONAL MATCH (n)-[r]-()
        WITH n, count(r) as degree
        RETURN toString(id(n)) as node_id, labels(n)[0] as node_label,
               toFloat(degree) as score
        ORDER BY degree DESC
        LIMIT $limit
        """

        async with self.get_session() as session:
            result = await session.run(query, {"limit": top_k})

            rankings = []
            rank = 1
            scores = []

            async for record in result:
                scores.append(record["score"])

            if scores:
                max_score = max(scores)
                min_score = min(scores)

                # Reset result cursor
                result = await session.run(query, {"limit": top_k})

                async for record in result:
                    percentile = (record["score"] - min_score) / (max_score - min_score) if max_score > min_score else 0

                    rankings.append(CentralityRanking(
                        node_id=record["node_id"],
                        node_label=record["node_label"],
                        node_type=NodeType.ENTITY,
                        score=record["score"],
                        rank=rank,
                        percentile=percentile
                    ))
                    rank += 1

            return rankings

    def _create_score_distribution(self, scores: List[float]) -> Dict[str, int]:
        """Create score distribution buckets"""
        if not scores:
            return {}

        min_score = min(scores)
        max_score = max(scores)
        bucket_count = 10
        bucket_size = (max_score - min_score) / bucket_count if max_score > min_score else 1

        distribution = {}
        for i in range(bucket_count):
            bucket_min = min_score + (i * bucket_size)
            bucket_max = min_score + ((i + 1) * bucket_size)
            bucket_label = f"{bucket_min:.2f}-{bucket_max:.2f}"

            count = sum(1 for score in scores if bucket_min <= score < bucket_max)
            if i == bucket_count - 1:  # Include max in last bucket
                count = sum(1 for score in scores if bucket_min <= score <= bucket_max)

            distribution[bucket_label] = count

        return distribution

    def _build_node_filter(self, node_filters: Optional[Dict[str, Any]]) -> str:
        """Build node filter Cypher clause"""
        if not node_filters:
            return ""

        conditions = []
        for key, value in node_filters.items():
            if key == "labels":
                labels_str = " AND ".join([f"'{label}' in labels(n)" for label in value])
                conditions.append(labels_str)
            elif key == "properties":
                for prop_key, prop_value in value.items():
                    if isinstance(prop_value, str):
                        conditions.append(f"n.{prop_key} = '{prop_value}'")
                    else:
                        conditions.append(f"n.{prop_key} = {prop_value}")

        return f"WHERE {' AND '.join(conditions)}" if conditions else ""

    def _build_edge_filter(self, edge_filters: Optional[Dict[str, Any]]) -> str:
        """Build edge filter Cypher clause"""
        if not edge_filters:
            return ""

        conditions = []
        for key, value in edge_filters.items():
            if key == "types":
                types_str = " OR ".join([f"type(r) = '{edge_type}'" for edge_type in value])
                conditions.append(f"({types_str})")
            elif key == "properties":
                for prop_key, prop_value in value.items():
                    if isinstance(prop_value, str):
                        conditions.append(f"r.{prop_key} = '{prop_value}'")
                    else:
                        conditions.append(f"r.{prop_key} = {prop_value}")

        return f"WHERE {' AND '.join(conditions)}" if conditions else ""

    async def _store_node_metrics(self, analysis_id: uuid.UUID, rankings: List[Dict[str, Any]], metric_field: str):
        """Store node metrics in database"""
        try:
            async with get_async_session() as db:
                for ranking in rankings:
                    node_metric = NodeMetrics(
                        analytics_result_id=analysis_id,
                        node_id=ranking["node_id"],
                        node_type=NodeType.ENTITY,  # Would need proper mapping
                        node_label=None,  # Would need to fetch from Neo4j
                        **{metric_field: ranking["score"]}
                    )
                    db.add(node_metric)

                await db.commit()

        except Exception as e:
            logger.error(f"Error storing node metrics: {e}")

    async def _store_community_metrics(self, analysis_id: uuid.UUID, assignments: List[Dict[str, Any]]):
        """Store community metrics in database"""
        try:
            # Group by community
            communities = {}
            for assignment in assignments:
                community_id = assignment["community_id"]
                if community_id not in communities:
                    communities[community_id] = []
                communities[community_id].append(assignment["node_id"])

            async with get_async_session() as db:
                for community_id, node_ids in communities.items():
                    community_metric = CommunityMetrics(
                        analytics_result_id=analysis_id,
                        community_id=community_id,
                        node_count=len(node_ids),
                        edge_count=0,  # Would need to calculate
                        density=0.0,  # Would need to calculate
                        modularity=0.0,  # Would need to calculate
                        internal_edges=0,  # Would need to calculate
                        external_edges=0  # Would need to calculate
                    )
                    db.add(community_metric)

                await db.commit()

        except Exception as e:
            logger.error(f"Error storing community metrics: {e}")

    async def _get_analysis_response(self, analysis_id: uuid.UUID) -> GraphAnalysisResponse:
        """Get complete analysis response with metrics"""
        try:
            async with get_async_session() as db:
                # Get main analysis result
                query = select(GraphAnalyticsResult).where(
                    GraphAnalyticsResult.id == analysis_id
                ).options(
                    selectinload(GraphAnalyticsResult.node_metrics),
                    selectinload(GraphAnalyticsResult.edge_metrics),
                    selectinload(GraphAnalyticsResult.community_metrics)
                )
                result = await db.execute(query)
                analysis = result.scalar_one_or_none()

                if not analysis:
                    raise ValueError(f"Analysis not found: {analysis_id}")

                # Convert to response format
                return GraphAnalysisResponse(
                    id=analysis.id,
                    analysis_type=analysis.analysis_type,
                    analysis_name=analysis.analysis_name,
                    description=analysis.description,
                    query_config=analysis.query_config,
                    graph_metrics=GraphStatistics(
                        total_nodes=analysis.node_count,
                        total_edges=analysis.edge_count,
                        node_types={},
                        edge_types={},
                        density=analysis.density,
                        connected_components=analysis.component_count,
                        largest_component_size=None,
                        average_degree=(2 * analysis.edge_count) / analysis.node_count if analysis.node_count > 0 else 0,
                        last_updated=analysis.updated_at
                    ),
                    node_metrics=[
                        NodeMetricData(
                            node_id=m.node_id,
                            node_type=m.node_type,
                            node_label=m.node_label,
                            pagerank_score=m.pagerank_score,
                            betweenness_centrality=m.betweenness_centrality,
                            closeness_centrality=m.closeness_centrality,
                            eigenvector_centrality=m.eigenvector_centrality,
                            degree_centrality=m.degree_centrality,
                            degree=m.degree,
                            in_degree=m.in_degree,
                            out_degree=m.out_degree,
                            clustering_coefficient=m.clustering_coefficient,
                            community_id=m.community_id,
                            community_size=m.community_size,
                            modularity=m.modularity,
                            custom_metrics=m.custom_metrics
                        ) for m in analysis.node_metrics
                    ] if analysis.include_node_metrics else None,
                    edge_metrics=[
                        EdgeMetricData(
                            edge_id=m.edge_id,
                            source_node_id=m.source_node_id,
                            target_node_id=m.target_node_id,
                            edge_type=m.edge_type,
                            weight=m.weight,
                            betweenness=m.betweenness,
                            edge_betweenness=m.edge_betweenness,
                            jaccard_similarity=m.jaccard_similarity,
                            adamic_adar=m.adamic_adar,
                            shortest_path_length=m.shortest_path_length,
                            bridges_count=m.bridges_count,
                            custom_metrics=m.custom_metrics
                        ) for m in analysis.edge_metrics
                    ] if analysis.include_edge_metrics else None,
                    community_metrics=[
                        CommunityMetricData(
                            community_id=m.community_id,
                            community_label=m.community_label,
                            node_count=m.node_count,
                            edge_count=m.edge_count,
                            density=m.density,
                            modularity=m.modularity,
                            conductance=m.conductance,
                            cluster_coefficient=m.cluster_coefficient,
                            silhouette_score=m.silhouette_score,
                            internal_edges=m.internal_edges,
                            external_edges=m.external_edges,
                            expansion=m.expansion,
                            node_type_distribution=m.node_type_distribution,
                            edge_type_distribution=m.edge_type_distribution,
                            central_nodes=m.central_nodes,
                            bridge_nodes=m.bridge_nodes
                        ) for m in analysis.community_metrics
                    ] if analysis.include_community_metrics else None,
                    execution_time_ms=analysis.execution_time_ms,
                    memory_usage_mb=analysis.memory_usage_mb,
                    status=analysis.status,
                    created_at=analysis.created_at,
                    updated_at=analysis.updated_at
                )

        except Exception as e:
            logger.error(f"Error getting analysis response: {e}")
            raise


# Global instance
graph_analytics_service = GraphAnalyticsService()