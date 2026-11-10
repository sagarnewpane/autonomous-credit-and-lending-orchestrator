"""
SQLite data backend.

The API and the agents only use a small subset of the Supabase-style query
builder: select, eq/neq/is_null/is_not_null, order, limit, single, insert,
update, upsert, delete, plus raw SQL for the admin dashboard. This module
implements that subset with the Python standard-library ``sqlite3`` module.

The database is intentionally schema-on-demand: the core tables are created
up-front so admin raw-SQL queries work against an empty database, and columns
are added as records are written. That keeps the SQLite backend compatible with
the pipeline's optional assessment columns without a migration step.

Set ``DATA_BACKEND=sqlite`` to use it. ``SQLITE_PATH`` selects the file. On
Vercel the default is ``/tmp/dhago.db`` because only ``/tmp`` is writable; that
means the database is per-instance and disappears on a cold start.
"""

from __future__ import annotations

import json
import math
import os
import re
import sqlite3
import threading
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# Values stored as JSON text and decoded again when read.
_JSON_COLUMNS = {
    "compliance_flags",
    "decision_reasons",
    "drivers",
    "features",
    "income_flags",
    "shap_features",
}

# Values stored as SQLite integers and exposed as Python booleans.
_BOOL_COLUMNS = {
    "aml_flag",
    "cooperative_member",
    "has_esewa_account",
    "has_khalti_account",
    "is_active",
    "is_admin",
    "nrb_blacklist_flag",
    "remittance_receiving",
}

# Core tables and the columns that raw SQL and the application rely on. Missing
# columns are added automatically, so this is a starting point, not a limit.
_CORE_SCHEMA: Dict[str, Dict[str, str]] = {
    "users": {
        "email": "TEXT UNIQUE NOT NULL",
        "hashed_password": "TEXT NOT NULL",
        "applicant_id": "TEXT",
        "is_admin": "INTEGER NOT NULL DEFAULT 0",
        "is_active": "INTEGER NOT NULL DEFAULT 1",
        "created_at": "TEXT DEFAULT CURRENT_TIMESTAMP",
    },
    "applicant_profiles": {
        "applicant_id": "TEXT",
        "full_name_en": "TEXT",
        "father_name_en": "TEXT",
        "grandfather_name_en": "TEXT",
        "gender": "TEXT",
        "marital_status": "TEXT",
        "citizenship_number": "TEXT",
        "citizenship_date_bs": "TEXT",
        "citizenship_office": "TEXT",
        "dob_ad": "TEXT",
        "dob_bs": "TEXT",
        "province_en": "TEXT",
        "district_en": "TEXT",
        "municipality_en": "TEXT",
        "ward_no": "INTEGER",
        "phone_primary": "TEXT",
        "occupation_en": "TEXT",
        "occupation_np": "TEXT",
        "education_level": "TEXT",
        "household_size": "INTEGER",
        "has_esewa_account": "INTEGER DEFAULT 0",
        "esewa_account_id": "TEXT",
        "has_khalti_account": "INTEGER DEFAULT 0",
        "khalti_account_id": "TEXT",
        "primary_bank": "TEXT",
        "remittance_receiving": "INTEGER DEFAULT 0",
        "cooperative_member": "INTEGER DEFAULT 0",
        "cooperative_id": "TEXT",
        "land_area_ropani": "REAL",
        "kyc_tier": "TEXT",
        "nrb_blacklist_flag": "INTEGER",
        "aml_flag": "INTEGER",
        "created_at": "TEXT DEFAULT CURRENT_TIMESTAMP",
    },
    "loan_applications": {
        "application_id": "TEXT",
        "applicant_id": "TEXT",
        "application_date_ad": "TEXT",
        "application_date_bs": "TEXT",
        "loan_purpose": "TEXT",
        "requested_amount_nrs": "REAL",
        "requested_tenure_months": "INTEGER",
        "collateral_type": "TEXT",
        "collateral_value_nrs": "REAL",
        "has_esewa_account": "INTEGER DEFAULT 0",
        "has_khalti_account": "INTEGER DEFAULT 0",
        "remittance_receiving": "INTEGER DEFAULT 0",
        "cooperative_member": "INTEGER DEFAULT 0",
        "cooperative_id": "TEXT",
        "province_en": "TEXT",
        "district_en": "TEXT",
        "municipality_en": "TEXT",
        "ward_no": "INTEGER",
        "existing_loan_count": "INTEGER DEFAULT 0",
        "existing_loan_amount": "REAL",
        "final_decision": "TEXT",
        "approved_amount_nrs": "REAL",
        "interest_tier": "TEXT",
        "interest_rate_pct": "REAL",
        "interest_rate": "REAL",
        "decision_reason": "TEXT",
        "decision_reasons": "TEXT",
        "counter_offer": "TEXT",
        "credit_score": "INTEGER",
        "score_band": "TEXT",
        "pd_estimate": "REAL",
        "shap_features": "TEXT",
        "model_version": "TEXT",
        "income_agent_monthly_est": "REAL",
        "income_confidence": "REAL",
        "income_mismatch_ratio": "REAL",
        "dsr": "REAL",
        "loan_to_income": "REAL",
        "monthly_debt": "REAL",
        "policy_version": "TEXT",
        "compliance_status": "TEXT",
        "compliance_flags": "TEXT",
        "nrb_blacklist_flag": "INTEGER",
        "aml_flag": "INTEGER",
        "officer_notes": "TEXT",
        "created_at": "TEXT DEFAULT CURRENT_TIMESTAMP",
    },
    "income_signal_features": {
        "applicant_id": "TEXT",
    },
    "credit_score_components": {},
    "loan_outcomes": {},
}

