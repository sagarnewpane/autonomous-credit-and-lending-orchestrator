"""
In-memory data backend for offline runs.

Lets the whole LangGraph pipeline run on the hackathon's Track A files without
PostgreSQL. Enable it with:

    DATA_BACKEND=files
    TRACK_A_DIR=/path/to/"Track A"/structured

Tables load lazily from CSV or Parquet the first time they are queried. Writes
(insert, update, upsert, delete) change the in-memory copy only and are lost when
the process exits; nothing is written back to the source files.

The query builder mirrors the subset of the Supabase-style API used in this code
base (see app/db/postgres.py), so agents do not need to know which backend runs.
"""

from __future__ import annotations

import math
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from app.services.as_of import TRACK_A_AS_OF

# Track A records run from January to June 2024: replay them as of the end of that window,
# so results do not depend on the day the code runs.
os.environ.setdefault("INCOME_AS_OF_DATE", TRACK_A_AS_OF)

TABLE_FILES = {
    "applicant_profiles": "applicant_profiles.csv",
    "loan_applications": "loan_applications.csv",
    "income_signal_features": "income_signal_features.csv",
    "cooperative_members": "cooperative_members.csv",
    "cooperative_sales": "cooperative_sales.csv",
    "credit_score_components": "credit_score_components.csv",
    "loan_outcomes": "loan_outcomes.csv",
    "mobile_money_transactions": "mobile_money_transactions.parquet",
    "remittance_records": "remittance_records.parquet",
    "utility_payments": "utility_payments.parquet",
}


def _clean(value: Any) -> Any:
    """Convert pandas/numpy scalars to plain Python values; NaN becomes None."""
    if value is None:
        return None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        f = float(value)
        return None if math.isnan(f) else f
    if isinstance(value, pd.Timestamp):
        return None if pd.isna(value) else value.isoformat()
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


class _Store:
    """Holds one DataFrame per table plus lookup indexes, guarded by a lock."""

    def __init__(self, root: Optional[str]):
        self.root = Path(root) if root else None
        self.frames: Dict[str, pd.DataFrame] = {}
        self.indexes: Dict[tuple, Dict[Any, np.ndarray]] = {}
        self.lock = threading.RLock()
        self.next_id: Dict[str, int] = {}

    def frame(self, name: str) -> pd.DataFrame:
        with self.lock:
            if name not in self.frames:
                self.frames[name] = self._load(name)
            return self.frames[name]

    def _load(self, name: str) -> pd.DataFrame:
        fname = TABLE_FILES.get(name)
        if not fname or self.root is None:
            return pd.DataFrame()
        path = self.root / fname
        if not path.exists():
            return pd.DataFrame()
        if path.suffix == ".parquet":
            return pd.read_parquet(path)
        return pd.read_csv(path, low_memory=False)

    def set_frame(self, name: str, df: pd.DataFrame) -> None:
        with self.lock:
            self.frames[name] = df.reset_index(drop=True)
            for key in [k for k in self.indexes if k[0] == name]:
                del self.indexes[key]

    def invalidate(self, name: str, cols: List[str]) -> None:
        """Drop cached indexes on the given columns after an in-place update."""
        with self.lock:
            for col in cols:
                self.indexes.pop((name, col), None)

    def positions(self, name: str, col: str, value: Any) -> np.ndarray:
        """Row positions where frame[col] == value, using a cached group index."""
        with self.lock:
            df = self.frame(name)
            if col not in df.columns:
                return np.array([], dtype=int)
            key = (name, col)
            if key not in self.indexes:
                self.indexes[key] = df.groupby(col, sort=False, dropna=True).indices
            return self.indexes[key].get(value, np.array([], dtype=int))


class Result:
    def __init__(self, data):
        self.data = data


