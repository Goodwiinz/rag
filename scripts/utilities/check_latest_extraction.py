#!/usr/bin/env python3
"""Check the latest extraction results despite connection errors"""

import sys
sys.path.append('/Users/goodwiinz/development/RAG_system/backend')

from src.services.knowledge_graph_service import KnowledgeGraphService
from src.models.graph import EntityType

try:
    kg = KnowledgeGraphService()

    # Search for the latest paper
    print("=== Checking Latest Extraction ===\n")

    # Search for the specific paper
    docs = kg.search_entities(
        query="In Pursuit of Pixel Supervision",
        entity_types=[EntityType.DOCUMENT],
        limit=5
    )

    if docs:
        print(f"✅ Found '{docs[0].name}' in the knowledge graph!")
        print(f"   ID: {docs[0].id}")
        print(f"   Created: {docs[0].created_at}")
        print(f"   Paper ID: {docs[0].metadata.get('paper_id') if docs[0].metadata else 'N/A'}")
    else:
        print("❌ Paper not found in KG")

    # Get all recent documents
    print("\n=== Recent Documents (Last 10) ===")
    all_docs = kg.search_entities(
        query="",
        entity_types=[EntityType.DOCUMENT],
        limit=50
    )

    recent_docs = sorted(all_docs, key=lambda x: x.created_at, reverse=True)[:10]

    for i, doc in enumerate(recent_docs, 1):
        created = str(doc.created_at) if doc.created_at else "Unknown"
        print(f"{i}. {doc.name[:50]}...")
        print(f"   Created: {created}")
        if doc.metadata and doc.metadata.get('source'):
            print(f"   Source: {doc.metadata['source']}")

    # Count total
    print(f"\nTotal DOCUMENT entities: {len([d for d in all_docs if d.entity_type == EntityType.DOCUMENT])}")

except Exception as e:
    print(f"Connection error: {e}")
    print("\nThis means the KG service connection is temporarily broken.")
    print("The extraction might have succeeded, but we can't verify it right now.")
    print("\nTo fix:")
    print("1. Restart the backend service")
    print("2. Or wait a minute and try again")
    print("3. The connection should auto-recover")