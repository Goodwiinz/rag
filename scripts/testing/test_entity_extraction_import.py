#!/usr/bin/env python3
"""
Test entity extraction service imports and basic functionality
"""

import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

def test_imports():
    """Test if the entity extraction service can be imported without errors"""
    try:
        print("Testing imports...")

        # Test basic imports
        from src.models.entity import EntityType, ExtractionMethod
        from src.models.graph import RelationshipType
        print("✓ Model imports successful")

        # Test service import
        from src.services.services.entity_extraction_service import EntityExtractionService
        print("✓ EntityExtractionService import successful")

        # Check enum values
        print(f"\nEntity Types: {[e.value for e in EntityType]}")
        print(f"Extraction Methods: {[e.value for e in ExtractionMethod]}")

        # Initialize service
        service = EntityExtractionService()
        print("\n✓ EntityExtractionService initialized successfully")

        # Test simple pattern extraction
        test_text = "Contact John at john@example.com or call (555) 123-4567."
        entities = service.extract_entities_sync(test_text, "test_doc")
        print(f"\nExtracted {len(entities)} entities from test text:")
        for e in entities:
            print(f"  - {e['name']} ({e['entity_type']}) - method: {e['extraction_method']}")

        return True

    except Exception as e:
        print(f"✗ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("="*80)
    print("ENTITY EXTRACTION IMPORT TEST")
    print("="*80)

    success = test_imports()

    if success:
        print("\n✅ All tests passed! The entity extraction service is ready.")
    else:
        print("\n❌ Tests failed. Please fix the errors above.")