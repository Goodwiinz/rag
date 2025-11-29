"""
Simple PubLayNet Indexer - Standalone Version

This script indexes PubLayNet data without requiring full RAG system imports.
It can be run as a standalone script to verify the data and prepare it for indexing.

Usage:
    python examples/index_publaynet_simple.py --data-dir /app/uploads/publaynet_data
"""

import os
import sys
import argparse
import json
from pathlib import Path
from typing import Dict, List
from datetime import datetime

try:
    from PIL import Image
    import numpy as np
    print("✅ Basic dependencies loaded")
except ImportError as e:
    print(f"❌ Error: {e}")
    sys.exit(1)


class PubLayNetSimpleIndexer:
    """
    Simple indexer for PubLayNet dataset
    Prepares data for RAG system integration
    """

    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.images_dir = self.data_dir / "images"
        self.annotations_dir = self.data_dir / "annotations"
        self.metadata_dir = self.data_dir / "metadata"

        # Verify directories exist
        for dir_path in [self.images_dir, self.annotations_dir, self.metadata_dir]:
            if not dir_path.exists():
                raise FileNotFoundError(f"Directory not found: {dir_path}")

        print(f"📁 Data directory: {self.data_dir}")

    def load_metadata(self) -> List[Dict]:
        """Load dataset metadata"""
        metadata_file = self.metadata_dir / "dataset_metadata.json"

        if not metadata_file.exists():
            raise FileNotFoundError(f"Metadata file not found: {metadata_file}")

        with open(metadata_file, 'r') as f:
            metadata = json.load(f)

        print(f"✅ Loaded metadata for {len(metadata)} samples")
        return metadata

    def extract_layout_text(self, annotations: List[Dict]) -> str:
        """
        Extract text description from layout annotations
        """
        # Group by category
        category_counts = {}
        for ann in annotations:
            category = ann["category"]
            category_counts[category] = category_counts.get(category, 0) + 1

        # Generate description
        parts = []
        parts.append("Scientific paper document with layout analysis:")

        for category, count in sorted(category_counts.items()):
            parts.append(f"- {count} {category} region{'s' if count > 1 else ''}")

        # Add spatial information
        if annotations:
            parts.append("\nLayout regions:")
            for i, ann in enumerate(annotations[:10], 1):  # Limit to first 10
                bbox = ann["bbox"]
                category = ann["category"]
                if len(bbox) == 4:
                    x, y, w, h = bbox
                    parts.append(f"{i}. {category} at position ({x:.0f}, {y:.0f}), size {w:.0f}×{h:.0f}px")

        return "\n".join(parts)

    def create_rag_document(
        self,
        sample_metadata: Dict,
        annotations: List[Dict]
    ) -> Dict:
        """
        Create a RAG-ready document structure
        """
        # Extract layout text
        layout_text = self.extract_layout_text(annotations)

        # Create document structure
        document = {
            "id": f"publaynet_{sample_metadata['id']:08d}",
            "title": f"PubLayNet Document {sample_metadata['id']:08d}",
            "source": "publaynet",
            "type": "image",
            "file_path": str(self.data_dir / sample_metadata['image_path']),
            "text_content": layout_text,
            "metadata": {
                "sample_id": sample_metadata['id'],
                "width": sample_metadata['width'],
                "height": sample_metadata['height'],
                "num_annotations": sample_metadata['num_annotations'],
                "categories": sample_metadata['categories'],
                "annotations": annotations,
                "processed_at": datetime.now().isoformat()
            }
        }

        return document

    def process_dataset(self, limit: int = None) -> List[Dict]:
        """
        Process entire dataset and create RAG-ready documents
        """
        print(f"\n{'='*70}")
        print(f"Processing PubLayNet Dataset")
        print(f"{'='*70}\n")

        # Load metadata
        metadata = self.load_metadata()

        if limit:
            metadata = metadata[:limit]
            print(f"📊 Limited to {limit} samples")

        documents = []

        print(f"📊 Processing {len(metadata)} samples...\n")

        for idx, sample_metadata in enumerate(metadata):
            try:
                # Load annotations
                annotations_path = self.data_dir / sample_metadata['annotations_path']
                with open(annotations_path, 'r') as f:
                    annotations = json.load(f)

                # Create RAG document
                document = self.create_rag_document(
                    sample_metadata,
                    annotations
                )

                documents.append(document)

                # Progress reporting
                if (idx + 1) % 10 == 0 or (idx + 1) == len(metadata):
                    progress = (idx + 1) / len(metadata) * 100
                    print(f"Progress: {idx + 1}/{len(metadata)} ({progress:.1f}%)")

            except Exception as e:
                print(f"⚠️  Error processing sample {sample_metadata['id']}: {e}")
                continue

        # Save processed documents
        output_file = self.metadata_dir / "rag_documents.json"
        with open(output_file, 'w') as f:
            json.dump(documents, f, indent=2)

        print(f"\n✅ Saved {len(documents)} RAG documents to: {output_file}")

        # Generate statistics
        self.generate_statistics(documents)

        return documents

    def generate_statistics(self, documents: List[Dict]):
        """Generate processing statistics"""
        print(f"\n{'='*70}")
        print(f"Processing Statistics")
        print(f"{'='*70}\n")

        total_docs = len(documents)

        # Category counts
        all_categories = set()
        category_doc_counts = {}

        for doc in documents:
            categories = doc["metadata"]["categories"]
            for category in categories:
                all_categories.add(category)
                category_doc_counts[category] = category_doc_counts.get(category, 0) + 1

        # Annotation counts
        total_annotations = sum(doc["metadata"]["num_annotations"] for doc in documents)
        avg_annotations = total_annotations / total_docs if total_docs > 0 else 0

        print(f"Total Documents: {total_docs}")
        print(f"Total Annotations: {total_annotations}")
        print(f"Avg Annotations per Document: {avg_annotations:.2f}")
        print()

        print("Category Distribution:")
        for category in sorted(all_categories):
            count = category_doc_counts.get(category, 0)
            percentage = count / total_docs * 100
            print(f"  {category:10s}: {count:5d} documents ({percentage:5.1f}%)")
        print()

        # Save statistics
        stats = {
            "total_documents": total_docs,
            "total_annotations": total_annotations,
            "avg_annotations": avg_annotations,
            "category_distribution": category_doc_counts,
            "categories": sorted(all_categories),
            "generated_at": datetime.now().isoformat()
        }

        stats_file = self.metadata_dir / "rag_statistics.json"
        with open(stats_file, 'w') as f:
            json.dump(stats, f, indent=2)

        print(f"✅ Statistics saved to: {stats_file}")

    def display_sample(self, doc: Dict):
        """Display a sample document"""
        print(f"\n{'='*70}")
        print(f"Sample Document: {doc['id']}")
        print(f"{'='*70}")
        print(f"\nTitle: {doc['title']}")
        print(f"Source: {doc['source']}")
        print(f"Type: {doc['type']}")
        print(f"File: {doc['file_path']}")
        print(f"\nCategories: {', '.join(doc['metadata']['categories'])}")
        print(f"Annotations: {doc['metadata']['num_annotations']}")
        print(f"Dimensions: {doc['metadata']['width']}×{doc['metadata']['height']}px")
        print(f"\nText Content Preview:")
        print("-" * 70)
        text_lines = doc['text_content'].split('\n')
        for line in text_lines[:15]:  # First 15 lines
            print(line)
        if len(text_lines) > 15:
            print(f"... ({len(text_lines) - 15} more lines)")
        print()


