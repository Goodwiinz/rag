#!/usr/bin/env python3
"""Test knowledge graph update with sample data"""

import sys
import os
sys.path.append('/Users/goodwiinz/development/RAG_system/backend')

from datetime import datetime

# Import the function that handles KG updates
from src.api.arxiv_local import _update_knowledge_graph_with_local_extractions_sync

# Create test result data
test_result = {
    "paper_id": "test_paper_2025_001",
    "filename": "test_paper.pdf",
    "extraction_status": "completed",
    "features": {
        "extracted_text": "This is a test paper about machine learning and artificial intelligence. It discusses various algorithms including neural networks, support vector machines, and decision trees. The paper also covers topics like deep learning, computer vision, and natural language processing.",
        "metadata": {
            "title": "Test Paper on Machine Learning Fundamentals",
            "author": "Test Author",
            "subject": "Computer Science - Machine Learning",
            "creator": "Test Creator"
        },
        "topics": [
            "Machine Learning",
            "Neural Networks",
            "Deep Learning",
            "Computer Vision",
            "Natural Language Processing"
        ],
        "keyphrases": [
            "support vector machines",
            "decision trees",
            "artificial intelligence",
            "algorithms"
        ],
        "summary": "This paper provides an overview of fundamental machine learning concepts and algorithms."
    }
}

print("Testing knowledge graph update...")
print(f"Test data: Paper ID = {test_result['paper_id']}")
print(f"Topics to add: {test_result['features']['topics']}")
print(f"Keyphrases to add: {test_result['features']['keyphrases']}")

# Call the function
try:
    print("\nExecuting _update_knowledge_graph_with_local_extractions_sync...")
    _update_knowledge_graph_with_local_extractions_sync(test_result)
    print("✅ Knowledge graph update completed successfully!")
except Exception as e:
    print(f"❌ Error during KG update: {e}")
    import traceback
    traceback.print_exc()

# Verify the update
print("\nVerifying update...")
from src.services.knowledge_graph_service import KnowledgeGraphService

kg_service = KnowledgeGraphService()

# Search for the test paper
results = kg_service.search_entities(
    query="Test Paper on Machine Learning Fundamentals",
    entity_types=None,
    limit=5
)

if results:
    print(f"✅ Found {len(results)} entities")
    for entity in results:
        print(f"   - {entity.name} (Type: {entity.entity_type})")
else:
    print("❌ No entities found")