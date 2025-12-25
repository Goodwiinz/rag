#!/usr/bin/env python3
"""
Check how metadata is stored in the database
"""

import sys
import os
from neo4j import GraphDatabase

# Add backend to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))
from src.core.config import settings

def check_metadata_format():
    """Check how metadata is stored in entities"""
    driver = None
    try:
        driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )

        with driver.session() as session:
            print("Checking metadata format in entities...")

            # Check the type of metadata field
            result = session.run("""
                MATCH (e:Entity)
                WHERE e.metadata IS NOT NULL AND e.name = 'Huang'
                RETURN e.metadata as metadata, e.name as name
                LIMIT 3
            """)

            for record in result:
                metadata = record['metadata']
                name = record['name']
                print(f"\nEntity: {name}")
                print(f"Metadata type: {type(metadata)}")
                print(f"Metadata value: {metadata}")

                # Try to access paper_id
                if isinstance(metadata, dict):
                    print(f"  Paper ID: {metadata.get('paper_id', 'Not found')}")
                    print(f"  Paper title: {metadata.get('paper_title', 'Not found')}")
                elif isinstance(metadata, str):
                    import json
                    try:
                        # Replace single quotes with double quotes for valid JSON
                        metadata_json = metadata.replace("'", '"')
                        metadata_dict = json.loads(metadata_json)
                        print(f"  Paper ID: {metadata_dict.get('paper_id', 'Not found')}")
                        print(f"  Paper title: {metadata_dict.get('paper_title', 'Not found')}")
                    except json.JSONDecodeError:
                        print(f"  Could not parse metadata as JSON")
                else:
                    print(f"  Metadata type: {type(metadata)}")

            # Now check for all entities with paper_id in metadata
            print("\n\nSearching for entities with paper_id in metadata...")
            result = session.run("""
                MATCH (e:Entity)
                WHERE e.metadata IS NOT NULL AND e.metadata CONTAINS 'paper_id'
                RETURN e.name as name, e.metadata as metadata
                LIMIT 20
            """)

            papers_found = {}
            for record in result:
                metadata_str = record['metadata']
                name = record['name']

                # Parse metadata string
                import json
                try:
                    # Replace single quotes with double quotes for valid JSON
                    metadata_json = metadata_str.replace("'", '"')
                    metadata = json.loads(metadata_json)

                    paper_id = metadata.get('paper_id')
                    if paper_id:
                        if paper_id not in papers_found:
                            papers_found[paper_id] = {
                                'title': metadata.get('paper_title', 'Unknown'),
                                'category': metadata.get('arxiv_category', ''),
                                'entities': []
                            }
                        papers_found[paper_id]['entities'].append(name)
                except json.JSONDecodeError:
                    continue

            print(f"\nFound {len(papers_found)} papers with entities:")
            for paper_id, info in papers_found.items():
                print(f"\nPaper ID: {paper_id}")
                print(f"  Title: {info['title']}")
                print(f"  Entities: {info['entities'][:5]}{'...' if len(info['entities']) > 5 else ''}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if driver:
            driver.close()

if __name__ == "__main__":
    print("="*80)
    print("METADATA FORMAT CHECKER")
    print("="*80)
    check_metadata_format()