_DEMO_ADMIN = {
    "email_env": "DEMO_ADMIN_EMAIL",
    "email_default": "admin@dhago.app",
    "password_env": "DEMO_ADMIN_PASSWORD",
    "password_default": "Admin@2026",
    "applicant_default": "AP-ADMIN001",
    "is_admin": True,
}
_DEMO_USER = {
    "email_env": "DEMO_USER_EMAIL",
    "email_default": "demo@dhago.app",
    "password_env": "DEMO_USER_PASSWORD",
    "password_default": "Demo@2026",
    "applicant_default": "AP-DEMO001",
    "is_admin": False,
}


def _check_identifier(name: str) -> str:
    if not _IDENTIFIER.match(name):
        raise ValueError(f"Invalid SQL identifier: {name!r}")
    return name


def _quote(name: str) -> str:
    return f'"{_check_identifier(name)}"'


def _sql_type(value: Any) -> str:
    if isinstance(value, bool) or isinstance(value, int):
        return "INTEGER"
    if isinstance(value, float):
        return "REAL"
    return "TEXT"


def _base_type(declaration: str) -> str:
    """Strip constraints so a column can be added to an existing table."""
    return declaration.split()[0] if declaration else "TEXT"


def _serialize(value: Any) -> Any:
    """Convert Python/pandas/numpy values into something sqlite3 accepts."""
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return None if math.isnan(value) or math.isinf(value) else value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, default=str)
    # numpy scalars expose .item(); pandas timestamps expose .isoformat().
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        try:
            return _serialize(value.item())
        except (TypeError, ValueError):
            pass
    if hasattr(value, "isoformat") and not isinstance(value, (str, bytes)):
        try:
            return value.isoformat()
        except (TypeError, ValueError):
            pass
    return str(value)


def _decode_row(row: sqlite3.Row) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key in row.keys():
        value = row[key]
        if value is not None and key in _BOOL_COLUMNS:
            out[key] = bool(value)
        elif value is not None and key in _JSON_COLUMNS and isinstance(value, str):
            try:
                out[key] = json.loads(value)
            except (TypeError, ValueError):
                out[key] = value
        else:
            out[key] = value
    return out


class Result:
    """Mimics the Supabase result object with a .data attribute."""

    def __init__(self, data: Any):
        self.data = data


