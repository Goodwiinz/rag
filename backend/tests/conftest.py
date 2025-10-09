"""
Pytest configuration for test suite
"""

import sys
from pathlib import Path

# Add the backend directory to Python path so 'src' imports work
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))
