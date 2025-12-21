import sys
import os

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from backend.src.models.graph import ExtractionMethod
    print("ExtractionMethod members:")
    for member in ExtractionMethod:
        print(f"{member.name} = {member.value}")
except Exception as e:
    print(f"Error: {e}")
