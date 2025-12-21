#!/usr/bin/env python3
"""
Fetch actual paper titles from ArXiv to replace generic 'pdf' titles
"""

import sys
import os
import requests
from datetime import datetime
from neo4j import GraphDatabase

# Add backend to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))
from src.core.config import settings

def fetch_arxiv_title(paper_id):
    """Fetch paper title from ArXiv API"""
    try:
        # ArXiv API endpoint
        url = f"http://export.arxiv.org/api/query?id_list={paper_id}"

        response = requests.get(url, timeout=10)
        response.raise_for_status()

        # Parse XML response (simple extraction)
        import xml.etree.ElementTree as ET
        root = ET.fromstring(response.text)

        # Find title in the XML
        # Namespace handling
        ns = {'atom': 'http://www.w3.org/2005/Atom'}

        for entry in root.findall('atom:entry', ns):
            title_elem = entry.find('atom:title', ns)
            if title_elem is not None:
                title = title_elem.text.strip()
                return title

        return None
    except Exception as e:
        print(f"Error fetching title for {paper_id}: {e}")
        return None

def update_document_titles():
    """Update document titles with real ArXiv paper titles"""
    driver = None
    try:
        driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )

        with driver.session() as session:
            print("Fetching ArXiv paper titles and updating documents...")

            # Get all documents with paper_id and 'pdf' or 'Unknown Title' as title
            result = session.run("""
                MATCH (d:DOCUMENT)
                WHERE d.title IN ['pdf', 'Unknown Title'] AND d.paper_id IS NOT NULL
                RETURN d.paper_id as paper_id, d.id as id
                ORDER BY d.paper_id
            """)

            documents = list(result)
            print(f"\nFound {len(documents)} documents to update:")

            # First, collect unique paper IDs
            paper_ids = set()
            for doc in documents:
                paper_id = doc['paper_id']
                if paper_id and paper_id != doc['id']:  # Skip if paper_id equals id (not an arxiv paper)
                    paper_ids.add(paper_id)

            print(f"\nFetching titles for {len(paper_ids)} unique papers...")

            # Fetch titles in batches
            updated_count = 0
            for paper_id in sorted(paper_ids):
                print(f"\nProcessing: {paper_id}")

                # Try to extract ArXiv ID from the paper_id
                # Some paper_ids might be timestamps, extract the ArXiv pattern
                arxiv_id = None
                if '.' in paper_id and 'v' in paper_id:
                    arxiv_id = paper_id
                elif len(paper_id) == 10 and '.' not in paper_id:  # Timestamp format
                    # Look for entities with this paper_id to find the actual ArXiv ID
                    entity_result = session.run("""
                        MATCH (e:Entity)
                        WHERE e.metadata CONTAINS $paper_id
                        RETURN e.metadata as metadata
                        LIMIT 1
                    """, paper_id=paper_id)

                    entity_record = entity_result.single()
                    if entity_record:
                        import json
                        metadata_str = entity_record['metadata']
                        try:
                            metadata_json = metadata_str.replace("'", '"')
                            metadata = json.loads(metadata_json)
                            arxiv_id = metadata.get('paper_id')
                        except:
                            pass

                if arxiv_id:
                    title = fetch_arxiv_title(arxiv_id)
                    if title:
                        # Update all documents with this paper_id
                        result = session.run("""
                            MATCH (d:DOCUMENT)
                            WHERE d.paper_id = $paper_id
                            SET d.title = $title,
                                d.name = $title,
                                d.arxiv_title_fetched_at = datetime()
                            RETURN count(d) as updated
                        """, paper_id=paper_id, title=title)

                        count = result.single()['updated']
                        if count > 0:
                            updated_count += count
                            print(f"  ✓ Updated {count} documents: {title[:80]}...")
                    else:
                        print(f"  ✗ Could not fetch title for {arxiv_id}")
                else:
                    print(f"  ✗ No ArXiv ID found for {paper_id}")

            # Also update documents that have ArXiv IDs in their id field
            print("\n\nChecking for documents with ArXiv IDs in the id field...")
            result = session.run("""
                MATCH (d:DOCUMENT)
                WHERE d.id =~ '\\d{4}\\.\\d{4,5}v\\d+'
                AND d.title IN ['pdf', 'Unknown Title']
                RETURN d.id as arxiv_id, d.id as doc_id
            """)

            arxiv_docs = list(result)
            for doc in arxiv_docs:
                arxiv_id = doc['arxiv_id']
                print(f"\nProcessing ArXiv ID from id field: {arxiv_id}")

                title = fetch_arxiv_title(arxiv_id)
                if title:
                    session.run("""
                        MATCH (d:DOCUMENT)
                        WHERE d.id = $arxiv_id
                        SET d.title = $title,
                            d.name = $title,
                            d.arxiv_title_fetched_at = datetime()
                    """, arxiv_id=arxiv_id, title=title)
                    print(f"  ✓ Updated: {title[:80]}...")
                    updated_count += 1

            print("\n" + "="*80)
            print("UPDATE SUMMARY")
            print("="*80)
            print(f"Documents updated: {updated_count}")

            # Show sample of updated documents
            if updated_count > 0:
                print("\nSample of updated documents:")
                result = session.run("""
                    MATCH (d:DOCUMENT)
                    WHERE d.arxiv_title_fetched_at IS NOT NULL
                    RETURN d.title as title, d.paper_id as paper_id, d.entity_count as entities
                    LIMIT 5
                """)

                for record in result:
                    print(f"\n  {record['title']}")
                    print(f"    Paper ID: {record['paper_id']}")
                    print(f"    Entities: {record.get('entities', 0)}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if driver:
            driver.close()

if __name__ == "__main__":
    print("="*80)
    print("ARXIV TITLE FETCHER")
    print("="*80)
    print("This script will fetch actual paper titles from ArXiv API")
    print("to replace generic 'pdf' or 'Unknown Title' labels.\n")

    update_document_titles()