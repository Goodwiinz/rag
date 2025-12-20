#!/usr/bin/env python3
import sys
sys.path.append('/Users/goodwiinz/development/RAG_system/backend')

from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

# Get Neo4j connection details
URI = os.getenv('NEO4J_URI', 'bolt://127.0.0.1:7687')
USER = os.getenv('NEO4J_USER', 'neo4j')
PASSWORD = os.getenv('NEO4J_PASSWORD', 'neo4j_password')

try:
    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))

    with driver.session() as session:
        print("=== Checking Existing Documents ===\n")

        # Check all documents
        result = session.run("""
            MATCH (doc:Entity:DOCUMENT)
            RETURN doc.name as name, doc.id as id, doc.source as source,
                   doc.created_at as created, labels(doc) as labels
            ORDER BY doc.created_at DESC
            LIMIT 20
        """)

        print(f"Found {len(list(result))} DOCUMENT entities:")
        print("-" * 60)

        # Reset result iterator
        result = session.run("""
            MATCH (doc:Entity:DOCUMENT)
            RETURN doc.name as name, doc.id as id, doc.source as source,
                   doc.created_at as created, labels(doc) as labels
            ORDER BY doc.created_at DESC
            LIMIT 20
        """)

        for record in result:
            print(f"Name: {record['name']}")
            print(f"ID: {record['id']}")
            print(f"Source: {record.get('source', 'Not set')}")
            print(f"Created: {record.get('created', 'Unknown')}")
            print(f"Labels: {record['labels']}")
            print("-" * 60)

        # Check for any entities with paper_id
        print("\n=== Entities with paper_id ===\n")
        result = session.run("""
            MATCH (n)
            WHERE n.paper_id IS NOT NULL
            RETURN n.name as name, n.paper_id as paper_id, labels(n) as labels
        """)

        for record in result:
            print(f"Name: {record['name']}")
            print(f"Paper ID: {record['paper_id']}")
            print(f"Labels: {record['labels']}")
            print("-" * 60)

        # Check relationships
        print("\n=== Relationship Statistics ===\n")
        result = session.run("""
            MATCH ()-[r]->()
            RETURN type(r) as rel_type, count(r) as count
            ORDER BY count DESC
        """)

        for record in result:
            print(f"{record['rel_type']}: {record['count']} relationships")

    driver.close()

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()