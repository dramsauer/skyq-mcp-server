"""Pytest configuration."""
import sys
import pathlib

# Ensure src/ is on the path when running tests directly
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "src"))
