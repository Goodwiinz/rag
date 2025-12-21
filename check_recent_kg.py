#!/usr/bin/env python3
"""Check for recent knowledge graph updates"""

import sys
sys.path.append('/Users/goodwiinz/development/RAG_system/backend')

from src.services.knowledge_graph_service import KnowledgeGraphService
from src.models.graph import EntityType

kg = KnowledgeGraphService()

# Search for the specific paper
print("Searching for 'Multi-View Foundation Models'...")
results = kg.search_entities(
    query="Multi-View Foundation Models",
    entity_types=None,
    limit=10
)

if results:
    print(f"✅ Found {len(results)} entities:")
    for r in results:
        print(f"   - {r.name} (Type: {r.entity_type.value})")
        print(f"     ID: {r.id}")
        print(f"     Created: {r.created_at}")
else:
    print("❌ Not found in KG")

# Search for any recent documents
print("\nSearching for recent ArXiv papers...")
docs = kg.search_entities(
    query="ArXiv Paper",
    entity_types=[EntityType.DOCUMENT],
    limit=50
)

print(f"Found {len(docs)} document entities")
if docs:
    print("Most recent:")
    for doc in docs[-5:]:  # Last 5
        created = str(doc.created_at) if doc.created_at else "Unknown"
        print(f"   - {doc.name[:50]}... (Created: {created})")

# Check if any entities were created in the last few minutes
print("\nChecking for very recent entities...")
try:
    from datetime import datetime, timedelta
    import neo4j
    from dotenv import load_dotenv
    import os

    load_dotenv()
    URI = os.getenv('NEO4J_URI', 'bolt://127.0.0.1:7687')
    USER = os.getenv('NEO4J_USER', 'neo4j')
    PASSWORD = os.getenv('NEO4J_PASSWORD', 'neo4j_password')

    driver = neo4j.GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    with driver.session() as session:
        # Get entities created in last 10 minutes
        ten_min_ago = datetime.now() - timedelta(minutes=10)
        query = """
        MATCH (e:Entity)
        WHERE e.created_at >= datetime($time)
        RETURN e.name as name, e.type as type, e.created_at as created
        ORDER BY e.created_at DESC
        LIMIT 20
        """
        result = session.run(query, time=ten_min_ago.isoformat())

        recent = list(result)
        if recent:
            print(f"Found {len(recent)} entities created in last 10 minutes:")
            for r in recent:
                print(f"   - {r['name'][:50]}... ({r['type']})")
        else:
            print("No entities created in last 10 minutes")

    driver.close()
except Exception as e:
    print(f"Error: {e}")