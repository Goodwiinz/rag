#!/usr/bin/env python3
"""
Index Full Paper PDFs to Qdrant

This script extracts full text from ArXiv PDFs and indexes them to Qdrant
for improved RAG performance. Unlike the abstract-only indexing, this
provides full context for answering questions about methodology, results,
limitations, and future work.
"""

import sys
import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional
import re
import io
try:
    import fitz  # PyMuPDF
    import pytesseract
    from PIL import Image
    PYMUPDF_AVAILABLE = True
except ImportError:
    import PyPDF2
    PYMUPDF_AVAILABLE = False


# Load environment from backend/.env BEFORE importing services
from dotenv import load_dotenv
backend_env = os.path.join(os.path.dirname(__file__), '../backend/.env')
load_dotenv(backend_env, override=True)
print(f"✅ Loaded environment from {backend_env}")

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../backend'))

# Import and reinitialize services to pick up environment variables
from src.core.config import settings

# Force reload settings from environment
import importlib
from src.core import config as config_module
importlib.reload(config_module)
settings = config_module.settings

# Now import and reinitialize services
from src.services import azure_openai_service as aos_module
importlib.reload(aos_module)

from src.services import embedding_service as es_module  
importlib.reload(es_module)

from src.services import vector_search_service as vss_module
importlib.reload(vss_module)

vector_search_service = vss_module.vector_search_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def _clean_extracted_text(text: str) -> str:
    """Clean and preprocess extracted text"""
    try:
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove common PDF artifacts
        text = re.sub(r'\f', '\n', text)  # Form feeds
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)  # Control characters
        
        # Fix common OCR errors
        text = re.sub(r'\|', 'I', text)  # Vertical bars to I
        
        # Normalize line breaks
        text = re.sub(r'\n\s*\n', '\n\n', text)  # Multiple empty lines to double newline
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text.strip()
    except Exception as e:
        logger.warning(f"Text cleaning failed: {str(e)}")
        return text

def extract_pdf_text_pymupdf(pdf_path: Path) -> Optional[str]:
    """Extract text from a PDF file using PyMuPDF with OCR fallback"""
    try:
        # First attempt: Extract text directly
        text = []
        try:
            doc = fitz.open(pdf_path)
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                page_text = page.get_text()
                
                if page_text.strip():
                    text.append(page_text)
                else:
                    # If no text found, try OCR
                    logger.info(f"Page {page_num+1} has no text, trying OCR...")
                    pix = page.get_pixmap()
                    img_data = pix.tobytes("png")
                    img = Image.open(io.BytesIO(img_data))
                    ocr_text = pytesseract.image_to_string(img)
                    if ocr_text.strip():
                        text.append(f"[OCR Page {page_num + 1}]\n{ocr_text}")
            
            doc.close()
            
        except Exception as pdf_error:
            logger.warning(f"Direct PDF extraction failed: {pdf_error}. Trying complete OCR fallback.")
            # Fallback: Convert all pages to images and OCR them
            try:
                doc = fitz.open(pdf_path)
                text = [] # Reset text
                for page_num in range(len(doc)):
                    page = doc.load_page(page_num)
                    pix = page.get_pixmap()
                    img_data = pix.tobytes("png")
                    img = Image.open(io.BytesIO(img_data))
                    ocr_text = pytesseract.image_to_string(img)
                    if ocr_text.strip():
                        text.append(f"[OCR Page {page_num + 1}]\n{ocr_text}")
                doc.close()
            except Exception as ocr_error:
                logger.error(f"OCR fallback also failed: {ocr_error}")
                return None

        extracted_text = '\n'.join(text)
        
        # Post-process and clean the text
        if extracted_text:
            extracted_text = _clean_extracted_text(extracted_text)
            
        return extracted_text

    except Exception as e:
        logger.error(f"Failed to extract PDF {pdf_path}: {e}")
        return None