class SQLiteTable:
    """Supabase-like query builder for one SQLite table."""

    def __init__(self, client: "SQLiteClient", table_name: str):
        self.client = client
        self.table_name = _check_identifier(table_name)
        self.reset()

    def reset(self):
        self._select_cols: Optional[List[str]] = None
        self._filters: List[tuple] = []
        self._order: Optional[tuple] = None
        self._limit: Optional[int] = None
        self._single = False
        return self

    # ---- query building -------------------------------------------------
    def select(self, cols: str = "*"):
        cols = (cols or "*").strip()
        self._select_cols = None if cols == "*" else [c.strip() for c in cols.split(",") if c.strip()]
        return self

    def eq(self, col: str, val):
        self._filters.append(("eq", _check_identifier(col), val))
        return self

    def neq(self, col: str, val):
        self._filters.append(("neq", _check_identifier(col), val))
        return self

    def is_null(self, col: str):
        self._filters.append(("is_null", _check_identifier(col), None))
        return self

    def is_not_null(self, col: str):
        self._filters.append(("is_not_null", _check_identifier(col), None))
        return self

    def order(self, col: str, desc: bool = False):
        self._order = (_check_identifier(col), bool(desc))
        return self

    def limit(self, n: int):
        self._limit = int(n)
        return self

    def single(self):
        self._single = True
        self._limit = 1
        return self

    # ---- helpers --------------------------------------------------------
    def _columns_to_ensure(self) -> Dict[str, str]:
        columns: Dict[str, str] = {}
        for col in self._select_cols or []:
            columns.setdefault(col, "TEXT")
        for _op, col, _val in self._filters:
            columns.setdefault(col, "TEXT")
        if self._order:
            columns.setdefault(self._order[0], "TEXT")
        return columns

    def _where_sql(self) -> tuple[str, List[Any]]:
        clauses: List[str] = []
        params: List[Any] = []
        for op, col, val in self._filters:
            quoted = _quote(col)
            if op == "eq":
                clauses.append(f"{quoted} = ?")
                params.append(_serialize(val))
            elif op == "neq":
                clauses.append(f"{quoted} != ?")
                params.append(_serialize(val))
            elif op == "is_null":
                clauses.append(f"{quoted} IS NULL")
            elif op == "is_not_null":
                clauses.append(f"{quoted} IS NOT NULL")
        return (" WHERE " + " AND ".join(clauses)) if clauses else "", params

    def _select(self, conn: sqlite3.Connection, fetch_all: bool = True) -> Any:
        cols = ", ".join(_quote(c) for c in self._select_cols) if self._select_cols else "*"
        sql = f"SELECT {cols} FROM {_quote(self.table_name)}"
        where, params = self._where_sql()
        sql += where
        if self._order:
            sql += f" ORDER BY {_quote(self._order[0])} {'DESC' if self._order[1] else 'ASC'}"
        if self._limit is not None:
            sql += f" LIMIT {int(self._limit)}"
        rows = conn.execute(sql, params).fetchall()
        if not fetch_all:
            return rows
        if self._single:
            return _decode_row(rows[0]) if rows else None
        return [_decode_row(row) for row in rows]

    # ---- reads ----------------------------------------------------------
    def execute(self):
        with self.client._lock, self.client._connect() as conn:
            self.client._ensure_table(conn, self.table_name)
            self.client._ensure_columns(conn, self.table_name, self._columns_to_ensure())
            data = self._select(conn)
        self.reset()
        return Result(data)

    # ---- writes ---------------------------------------------------------
    def insert(self, record):
        records = [dict(r) for r in (record if isinstance(record, list) else [record])]
        if not records:
            return Result([])
        out: List[Dict[str, Any]] = []
        with self.client._lock, self.client._connect() as conn:
            self.client._ensure_table(conn, self.table_name)
            for rec in records:
                self.client._ensure_columns(
                    conn,
                    self.table_name,
                    {k: _sql_type(v) for k, v in rec.items() if k != "id"},
                )
                cols = [k for k in rec.keys() if k != "id" or rec[k] is not None]
                if cols:
                    placeholders = ", ".join("?" for _ in cols)
                    sql = (
                        f"INSERT INTO {_quote(self.table_name)} "
                        f"({', '.join(_quote(c) for c in cols)}) VALUES ({placeholders})"
                    )
                    cursor = conn.execute(sql, [_serialize(rec[c]) for c in cols])
                else:
                    cursor = conn.execute(f"INSERT INTO {_quote(self.table_name)} DEFAULT VALUES")
                row_id = rec.get("id") or cursor.lastrowid
                row = conn.execute(
                    f"SELECT * FROM {_quote(self.table_name)} WHERE {_quote('id')} = ?",
                    (row_id,),
                ).fetchone()
                if row is not None:
                    out.append(_decode_row(row))
        self.reset()
        return Result(out)

    def update(self, record: dict):
        if not self._filters:
            raise ValueError("UPDATE requires at least one WHERE clause")
        record = dict(record)
        with self.client._lock, self.client._connect() as conn:
            self.client._ensure_table(conn, self.table_name)
            self.client._ensure_columns(
                conn,
                self.table_name,
                {k: _sql_type(v) for k, v in record.items()},
            )
            self.client._ensure_columns(conn, self.table_name, self._columns_to_ensure())
            set_sql = ", ".join(f"{_quote(c)} = ?" for c in record)
            where, where_params = self._where_sql()
            sql = f"UPDATE {_quote(self.table_name)} SET {set_sql}{where}"
            conn.execute(sql, [_serialize(v) for v in record.values()] + where_params)
            rows = conn.execute(
                f"SELECT * FROM {_quote(self.table_name)}{where}",
                where_params,
            ).fetchall()
        self.reset()
        return Result([_decode_row(row) for row in rows])

    def upsert(self, record, on_conflict: Optional[str] = None):
        records = [dict(r) for r in (record if isinstance(record, list) else [record])]
        key = _check_identifier(on_conflict or "id")
        out: List[Dict[str, Any]] = []
        with self.client._lock, self.client._connect() as conn:
            self.client._ensure_table(conn, self.table_name)
            for rec in records:
                self.client._ensure_columns(
                    conn,
                    self.table_name,
                    {k: _sql_type(v) for k, v in rec.items() if k != "id"},
                )
                existing = None
                if rec.get(key) is not None:
                    existing = conn.execute(
                        f"SELECT {_quote('id')} FROM {_quote(self.table_name)} "
                        f"WHERE {_quote(key)} = ? LIMIT 1",
                        (_serialize(rec[key]),),
                    ).fetchone()

                if existing is not None:
                    changes = {k: v for k, v in rec.items() if k != key}
                    if changes:
                        set_sql = ", ".join(f"{_quote(c)} = ?" for c in changes)
                        conn.execute(
                            f"UPDATE {_quote(self.table_name)} SET {set_sql} "
                            f"WHERE {_quote(key)} = ?",
                            [_serialize(v) for v in changes.values()] + [_serialize(rec[key])],
                        )
                    row = conn.execute(
                        f"SELECT * FROM {_quote(self.table_name)} "
                        f"WHERE {_quote(key)} = ? LIMIT 1",
                        (_serialize(rec[key]),),
                    ).fetchone()
                else:
                    cols = [k for k in rec.keys() if k != "id" or rec[k] is not None]
                    if cols:
                        placeholders = ", ".join("?" for _ in cols)
                        cursor = conn.execute(
                            f"INSERT INTO {_quote(self.table_name)} "
                            f"({', '.join(_quote(c) for c in cols)}) VALUES ({placeholders})",
                            [_serialize(rec[c]) for c in cols],
                        )
                    else:
                        cursor = conn.execute(
                            f"INSERT INTO {_quote(self.table_name)} DEFAULT VALUES"
                        )
                    row_id = rec.get("id") or cursor.lastrowid
                    row = conn.execute(
                        f"SELECT * FROM {_quote(self.table_name)} WHERE {_quote('id')} = ?",
                        (row_id,),
                    ).fetchone()
                if row is not None:
                    out.append(_decode_row(row))
        self.reset()
        return Result(out)

    def delete(self):
        with self.client._lock, self.client._connect() as conn:
            self.client._ensure_table(conn, self.table_name)
            self.client._ensure_columns(conn, self.table_name, self._columns_to_ensure())
            where, params = self._where_sql()
            conn.execute(f"DELETE FROM {_quote(self.table_name)}{where}", params)
        self.reset()
        return Result([])


