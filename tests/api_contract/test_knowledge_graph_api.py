"""
Knowledge Graph API Contract Tests
Comprehensive testing for entity search, relationship queries, and graph visualization
"""

import pytest
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List
from fastapi.testclient import TestClient
from httpx import AsyncClient


@pytest.mark.contract
@pytest.mark.knowledge_graph
class TestEntitySearchAPI:
    """Test entity search endpoints"""

    def test_search_entities_success(self, test_client: TestClient, auth_headers, mock_external_services):
        """Test successful entity search"""
        headers = auth_headers({"email": "entity@example.com", "first_name": "Entity", "last_name": "Search"})

        search_params = {
            "query": "machine learning",
            "entity_types": ["person", "organization", "technology"],
            "limit": 10,
            "offset": 0,
            "include_metadata": True
        }

        response = test_client.get(
            "/api/v1/graph/entities",
            params=search_params,
            headers=headers
        )

        assert response.status_code == 200
        response_data = response.json()

        # Verify response structure
        assert "entities" in response_data
        assert "total_count" in response_data
        assert "pagination" in response_data
        assert isinstance(response_data["entities"], list)

        # Verify entity structure
        if response_data["entities"]:
            first_entity = response_data["entities"][0]
            assert "id" in first_entity
            assert "name" in first_entity
            assert "type" in first_entity
            assert "confidence" in first_entity
            assert "mentions" in first_entity
            assert "metadata" in first_entity

            # Confidence should be between 0 and 1
            assert 0 <= first_entity["confidence"] <= 1

    def test_search_entities_by_type(self, test_client: TestClient, auth_headers):
        """Test entity search filtered by type"""
        headers = auth_headers({"email": "type@example.com", "first_name": "Type", "last_name": "Filter"})

        search_params = {
            "query": "research",
            "entity_types": ["person"],
            "limit": 5
        }

        response = test_client.get(
            "/api/v1/graph/entities",
            params=search_params,
            headers=headers
        )

        assert response.status_code == 200
        response_data = response.json()

        # All returned entities should be of type 'person'
        if response_data["entities"]:
            for entity in response_data["entities"]:
                assert entity["type"] == "person"

    def test_search_entities_with_pagination(self, test_client: TestClient, auth_headers):
        """Test entity search with pagination"""
        headers = auth_headers({"email": "page@example.com", "first_name": "Page", "last_name": "Entity"})

        # First page
        search_params = {
            "query": "artificial intelligence",
            "limit": 5,
            "offset": 0
        }

        response = test_client.get(
            "/api/v1/graph/entities",
            params=search_params,
            headers=headers
        )

        assert response.status_code == 200
        response_data = response.json()

        assert len(response_data["entities"]) <= 5
        assert response_data["pagination"]["limit"] == 5
        assert response_data["pagination"]["offset"] == 0

    def test_search_entities_empty_query(self, test_client: TestClient, auth_headers):
        """Test entity search with empty query"""
        headers = auth_headers({"email": "empty@example.com", "first_name": "Empty", "last_name": "Query"})

        search_params = {
            "query": "",
            "entity_types": ["organization"],
            "limit": 10
        }

        response = test_client.get(
            "/api/v1/graph/entities",
            params=search_params,
            headers=headers
        )

        assert response.status_code == 200
        response_data = response.json()

        # Should return all organizations or handle gracefully
        assert "entities" in response_data

    def test_search_entities_invalid_type(self, test_client: TestClient, auth_headers):
        """Test entity search with invalid entity type"""
        headers = auth_headers({"email": "invalidtype@example.com", "first_name": "Invalid", "last_name": "Type"})

        search_params = {
            "query": "test",
            "entity_types": ["invalid_type"],
            "limit": 10
        }

        response = test_client.get(
            "/api/v1/graph/entities",
            params=search_params,
            headers=headers
        )

        # Should handle invalid types gracefully
        assert response.status_code in [200, 422]

    def test_search_entities_unauthorized(self, test_client: TestClient):
        """Test entity search without authentication"""
        search_params = {
            "query": "test",
            "limit": 10
        }

        response = test_client.get(
            "/api/v1/graph/entities",
            params=search_params
        )

        assert response.status_code == 401

    def test_get_entity_details_success(self, test_client: TestClient, auth_headers):
        """Test getting detailed information about a specific entity"""
        headers = auth_headers({"email": "details@example.com", "first_name": "Entity", "last_name": "Details"})

        entity_id = str(uuid.uuid4())

        response = test_client.get(
            f"/api/v1/graph/entities/{entity_id}",
            headers=headers
        )

        # Might return 404 for non-existent entity, which is expected
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            response_data = response.json()
            assert "id" in response_data
            assert "name" in response_data
            assert "type" in response_data
            assert "relationships" in response_data
            assert "mentions" in response_data
            assert "metadata" in response_data

    def test_get_entity_details_not_found(self, test_client: TestClient, auth_headers):
        """Test getting details for non-existent entity"""
        headers = auth_headers({"email": "notfound@example.com", "first_name": "Not", "last_name": "Found"})

        fake_entity_id = str(uuid.uuid4())
        response = test_client.get(
            f"/api/v1/graph/entities/{fake_entity_id}",
            headers=headers
        )

        assert response.status_code == 404
        response_data = response.json()
        assert "not found" in response_data["error"]["message"].lower()


