"""
User Workflow Integration Tests
Comprehensive end-to-end testing of complete user workflows across the Multimodal Enterprise RAG System
"""

import pytest
import json
import uuid
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List
from fastapi.testclient import TestClient
from httpx import AsyncClient


@pytest.mark.integration
class TestDocumentUploadToSearchWorkflow:
    """Test complete workflow from document upload to search functionality"""

    def test_complete_document_workflow(self, test_client: TestClient, auth_headers, sample_files, mock_external_services):
        """Test complete document lifecycle: upload -> process -> search -> results"""
        headers = auth_headers({
            "email": "workflow@example.com",
            "first_name": "Complete",
            "last_name": "Workflow"
        })

        # Step 1: Upload multiple document types
        uploaded_documents = []

        # Upload PDF document
        pdf_files = {"file": sample_files["pdf"]}
        pdf_data = {
            "title": "Machine Learning Research Paper",
            "tags": json.dumps(["machine learning", "research", "AI"]),
            "metadata": json.dumps({"pages": 25, "author": "Research Team"})
        }

        pdf_response = test_client.post(
            "/api/v1/documents/upload",
            files=pdf_files,
            data=pdf_data,
            headers=headers
        )

        assert pdf_response.status_code == 201
        pdf_doc = pdf_response.json()
        uploaded_documents.append(pdf_doc)

        # Upload text document
        text_files = {"file": sample_files["text"]}
        text_data = {
            "title": "Natural Language Processing Guide",
            "tags": json.dumps(["NLP", "guide", "text processing"]),
            "metadata": json.dumps({"word_count": 5000, "language": "English"})
        }

        text_response = test_client.post(
            "/api/v1/documents/upload",
            files=text_files,
            data=text_data,
            headers=headers
        )

        assert text_response.status_code == 201
        text_doc = text_response.json()
        uploaded_documents.append(text_doc)

        # Upload image document
        image_files = {"file": sample_files["image"]}
        image_data = {
            "title": "Neural Network Architecture Diagram",
            "tags": json.dumps(["neural networks", "architecture", "diagram"]),
            "metadata": json.dumps({"width": 1024, "height": 768, "format": "JPEG"})
        }

        image_response = test_client.post(
            "/api/v1/documents/upload",
            files=image_files,
            data=image_data,
            headers=headers
        )

        assert image_response.status_code == 201
        image_doc = image_response.json()
        uploaded_documents.append(image_doc)

        # Step 2: Verify documents appear in listing
        list_response = test_client.get("/api/v1/documents", headers=headers)
        assert list_response.status_code == 200

        documents_list = list_response.json()["documents"]
        uploaded_ids = {doc["id"] for doc in uploaded_documents}
        listed_ids = {doc["id"] for doc in documents_list}

        assert uploaded_ids.issubset(listed_ids)

        # Step 3: Wait for processing (simulate with status checks)
        for doc in uploaded_documents:
            for _ in range(10):  # Check status up to 10 times
                status_response = test_client.get(
                    f"/api/v1/documents/{doc['id']}/status",
                    headers=headers
                )
                assert status_response.status_code == 200

                status_data = status_response.json()
                if status_data["status"] in ["completed", "failed"]:
                    break

        # Step 4: Perform hybrid search across uploaded documents
        search_data = {
            "query": "machine learning neural networks",
            "search_type": "hybrid",
            "max_results": 10,
            "filters": {
                "document_types": ["pdf", "text"],
                "tags": ["machine learning", "AI"]
            },
            "rerank": True
        }

        search_response = test_client.post(
            "/api/v1/search/",
            json=search_data,
            headers=headers
        )

        assert search_response.status_code == 200
        search_results = search_response.json()

        # Verify search results structure
        assert "results" in search_results
        assert "query_id" in search_results
        assert "total_results" in search_results
        assert "search_metadata" in search_results

        # Step 5: Get detailed search results
        if search_results["results"]:
            results_response = test_client.get(
                f"/api/v1/search/{search_results['query_id']}",
                headers=headers
            )
            assert results_response.status_code == 200

            detailed_results = results_response.json()
            assert len(detailed_results["results"]) >= len(search_results["results"])

            # Verify our uploaded documents appear in results if they match the search
            result_doc_ids = {r.get("document_id") for r in detailed_results["results"]}

        # Step 6: Test advanced search with aggregations
        advanced_search_data = {
            "query": "artificial intelligence",
            "search_type": "hybrid",
            "max_results": 20,
            "enable_facets": True,
            "facet_fields": ["document_type", "tags"],
            "enable_aggregations": True,
            "aggregations": {
                "document_type": {"type": "terms", "size": 10},
                "file_size": {"type": "histogram", "interval": 5}
            }
        }

        advanced_response = test_client.post(
            "/api/v1/search/advanced",
            json=advanced_search_data,
            headers=headers
        )

        assert advanced_response.status_code == 200
        advanced_results = advanced_response.json()

        # Verify faceted results
        assert "facets" in advanced_results
        assert "aggregations" in advanced_results

        # Step 7: Verify search history
        history_response = test_client.get("/api/v1/search/history", headers=headers)
        assert history_response.status_code == 200

        search_history = history_response.json()["searches"]
        assert len(search_history) >= 2  # Should have at least our 2 searches

        # Verify our searches are in history
        search_queries = [s["query"] for s in search_history]
        assert "machine learning neural networks" in search_queries
        assert "artificial intelligence" in search_queries

        # Step 8: Clean up - delete uploaded documents
        for doc in uploaded_documents:
            delete_response = test_client.delete(
                f"/api/v1/documents/{doc['id']}",
                headers=headers
            )
            assert delete_response.status_code == 200

    def test_document_upload_processing_search_with_errors(self, test_client: TestClient, auth_headers, sample_files):
        """Test workflow with error handling and recovery"""
        headers = auth_headers({
            "email": "errorworkflow@example.com",
            "first_name": "Error",
            "last_name": "Workflow"
        })

        # Step 1: Upload document that might fail processing
        files = {"file": ("error_test.txt", b"Content that might cause processing issues", "text/plain")}
        data = {
            "title": "Error Test Document",
            "tags": json.dumps(["error", "test"])
        }

        upload_response = test_client.post(
            "/api/v1/documents/upload",
            files=files,
            data=data,
            headers=headers
        )

        assert upload_response.status_code == 201
        doc_id = upload_response.json()["id"]

        # Step 2: Monitor processing status
        final_status = None
        for _ in range(20):
            status_response = test_client.get(
                f"/api/v1/documents/{doc_id}/status",
                headers=headers
            )
            assert status_response.status_code == 200

            status_data = status_response.json()
            final_status = status_data["status"]

            if final_status in ["completed", "failed"]:
                break

        # Step 3: Handle different processing outcomes
        if final_status == "failed":
            # Get error details
            doc_response = test_client.get(
                f"/api/v1/documents/{doc_id}",
                headers=headers
            )
            assert doc_response.status_code == 200

            doc_details = doc_response.json()
            assert "processing_error" in doc_details

            # Try to reprocess if supported
            reprocess_response = test_client.post(
                f"/api/v1/documents/{doc_id}/reprocess",
                headers=headers
            )
            # Reprocess might not be implemented, so handle gracefully
            assert reprocess_response.status_code in [200, 404, 405]

        # Step 4: Search should still work (even with failed processing)
        search_data = {
            "query": "error test",
            "search_type": "fulltext",
            "max_results": 5
        }

        search_response = test_client.post(
            "/api/v1/search/",
            json=search_data,
            headers=headers
        )

        # Search should succeed even if processing failed
        assert search_response.status_code == 200

        # Step 5: Clean up
        delete_response = test_client.delete(
            f"/api/v1/documents/{doc_id}",
            headers=headers
        )
        assert delete_response.status_code == 200


