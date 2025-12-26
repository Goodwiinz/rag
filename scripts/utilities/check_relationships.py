#!/usr/bin/env python3
"""Check relationships in the knowledge graph"""

import sys
sys.path.append('/Users/goodwiinz/development/RAG_system/backend')

from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()
URI = os.getenv('NEO4J_URI', 'bolt://127.0.0.1:7687')
USER = os.getenv('NEO4J_USER', 'neo4j')
PASSWORD = os.getenv('NEO4J_PASSWORD', 'neo4j_password')

try:
    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    with driver.session() as session:
        print("=== Current Relationships ===")

        # Check all relationships
        result = session.run("""
        MATCH (source)-[r]->(target)
        RETURN source.name as source, type(r) as rel_type, target.name as target, r.created_at as created
        ORDER BY r.created_at DESC
        LIMIT 20
        """)

        records = list(result)
        print(f"\nFound {len(records)} relationships:\n")

        for r in records:
            print(f"'{r['source'][:30]}...' --[{r['rel_type']}]--> '{r['target'][:30]}...'")

        if not records:
            print("\n❌ NO RELATIONSHIPS FOUND!")
            print("\nLet's check what entities we have:")

            result = session.run("""
            MATCH (n:Entity)
            WHERE n.paper_id = '2512.15715v1'
            RETURN n.name as name, n.type as type, labels(n) as labels
            LIMIT 10
            """)

            print("\nEntities for paper 2512.15715v1:")
            for r in result:
                print(f"  - {r['name']} ({r['type']}) {list(r['labels'])}")

    driver.close()

except Exception as e:
    print(f"Error: {e}")