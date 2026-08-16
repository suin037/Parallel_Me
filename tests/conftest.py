"""Shared import paths for repository-level tests."""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"

for path in (ROOT, BACKEND):
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)