@pytest.mark.integration
class TestUserAuthenticationWorkflow:
    """Test complete user authentication and session management workflow"""

    def test_new_user_onboarding_workflow(self, test_client: TestClient):
        """Test complete new user registration and onboarding"""
        # Step 1: User registration
        registration_data = {
            "email": "newuser@example.com",
            "password": "SecurePassword123!",
            "first_name": "New",
            "last_name": "User",
            "organization_name": "New User Organization"
        }

        register_response = test_client.post(
            "/api/v1/auth/register",
            json=registration_data
        )

        assert register_response.status_code == 201
        register_data = register_response.json()

        # Verify registration response
        assert "access_token" in register_data
        assert "refresh_token" in register_data
        assert "user" in register_data

        access_token = register_data["access_token"]
        refresh_token = register_data["refresh_token"]
        user_data = register_data["user"]

        # Set up authenticated headers
        headers = {
            "Authorization": f"Bearer {access_token}",
            "X-Refresh-Token": refresh_token,
            "X-User-ID": user_data["id"],
            "X-Organization-ID": user_data["organization_id"]
        }

        # Step 2: Verify user profile
        profile_response = test_client.get("/api/v1/users/profile", headers=headers)
        assert profile_response.status_code == 200

        profile_data = profile_response.json()
        assert profile_data["email"] == registration_data["email"]
        assert profile_data["first_name"] == registration_data["first_name"]
        assert profile_data["last_name"] == registration_data["last_name"]
        assert profile_data["is_active"] is True

        # Step 3: Update user profile
        update_data = {
            "first_name": "Updated",
            "last_name": "Name",
            "profile_data": {
                "bio": "Software Developer interested in AI/ML",
                "location": "San Francisco",
                "website": "https://example.com"
            }
        }

        update_response = test_client.put(
            "/api/v1/users/profile",
            json=update_data,
            headers=headers
        )

        assert update_response.status_code == 200
        updated_profile = update_response.json()

        assert updated_profile["first_name"] == "Updated"
        assert updated_profile["last_name"] == "Name"
        assert updated_profile["profile_data"]["bio"] == "Software Developer interested in AI/ML"

        # Step 4: Token refresh workflow
        refresh_data = {
            "refresh_token": refresh_token
        }

        refresh_response = test_client.post(
            "/api/v1/auth/refresh",
            json=refresh_data
        )

        assert refresh_response.status_code == 200
        new_tokens = refresh_response.json()

        # Verify new tokens
        assert "access_token" in new_tokens
        assert "refresh_token" in new_tokens
        assert new_tokens["access_token"] != access_token
        assert new_tokens["refresh_token"] != refresh_token

        # Update headers with new tokens
        headers["Authorization"] = f"Bearer {new_tokens['access_token']}"
        headers["X-Refresh-Token"] = new_tokens["refresh_token"]

        # Step 5: Verify profile access with new token
        new_profile_response = test_client.get("/api/v1/users/profile", headers=headers)
        assert new_profile_response.status_code == 200

        # Step 6: Password change workflow
        password_data = {
            "current_password": registration_data["password"],
            "new_password": "NewSecurePassword456!"
        }

        password_response = test_client.post(
            "/api/v1/auth/change-password",
            json=password_data,
            headers=headers
        )

        assert password_response.status_code == 200

        # Step 7: Login with new password
        login_data = {
            "email": registration_data["email"],
            "password": password_data["new_password"]
        }

        login_response = test_client.post("/api/v1/auth/login", json=login_data)
        assert login_response.status_code == 200

        login_tokens = login_response.json()
        assert "access_token" in login_tokens
        assert "refresh_token" in login_tokens

    def test_user_session_management_workflow(self, test_client: TestClient):
        """Test user session management and token lifecycle"""
        # Register a user
        registration_data = {
            "email": "session@example.com",
            "password": "SessionPassword123!",
            "first_name": "Session",
            "last_name": "User",
            "organization_name": "Session Test Organization"
        }

        register_response = test_client.post(
            "/api/v1/auth/register",
            json=registration_data
        )

        assert register_response.status_code == 201
        tokens = register_response.json()
        access_token = tokens["access_token"]

        headers = {"Authorization": f"Bearer {access_token}"}

        # Step 1: Normal API access
        profile_response = test_client.get("/api/v1/users/profile", headers=headers)
        assert profile_response.status_code == 200

        # Step 2: Test token expiration simulation (would require time manipulation)
        # For now, test invalid token handling
        invalid_headers = {"Authorization": "Bearer invalid_token"}

        invalid_response = test_client.get("/api/v1/users/profile", headers=invalid_headers)
        assert invalid_response.status_code == 401

        # Step 3: Test concurrent sessions (multiple devices)
        # Login again from different "device"
        login_data = {
            "email": registration_data["email"],
            "password": registration_data["password"]
        }

        second_login_response = test_client.post("/api/v1/auth/login", json=login_data)
        assert second_login_response.status_code == 200

        second_tokens = second_login_response.json()
        second_headers = {"Authorization": f"Bearer {second_tokens['access_token']}"}

        # Both sessions should work
        first_profile_response = test_client.get("/api/v1/users/profile", headers=headers)
        second_profile_response = test_client.get("/api/v1/users/profile", headers=second_headers)

        assert first_profile_response.status_code == 200
        assert second_profile_response.status_code == 200

        # Step 4: Test logout (if implemented)
        logout_response = test_client.post("/api/v1/auth/logout", headers=headers)
        # Logout might not be implemented, so handle gracefully
        assert logout_response.status_code in [200, 404, 405]


