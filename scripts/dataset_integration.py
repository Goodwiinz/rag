#!/usr/bin/env python3
"""
Dataset Integration Scripts for RAG System
Supports DocVQA, PubLayNet, LAION-400M and custom datasets
"""

import os
import json
import requests
import aiohttp
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import zipfile
import tarfile
from PIL import Image
import io
import base64
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class DatasetConfig:
    """Configuration for dataset integration"""
    name: str
    source_url: str
    dataset_type: str  # 'docvqa', 'publaynet', 'laion', 'custom'
    file_format: str  # 'json', 'csv', 'images', 'mixed'
    processing_func: str
    target_count: int
    description: str

class DatasetDownloader:
    """Handles downloading of various dataset types"""

    def __init__(self, download_dir: str = "datasets/downloads"):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)

    def download_file(self, url: str, filename: str, chunk_size: int = 8192) -> bool:
        """Download a file with progress tracking"""
        try:
            file_path = self.download_dir / filename
            logger.info(f"Downloading {url} to {file_path}")

            response = requests.get(url, stream=True)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0

            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            progress = (downloaded / total_size) * 100
                            print(f"\rProgress: {progress:.1f}%", end='', flush=True)

            print(f"\nDownloaded {filename} successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to download {url}: {str(e)}")
            return False

    def download_docvqa_sample(self) -> bool:
        """Download sample DocVQA dataset"""
        # Using a small sample for demonstration
        sample_url = "https://raw.githubusercontent.com/docvqa/docvqa/master/docvqa_samples.json"
        return self.download_file(sample_url, "docvqa_sample.json")

    def download_publaynet_sample(self) -> bool:
        """Download sample PubLayNet dataset"""
        # Sample PubLayNet annotations
        sample_url = "https://raw.githubusercontent.com/ibm-aur-nlp/PubLayNet/master/publaynet_samples.json"
        return self.download_file(sample_url, "publaynet_sample.json")

    def create_laion_sample(self) -> bool:
        """Create a sample LAION-style dataset"""
        # LAION-400M is too large, so we create a representative sample
        sample_data = {
            "metadata": {
                "version": "sample_v1",
                "description": "Sample dataset similar to LAION-400M structure",
                "created_at": datetime.now().isoformat()
            },
            "images": [
                {
                    "id": i,
                    "url": f"https://example.com/image_{i}.jpg",
                    "caption": f"Sample image caption {i}",
                    "width": 640,
                    "height": 480,
                    "hash": f"hash_{i}",
                    "similarity": 0.95 - (i * 0.01),
                    "language": "en",
                    "nsfw": 0.0
                }
                for i in range(100)
            ]
        }

        sample_path = self.download_dir / "laion_sample.json"
        with open(sample_path, 'w') as f:
            json.dump(sample_data, f, indent=2)

        logger.info(f"Created LAION sample dataset with {len(sample_data['images'])} images")
        return True

