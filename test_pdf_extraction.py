#!/usr/bin/env python3
"""
Test script to verify PDF text extraction is working
"""

import os
import sys
import asyncio
import uuid
from pathlib import Path

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from src.services.multimodal_processing_service import MultimodalProcessingService
from src.shared.schemas import Document, ProcessingJob


async def test_pdf_extraction():
    """Test PDF text extraction on a sample file"""

    # Path to ArXiv PDFs
    arxiv_path = Path("/Users/goodwiinz/development/RAG_system/data/arxiv")

    # Find a PDF file
    pdf_files = list(arxiv_path.glob("*.pdf"))
    if not pdf_files:
        print("No PDF files found!")
        return

    pdf_file = pdf_files[0]
    print(f"\nTesting extraction on: {pdf_file.name}")
    print(f"File size: {pdf_file.stat().st_size} bytes")

    try:
        # Create document object
        doc = Document(
            id=str(uuid.uuid4()),
            filename=pdf_file.name,
            file_path=str(pdf_file),
            file_type="pdf",
            title=f"Test: {pdf_file.stem}",
            status="processing"
        )

        # Create processing job
        job = ProcessingJob(
            id=str(uuid.uuid4()),
            document_id=doc.id,
            job_type="pdf_extraction",
            status="pending"
        )

        # Process the PDF
        multimodal_service = MultimodalProcessingService()
        result = await multimodal_service.process_pdf(doc, job)

        # Display results
        if "error" in result:
            print(f"❌ Error: {result['error']}")
            return

        print("\n✅ Extraction Results:")
        print(f"Page count: {result.get('page_count', 0)}")
        print(f"Images extracted: {result.get('images_extracted', 0)}")

        # Show metadata
        metadata = result.get('metadata', {})
        if metadata:
            print("\n📄 Metadata:")
            print(f"  Title: {metadata.get('title', 'N/A')}")
            print(f"  Author: {metadata.get('author', 'N/A')}")
            print(f"  Subject: {metadata.get('subject', 'N/A')}")

        # Show text preview
        text_content = result.get('text_content', '')
        if text_content:
            print(f"\n📝 Text length: {len(text_content)} characters")
            print("\nFirst 500 characters:")
            print("-" * 50)
            print(text_content[:500])
            print("-" * 50)

            # Extract potential title
            lines = text_content.split('\n')[:10]
            print("\nPotential title lines:")
            for i, line in enumerate(lines[:5]):
                if line.strip() and len(line.strip()) < 200:
                    print(f"  Line {i+1}: {line.strip()[:80]}")

    except Exception as e:
        print(f"❌ Error during extraction: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_pdf_extraction())