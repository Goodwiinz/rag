#!/usr/bin/env python3
"""
Test ArXiv Knowledge Graph Integration
"""

import sys
import asyncio
from pathlib import Path
import json

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent / "backend"))

async def test_kg_integration():
    """Test the knowledge graph integration"""
    print("=" * 60)
    print("ArXiv Knowledge Graph Integration Test")
    print("=" * 60)

    # Import services
    try:
        from src.services.arxiv_kg_integration import ArXivKnowledgeGraphIntegration
        from src.services.arxiv_service import ArXivIngestionService
        print("✓ Services imported successfully")
    except Exception as e:
        print(f"✗ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # Initialize services
    try:
        kg_integration = ArXivKnowledgeGraphIntegration()
        arxiv_service = ArXivIngestionService()
        print("\n✓ Services initialized")
    except Exception as e:
        print(f"\n✗ Service initialization failed: {e}")
        return

    # Test 1: Search for a recent paper
    print("\n" + "-" * 40)
    print("Test 1: Search for papers")
    print("-" * 40)

    try:
        papers = []
        async with arxiv_service as service:
            papers = await service.search_papers(
                query="transformer architecture attention mechanisms",
                max_results=3
            )

        if papers:
            print(f"✓ Found {len(papers)} papers")
            for i, paper in enumerate(papers[:2], 1):
                print(f"\n{i}. {paper['title']}")
                print(f"   Authors: {', '.join(paper['authors'][:3])}...")
                print(f"   Category: {paper.get('primary_category', 'N/A')}")
                print(f"   Published: {paper.get('published', 'N/A')}")
        else:
            print("✗ No papers found")
            return

    except Exception as e:
        print(f"✗ Search failed: {e}")
        return

    # Test 2: Extract entities from a paper
    print("\n" + "-" * 40)
    print("Test 2: Extract entities and relationships")
    print("-" * 40)

    test_paper = papers[0]

    try:
        entities = await kg_integration._extract_entities_from_paper(test_paper)
        print(f"✓ Extracted {len(entities)} entities:")

        # Group entities by type
        entity_types = {}
        for entity in entities:
            etype = entity['type']
            if etype not in entity_types:
                entity_types[etype] = []
            entity_types[etype].append(entity)

        for etype, entity_list in entity_types.items():
            print(f"\n  {etype.upper()} ({len(entity_list)}):")
            for entity in entity_list[:5]:  # Show first 5
                print(f"    - {entity['text']} (confidence: {entity['confidence']:.2f})")

        relationships = await kg_integration._extract_relationships_from_paper(test_paper)
        print(f"\n✓ Extracted {len(relationships)} relationships:")

        for rel in relationships[:5]:  # Show first 5
            print(f"    - {rel['source']['text']} --[{rel['relation']}]--> {rel['target']['text']}")

    except Exception as e:
        print(f"✗ Entity extraction failed: {e}")
        import traceback
        traceback.print_exc()

    # Test 3: Create knowledge graph subgraph
    print("\n" + "-" * 40)
    print("Test 3: Create knowledge graph subgraph")
    print("-" * 40)

    try:
        paper_id = test_paper['id'].split('/')[-1]  # Extract just the ID part
        subgraph = await kg_integration.create_paper_kg_subgraph(
            paper_id=paper_id,
            depth=1
        )

        if 'error' not in subgraph:
            print(f"✓ Created subgraph for paper {paper_id}")
            print(f"  Entities: {len(subgraph.get('entities', []))}")
            print(f"  Relationships: {len(subgraph.get('relationships', []))}")
            print(f"  Cited papers: {len(subgraph.get('cited_papers', []))}")
        else:
            print(f"✗ Subgraph creation failed: {subgraph['error']}")

    except Exception as e:
        print(f"✗ Subgraph creation error: {e}")

    # Test 4: Analyze research trends
    print("\n" + "-" * 40)
    print("Test 4: Analyze research trends")
    print("-" * 40)

    try:
        trends = await kg_integration.analyze_research_area_trends(
            category="cs.LG",  # Machine Learning
            days=7
        )

        if 'error' not in trends:
            print(f"✓ Analyzed trends for cs.LG (last 7 days)")
            print(f"  Total papers: {trends.get('total_papers', 0)}")

            trending_topics = trends.get('trending_topics', [])[:5]
            if trending_topics:
                print("\n  Top trending topics:")
                for topic in trending_topics:
                    print(f"    - {topic['term']} (count: {topic['count']})")

            collab_analysis = trends.get('author_collaborations', {})
            if collab_analysis.get('total_collaborations', 0) > 0:
                print(f"\n  Total collaborations found: {collab_analysis['total_collaborations']}")

        else:
            print(f"✗ Trend analysis failed: {trends['error']}")

    except Exception as e:
        print(f"✗ Trend analysis error: {e}")

    # Test 5: Author collaboration network
    print("\n" + "-" * 40)
    print("Test 5: Build author collaboration network")
    print("-" * 40)

    if test_paper['authors']:
        test_author = test_paper['authors'][0]  # Use first author

        try:
            network = await kg_integration.get_author_collaboration_network(
                author_name=test_author,
                max_depth=2
            )

            if 'error' not in network:
                print(f"✓ Built collaboration network for {test_author}")
                print(f"  Papers found: {len(network.get('papers', []))}")
                print(f"  Co-authors: {len(network.get('coauthors', set()))}")

                collaborators = network.get('collaborators', {})
                if collaborators:
                    print("\n  Top collaborators:")
                    sorted_collabs = sorted(
                        collaborators.items(),
                        key=lambda x: len(x[1]),
                        reverse=True
                    )[:5]

                    for collaborator, papers_list in sorted_collabs:
                        print(f"    - {collaborator}: {len(papers_list)} papers")

            else:
                print(f"✗ Network building failed: {network['error']}")

        except Exception as e:
            print(f"✗ Network building error: {e}")

    # Test 6: Process paper with full KG integration
    print("\n" + "-" * 40)
    print("Test 6: Process paper with KG integration")
    print("-" * 40)

    try:
        print(f"Processing paper: {test_paper['title'][:50]}...")

        result = await kg_integration.process_paper_kg_integration(test_paper)

        if result:
            print("✓ Paper processed successfully")
            print(f"  Entities extracted: {len(result.get('entities', []))}")
            print(f"  Relationships created: {len(result.get('relationships', []))}")
        else:
            print("✗ Paper processing failed")

    except Exception as e:
        print(f"✗ Paper processing error: {e}")

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    print("\nThe ArXiv Knowledge Graph Integration provides:")
    print("• Entity extraction from papers (authors, concepts, methods, datasets)")
    print("• Relationship detection (citations, authorship, topic relationships)")
    print("• Knowledge graph subgraph creation for specific papers")
    print("• Research trend analysis for categories")
    print("• Author collaboration network building")
    print("• Integration with the main knowledge graph system")

    print("\nTo use these features in the API:")
    print("• POST /api/v1/arxiv/kg/subgraph - Create paper subgraph")
    print("• POST /api/v1/arxiv/kg/author-network - Get collaboration network")
    print("• POST /api/v1/arxiv/kg/analyze-trends - Analyze research trends")
    print("• POST /api/v1/arxiv/kg/bulk-ingest - Bulk ingest with KG integration")
    print("• GET /api/v1/arxiv/kg/entity/{name} - Get entity details")
    print("• GET /api/v1/arxiv/kg/path/{source}/{target} - Find entity paths")
    print("• GET /api/v1/arxiv/kg/stats - Get KG statistics")

if __name__ == "__main__":
    asyncio.run(test_kg_integration())