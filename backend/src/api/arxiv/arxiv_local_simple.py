"""
Simple ArXiv Local PDF Processing - No Full Content Processing
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from src.core.dependencies import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()

# Path to local ArXiv PDFs
ARXIV_DATA_PATH = Path("/Users/goodwiinz/development/RAG_system/data/arxiv")


@router.post("/extract-local-features-simple")
async def extract_features_simple(current_user: dict = Depends(get_current_user)):
    """
    Simple PDF feature extraction without processing full content
    """
    try:
        logger.info(
            f"Simple PDF extraction request from user {current_user.get('email')}"
        )

        # Get all PDF files
        pdf_files = list(ARXIV_DATA_PATH.glob("*.pdf"))
        logger.info(f"Found {len(pdf_files)} PDF files")

        # Process PDF files quickly - just extract from filenames
        extraction_results = []
        processed_count = 0

        for idx, pdf_file in enumerate(pdf_files):
            try:
                paper_id = pdf_file.stem
                logger.info(f"Processing {idx+1}/{len(pdf_files)}: {paper_id}")

                # Extract features from filename only (no PDF processing)
                features = {
                    "topics": _extract_topics_from_filename(pdf_file.name),
                    "keyphrases": _extract_keyphrases_from_filename(pdf_file.name),
                    "summary": f"Paper {paper_id} from ArXiv repository",
                }

                extraction_result = {
                    "paper_id": paper_id,
                    "filename": pdf_file.name,
                    "extraction_status": "completed",
                    "features": features,
                }
                extraction_results.append(extraction_result)
                processed_count += 1

                # Log progress every 10 files
                if processed_count % 10 == 0:
                    logger.info(f"Processed {processed_count} files so far...")

            except Exception as e:
                logger.error(f"Failed to process {pdf_file}: {e}")
                extraction_results.append(
                    {
                        "paper_id": pdf_file.stem,
                        "filename": pdf_file.name,
                        "extraction_status": "failed",
                        "error": str(e),
                    }
                )

        logger.info(f"Completed processing {processed_count} PDF files")

        return {
            "status": "success",
            "message": f"Successfully processed {processed_count} PDF files",
            "total_files_found": len(pdf_files),
            "processed_count": processed_count,
            "results": extraction_results,
        }

    except Exception as e:
        logger.error(f"Simple PDF extraction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _extract_topics_from_filename(filename: str) -> List[str]:
    """Extract topics from filename based on common patterns"""
    topics = []
    filename_lower = filename.lower()

    topic_keywords = {
        "learning": ["Machine Learning", "Deep Learning"],
        "neural": ["Neural Networks", "Deep Learning"],
        "quantum": ["Quantum Computing", "Quantum Physics"],
        "optimization": ["Optimization", "Mathematical Optimization"],
        "algorithm": ["Algorithms", "Computer Science"],
        "network": ["Networks", "Graph Theory"],
        "analysis": ["Data Analysis", "Statistical Analysis"],
        "classification": ["Classification", "Machine Learning"],
        "detection": ["Object Detection", "Pattern Recognition"],
        "attention": ["Attention Mechanism", "Transformers"],
        "transformer": ["Transformers", "NLP"],
        "clustering": ["Clustering", "Unsupervised Learning"],
        "reinforcement": ["Reinforcement Learning", "RL"],
        "cnn": ["CNN", "Computer Vision"],
        "gan": ["GAN", "Generative Models"],
        "graph": ["Graph Neural Networks", "GNN"],
        "nlp": ["NLP", "Natural Language Processing"],
    }

    for keyword, topic_list in topic_keywords.items():
        if keyword in filename_lower:
            topics.extend(topic_list)

    return list(set(topics))[:5]


def _extract_keyphrases_from_filename(filename: str) -> List[str]:
    """Extract potential key phrases from filename"""
    import re

    name = filename.replace(".pdf", "").split("v")[0]
    parts = re.split(r"[_\-\.]", name)

    keyphrases = []
    skip_words = {
        "arxiv",
        "paper",
        "pdf",
        "study",
        "analysis",
        "approach",
        "method",
        "system",
    }

    for part in parts:
        if len(part) > 3 and part.lower() not in skip_words:
            clean_part = re.sub(r"[^a-zA-Z0-9]", "", part)
            if clean_part:
                keyphrases.append(clean_part)

    return keyphrases[:10]
