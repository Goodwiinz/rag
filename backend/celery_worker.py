"""
Celery worker startup script
"""

import os
import sys
from pathlib import Path

# Add src directory to Python path
sys.path.append(str(Path(__file__).parent / "src"))

from src.tasks.processing_tasks import celery_app

if __name__ == "__main__":
    # Start Celery worker
    celery_app.start([
        "worker",
        "--loglevel=info",
        "--queues=document_processing,text_processing,vector_processing,entity_processing,graph_processing",
        "--concurrency=4",
        "--prefetch-multiplier=1",
        "--max-tasks-per-child=1000"
    ])