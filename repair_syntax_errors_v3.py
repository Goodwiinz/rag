import os

files_to_check = [
    "backend/src/performance/multi_tier_cache.py",
    # Add other files just in case
    "backend/src/cache/analytics_cache.py",
    "backend/src/cache/cache_keys.py",
    "backend/src/performance/database_optimization.py",
    "backend/src/performance/optimization.py",
    "backend/src/services/ab_testing/ab_experiment_assignment_service.py",
    "backend/src/services/core/cache.py",
    "backend/src/services/documents/document_upload_service.py",
    "backend/src/services/documents/enhanced_document_processing_service.py",
    "backend/src/services/knowledge_graph/graph_visualization_service.py",
    "backend/src/services/research/draft_generation_service.py",
    "backend/src/services/search/bm25_service.py",
    "backend/src/utils/analytics_validation.py"
]

def repair_file(filepath):
    if not os.path.exists(filepath):
        return

    try:
        with open(filepath, 'r') as f:
            content = f.read()

        new_content = content

        # Fix join(..., usedforsecurity=False)
        # Matches: .join(key_parts, usedforsecurity=False)
        new_content = new_content.replace(".join(key_parts, usedforsecurity=False)", ".join(key_parts)")

        # Just in case generic join
        # This is risky but "join" usually takes 1 arg.
        # But let's stick to the specific one we saw.

        if new_content != content:
            print(f"Repaired {filepath}")
            with open(filepath, 'w') as f:
                f.write(new_content)
    except Exception as e:
        print(f"Error repairing {filepath}: {e}")

for f in files_to_check:
    repair_file(f)