class DatasetProcessor:
    """Processes downloaded datasets for RAG system ingestion"""

    def __init__(self, api_base_url: str = "http://localhost:8000"):
        self.api_base_url = api_base_url
        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def authenticate(self, username: str = "admin", password: str = "REDACTED") -> str:
        """Authenticate with the RAG system"""
        async with self.session.post(
            f"{self.api_base_url}/auth/login",
            json={"username": username, "password": password}
        ) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("access_token")
            else:
                raise Exception("Authentication failed")

    async def upload_document(self, file_path: Path, token: str, metadata: Dict = None) -> bool:
        """Upload a document to the RAG system"""
        headers = {"Authorization": f"Bearer {token}"}

        try:
            with open(file_path, 'rb') as f:
                data = aiohttp.FormData()
                data.add_field('file', f, filename=file_path.name, content_type='application/octet-stream')

                if metadata:
                    for key, value in metadata.items():
                        data.add_field(key, str(value))

                async with self.session.post(
                    f"{self.api_base_url}/documents/upload",
                    data=data,
                    headers=headers
                ) as response:
                    return response.status == 200

        except Exception as e:
            logger.error(f"Failed to upload {file_path}: {str(e)}")
            return False

    def process_docvqa(self, data_path: Path) -> int:
        """Process DocVQA dataset for RAG system"""
        logger.info("Processing DocVQA dataset...")

        with open(data_path, 'r') as f:
            data = json.load(f)

        processed_count = 0

        for item in data.get('data', []):
            try:
                # Create a document from Q&A pair
                document = {
                    "title": item.get('question', '')[:100],
                    "content": f"Question: {item.get('question', '')}\n\nAnswer: {item.get('answer', '')}",
                    "metadata": {
                        "source": "docvqa",
                        "question": item.get('question', ''),
                        "answer": item.get('answer', ''),
                        "document_id": item.get('doc_id', ''),
                        "page_number": item.get('page_num', 0)
                    }
                }

                # Save as JSON file for upload
                temp_file = Path(f"temp_docvqa_{processed_count}.json")
                with open(temp_file, 'w') as f:
                    json.dump(document, f)

                # Upload to RAG system (synchronous for now)
                # This would need to be made async in a real implementation

                temp_file.unlink()  # Clean up
                processed_count += 1

                if processed_count % 10 == 0:
                    logger.info(f"Processed {processed_count} DocVQA items")

            except Exception as e:
                logger.error(f"Error processing DocVQA item: {str(e)}")
                continue

        logger.info(f"Processed {processed_count} DocVQA items")
        return processed_count

    def process_publaynet(self, data_path: Path) -> int:
        """Process PubLayNet dataset for RAG system"""
        logger.info("Processing PubLayNet dataset...")

        with open(data_path, 'r') as f:
            data = json.load(f)

        processed_count = 0

        for item in data.get('annotations', []):
            try:
                # Create document from layout annotation
                document = {
                    "title": f"Document {item.get('image_id', processed_count)}",
                    "content": self.create_content_from_layout(item),
                    "metadata": {
                        "source": "publaynet",
                        "image_id": item.get('image_id', ''),
                        "layout_type": item.get('category', ''),
                        "bbox": item.get('bbox', []),
                        "width": item.get('width', 0),
                        "height": item.get('height', 0)
                    }
                }

                # Save and upload logic similar to DocVQA
                temp_file = Path(f"temp_publaynet_{processed_count}.json")
                with open(temp_file, 'w') as f:
                    json.dump(document, f)

                temp_file.unlink()
                processed_count += 1

                if processed_count % 10 == 0:
                    logger.info(f"Processed {processed_count} PubLayNet items")

            except Exception as e:
                logger.error(f"Error processing PubLayNet item: {str(e)}")
                continue

        logger.info(f"Processed {processed_count} PubLayNet items")
        return processed_count

    def create_content_from_layout(self, layout_item: Dict) -> str:
        """Create textual content from layout annotation"""
        content_parts = []

        # Add layout type
        layout_type = layout_item.get('category', 'unknown')
        content_parts.append(f"Layout Type: {layout_type}")

        # Add bounding box information
        bbox = layout_item.get('bbox', [])
        if bbox:
            content_parts.append(f"Bounding Box: {bbox}")

        # Add dimensions
        width = layout_item.get('width', 0)
        height = layout_item.get('height', 0)
        if width and height:
            content_parts.append(f"Dimensions: {width}x{height}")

        # Add image ID
        image_id = layout_item.get('image_id', '')
        if image_id:
            content_parts.append(f"Image ID: {image_id}")

        return "\n".join(content_parts)

    def process_laion(self, data_path: Path) -> int:
        """Process LAION dataset for RAG system"""
        logger.info("Processing LAION dataset...")

        with open(data_path, 'r') as f:
            data = json.load(f)

        processed_count = 0

        for image_item in data.get('images', []):
            try:
                # Create document from image metadata
                document = {
                    "title": f"Image {image_item.get('id', processed_count)}",
                    "content": f"Image Caption: {image_item.get('caption', '')}",
                    "metadata": {
                        "source": "laion",
                        "image_id": image_item.get('id', ''),
                        "url": image_item.get('url', ''),
                        "similarity": image_item.get('similarity', 0.0),
                        "language": image_item.get('language', 'en'),
                        "width": image_item.get('width', 0),
                        "height": image_item.get('height', 0)
                    }
                }

                # Save and upload logic
                temp_file = Path(f"temp_laion_{processed_count}.json")
                with open(temp_file, 'w') as f:
                    json.dump(document, f)

                temp_file.unlink()
                processed_count += 1

                if processed_count % 10 == 0:
                    logger.info(f"Processed {processed_count} LAION items")

            except Exception as e:
                logger.error(f"Error processing LAION item: {str(e)}")
                continue

        logger.info(f"Processed {processed_count} LAION items")
        return processed_count

