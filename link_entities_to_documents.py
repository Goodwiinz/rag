#!/usr/bin/env python3
"""
Link entities to their source documents and add extraction statistics
"""

import sys
import os
from neo4j import GraphDatabase

# Add backend to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))
from src.core.config import settings

def link_entities_to_documents():
    """Link entities to their source documents and add extraction statistics"""
    driver = None
    try:
        driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )

        with driver.session() as session:
            print("Linking entities to documents and adding extraction statistics...")

            # First, let's see what properties DOCUMENT nodes have
            print("\nChecking DOCUMENT node properties...")
            result = session.run("""
                MATCH (d:DOCUMENT)
                RETURN keys(d) as properties, count(*) as count
            """)

            for record in result:
                print(f"  DOCUMENT properties: {record['properties']}")
                print(f"  Number of DOCUMENT nodes: {record['count']}")

            # Get a sample DOCUMENT node to understand its structure
            result = session.run("""
                MATCH (d:DOCUMENT)
                RETURN d LIMIT 1
            """)

            sample_doc = result.single()
            if sample_doc:
                print(f"\nSample DOCUMENT node: {dict(sample_doc['d'])}")

            # Get entities with their source_document_id (if they have it)
            print("\n\nChecking entities for source_document_id...")
            result = session.run("""
                MATCH (e:Entity)
                WHERE e.source_document_id IS NOT NULL
                RETURN e.source_document_id as doc_id,
                       count(*) as entity_count,
                       collect(DISTINCT e.extraction_method) as methods
                ORDER BY entity_count DESC
            """)

            entities_with_doc_id = list(result)
            if entities_with_doc_id:
                print(f"\nFound {len(entities_with_doc_id)} document IDs with entities:")
                for record in entities_with_doc_id[:5]:  # Show first 5
                    print(f"  Document {record['doc_id']}: {record['entity_count']} entities, methods: {record['methods']}")

                # Create relationships between entities and documents
                print("\n\nCreating relationships between entities and documents...")
                for record in entities_with_doc_id:
                    doc_id = record['doc_id']
                    methods = record['methods']

                    # Create EXTRACTED_FROM relationship
                    result = session.run("""
                        MATCH (e:Entity {source_document_id: $doc_id})
                        MATCH (d:DOCUMENT {id: $doc_id})
                        MERGE (e)-[r:EXTRACTED_FROM]->(d)
                        RETURN count(r) as relationships_created
                    """, doc_id=doc_id)

                    rel_count = result.single()["relationships_created"]
                    if rel_count > 0:
                        print(f"  Created {rel_count} relationships for document {doc_id}")

            # Get extraction statistics for documents
            print("\n\nCalculating extraction statistics for documents...")
            result = session.run("""
                MATCH (d:DOCUMENT)<-[e:EXTRACTED_FROM]-(entity:Entity)
                WITH d,
                     count(DISTINCT entity) as entity_count,
                     collect(DISTINCT entity.extraction_method) as extraction_methods,
                     collect(DISTINCT entity.entity_type) as entity_types
                RETURN d.id as document_id,
                       entity_count,
                       extraction_methods,
                       entity_types
            """)

            doc_stats = list(result)
            print(f"\nFound extraction statistics for {len(doc_stats)} documents:")

            # Update documents with extraction statistics
            for record in doc_stats:
                doc_id = record['document_id']
                entity_count = record['entity_count']
                methods = [m for m in record['extraction_methods'] if m is not None]
                types = [t for t in record['entity_types'] if t is not None]

                # Update document node
                session.run("""
                    MATCH (d:DOCUMENT {id: $doc_id})
                    SET d.entity_count = $entity_count,
                        d.extraction_methods = $methods,
                        d.entity_types = $types,
                        d.last_extracted_at = datetime(),
                        d.extraction_summary = $summary
                """,
                doc_id=doc_id,
                entity_count=entity_count,
                methods=methods,
                types=types,
                summary=f"Extracted {entity_count} entities using methods: {', '.join(methods)}"
                )

                print(f"  Updated document {doc_id}: {entity_count} entities")
                print(f"    Methods: {methods}")
                print(f"    Entity types: {types}")

            # Also update documents without entities
            result = session.run("""
                MATCH (d:DOCUMENT)
                WHERE NOT (d)<-[:EXTRACTED_FROM]-(:Entity)
                SET d.entity_count = 0,
                    d.extraction_methods = [],
                    d.entity_types = [],
                    d.last_extracted_at = datetime()
                RETURN count(d) as empty_docs
            """)

            empty_count = result.single()["empty_docs"]
            if empty_count > 0:
                print(f"\nUpdated {empty_count} documents with no entities")

            # Overall statistics
            print("\n\n" + "="*80)
            print("OVERALL EXTRACTION STATISTICS")
            print("="*80)

            result = session.run("""
                MATCH (d:DOCUMENT)
                RETURN count(d) as total_documents,
                       sum(d.entity_count) as total_entities
            """)

            stats = result.single()
            print(f"Total documents: {stats['total_documents']}")
            print(f"Total entities extracted: {stats['total_entities'] or 0}")

            # Method distribution
            result = session.run("""
                MATCH (d:DOCUMENT)
                UNWIND d.extraction_methods as method
                RETURN method, count(*) as count
                ORDER BY count DESC
            """)

            print("\nExtraction method distribution across documents:")
            for record in result:
                print(f"  {record['method']}: {record['count']} documents")

            # Documents with the most entities
            result = session.run("""
                MATCH (d:DOCUMENT)
                WHERE d.entity_count > 0
                RETURN d.id as document_id, d.entity_count, d.extraction_methods
                ORDER BY d.entity_count DESC
                LIMIT 5
            """)

            print("\nTop 5 documents by entity count:")
            for record in result:
                print(f"  {record['document_id']}: {record['entity_count']} entities ({', '.join(record['extraction_methods'])})")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if driver:
            driver.close()
            print("\nNeo4j connection closed.")

if __name__ == "__main__":
    print("="*80)
    print("ENTITY-DOCUMENT LINKER")
    print("="*80)
    link_entities_to_documents()