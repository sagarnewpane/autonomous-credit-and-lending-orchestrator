"""
Shared helpers for the experiments.

All experiments read the hackathon's Track A files from TRACK_A_DIR (or --data).
The data are not redistributed with this repository. Outputs:
  experiments/cache/    per-applicant intermediate files (git-ignored, contain derived data)
  experiments/results/  aggregate metrics (JSON/CSV) used in the paper
  experiments/figures/  figures used in the paper
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Replay Track A as of the end of its record window (January to June 2024), so that records
# dated later (the generator's impossible timestamps) are excluded without using its labels.
os.environ.setdefault("INCOME_AS_OF_DATE", "2024-06-30T23:59:59")

EXP = Path(__file__).resolve().parent
CACHE = EXP / "cache"
RESULTS = EXP / "results"
FIGURES = EXP / "figures"
SEED = 20261110


def data_dir(argv=None) -> Path:
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--data", default=os.getenv("TRACK_A_DIR"))
    args, _ = p.parse_known_args(argv)
    if not args.data:
        sys.exit("Set TRACK_A_DIR or pass --data /path/to/'Track A'/structured")
    d = Path(args.data)
    if not (d / "loan_applications.csv").exists():
        sys.exit(f"loan_applications.csv not found in {d}")
    return d


def ensure_dirs() -> None:
    for d in (CACHE, RESULTS, FIGURES):
        d.mkdir(parents=True, exist_ok=True)


def clean_amount(series: pd.Series) -> pd.Series:
    s = series.astype(str).str.replace(r"[^\d.\-]", "", regex=True).replace({"": np.nan, "-": np.nan, ".": np.nan})
    return pd.to_numeric(s, errors="coerce").abs()


def load_applications(d: Path) -> pd.DataFrame:
    la = pd.read_csv(d / "loan_applications.csv", low_memory=False)
    la["requested_amount_nrs"] = clean_amount(la["requested_amount_nrs"])
    return la


def load_profiles(d: Path) -> pd.DataFrame:
    return pd.read_csv(d / "applicant_profiles.csv", low_memory=False)


def load_outcomes(d: Path) -> pd.DataFrame:
    return pd.read_csv(d / "loan_outcomes.csv", low_memory=False)


def save_json(obj, name: str) -> Path:
    ensure_dirs()
    path = RESULTS / name
    path.write_text(json.dumps(obj, indent=2, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    return path


def records(df: pd.DataFrame) -> list:
    """DataFrame rows as dicts with NaN turned into None (the shape the database returns)."""
    obj = df.astype(object).where(df.notna(), None)
    return obj.to_dict(orient="records")