@pytest.mark.contract
@pytest.mark.knowledge_graph
class TestRelationshipQueriesAPI:
    """Test relationship query endpoints"""

    def test_search_relationships_success(self, test_client: TestClient, auth_headers):
        """Test successful relationship search"""
        headers = auth_headers({"email": "relation@example.com", "first_name": "Relation", "last_name": "Search"})

        search_params = {
            "entity_id": str(uuid.uuid4()),
            "relationship_types": ["works_for", "collaborates_with", "mentions"],
            "direction": "outgoing",
            "limit": 10,
            "include_metadata": True
        }

        response = test_client.get(
            "/api/v1/graph/relationships",
            params=search_params,
            headers=headers
        )

        assert response.status_code == 200
        response_data = response.json()

        # Verify response structure
        assert "relationships" in response_data
        assert "total_count" in response_data
        assert "pagination" in response_data
        assert isinstance(response_data["relationships"], list)

        # Verify relationship structure
        if response_data["relationships"]:
            first_rel = response_data["relationships"][0]
            assert "id" in first_rel
            assert "source_entity" in first_rel
            assert "target_entity" in first_rel
            assert "relationship_type" in first_rel
            assert "confidence" in first_rel
            assert "metadata" in first_rel

            # Source and target entities should have basic structure
            for entity in [first_rel["source_entity"], first_rel["target_entity"]]:
                assert "id" in entity
                assert "name" in entity
                assert "type" in entity

    def test_search_relationships_by_type(self, test_client: TestClient, auth_headers):
        """Test relationship search filtered by type"""
        headers = auth_headers({"email": "reltype@example.com", "first_name": "Rel", "last_name": "Type"})

        search_params = {
            "entity_id": str(uuid.uuid4()),
            "relationship_types": ["works_for"],
            "direction": "outgoing",
            "limit": 5
        }

        response = test_client.get(
            "/api/v1/graph/relationships",
            params=search_params,
            headers=headers
        )

        assert response.status_code == 200
        response_data = response.json()

        # All returned relationships should be of type 'works_for'
        if response_data["relationships"]:
            for rel in response_data["relationships"]:
                assert rel["relationship_type"] == "works_for"

    def test_search_relationships_bidirectional(self, test_client: TestClient, auth_headers):
        """Test bidirectional relationship search"""
        headers = auth_headers({"email": "bidirectional@example.com", "first_name": "Bi", "last_name": "Directional"})

        search_params = {
            "entity_id": str(uuid.uuid4()),
            "direction": "both",
            "limit": 10
        }

        response = test_client.get(
            "/api/v1/graph/relationships",
            params=search_params,
            headers=headers
        )

        assert response.status_code == 200
        response_data = response.json()

        # Should include both incoming and outgoing relationships
        assert "relationships" in response_data

    def test_search_relationships_between_entities(self, test_client: TestClient, auth_headers):
        """Test relationship search between specific entities"""
        headers = auth_headers({"email": "between@example.com", "first_name": "Between", "last_name": "Entities"})

        entity1_id = str(uuid.uuid4())
        entity2_id = str(uuid.uuid4())

        search_params = {
            "source_entity_id": entity1_id,
            "target_entity_id": entity2_id,
            "limit": 5
        }

        response = test_client.get(
            "/api/v1/graph/relationships/between",
            params=search_params,
            headers=headers
        )

        assert response.status_code == 200
        response_data = response.json()

        # Verify response structure
        assert "relationships" in response_data
        assert "source_entity" in response_data
        assert "target_entity" in response_data

    def test_search_relationships_invalid_entity_id(self, test_client: TestClient, auth_headers):
        """Test relationship search with invalid entity ID"""
        headers = auth_headers({"email": "invalidrel@example.com", "first_name": "Invalid", "last_name": "Rel"})

        search_params = {
            "entity_id": "invalid-uuid",
            "limit": 10
        }

        response = test_client.get(
            "/api/v1/graph/relationships",
            params=search_params,
            headers=headers
        )

        assert response.status_code == 422  # Validation error

    def test_search_relationships_unauthorized(self, test_client: TestClient):
        """Test relationship search without authentication"""
        search_params = {
            "entity_id": str(uuid.uuid4()),
            "limit": 10
        }

        response = test_client.get(
            "/api/v1/graph/relationships",
            params=search_params
        )

        assert response.status_code == 401


