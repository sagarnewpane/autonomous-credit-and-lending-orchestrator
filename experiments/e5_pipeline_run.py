"""
E5. End-to-end run of the LangGraph pipeline in offline mode.

Runs income -> compliance -> scoring -> decision on public_test applications with the
file-backed data layer, then checks that
  * every run finishes with a decision and the audit chain verifies;
  * decisions match the batch computation in E4 for the same applications (same code path);
and reports per-stage wall-clock times (in-process; no network, database or LLM calls).

    python experiments/e5_pipeline_run.py --data "/path/Track A/structured" --n 300
"""

from __future__ import annotations

import argparse
import os
import re
import tempfile
import time

import numpy as np
import pandas as pd

import common  # noqa: F401
from common import CACHE, data_dir, ensure_dirs, save_json


def _amount(v):
    s = re.sub(r"[^\d.\-]", "", str(v or ""))
    try:
        return abs(float(s)) if s not in ("", "-", ".") else None
    except ValueError:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    args, _ = ap.parse_known_args()
    d = data_dir()
    ensure_dirs()
    os.environ["DATA_BACKEND"] = "files"
    os.environ["TRACK_A_DIR"] = str(d)
    log = os.path.join(tempfile.mkdtemp(), "audit_log.jsonl")
    os.environ["AUDIT_LOG_PATH"] = log
    import logging
    logging.basicConfig(level=logging.ERROR)
    from app.agents.pipeline import get_workflow
    from app.db import db
    from app.services import audit

    t_load = time.perf_counter()
    apps = db.table("loan_applications").select("*").eq("data_split", "public_test").limit(args.n).execute().data
    wf = get_workflow()
    wf.invoke({"applicant_id": apps[0]["applicant_id"], "application_id": "WARMUP", "loan_request": {}})  # loads tables
    load_s = time.perf_counter() - t_load
    rows = []
    for app in apps:
        state = {"applicant_id": app["applicant_id"], "application_id": app["application_id"],
                 "loan_request": {"amount": _amount(app.get("requested_amount_nrs")),
                                  "tenure_months": app.get("requested_tenure_months") or 12,
                                  "collateral_value_nrs": app.get("collateral_value_nrs"),
                                  "loan_purpose": app.get("loan_purpose"), "existing_liabilities_monthly": 0}}
        t0 = time.perf_counter()
        out = wf.invoke(state)
        total = (time.perf_counter() - t0) * 1000
        tm = (out.get("debug_info") or {}).get("timings_ms", {})
        rows.append({"application_id": app["application_id"], "decision": out.get("final_decision"),
                     "pd": (out.get("scorecard") or {}).get("pd"), "total_ms": total, **{f"ms_{k}": v for k, v in tm.items()}})
    df = pd.DataFrame(rows)
    e4 = pd.read_parquet(CACHE / "e4_decisions.parquet")[["application_id", "decision", "pd"]] \
        .rename(columns={"decision": "batch_decision", "pd": "batch_pd"})
    m = df.merge(e4, on="application_id", how="left")
    chain = audit.verify()
    stage_cols = [c for c in df.columns if c.startswith("ms_")]
    res = {
        "n": int(len(df)), "table_load_seconds": round(load_s, 1),
        "all_finished_with_decision": bool(df["decision"].notna().all()),
        "decision_mix": df["decision"].value_counts().to_dict(),
        "agreement_with_batch_decisions": round(float((m["decision"] == m["batch_decision"]).mean()), 4),
        "max_abs_pd_difference_vs_batch": round(float(np.nanmax(np.abs(m["pd"].astype(float) - m["batch_pd"].astype(float)))), 8),
        "audit_chain": chain,
        "audit_entries_per_application": round(chain["entries"] / max(len(df) + 1, 1), 2),
        "audit_entries_note": "includes one warm-up application; an application declined by a veto has 3 entries (scoring is skipped)",
        "latency_ms": {"total_median": round(float(df["total_ms"].median()), 1), "total_p95": round(float(df["total_ms"].quantile(0.95)), 1),
                       **{c[3:] + "_median": round(float(df[c].median()), 1) for c in stage_cols}},
        "note": "In-process times on a 2-vCPU container with in-memory tables; excludes database, network, OCR and LLM calls.",
    }
    save_json(res, "e5_pipeline_run.json")
    print(res)


if __name__ == "__main__":
    main()