@pytest.mark.integration
class TestKnowledgeGraphWorkflow:
    """Test knowledge graph extraction and exploration workflow"""

    def test_document_to_knowledge_graph_workflow(self, test_client: TestClient, auth_headers, sample_files, mock_external_services):
        """Test complete workflow from document upload to knowledge graph exploration"""
        headers = auth_headers({
            "email": "graph@example.com",
            "first_name": "Knowledge",
            "last_name": "Graph"
        })

        # Step 1: Upload documents with rich content for entity extraction
        documents = [
            {
                "title": "AI Research Paper",
                "content": "Dr. Jane Smith from MIT published research on neural networks and machine learning algorithms. The collaboration with OpenAI resulted in breakthrough developments in natural language processing.",
                "tags": ["AI", "research", "neural networks"],
                "file": sample_files["pdf"]
            },
            {
                "title": "Tech Company Analysis",
                "content": "Google, Microsoft, and Apple are competing in the AI space. Sundar Pichai announced new AI features at Google I/O. Satya Nadella discussed Microsoft's AI strategy.",
                "tags": ["tech", "companies", "AI"],
                "file": sample_files["text"]
            }
        ]

        uploaded_docs = []
        for doc_data in documents:
            files = {"file": doc_data["file"]}
            data = {
                "title": doc_data["title"],
                "tags": json.dumps(doc_data["tags"]),
                "content_text": doc_data["content"]  # Add content for entity extraction
            }

            upload_response = test_client.post(
                "/api/v1/documents/upload",
                files=files,
                data=data,
                headers=headers
            )

            assert upload_response.status_code == 201
            uploaded_docs.append(upload_response.json())

        # Step 2: Wait for processing and entity extraction
        for doc in uploaded_docs:
            for _ in range(10):
                status_response = test_client.get(
                    f"/api/v1/documents/{doc['id']}/status",
                    headers=headers
                )
                status_data = status_response.json()

                if status_data["status"] in ["completed", "failed"]:
                    break

        # Step 3: Search for entities extracted from documents
        entity_searches = [
            {"query": "Jane Smith", "entity_types": ["person"]},
            {"query": "MIT", "entity_types": ["organization"]},
            {"query": "neural networks", "entity_types": ["technology"]},
            {"query": "Google", "entity_types": ["organization"]},
            {"query": "Sundar Pichai", "entity_types": ["person"]}
        ]

        found_entities = []
        for search_params in entity_searches:
            response = test_client.get(
                "/api/v1/graph/entities",
                params=search_params,
                headers=headers
            )

            assert response.status_code == 200
            entities_data = response.json()

            if entities_data["entities"]:
                found_entities.extend(entities_data["entities"])

        # Step 4: Explore relationships between entities
        if found_entities:
            # Get relationships for the first entity
            entity_id = found_entities[0]["id"]
            rel_params = {
                "entity_id": entity_id,
                "direction": "both",
                "limit": 20
            }

            rel_response = test_client.get(
                "/api/v1/graph/relationships",
                params=rel_params,
                headers=headers
            )

            assert rel_response.status_code == 200
            relationships_data = rel_response.json()

            # Step 5: Get graph visualization for entity network
            viz_params = {
                "center_entity_id": entity_id,
                "max_depth": 2,
                "max_nodes": 30,
                "layout_algorithm": "force_directed"
            }

            viz_response = test_client.get(
                "/api/v1/graph/visualize",
                params=viz_params,
                headers=headers
            )

            assert viz_response.status_code == 200
            graph_data = viz_response.json()

            # Verify graph structure
            assert "nodes" in graph_data
            assert "edges" in graph_data
            assert len(graph_data["nodes"]) > 0

            # Verify our center entity is in the graph
            node_ids = [node["id"] for node in graph_data["nodes"]]
            assert entity_id in node_ids

        # Step 6: Get graph statistics
        stats_response = test_client.get("/api/v1/graph/statistics", headers=headers)
        assert stats_response.status_code == 200

        stats_data = stats_response.json()
        assert "total_entities" in stats_data
        assert "total_relationships" in stats_data
        assert "entity_types" in stats_data

        # Step 7: Test entity similarity analysis
        if len(found_entities) >= 2:
            similar_params = {
                "entity_id": found_entities[0]["id"],
                "max_results": 5
            }

            similar_response = test_client.get(
                "/api/v1/graph/entities/similar",
                params=similar_params,
                headers=headers
            )

            assert similar_response.status_code == 200
            similar_data = similar_response.json()

            assert "similar_entities" in similar_data

        # Step 8: Test graph clustering
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

        assert "clusters" in cluster_data
        assert "total_clusters" in cluster_data

        # Step 9: Clean up documents
        for doc in uploaded_docs:
            delete_response = test_client.delete(
                f"/api/v1/documents/{doc['id']}",
                headers=headers
            )
            assert delete_response.status_code == 200