@pytest.mark.contract
@pytest.mark.knowledge_graph
class TestGraphVisualizationAPI:
    """Test graph visualization endpoints"""

    def test_get_graph_visualization_success(self, test_client: TestClient, auth_headers):
        """Test successful graph visualization data retrieval"""
        headers = auth_headers({"email": "visual@example.com", "first_name": "Graph", "last_name": "Visual"})

        viz_params = {
            "center_entity_id": str(uuid.uuid4()),
            "max_depth": 2,
            "max_nodes": 50,
            "include_relationships": True,
            "layout_algorithm": "force_directed"
        }

        response = test_client.get(
            "/api/v1/graph/visualize",
            params=viz_params,
            headers=headers
        )

        assert response.status_code == 200
        response_data = response.json()

        # Verify graph structure
        assert "nodes" in response_data
        assert "edges" in response_data
        assert "layout" in response_data
        assert "metadata" in response_data

        # Verify nodes structure
        assert isinstance(response_data["nodes"], list)
        if response_data["nodes"]:
            first_node = response_data["nodes"][0]
            assert "id" in first_node
            assert "label" in first_node
            assert "type" in first_node
            assert "position" in first_node
            assert "x" in first_node["position"]
            assert "y" in first_node["position"]

        # Verify edges structure
        assert isinstance(response_data["edges"], list)
        if response_data["edges"]:
            first_edge = response_data["edges"][0]
            assert "id" in first_edge
            assert "source" in first_edge
            assert "target" in first_edge
            assert "type" in first_edge
            assert "weight" in first_edge

        # Verify layout information
        layout_data = response_data["layout"]
        assert "algorithm" in layout_data
        assert "bounds" in layout_data
        assert "min_x" in layout_data["bounds"]
        assert "max_x" in layout_data["bounds"]
        assert "min_y" in layout_data["bounds"]
        assert "max_y" in layout_data["bounds"]

    def test_get_graph_visualization_with_filters(self, test_client: TestClient, auth_headers):
        """Test graph visualization with entity and relationship filters"""
        headers = auth_headers({"email": "vizfilter@example.com", "first_name": "Viz", "last_name": "Filter"})

        viz_params = {
            "center_entity_id": str(uuid.uuid4()),
            "max_depth": 3,
            "max_nodes": 30,
            "entity_types": ["person", "organization"],
            "relationship_types": ["works_for", "collaborates_with"],
            "layout_algorithm": "hierarchical"
        }

        response = test_client.get(
            "/api/v1/graph/visualize",
            params=viz_params,
            headers=headers
        )

        assert response.status_code == 200
        response_data = response.json()

        # All nodes should be of the specified types
        if response_data["nodes"]:
            for node in response_data["nodes"]:
                assert node["type"] in ["person", "organization"]

        # All edges should be of the specified types
        if response_data["edges"]:
            for edge in response_data["edges"]:
                assert edge["type"] in ["works_for", "collaborates_with"]

    def test_get_graph_visualization_different_layouts(self, test_client: TestClient, auth_headers):
        """Test graph visualization with different layout algorithms"""
        headers = auth_headers({"email": "layout@example.com", "first_name": "Graph", "last_name": "Layout"})

        layouts = ["force_directed", "hierarchical", "circular", "grid"]

        for layout in layouts:
            viz_params = {
                "center_entity_id": str(uuid.uuid4()),
                "max_depth": 2,
                "max_nodes": 20,
                "layout_algorithm": layout
            }

            response = test_client.get(
                "/api/v1/graph/visualize",
                params=viz_params,
                headers=headers
            )

            assert response.status_code == 200
            response_data = response.json()

            # Layout should match requested algorithm
            assert response_data["layout"]["algorithm"] == layout

    def test_get_graph_visualization_large_graph(self, test_client: TestClient, auth_headers):
        """Test graph visualization with large number of nodes"""
        headers = auth_headers({"email": "large@example.com", "first_name": "Large", "last_name": "Graph"})

        viz_params = {
            "center_entity_id": str(uuid.uuid4()),
            "max_depth": 3,
            "max_nodes": 100,
            "include_relationships": True
        }

        response = test_client.get(
            "/api/v1/graph/visualize",
            params=viz_params,
            headers=headers
        )

        assert response.status_code == 200
        response_data = response.json()

        # Should respect max_nodes limit
        assert len(response_data["nodes"]) <= 100

    def test_get_graph_visualization_invalid_parameters(self, test_client: TestClient, auth_headers):
        """Test graph visualization with invalid parameters"""
        headers = auth_headers({"email": "invalidviz@example.com", "first_name": "Invalid", "last_name": "Viz"})

        # Invalid max_depth
        viz_params = {
            "center_entity_id": str(uuid.uuid4()),
            "max_depth": -1,  # Invalid
            "max_nodes": 50
        }

        response = test_client.get(
            "/api/v1/graph/visualize",
            params=viz_params,
            headers=headers
        )

        assert response.status_code == 422  # Validation error

        # Invalid layout algorithm
        viz_params = {
            "center_entity_id": str(uuid.uuid4()),
            "max_depth": 2,
            "max_nodes": 50,
            "layout_algorithm": "invalid_algorithm"
        }

        response = test_client.get(
            "/api/v1/graph/visualize",
            params=viz_params,
            headers=headers
        )

        assert response.status_code == 422  # Validation error

    def test_get_graph_visualization_unauthorized(self, test_client: TestClient):
        """Test graph visualization without authentication"""
        viz_params = {
            "center_entity_id": str(uuid.uuid4()),
            "max_depth": 2,
            "max_nodes": 50
        }

        response = test_client.get(
            "/api/v1/graph/visualize",
            params=viz_params
        )

        assert response.status_code == 401

    def test_get_graph_statistics(self, test_client: TestClient, auth_headers):
        """Test graph statistics endpoint"""
        headers = auth_headers({"email": "stats@example.com", "first_name": "Graph", "last_name": "Stats"})

        response = test_client.get(
            "/api/v1/graph/statistics",
            headers=headers
        )

        assert response.status_code == 200
        response_data = response.json()

        # Verify statistics structure
        assert "total_entities" in response_data
        assert "total_relationships" in response_data
        assert "entity_types" in response_data
        assert "relationship_types" in response_data
        assert "avg_degree" in response_data
        assert "graph_density" in response_data

        # Verify entity type breakdown
        entity_types = response_data["entity_types"]
        assert isinstance(entity_types, dict)
        for entity_type, count in entity_types.items():
            assert isinstance(entity_type, str)
            assert isinstance(count, int)

        # Verify relationship type breakdown
        relationship_types = response_data["relationship_types"]
        assert isinstance(relationship_types, dict)
        for rel_type, count in relationship_types.items():
            assert isinstance(rel_type, str)
            assert isinstance(count, int)


