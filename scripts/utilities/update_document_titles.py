#!/usr/bin/env python3
"""
Update document nodes with real paper titles from entity metadata
"""

import sys
import os
import json
from neo4j import GraphDatabase

# Add backend to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))
from src.core.config import settings

def update_document_titles():
    """Update document nodes with real paper titles"""
    driver = None
    try:
        driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )

        with driver.session() as session:
            print("Updating document nodes with real paper titles...")

            # First, let's get unique paper IDs from entity metadata
            result = session.run("""
                MATCH (e:Entity)
                WHERE e.metadata IS NOT NULL AND e.metadata CONTAINS 'paper_id'
                RETURN e.name as entity_name, e.metadata as metadata, e.extraction_method as extraction_method
            """)

            papers = {}
            for record in result:
                metadata_str = record['metadata']
                entity_name = record['entity_name']
                extraction_method = record.get('extraction_method', 'unknown')

                # Parse metadata string (stored as Python dict string, need to convert to JSON)
                if metadata_str and isinstance(metadata_str, str):
                    try:
                        # Replace single quotes with double quotes for valid JSON
                        metadata_json = metadata_str.replace("'", '"')
                        metadata = json.loads(metadata_json)

                        if 'paper_id' in metadata:
                            paper_id = metadata['paper_id']
                            if paper_id not in papers:
                                papers[paper_id] = {
                                    'title': metadata.get('paper_title', 'Unknown Title'),
                                    'category': metadata.get('arxiv_category', ''),
                                    'date': metadata.get('publication_date', ''),
                                    'entity_count': 0,
                                    'extraction_methods': set(),
                                    'entity_types': set()
                                }

                            # Update entity count and methods
                            papers[paper_id]['entity_count'] += 1
                            papers[paper_id]['extraction_methods'].add(extraction_method)

                            if 'entity_type_original' in metadata:
                                papers[paper_id]['entity_types'].add(metadata['entity_type_original'])

                    except json.JSONDecodeError:
                        # If JSON parsing fails, try a different approach
                        # Look for paper_id pattern in the string
                        import re
                        paper_id_match = re.search(r'paper_id["\s:]+([^\s,}]+)', metadata_str)
                        if paper_id_match:
                            paper_id = paper_id_match.group(1).strip('"')
                            if paper_id not in papers:
                                papers[paper_id] = {
                                    'title': f'Paper {paper_id}',  # Use paper_id as title
                                    'category': '',
                                    'date': '',
                                    'entity_count': 0,
                                    'extraction_methods': set(),
                                    'entity_types': set()
                                }
                            papers[paper_id]['entity_count'] += 1
                            papers[paper_id]['extraction_methods'].add(extraction_method)

            print(f"\nFound {len(papers)} unique papers:")
            for paper_id, info in papers.items():
                print(f"\nPaper ID: {paper_id}")
                print(f"  Title: {info['title']}")
                print(f"  Category: {info['category']}")
                print(f"  Date: {info['date']}")
                print(f"  Entity count: {info['entity_count']}")
                print(f"  Extraction methods: {', '.join(info['extraction_methods'])}")

            # Now update DOCUMENT nodes with paper titles
            print("\n\nUpdating DOCUMENT nodes with paper information...")

            updated_count = 0
            created_count = 0

            for paper_id, info in papers.items():
                # Check if a DOCUMENT node with this paper_id already exists
                result = session.run("""
                    MATCH (d:DOCUMENT)
                    WHERE d.id = $paper_id OR d.paper_id = $paper_id
                    RETURN d
                """, paper_id=paper_id)

                existing_doc = result.single()

                if existing_doc:
                    # Update existing document
                    session.run("""
                        MATCH (d:DOCUMENT)
                        WHERE d.id = $paper_id OR d.paper_id = $paper_id
                        SET d.name = $title,
                            d.title = $title,
                            d.paper_id = $paper_id,
                            d.arxiv_category = $category,
                            d.publication_date = $date,
                            d.entity_count = $entity_count,
                            d.extraction_methods = $methods,
                            d.entity_types = $types,
                            d.last_updated = datetime()
                    """,
                    paper_id=paper_id,
                    title=info['title'],
                    category=info['category'],
                    date=info['date'],
                    entity_count=info['entity_count'],
                    methods=list(info['extraction_methods']),
                    types=list(info['entity_types'])
                    )
                    updated_count += 1
                    print(f"  Updated document: {paper_id} -> {info['title']}")
                else:
                    # Create new document node if needed
                    print(f"  No existing document found for paper: {paper_id}")
                    # We'll link entities to existing DOCUMENT nodes later

            # Link entities to documents based on paper_id
            print("\n\nLinking entities to their document nodes...")
            linked_count = 0

            for paper_id in papers.keys():
                # First, check if we have a document with this paper_id
                result = session.run("""
                    MATCH (d:DOCUMENT)
                    WHERE d.id = $paper_id OR d.name = $paper_id
                    RETURN d.id as doc_id
                """, paper_id=paper_id)

                existing_doc = result.single()

                if not existing_doc:
                    # Create a new document node if it doesn't exist
                    paper_info = papers[paper_id]
                    session.run("""
                        CREATE (d:DOCUMENT {
                            id: $paper_id,
                            paper_id: $paper_id,
                            name: $title,
                            title: $title,
                            arxiv_category: $category,
                            publication_date: $date,
                            entity_count: $entity_count,
                            extraction_methods: $methods,
                            entity_types: $types,
                            created_at: datetime(),
                            last_extracted_at: datetime()
                        })
                    """,
                    paper_id=paper_id,
                    title=paper_info['title'],
                    category=paper_info['category'],
                    date=paper_info['date'],
                    entity_count=paper_info['entity_count'],
                    methods=list(paper_info['extraction_methods']),
                    types=list(paper_info['entity_types'])
                    )
                    print(f"  Created document for paper: {paper_id} - {paper_info['title']}")

                # Now link entities
                result = session.run("""
                    MATCH (e:Entity)
                    WHERE e.metadata CONTAINS $paper_id
                    MATCH (d:DOCUMENT)
                    WHERE d.id = $paper_id OR d.paper_id = $paper_id
                    MERGE (e)-[:EXTRACTED_FROM]->(d)
                    RETURN count(*) as links_created
                """, paper_id=paper_id)

                links = result.single()['links_created']
                if links > 0:
                    linked_count += links
                    print(f"  Linked {links} entities to document {paper_id}")

            # Update document statistics
            print("\n\nRecalculating document statistics...")
            result = session.run("""
                MATCH (d:DOCUMENT)
                OPTIONAL MATCH (d)<-[:EXTRACTED_FROM]-(e:Entity)
                WITH d, count(DISTINCT e) as actual_entity_count,
                     collect(DISTINCT e.extraction_method) as actual_methods,
                     collect(DISTINCT e.type) as actual_types
                SET d.entity_count = actual_entity_count,
                    d.extraction_methods = actual_methods,
                    d.entity_types = actual_types,
                    d.last_extracted_at = datetime()
                RETURN d.name as title, d.entity_count, d.extraction_methods
                ORDER BY d.entity_count DESC
            """)

            print("\nDocument statistics after update:")
            for record in result:
                title = record.get('title', 'Unknown Title')
                count = record.get('actual_entity_count', 0)
                methods = [m for m in record.get('actual_methods', []) if m is not None]
                print(f"  {title}: {count} entities")
                if methods:
                    print(f"    Methods: {', '.join(methods)}")

            print("\n" + "="*80)
            print("SUMMARY")
            print("="*80)
            print(f"Updated documents: {updated_count}")
            print(f"Created documents: {created_count}")
            print(f"Linked entities: {linked_count}")

            # Display query for checking results
            print("\n\nTo check the results in Neo4j Browser, run:")
            print("MATCH (d:DOCUMENT) RETURN d")
            print("\nOr to see documents with their entities:")
            print("MATCH (d:DOCUMENT)<-[:EXTRACTED_FROM]-(e:Entity)")
            print("RETURN d.name as document, e.name as entity, e.type as entity_type, e.extraction_method as method")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if driver:
            driver.close()

if __name__ == "__main__":
    print("="*80)
    print("DOCUMENT TITLE UPDATER")
    print("="*80)
    update_document_titles()