#!/usr/bin/env python3
"""Test direct KG update with extracted data"""

import sys
import os
sys.path.append('/Users/goodwiinz/development/RAG_system/backend')

import asyncio
from src.api.arxiv_local import _post_process_extraction
from src.api.arxiv_local import LocalExtractionRequest

# Create a test result similar to what you're getting
test_result = {
    "paper_id": "2512.15708v1",
    "filename": "2512.15708v1.pdf",
    "extraction_status": "completed",
    "features": {
        "metadata": {
            "title": "Multi-View Foundation Models",
            "author": "Leo Segre",
            "subject": "Computer Science"
        },
        "topics": [
            "distributed systems",
            "graph theory",
            "robotics",
            "computer vision",
            "algorithms",
            "statistics",
            "machine learning"
        ],
        "keyphrases": [
            "view",
            "multi",
            "features",
            "model",
            "foundation",
            "consistency"
        ],
        "summary": "Multi-View Foundation Models paper about view consistency and feature extraction.",
        "extracted_text": "Multi-View Foundation Models Leo Segre Or Hirschorn Shai Avidan Tel Aviv University"
    }
}

# Create request object
request = LocalExtractionRequest(
    paper_ids=None,
    extract_entities=True,
    extract_topics=True,
    extract_citations=False,
    extract_keyphrases=True,
    extract_summaries=True,
    process_full_content=True,
    update_knowledge_graph=True,
    extract_images=False,
    extract_tables=False,
    extract_references=True
)

async def test_direct_update():
    """Test the post-processing directly"""
    print(f"Testing direct KG update for {test_result['paper_id']}...")
    print(f"Topics: {test_result['features']['topics']}")
    print(f"Keyphrases: {test_result['features']['keyphrases']}")

    try:
        # Call the post-processing function directly
        await _post_process_extraction(test_result, request)
        print("✅ Post-processing completed successfully!")

        # Check the KG
        from src.services.knowledge_graph_service import KnowledgeGraphService
        kg = KnowledgeGraphService()

        # Search for the document
        docs = kg.search_entities("Multi-View Foundation Models", limit=10)
        print(f"\nFound {len(docs)} documents in KG")

        # Search for topics
        for topic in test_result['features']['topics'][:3]:
            concepts = kg.search_entities(topic, limit=5)
            if concepts:
                print(f"\nFound {len(concepts)} entities for topic '{topic}':")
                for c in concepts[:2]:
                    print(f"   - {c.name} (ID: {c.id})")

        # Count total DOCUMENT entities
        all_docs = kg.search_entities("ArXiv Paper", entity_types=None, limit=100)
        doc_count = sum(1 for d in all_docs if d.entity_type.value == "DOCUMENT")
        print(f"\nTotal DOCUMENT entities in KG: {doc_count}")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

# Run the test
asyncio.run(test_direct_update())