#!/usr/bin/env python3
"""
API Client for Dataset Upload to RAG System
Handles bulk upload of processed datasets with proper authentication and metadata
"""

import asyncio
import aiohttp
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, AsyncGenerator
from dataclasses import dataclass, asdict
from datetime import datetime
import base64
import hashlib
from concurrent.futures import ThreadPoolExecutor
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class UploadConfig:
    """Configuration for dataset upload"""
    batch_size: int = 10
    max_retries: int = 3
    retry_delay: float = 1.0
    timeout: int = 30
    max_concurrent_uploads: int = 5

@dataclass
class DocumentMetadata:
    """Metadata for uploaded documents"""
    source: str
    dataset_type: str
    original_id: str
    created_at: datetime
    tags: List[str]
    language: str = "en"
    quality_score: float = 1.0

@dataclass
class UploadResult:
    """Result of upload operation"""
    success: bool
    document_id: Optional[str]
    error_message: Optional[str]
    upload_time: float
    status_code: Optional[int]

class DatasetUploader:
    """Handles uploading of datasets to RAG system API"""

    def __init__(self, api_base_url: str = "http://localhost:8000", config: UploadConfig = None):
        self.api_base_url = api_base_url
        self.config = config or UploadConfig()
        self.session: Optional[aiohttp.ClientSession] = None
        self.access_token: Optional[str] = None
        self.upload_stats = {
            "total_documents": 0,
            "successful_uploads": 0,
            "failed_uploads": 0,
            "total_time": 0.0,
            "errors": []
        }

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.config.timeout)
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def authenticate(self, username: str = "admin", password: str = "REDACTED") -> bool:
        """Authenticate with the RAG system"""
        try:
            async with self.session.post(
                f"{self.api_base_url}/auth/login",
                json={"username": username, "password": password}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self.access_token = data.get("access_token")
                    logger.info("Authentication successful")
                    return True
                else:
                    logger.error(f"Authentication failed: {response.status}")
                    return False

        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return False

    def get_headers(self) -> Dict[str, str]:
        """Get headers with authentication"""
        headers = {"Content-Type": "application/json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    async def upload_document(self, document: Dict[str, Any], metadata: DocumentMetadata) -> UploadResult:
        """Upload a single document to the RAG system"""
        start_time = time.time()

        for attempt in range(self.config.max_retries):
            try:
                # Prepare payload
                payload = {
                    "title": document.get("title", ""),
                    "content": document.get("content", ""),
                    "metadata": {
                        **asdict(metadata),
                        **document.get("metadata", {})
                    }
                }

                async with self.session.post(
                    f"{self.api_base_url}/documents",
                    json=payload,
                    headers=self.get_headers()
                ) as response:
                    upload_time = time.time() - start_time

                    if response.status == 201:
                        data = await response.json()
                        return UploadResult(
                            success=True,
                            document_id=data.get("id"),
                            error_message=None,
                            upload_time=upload_time,
                            status_code=response.status
                        )
                    else:
                        error_text = await response.text()
                        if attempt == self.config.max_retries - 1:
                            return UploadResult(
                                success=False,
                                document_id=None,
                                error_message=f"HTTP {response.status}: {error_text}",
                                upload_time=upload_time,
                                status_code=response.status
                            )
                        logger.warning(f"Upload attempt {attempt + 1} failed: {response.status}")
                        await asyncio.sleep(self.config.retry_delay)

            except Exception as e:
                if attempt == self.config.max_retries - 1:
                    return UploadResult(
                        success=False,
                        document_id=None,
                        error_message=str(e),
                        upload_time=time.time() - start_time,
                        status_code=None
                    )
                logger.warning(f"Upload attempt {attempt + 1} error: {str(e)}")
                await asyncio.sleep(self.config.retry_delay)

        return UploadResult(
            success=False,
            document_id=None,
            error_message="Max retries exceeded",
            upload_time=time.time() - start_time,
            status_code=None
        )

    async def upload_batch(self, documents: List[Dict[str, Any]], metadata_base: DocumentMetadata) -> List[UploadResult]:
        """Upload a batch of documents concurrently"""
        semaphore = asyncio.Semaphore(self.config.max_concurrent_uploads)

        async def upload_with_semaphore(doc_data: tuple) -> UploadResult:
            doc, idx = doc_data
            metadata = DocumentMetadata(
                **{**asdict(metadata_base), "original_id": f"{metadata_base.original_id}_{idx}"}
            )
            async with semaphore:
                return await self.upload_document(doc, metadata)

        tasks = [upload_with_semaphore((doc, i)) for i, doc in enumerate(documents)]
        return await asyncio.gather(*tasks, return_exceptions=True)

    def process_docvqa_documents(self, data_path: Path) -> List[Dict[str, Any]]:
        """Process DocVQA data into uploadable documents"""
        with open(data_path, 'r') as f:
            data = json.load(f)

        documents = []
        for item in data.get('data', []):
            doc = {
                "title": f"DocVQA Question: {item.get('question', '')[:100]}",
                "content": f"Question: {item.get('question', '')}\n\nAnswer: {item.get('answer', '')}",
                "metadata": {
                    "question": item.get('question', ''),
                    "answer": item.get('answer', ''),
                    "document_id": item.get('doc_id', ''),
                    "page_number": item.get('page_num', 0),
                    "dataset_source": "docvqa"
                }
            }
            documents.append(doc)

        return documents

    def process_publaynet_documents(self, data_path: Path) -> List[Dict[str, Any]]:
        """Process PubLayNet data into uploadable documents"""
        with open(data_path, 'r') as f:
            data = json.load(f)

        documents = []
        for item in data.get('annotations', []):
            content_parts = []
            content_parts.append(f"Layout Type: {item.get('category', 'unknown')}")
            content_parts.append(f"Image ID: {item.get('image_id', '')}")
            content_parts.append(f"Bounding Box: {item.get('bbox', [])}")
            content_parts.append(f"Dimensions: {item.get('width', 0)}x{item.get('height', 0)}")

            doc = {
                "title": f"Layout Analysis: Document {item.get('image_id', '')}",
                "content": "\n".join(content_parts),
                "metadata": {
                    "image_id": item.get('image_id', ''),
                    "layout_type": item.get('category', ''),
                    "bbox": item.get('bbox', []),
                    "width": item.get('width', 0),
                    "height": item.get('height', 0),
                    "dataset_source": "publaynet"
                }
            }
            documents.append(doc)

        return documents

    def process_laion_documents(self, data_path: Path) -> List[Dict[str, Any]]:
        """Process LAION data into uploadable documents"""
        with open(data_path, 'r') as f:
            data = json.load(f)

        documents = []
        for item in data.get('images', []):
            doc = {
                "title": f"Image Caption: {item.get('id', '')}",
                "content": f"Image Description: {item.get('caption', '')}",
                "metadata": {
                    "image_id": item.get('id', ''),
                    "url": item.get('url', ''),
                    "similarity": item.get('similarity', 0.0),
                    "language": item.get('language', 'en'),
                    "width": item.get('width', 0),
                    "height": item.get('height', 0),
                    "hash": item.get('hash', ''),
                    "dataset_source": "laion"
                }
            }
            documents.append(doc)

        return documents

    async def upload_dataset(self, dataset_path: Path, dataset_type: str) -> Dict[str, Any]:
        """Upload an entire dataset"""
        logger.info(f"Starting upload of {dataset_type} dataset from {dataset_path}")

        start_time = time.time()

        try:
            # Process documents based on dataset type
            if dataset_type == "docvqa":
                documents = self.process_docvqa_documents(dataset_path)
            elif dataset_type == "publaynet":
                documents = self.process_publaynet_documents(dataset_path)
            elif dataset_type == "laion":
                documents = self.process_laion_documents(dataset_path)
            else:
                raise ValueError(f"Unsupported dataset type: {dataset_type}")

            logger.info(f"Processed {len(documents)} documents for upload")

            # Create metadata base
            metadata_base = DocumentMetadata(
                source=dataset_type,
                dataset_type=dataset_type,
                original_id=f"{dataset_type}_batch_{int(time.time())}",
                created_at=datetime.now(),
                tags=[dataset_type, "uploaded", datetime.now().strftime("%Y-%m-%d")]
            )

            # Upload in batches
            total_uploads = 0
            successful_uploads = 0
            failed_uploads = 0
            errors = []

            for i in range(0, len(documents), self.config.batch_size):
                batch = documents[i:i + self.config.batch_size]
                logger.info(f"Uploading batch {i//self.config.batch_size + 1}/{(len(documents) + self.config.batch_size - 1)//self.config.batch_size}")

                results = await self.upload_batch(batch, metadata_base)

                for result in results:
                    total_uploads += 1
                    if isinstance(result, Exception):
                        failed_uploads += 1
                        errors.append(str(result))
                    elif result.success:
                        successful_uploads += 1
                    else:
                        failed_uploads += 1
                        errors.append(result.error_message)

                # Small delay between batches
                await asyncio.sleep(0.1)

            total_time = time.time() - start_time

            upload_stats = {
                "dataset_type": dataset_type,
                "total_documents": len(documents),
                "successful_uploads": successful_uploads,
                "failed_uploads": failed_uploads,
                "success_rate": successful_uploads / total_uploads * 100 if total_uploads > 0 else 0,
                "total_time": total_time,
                "avg_time_per_document": total_time / total_uploads if total_uploads > 0 else 0,
                "errors": errors[:10]  # Limit error display
            }

            logger.info(f"Upload completed: {successful_uploads}/{total_uploads} successful ({upload_stats['success_rate']:.1f}%)")
            return upload_stats

        except Exception as e:
            logger.error(f"Dataset upload failed: {str(e)}")
            return {
                "dataset_type": dataset_type,
                "error": str(e),
                "total_time": time.time() - start_time
            }

    async def upload_all_datasets(self, datasets_dir: Path = None) -> Dict[str, Any]:
        """Upload all available datasets"""
        if datasets_dir is None:
            datasets_dir = Path("datasets/downloads")

        dataset_files = {
            "docvqa_sample.json": "docvqa",
            "publaynet_sample.json": "publaynet",
            "laion_sample.json": "laion"
        }

        results = {}

        for filename, dataset_type in dataset_files.items():
            dataset_path = datasets_dir / filename
            if dataset_path.exists():
                logger.info(f"Found {dataset_type} dataset: {dataset_path}")
                result = await self.upload_dataset(dataset_path, dataset_type)
                results[dataset_type] = result
            else:
                logger.warning(f"Dataset file not found: {dataset_path}")
                results[dataset_type] = {"error": "Dataset file not found"}

        return results

    def generate_upload_report(self, results: Dict[str, Any]) -> str:
        """Generate a comprehensive upload report"""
        report = []
        report.append("Dataset Upload Report")
        report.append("=" * 50)
        report.append(f"Generated: {datetime.now().isoformat()}")
        report.append("")

        # Overall statistics
        total_docs = sum(r.get("total_documents", 0) for r in results.values() if "total_documents" in r)
        total_successful = sum(r.get("successful_uploads", 0) for r in results.values() if "successful_uploads" in r)
        total_failed = sum(r.get("failed_uploads", 0) for r in results.values() if "failed_uploads" in r)

        report.append("Overall Statistics:")
        report.append(f"  Total Datasets: {len(results)}")
        report.append(f"  Total Documents: {total_docs}")
        report.append(f"  Successful Uploads: {total_successful}")
        report.append(f"  Failed Uploads: {total_failed}")
        report.append(f"  Overall Success Rate: {(total_successful / total_docs * 100) if total_docs > 0 else 0:.1f}%")
        report.append("")

        # Per-dataset details
        for dataset_type, result in results.items():
            report.append(f"{dataset_type.upper()}:")
            if "error" in result:
                report.append(f"  Status: ❌ FAILED")
                report.append(f"  Error: {result['error']}")
            else:
                report.append(f"  Status: ✅ SUCCESS" if result.get("failed_uploads", 0) == 0 else f"  Status: ⚠️  PARTIAL")
                report.append(f"  Documents: {result.get('successful_uploads', 0)}/{result.get('total_documents', 0)}")
                report.append(f"  Success Rate: {result.get('success_rate', 0):.1f}%")
                report.append(f"  Total Time: {result.get('total_time', 0):.2f}s")
                report.append(f"  Avg Time/Doc: {result.get('avg_time_per_document', 0):.3f}s")

                if result.get("errors"):
                    report.append(f"  Sample Errors: {len(result['errors'])} errors")
                    for error in result["errors"][:3]:
                        report.append(f"    - {error}")
            report.append("")

        return "\n".join(report)

async def main():
    """Main execution function"""
    print("📤 Dataset Upload API Client")
    print("=" * 40)

    config = UploadConfig(
        batch_size=10,
        max_retries=3,
        max_concurrent_uploads=5
    )

    async with DatasetUploader(config=config) as uploader:
        # Authenticate
        print("\n🔐 Authenticating...")
        if not await uploader.authenticate():
            print("❌ Authentication failed. Please check if the RAG system is running.")
            return

        print("✅ Authentication successful")

        # Upload datasets
        print("\n📤 Uploading datasets...")
        results = await uploader.upload_all_datasets()

        # Generate report
        print("\n📊 Generating upload report...")
        report = uploader.generate_upload_report(results)

        # Save report
        report_path = Path("dataset_upload_report.txt")
        with open(report_path, 'w') as f:
            f.write(report)

        print("\n" + report)
        print(f"\n✅ Upload complete! Report saved to: {report_path}")

if __name__ == "__main__":
    asyncio.run(main())