def extract_pdf_text(pdf_path: Path) -> Optional[str]:
    """Extract text from a PDF file"""
    if PYMUPDF_AVAILABLE:
        return extract_pdf_text_pymupdf(pdf_path)
        
    # Fallback to PyPDF2 if PyMuPDF not available (legacy)
    try:
        with open(pdf_path, 'rb') as f:
            pdf_reader = PyPDF2.PdfReader(f)
            
            full_text = []
            for page_num, page in enumerate(pdf_reader.pages):
                try:
                    page_text = page.extract_text()
                    if page_text:
                        full_text.append(f"[Page {page_num + 1}]\n{page_text}")
                except Exception as e:
                    logger.warning(f"Failed to extract text from page {page_num + 1}: {e}")
            
            return "\n\n".join(full_text)
    except Exception as e:
        logger.error(f"Failed to extract PDF {pdf_path}: {e}")
        return None


def find_pdf_for_paper(paper_id: str, pdf_dir: Path) -> Optional[Path]:
    """Find the PDF file for a given paper ID"""
    # Try exact match first
    pdf_path = pdf_dir / f"{paper_id}.pdf"
    if pdf_path.exists():
        return pdf_path
    
    # Try without version suffix (e.g., 2512.16920 instead of 2512.16920v1)
    base_id = paper_id.replace('v1', '').replace('v2', '').replace('v3', '')
    pdf_path = pdf_dir / f"{base_id}.pdf"
    if pdf_path.exists():
        return pdf_path
    
    return None


def load_evaluation_dataset(dataset_path: Path) -> List[Dict]:
    """Load the evaluation dataset"""
    with open(dataset_path, 'r') as f:
        data = json.load(f)
    return data.get('test_cases', [])


