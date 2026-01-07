"""Standalone script for manual JWT testing (can be run independently)."""
import os
import sys
from pathlib import Path

# Add src to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.auth.test_jwt import test_jwt_generation

if __name__ == "__main__":
    test_jwt_generation()
