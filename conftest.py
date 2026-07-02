"""Ensure the repo root is importable so tests can `import pipeline`."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
