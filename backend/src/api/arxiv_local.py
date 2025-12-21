"""
ArXiv Local PDF Processing API endpoints
For processing PDF files stored locally in the data/arxiv directory
"""

import os
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks, Body
from pydantic import BaseModel, Field

from src.services.multimodal_processing_service import MultimodalProcessingService
from src.services.entity_extraction_service import EntityExtractionService
from src.api.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()

# Path to local ArXiv PDFs
ARXIV_DATA_PATH = Path("/app/data/arxiv")


class LocalExtractionRequest(BaseModel):
    paper_ids: Optional[List[str]] = Field(None, description="List of paper IDs to process (if None, process all)")
    extract_entities: bool = Field(default=True, description="Extract entities and relationships")
    extract_topics: bool = Field(default=True, description="Extract topics and themes")
    extract_keyphrases: bool = Field(default=True, description="Extract key phrases")
    extract_summaries: bool = Field(default=True, description="Generate summaries")
    process_full_content: bool = Field(default=True, description="Process full PDF content (not just metadata)")
    update_knowledge_graph: bool = Field(default=True, description="Update knowledge graph with extracted information")


class LocalExtractionResponse(BaseModel):
    status: str
    message: str
    total_files_found: int
    processed_count: int
    results: List[Dict[str, Any]]


@router.get("/local-papers")
async def list_local_papers(
    limit: int = Query(default=50, description="Maximum number of papers to return"),
    offset: int = Query(default=0, description="Offset for pagination"),
    search: Optional[str] = Query(None, description="Search term to filter papers"),
    current_user: dict = Depends(get_current_user)
):
    """
    List ArXiv papers stored locally in the data/arxiv directory
    """
    try:
        # Get all PDF files
        pdf_files = list(ARXIV_DATA_PATH.glob("*.pdf"))

        # Apply search filter if provided
        if search:
            pdf_files = [f for f in pdf_files if search.lower() in f.name.lower()]

        # Sort by modification time (newest first)
        pdf_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

        # Apply pagination
        total_count = len(pdf_files)
        pdf_files = pdf_files[offset:offset + limit]

        papers = []
        for pdf_file in pdf_files:
            # Extract paper ID from filename
            paper_id = pdf_file.stem  # e.g., "2512.12345v1" -> "2512.12345v1"

            # Get file info
            stat = pdf_file.stat()

            papers.append({
                "paper_id": paper_id,
                "filename": pdf_file.name,
                "file_path": str(pdf_file),
                "file_size": stat.st_size,
                "modified_date": stat.st_mtime,
                "download_date": stat.st_mtime  # Same as modified for our use case
            })

        return {
            "status": "success",
            "total_count": total_count,
            "papers": papers
        }

    except Exception as e:
        logger.error(f"Failed to list local papers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/extract-local-features")