def index_full_papers(
    dataset_path: Path,
    pdf_dir: Path,
    chunk_size: int = 1000,
    overlap: int = 200,
    clear_existing: bool = False
):
    """
    Index full paper PDFs to Qdrant
    
    Args:
        dataset_path: Path to evaluation dataset JSON
        pdf_dir: Directory containing PDF files
        chunk_size: Size of text chunks for embedding
        overlap: Overlap between chunks
        clear_existing: Whether to clear existing vectors first
    """
    print("=" * 60)
    print("📚 FULL PAPER PDF INDEXING (Azure OpenAI 1536d)")
    print("=" * 60)
    
    # Verify Azure OpenAI is available
    from src.services.azure_openai_service import azure_openai_service
    from src.services.embedding_service import embedding_service
    
    if not azure_openai_service.is_embedding_available():
        print("❌ ERROR: Azure OpenAI embedding service is NOT available!")
        print("   Please check your AZURE_OPENAI_EMBEDDING_ENDPOINT and API keys in backend/.env")
        return
    
    print(f"✅ Azure OpenAI embedding service is available")
    print(f"   Provider: {embedding_service.embedding_provider}")
    print(f"   Dimension: {embedding_service.embedding_dimension}")
    
    # Load papers from dataset
    papers = load_evaluation_dataset(dataset_path)
    print(f"📄 Found {len(papers)} papers in dataset")
    
    # Count available PDFs
    available_pdfs = list(pdf_dir.glob("*.pdf"))
    print(f"📁 Found {len(available_pdfs)} PDFs in {pdf_dir}")
    
    if clear_existing:
        print("🗑️  Clearing existing vectors and recreating collection...")
        try:
            from src.models.vector import VectorCollectionType
            # Delete the existing collection
            vector_search_service.vector_service.delete_collection(
                VectorCollectionType.DOCUMENT_CHUNKS
            )
            # Recreate with correct dimension for Azure OpenAI (1536)
            vector_search_service.vector_service.ensure_collection_exists(
                VectorCollectionType.DOCUMENT_CHUNKS,
                vector_size=1536  # Azure OpenAI text-embedding-ada-002 dimension
            )
            print("   ✅ Recreated collection with 1536-dim Azure OpenAI vectors")
        except Exception as e:
            print(f"   ⚠️  Could not recreate collection: {e}")
    
    print("\n" + "-" * 60)
    print("Starting indexing...\n")
    
    success_count = 0
    pdf_found_count = 0
    total_chunks = 0
    
    for i, paper in enumerate(papers):
        paper_id = paper.get('paper_id', '')
        title = paper.get('paper_title', '')[:50]
        
        print(f"[{i+1}/{len(papers)}] {paper_id} - '{title}...'")
        
        # Find PDF for this paper
        pdf_path = find_pdf_for_paper(paper_id, pdf_dir)
        
        if not pdf_path:
            print(f"   ⚠️  PDF not found, using abstract only")
            # Fall back to abstract indexing
            text = f"""Title: {paper.get('paper_title', '')}
Authors: {', '.join(paper.get('authors', []))}
Categories: {', '.join(paper.get('categories', []))}

Abstract:
{paper.get('paper_abstract', '')}"""
        else:
            pdf_found_count += 1
            print(f"   📄 Found PDF: {pdf_path.name}")
            
            # Extract full text from PDF
            pdf_text = extract_pdf_text(pdf_path)
            
            if pdf_text and len(pdf_text) > 500:
                # Prepend metadata for better context
                text = f"""Title: {paper.get('paper_title', '')}
Authors: {', '.join(paper.get('authors', []))}
Categories: {', '.join(paper.get('categories', []))}

{pdf_text}"""
                print(f"   📝 Extracted {len(pdf_text):,} characters")
            else:
                print(f"   ⚠️  PDF extraction yielded little text, using abstract")
                text = f"""Title: {paper.get('paper_title', '')}
Authors: {', '.join(paper.get('authors', []))}
Categories: {', '.join(paper.get('categories', []))}

Abstract:
{paper.get('paper_abstract', '')}"""
        
        # Prepare metadata
        metadata = {
            "title": paper.get('paper_title', ''),
            "authors": ', '.join(paper.get('authors', [])),
            "categories": ', '.join(paper.get('categories', [])),
            "published": paper.get('published', ''),
            "pdf_link": paper.get('pdf_link', ''),
            "document_id": paper_id,
            "arxiv_id": paper_id,
            "has_full_text": pdf_path is not None,
            "primary_category": paper.get('primary_category', '')
        }
        
        # Index the document
        try:
            result = vector_search_service.index_document(
                document_id=paper_id,
                text=text,
                organization_id="arxiv_eval",
                content_type="text",
                source_type="arxiv_paper",
                chunk_size=chunk_size,
                overlap=overlap,
                metadata=metadata
            )
            
            if result.success:
                success_count += 1
                # Parse chunk count from message if available
                if "chunks" in result.message:
                    import re
                    match = re.search(r'(\d+) chunks', result.message)
                    if match:
                        total_chunks += int(match.group(1))
                print(f"   ✅ Indexed successfully")
            else:
                print(f"   ❌ Failed: {result.message}")
                if result.error:
                    print(f"      Error: {result.error}")
                    
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 INDEXING SUMMARY")
    print("=" * 60)
    print(f"Total papers processed: {len(papers)}")
    print(f"PDFs found and extracted: {pdf_found_count}")
    print(f"Successfully indexed: {success_count}")
    print(f"Total chunks created: {total_chunks}")
    print(f"Success rate: {success_count/len(papers)*100:.1f}%")
    print("=" * 60)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Index full paper PDFs to Qdrant")
    parser.add_argument(
        "--dataset",
        type=str,
        default="backend/data/arxiv/evaluation_dataset_improved.json",
        help="Path to evaluation dataset JSON"
    )
    parser.add_argument(
        "--pdf-dir",
        type=str,
        default="data/arxiv",
        help="Directory containing PDF files"
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=1000,
        help="Size of text chunks for embedding"
    )
    parser.add_argument(
        "--overlap",
        type=int,
        default=200,
        help="Overlap between chunks"
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing vectors before indexing"
    )
    
    args = parser.parse_args()
    
    # Resolve paths
    project_root = Path(__file__).parent.parent
    dataset_path = project_root / args.dataset
    pdf_dir = project_root / args.pdf_dir
    
    if not dataset_path.exists():
        print(f"❌ Dataset not found: {dataset_path}")
        sys.exit(1)
    
    if not pdf_dir.exists():
        print(f"❌ PDF directory not found: {pdf_dir}")
        sys.exit(1)
    
    index_full_papers(
        dataset_path=dataset_path,
        pdf_dir=pdf_dir,
        chunk_size=args.chunk_size,
        overlap=args.overlap,
        clear_existing=args.clear
    )


if __name__ == "__main__":
    main()
