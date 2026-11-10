"""
Database access.

DATA_BACKEND selects where agents read and write:
  postgres (default)  PostgreSQL via psycopg2, configured by DB_URL
  files               in-memory tables loaded from the Track A files in TRACK_A_DIR
"""

import os

# On Vercel there is no bundled PostgreSQL, so the file-backed API is the safe default.
_default_backend = "files" if os.getenv("VERCEL") else "postgres"

if os.getenv("DATA_BACKEND", _default_backend).strip().lower() == "files":
    from .memory import db  # noqa: F401
else:
    from .postgres import db  # noqa: F401

from .database import get_db, create_db_and_tables  # noqa: E402,F401