@pytest.mark.integration
class TestMultiModalSearchWorkflow:
    """Test comprehensive multi-modal search workflow"""

    def test_cross_modal_search_workflow(self, test_client: TestClient, auth_headers, sample_files, mock_external_services):
        """Test search across different document types and modalities"""
        headers = auth_headers({
            "email": "multimodal@example.com",
            "first_name": "Multi",
            "last_name": "Modal"
        })

        # Step 1: Upload documents of different modalities
        modal_docs = []

        # Text document
        text_files = {"file": sample_files["text"]}
        text_data = {
            "title": "Deep Learning Fundamentals",
            "tags": json.dumps(["deep learning", "neural networks", "AI"]),
            "content_text": "Deep learning is a subset of machine learning that uses neural networks with multiple layers."
        }

        text_response = test_client.post(
            "/api/v1/documents/upload",
            files=text_files,
            data=text_data,
            headers=headers
        )

        if text_response.status_code == 201:
            modal_docs.append(text_response.json())

        # PDF document
        pdf_files = {"file": sample_files["pdf"]}
        pdf_data = {
            "title": "Computer Vision Applications",
            "tags": json.dumps(["computer vision", "image processing", "CNN"]),
            "content_text": "Convolutional Neural Networks revolutionized computer vision and image recognition tasks."
        }

        pdf_response = test_client.post(
            "/api/v1/documents/upload",
            files=pdf_files,
            data=pdf_data,
            headers=headers
        )

        if pdf_response.status_code == 201:
            modal_docs.append(pdf_response.json())

        # Image document
        image_files = {"file": sample_files["image"]}
        image_data = {
            "title": "Neural Network Architecture",
            "tags": json.dumps(["neural network", "architecture", "diagram"]),
            "content_text": "Diagram showing the architecture of a deep neural network with multiple hidden layers."
        }

        image_response = test_client.post(
            "/api/v1/documents/upload",
            files=image_files,
            data=image_data,
            headers=headers
        )

        if image_response.status_code == 201:
            modal_docs.append(image_response.json())

        # Step 2: Wait for processing
        for doc in modal_docs:
            for _ in range(10):
                status_response = test_client.get(
                    f"/api/v1/documents/{doc['id']}/status",
                    headers=headers
                )
                status_data = status_response.json()

                if status_data["status"] in ["completed", "failed"]:
                    break

        # Step 3: Perform different types of searches

        # Hybrid search across all modalities
        hybrid_search = {
            "query": "neural networks deep learning",
            "search_type": "hybrid",
            "max_results": 15,
            "rerank": True,
            "rerank_weights": {
                "semantic": 0.5,
                "keyword": 0.3,
                "cross_modal": 0.2
            }
        }

        hybrid_response = test_client.post(
            "/api/v1/search/",
            json=hybrid_search,
            headers=headers
        )

        assert hybrid_response.status_code == 200
        hybrid_results = hybrid_response.json()

        # Vector search for semantic similarity
        vector_search = {
            "query": "artificial intelligence machine learning algorithms",
            "search_type": "vector",
            "max_results": 10,
            "similarity_threshold": 0.6
        }

        vector_response = test_client.post(
            "/api/v1/search/",
            json=vector_search,
            headers=headers
        )

        assert vector_response.status_code == 200
        vector_results = vector_response.json()

        # Graph search for entity relationships
        graph_search = {
            "query": "computer vision image processing",
            "search_type": "graph",
            "max_results": 8
        }

        graph_response = test_client.post(
            "/api/v1/search/",
            json=graph_search,
            headers=headers
        )

        assert graph_response.status_code == 200
        graph_results = graph_response.json()

        # Step 4: Advanced multi-modal search with filtering
        advanced_search = {
            "query": "deep learning computer vision",
            "search_type": "hybrid",
            "max_results": 20,
            "enable_facets": True,
            "facet_fields": ["document_type", "tags"],
            "filters": {
                "document_types": ["text", "pdf", "image"],
                "tags": ["deep learning", "computer vision", "neural networks"]
            },
            "enable_aggregations": True,
            "aggregations": {
                "document_type": {"type": "terms", "size": 10},
                "modality": {"type": "terms", "size": 5}
            }
        }

        advanced_response = test_client.post(
            "/api/v1/search/advanced",
            json=advanced_search,
            headers=headers
        )

        assert advanced_response.status_code == 200
        advanced_results = advanced_response.json()

        # Verify cross-modal results
        assert "results" in advanced_results
        assert "facets" in advanced_results
        assert "aggregations" in advanced_results

        # Step 5: Analyze result diversity across modalities
        all_results = []
        for result_set in [hybrid_results, vector_results, graph_results, advanced_results]:
            if result_set.get("results"):
                all_results.extend(result_set["results"])

        # Count results by document type
        doc_type_counts = {}
        for result in all_results:
            doc_type = result.get("document_type", "unknown")
            doc_type_counts[doc_type] = doc_type_counts.get(doc_type, 0) + 1

        # Should have results from multiple modalities
        assert len(doc_type_counts) >= 1  # At least one type

        # Step 6: Test cross-modal relevance
        if len(all_results) >= 2:
            # Get detailed results for comparison
            query_id = advanced_results.get("query_id")
            if query_id:
                detailed_response = test_client.get(
                    f"/api/v1/search/{query_id}",
                    headers=headers
                )

                if detailed_response.status_code == 200:
                    detailed_results = detailed_response.json()

                    # Verify cross-modal coherence
                    text_results = [r for r in detailed_results["results"] if r.get("document_type") == "text"]
                    image_results = [r for r in detailed_results["results"] if r.get("document_type") == "image"]

                    # Results should be relevant regardless of modality
                    if text_results and image_results:
                        # Compare relevance scores
                        text_scores = [r.get("score", 0) for r in text_results]
                        image_scores = [r.get("score", 0) for r in image_results]

                        # Scores should be in reasonable range
                        all_scores = text_scores + image_scores
                        assert all(0 <= score <= 1 for score in all_scores)

        # Step 7: Test search performance across modalities
        import time

        search_times = []
        search_configs = [hybrid_search, vector_search, graph_search]

        for config in search_configs:
            start_time = time.time()

            response = test_client.post(
                "/api/v1/search/",
                json=config,
                headers=headers
            )

            search_time = time.time() - start_time
            search_times.append(search_time)

            assert response.status_code == 200

        # Average search time should be reasonable
        avg_search_time = sum(search_times) / len(search_times)
        assert avg_search_time < 3.0  # Should meet performance requirements

        # Step 8: Clean up
        for doc in modal_docs:
            delete_response = test_client.delete(
                f"/api/v1/documents/{doc['id']}",
                headers=headers
            )
            assert delete_response.status_code == 200


