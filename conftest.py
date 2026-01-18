"""
Pytest configuration for CAR-ETL project.

This file ensures that the project root is in sys.path so that
tests can import from the src/ directory.
"""
import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