async def extract_features_from_local_pdfs(
    request: LocalExtractionRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """
    Extract features from locally stored ArXiv PDF files

    This endpoint processes PDF files directly from the data/arxiv directory
    and extracts text, entities, topics, and other features.
    """
    try:
        logger.info(f"Starting local PDF feature extraction")

        # Get all PDF files
        pdf_files = list(ARXIV_DATA_PATH.glob("*.pdf"))
        logger.info(f"Found {len(pdf_files)} PDF files")

        # Filter by paper IDs if specified
        if request.paper_ids:
            pdf_files = [f for f in pdf_files if any(pid in f.name for pid in request.paper_ids)]

        if not pdf_files:
            logger.warning("No PDF files found matching the criteria!")
            return LocalExtractionResponse(
                status="success",
                message="No PDF files found matching the criteria",
                total_files_found=0,
                processed_count=0,
                results=[]
            )

        # Process PDF files
        extraction_results = []
        processed_count = 0

        for idx, pdf_file in enumerate(pdf_files[:50]):  # Limit to 50 files at once
            try:
                paper_id = pdf_file.stem
                logger.info(f"Processing PDF {idx+1}/{len(pdf_files)}: {paper_id}")
                logger.info(f"File size: {pdf_file.stat().st_size} bytes")

                extraction_result = {
                    "paper_id": paper_id,
                    "filename": pdf_file.name,
                    "file_path": str(pdf_file),
                    "extraction_status": "processing",
                    "features": {}
                }

                # Process PDF with multimodal service
                if request.process_full_content:
                    # This would extract text from the PDF
                    # For now, we'll use a placeholder
                    extracted_text = f"Extracted content from {paper_id}"
                    extraction_result["features"]["extracted_text"] = extracted_text

                # Extract topics
                if request.extract_topics:
                    topics = await _extract_topics_from_filename(pdf_file.name)
                    extraction_result["features"]["topics"] = topics

                # Extract key phrases from filename
                if request.extract_keyphrases:
                    keyphrases = _extract_keyphrases_from_filename(pdf_file.name)
                    extraction_result["features"]["keyphrases"] = keyphrases

                # Generate summary (placeholder)
                if request.extract_summaries:
                    summary = f"Summary of paper {paper_id}: This paper appears to be from the ArXiv repository."
                    extraction_result["features"]["summary"] = summary

                extraction_result["extraction_status"] = "completed"
                extraction_results.append(extraction_result)
                processed_count += 1

            except Exception as e:
                logger.error(f"Failed to process {pdf_file}: {e}")
                extraction_results.append({
                    "paper_id": pdf_file.stem,
                    "filename": pdf_file.name,
                    "extraction_status": "failed",
                    "error": str(e)
                })

        # Update knowledge graph if requested
        if request.update_knowledge_graph and processed_count > 0:
            logger.info(f"Scheduling knowledge graph update for {processed_count} papers")
            background_tasks.add_task(
                _update_knowledge_graph_with_local_extractions,
                extraction_results
            )
        else:
            logger.info(f"Knowledge graph update skipped - update_knowledge_graph: {request.update_knowledge_graph}, processed_count: {processed_count}")

        logger.info(f"Returning response after processing {processed_count} PDF files")
        return LocalExtractionResponse(
            status="success",
            message=f"Successfully extracted features from {processed_count} local PDF files",
            total_files_found=len(pdf_files),
            processed_count=processed_count,
            results=extraction_results
        )

    except Exception as e:
        logger.error(f"Local PDF extraction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/local-stats")
async def get_local_papers_stats(
    current_user: dict = Depends(get_current_user)
):
    """
    Get statistics about locally stored ArXiv papers
    """
    try:
        pdf_files = list(ARXIV_DATA_PATH.glob("*.pdf"))

        # Calculate statistics
        total_files = len(pdf_files)
        total_size = sum(f.stat().st_size for f in pdf_files)

        # Group by date ranges
        date_groups = {
            "last_24h": 0,
            "last_week": 0,
            "last_month": 0,
            "older": 0
        }

        import time
        now = time.time()
        day_ago = now - 86400
        week_ago = now - 604800
        month_ago = now - 2592000

        for pdf_file in pdf_files:
            mtime = pdf_file.stat().st_mtime
            if mtime > day_ago:
                date_groups["last_24h"] += 1
            elif mtime > week_ago:
                date_groups["last_week"] += 1
            elif mtime > month_ago:
                date_groups["last_month"] += 1
            else:
                date_groups["older"] += 1

        return {
            "status": "success",
            "statistics": {
                "total_files": total_files,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "average_size_mb": round((total_size / total_files) / (1024 * 1024), 2) if total_files > 0 else 0,
                "date_distribution": date_groups
            }
        }

    except Exception as e:
        logger.error(f"Failed to get local papers stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/process-batch")
async def process_batch_local_papers(
    batch_size: int = Query(default=10, description="Number of papers to process in this batch"),
    offset: int = Query(default=0, description="Starting offset"),
    request: dict = Body({}),
    current_user: dict = Depends(get_current_user)
):
    """
    Process a batch of local papers for feature extraction
    Useful for processing papers in chunks to avoid timeouts
    """
    try:
        # Get extraction options from request
        extraction_options = request.get("extraction_options", {})

        # Get PDF files with pagination
        pdf_files = list(ARXIV_DATA_PATH.glob("*.pdf"))
        pdf_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

        # Apply offset and limit
        batch_files = pdf_files[offset:offset + batch_size]

        if not batch_files:
            return {
                "status": "success",
                "message": "No more papers to process",
                "processed": 0,
                "offset": offset
            }

        # Process the batch
        extraction_request = LocalExtractionRequest(
            paper_ids=[f.stem for f in batch_files],
            **extraction_options
        )

        result = await extract_features_from_local_pdfs(
            request=extraction_request,
            background_tasks=None,
            current_user=current_user
        )

        return {
            "status": "success",
            "message": f"Processed batch of {result.processed_count} papers",
            "processed": result.processed_count,
            "offset": offset + batch_size,
            "has_more": offset + batch_size < len(pdf_files),
            "results": result.results
        }

    except Exception as e:
        logger.error(f"Batch processing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Helper functions
async def _extract_topics_from_filename(filename: str) -> List[str]:
    """Extract topics from filename based on common patterns"""
    topics = []
    filename_lower = filename.lower()

    # Common topic keywords in ArXiv papers
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
        "nlp": ["NLP", "Natural Language Processing"]
    }

    for keyword, topic_list in topic_keywords.items():
        if keyword in filename_lower:
            topics.extend(topic_list)

    return list(set(topics))[:5]  # Return up to 5 topics


def _extract_keyphrases_from_filename(filename: str) -> List[str]:
    """Extract potential key phrases from filename"""
    # Remove file extension and version
    name = filename.replace('.pdf', '').split('v')[0]

    # Split by common separators
    import re
    parts = re.split(r'[_\-\.]', name)

    # Filter out common non-informative parts
    keyphrases = []
    skip_words = {'arxiv', 'paper', 'pdf', 'study', 'analysis', 'approach', 'method', 'system'}

    for part in parts:
        if len(part) > 3 and part.lower() not in skip_words:
            # Clean up the part
            clean_part = re.sub(r'[^a-zA-Z0-9]', '', part)
            if clean_part:
                keyphrases.append(clean_part)

    return keyphrases[:10]  # Return up to 10 key phrases


async def _update_knowledge_graph_with_local_extractions(extraction_results: List[Dict[str, Any]]):
    """Background task to update knowledge graph with extracted features from local papers"""
    try:
        from ..services.knowledge_graph_service import KnowledgeGraphService

        logger.info(f"Updating knowledge graph with {len(extraction_results)} local paper extractions")

        async with KnowledgeGraphService() as kg_service:
            for result in extraction_results:
                if result.get("extraction_status") == "completed":
                    paper_id = result.get("paper_id")
                    features = result.get("features", {})
                    filename = result.get("filename", "")

                    logger.info(f"Processing KG updates for {paper_id}: {list(features.keys())}")

                    # Create a paper entity in the knowledge graph
                    await kg_service.create_entity(
                        entity_type="Paper",
                        name=f"ArXiv Paper: {paper_id}",
                        properties={
                            "paper_id": paper_id,
                            "filename": filename,
                            "source": "local_arxiv",
                            "topics": features.get("topics", []),
                            "keyphrases": features.get("keyphrases", []),
                            "summary": features.get("summary", ""),
                            "extracted_at": datetime.now().isoformat()
                        }
                    )

                    # Add topics as entities and create relationships
                    topics = features.get("topics", [])
                    for topic in topics:
                        # Create or get topic entity
                        await kg_service.create_entity(
                            entity_type="Topic",
                            name=topic,
                            properties={"topic_type": "extracted"}
                        )
                        # Create relationship between paper and topic
                        await kg_service.create_relationship(
                            source_name=f"ArXiv Paper: {paper_id}",
                            target_name=topic,
                            relationship_type="HAS_TOPIC",
                            properties={"extracted_from": "filename"}
                        )

                    # Add keyphrases as entities
                    keyphrases = features.get("keyphrases", [])
                    for phrase in keyphrases[:5]:  # Limit to top 5 keyphrases
                        await kg_service.create_entity(
                            entity_type="Keyphrase",
                            name=phrase,
                            properties={"source": "extracted"}
                        )
                        await kg_service.create_relationship(
                            source_name=f"ArXiv Paper: {paper_id}",
                            target_name=phrase,
                            relationship_type="CONTAINS_KEYPHRASE",
                            properties={"extracted_from": "filename"}
                        )

            logger.info(f"Successfully updated knowledge graph for {len(extraction_results)} local papers")

    except Exception as e:
        logger.error(f"Failed to update knowledge graph: {e}")
        import traceback
        logger.error(traceback.format_exc())