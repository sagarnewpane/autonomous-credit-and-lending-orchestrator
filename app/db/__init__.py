"""
Database access.

DATA_BACKEND selects where agents read and write:
  sqlite (default)    SQLite via the Python standard library
  postgres            PostgreSQL via psycopg2, configured by DB_URL
  files               in-memory tables loaded from the Track A files in TRACK_A_DIR

SQLite is the default so the API runs out of the box without a database server.
Set SQLITE_PATH to choose the file. On Vercel the default is /tmp/dhago.db.
"""

import os

_default_backend = "sqlite"

_backend = os.getenv("DATA_BACKEND", _default_backend).strip().lower()
if _backend == "files":
    from .memory import db  # noqa: F401
elif _backend == "postgres":
    from .postgres import db  # noqa: F401
else:
    from .sqlite import db  # noqa: F401

from .database import get_db, create_db_and_tables  # noqa: E402,F401