def main():
    parser = argparse.ArgumentParser(description="Simple PubLayNet indexer")
    parser.add_argument("--data-dir", type=str, default="/app/uploads/publaynet_data",
                        help="PubLayNet data directory")
    parser.add_argument("--limit", type=int, default=None,
                        help="Limit number of samples to process")
    parser.add_argument("--show-sample", action="store_true",
                        help="Show first sample document")

    args = parser.parse_args()

    print("="*70)
    print("PubLayNet Simple Indexer")
    print("="*70)
    print(f"\nConfiguration:")
    print(f"  Data directory: {args.data_dir}")
    print(f"  Limit: {args.limit or 'all'}")
    print()

    # Create indexer
    indexer = PubLayNetSimpleIndexer(data_dir=args.data_dir)

    # Process dataset
    documents = indexer.process_dataset(limit=args.limit)

    # Show sample if requested
    if args.show_sample and documents:
        indexer.display_sample(documents[0])

    print(f"\n{'='*70}")
    print(f"✅ Processing Complete!")
    print(f"{'='*70}")
    print(f"\nRAG-ready documents saved to:")
    print(f"  {indexer.metadata_dir / 'rag_documents.json'}")
    print()

    print("Next Steps:")
    print("1. Review the rag_documents.json file")
    print("2. Import into your RAG system:")
    print("   - Add to PostgreSQL documents table")
    print("   - Generate embeddings")
    print("   - Index in Qdrant")
    print("3. Query via RAG API")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
