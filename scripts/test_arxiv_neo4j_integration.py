#!/usr/bin/env python3
"""
Test ArXiv to Neo4j Integration
"""

import sys
import asyncio
from pathlib import Path
import json

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent / "backend"))

async def test_neo4j_integration():
    """Test arXiv papers being stored in Neo4j"""
    print("=" * 60)
    print("ArXiv to Neo4j Integration Test")
    print("=" * 60)

    # Import services
    try:
        from src.services.arxiv_kg_integration import ArXivKnowledgeGraphIntegration
        from src.services.knowledge_graph_service import KnowledgeGraphService
        print("✓ Services imported successfully")
    except Exception as e:
        print(f"✗ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # Test Neo4j connection
    print("\n" + "-" * 40)
    print("Test 1: Neo4j Connection")
    print("-" * 40)

    try:
        kg_service = KnowledgeGraphService()
        print(f"✓ Connected to Neo4j at {kg_service.uri}")

        # Get some basic stats
        with kg_service.get_session() as session:
            result = session.run("MATCH (n) RETURN count(n) as node_count")
            count = result.single()['node_count']
            print(f"✓ Current node count in Neo4j: {count}")
    except Exception as e:
        print(f"✗ Neo4j connection failed: {e}")
        return

    # Test ArXiv integration with KG
    print("\n" + "-" * 40)
    print("Test 2: Process ArXiv Papers with KG")
    print("-" * 40)

    try:
        async with ArXivKnowledgeGraphIntegration() as kg_integration:
            print(f"✓ KG Integration initialized")
            print(f"✓ KG Service available: {kg_integration.kg_service is not None}")

            # Search for a paper
            papers = []
            async with kg_integration.arxiv_service as arxiv:
                papers = await arxiv.search_papers(
                    query="transformer architecture",
                    max_results=1
                )

            if papers:
                paper = papers[0]
                print(f"\nProcessing paper: {paper['title'][:50]}...")

                # Process with KG integration
                result = await kg_integration.process_paper_kg_integration(paper)

                if result:
                    print(f"✓ Paper processed successfully")
                    print(f"  Entities extracted: {len(result.get('entities', []))}")
                    print(f"  Relationships: {len(result.get('relationships', []))}")
                    print(f"  KG Updated: {result.get('kg_updated', False)}")
                else:
                    print("✗ Paper processing failed")

    except Exception as e:
        print(f"✗ Processing failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # Verify data in Neo4j
    print("\n" + "-" * 40)
    print("Test 3: Verify Data in Neo4j")
    print("-" * 40)

    try:
        with kg_service.get_session() as session:
            # Check for new entities
            result = session.run("""
                MATCH (e:Entity)
                WHERE e.metadata CONTAINS 'arxiv_category'
                RETURN count(e) as arxiv_entities
            """)
            arxiv_count = result.single()['arxiv_entities']
            print(f"✓ ArXiv entities in Neo4j: {arxiv_count}")

            # Show sample entities
            result = session.run("""
                MATCH (e:Entity)
                WHERE e.metadata CONTAINS 'arxiv_category'
                RETURN e.name as name, e.type as type, labels(e) as labels
                LIMIT 5
            """)
            print("\nSample entities:")
            for record in result:
                print(f"  - {record['name']} (type: {record['type']}, labels: {record['labels']})")

            # Check for relationships
            result = session.run("""
                MATCH ()-[r]->()
                WHERE r.metadata CONTAINS 'paper_id'
                RETURN count(r) as arxiv_relationships
            """)
            rel_count = result.single()['arxiv_relationships']
            print(f"\n✓ ArXiv relationships: {rel_count}")

    except Exception as e:
        print(f"✗ Verification failed: {e}")

    # Manual entity creation test
    print("\n" + "-" * 40)
    print("Test 4: Manual Entity Creation")
    print("-" * 40)

    try:
        from src.models.graph import CreateEntityRequest, EntityType, ExtractionMethod

        # Create a test entity
        request = CreateEntityRequest(
            name="Attention Mechanism",
            entity_type=EntityType.CONCEPT,
            confidence_score=0.95,
            extraction_method=ExtractionMethod.MANUAL,
            metadata={
                'source': 'test',
                'arxiv_category': 'cs.AI'
            }
        )

        response = kg_service.create_entity(request)
        print(f"✓ Created test entity with ID: {response.id}")

        # Create another entity
        request2 = CreateEntityRequest(
            name="Transformer Architecture",
            entity_type=EntityType.CONCEPT,
            confidence_score=0.95,
            extraction_method=ExtractionMethod.MANUAL
        )
        response2 = kg_service.create_entity(request2)
        print(f"✓ Created test entity with ID: {response2.id}")

        # Create relationship between them
        from src.models.graph import CreateRelationshipRequest, RelationshipType

        rel_request = CreateRelationshipRequest(
            source_entity_id=response.id,
            target_entity_id=response2.id,
            relationship_type=RelationshipType.RELATED_TO,
            confidence_score=0.9,
            metadata={
                'relationship_type': 'includes',
                'source': 'test'
            }
        )

        rel_response = kg_service.create_relationship(rel_request)
        print(f"✓ Created relationship with ID: {rel_response.id}")

    except Exception as e:
        print(f"✗ Manual creation failed: {e}")
        import traceback
        traceback.print_exc()

    # Final count
    print("\n" + "-" * 40)
    print("Test 5: Final Neo4j Statistics")
    print("-" * 40)

    try:
        with kg_service.get_session() as session:
            # Total counts
            result = session.run("MATCH (n) RETURN count(n) as total_nodes")
            total_nodes = result.single()['total_nodes']

            result = session.run("MATCH ()-[r]->() RETURN count(r) as total_relationships")
            total_rels = result.single()['total_relationships']

            print(f"✓ Total nodes: {total_nodes}")
            print(f"✓ Total relationships: {total_rels}")

            # ArXiv specific
            result = session.run("""
                MATCH (e:Entity)
                WHERE e.metadata CONTAINS 'arxiv'
                RETURN count(e) as arxiv_nodes
            """)
            if result.peek():
                arxiv_nodes = result.single()['arxiv_nodes']
                print(f"✓ ArXiv-related nodes: {arxiv_nodes}")

    except Exception as e:
        print(f"✗ Statistics failed: {e}")

    print("\n" + "=" * 60)
    print("Test Complete!")
    print("=" * 60)
    print("\nTo view the data in Neo4j Browser:")
    print("1. Open http://localhost:7474")
    print("2. Run query: MATCH (n:Entity) WHERE n.metadata CONTAINS 'arxiv' RETURN n")
    print("3. Or run: MATCH (e:Entity)-[r]->(f:Entity) RETURN e, r, f LIMIT 25")

if __name__ == "__main__":
    asyncio.run(test_neo4j_integration())