@pytest.mark.contract
@pytest.mark.knowledge_graph
class TestGraphAnalysisAPI:
    """Test graph analysis endpoints"""

    def test_get_entity_path_success(self, test_client: TestClient, auth_headers):
        """Test finding path between entities"""
        headers = auth_headers({"email": "path@example.com", "first_name": "Entity", "last_name": "Path"})

        path_params = {
            "source_entity_id": str(uuid.uuid4()),
            "target_entity_id": str(uuid.uuid4()),
            "max_path_length": 5,
            "include_weights": True
        }

        response = test_client.get(
            "/api/v1/graph/path",
            params=path_params,
            headers=headers
        )

        assert response.status_code == 200
        response_data = response.json()

        # Verify path structure
        assert "path_found" in response_data
        assert "path_length" in response_data
        assert "entities" in response_data
        assert "relationships" in response_data
        assert "total_weight" in response_data

        if response_data["path_found"]:
            assert len(response_data["entities"]) > 0
            assert len(response_data["relationships"]) >= 0

    def test_get_entity_neighbors_success(self, test_client: TestClient, auth_headers):
        """Test getting entity neighbors"""
        headers = auth_headers({"email": "neighbors@example.com", "first_name": "Entity", "last_name": "Neighbors"})

        neighbor_params = {
            "entity_id": str(uuid.uuid4()),
            "max_neighbors": 20,
            "relationship_types": ["works_for", "collaborates_with"],
            "include_metadata": True
        }

        response = test_client.get(
            "/api/v1/graph/entities/neighbors",
            params=neighbor_params,
            headers=headers
        )

        assert response.status_code == 200
        response_data = response.json()

        # Verify neighbors structure
        assert "neighbors" in response_data
        assert "total_count" in response_data
        assert isinstance(response_data["neighbors"], list)

        if response_data["neighbors"]:
            first_neighbor = response_data["neighbors"][0]
            assert "entity" in first_neighbor
            assert "relationship" in first_neighbor
            assert "weight" in first_neighbor

    def test_get_similar_entities_success(self, test_client: TestClient, auth_headers):
        """Test finding similar entities"""
        headers = auth_headers({"email": "similar@example.com", "first_name": "Similar", "last_name": "Entities"})

        similar_params = {
            "entity_id": str(uuid.uuid4()),
            "similarity_threshold": 0.5,
            "max_results": 10,
            "similarity_metrics": ["jaccard", "cosine"]
        }

        response = test_client.get(
            "/api/v1/graph/entities/similar",
            params=similar_params,
            headers=headers
        )

        assert response.status_code == 200
        response_data = response.json()

        # Verify similar entities structure
        assert "similar_entities" in response_data
        assert isinstance(response_data["similar_entities"], list)

        if response_data["similar_entities"]:
            first_similar = response_data["similar_entities"][0]
            assert "entity" in first_similar
            assert "similarity_score" in first_similar
            assert "similarity_metrics" in first_similar
            assert 0 <= first_similar["similarity_score"] <= 1

    def test_get_graph_clusters_success(self, test_client: TestClient, auth_headers):
        """Test graph clustering analysis"""
        headers = auth_headers({"email": "clusters@example.com", "first_name": "Graph", "last_name": "Clusters"})

        cluster_params = {
            "algorithm": "louvain",
            "min_cluster_size": 3,
            "max_clusters": 10
        }

        response = test_client.get(
            "/api/v1/graph/clusters",
            params=cluster_params,
            headers=headers
        )

        assert response.status_code == 200
        response_data = response.json()

        # Verify clusters structure
        assert "clusters" in response_data
        assert "total_clusters" in response_data
        assert "modularity_score" in response_data
        assert isinstance(response_data["clusters"], list)

        if response_data["clusters"]:
            first_cluster = response_data["clusters"][0]
            assert "cluster_id" in first_cluster
            assert "entities" in first_cluster
            assert "size" in first_cluster
            assert "density" in first_cluster


