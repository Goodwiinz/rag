#!/usr/bin/env python3
"""
Backfill Knowledge Graph - Process existing documents to extract entities

This script processes all existing documents in the database and extracts
their entities into the knowledge graph.
"""

import sys
import os
import asyncio
import time
from typing import List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import and_
from src.core.database import SessionLocal
from src.models.document import Document, ProcessingStatus
from src.services.knowledge_graph.knowledge_graph_service import knowledge_graph_service
from src.services.processing import EntityExtractionService
from src.models.graph import CreateEntityRequest, EntityType as GraphEntityType, ExtractionMethod


class KnowledgeGraphBackfiller:
    """Service to backfill knowledge graph from existing documents"""

    def __init__(self, db):
        self.db = db
        self.entity_service = EntityExtractionService()
        self.stats = {
            "documents_processed": 0,
            "documents_skipped": 0,
            "entities_extracted": 0,
            "entities_stored": 0,
            "errors": [],
            "processing_time": 0
        }

    def get_documents_to_process(
        self,
        limit: Optional[int] = None,
        skip_processed: bool = True,
        document_ids: Optional[List[str]] = None
    ) -> List[Document]:
        """Get documents that need knowledge graph extraction"""

        query = self.db.query(Document)

        # Filter conditions
        conditions = [
            Document.is_deleted == False,
            Document.content_text.isnot(None),
            Document.content_text != ""
        ]

        # Skip documents that have already been processed (have entities in KG)
        if skip_processed:
            # Get document IDs that already have entities in knowledge graph
            with knowledge_graph_service.get_session() as session:
                result = session.run("""
                    MATCH (e:Entity)
                    WHERE e.source_document_id IS NOT NULL
                    RETURN DISTINCT e.source_document_id as doc_id
                """)
                processed_doc_ids = [record['doc_id'] for record in result]

            if processed_doc_ids:
                conditions.append(~Document.id.in_(processed_doc_ids))
                print(f"Found {len(processed_doc_ids)} documents already processed")

        # Filter by specific document IDs if provided
        if document_ids:
            conditions.append(Document.id.in_(document_ids))

        query = query.filter(and_(*conditions))

        # Apply limit
        if limit:
            query = query.limit(limit)

        documents = query.all()
        print(f"Found {len(documents)} documents to process")

        return documents

    def process_document(self, document: Document) -> dict:
        """Process a single document and extract entities to knowledge graph"""

        result = {
            "document_id": str(document.id),
            "title": document.title,
            "entities_extracted": 0,
            "entities_stored": 0,
            "errors": [],
            "success": False
        }

        try:
            # Extract entities using spaCy
            entities = self.entity_service.extract_entities_from_text(
                document,
                document.content_text
            )

            result["entities_extracted"] = len(entities)
            self.stats["entities_extracted"] += len(entities)

            if not entities:
                result["success"] = True
                return result

            # Store each entity in knowledge graph
            for entity in entities:
                try:
                    # Map entity type
                    entity_type_str = entity.entity_type.value if hasattr(entity.entity_type, 'value') else str(entity.entity_type)

                    # Skip if type is not valid
                    try:
                        graph_entity_type = GraphEntityType(entity_type_str.upper())
                    except ValueError:
                        # Default to OTHER for unknown types
                        graph_entity_type = GraphEntityType.OTHER

                    # Get context - handle different attribute names
                    context_text = ""
                    if hasattr(entity, 'context') and entity.context:
                        context_text = entity.context
                    elif hasattr(entity, 'description') and entity.description:
                        context_text = entity.description
                    elif hasattr(entity, 'properties') and entity.properties:
                        context_text = str(entity.properties)
                    else:
                        context_text = document.content_text[:200] if document.content_text else ""

                    # Get confidence score - handle different attribute names
                    confidence = 0.8
                    if hasattr(entity, 'confidence_score'):
                        confidence = entity.confidence_score
                    elif hasattr(entity, 'confidence'):
                        confidence = entity.confidence
                    elif hasattr(entity, 'relevance_score'):
                        confidence = entity.relevance_score

                    # Create entity request
                    entity_request = CreateEntityRequest(
                        name=entity.name,
                        entity_type=graph_entity_type,
                        confidence_score=confidence,
                        extraction_method=ExtractionMethod.SPACY_NER,
                        context=context_text,
                        metadata={
                            "document_id": str(document.id),
                            "document_title": document.title,
                            "document_type": document.document_type.value if document.document_type else "UNKNOWN",
                            "extraction_date": str(document.created_at),
                            "source": "backfill_processing",
                            "backfilled": True
                        },
                        source_document_id=str(document.id)
                    )

                    # Store in knowledge graph
                    graph_entity = knowledge_graph_service.create_entity(entity_request)
                    result["entities_stored"] += 1
                    self.stats["entities_stored"] += 1

                except Exception as e:
                    error_msg = f"Failed to store entity {entity.name}: {str(e)}"
                    result["errors"].append(error_msg)
                    self.stats["errors"].append(error_msg)

            result["success"] = True
            self.stats["documents_processed"] += 1

        except Exception as e:
            error_msg = f"Failed to process document {document.id}: {str(e)}"
            result["errors"].append(error_msg)
            self.stats["errors"].append(error_msg)
            self.stats["documents_skipped"] += 1

        return result

    def process_batch(
        self,
        batch_size: int = 10,
        limit: Optional[int] = None,
        document_ids: Optional[List[str]] = None,
        skip_processed: bool = True
    ):
        """Process documents in batches"""

        print("\n" + "="*70)
        print("Knowledge Graph Backfill - Processing Existing Documents")
        print("="*70 + "\n")

        start_time = time.time()

        # Get documents to process
        documents = self.get_documents_to_process(
            limit=limit,
            skip_processed=skip_processed,
            document_ids=document_ids
        )

        if not documents:
            print("No documents found to process")
            return

        total_docs = len(documents)
        print(f"\nProcessing {total_docs} documents in batches of {batch_size}\n")

        # Process in batches
        for i in range(0, total_docs, batch_size):
            batch = documents[i:i+batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (total_docs + batch_size - 1) // batch_size

            print(f"Batch {batch_num}/{total_batches} ({len(batch)} documents)")
            print("-" * 70)

            for doc in batch:
                result = self.process_document(doc)

                status = "✓" if result["success"] else "✗"
                print(f"{status} {result['title'][:50]:50} | Entities: {result['entities_stored']:3}")

                if result["errors"]:
                    for error in result["errors"][:2]:  # Show first 2 errors
                        print(f"    ⚠ {error[:65]}")

            print()

            # Commit after each batch
            self.db.commit()

        # Final stats
        self.stats["processing_time"] = time.time() - start_time

        print("\n" + "="*70)
        print("Backfill Complete!")
        print("="*70)
        print(f"\nStatistics:")
        print(f"  Documents processed:    {self.stats['documents_processed']:5}")
        print(f"  Documents skipped:      {self.stats['documents_skipped']:5}")
        print(f"  Entities extracted:     {self.stats['entities_extracted']:5}")
        print(f"  Entities stored:        {self.stats['entities_stored']:5}")
        print(f"  Errors:                 {len(self.stats['errors']):5}")
        print(f"  Processing time:        {self.stats['processing_time']:.2f}s")

        if self.stats['documents_processed'] > 0:
            avg_time = self.stats['processing_time'] / self.stats['documents_processed']
            avg_entities = self.stats['entities_stored'] / self.stats['documents_processed']
            print(f"  Avg time per document:  {avg_time:.2f}s")
            print(f"  Avg entities per doc:   {avg_entities:.1f}")

        print("\nVerify in Neo4j:")
        print("  1. Open http://localhost:7474")
        print("  2. Run: MATCH (e:Entity) WHERE e.metadata.backfilled = true RETURN count(e)")
        print()


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Backfill knowledge graph from existing documents')
    parser.add_argument('--batch-size', type=int, default=10, help='Number of documents per batch')
    parser.add_argument('--limit', type=int, help='Maximum number of documents to process')
    parser.add_argument('--document-ids', nargs='+', help='Specific document IDs to process')
    parser.add_argument('--reprocess-all', action='store_true', help='Reprocess documents that already have entities')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be processed without processing')

    args = parser.parse_args()

    db = SessionLocal()

    try:
        backfiller = KnowledgeGraphBackfiller(db)

        if args.dry_run:
            # Just show what would be processed
            documents = backfiller.get_documents_to_process(
                limit=args.limit,
                skip_processed=not args.reprocess_all,
                document_ids=args.document_ids
            )

            print("\n" + "="*70)
            print("DRY RUN - Documents that would be processed:")
            print("="*70 + "\n")

            for i, doc in enumerate(documents, 1):
                text_len = len(doc.content_text) if doc.content_text else 0
                print(f"{i:3}. {doc.title[:60]:60} | {doc.document_type.value:10} | {text_len:6} chars")

            print(f"\nTotal: {len(documents)} documents")
            print("\nRun without --dry-run to process these documents\n")
        else:
            # Process documents
            backfiller.process_batch(
                batch_size=args.batch_size,
                limit=args.limit,
                document_ids=args.document_ids,
                skip_processed=not args.reprocess_all
            )

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()
