#!/usr/bin/env python3
"""Detailed check of graph entities"""

import sys
sys.path.append('/Users/goodwiinz/development/RAG_system/backend')

from src.services.knowledge_graph_service import KnowledgeGraphService
from src.models.graph import EntityType

kg_service = KnowledgeGraphService()

# Count all entities by type
print("=== Entity Count by Type ===")
for entity_type in EntityType:
    count = len(kg_service.search_entities(
        query="",
        entity_types=[entity_type],
        limit=1000
    ))
    print(f"{entity_type.value}: {count} entities")

# Get recent documents
print("\n=== Recent Documents (Last 10) ===")
docs = kg_service.search_entities(
    query="ArXiv Paper",
    entity_types=[EntityType.DOCUMENT],
    limit=10
)

for i, doc in enumerate(docs, 1):
    print(f"{i}. {doc.name}")
    if doc.metadata and doc.metadata.get('paper_id'):
        print(f"   Paper ID: {doc.metadata['paper_id']}")

# Check relationships
print("\n=== Relationship Statistics ===")
try:
    from neo4j import GraphDatabase
    import os
    from dotenv import load_dotenv

    load_dotenv()
    URI = os.getenv('NEO4J_URI', 'bolt://127.0.0.1:7687')
    USER = os.getenv('NEO4J_USER', 'neo4j')
    PASSWORD = os.getenv('NEO4J_PASSWORD', 'neo4j_password')

    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    with driver.session() as session:
        # Count relationships
        result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
        rel_count = result.single()["count"]
        print(f"Total relationships: {rel_count}")

        # Count relationships by type
        result = session.run("MATCH ()-[r]->() RETURN type(r) as type, count(r) as count ORDER BY count DESC")
        for record in result:
            print(f"   {record['type']}: {record['count']}")

    driver.close()
except Exception as e:
    print(f"Error: {e}")