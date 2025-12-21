#!/usr/bin/env python3
"""Test ArXiv knowledge graph integration"""

import sys
sys.path.append('/Users/goodwiinz/development/RAG_system/backend')

import asyncio

# Test extraction result
test_extraction = {
    "paper_id": "2512.15708v1",
    "title": "Multi-View Foundation Models",
    "extraction_status": "completed",
    "features": {
        "entities": {
            "entities": [
                {
                    "name": "Multi-View Foundation Models",
                    "type": "DOCUMENT",
                    "properties": {
                        "confidence": 0.9,
                        "paper_id": "2512.15708v1"
                    }
                },
                {
                    "name": "machine learning",
                    "type": "CONCEPT",
                    "properties": {
                        "confidence": 0.8
                    }
                }
            ],
            "relationships": [
                {
                    "source": "Multi-View Foundation Models",
                    "target": "machine learning",
                    "type": "RELATED_TO",
                    "properties": {
                        "confidence": 0.85
                    }
                }
            ]
        }
    }
}

async def test_arxiv_kg():
    """Test ArXiv KG integration"""
    try:
        from src.services.arxiv_kg_integration import ArXivKnowledgeGraphIntegration

        print("Testing ArXiv Knowledge Graph Integration...")

        async with ArXivKnowledgeGraphIntegration() as kg:
            print(f"KG Service initialized: {kg.kg_service}")

            # Test the update function
            from src.api.arxiv_extraction import _update_knowledge_graph_with_extractions

            print("\nUpdating KG with test extraction...")
            await _update_knowledge_graph_with_extractions([test_extraction])

            print("✅ KG update completed!")

            # Check the results
            from src.services.knowledge_graph_service import KnowledgeGraphService
            kg_service = KnowledgeGraphService()

            # Search for the document
            docs = kg_service.search_entities("Multi-View Foundation Models", limit=10)
            print(f"\nFound {len(docs)} documents")

            # Search for concepts
            concepts = kg_service.search_entities("machine learning", limit=10)
            print(f"Found {len(concepts)} concepts")

            # Get total counts
            from src.models.graph import EntityType
            all_docs = kg_service.search_entities("", entity_types=[EntityType.DOCUMENT], limit=1000)
            print(f"\nTotal DOCUMENT entities: {len(all_docs)}")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

# Run the test
asyncio.run(test_arxiv_kg())