#!/usr/bin/env python3
"""
Test script to verify automatic knowledge graph extraction from uploaded documents
"""

import sys
import os
import time
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.services.knowledge_graph_service import knowledge_graph_service
from src.core.database import SessionLocal
from src.models.document import Document, DocumentType
from src.models.user import User
from src.models.organization import Organization
from src.services.multimodal_processing_service import MultimodalProcessingService
from src.models.processing import ProcessingJob, JobType, JobStatus, JobPriority


def create_test_document(db):
    """Create a test document with sample text"""

    # Sample text with entities
    sample_text = """
    Dr. Jane Smith is the Chief Technology Officer at TechCorp Solutions, a leading
    artificial intelligence company based in San Francisco, California. She previously
    worked at Google and Microsoft before joining TechCorp in 2020.

    TechCorp recently partnered with Stanford University to research machine learning
    applications in healthcare. The project aims to improve diagnostic accuracy using
    deep learning algorithms.

    Jane can be reached at jane.smith@techcorp.com or by phone at +1-415-555-0123.
    For more information, visit https://www.techcorp.com.

    The company's headquarters is located at 100 Market Street, San Francisco, CA 94105.
    """

    # Get first organization and user
    org = db.query(Organization).first()
    user = db.query(User).first()

    if not org or not user:
        print("❌ No organization or user found in database")
        return None, None

    # Create temporary file with the text
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(sample_text)
        temp_file_path = f.name

    # Create document
    document = Document(
        title="TechCorp AI Research Announcement",
        file_path=temp_file_path,
        filename="techcorp_announcement.txt",
        document_type=DocumentType.TEXT,
        mime_type="text/plain",
        file_size_bytes=len(sample_text.encode('utf-8')),
        content_text=sample_text,
        organization_id=org.id,
        uploaded_by_user_id=user.id
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    print(f"✓ Created test document: {document.id} - {document.title}")
    return document, temp_file_path


def test_automatic_extraction():
    """Test automatic entity extraction and knowledge graph storage"""

    print("\n" + "="*70)
    print("Testing Automatic Knowledge Graph Extraction from Document Upload")
    print("="*70 + "\n")

    db = SessionLocal()

    try:
        # Get current entity count before processing
        with knowledge_graph_service.get_session() as session:
            result = session.run("MATCH (e:Entity) RETURN count(e) as count")
            initial_count = result.single()['count']
            print(f"Current entities in knowledge graph: {initial_count}\n")

        # Create test document
        document, temp_file = create_test_document(db)
        if not document:
            return

        # Create processing job
        job = ProcessingJob(
            job_type=JobType.DOCUMENT_INGESTION,
            status=JobStatus.PENDING,
            priority=JobPriority.NORMAL,
            document_id=document.id,
            organization_id=document.organization_id,
            created_by_user_id=document.uploaded_by_user_id,
            parameters={
                "document_id": str(document.id),
                "test_mode": True
            },
            config={
                "enable_entity_extraction": True
            },
            total_steps=6,
            queue_name="document_processing"
        )

        db.add(job)
        db.commit()
        db.refresh(job)

        print(f"✓ Created processing job: {job.id}\n")

        # Process the document
        print("Processing document...\n")
        processing_service = MultimodalProcessingService(db)

        import asyncio
        processing_results = asyncio.run(processing_service.process_document(document, job))

        # Display results
        print("\n" + "-"*70)
        print("Processing Results:")
        print("-"*70)
        print(f"Success: {processing_results['success']}")
        print(f"Processing Time: {processing_results['processing_time']:.2f}s")

        if processing_results.get('errors'):
            print(f"\nErrors: {len(processing_results['errors'])}")
            for error in processing_results['errors']:
                print(f"  • {error}")

        # Check entity extraction results
        if 'entity_extraction' in processing_results:
            entity_results = processing_results['entity_extraction']
            print(f"\n✓ Entity Extraction:")
            print(f"  Entities found: {entity_results.get('entity_count', 0)}")
            print(f"  Processing time: {entity_results.get('processing_time', 0):.2f}s")

            if 'entities' in entity_results:
                print(f"\n  Sample entities:")
                for i, entity in enumerate(entity_results['entities'][:5], 1):
                    print(f"    {i}. {entity.get('text')} ({entity.get('label')}) - confidence: {entity.get('confidence', 0):.2f}")

        # Check knowledge graph storage results
        if 'knowledge_graph_storage' in processing_results:
            kg_results = processing_results['knowledge_graph_storage']
            print(f"\n✓ Knowledge Graph Storage:")
            print(f"  Entities stored: {kg_results.get('entities_stored', 0)}")
            print(f"  Relationships stored: {kg_results.get('relationships_stored', 0)}")
            print(f"  Processing time: {kg_results.get('processing_time', 0):.2f}s")

            if kg_results.get('errors'):
                print(f"  Errors: {len(kg_results['errors'])}")

        # Verify entities are in knowledge graph
        print("\n" + "-"*70)
        print("Verifying Knowledge Graph:")
        print("-"*70)

        with knowledge_graph_service.get_session() as session:
            # Get total count
            result = session.run("MATCH (e:Entity) RETURN count(e) as count")
            final_count = result.single()['count']
            new_entities = final_count - initial_count

            print(f"Total entities now: {final_count}")
            print(f"New entities added: {new_entities}\n")

            # Get entities from this document
            result = session.run("""
                MATCH (e:Entity)
                WHERE e.source_document_id = $doc_id
                RETURN e.name as name, e.type as type, e.confidence_score as confidence
                ORDER BY e.confidence_score DESC
            """, doc_id=str(document.id))

            doc_entities = list(result)

            if doc_entities:
                print(f"✓ Found {len(doc_entities)} entities from this document:")
                for i, entity in enumerate(doc_entities[:10], 1):
                    print(f"  {i}. {entity['name']} ({entity['type']}) - confidence: {entity['confidence']:.2f}")

                if len(doc_entities) > 10:
                    print(f"  ... and {len(doc_entities) - 10} more")
            else:
                print("⚠ No entities found for this document in knowledge graph")

        # Clean up temp file
        if temp_file and os.path.exists(temp_file):
            os.unlink(temp_file)

        print("\n" + "="*70)
        print("✓ Test completed successfully!")
        print("="*70 + "\n")

        print("Next steps:")
        print("1. Check Neo4j Browser at http://localhost:7474")
        print("2. Run query: MATCH (n:Entity) WHERE n.source_document_id = '" + str(document.id) + "' RETURN n")
        print("3. Upload more documents via the frontend to see automatic extraction")
        print("4. Use the knowledge graph API to query relationships")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    test_automatic_extraction()
