"""
Backfill script to add relationships to existing documents in the knowledge graph.
This script processes documents that already have entities extracted,
and adds relationships between those entities.

Usage:
    # Process all documents
    python backfill_relationships.py

    # Process specific documents
    python backfill_relationships.py --document-ids doc1,doc2,doc3

    # Dry run (don't actually create relationships)
    python backfill_relationships.py --dry-run

    # Process in batches
    python backfill_relationships.py --batch-size 10

    # Reprocess all (including documents that already have relationships)
    python backfill_relationships.py --reprocess-all
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import asyncio
import argparse
from typing import List, Dict, Any
from datetime import datetime
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from src.core.config import settings
from src.models.document import Document
from src.services.entity_extraction_service import EntityExtractionService
from src.services.knowledge_graph_service import knowledge_graph_service
from src.models.graph import CreateRelationshipRequest, RelationshipType as GraphRelationshipType
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_database_session():
    """Create database session"""
    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    return Session()


def get_documents_with_entities(db_session, document_ids: List[str] = None, limit: int = None) -> List[Document]:
    """Get documents that have entities in the knowledge graph"""
    query = select(Document).where(Document.content_text.isnot(None))

    if document_ids:
        query = query.where(Document.id.in_(document_ids))

    if limit:
        query = query.limit(limit)

    documents = db_session.execute(query).scalars().all()
    return documents


def get_entities_for_document(document_id: str) -> List[Dict[str, Any]]:
    """Get all entities for a document from the knowledge graph"""
    query = """
    MATCH (e:Entity)
    WHERE e.source_document_id = $document_id
    RETURN e.id as id, e.name as name, e.entity_type as type,
           e.confidence_score as confidence, e.metadata as metadata
    ORDER BY e.name
    """

    with knowledge_graph_service.driver.session() as session:
        result = session.run(query, document_id=str(document_id))
        return [dict(record) for record in result]


def get_relationship_count_for_document(document_id: str) -> int:
    """Count existing relationships for a document"""
    query = """
    MATCH (a:Entity)-[r]->(b:Entity)
    WHERE r.source_document_id = $document_id
    RETURN count(r) as count
    """

    with knowledge_graph_service.driver.session() as session:
        result = session.run(query, document_id=str(document_id))
        record = result.single()
        return record["count"] if record else 0


def relationship_exists(source_id: str, target_id: str, rel_type: str) -> bool:
    """Check if a relationship already exists"""
    query = """
    MATCH (a:Entity {id: $source_id})-[r:%s]->(b:Entity {id: $target_id})
    RETURN count(r) as count
    """ % rel_type

    with knowledge_graph_service.driver.session() as session:
        result = session.run(query, source_id=source_id, target_id=target_id)
        record = result.single()
        return record["count"] > 0 if record else False


def extract_and_store_relationships(
    document: Document,
    dry_run: bool = False
) -> Dict[str, Any]:
    """Extract and store relationships for a document"""

    logger.info(f"Processing document: {document.title} (ID: {document.id})")

    stats = {
        "document_id": str(document.id),
        "document_title": document.title,
        "entities_found": 0,
        "relationships_extracted": 0,
        "relationships_stored": 0,
        "relationships_skipped": 0,
        "errors": []
    }

    try:
        # Get existing entities for this document
        entities_data = get_entities_for_document(str(document.id))
        stats["entities_found"] = len(entities_data)

        if not entities_data:
            logger.info(f"No entities found for document {document.id}")
            return stats

        logger.info(f"Found {len(entities_data)} entities for document {document.id}")

        # Get document text
        text_content = document.content_text
        if not text_content or len(text_content.strip()) < 10:
            logger.info(f"Insufficient text content for document {document.id}")
            return stats

        # Initialize entity extraction service
        entity_service = EntityExtractionService()

        # Process text with spaCy
        spacy_doc = entity_service.nlp(text_content)

        # Re-extract entities to get the full entity objects with properties
        entities = entity_service.extract_entities_from_text(document, text_content)

        if not entities or len(entities) < 2:
            logger.info(f"Not enough entities extracted for relationship detection")
            return stats

        # Extract relationships
        relationships = entity_service._extract_relationships(spacy_doc, entities)
        stats["relationships_extracted"] = len(relationships)

        logger.info(f"Extracted {len(relationships)} relationships from document")

        # Build entity name to graph ID mapping
        entity_name_to_id = {
            e["name"].lower().strip(): e["id"]
            for e in entities_data
        }

        # Store relationships
        for rel in relationships:
            try:
                source_entity = rel.get('source_entity')
                target_entity = rel.get('target_entity')
                relationship_type = rel.get('relationship_type', 'related_to')

                # Find graph IDs by matching entity names
                source_graph_id = None
                target_graph_id = None

                source_name = source_entity.name.lower().strip()
                target_name = target_entity.name.lower().strip()

                # Try exact match first
                source_graph_id = entity_name_to_id.get(source_name)
                target_graph_id = entity_name_to_id.get(target_name)

                if not source_graph_id or not target_graph_id:
                    logger.debug(f"Could not find graph IDs for relationship: {source_entity.name} -> {target_entity.name}")
                    continue

                # Map relationship type
                relationship_type_mapping = {
                    'works_for': GraphRelationshipType.WORKS_FOR,
                    'located_in': GraphRelationshipType.LOCATED_IN,
                    'part_of': GraphRelationshipType.PART_OF,
                    'related_to': GraphRelationshipType.RELATED_TO,
                    'owns': GraphRelationshipType.OWNS,
                    'created_by': GraphRelationshipType.CREATED_BY,
                    'manages': GraphRelationshipType.MANAGES,
                    'knows': GraphRelationshipType.KNOWS,
                    'collaborates_with': GraphRelationshipType.COLLABORATES_WITH
                }

                graph_rel_type = relationship_type_mapping.get(
                    relationship_type.lower(),
                    GraphRelationshipType.RELATED_TO
                )

                # Check if relationship already exists
                if relationship_exists(source_graph_id, target_graph_id, graph_rel_type.value):
                    logger.debug(f"Relationship already exists: {source_entity.name} --[{graph_rel_type.value}]--> {target_entity.name}")
                    stats["relationships_skipped"] += 1
                    continue

                if dry_run:
                    logger.info(f"[DRY RUN] Would create: {source_entity.name} --[{graph_rel_type.value}]--> {target_entity.name}")
                    stats["relationships_stored"] += 1
                    continue

                # Create relationship
                rel_request = CreateRelationshipRequest(
                    source_entity_id=source_graph_id,
                    target_entity_id=target_graph_id,
                    relationship_type=graph_rel_type,
                    confidence_score=rel.get('confidence', 0.7),
                    context=rel.get('evidence', ''),
                    evidence=[rel.get('evidence', '')] if rel.get('evidence') else [],
                    metadata={
                        "document_id": str(document.id),
                        "pattern_matched": rel.get('pattern_matched', ''),
                        "extraction_date": datetime.utcnow().isoformat(),
                        "source": "backfill_script"
                    },
                    source_document_id=str(document.id)
                )

                knowledge_graph_service.create_relationship(rel_request)
                stats["relationships_stored"] += 1

                logger.info(f"✓ Created: {source_entity.name} --[{graph_rel_type.value}]--> {target_entity.name}")

            except Exception as e:
                error_msg = f"Failed to store relationship: {str(e)}"
                logger.warning(error_msg)
                stats["errors"].append(error_msg)

    except Exception as e:
        error_msg = f"Error processing document {document.id}: {str(e)}"
        logger.error(error_msg)
        stats["errors"].append(error_msg)

    return stats


def main():
    """Main backfill function"""
    parser = argparse.ArgumentParser(description='Backfill relationships for existing documents')
    parser.add_argument('--batch-size', type=int, default=10, help='Number of documents to process in each batch')
    parser.add_argument('--limit', type=int, help='Maximum number of documents to process')
    parser.add_argument('--document-ids', type=str, help='Comma-separated list of document IDs to process')
    parser.add_argument('--reprocess-all', action='store_true', help='Reprocess all documents, even those with existing relationships')
    parser.add_argument('--dry-run', action='store_true', help='Perform a dry run without actually creating relationships')

    args = parser.parse_args()

    logger.info("="*80)
    logger.info("KNOWLEDGE GRAPH RELATIONSHIP BACKFILL")
    logger.info("="*80)

    if args.dry_run:
        logger.info("DRY RUN MODE - No relationships will be created")

    # Parse document IDs if provided
    document_ids = None
    if args.document_ids:
        document_ids = [d.strip() for d in args.document_ids.split(',')]
        logger.info(f"Processing specific documents: {document_ids}")

    # Get database session
    db_session = get_database_session()

    try:
        # Get documents to process
        documents = get_documents_with_entities(db_session, document_ids, args.limit)
        logger.info(f"Found {len(documents)} documents to process")

        if not documents:
            logger.info("No documents found to process")
            return

        total_stats = {
            "documents_processed": 0,
            "documents_skipped": 0,
            "total_entities_found": 0,
            "total_relationships_extracted": 0,
            "total_relationships_stored": 0,
            "total_relationships_skipped": 0,
            "documents_with_errors": 0
        }

        # Process documents
        for i, document in enumerate(documents, 1):
            logger.info(f"\nProcessing document {i}/{len(documents)}")

            # Check if document already has relationships
            if not args.reprocess_all:
                existing_rel_count = get_relationship_count_for_document(str(document.id))
                if existing_rel_count > 0:
                    logger.info(f"Skipping document {document.id} - already has {existing_rel_count} relationships")
                    total_stats["documents_skipped"] += 1
                    continue

            # Process document
            stats = extract_and_store_relationships(document, dry_run=args.dry_run)

            # Update totals
            total_stats["documents_processed"] += 1
            total_stats["total_entities_found"] += stats["entities_found"]
            total_stats["total_relationships_extracted"] += stats["relationships_extracted"]
            total_stats["total_relationships_stored"] += stats["relationships_stored"]
            total_stats["total_relationships_skipped"] += stats["relationships_skipped"]

            if stats["errors"]:
                total_stats["documents_with_errors"] += 1

            # Log progress
            logger.info(f"Document stats: {stats['relationships_stored']} relationships stored, {stats['relationships_skipped']} skipped")

        # Print final summary
        logger.info("\n" + "="*80)
        logger.info("BACKFILL COMPLETE")
        logger.info("="*80)
        logger.info(f"Documents processed: {total_stats['documents_processed']}")
        logger.info(f"Documents skipped: {total_stats['documents_skipped']}")
        logger.info(f"Total entities found: {total_stats['total_entities_found']}")
        logger.info(f"Total relationships extracted: {total_stats['total_relationships_extracted']}")
        logger.info(f"Total relationships stored: {total_stats['total_relationships_stored']}")
        logger.info(f"Total relationships skipped (duplicates): {total_stats['total_relationships_skipped']}")
        logger.info(f"Documents with errors: {total_stats['documents_with_errors']}")

        if args.dry_run:
            logger.info("\n⚠️  DRY RUN - No changes were made to the database")

    finally:
        db_session.close()


if __name__ == "__main__":
    main()
