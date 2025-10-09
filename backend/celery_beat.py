"""
Celery beat scheduler startup script
"""

import os
import sys
from pathlib import Path

# Add src directory to Python path
sys.path.append(str(Path(__file__).parent / "src"))

from src.tasks.processing_tasks import celery_app

if __name__ == "__main__":
    # Start Celery beat scheduler
    celery_app.start([
        "beat",
        "--loglevel=info",
        "--pidfile=/tmp/celerybeat.pid"
    ])