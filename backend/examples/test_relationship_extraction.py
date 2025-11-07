"""
Test script to verify automatic relationship extraction works correctly.
Creates a test document with known entities and relationships, then verifies they are extracted.

Usage:
    python test_relationship_extraction.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import asyncio
import uuid
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.config import settings
from src.models.document import Document, DocumentType, ProcessingStatus
from src.services.multimodal_processing_service import MultimodalProcessingService
from src.services.knowledge_graph_service import knowledge_graph_service
from src.models.processing import ProcessingJob
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Test document with clear entities and relationships
TEST_DOCUMENT_TEXT = """
Tech Innovation Report 2024

Executive Summary:
Sarah Johnson works for TechCorp International, a leading software company located in San Francisco.
She manages the AI Research Division and reports to the CTO, Michael Chen.

TechCorp International collaborates with DataSystems Inc on several cloud computing projects.
The partnership between TechCorp International and DataSystems Inc was established in 2022.

Michael Chen, who is based in San Francisco, previously worked at Google before joining TechCorp International.
He knows several executives at Microsoft and Amazon.

The company's main office is located in downtown San Francisco at 123 Market Street.
TechCorp International owns the patent for an innovative machine learning algorithm.
This algorithm was created by the AI Research Division led by Sarah Johnson.

Contact Information:
- Email: sarah.johnson@techcorp.com
- Phone: +1-415-555-0123
- Website: https://techcorp.com

Key Projects:
- PROJ-2024-AI: Advanced Natural Language Processing
- PROD-5678: Cloud Analytics Platform
"""


def create_test_document(db_session) -> Document:
    """Create a test document in the database"""
    document = Document(
        id=uuid.uuid4(),
        title="Tech Innovation Report 2024 - Relationship Test",
        filename="test_relationships.txt",
        file_path="/tmp/test_relationships.txt",
        mime_type="text/plain",
        file_size_bytes=len(TEST_DOCUMENT_TEXT),
        document_type=DocumentType.TEXT,
        content_text=TEST_DOCUMENT_TEXT,
        processing_status=ProcessingStatus.PENDING,
        organization_id=uuid.uuid4(),
        uploaded_by_user_id=uuid.uuid4(),
        created_at=datetime.utcnow()
    )

    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)

    return document


def get_entities_for_document(document_id: str):
    """Get all entities for a document"""
    query = """
    MATCH (e:Entity)
    WHERE e.source_document_id = $document_id
    RETURN e.id as id, e.name as name, e.entity_type as type, e.confidence_score as confidence
    ORDER BY e.name
    """

    with knowledge_graph_service.driver.session() as session:
        result = session.run(query, document_id=str(document_id))
        return [dict(record) for record in result]


def get_relationships_for_document(document_id: str):
    """Get all relationships for a document"""
    query = """
    MATCH (a:Entity)-[r]->(b:Entity)
    WHERE r.source_document_id = $document_id
    RETURN a.name as source, type(r) as relationship, b.name as target, r.confidence_score as confidence
    ORDER BY a.name, type(r), b.name
    """

    with knowledge_graph_service.driver.session() as session:
        result = session.run(query, document_id=str(document_id))
        return [dict(record) for record in result]


async def main():
    """Main test function"""
    logger.info("="*80)
    logger.info("RELATIONSHIP EXTRACTION TEST")
    logger.info("="*80)

    # Create database session
    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    db_session = Session()

    try:
        # Create test document
        logger.info("\n1. Creating test document...")
        document = create_test_document(db_session)
        logger.info(f"✓ Created document: {document.title} (ID: {document.id})")

        # Create processing job
        job = ProcessingJob(
            document_id=document.id,
            organization_id=document.organization_id,
            total_steps=0,
            completed_steps=0
        )

        # Initialize processing service
        logger.info("\n2. Initializing processing service...")
        processing_service = MultimodalProcessingService(db_session)

        # Process the document (extract entities and relationships)
        logger.info("\n3. Extracting entities and relationships...")
        result = await processing_service.store_entities_in_knowledge_graph(document, job)

        logger.info("\n" + "="*80)
        logger.info("EXTRACTION RESULTS")
        logger.info("="*80)
        logger.info(f"Entities stored: {result['entities_stored']}")
        logger.info(f"Relationships stored: {result['relationships_stored']}")
        logger.info(f"Processing time: {result['processing_time']:.2f}s")

        if result['errors']:
            logger.warning(f"Errors encountered: {len(result['errors'])}")
            for error in result['errors']:
                logger.warning(f"  - {error}")

        # Verify entities in the graph
        logger.info("\n4. Verifying entities in knowledge graph...")
        entities = get_entities_for_document(str(document.id))
        logger.info(f"\nFound {len(entities)} entities:")
        logger.info("-" * 80)

        # Group by type
        by_type = {}
        for entity in entities:
            entity_type = entity["type"]
            if entity_type not in by_type:
                by_type[entity_type] = []
            by_type[entity_type].append(entity)

        for entity_type, items in sorted(by_type.items()):
            logger.info(f"\n{entity_type} ({len(items)}):")
            for item in items:
                logger.info(f"  - {item['name']} (confidence: {item['confidence']:.2f})")

        # Verify relationships in the graph
        logger.info("\n5. Verifying relationships in knowledge graph...")
        relationships = get_relationships_for_document(str(document.id))
        logger.info(f"\nFound {len(relationships)} relationships:")
        logger.info("-" * 80)

        if relationships:
            # Group by type
            by_rel_type = {}
            for rel in relationships:
                rel_type = rel["relationship"]
                if rel_type not in by_rel_type:
                    by_rel_type[rel_type] = []
                by_rel_type[rel_type].append(rel)

            for rel_type, items in sorted(by_rel_type.items()):
                logger.info(f"\n{rel_type} ({len(items)}):")
                for item in items:
                    logger.info(f"  {item['source']} --> {item['target']} (confidence: {item['confidence']:.2f})")
        else:
            logger.warning("⚠️  No relationships were extracted!")
            logger.info("\nExpected relationships from the test document:")
            logger.info("  - Sarah Johnson --[WORKS_FOR]--> TechCorp International")
            logger.info("  - Sarah Johnson --[MANAGES]--> AI Research Division")
            logger.info("  - TechCorp International --[LOCATED_IN]--> San Francisco")
            logger.info("  - TechCorp International --[COLLABORATES_WITH]--> DataSystems Inc")
            logger.info("  - Michael Chen --[WORKS_FOR]--> TechCorp International")

        # Summary
        logger.info("\n" + "="*80)
        logger.info("TEST SUMMARY")
        logger.info("="*80)
        logger.info(f"Document ID: {document.id}")
        logger.info(f"Total entities: {len(entities)}")
        logger.info(f"Total relationships: {len(relationships)}")

        if len(relationships) > 0:
            logger.info("\n✓ Relationship extraction is working!")
        else:
            logger.warning("\n⚠️  Relationship extraction may need adjustment")
            logger.info("Check the entity extraction service patterns in:")
            logger.info("  backend/src/services/entity_extraction_service.py")

        logger.info("\nYou can view the results in Neo4j Browser:")
        logger.info("  http://localhost:7474")
        logger.info(f"  Run: MATCH (e:Entity)-[r]-(other) WHERE e.source_document_id = '{document.id}' RETURN e, r, other")

    except Exception as e:
        logger.error(f"Test failed: {str(e)}", exc_info=True)

    finally:
        db_session.close()


if __name__ == "__main__":
    asyncio.run(main())
