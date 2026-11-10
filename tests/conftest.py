"""Tests run without PostgreSQL or Ollama: the file-backed data layer is used throughout."""
import os
import sys
from pathlib import Path

os.environ.setdefault("DATA_BACKEND", "files")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
