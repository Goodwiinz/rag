#!/usr/bin/env python3
"""
Check the current state of the knowledge graph - documents and entities
"""

import sys
import os
from neo4j import GraphDatabase

# Add backend to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))
from src.core.config import settings

def check_knowledge_graph():
    """Check the current state of the knowledge graph"""
    driver = None
    try:
        driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )

        with driver.session() as session:
            print("Checking node labels in the database...")

            # Get all node labels
            result = session.run("CALL db.labels() YIELD label RETURN label")
            labels = [record["label"] for record in result]
            print(f"\nFound labels: {labels}")

            # Get count of each node type
            print("\nNode counts by label:")
            for label in labels:
                result = session.run(f"MATCH (n:{label}) RETURN count(n) as count")
                count = result.single()["count"]
                print(f"  {label}: {count}")

            # Check entities with extraction methods
            print("\nChecking entities with extraction methods...")
            result = session.run("""
                MATCH (e:Entity)
                WHERE e.extraction_method IS NOT NULL
                RETURN e.extraction_method as extraction_method,
                       count(*) as count
                ORDER BY count DESC
            """)

            extraction_methods = []
            for record in result:
                extraction_methods.append(f"{record['extraction_method']}: {record['count']}")

            if extraction_methods:
                print("  Extraction methods found:")
                for method in extraction_methods:
                    print(f"    - {method}")
            else:
                print("  No entities with extraction_method property found")

            # Check if there are any document-like nodes
            print("\nChecking for document-like nodes...")
            doc_like_labels = [l for l in labels if 'doc' in l.lower() or 'paper' in l.lower() or 'arxiv' in l.lower()]

            if doc_like_labels:
                print(f"  Document-like labels found: {doc_like_labels}")
                for label in doc_like_labels:
                    result = session.run(f"MATCH (n:{label}) RETURN n.title as title, n.id as id LIMIT 5")
                    records = list(result)
                    if records:
                        print(f"\n  Sample {label} nodes:")
                        for record in records:
                            print(f"    - ID: {record['id']}, Title: {record['title']}")
            else:
                print("  No document-like labels found")

            # Check relationships
            print("\nChecking relationship types...")
            result = session.run("CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType")
            rel_types = [record["relationshipType"] for record in result]
            print(f"  Relationship types: {rel_types}")

            # Check if entities are connected to anything that might be a document
            print("\nChecking if entities have connections to other nodes...")
            result = session.run("""
                MATCH (e:Entity)-[r]->(n)
                WHERE NOT n:Entity
                RETURN DISTINCT labels(n) as connected_labels, count(*) as count
                ORDER BY count DESC
            """)

            connections = list(result)
            if connections:
                print("  Entities are connected to:")
                for record in connections:
                    print(f"    - {record['connected_labels']}: {record['count']} connections")
            else:
                print("  No connections found from entities to non-Entity nodes")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if driver:
            driver.close()

if __name__ == "__main__":
    print("="*80)
    print("KNOWLEDGE GRAPH STATE CHECKER")
    print("="*80)
    check_knowledge_graph()