#!/usr/bin/env python3
"""
Re-process PDFs to update knowledge graph with proper topics and embeddings
"""
import sys
sys.path.append('/Users/goodwiinz/development/RAG_system/backend')

import asyncio
import aiofiles
from pathlib import Path
from typing import Dict, Any, List
import logging

from src.services.knowledge_graph_service import KnowledgeGraphService
from src.models.graph import CreateEntityRequest, EntityType, ExtractionMethod, CreateRelationshipRequest, RelationshipType
from src.services.embedding_service import EmbeddingService
from src.services.entity_extraction_service import EntityExtractionService
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Path to uploaded PDFs
UPLOADS_PATH = Path("/Users/goodwiinz/development/RAG_system/uploads/documents")

async def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract text from PDF file"""
    try:
        # Try to use PyPDF2 first
        import PyPDF2

        text = ""
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page_num in range(min(len(pdf_reader.pages), 10)):  # Limit to first 10 pages
                page = pdf_reader.pages[page_num]
                text += page.extract_text() + "\n"

        return text
    except Exception as e:
        logger.error(f"Error extracting text from {pdf_path}: {e}")
        return ""

async def extract_topics_from_text(text: str) -> List[str]:
    """Extract topics from text using keyword patterns"""
    import re
    topics = set()
    text_lower = text.lower()

    # Academic topic keywords
    topic_patterns = {
        'machine learning': r'\bmachine learning\b|\bml\b|\bneural network\b|\bdeep learning\b',
        'computer vision': r'\bcomputer vision\b|\bcv\b|\bimage recognition\b|\bobject detection\b',
        'natural language processing': r'\bnatural language processing\b|\bnlp\b|\btext analysis\b',
        'quantum computing': r'\bquantum computer\b|\bquantum computing\b|\bquantum algorithm\b',
        'robotics': r'\brobotic\b|\brobotics\b|\bautonomous\b',
        'algorithms': r'\balgorithm\b|\boptimization\b|\bcomplexity\b',
        'databases': r'\bdatabase\b|\bdata management\b|\bsql\b|\bnosql\b',
        'security': r'\bcryptography\b|\bsecurity\b|\bprivacy\b|\bencryption\b',
        'graph theory': r'\bgraph\b|\bnetwork\b|\bnode\b|\bedge\b',
        'statistics': r'\bstatistic\b|\bprobability\b|\bbayesian\b',
        'bioinformatics': r'\bbioinformatic\b|\bgenomics\b|\bdna\b|\bprotein\b',
        'distributed systems': r'\bdistributed\b|\bscalable\b|\bparallel\b'
    }

    for topic, pattern in topic_patterns.items():
        if re.search(pattern, text_lower):
            topics.add(topic)

    return list(topics)

async def extract_entities_from_text(text: str) -> List[Dict[str, Any]]:
    """Extract entities from text using spaCy"""
    try:
        entity_service = EntityExtractionService()

        # Create a minimal Document object
        from src.models.document import Document, DocumentType

        doc = Document(
            id=None,
            title="PDF Document",
            content=text,
            document_type=DocumentType.PDF,
            metadata={"source": "pdf_reprocessing"},
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        entities = entity_service.extract_entities_from_text(document=doc, text=text)
        return entities

    except Exception as e:
        logger.error(f"Error extracting entities: {e}")
        return []

async def process_pdf_for_knowledge_graph(pdf_path: Path, kg_service: KnowledgeGraphService):
    """Process a single PDF and update the knowledge graph"""
    logger.info(f"Processing PDF: {pdf_path.name}")

    # Extract text
    text = await extract_text_from_pdf(pdf_path)
    if not text or len(text.strip()) < 100:
        logger.warning(f"No significant text found in {pdf_path.name}")
        return

    # Extract topics
    topics = await extract_topics_from_text(text)
    logger.info(f"Extracted {len(topics)} topics: {topics[:5]}")

    # Extract entities
    entities = await extract_entities_from_text(text)
    logger.info(f"Extracted {len(entities)} entities")

    # Generate embedding using Azure
    try:
        embedding_service = EmbeddingService()
        if hasattr(embedding_service, 'embedding_provider') and embedding_service.embedding_provider == "azure_openai":
            embedding = await embedding_service.generate_embedding_azure(text[:2000])
            logger.info(f"Generated Azure embedding with {len(embedding.embedding)} dimensions")
        else:
            logger.warning("Azure OpenAI not available, skipping embedding generation")
            embedding = None
    except Exception as e:
        logger.error(f"Error generating embedding: {e}")
        embedding = None

    # Create document entity
    paper_id = pdf_path.stem
    doc_entity_request = CreateEntityRequest(
        entity_type=EntityType.DOCUMENT,
        name=f"PDF Document: {paper_id}",
        confidence_score=0.9,
        extraction_method=ExtractionMethod.SPACY_NER,
        metadata={
            "paper_id": paper_id,
            "filename": pdf_path.name,
            "source": "local_pdf_reprocess",
            "topics": topics,
            "extracted_at": datetime.now().isoformat(),
            "has_embedding": embedding is not None
        }
    )

    doc_entity = kg_service.create_entity(doc_entity_request)
    if not doc_entity:
        logger.error(f"Failed to create document entity for {paper_id}")
        return

    logger.info(f"Created document entity: {doc_entity.id}")

    # Add topics as entities and relationships
    for topic in topics:
        # Create topic entity
        topic_entity_request = CreateEntityRequest(
            entity_type=EntityType.CONCEPT,
            name=topic,
            confidence_score=0.8,
            extraction_method=ExtractionMethod.SPACY_NER,
            metadata={
                "source": "pdf_reprocess",
                "paper_id": paper_id
            }
        )

        topic_entity = kg_service.create_entity(topic_entity_request)
        if topic_entity:
            # Create relationship
            rel_request = CreateRelationshipRequest(
                source_entity_id=doc_entity.id,
                target_entity_id=topic_entity.id,
                relationship_type=RelationshipType.RELATED_TO,
                confidence_score=0.85,
                metadata={"type": "topic_extraction"}
            )

            relationship = kg_service.create_relationship(rel_request)
            if relationship:
                logger.info(f"✅ Created relationship: {paper_id} -> {topic}")

    # Add entities
    for entity in entities.get("entities", []):
        entity_name = entity.get("name", "")
        entity_type = entity.get("type", "OTHER")

        if entity_name:
            entity_request = CreateEntityRequest(
                entity_type=EntityType(entity_type) if entity_type in ["PERSON", "ORG", "GPE", "CONCEPT"] else EntityType.CONCEPT,
                name=entity_name,
                confidence_score=entity.get("properties", {}).get("confidence", 0.7),
                extraction_method=ExtractionMethod.SPACY_NER,
                metadata=entity.get("properties", {})
            )

            entity_obj = kg_service.create_entity(entity_request)
            if entity_obj:
                rel_request = CreateRelationshipRequest(
                    source_entity_id=doc_entity.id,
                    target_entity_id=entity_obj.id,
                    relationship_type=RelationshipType.RELATED_TO,
                    confidence_score=0.7,
                    metadata={"type": "entity_extraction"}
                )
                kg_service.create_relationship(rel_request)

async def main():
    """Main function to re-process all PDFs"""
    logger.info("=== Re-processing PDFs for Knowledge Graph ===\n")

    # Get all PDF files
    pdf_files = []
    for pdf_file in UPLOADS_PATH.rglob("*.pdf"):
        if pdf_file.is_file():
            pdf_files.append(pdf_file)

    logger.info(f"Found {len(pdf_files)} PDF files")

    # Initialize knowledge graph service
    kg_service = KnowledgeGraphService()

    # Process each PDF
    processed = 0
    for pdf_path in pdf_files[:10]:  # Limit to first 10 for testing
        try:
            await process_pdf_for_knowledge_graph(pdf_path, kg_service)
            processed += 1
        except Exception as e:
            logger.error(f"Error processing {pdf_path.name}: {e}")
            import traceback
            traceback.print_exc()

    logger.info(f"\n✅ Successfully processed {processed} PDFs")
    logger.info("\nRun the knowledge tree visualization again to see the updates:")
    logger.info("python create_knowledge_visualization.py")

if __name__ == "__main__":
    asyncio.run(main())