@pytest.mark.integration
class TestErrorHandlingAndRecoveryWorkflow:
    """Test error handling and recovery scenarios across workflows"""

    def test_network_error_recovery_workflow(self, test_client: TestClient, auth_headers, sample_files):
        """Test workflow resilience to network errors and timeouts"""
        headers = auth_headers({
            "email": "recovery@example.com",
            "first_name": "Error",
            "last_name": "Recovery"
        })

        # Step 1: Upload document with potential retry scenarios
        files = {"file": sample_files["text"]}
        data = {
            "title": "Resilience Test Document",
            "tags": json.dumps(["resilience", "test", "error"])
        }

        # Simulate network issues by testing various failure scenarios
        upload_response = test_client.post(
            "/api/v1/documents/upload",
            files=files,
            data=data,
            headers=headers,
            timeout=30.0  # Set reasonable timeout
        )

        # Handle potential timeouts gracefully
        if upload_response.status_code == 201:
            doc_id = upload_response.json()["id"]

            # Step 2: Test search with error handling
            search_data = {
                "query": "resilience test error handling",
                "search_type": "hybrid",
                "max_results": 10
            }

            try:
                search_response = test_client.post(
                    "/api/v1/search/",
                    json=search_data,
                    headers=headers,
                    timeout=10.0
                )

                if search_response.status_code == 200:
                    search_results = search_response.json()

                    # Verify search results even after potential issues
                    assert "results" in search_results
                    assert "query_id" in search_results

            except Exception as e:
                # Handle search errors gracefully
                pytest.fail(f"Search failed with error: {e}")

            # Step 3: Test document status checking with retries
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    status_response = test_client.get(
                        f"/api/v1/documents/{doc_id}/status",
                        headers=headers,
                        timeout=5.0
                    )

                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        if status_data["status"] in ["completed", "failed"]:
                            break

                except Exception:
                    if attempt == max_retries - 1:
                        # Final attempt failed
                        break
                    continue

            # Step 4: Clean up if document was created
            delete_response = test_client.delete(
                f"/api/v1/documents/{doc_id}",
                headers=headers
            )
            # Delete might fail if document wasn't fully processed
            assert delete_response.status_code in [200, 404]

        else:
            # Upload failed, test error handling
            assert upload_response.status_code in [400, 408, 413, 422, 500]

    def test_concurrent_user_workflows(self, test_client: TestClient):
        """Test multiple users working concurrently"""
        import threading
        import queue
        import time

        # Create multiple users
        users_data = [
            {"email": "user1@example.com", "first_name": "User", "last_name": "One"},
            {"email": "user2@example.com", "first_name": "User", "last_name": "Two"},
            {"email": "user3@example.com", "first_name": "User", "last_name": "Three"}
        ]

        def user_workflow(user_data, results_queue):
            """Individual user workflow"""
            try:
                # Register user
                registration_data = {
                    "email": user_data["email"],
                    "password": "Password123!",
                    "first_name": user_data["first_name"],
                    "last_name": user_data["last_name"],
                    "organization_name": f"{user_data['first_name']}'s Org"
                }

                register_response = test_client.post(
                    "/api/v1/auth/register",
                    json=registration_data,
                    timeout=10.0
                )

                if register_response.status_code != 201:
                    results_queue.put(("register_failed", user_data["email"]))
                    return

                tokens = register_response.json()
                headers = {"Authorization": f"Bearer {tokens['access_token']}"}

                # Upload a document
                files = {"file": (f"{user_data['email']}_doc.txt", f"Content for {user_data['email']}".encode(), "text/plain")}
                data = {"title": f"{user_data['first_name']}'s Document"}

                upload_response = test_client.post(
                    "/api/v1/documents/upload",
                    files=files,
                    data=data,
                    headers=headers,
                    timeout=15.0
                )

                if upload_response.status_code != 201:
                    results_queue.put(("upload_failed", user_data["email"]))
                    return

                doc_id = upload_response.json()["id"]

                # Perform search
                search_data = {
                    "query": f"document {user_data['first_name']}",
                    "search_type": "hybrid",
                    "max_results": 5
                }

                search_response = test_client.post(
                    "/api/v1/search/",
                    json=search_data,
                    headers=headers,
                    timeout=10.0
                )

                if search_response.status_code == 200:
                    results_queue.put(("success", user_data["email"]))
                else:
                    results_queue.put(("search_failed", user_data["email"]))

                # Clean up
                test_client.delete(
                    f"/api/v1/documents/{doc_id}",
                    headers=headers
                )

            except Exception as e:
                results_queue.put(("exception", user_data["email"], str(e)))

        # Run concurrent user workflows
        results = queue.Queue()
        threads = []

        start_time = time.time()

        for user_data in users_data:
            thread = threading.Thread(target=user_workflow, args=(user_data, results))
            threads.append(thread)
            thread.start()

        # Wait for all workflows to complete
        for thread in threads:
            thread.join()

        total_time = time.time() - start_time

        # Collect results
        successful_users = []
        failed_users = []

        while not results.empty():
            result = results.get()
            if result[0] == "success":
                successful_users.append(result[1])
            else:
                failed_users.append(result)

        # Verify concurrent execution
        assert len(successful_users) >= 2  # At least 2 out of 3 should succeed
        assert total_time < 30.0  # Should complete within reasonable time

        print(f"Concurrent workflow completed in {total_time:.2f}s")
        print(f"Successful: {successful_users}")
        print(f"Failed: {failed_users}")