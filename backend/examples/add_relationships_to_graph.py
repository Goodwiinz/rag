#!/usr/bin/env python3
"""
Add relationships between entities in the knowledge graph

This script demonstrates how to extract and store relationships
between entities to create a richer knowledge graph.
"""

import sys
import os
import re
from typing import List, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.services.knowledge_graph.knowledge_graph_service import knowledge_graph_service
from src.models.graph import CreateRelationshipRequest, RelationshipType


class RelationshipExtractor:
    """Extract relationships from text using pattern matching"""

    def __init__(self):
        # Patterns for common relationships
        self.patterns = {
            RelationshipType.WORKS_FOR: [
                r"(.+?)\s+(?:works for|works at|employed by|employee of)\s+(.+)",
                r"(.+?),\s+(?:CEO|CTO|CFO|President|Director|Manager)\s+(?:of|at)\s+(.+)",
            ],
            RelationshipType.LOCATED_IN: [
                r"(.+?)\s+(?:located in|based in|in|at)\s+(.+)",
                r"(.+?)\s+headquarters\s+(?:is|are)\s+(?:in|at|located in)\s+(.+)",
            ],
            RelationshipType.COLLABORATES_WITH: [
                r"(.+?)\s+(?:partnered with|partners with|collaborates with|works with)\s+(.+)",
                r"(.+?)\s+and\s+(.+?)\s+(?:collaborated|partnered|worked together)",
            ],
            RelationshipType.PART_OF: [
                r"(.+?)\s+(?:is part of|belongs to|is a division of)\s+(.+)",
            ],
        }

    def extract_from_text(self, text: str) -> List[Tuple[str, RelationshipType, str]]:
        """Extract relationships from text"""
        relationships = []

        for rel_type, patterns in self.patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    source = match.group(1).strip()
                    target = match.group(2).strip()
                    relationships.append((source, rel_type, target))

        return relationships


def find_entity_by_name(name: str) -> str:
    """Find entity ID by name in knowledge graph"""
    with knowledge_graph_service.get_session() as session:
        result = session.run("""
            MATCH (e:Entity)
            WHERE toLower(e.name) = toLower($name)
            RETURN e.id as id
            LIMIT 1
        """, name=name)

        record = result.single()
        return record['id'] if record else None


def add_relationship_examples():
    """Add some example relationships to demonstrate"""

    print("\n" + "="*70)
    print("Adding Relationships to Knowledge Graph")
    print("="*70 + "\n")

    # Example relationships to add
    relationships_to_add = [
        {
            "source": "Jane Smith",
            "target": "TechCorp Solutions",
            "type": RelationshipType.WORKS_FOR,
            "context": "Jane Smith is the CTO at TechCorp Solutions",
            "strength": 1.0
        },
        {
            "source": "TechCorp Solutions",
            "target": "San Francisco",
            "type": RelationshipType.LOCATED_IN,
            "context": "TechCorp Solutions is based in San Francisco",
            "strength": 1.0
        },
        {
            "source": "TechCorp Solutions",
            "target": "Stanford University",
            "type": RelationshipType.COLLABORATES_WITH,
            "context": "TechCorp partnered with Stanford University",
            "strength": 0.8
        },
        {
            "source": "Machine Learning",
            "target": "Artificial Intelligence",
            "type": RelationshipType.PART_OF,
            "context": "Machine Learning is part of Artificial Intelligence",
            "strength": 1.0
        },
    ]

    created_count = 0
    skipped_count = 0

    for rel_data in relationships_to_add:
        print(f"Adding: {rel_data['source']} → {rel_data['type'].value} → {rel_data['target']}")

        # Find entity IDs
        source_id = find_entity_by_name(rel_data['source'])
        target_id = find_entity_by_name(rel_data['target'])

        if not source_id:
            print(f"  ⚠ Source entity '{rel_data['source']}' not found - skipping")
            skipped_count += 1
            continue

        if not target_id:
            print(f"  ⚠ Target entity '{rel_data['target']}' not found - skipping")
            skipped_count += 1
            continue

        try:
            # Create relationship
            rel_request = CreateRelationshipRequest(
                source_entity_id=source_id,
                target_entity_id=target_id,
                relationship_type=rel_data['type'],
                strength=rel_data['strength'],
                confidence_score=0.9,
                context=rel_data['context'],
                evidence=["Manual relationship creation"],
                metadata={
                    "source": "manual_addition",
                    "added_via": "example_script"
                }
            )

            relationship = knowledge_graph_service.create_relationship(rel_request)
            print(f"  ✓ Created relationship: {relationship.id}")
            created_count += 1

        except Exception as e:
            print(f"  ✗ Error: {str(e)[:60]}")
            skipped_count += 1

    print("\n" + "="*70)
    print(f"✓ Created: {created_count} relationships")
    print(f"⚠ Skipped: {skipped_count} relationships")
    print("="*70)

    # Show how to query relationships
    print("\nQuery relationships in Neo4j Browser:")
    print("1. Open http://localhost:7474")
    print("2. Run these queries:")
    print()
    print("// See all relationships")
    print("MATCH (a)-[r]->(b) RETURN a, r, b LIMIT 25")
    print()
    print("// Find who works where")
    print("MATCH (p:Entity)-[r:RELATED_TO]->(o:Entity)")
    print("WHERE r.type = 'WORKS_FOR'")
    print("RETURN p.name, o.name")
    print()


