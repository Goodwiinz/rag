#!/usr/bin/env python3
import sys
import os
import json
import logging
from typing import List, Dict
from neo4j import GraphDatabase
from dotenv import load_dotenv

# Load environment variables
load_dotenv('backend/.env')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_dataset(path: str) -> List[Dict]:
    with open(path, 'r') as f:
        data = json.load(f)
    return data.get('test_cases', [])

def ingest_paper(tx, paper):
    """Transaction function to ingest a single paper"""
    doc_id = paper['paper_id']
    title = paper['paper_title']
    abstract = paper['paper_abstract']
    authors = paper.get('authors', [])
    categories = paper.get('categories', [])
    published = paper.get('published', '')
    pdf_link = paper.get('pdf_link', '')
    
    # Create document
    tx.run("""
        MERGE (d:DOCUMENT {id: $doc_id})
        SET d.title = $title,
            d.abstract = $abstract,
            d.published = $published,
            d.pdf_link = $pdf_link,
            d.arxiv_id = $doc_id,
            d.source = 'arxiv_eval_import',
            d.indexed_at = datetime()
    """, doc_id=doc_id, title=title, abstract=abstract, 
       published=published, pdf_link=pdf_link)
    
    # Link Authors
    if authors:
        tx.run("""
            MATCH (d:DOCUMENT {id: $doc_id})
            UNWIND $authors as author_name
            MERGE (a:Entity {name: author_name})
            SET a.type = 'PERSON'
            MERGE (a)-[:EXTRACTED_FROM]->(d)
            MERGE (d)-[:AUTHORED_BY]->(a)
        """, doc_id=doc_id, authors=authors)
    
    # Link Categories
    if categories:
        tx.run("""
            MATCH (d:DOCUMENT {id: $doc_id})
            UNWIND $categories as cat_name
            MERGE (c:Entity {name: cat_name})
            SET c.type = 'TOPIC'
            MERGE (c)-[:EXTRACTED_FROM]->(d)
            MERGE (d)-[:HAS_TOPIC]->(c)
        """, doc_id=doc_id, categories=categories)

def update_neo4j():
    print("🚀 Starting Neo4j Knowledge Graph Update...")
    
    uri = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")
    
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        driver.verify_connectivity()
        print(f"✅ Connected to Neo4j at {uri}")
    except Exception as e:
        print(f"❌ Failed to connect to Neo4j: {e}")
        return

    # Path to dataset
    dataset_path = os.path.join(os.path.dirname(__file__), '../backend/data/arxiv/evaluation_dataset_improved.json')
    if not os.path.exists(dataset_path):
        dataset_path = os.path.join(os.path.dirname(__file__), '../data/arxiv/evaluation_dataset_146.json')
    if not os.path.exists(dataset_path):
        print(f"❌ Dataset not found")
        return

    print(f"📂 Loading papers from {dataset_path}...")
    papers = load_dataset(dataset_path)
    print(f"📄 Found {len(papers)} papers to process.")

    success_count = 0
    
    for i, paper in enumerate(papers):
        doc_id = paper['paper_id']
        title = paper['paper_title'][:30]
        print(f"[{i+1}/{len(papers)}] Ingesting {doc_id} ('{title}...')...", end=" ", flush=True)
        
        try:
            with driver.session() as session:
                session.execute_write(ingest_paper, paper)
            print("✓")
            success_count += 1
        except Exception as e:
            print(f"✗ {e}")

    driver.close()
    print("\n" + "="*50)
    print(f"🎉 Update Complete!")
    print(f"✅ Successfully ingested: {success_count}/{len(papers)}")
    print("="*50)

if __name__ == "__main__":
    update_neo4j()
