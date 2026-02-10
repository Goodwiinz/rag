"""
Celery beat scheduler startup script
"""

import os
import sys
from pathlib import Path

# Add src directory to Python path
sys.path.append(str(Path(__file__).parent / "src"))

import tempfile
import os

from src.tasks.processing_tasks import celery_app

if __name__ == "__main__":
    # Use system tempdir for secure PID file location
    pidfile = os.path.join(tempfile.gettempdir(), "celerybeat.pid")
    
    # Start Celery beat scheduler
    celery_app.start([
        "beat",
        "--loglevel=info",
        f"--pidfile={pidfile}"
    ])