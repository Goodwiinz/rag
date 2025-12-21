#!/usr/bin/env python3
import sys
import os
import json
import logging
import asyncio
from typing import List, Dict

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../backend'))

from src.services.vector_search_service import vector_search_service
from src.core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_dataset(path: str) -> List[Dict]:
    with open(path, 'r') as f:
        data = json.load(f)
    return data.get('test_cases', [])

def update_collection():
    print("🚀 Starting Qdrant Collection Update...")
    
    # Path to dataset
    dataset_path = os.path.join(os.path.dirname(__file__), '../backend/data/arxiv/evaluation_dataset_improved.json')
    
    # Fallback to the one we used if improved doesn't exist
    if not os.path.exists(dataset_path):
        dataset_path = os.path.join(os.path.dirname(__file__), '../data/arxiv/evaluation_dataset_146.json')
        
    if not os.path.exists(dataset_path):
        print(f"❌ Dataset not found at {dataset_path}")
        return

    print(f"📂 Loading papers from {dataset_path}...")
    papers = load_dataset(dataset_path)
    print(f"📄 Found {len(papers)} papers to process.")

    success_count = 0
    
    for i, paper in enumerate(papers):
        doc_id = paper['paper_id']
        title = paper['paper_title']
        abstract = paper['paper_abstract']
        
        # Construct meaningful text content
        # Combining title, authors, categories, and abstract
        authors = ", ".join(paper.get('authors', []))
        categories = ", ".join(paper.get('categories', []))
        
        full_text = f"Title: {title}\nAuthors: {authors}\nCategories: {categories}\n\nAbstract:\n{abstract}"
        
        print(f"[{i+1}/{len(papers)}] Indexing {doc_id} ('{title[:30]}...')...")
        
        try:
            # Metadata for the document
            metadata = {
                "title": title,
                "authors": authors,
                "categories": categories,
                "published": paper.get("published"),
                "pdf_link": paper.get("pdf_link"),
                "document_id": doc_id,
                "arxiv_id": doc_id
            }

            result = vector_search_service.index_document(
                document_id=doc_id,
                text=full_text,
                organization_id="arxiv_eval",
                content_type="text",
                source_type="arxiv_paper",
                metadata=metadata
            )
            
            if result.success:
                success_count += 1
                # print(f"  ✅ Success: {result.message}")
            else:
                print(f"  ❌ Failed: {result.message}")
                if result.error:
                    print(f"     Error: {result.error}")
                    
        except Exception as e:
            print(f"  ❌ Error processing {doc_id}: {e}")

    print("\n" + "="*50)
    print(f"🎉 Update Complete!")
    print(f"✅ Successfully indexed: {success_count}/{len(papers)}")
    print("="*50)

if __name__ == "__main__":
    update_collection()
