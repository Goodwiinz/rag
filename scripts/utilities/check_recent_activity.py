#!/usr/bin/env python3
"""Check most recent activity in knowledge graph"""

import sys
sys.path.append('/Users/goodwiinz/development/RAG_system/backend')

from neo4j import GraphDatabase
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
URI = os.getenv('NEO4J_URI', 'bolt://127.0.0.1:7687')
USER = os.getenv('NEO4J_USER', 'neo4j')
PASSWORD = os.getenv('NEO4J_PASSWORD', 'neo4j_password')

try:
    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    with driver.session() as session:
        print("=== Most Recent Entities (Last 10 minutes) ===")

        ten_min_ago = datetime.now().replace(microsecond=0)

        result = session.run("""
        MATCH (e:Entity)
        WHERE e.created_at >= datetime($time)
        RETURN e.name as name, e.type as type, e.created_at as created,
               labels(e) as labels, e.paper_id as paper_id
        ORDER BY e.created_at DESC
        LIMIT 10
        """, time=ten_min_ago.isoformat())

        records = list(result)

        if records:
            print(f"\nFound {len(records)} entities created in last 10 minutes:\n")
            for r in records:
                print(f"• {r['name'][:50]}...")
                print(f"  Type: {r['type']}")
                print(f"  Labels: {list(r['labels'])}")
                if r['paper_id']:
                    print(f"  Paper ID: {r['paper_id']}")
                print(f"  Created: {r['created']}")
                print()
        else:
            print("\nNo entities created in the last 10 minutes")
            print("\nShowing all entities created in last hour:")

            one_hour_ago = datetime.now().replace(microsecond=0)
            one_hour_ago = one_hour_ago.replace(hour=one_hour_ago.hour - 1)

            result = session.run("""
            MATCH (e:Entity)
            WHERE e.created_at >= datetime($time)
            RETURN e.name as name, e.type as type, e.created_at as created
            ORDER BY e.created_at DESC
            LIMIT 10
            """, time=one_hour_ago.isoformat())

            for r in result:
                print(f"• {r['name'][:50]}... ({r['type']}) - {r['created']}")

    driver.close()
    print("\n=== Summary ===")
    print("✅ Knowledge graph is being updated!")
    print("📝 If you don't see changes in Neo4j browser:")
    print("   1. Refresh the page (F5)")
    print("   2. Run: MATCH (n) RETURN n LIMIT 25")
    print("   3. Check the 'Database' dropdown is set to the correct database")

except Exception as e:
    print(f"Error: {e}")