class SQLiteClient:
    """Drop-in SQLite replacement for the PostgreSQL client."""

    def __init__(self, path: Optional[str] = None):
        self.path = str(Path(path or _default_path()).expanduser())
        parent = Path(self.path).parent
        parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._known_columns: Dict[str, set] = {}
        self._initialize()

    # ---- connection / schema -------------------------------------------
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _table_columns(self, conn: sqlite3.Connection, table: str) -> set:
        rows = conn.execute(f"PRAGMA table_info({_quote(table)})").fetchall()
        return {row["name"] for row in rows}

    def _create_core_table(self, conn: sqlite3.Connection, table: str, columns: Dict[str, str]) -> None:
        definitions = ["id INTEGER PRIMARY KEY AUTOINCREMENT"]
        for col, decl in columns.items():
            definitions.append(f"{_quote(col)} {decl}")
        conn.execute(
            f"CREATE TABLE IF NOT EXISTS {_quote(table)} ({', '.join(definitions)})"
        )
        self._known_columns[table] = self._table_columns(conn, table)

    def _ensure_table(self, conn: sqlite3.Connection, table: str) -> None:
        table = _check_identifier(table)
        if table in self._known_columns:
            return
        columns = _CORE_SCHEMA.get(table, {})
        if columns:
            self._create_core_table(conn, table, columns)
        else:
            conn.execute(
                f"CREATE TABLE IF NOT EXISTS {_quote(table)} "
                "(id INTEGER PRIMARY KEY AUTOINCREMENT)"
            )
            self._known_columns[table] = self._table_columns(conn, table)

    def _ensure_columns(self, conn: sqlite3.Connection, table: str, columns: Dict[str, str]) -> None:
        if not columns:
            return
        existing = self._known_columns.get(table)
        if existing is None:
            existing = self._table_columns(conn, table)
            self._known_columns[table] = existing
        for col, decl in columns.items():
            col = _check_identifier(col)
            if col == "id" or col in existing:
                continue
            conn.execute(
                f"ALTER TABLE {_quote(table)} ADD COLUMN {_quote(col)} {decl}"
            )
            existing.add(col)

    def _initialize(self) -> None:
        with self._lock, self._connect() as conn:
            for table, columns in _CORE_SCHEMA.items():
                self._create_core_table(conn, table, columns)
                # Upgrade a database created by an older version of this module.
                self._ensure_columns(
                    conn,
                    table,
                    {col: _base_type(decl) for col, decl in columns.items()},
                )
            self._seed_demo_users(conn)

    def _seed_demo_users(self, conn: sqlite3.Connection) -> None:
        if os.getenv("SEED_DEMO_USERS", "1").strip().lower() in {"0", "false", "no", "off"}:
            return
        from app.services.auth_service import hash_password

        for spec in (_DEMO_ADMIN, _DEMO_USER):
            email = os.getenv(spec["email_env"], spec["email_default"]).strip()
            password = os.getenv(spec["password_env"], spec["password_default"])
            if not email or not password:
                continue
            exists = conn.execute(
                f"SELECT {_quote('id')} FROM {_quote('users')} WHERE {_quote('email')} = ? LIMIT 1",
                (email,),
            ).fetchone()
            if exists:
                continue
            conn.execute(
                f"INSERT INTO {_quote('users')} "
                f"({_quote('email')}, {_quote('hashed_password')}, "
                f"{_quote('applicant_id')}, {_quote('is_admin')}, {_quote('is_active')}) "
                "VALUES (?, ?, ?, ?, 1)",
                (
                    email,
                    hash_password(password),
                    spec["applicant_default"],
                    int(spec["is_admin"]),
                ),
            )

    # ---- public API -----------------------------------------------------
    def table(self, name: str) -> SQLiteTable:
        return SQLiteTable(self, name)

    def raw(self, sql: str, params: Optional[Iterable[Any]] = None):
        """Execute raw SQL and return rows as a list of dictionaries."""
        # The admin queries are shared with psycopg2, so accept its %s markers.
        adapted = sql.replace("%s", "?")
        with self._lock, self._connect() as conn:
            rows = conn.execute(adapted, list(params or [])).fetchall()
        return [_decode_row(row) for row in rows]


def _default_path() -> str:
    configured = os.getenv("SQLITE_PATH")
    if configured:
        return configured
    if os.getenv("VERCEL"):
        return "/tmp/dhago.db"
    return str(Path(__file__).resolve().parents[2] / "data" / "dhago.db")


db = SQLiteClient()
