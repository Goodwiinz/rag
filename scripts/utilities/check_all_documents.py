#!/usr/bin/env python3
"""Check all documents in the knowledge graph"""

import sys
sys.path.append('/Users/goodwiinz/development/RAG_system/backend')

from src.services.knowledge_graph_service import KnowledgeGraphService
from src.models.graph import EntityType

kg = KnowledgeGraphService()

# Get all documents
print("=== All DOCUMENT entities in Knowledge Graph ===")
docs = kg.search_entities(
    query="",  # Empty query to get all
    entity_types=[EntityType.DOCUMENT],
    limit=100
)

print(f"\nFound {len(docs)} DOCUMENT entities:\n")
for i, doc in enumerate(docs, 1):
    print(f"{i}. {doc.name}")
    print(f"   ID: {doc.id}")
    print(f"   Created: {doc.created_at}")
    if doc.metadata:
        if doc.metadata.get('paper_id'):
            print(f"   Paper ID: {doc.metadata['paper_id']}")
        if doc.metadata.get('source'):
            print(f"   Source: {doc.metadata['source']}")
        if doc.metadata.get('title'):
            print(f"   Title: {doc.metadata['title']}")
    print()