@pytest.mark.integration
@pytest.mark.knowledge_graph
@pytest.mark.performance
class TestKnowledgeGraphPerformance:
    """Performance tests for knowledge graph functionality"""

    def test_entity_search_performance(self, test_client: TestClient, auth_headers, performance_tracker):
        """Test entity search performance"""
        headers = auth_headers({"email": "perfentity@example.com", "first_name": "Perf", "last_name": "Entity"})

        search_params = {
            "query": "machine learning",
            "entity_types": ["person", "organization"],
            "limit": 20
        }

        performance_tracker.start_timer("entity_search")

        response = test_client.get(
            "/api/v1/graph/entities",
            params=search_params,
            headers=headers
        )

        duration = performance_tracker.end_timer("entity_search")

        assert response.status_code == 200
        assert duration < 2.0  # Entity search should be fast

    def test_relationship_search_performance(self, test_client: TestClient, auth_headers, performance_tracker):
        """Test relationship search performance"""
        headers = auth_headers({"email": "perfrel@example.com", "first_name": "Perf", "last_name": "Relation"})

        search_params = {
            "entity_id": str(uuid.uuid4()),
            "direction": "both",
            "limit": 30
        }

        performance_tracker.start_timer("relationship_search")

        response = test_client.get(
            "/api/v1/graph/relationships",
            params=search_params,
            headers=headers
        )

        duration = performance_tracker.end_timer("relationship_search")

        assert response.status_code == 200
        assert duration < 3.0  # Relationship search should be reasonably fast

    def test_graph_visualization_performance(self, test_client: TestClient, auth_headers, performance_tracker):
        """Test graph visualization performance"""
        headers = auth_headers({"email": "perfviz@example.com", "first_name": "Perf", "last_name": "Viz"})

        viz_params = {
            "center_entity_id": str(uuid.uuid4()),
            "max_depth": 3,
            "max_nodes": 50,
            "layout_algorithm": "force_directed"
        }

        performance_tracker.start_timer("graph_visualization")

        response = test_client.get(
            "/api/v1/graph/visualize",
            params=viz_params,
            headers=headers
        )

        duration = performance_tracker.end_timer("graph_visualization")

        assert response.status_code == 200
        assert duration < 5.0  # Graph visualization might take longer but should be reasonable

    def test_concurrent_graph_queries_performance(self, test_client: TestClient, auth_headers, performance_tracker):
        """Test concurrent graph queries performance"""
        import threading
        import queue
        import time

        headers = auth_headers({"email": "perfconcurrent@example.com", "first_name": "Perf", "last_name": "Concurrent"})

        results = queue.Queue()

        def query_graph(query_type):
            """Perform a graph query in a separate thread"""
            if query_type == "entities":
                params = {
                    "query": "artificial intelligence",
                    "limit": 10
                }
                endpoint = "/api/v1/graph/entities"
            elif query_type == "relationships":
                params = {
                    "entity_id": str(uuid.uuid4()),
                    "limit": 10
                }
                endpoint = "/api/v1/graph/relationships"
            else:  # visualization
                params = {
                    "center_entity_id": str(uuid.uuid4()),
                    "max_nodes": 20
                }
                endpoint = "/api/v1/graph/visualize"

            start_time = time.time()

            response = test_client.get(
                endpoint,
                params=params,
                headers=headers
            )

            duration = time.time() - start_time
            results.put((response.status_code, duration, query_type))

        # Start concurrent queries
        threads = []
        query_types = ["entities", "relationships", "visualization"]

        performance_tracker.start_timer("concurrent_graph_queries")

        for query_type in query_types * 2:  # 2 of each type
            thread = threading.Thread(target=query_graph, args=(query_type,))
            threads.append(thread)
            thread.start()

        # Wait for all queries to complete
        for thread in threads:
            thread.join()

        total_duration = performance_tracker.end_timer("concurrent_graph_queries")

        # Collect results
        successful_queries = 0
        query_durations = []

        while not results.empty():
            status, duration, query_type = results.get()
            if status == 200:
                successful_queries += 1
                query_durations.append(duration)

        assert successful_queries >= 5  # At least 5 out of 6 should succeed
        assert len(query_durations) > 0

        avg_query_time = sum(query_durations) / len(query_durations)
        assert avg_query_time < 4.0  # Average query time should be reasonable


