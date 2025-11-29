"""
Load and Process PubLayNet Dataset from HuggingFace

This script downloads the PubLayNet dataset from HuggingFace and processes it
for integration with your RAG system.

Dataset: https://huggingface.co/datasets/jordanparker6/publaynet
- 27.4K document images (16.1K train + 11.2K validation)
- Scientific papers from PubMed Central
- Layout annotations (bounding boxes + segmentation)
- 5 categories: text, title, list, table, figure

Usage:
    python examples/load_publaynet_dataset.py --split train --limit 100
"""

import os
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Optional
import json
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from datasets import load_dataset
    from PIL import Image
    import numpy as np
    print("✅ Dependencies loaded successfully")
except ImportError as e:
    print(f"❌ Error importing dependencies: {e}")
    print("Install with: pip install datasets pillow")
    sys.exit(1)


# Layout category mapping
CATEGORY_MAP = {
    1: "text",
    2: "title",
    3: "list",
    4: "table",
    5: "figure"
}


class PubLayNetLoader:
    """
    Loader for PubLayNet dataset from HuggingFace
    """

    def __init__(self, output_dir: str = "./publaynet_data"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        self.images_dir = self.output_dir / "images"
        self.annotations_dir = self.output_dir / "annotations"
        self.metadata_dir = self.output_dir / "metadata"

        for dir_path in [self.images_dir, self.annotations_dir, self.metadata_dir]:
            dir_path.mkdir(exist_ok=True)

        print(f"📁 Output directory: {self.output_dir}")

    def load_dataset(self, split: str = "train", limit: Optional[int] = None):
        """
        Load PubLayNet dataset from HuggingFace

        Args:
            split: Dataset split ('train' or 'validation')
            limit: Maximum number of samples to load (None for all)
        """
        print(f"\n{'='*70}")
        print(f"Loading PubLayNet Dataset - Split: {split}")
        print(f"{'='*70}\n")

        try:
            # Load dataset
            print(f"🔄 Downloading dataset from HuggingFace...")
            dataset = load_dataset("jordanparker6/publaynet", split=split)

            print(f"✅ Dataset loaded: {len(dataset)} samples")

            # Limit if specified
            if limit and limit < len(dataset):
                dataset = dataset.select(range(limit))
                print(f"📊 Limited to: {limit} samples")

            return dataset

        except Exception as e:
            print(f"❌ Error loading dataset: {e}")
            raise

    def process_sample(self, sample: Dict, index: int) -> Dict:
        """
        Process a single dataset sample

        Args:
            sample: Dataset sample with image and annotations
            index: Sample index

        Returns:
            Processed sample metadata
        """
        sample_id = sample.get("id", index)

        # Extract image
        image = sample["image"]
        if isinstance(image, dict):
            # PIL Image wrapped in dict
            pil_image = image
        else:
            pil_image = image

        # Save image
        image_filename = f"{sample_id:08d}.jpg"
        image_path = self.images_dir / image_filename

        if isinstance(pil_image, dict) and 'bytes' in pil_image:
            # Handle ImageObject format
            from io import BytesIO
            img = Image.open(BytesIO(pil_image['bytes']))
        else:
            img = pil_image

        img.save(image_path, format="JPEG", quality=95)

        # Get image dimensions
        width, height = img.size

        # Process annotations
        annotations = sample.get("annotations", [])
        processed_annotations = []

        if isinstance(annotations, dict):
            # Single annotation
            annotations = [annotations]

        for ann in annotations:
            category_id = ann.get("category_id", 0)
            category_name = CATEGORY_MAP.get(category_id, "unknown")

            processed_ann = {
                "category_id": category_id,
                "category": category_name,
                "bbox": ann.get("bbox", []),
                "area": ann.get("area", 0),
                "segmentation": ann.get("segmentation", []),
                "iscrowd": ann.get("iscrowd", 0)
            }
            processed_annotations.append(processed_ann)

        # Save annotations
        annotations_filename = f"{sample_id:08d}.json"
        annotations_path = self.annotations_dir / annotations_filename

        with open(annotations_path, 'w') as f:
            json.dump(processed_annotations, f, indent=2)

        # Create metadata
        metadata = {
            "id": sample_id,
            "image_path": str(image_path.relative_to(self.output_dir)),
            "annotations_path": str(annotations_path.relative_to(self.output_dir)),
            "width": width,
            "height": height,
            "num_annotations": len(processed_annotations),
            "categories": list(set(ann["category"] for ann in processed_annotations)),
            "processed_at": datetime.now().isoformat()
        }

        return metadata

    def process_dataset(self, dataset, batch_size: int = 10):
        """
        Process entire dataset in batches

        Args:
            dataset: HuggingFace dataset
            batch_size: Progress reporting interval
        """
        print(f"\n{'='*70}")
        print(f"Processing Dataset")
        print(f"{'='*70}\n")

        total_samples = len(dataset)
        all_metadata = []

        print(f"📊 Processing {total_samples} samples...\n")

        for idx, sample in enumerate(dataset):
            try:
                # Process sample
                metadata = self.process_sample(sample, idx)
                all_metadata.append(metadata)

                # Progress reporting
                if (idx + 1) % batch_size == 0 or (idx + 1) == total_samples:
                    progress = (idx + 1) / total_samples * 100
                    print(f"Progress: {idx + 1}/{total_samples} ({progress:.1f}%)")

            except Exception as e:
                print(f"⚠️  Error processing sample {idx}: {e}")
                continue

        # Save consolidated metadata
        metadata_file = self.metadata_dir / "dataset_metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(all_metadata, f, indent=2)

        print(f"\n✅ Saved metadata to: {metadata_file}")

        # Generate statistics
        self.generate_statistics(all_metadata)

        return all_metadata

    def generate_statistics(self, metadata: List[Dict]):
        """
        Generate dataset statistics

        Args:
            metadata: List of sample metadata
        """
        print(f"\n{'='*70}")
        print(f"Dataset Statistics")
        print(f"{'='*70}\n")

        total_samples = len(metadata)
        total_annotations = sum(m["num_annotations"] for m in metadata)

        # Category counts
        category_counts = {}
        for sample in metadata:
            for category in sample["categories"]:
                category_counts[category] = category_counts.get(category, 0) + 1

        # Image dimensions
        widths = [m["width"] for m in metadata]
        heights = [m["height"] for m in metadata]

        print(f"Total Samples: {total_samples}")
        print(f"Total Annotations: {total_annotations}")
        print(f"Avg Annotations per Sample: {total_annotations / total_samples:.2f}")
        print()

        print("Category Distribution:")
        for category, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
            percentage = count / total_samples * 100
            print(f"  {category:10s}: {count:5d} samples ({percentage:5.1f}%)")
        print()

        print("Image Dimensions:")
        print(f"  Width:  min={min(widths)}, max={max(widths)}, avg={sum(widths)/len(widths):.0f}")
        print(f"  Height: min={min(heights)}, max={max(heights)}, avg={sum(heights)/len(heights):.0f}")
        print()

        # Save statistics
        stats = {
            "total_samples": total_samples,
            "total_annotations": total_annotations,
            "avg_annotations": total_annotations / total_samples,
            "category_counts": category_counts,
            "dimensions": {
                "width": {"min": min(widths), "max": max(widths), "avg": sum(widths) / len(widths)},
                "height": {"min": min(heights), "max": max(heights), "avg": sum(heights) / len(heights)}
            },
            "generated_at": datetime.now().isoformat()
        }

        stats_file = self.metadata_dir / "statistics.json"
        with open(stats_file, 'w') as f:
            json.dump(stats, f, indent=2)

        print(f"✅ Statistics saved to: {stats_file}")


def main():
    parser = argparse.ArgumentParser(description="Load PubLayNet dataset from HuggingFace")
    parser.add_argument("--split", type=str, default="train", choices=["train", "validation"],
                        help="Dataset split to load (default: train)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Limit number of samples to load (default: all)")
    parser.add_argument("--output-dir", type=str, default="./publaynet_data",
                        help="Output directory for processed data (default: ./publaynet_data)")
    parser.add_argument("--batch-size", type=int, default=10,
                        help="Progress reporting interval (default: 10)")

    args = parser.parse_args()

    print("="*70)
    print("PubLayNet Dataset Loader")
    print("="*70)
    print(f"\nConfiguration:")
    print(f"  Split: {args.split}")
    print(f"  Limit: {args.limit or 'all'}")
    print(f"  Output: {args.output_dir}")
    print(f"  Batch size: {args.batch_size}")
    print()

    # Create loader
    loader = PubLayNetLoader(output_dir=args.output_dir)

    # Load dataset
    dataset = loader.load_dataset(split=args.split, limit=args.limit)

    # Process dataset
    metadata = loader.process_dataset(dataset, batch_size=args.batch_size)

    print(f"\n{'='*70}")
    print(f"✅ Dataset Loading Complete!")
    print(f"{'='*70}")
    print(f"\nOutput Directory: {loader.output_dir}")
    print(f"  Images: {loader.images_dir}")
    print(f"  Annotations: {loader.annotations_dir}")
    print(f"  Metadata: {loader.metadata_dir}")
    print()

    print("Next Steps:")
    print("1. Review the processed data in the output directory")
    print("2. Run: python examples/index_publaynet_to_rag.py")
    print("3. Use the indexed data in your RAG system")
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
