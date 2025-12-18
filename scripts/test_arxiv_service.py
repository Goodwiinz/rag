#!/usr/bin/env python3
"""
Test arXiv service directly
"""

import sys
import asyncio
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent / "backend"))

async def test_service():
    """Test the arXiv service"""
    print("Creating ArXivIngestionService...")

    # Import here to see if import works
    try:
        from src.services.arxiv_service import ArXivIngestionService
        print("✓ Import successful")
    except Exception as e:
        print(f"✗ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return

    print("\nInitializing service...")

    # Test initialization
    try:
        service = ArXivIngestionService()
        print(f"✓ Service created, session: {service.session}")
    except Exception as e:
        print(f"✗ Service creation failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # Test context manager
    try:
        print("\nUsing async context manager...")
        async with ArXivIngestionService() as service:
            print(f"✓ In context manager, session: {service.session}")
            print(f"✓ Session type: {type(service.session)}")

            # Test sync request method
            print("\nTesting sync request method...")
            test_text = service._make_sync_request(
                "http://export.arxiv.org/api/query",
                {
                    'search_query': 'machine learning',
                    'max_results': 1
                }
            )
            print(f"✓ Got response text, length: {len(test_text)}")
            print(f"Response preview: {test_text[:200]}...")

            # Test search papers
            print("\nTesting search_papers...")
            papers = await service.search_papers(
                query="machine learning",
                max_results=2,
                categories=['cs.LG']
            )
            print(f"✓ Found {len(papers)} papers")

            for paper in papers[:2]:
                print(f"  - {paper.get('title', 'No title')}")

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return

    print("\n✓ All tests passed!")

if __name__ == "__main__":
    asyncio.run(test_service())