@pytest.mark.integration
@pytest.mark.knowledge_graph
class TestKnowledgeGraphIntegration:
    """Integration tests for knowledge graph workflows"""

    def test_entity_to_relationship_workflow(self, test_client: TestClient, auth_headers):
        """Test workflow from entity search to relationship exploration"""
        headers = auth_headers({"email": "workflow@example.com", "first_name": "Graph", "last_name": "Workflow"})

        # Step 1: Search for entities
        entity_params = {
            "query": "research",
            "entity_types": ["person"],
            "limit": 1
        }

        entity_response = test_client.get(
            "/api/v1/graph/entities",
            params=entity_params,
            headers=headers
        )

        assert entity_response.status_code == 200
        entity_data = entity_response.json()

        if entity_data["entities"]:
            entity_id = entity_data["entities"][0]["id"]

            # Step 2: Get relationships for this entity
            rel_params = {
                "entity_id": entity_id,
                "direction": "both",
                "limit": 10
            }

            rel_response = test_client.get(
                "/api/v1/graph/relationships",
                params=rel_params,
                headers=headers
            )

            assert rel_response.status_code == 200
            rel_data = rel_response.json()

            # Step 3: Get graph visualization centered on this entity
            viz_params = {
                "center_entity_id": entity_id,
                "max_depth": 2,
                "max_nodes": 20
            }

            viz_response = test_client.get(
                "/api/v1/graph/visualize",
                params=viz_params,
                headers=headers
            )

            assert viz_response.status_code == 200
            viz_data = viz_response.json()

            # Verify visualization includes our entity
            entity_ids = [node["id"] for node in viz_data["nodes"]]
            assert entity_id in entity_ids

    def test_comprehensive_graph_analysis(self, test_client: TestClient, auth_headers):
        """Test comprehensive graph analysis workflow"""
        headers = auth_headers({"email": "analysis@example.com", "first_name": "Graph", "last_name": "Analysis"})

        # Step 1: Get graph statistics
        stats_response = test_client.get(
            "/api/v1/graph/statistics",
            headers=headers
        )

        assert stats_response.status_code == 200
        stats_data = stats_response.json()

        # Step 2: Search for entities of different types
        entity_types = ["person", "organization", "technology"]
        found_entities = []

        for entity_type in entity_types:
            params = {
                "query": "test",
                "entity_types": [entity_type],
                "limit": 5
            }

            response = test_client.get(
                "/api/v1/graph/entities",
                params=params,
                headers=headers
            )

            assert response.status_code == 200
            data = response.json()
            found_entities.extend(data["entities"])

        # Step 3: If we found entities, analyze their connections
        if found_entities:
            # Pick the first entity for deeper analysis
            entity_id = found_entities[0]["id"]

            # Get neighbors
            neighbor_params = {
                "entity_id": entity_id,
                "max_neighbors": 10
            }

            neighbor_response = test_client.get(
                "/api/v1/graph/entities/neighbors",
                params=neighbor_params,
                headers=headers
            )

            assert neighbor_response.status_code == 200

            # Find similar entities
            similar_params = {
                "entity_id": entity_id,
                "max_results": 5
            }

            similar_response = test_client.get(
                "/api/v1/graph/entities/similar",
                params=similar_params,
                headers=headers
            )

            assert similar_response.status_code == 200

        # Step 4: Get clustering information
        cluster_params = {
            "algorithm": "louvain",
            "min_cluster_size": 2
        }

        cluster_response = test_client.get(
            "/api/v1/graph/clusters",
            params=cluster_params,
            headers=headers
        )

        assert cluster_response.status_code == 200
        cluster_data = cluster_response.json()

        # Verify clustering results
        assert "clusters" in cluster_data
        assert "total_clusters" in cluster_data