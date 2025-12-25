import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

try:
    from src.models.graph import EntityType, RelationshipType
    
    print("EntityType values:")
    for e in EntityType:
        print(f"  {e.name}: '{e.value}'")
        
    print("\nRelationshipType values:")
    for r in RelationshipType:
        print(f"  {r.name}: '{r.value}'")
        
except ImportError as e:
    print(f"ImportError: {e}")
except Exception as e:
    print(f"Error: {e}")
