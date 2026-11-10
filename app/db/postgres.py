"""
PostgreSQL database client using psycopg2.
Replaces the Supabase client with direct SQL queries.
"""

import os
import json
import psycopg2
import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool
from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.getenv("DB_URL", "postgresql://user:password@localhost:5432/lending")

_pool = None


def _get_pool():
    global _pool
    if _pool is None:
        _pool = ThreadedConnectionPool(2, 10, DB_URL)
    return _pool


def get_connection():
    """Get a pooled database connection."""
    return _get_pool().getconn()


def put_connection(conn):
    """Return a connection to the pool."""
    _get_pool().putconn(conn)


@contextmanager
def get_cursor():
    """Context manager for database cursor using connection pool."""
    conn = get_connection()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        put_connection(conn)


class Table:
    """Supabase-like query builder for a single PostgreSQL table."""

    def __init__(self, table_name: str):
        self.table_name = table_name
        self._select_cols = "*"
        self._where_clauses = []
        self._where_params = []
        self._order_by = None
        self._limit_val = None
        self._single = False

    def select(self, cols: str = "*"):
        self._select_cols = cols
        return self

    def eq(self, col: str, val):
        self._where_clauses.append(f"{col} = %s")
        self._where_params.append(val)
        return self

    def neq(self, col: str, val):
        self._where_clauses.append(f"{col} != %s")
        self._where_params.append(val)
        return self

    def is_null(self, col: str):
        self._where_clauses.append(f"{col} IS NULL")
        return self

    def is_not_null(self, col: str):
        self._where_clauses.append(f"{col} IS NOT NULL")
        return self

    def order(self, col: str, desc: bool = False):
        direction = "DESC" if desc else "ASC"
        self._order_by = f"{col} {direction}"
        return self

    def limit(self, n: int):
        self._limit_val = n
        return self

    def single(self):
        self._single = True
        self._limit_val = 1
        return self

    def _build_select(self):
        sql = f"SELECT {self._select_cols} FROM {self.table_name}"
        params = list(self._where_params)
        if self._where_clauses:
            sql += " WHERE " + " AND ".join(self._where_clauses)
        if self._order_by:
            sql += f" ORDER BY {self._order_by}"
        if self._limit_val:
            sql += f" LIMIT {self._limit_val}"
        return sql, params

    def execute(self):
        sql, params = self._build_select()
        with get_cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        data = [dict(r) for r in rows]
        if self._single:
            data = data[0] if data else {}
        return Result(data)

    def insert(self, record):
        # Handle batch insert (list of dicts)
        if isinstance(record, list):
            if not record:
                return Result([])
            cols = list(record[0].keys())
            col_str = ", ".join(cols)
            placeholders = ", ".join(["%s"] * len(cols))
            sql = f"INSERT INTO {self.table_name} ({col_str}) VALUES ({placeholders})"
            with get_cursor() as cur:
                for r in record:
                    vals = [r.get(c) for c in cols]
                    cur.execute(sql, vals)
            return Result([])

        # Single record insert
        cols = list(record.keys())
        vals = list(record.values())
        placeholders = ", ".join(["%s"] * len(cols))
        col_str = ", ".join(cols)
        sql = f"INSERT INTO {self.table_name} ({col_str}) VALUES ({placeholders}) RETURNING *"
        with get_cursor() as cur:
            cur.execute(sql, vals)
            row = cur.fetchone()
        return Result([dict(row)] if row else [])

    def update(self, record: dict):
        if not self._where_clauses:
            raise ValueError("UPDATE requires at least one WHERE clause")
        set_parts = []
        set_params = []
        for col, val in record.items():
            set_parts.append(f"{col} = %s")
            set_params.append(val)
        sql = f"UPDATE {self.table_name} SET {', '.join(set_parts)} WHERE {' AND '.join(self._where_clauses)}"
        params = set_params + self._where_params
        with get_cursor() as cur:
            cur.execute(sql, params)
        return Result([])

    def upsert(self, record, on_conflict: str = None):
        # Handle batch upsert (list of dicts)
        if isinstance(record, list):
            if not record:
                return Result([])
            cols = list(record[0].keys())
            col_str = ", ".join(cols)
            update_cols = [c for c in cols if c != on_conflict] if on_conflict else cols
            update_set = ", ".join([f"{c} = EXCLUDED.{c}" for c in update_cols])
            placeholders = ", ".join(["%s"] * len(cols))

            if on_conflict and update_set:
                sql = (
                    f"INSERT INTO {self.table_name} ({col_str}) VALUES ({placeholders}) "
                    f"ON CONFLICT ({on_conflict}) DO UPDATE SET {update_set}"
                )
            else:
                sql = f"INSERT INTO {self.table_name} ({col_str}) VALUES ({placeholders})"

            with get_cursor() as cur:
                for r in record:
                    vals = [r.get(c) for c in cols]
                    cur.execute(sql, vals)
            return Result([])

        # Single record upsert
        cols = list(record.keys())
        vals = list(record.values())
        placeholders = ", ".join(["%s"] * len(cols))
        col_str = ", ".join(cols)
        update_cols = [c for c in cols if c != on_conflict] if on_conflict else cols
        update_set = ", ".join([f"{c} = EXCLUDED.{c}" for c in update_cols])

        if on_conflict and update_set:
            sql = (
                f"INSERT INTO {self.table_name} ({col_str}) VALUES ({placeholders}) "
                f"ON CONFLICT ({on_conflict}) DO UPDATE SET {update_set} RETURNING *"
            )
        else:
            sql = f"INSERT INTO {self.table_name} ({col_str}) VALUES ({placeholders}) RETURNING *"

        with get_cursor() as cur:
            cur.execute(sql, vals)
            row = cur.fetchone()
        return Result([dict(row)] if row else [])

    def delete(self):
        if not self._where_clauses:
            raise ValueError("DELETE requires at least one WHERE clause")
        sql = f"DELETE FROM {self.table_name} WHERE {' AND '.join(self._where_clauses)}"
        with get_cursor() as cur:
            cur.execute(sql, self._where_params)
        return Result([])

    def reset(self):
        self._select_cols = "*"
        self._where_clauses = []
        self._where_params = []
        self._order_by = None
        self._limit_val = None
        self._single = False
        return self


class Result:
    """Mimics Supabase Result object with .data attribute."""

    def __init__(self, data):
        self.data = data


class PostgresClient:
    """Main client that provides table() access, similar to Supabase Client."""

    def table(self, name: str) -> Table:
        return Table(name)

    def raw(self, sql: str, params=None):
        """Execute raw SQL and return rows as list of dicts."""
        with get_cursor() as cur:
            cur.execute(sql, params or [])
            rows = cur.fetchall()
        return [dict(r) for r in rows]


# Singleton client instance
db = PostgresClient()