def extract_relationships_from_documents():
    """Extract relationships from existing documents"""

    print("\n" + "="*70)
    print("Extracting Relationships from Documents")
    print("="*70 + "\n")

    from src.core.database import SessionLocal
    from src.models.document import Document

    db = SessionLocal()
    extractor = RelationshipExtractor()

    try:
        # Get documents with text
        documents = db.query(Document).filter(
            Document.content_text.isnot(None),
            Document.content_text != ""
        ).limit(10).all()

        print(f"Processing {len(documents)} documents...\n")

        total_extracted = 0
        total_created = 0

        for doc in documents:
            print(f"Document: {doc.title[:50]}")

            # Extract relationships
            relationships = extractor.extract_from_text(doc.content_text)

            if relationships:
                print(f"  Found {len(relationships)} potential relationships:")
                for source, rel_type, target in relationships[:3]:
                    print(f"    • {source[:30]} → {rel_type.value} → {target[:30]}")
                    total_extracted += 1

                    # Try to create in graph
                    source_id = find_entity_by_name(source)
                    target_id = find_entity_by_name(target)

                    if source_id and target_id:
                        try:
                            rel_request = CreateRelationshipRequest(
                                source_entity_id=source_id,
                                target_entity_id=target_id,
                                relationship_type=rel_type,
                                strength=0.7,
                                confidence_score=0.7,
                                context=doc.content_text[:200],
                                evidence=[f"Extracted from document: {doc.title}"],
                                metadata={
                                    "source": "automatic_extraction",
                                    "document_id": str(doc.id)
                                }
                            )

                            relationship = knowledge_graph_service.create_relationship(rel_request)
                            total_created += 1
                            print(f"      ✓ Created in graph")
                        except Exception as e:
                            print(f"      ✗ Error: {str(e)[:40]}")
            else:
                print("  No relationships found")

            print()

        print("="*70)
        print(f"Total relationships extracted: {total_extracted}")
        print(f"Total relationships created: {total_created}")
        print("="*70)

    finally:
        db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Add relationships to knowledge graph')
    parser.add_argument('--examples', action='store_true', help='Add example relationships')
    parser.add_argument('--extract', action='store_true', help='Extract from documents')
    parser.add_argument('--all', action='store_true', help='Do both')

    args = parser.parse_args()

    if args.all or args.examples:
        add_relationship_examples()

    if args.all or args.extract:
        extract_relationships_from_documents()

    if not (args.examples or args.extract or args.all):
        print("Usage:")
        print("  --examples : Add example relationships")
        print("  --extract  : Extract relationships from documents")
        print("  --all      : Do both")
