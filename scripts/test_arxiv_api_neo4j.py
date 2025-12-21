#!/usr/bin/env python3
"""
Test ArXiv API with Neo4j storage
"""

import requests
import json
import time

def test_arxiv_api():
    """Test arXiv API endpoints"""

    # API base URL
    base_url = "http://localhost:8000"

    print("=" * 60)
    print("ArXiv API Neo4j Integration Test")
    print("=" * 60)

    # First login to get token
    print("\n1. Authenticating...")
    login_data = {
        "email": "admin@multimodal-rag.com",
        "password": "admin123"
    }

    try:
        response = requests.post(f"{base_url}/api/v1/auth/login", json=login_data)
        if response.status_code == 200:
            token = response.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            print("✓ Authentication successful")
        else:
            print(f"✗ Authentication failed: {response.text}")
            return
    except Exception as e:
        print(f"✗ Connection error: {e}")
        print("Make sure the backend is running: docker-compose -f docker-compose.development.yml up backend")
        return

    # Test bulk ingestion with KG
    print("\n2. Bulk ingesting arXiv papers with knowledge graph...")

    bulk_data = {
        "query": "quantum computing",
        "max_results": 5,
        "categories": ["quant-ph"],
        "create_kg_entries": True
    }

    try:
        response = requests.post(
            f"{base_url}/api/v1/arxiv/kg/bulk-ingest",
            json=bulk_data,
            headers=headers
        )

        if response.status_code == 200:
            result = response.json()
            print(f"✓ Bulk ingestion successful")
            print(f"  Papers found: {result.get('papers_found', 0)}")
            print(f"  Papers ingested: {result.get('papers_ingested', 0)}")
            print(f"  KG entries created: {result.get('kg_entries_created', 0)}")
        else:
            print(f"✗ Bulk ingestion failed: {response.text}")
    except Exception as e:
        print(f"✗ Error: {e}")

    # Wait a moment for processing
    time.sleep(2)

    # Check KG statistics
    print("\n3. Checking knowledge graph statistics...")

    try:
        response = requests.get(
            f"{base_url}/api/v1/arxiv/kg/stats",
            headers=headers
        )

        if response.status_code == 200:
            result = response.json()
            stats = result.get('statistics', {})
            print(f"✓ Retrieved statistics")
            print(f"  ArXiv papers processed: {stats.get('arxiv_papers_processed', 0)}")
            print(f"  Unique authors: {stats.get('unique_authors', 0)}")
            print(f"  Research concepts: {stats.get('research_concepts', 0)}")
            print(f"  Total relationships: {stats.get('total_relationships', 0)}")
        else:
            print(f"✗ Failed to get stats: {response.text}")
    except Exception as e:
        print(f"✗ Error: {e}")

    # Search for a paper to create subgraph
    print("\n4. Searching for a specific paper...")

    try:
        response = requests.post(
            f"{base_url}/api/v1/arxiv/search",
            json={
                "query": "artificial intelligence machine learning",
                "max_results": 1
            },
            headers=headers
        )

        if response.status_code == 200:
            papers = response.json().get('papers', [])
            if papers:
                paper = papers[0]
                paper_id = paper.get('id', '').split('/')[-1]
                print(f"✓ Found paper: {paper.get('title', 'Unknown')[:50]}...")
                print(f"  Paper ID: {paper_id}")

                # Create subgraph for this paper
                print("\n5. Creating knowledge graph subgraph...")

                subgraph_data = {
                    "paper_id": paper_id,
                    "depth": 2
                }

                response = requests.post(
                    f"{base_url}/api/v1/arxiv/kg/subgraph",
                    json=subgraph_data,
                    headers=headers
                )

                if response.status_code == 200:
                    subgraph = response.json()
                    print(f"✓ Subgraph created")
                    print(f"  Entities: {len(subgraph.get('subgraph', {}).get('entities', []))}")
                    print(f"  Relationships: {len(subgraph.get('subgraph', {}).get('relationships', []))}")
                else:
                    print(f"✗ Subgraph creation failed: {response.text}")
            else:
                print("✗ No papers found")
        else:
            print(f"✗ Search failed: {response.text}")
    except Exception as e:
        print(f"✗ Error: {e}")

    # Test entity details
    print("\n6. Testing entity details lookup...")

    try:
        response = requests.get(
            f"{base_url}/api/v1/arxiv/kg/entity/Machine%20Learning",
            headers=headers
        )

        if response.status_code == 200:
            entity = response.json().get('entity', {})
            print(f"✓ Found entity: {entity.get('name', 'Unknown')}")
            print(f"  Type: {entity.get('type', 'Unknown')}")
            print(f"  Properties: {list(entity.get('properties', {}).keys())}")
        else:
            print(f"✓ Entity not found (expected if no ML papers processed)")
    except Exception as e:
        print(f"✗ Error: {e}")

    # Analyze trends
    print("\n7. Analyzing research trends...")

    trends_data = {
        "category": "cs.AI",
        "days": 7
    }

    try:
        response = requests.post(
            f"{base_url}/api/v1/arxiv/kg/analyze-trends",
            json=trends_data,
            headers=headers
        )

        if response.status_code == 200:
            analysis = response.json().get('analysis', {})
            print(f"✓ Trend analysis complete")
            print(f"  Total papers analyzed: {analysis.get('total_papers', 0)}")

            trending = analysis.get('trending_topics', [])[:5]
            if trending:
                print("  Top trending topics:")
                for topic in trending:
                    print(f"    - {topic.get('term')}: {topic.get('count', 0)} mentions")
        else:
            print(f"✗ Trend analysis failed: {response.text}")
    except Exception as e:
        print(f"✗ Error: {e}")

    print("\n" + "=" * 60)
    print("Test Complete!")
    print("=" * 60)
    print("\nTo view data in Neo4j Browser:")
    print("1. Open http://localhost:7474")
    print("2. Run query: MATCH (n) RETURN n LIMIT 25")
    print("3. Or for entities only: MATCH (e:Entity) RETURN e")
    print("4. For relationships: MATCH (e1)-[r]->(e2) RETURN e1, r, e2 LIMIT 10")

if __name__ == "__main__":
    test_arxiv_api()