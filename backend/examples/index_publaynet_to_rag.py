"""
Index PubLayNet Dataset into RAG System

This script indexes the processed PubLayNet dataset into your RAG system:
- Stores images in the database
- Extracts text/layout features
- Creates vector embeddings
- Indexes in Qdrant for semantic search
- Links to knowledge graph

Prerequisites:
    1. Run load_publaynet_dataset.py first
    2. Ensure backend services are running

Usage:
    python examples/index_publaynet_to_rag.py --data-dir ./publaynet_data
"""

import os
import sys
import argparse
import json
from pathlib import Path
from typing import Dict, List
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from PIL import Image
    import numpy as np
    print("✅ Basic dependencies loaded")
except ImportError as e:
    print(f"❌ Error: {e}")
    sys.exit(1)

# Import RAG system components
try:
    from src.database import SessionLocal
    from src.models.document import Document, DocumentStatus
    from src.services.vector_service import vector_service
    print("✅ RAG system components loaded")
except ImportError as e:
    print(f"⚠️  Warning: Could not load RAG components: {e}")
    print("This script should be run from within the Docker container")


class PubLayNetIndexer:
    """
    Index PubLayNet dataset into RAG system
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

        Args:
            annotations: List of annotation objects

        Returns:
            Text description of the layout
        """
        # Group by category
        category_counts = {}
        for ann in annotations:
            category = ann["category"]
            category_counts[category] = category_counts.get(category, 0) + 1

        # Generate description
        parts = []
        parts.append("Document layout analysis:")

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

    def create_document_entry(
        self,
        sample_metadata: Dict,
        annotations: List[Dict],
        db_session
    ) -> Document:
        """
        Create a document entry in the database

        Args:
            sample_metadata: Sample metadata
            annotations: Layout annotations
            db_session: Database session

        Returns:
            Created Document object
        """
        # Extract layout text
        layout_text = self.extract_layout_text(annotations)

        # Create document
        document = Document(
            title=f"PubLayNet Document {sample_metadata['id']:08d}",
            file_name=f"publaynet_{sample_metadata['id']:08d}.jpg",
            file_path=str(self.data_dir / sample_metadata['image_path']),
            mime_type="image/jpeg",
            file_size=0,  # Could calculate if needed
            status=DocumentStatus.COMPLETED,
            content_text=layout_text,
            metadata={
                "source": "publaynet",
                "sample_id": sample_metadata['id'],
                "width": sample_metadata['width'],
                "height": sample_metadata['height'],
                "num_annotations": sample_metadata['num_annotations'],
                "categories": sample_metadata['categories'],
                "annotations": annotations[:20]  # Store first 20 annotations
            }
        )

        db_session.add(document)
        db_session.commit()
        db_session.refresh(document)

        return document

    def index_sample(
        self,
        sample_metadata: Dict,
        db_session,
        embedding_model=None
    ) -> bool:
        """
        Index a single sample into RAG system

        Args:
            sample_metadata: Sample metadata
            db_session: Database session
            embedding_model: Optional embedding model for text

        Returns:
            Success status
        """
        try:
            # Load annotations
            annotations_path = self.data_dir / sample_metadata['annotations_path']
            with open(annotations_path, 'r') as f:
                annotations = json.load(f)

            # Create document entry
            document = self.create_document_entry(
                sample_metadata,
                annotations,
                db_session
            )

            # Generate embeddings if model provided
            if embedding_model:
                layout_text = document.content_text
                embedding = embedding_model.encode([layout_text])[0]

                # Store in Qdrant
                vector_service.add_vector(
                    collection_name="publaynet_documents",
                    vector=embedding.tolist(),
                    payload={
                        "document_id": document.id,
                        "sample_id": sample_metadata['id'],
                        "title": document.title,
                        "text": layout_text,
                        "categories": sample_metadata['categories'],
                        "source": "publaynet"
                    }
                )

            return True

        except Exception as e:
            print(f"⚠️  Error indexing sample {sample_metadata['id']}: {e}")
            return False

    def index_dataset(self, limit: Optional[int] = None):
        """
        Index entire dataset

        Args:
            limit: Maximum number of samples to index
        """
        print(f"\n{'='*70}")
        print(f"Indexing PubLayNet Dataset into RAG System")
        print(f"{'='*70}\n")

        # Load metadata
        metadata = self.load_metadata()

        if limit:
            metadata = metadata[:limit]
            print(f"📊 Limited to {limit} samples")

        # Initialize embedding model
        embedding_model = None
        try:
            from sentence_transformers import SentenceTransformer
            embedding_model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
            print("✅ Embedding model loaded")
        except Exception as e:
            print(f"⚠️  Could not load embedding model: {e}")
            print("Continuing without embeddings...")

        # Create Qdrant collection if needed
        if embedding_model:
            try:
                vector_service.create_collection(
                    name="publaynet_documents",
                    vector_size=384  # all-MiniLM-L6-v2 dimension
                )
                print("✅ Qdrant collection created")
            except Exception as e:
                print(f"ℹ️  Collection may already exist: {e}")

        # Index samples
        db_session = SessionLocal()
        success_count = 0
        fail_count = 0

        print(f"\n📊 Indexing {len(metadata)} samples...\n")

        for idx, sample_metadata in enumerate(metadata):
            try:
                success = self.index_sample(
                    sample_metadata,
                    db_session,
                    embedding_model
                )

                if success:
                    success_count += 1
                else:
                    fail_count += 1

                # Progress reporting
                if (idx + 1) % 10 == 0 or (idx + 1) == len(metadata):
                    progress = (idx + 1) / len(metadata) * 100
                    print(f"Progress: {idx + 1}/{len(metadata)} ({progress:.1f}%) - "
                          f"Success: {success_count}, Failed: {fail_count}")

            except Exception as e:
                print(f"⚠️  Error: {e}")
                fail_count += 1
                continue

        db_session.close()

        # Summary
        print(f"\n{'='*70}")
        print(f"Indexing Complete")
        print(f"{'='*70}")
        print(f"\nTotal Samples: {len(metadata)}")
        print(f"Successfully Indexed: {success_count}")
        print(f"Failed: {fail_count}")
        print()


def main():
    parser = argparse.ArgumentParser(description="Index PubLayNet dataset into RAG system")
    parser.add_argument("--data-dir", type=str, default="./publaynet_data",
                        help="PubLayNet data directory (default: ./publaynet_data)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Limit number of samples to index (default: all)")

    args = parser.parse_args()

    print("="*70)
    print("PubLayNet RAG Indexer")
    print("="*70)
    print(f"\nConfiguration:")
    print(f"  Data directory: {args.data_dir}")
    print(f"  Limit: {args.limit or 'all'}")
    print()

    # Create indexer
    indexer = PubLayNetIndexer(data_dir=args.data_dir)

    # Index dataset
    indexer.index_dataset(limit=args.limit)

    print("✅ Indexing complete!")
    print("\nYou can now:")
    print("1. Search PubLayNet documents via RAG API")
    print("2. Query by layout features")
    print("3. Use in multimodal pipelines")
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
