"""Citation Graph Service for Research Assistant.

Manages citation relationships in Neo4j and provides graph visualization data
for Cytoscape.js frontend component.

Features:
- Sync citations to Neo4j as :Citation nodes
- Create :CITES relationships between papers
- Compute force-directed layout positions
- Calculate influence scores based on citation counts
"""

import asyncio
import math
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from neo4j import AsyncDriver, AsyncGraphDatabase
from structlog import get_logger

from src.core.config import settings

logger = get_logger()


class CitationGraphService:
    """Service for managing citation graphs in Neo4j."""

    def __init__(self):
        """Initialize the citation graph service."""
        self._driver: Optional[AsyncDriver] = None

    async def connect(self) -> None:
        """Establish connection to Neo4j database."""
        if self._driver is None:
            self._driver = AsyncGraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            )
            # Verify connectivity
            try:
                await self._driver.verify_connectivity()
                logger.info("neo4j_connected", uri=settings.NEO4J_URI)
            except Exception as e:
                logger.error("neo4j_connection_failed", error=str(e))
                raise

    async def close(self) -> None:
        """Close Neo4j connection."""
        if self._driver:
            await self._driver.close()
            self._driver = None
            logger.info("neo4j_disconnected")

    async def _ensure_connected(self) -> AsyncDriver:
        """Ensure connection is established and return driver."""
        if self._driver is None:
            await self.connect()
        return self._driver

    # =========================================================================
    # Node Management
    # =========================================================================

    async def sync_citation_to_graph(
        self,
        citation_id: UUID,
        document_id: Optional[UUID],
        title: str,
        authors: Optional[List[str]] = None,
        year: Optional[int] = None,
        doi: Optional[str] = None,
        arxiv_id: Optional[str] = None,
        venue: Optional[str] = None,
        is_uploaded: bool = True,
        organization_id: str = "",
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Sync a citation to Neo4j as a :Citation node.

        Args:
            citation_id: Unique citation identifier
            document_id: Associated document ID (if uploaded)
            title: Paper title
            authors: List of author names
            year: Publication year
            doi: Digital Object Identifier
            arxiv_id: ArXiv identifier
            venue: Journal/conference name
            is_uploaded: Whether this is an uploaded document or external reference
            organization_id: Owning tenant — required for graph isolation
            project_id: Owning project, when the citation belongs to one

        Returns:
            Dict with node creation status

        Raises:
            ValueError: if organization_id is missing (fail closed, mirrors
                get_citation_graph) — a null-org node is invisible to every
                org-scoped read and needs a backfill to recover.
        """
        if not organization_id:
            raise ValueError("organization_id is required to sync a citation node")

        driver = await self._ensure_connected()

        query = """
        MERGE (c:Citation {citation_id: $citation_id})
        SET c.document_id = $document_id,
            c.title = $title,
            c.authors = $authors,
            c.year = $year,
            c.doi = $doi,
            c.arxiv_id = $arxiv_id,
            c.venue = $venue,
            c.is_uploaded = $is_uploaded,
            c.organization_id = $organization_id,
            c.project_id = $project_id,
            c.updated_at = datetime()
        RETURN c.citation_id as id, c.title as title
        """

        async with driver.session() as session:
            result = await session.run(
                query,
                citation_id=str(citation_id),
                document_id=str(document_id) if document_id else None,
                title=title,
                authors=authors or [],
                year=year,
                doi=doi,
                arxiv_id=arxiv_id,
                venue=venue,
                is_uploaded=is_uploaded,
                organization_id=organization_id,
                project_id=project_id,
            )
            record = await result.single()

            logger.info(
                "citation_synced_to_graph",
                citation_id=str(citation_id),
                title=title[:50] if title else None,
            )

            return {
                "id": record["id"] if record else str(citation_id),
                "title": record["title"] if record else title,
                "created": True,
            }

    async def create_cites_relationship(
        self,
        source_citation_id: UUID,
        target_citation_id: UUID,
        relationship_type: str = "CITES",
        citation_context: Optional[str] = None,
        confidence: float = 1.0,
    ) -> Dict[str, Any]:
        """Create a :CITES relationship between two citations.

        Args:
            source_citation_id: The citing paper
            target_citation_id: The cited paper
            relationship_type: Type of relationship (CITES, EXTENDS, CONTRADICTS, etc.)
            citation_context: Text context where citation appears
            confidence: Confidence score for the relationship

        Returns:
            Dict with relationship creation status
        """
        driver = await self._ensure_connected()

        query = """
        MATCH (source:Citation {citation_id: $source_id})
        MATCH (target:Citation {citation_id: $target_id})
        MERGE (source)-[r:CITES]->(target)
        SET r.relationship_type = $rel_type,
            r.citation_context = $context,
            r.confidence = $confidence,
            r.created_at = datetime()
        RETURN source.citation_id as source, target.citation_id as target
        """

        async with driver.session() as session:
            result = await session.run(
                query,
                source_id=str(source_citation_id),
                target_id=str(target_citation_id),
                rel_type=relationship_type,
                context=citation_context,
                confidence=confidence,
            )
            record = await result.single()

            if record:
                logger.info(
                    "citation_relationship_created",
                    source=str(source_citation_id),
                    target=str(target_citation_id),
                    type=relationship_type,
                )
                return {
                    "source": record["source"],
                    "target": record["target"],
                    "created": True,
                }
            else:
                logger.warning(
                    "citation_relationship_failed",
                    source=str(source_citation_id),
                    target=str(target_citation_id),
                    reason="One or both nodes not found",
                )
                return {"created": False, "error": "Nodes not found"}

    # =========================================================================
    # Graph Queries
    # =========================================================================

    async def get_citation_graph(
        self,
        project_id: Optional[UUID] = None,
        document_id: Optional[UUID] = None,
        depth: int = 2,
        include_external: bool = True,
        limit: int = 500,
        organization_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get citation graph data for visualization.

        Args:
            project_id: Filter by project (optional)
            document_id: Filter by specific document (optional)
            depth: How many levels of citations to traverse
            include_external: Include external (non-uploaded) papers
            limit: Maximum number of nodes to return
            organization_id: Tenant partition — every branch is scoped to it

        Returns:
            Dict with nodes and edges for Cytoscape.js
        """
        if not organization_id:
            # Fail closed: without a tenant partition this query would span
            # every organization's citations.
            raise ValueError("organization_id is required for citation graph reads")

        driver = await self._ensure_connected()

        # Build dynamic query based on filters — all anchored inside the
        # caller's tenant so the is_uploaded convenience branch can never
        # pull in foreign citations.
        org_scope = "start.organization_id = $organization_id"
        if document_id:
            match_clause = f"""
            MATCH (start:Citation {{document_id: $document_id, organization_id: $organization_id}})
            WHERE {org_scope}
            """
            params = {
                "document_id": str(document_id),
                "organization_id": organization_id,
                "depth": depth,
                "limit": limit,
            }
        elif project_id:
            # Strict project scope. The old `OR start.is_uploaded = true`
            # escape hatch let every uploaded citation in the org into any
            # project's graph (and, before project_id was stamped, the OR was
            # the only branch that matched at all).
            match_clause = f"""
            MATCH (start:Citation)
            WHERE {org_scope}
              AND start.project_id = $project_id
            """
            params = {
                "project_id": str(project_id),
                "organization_id": organization_id,
                "depth": depth,
                "limit": limit,
            }
        else:
            match_clause = f"MATCH (start:Citation) WHERE {org_scope}"
            params = {
                "organization_id": organization_id,
                "depth": depth,
                "limit": limit,
            }

        # Query to get nodes and relationships
        query = f"""
        {match_clause}
        CALL apoc.path.subgraphAll(start, {{
            relationshipFilter: 'CITES>|<CITES',
            maxLevel: $depth,
            limit: $limit
        }})
        YIELD nodes, relationships
        UNWIND nodes as n
        WITH COLLECT(DISTINCT n) as allNodes, relationships
        UNWIND allNodes as node
        OPTIONAL MATCH (node)<-[incoming:CITES]-(citer:Citation)
        WHERE citer.organization_id = $organization_id
        WITH node, COUNT(incoming) as citedBy, relationships
        RETURN
            node.citation_id as id,
            node.title as title,
            node.authors as authors,
            node.year as year,
            node.venue as venue,
            node.doi as doi,
            node.arxiv_id as arxiv_id,
            node.is_uploaded as is_uploaded,
            node.document_id as document_id,
            node.organization_id as organization_id,
            citedBy as citation_count,
            relationships
        """

        # Fallback query without APOC (if APOC not installed)
        fallback_query = f"""
        {match_clause}
        OPTIONAL MATCH path = (start)-[:CITES*0..{depth}]-(connected:Citation)
        WITH COLLECT(DISTINCT connected) + COLLECT(DISTINCT start) as nodes
        UNWIND nodes as node
        OPTIONAL MATCH (node)<-[incoming:CITES]-(citer:Citation)
        WHERE citer.organization_id = $organization_id
        WITH node, COUNT(incoming) as citedBy
        OPTIONAL MATCH (node)-[r:CITES]-(other:Citation)
        WHERE other IN nodes
        RETURN
            node.citation_id as id,
            node.title as title,
            node.authors as authors,
            node.year as year,
            node.venue as venue,
            node.doi as doi,
            node.arxiv_id as arxiv_id,
            node.is_uploaded as is_uploaded,
            node.document_id as document_id,
            node.organization_id as organization_id,
            citedBy as citation_count
        LIMIT $limit
        """

        async with driver.session() as session:
            try:
                # Try APOC query first
                result = await session.run(query, **params)
                records = await result.data()
            except Exception:
                # Fallback to basic query
                logger.warning("apoc_not_available", message="Using fallback query")
                result = await session.run(fallback_query, **params)
                records = await result.data()

            # Get edges separately
            edge_query = """
            MATCH (source:Citation)-[r:CITES]->(target:Citation)
            WHERE source.citation_id IN $node_ids AND target.citation_id IN $node_ids
            RETURN
                source.citation_id as source,
                target.citation_id as target,
                r.relationship_type as type,
                r.confidence as confidence
            """

            # Traversal (apoc.subgraphAll / variable-length path) can reach
            # nodes written before tenant scoping existed — drop anything
            # foreign here so the payload can never carry another org's
            # citations.
            records = [
                r for r in records if r.get("organization_id") == organization_id
            ]

            node_ids = [r["id"] for r in records if r.get("id")]

            if node_ids:
                edge_result = await session.run(edge_query, node_ids=node_ids)
                edges = await edge_result.data()
            else:
                edges = []

        # Filter external if needed
        if not include_external:
            records = [r for r in records if r.get("is_uploaded", True)]

        # Compute layout positions
        nodes_with_positions = self._compute_layout(records, edges)

        logger.info(
            "citation_graph_retrieved",
            node_count=len(nodes_with_positions),
            edge_count=len(edges),
            depth=depth,
        )

        return {
            "nodes": nodes_with_positions,
            "edges": [
                {
                    "id": f"{e['source']}-{e['target']}",
                    "source": e["source"],
                    "target": e["target"],
                    "type": e.get("type", "CITES"),
                    "confidence": e.get("confidence", 1.0),
                }
                for e in edges
            ],
            "metadata": {
                "total_nodes": len(nodes_with_positions),
                "total_edges": len(edges),
                "depth": depth,
                "include_external": include_external,
            },
        }

    async def get_node_details(self, citation_id: UUID) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific citation node.

        Args:
            citation_id: The citation to get details for

        Returns:
            Dict with full citation details or None if not found
        """
        driver = await self._ensure_connected()

        query = """
        MATCH (c:Citation {citation_id: $citation_id})
        OPTIONAL MATCH (c)<-[incoming:CITES]-()
        OPTIONAL MATCH (c)-[outgoing:CITES]->()
        WITH c, COUNT(DISTINCT incoming) as cited_by, COUNT(DISTINCT outgoing) as cites
        RETURN
            c.citation_id as id,
            c.document_id as document_id,
            c.title as title,
            c.authors as authors,
            c.year as year,
            c.venue as venue,
            c.doi as doi,
            c.arxiv_id as arxiv_id,
            c.is_uploaded as is_uploaded,
            cited_by,
            cites,
            (cited_by * 2 + cites) as influence_score
        """

        async with driver.session() as session:
            result = await session.run(query, citation_id=str(citation_id))
            record = await result.single()

            if record:
                return dict(record)
            return None

    async def calculate_influence_scores(
        self, citation_ids: Optional[List[UUID]] = None
    ) -> Dict[str, float]:
        """Calculate influence scores for citations based on citation network.

        Uses a simplified PageRank-like algorithm:
        - Incoming citations (cited_by) weight: 2x
        - Outgoing citations (cites) weight: 1x
        - Normalized to 0-100 scale

        Args:
            citation_ids: Specific citations to calculate for (None = all)

        Returns:
            Dict mapping citation_id to influence score
        """
        driver = await self._ensure_connected()

        if citation_ids:
            query = """
            MATCH (c:Citation)
            WHERE c.citation_id IN $ids
            OPTIONAL MATCH (c)<-[incoming:CITES]-()
            OPTIONAL MATCH (c)-[outgoing:CITES]->()
            WITH c, COUNT(DISTINCT incoming) as cited_by, COUNT(DISTINCT outgoing) as cites
            RETURN c.citation_id as id, (cited_by * 2 + cites) as raw_score
            """
            params = {"ids": [str(cid) for cid in citation_ids]}
        else:
            query = """
            MATCH (c:Citation)
            OPTIONAL MATCH (c)<-[incoming:CITES]-()
            OPTIONAL MATCH (c)-[outgoing:CITES]->()
            WITH c, COUNT(DISTINCT incoming) as cited_by, COUNT(DISTINCT outgoing) as cites
            RETURN c.citation_id as id, (cited_by * 2 + cites) as raw_score
            """
            params = {}

        async with driver.session() as session:
            result = await session.run(query, **params)
            records = await result.data()

        if not records:
            return {}

        # Normalize scores to 0-100
        max_score = max(r["raw_score"] for r in records) or 1
        return {r["id"]: round((r["raw_score"] / max_score) * 100, 2) for r in records}

    # =========================================================================
    # Layout Computation
    # =========================================================================

    def _compute_layout(
        self, nodes: List[Dict], edges: List[Dict]
    ) -> List[Dict[str, Any]]:
        """Compute force-directed layout positions for nodes.

        Uses a simple force-directed algorithm suitable for small-medium graphs.
        For large graphs (500+ nodes), positions should be computed client-side.

        Args:
            nodes: List of node records
            edges: List of edge records

        Returns:
            Nodes with added x, y position coordinates
        """
        if not nodes:
            return []

        # For large graphs, return without positions (let frontend handle it)
        if len(nodes) > 200:
            return [
                {
                    **node,
                    "position": None,  # Frontend will compute
                }
                for node in nodes
            ]

        # Build adjacency for layout
        node_ids = {n["id"]: i for i, n in enumerate(nodes)}
        adjacency: Dict[int, List[int]] = {i: [] for i in range(len(nodes))}

        for edge in edges:
            src_idx = node_ids.get(edge.get("source"))
            tgt_idx = node_ids.get(edge.get("target"))
            if src_idx is not None and tgt_idx is not None:
                adjacency[src_idx].append(tgt_idx)
                adjacency[tgt_idx].append(src_idx)

        # Initialize positions in a circle
        positions = []
        n = len(nodes)
        for i in range(n):
            angle = 2 * math.pi * i / n
            positions.append([math.cos(angle) * 300, math.sin(angle) * 300])

        # Simple force-directed iteration
        iterations = 50
        k = 100  # Optimal distance
        temp = 100  # Temperature for simulated annealing

        for _ in range(iterations):
            # Calculate repulsive forces
            displacements = [[0.0, 0.0] for _ in range(n)]

            for i in range(n):
                for j in range(i + 1, n):
                    dx = positions[i][0] - positions[j][0]
                    dy = positions[i][1] - positions[j][1]
                    dist = math.sqrt(dx * dx + dy * dy) or 0.01

                    # Repulsive force
                    force = (k * k) / dist
                    fx = (dx / dist) * force
                    fy = (dy / dist) * force

                    displacements[i][0] += fx
                    displacements[i][1] += fy
                    displacements[j][0] -= fx
                    displacements[j][1] -= fy

            # Calculate attractive forces (edges)
            for i, neighbors in adjacency.items():
                for j in neighbors:
                    if i < j:
                        dx = positions[i][0] - positions[j][0]
                        dy = positions[i][1] - positions[j][1]
                        dist = math.sqrt(dx * dx + dy * dy) or 0.01

                        # Attractive force
                        force = (dist * dist) / k
                        fx = (dx / dist) * force
                        fy = (dy / dist) * force

                        displacements[i][0] -= fx
                        displacements[i][1] -= fy
                        displacements[j][0] += fx
                        displacements[j][1] += fy

            # Apply displacements with temperature
            for i in range(n):
                dx, dy = displacements[i]
                dist = math.sqrt(dx * dx + dy * dy) or 0.01
                capped = min(dist, temp)
                positions[i][0] += (dx / dist) * capped
                positions[i][1] += (dy / dist) * capped

            # Cool down
            temp *= 0.95

        # Return nodes with positions
        return [
            {
                **node,
                "position": {
                    "x": round(positions[i][0], 2),
                    "y": round(positions[i][1], 2),
                },
            }
            for i, node in enumerate(nodes)
        ]

    async def delete_citation_node(self, citation_id: UUID) -> bool:
        """Delete a citation node and all its relationships.

        Args:
            citation_id: The citation to delete

        Returns:
            True if deleted, False if not found
        """
        driver = await self._ensure_connected()

        query = """
        MATCH (c:Citation {citation_id: $citation_id})
        DETACH DELETE c
        RETURN COUNT(c) as deleted
        """

        async with driver.session() as session:
            result = await session.run(query, citation_id=str(citation_id))
            record = await result.single()
            deleted = record["deleted"] > 0 if record else False

            if deleted:
                logger.info("citation_node_deleted", citation_id=str(citation_id))
            return deleted


# Singleton instance
_citation_graph_service: Optional[CitationGraphService] = None


async def get_citation_graph_service() -> CitationGraphService:
    """Get or create the citation graph service singleton."""
    global _citation_graph_service
    if _citation_graph_service is None:
        _citation_graph_service = CitationGraphService()
        await _citation_graph_service.connect()
    return _citation_graph_service
