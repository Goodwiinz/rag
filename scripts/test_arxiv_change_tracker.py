#!/usr/bin/env python3
"""
Test ArXiv Change Tracking System
"""

import sys
import asyncio
from pathlib import Path
import json

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent / "backend"))

async def test_change_tracker():
    """Test the change tracking system"""
    print("=" * 60)
    print("ArXiv Change Tracking Test")
    print("=" * 60)

    # Import the change tracker
    try:
        from src.services.arxiv_change_tracker import ArXivChangeTracker, track_arxiv_changes
        print("✓ Change tracker imported successfully")
    except Exception as e:
        print(f"✗ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # Initialize tracker
    tracker = ArXivChangeTracker()
    print(f"\n✓ Tracker initialized")
    print(f"  State file: {tracker.state_file}")
    print(f"  Currently tracking: {len(tracker.state)} papers")

    # Test 1: Track changes in a specific category
    print("\n" + "-" * 40)
    print("Test 1: Track changes in category")
    print("-" * 40)

    try:
        # Track recent changes in quantum physics
        result = await tracker.track_category_changes(
            categories=['quant-ph'],
            days_back=3,
            update_db=False  # Don't update DB for testing
        )

        print(f"✓ Tracked changes:")
        print(f"  Papers found: {result['papers_found']}")
        print(f"  Changes detected: {result['changes_detected']}")
        print(f"  New papers: {len(result.get('changes_by_type', {}).get('new', []))}")
        print(f"  Updated papers: {len(result.get('changes_by_type', {}).get('updated', []))}")

    except Exception as e:
        print(f"✗ Tracking failed: {e}")

    # Test 2: Track all categories
    print("\n" + "-" * 40)
    print("Test 2: Track all popular categories")
    print("-" * 40)

    try:
        result = await track_arxiv_changes(days_back=1)
        print(f"✓ Tracked all categories:")
        print(f"  Categories: {result['categories']}")
        print(f"  Period: {result['period_days']} days")
        print(f"  Summary: {result['summary']}")

    except Exception as e:
        print(f"✗ All tracking failed: {e}")

    # Test 3: Get change history
    print("\n" + "-" * 40)
    print("Test 3: Get change history")
    print("-" * 40)

    try:
        history = await tracker.get_change_history(limit=5)
        print(f"✓ Retrieved {len(history)} change records")

        for record in history[:3]:
            print(f"\n  Paper ID: {record['paper_id']}")
            print(f"    Last seen: {record['last_seen']}")
            print(f"    Deleted: {record['deleted']}")
            print(f"    Title: {record['metadata'].get('title', 'N/A')[:50]}...")

    except Exception as e:
        print(f"✗ History retrieval failed: {e}")

    # Test 4: Compute paper hash
    print("\n" + "-" * 40)
    print("Test 4: Test hash computation")
    print("-" * 40)

    try:
        test_paper = {
            'title': 'Test Paper on Quantum Computing',
            'abstract': 'This is a test abstract about quantum computing',
            'authors': ['Alice Smith', 'Bob Johnson'],
            'categories': ['quant-ph', 'cs.AI'],
            'primary_category': 'quant-ph'
        }

        hash1 = tracker.compute_paper_hash(test_paper)
        print(f"✓ Computed hash 1: {hash1[:16]}...")

        # Modify paper
        test_paper['abstract'] = 'This is a modified test abstract'
        hash2 = tracker.compute_paper_hash(test_paper)
        print(f"✓ Computed hash 2: {hash2[:16]}...")
        print(f"✓ Hashes are different: {hash1 != hash2}")

    except Exception as e:
        print(f"✗ Hash computation failed: {e}")

    # Test 5: Cleanup old state
    print("\n" + "-" * 40)
    print("Test 5: Cleanup old state")
    print("-" * 40)

    try:
        removed = await tracker.cleanup_old_state(days=0)  # Remove all old state for testing
        print(f"✓ Removed {removed} stale records")

    except Exception as e:
        print(f"✗ Cleanup failed: {e}")

    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    print("\nThe ArXiv Change Tracking System provides:")
    print("• Detects new, updated, and deleted arXiv papers")
    print("• Maintains persistent state tracking")
    print("• Automatic database updates when changes are detected")
    print("• Knowledge graph integration for entity updates")
    print("• Change history and audit trail")
    print("• Configurable category and time-based tracking")

    print("\nTo use in production:")
    print("1. Schedule periodic runs (e.g., daily)")
    print("2. Call /api/v1/arxiv/tracking/track-all for all categories")
    print("3. Or use /api/v1/arxiv/tracking/track-categories for specific categories")
    print("4. Monitor changes via /api/v1/arxiv/tracking/stats")

if __name__ == "__main__":
    asyncio.run(test_change_tracker())