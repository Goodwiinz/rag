#!/usr/bin/env python3
"""
Script to reclassify nodes labeled as OTHER to their proper labels
based on entity_type_original in their metadata
"""
import sys
sys.path.append('/Users/goodwiinz/development/RAG_system/backend')

from neo4j import GraphDatabase
import os
import json
import re
from dotenv import load_dotenv

def parse_metadata(metadata_str):
    """Parse metadata string into dictionary"""
    try:
        # Remove quotes if wrapped in them
        if metadata_str.startswith("'") and metadata_str.endswith("'"):
            metadata_str = metadata_str[1:-1]

        # Replace single quotes with double quotes for valid JSON
        metadata_str = metadata_str.replace("'", '"')

        return json.loads(metadata_str)
    except:
        # Fallback to regex-based extraction
        metadata = {}
        patterns = {
            'entity_type_original': r'entity_type_original\':\s*\'([^\']+)\'',
            'source': r'source\':\s*\'([^\']+)\'',
            'paper_id': r'paper_id\':\s*\'([^\']+)\'',
            'paper_title': r'paper_title\':\s*\'([^\']+)\''
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, metadata_str)
            if match:
                metadata[key] = match.group(1)

        return metadata

def reclassify_entities():
    """Reclassify entities from OTHER to their proper types"""

    print("=== Reclassifying OTHER Entities ===\n")

    load_dotenv()

    # Get Neo4j connection details
    URI = os.getenv('NEO4J_URI', 'bolt://127.0.0.1:7687')
    USER = os.getenv('NEO4J_USER', 'neo4j')
    PASSWORD = os.getenv('NEO4J_PASSWORD', 'neo4j')

    try:
        driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))

        with driver.session() as session:
            # Get all OTHER nodes
            query = "MATCH (n:OTHER) RETURN n"
            result = session.run(query)

            reclassified = {}
            failed = 0

            for record in result:
                node = record['n']
                node_id = node.id
                metadata_str = node.get('metadata', '{}')

                # Parse metadata
                metadata = parse_metadata(metadata_str)
                original_type = metadata.get('entity_type_original', 'other')

                # Skip if original_type is 'other' or missing
                if original_type.lower() == 'other' or original_type == 'other\'':
                    continue

                # Clean up the type
                original_type = original_type.rstrip('\'').strip()

                # Map to proper label
                label_mapping = {
                    'model': 'MODEL',
                    'dataset': 'DATASET',
                    'task': 'TASK',
                    'method': 'METHOD',
                    'technique': 'TECHNIQUE',
                    'algorithm': 'ALGORITHM',
                    'metric': 'METRIC',
                    'result': 'RESULT',
                    'comparison': 'COMPARISON',
                    'concept': 'CONCEPT',
                    'entity': 'ENTITY',
                    'organization': 'ORGANIZATION',
                    'person': 'PERSON',
                    'location': 'LOCATION',
                    'event': 'EVENT',
                    'date': 'DATE',
                    'product': 'PRODUCT',
                    'technology': 'TECHNOLOGY',
                    'research': 'RESEARCH',
                    'paper': 'PAPER',
                    'publication': 'PUBLICATION'
                }

                new_label = label_mapping.get(original_type.lower(), original_type.upper())

                # Update node labels
                try:
                    # Remove OTHER label and add new label
                    update_query = """
                    MATCH (n:OTHER)
                    WHERE id(n) = $node_id
                    REMOVE n:OTHER
                    SET n:$new_label
                    RETURN n
                    """

                    session.run(update_query, node_id=node_id, new_label=new_label)

                    # Track reclassification
                    if new_label not in reclassified:
                        reclassified[new_label] = 0
                    reclassified[new_label] += 1

                    print(f"✓ Reclassified node {node_id}: {node.get('name', 'Unknown')} -> {new_label}")

                except Exception as e:
                    print(f"✗ Failed to reclassify node {node_id}: {e}")
                    failed += 1

            # Print summary
            print("\n" + "=" * 60)
            print("📊 Reclassification Summary:")
            print(f"   • Total nodes processed: {sum(reclassified.values()) + failed}")
            print(f"   • Successfully reclassified: {sum(reclassified.values())}")
            print(f"   • Failed: {failed}")
            print(f"\n   • By type:")
            for label, count in sorted(reclassified.items(), key=lambda x: x[1], reverse=True):
                print(f"      - {label}: {count}")

            # Check remaining OTHER nodes
            remaining_query = "MATCH (n:OTHER) RETURN count(n) as count"
            remaining = session.run(remaining_query).single()["count"]
            print(f"\n   • Remaining OTHER nodes: {remaining}")

            # Get entity distribution
            print("\n" + "=" * 60)
            print("🏷️  Current Entity Distribution:")

            label_query = """
            MATCH (n:Entity)
            WITH labels(n) as labels, count(n) as count
            UNWIND labels as label
            WITH label, count(*) as total
            WHERE label <> 'Entity'
            RETURN label, total
            ORDER BY total DESC
            """

            label_result = session.run(label_query)
            for record in label_result:
                print(f"   • {record['label']}: {record['total']}")

        driver.close()
        print("\n✅ Reclassification completed!")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

def main():
    reclassify_entities()

if __name__ == "__main__":
    main()