#!/usr/bin/env python3
"""
Check entity properties and how they might be linked to documents
"""

import sys
import os
from neo4j import GraphDatabase

# Add backend to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))
from src.core.config import settings

def check_entity_properties():
    """Check entity properties and relationships"""
    driver = None
    try:
        driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )

        with driver.session() as session:
            print("Checking Entity properties...")

            # Get all entity properties
            result = session.run("""
                MATCH (e:Entity)
                RETURN DISTINCT keys(e) as all_keys
            """)

            all_keys = set()
            for record in result:
                all_keys.update(record['all_keys'])

            print(f"\nAll Entity properties found: {sorted(all_keys)}")

            # Get sample entities to see their structure
            print("\n\nSample entities:")
            result = session.run("""
                MATCH (e:Entity)
                RETURN e LIMIT 3
            """)

            for i, record in enumerate(result, 1):
                entity = dict(record['e'])
                print(f"\nEntity {i}:")
                for key, value in entity.items():
                    if key == 'metadata' and isinstance(value, str) and len(value) > 100:
                        # Truncate long metadata
                        print(f"  {key}: {value[:100]}...")
                    else:
                        print(f"  {key}: {value}")

            # Check if there's any document reference in metadata
            print("\n\nChecking metadata for document references...")
            result = session.run("""
                MATCH (e:Entity)
                WHERE e.metadata CONTAINS 'document' OR e.metadata CONTAINS 'paper' OR e.metadata CONTAINS 'arxiv'
                RETURN e.name as name, e.extraction_method as method, e.metadata as metadata
                LIMIT 5
            """)

            records = list(result)
            if records:
                print(f"Found {len(records)} entities with document references in metadata:")
                for record in records:
                    print(f"\n  Name: {record['name']}")
                    print(f"  Method: {record['method']}")
                    # Show first 200 chars of metadata
                    metadata = record['metadata']
                    if len(metadata) > 200:
                        metadata = metadata[:200] + "..."
                    print(f"  Metadata: {metadata}")

            # Check relationships between entities
            print("\n\nChecking entity relationships...")
            result = session.run("""
                MATCH (e1:Entity)-[r:RELATED_TO]-(e2:Entity)
                RETURN e1.name as entity1, e1.extraction_method as method1,
                       e2.name as entity2, e2.extraction_method as method2
                LIMIT 5
            """)

            relationships = list(result)
            if relationships:
                print(f"Found {len(relationships)} sample relationships:")
                for record in relationships:
                    print(f"  {record['entity1']} ({record['method1']}) RELATED_TO {record['entity2']} ({record['method2']})")
            else:
                print("No entity relationships found")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if driver:
            driver.close()

if __name__ == "__main__":
    print("="*80)
    print("ENTITY PROPERTY CHECKER")
    print("="*80)
    check_entity_properties()