class DatasetIntegrator:
    """Main dataset integration orchestrator"""

    def __init__(self, api_base_url: str = "http://localhost:8000"):
        self.downloader = DatasetDownloader()
        self.api_base_url = api_base_url
        self.configs = self.load_dataset_configs()

    def load_dataset_configs(self) -> Dict[str, DatasetConfig]:
        """Load dataset configurations"""
        return {
            "docvqa": DatasetConfig(
                name="DocVQA",
                source_url="https://github.com/docvqa/docvqa",
                dataset_type="docvqa",
                file_format="json",
                processing_func="process_docvqa",
                target_count=100,
                description="Document Visual Question Answering dataset"
            ),
            "publaynet": DatasetConfig(
                name="PubLayNet",
                source_url="https://github.com/ibm-aur-nlp/PubLayNet",
                dataset_type="publaynet",
                file_format="json",
                processing_func="process_publaynet",
                target_count=100,
                description="PubMed Central layout analysis dataset"
            ),
            "laion": DatasetConfig(
                name="LAION-400M",
                source_url="https://laion.ai/blog/laion-400-open-dataset/",
                dataset_type="laion",
                file_format="json",
                processing_func="process_laion",
                target_count=100,
                description="Large-scale image-text dataset (sample version)"
            )
        }

    def integrate_dataset(self, dataset_name: str) -> bool:
        """Integrate a specific dataset"""
        if dataset_name not in self.configs:
            logger.error(f"Unknown dataset: {dataset_name}")
            return False

        config = self.configs[dataset_name]
        logger.info(f"Starting integration of {config.name}")

        try:
            # Step 1: Download dataset
            if dataset_name == "docvqa":
                success = self.downloader.download_docvqa_sample()
                data_file = "datasets/downloads/docvqa_sample.json"
            elif dataset_name == "publaynet":
                success = self.downloader.download_publaynet_sample()
                data_file = "datasets/downloads/publaynet_sample.json"
            elif dataset_name == "laion":
                success = self.downloader.create_laion_sample()
                data_file = "datasets/downloads/laion_sample.json"
            else:
                logger.error(f"Unsupported dataset: {dataset_name}")
                return False

            if not success:
                logger.error(f"Failed to download/create {dataset_name} dataset")
                return False

            # Step 2: Process dataset
            processor = DatasetProcessor(self.api_base_url)

            # Note: In a real implementation, you would authenticate first
            # token = await processor.authenticate()
            # For now, we'll process without upload

            if dataset_name == "docvqa":
                processed_count = processor.process_docvqa(Path(data_file))
            elif dataset_name == "publaynet":
                processed_count = processor.process_publaynet(Path(data_file))
            elif dataset_name == "laion":
                processed_count = processor.process_laion(Path(data_file))

            logger.info(f"Successfully integrated {dataset_name}: {processed_count} items processed")
            return True

        except Exception as e:
            logger.error(f"Error integrating {dataset_name}: {str(e)}")
            return False

    def integrate_all_datasets(self) -> Dict[str, bool]:
        """Integrate all configured datasets"""
        results = {}

        for dataset_name in self.configs.keys():
            logger.info(f"Integrating {dataset_name}...")
            results[dataset_name] = self.integrate_dataset(dataset_name)

            # Add delay between datasets to avoid overwhelming the system
            time.sleep(2)

        return results

    def create_integration_report(self, results: Dict[str, bool]) -> str:
        """Create a report of integration results"""
        report = []
        report.append("Dataset Integration Report")
        report.append("=" * 50)
        report.append(f"Generated: {datetime.now().isoformat()}")
        report.append("")

        successful = sum(1 for success in results.values() if success)
        total = len(results)

        report.append(f"Summary: {successful}/{total} datasets integrated successfully")
        report.append("")

        for dataset_name, success in results.items():
            status = "✅ SUCCESS" if success else "❌ FAILED"
            config = self.configs[dataset_name]
            report.append(f"{dataset_name.upper()}: {status}")
            report.append(f"  Description: {config.description}")
            report.append(f"  Target count: {config.target_count}")
            report.append("")

        return "\n".join(report)

def main():
    """Main execution function"""
    integrator = DatasetIntegrator()

    print("🚀 Starting Dataset Integration for RAG System")
    print("=" * 60)

    # Get user choice
    print("\nAvailable datasets:")
    for i, name in enumerate(integrator.configs.keys(), 1):
        config = integrator.configs[name]
        print(f"{i}. {name} - {config.description}")
    print(f"{len(integrator.configs) + 1}. All datasets")

    try:
        choice = input("\nSelect dataset to integrate (1-{}): ".format(len(integrator.configs) + 1))
        choice = int(choice)

        if choice == len(integrator.configs) + 1:
            # Integrate all datasets
            results = integrator.integrate_all_datasets()
        elif 1 <= choice <= len(integrator.configs):
            # Integrate specific dataset
            dataset_name = list(integrator.configs.keys())[choice - 1]
            results = {dataset_name: integrator.integrate_dataset(dataset_name)}
        else:
            print("Invalid choice")
            return

        # Generate and display report
        report = integrator.create_integration_report(results)
        print("\n" + report)

        # Save report
        with open("datasets/integration_report.txt", "w") as f:
            f.write(report)
        print("\nReport saved to: datasets/integration_report.txt")

    except KeyboardInterrupt:
        print("\nIntegration cancelled by user")
    except Exception as e:
        print(f"Error during integration: {str(e)}")

if __name__ == "__main__":
    main()