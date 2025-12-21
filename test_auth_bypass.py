#!/usr/bin/env python3
"""Test script to bypass authentication and trigger extraction directly"""

import sys
import os
sys.path.append('/Users/goodwiinz/development/RAG_system/backend')

import asyncio
from src.api.arxiv_local import LocalExtractionRequest, extract_features_from_local_pdfs
from fastapi import BackgroundTasks
from unittest.mock import Mock

# Create a mock user for testing
mock_user = {
    "id": "test-user-123",
    "email": "test@example.com",
    "is_active": True,
    "is_superuser": False
}

# Create background tasks
background_tasks = BackgroundTasks()

# Create extraction request
request = LocalExtractionRequest(
    paper_ids=None,  # Process all files
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

async def test_extraction():
    """Test extraction with mock user"""
    try:
        print("Starting extraction with mock authentication...")
        print(f"Request: update_knowledge_graph={request.update_knowledge_graph}")

        # Call the extraction function with mock user
        result = await extract_features_from_local_pdfs(
            request=request,
            background_tasks=background_tasks,
            current_user=mock_user
        )

        print(f"✅ Extraction completed!")
        print(f"   Total files found: {result.total_files_found}")
        print(f"   Processed count: {result.processed_count}")
        print(f"   Status: {result.status}")

        # Wait a bit for background tasks to complete
        print("\nWaiting 5 seconds for background tasks...")
        await asyncio.sleep(5)

        # Check graph state
        print("\nChecking knowledge graph state...")
        from src.services.knowledge_graph_service import KnowledgeGraphService

        kg_service = KnowledgeGraphService()

        # Count document entities
        docs = kg_service.search_entities(
            query="ArXiv Paper",
            entity_types=None,
            limit=100
        )

        print(f"Found {len(docs)} document entities in knowledge graph")

        if docs:
            print("Recent documents:")
            for doc in docs[:5]:
                print(f"   - {doc.name[:50]}...")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

# Run the test
asyncio.run(test_extraction())