class MemoryTable:
    """Supabase-like query builder over an in-memory DataFrame."""

    def __init__(self, store: _Store, table_name: str):
        self.store = store
        self.table_name = table_name
        self.reset()

    def reset(self):
        self._cols: Optional[List[str]] = None
        self._filters: List[tuple] = []
        self._order: Optional[tuple] = None
        self._limit: Optional[int] = None
        self._single = False
        return self

    # ---- query building -------------------------------------------------
    def select(self, cols: str = "*"):
        self._cols = None if cols.strip() == "*" else [c.strip() for c in cols.split(",") if c.strip()]
        return self

    def eq(self, col: str, val):
        self._filters.append(("eq", col, val))
        return self

    def neq(self, col: str, val):
        self._filters.append(("neq", col, val))
        return self

    def is_null(self, col: str):
        self._filters.append(("is_null", col, None))
        return self

    def is_not_null(self, col: str):
        self._filters.append(("is_not_null", col, None))
        return self

    def order(self, col: str, desc: bool = False):
        self._order = (col, desc)
        return self

    def limit(self, n: int):
        self._limit = int(n)
        return self

    def single(self):
        self._single = True
        self._limit = 1
        return self

    # ---- evaluation -----------------------------------------------------
    def _matching_positions(self, df: pd.DataFrame) -> np.ndarray:
        positions = None
        rest = list(self._filters)
        for i, (op, col, val) in enumerate(rest):
            if op == "eq":
                positions = self.store.positions(self.table_name, col, val)
                rest.pop(i)
                break
        if positions is None:
            positions = np.arange(len(df))
        if len(positions) == 0 or not rest:
            return np.asarray(positions)
        sub = df.iloc[positions]
        mask = np.ones(len(sub), dtype=bool)
        for op, col, val in rest:
            if col not in sub.columns:
                mask &= op in ("is_null", "neq")
                continue
            s = sub[col]
            if op == "eq":
                mask &= (s == val).to_numpy()
            elif op == "neq":
                mask &= (s != val).to_numpy()
            elif op == "is_null":
                mask &= s.isna().to_numpy()
            elif op == "is_not_null":
                mask &= s.notna().to_numpy()
        return np.asarray(positions)[mask]

    def _records(self, df: pd.DataFrame) -> List[dict]:
        if self._cols:
            df = df[[c for c in self._cols if c in df.columns]]
        return [{k: _clean(v) for k, v in row.items()} for row in df.to_dict(orient="records")]

    def execute(self):
        with self.store.lock:
            df = self.store.frame(self.table_name)
            if df.empty:
                data: Any = None if self._single else []
                self.reset()
                return Result(data)
            sub = df.iloc[self._matching_positions(df)]
            if self._order and self._order[0] in sub.columns:
                sub = sub.sort_values(self._order[0], ascending=not self._order[1])
            if self._limit is not None:
                sub = sub.head(self._limit)
            rows = self._records(sub)
            single = self._single
            self.reset()
            if single:
                return Result(rows[0] if rows else None)
            return Result(rows)

    # ---- writes ---------------------------------------------------------
    def insert(self, record):
        records = [dict(r) for r in (record if isinstance(record, list) else [record])]
        with self.store.lock:  # mimic a database-generated integer primary key
            for r in records:
                if "id" not in r:
                    self.store.next_id[self.table_name] = self.store.next_id.get(self.table_name, 0) + 1
                    r["id"] = self.store.next_id[self.table_name]
        with self.store.lock:
            df = self.store.frame(self.table_name)
            new = pd.DataFrame(records)
            self.store.set_frame(self.table_name, pd.concat([df, new], ignore_index=True) if not df.empty else new)
        self.reset()
        return Result(records)

    def update(self, record: dict):
        with self.store.lock:
            df = self.store.frame(self.table_name)
            if df.empty:
                self.reset()
                return Result([])
            pos = self._matching_positions(df)
            for k, v in record.items():
                if k not in df.columns:
                    df[k] = pd.Series([None] * len(df), dtype=object)
                if len(pos):
                    is_scalar_number = isinstance(v, (int, float, np.number)) and not isinstance(v, bool)
                    if not is_scalar_number and df[k].dtype != object:
                        df[k] = df[k].astype(object)
                    elif is_scalar_number and df[k].dtype.kind not in "fiu" and df[k].dtype != object:
                        df[k] = df[k].astype(object)
                    col = df.columns.get_loc(k)
                    if isinstance(v, (list, dict)):
                        for p_ in pos:
                            df.iat[int(p_), col] = v
                    else:
                        df.iloc[pos, col] = v
            self.store.invalidate(self.table_name, list(record.keys()))
            updated = self._records(df.iloc[pos]) if len(pos) else []
        self.reset()
        return Result(updated)

    def upsert(self, record, on_conflict: Optional[str] = None):
        records = record if isinstance(record, list) else [record]
        key = on_conflict or "id"
        out = []
        for rec in records:
            self.reset()
            if key in rec and rec[key] is not None:
                existing = self.eq(key, rec[key])._matching_positions(self.store.frame(self.table_name)) \
                    if not self.store.frame(self.table_name).empty else np.array([])
                self.reset()
                if len(existing):
                    changes = {k: v for k, v in rec.items() if k != key}
                    out.extend(self.eq(key, rec[key]).update(changes).data)
                    continue
            out.extend(self.insert(rec).data)
        self.reset()
        return Result(out)

    def delete(self):
        with self.store.lock:
            df = self.store.frame(self.table_name)
            if not df.empty:
                pos = self._matching_positions(df)
                self.store.set_frame(self.table_name, df.drop(df.index[pos]))
        self.reset()
        return Result([])


class MemoryClient:
    """Drop-in replacement for PostgresClient backed by Track A files."""

    def __init__(self, root: Optional[str] = None):
        self.store = _Store(root or os.getenv("TRACK_A_DIR"))

    def table(self, name: str) -> MemoryTable:
        return MemoryTable(self.store, name)

    def raw(self, sql: str, params=None):
        raise NotImplementedError("Raw SQL is not available in the file-backed mode.")


db = MemoryClient()
