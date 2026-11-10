"""
Run the full LangGraph pipeline on Track A applications without PostgreSQL or Ollama.

    python scripts/run_offline.py --data "/path/Track A/structured" --split public_test --n 20
    python scripts/run_offline.py --data ... --application-id LA-2081-000123 --declared-income 25000

Reads the Track A files into memory (app/db/memory.py), runs income -> compliance ->
scoring -> decision for each application, prints one line per decision, writes the full
outputs to --out (JSON lines) and verifies the hash-chained audit log at the end.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _amount(v):
    if v is None:
        return None
    s = re.sub(r"[^\d.\-]", "", str(v))
    try:
        return abs(float(s)) if s not in ("", "-", ".") else None
    except ValueError:
        return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default=os.getenv("TRACK_A_DIR"), help="folder with the Track A structured files")
    ap.add_argument("--split", default="public_test", choices=["train", "val", "public_test"])
    ap.add_argument("--n", type=int, default=20, help="number of applications to run")
    ap.add_argument("--application-id", default=None)
    ap.add_argument("--declared-income", type=float, default=None,
                    help="self-declared monthly income to pass to the IMR check (Track A has none)")
    ap.add_argument("--out", default="offline_run.jsonl")
    ap.add_argument("--audit-log", default="audit_log.jsonl")
    args = ap.parse_args(argv)
    if not args.data:
        sys.exit("Pass --data or set TRACK_A_DIR")

    os.environ["DATA_BACKEND"] = "files"
    os.environ["TRACK_A_DIR"] = args.data
    os.environ["AUDIT_LOG_PATH"] = args.audit_log
    sys.path.insert(0, str(ROOT))
    import logging
    logging.basicConfig(level=logging.WARNING)

    from app.agents.pipeline import get_workflow
    from app.db import db
    from app.services import audit

    if args.application_id:
        apps = db.table("loan_applications").select("*").eq("application_id", args.application_id).execute().data
    else:
        apps = db.table("loan_applications").select("*").eq("data_split", args.split).limit(args.n).execute().data
    if not apps:
        sys.exit("No matching applications")

    wf = get_workflow()
    t_all = time.perf_counter()
    with open(args.out, "w", encoding="utf-8") as fh:
        for app in apps:
            state = {
                "applicant_id": app["applicant_id"],
                "application_id": app["application_id"],
                "loan_request": {
                    "amount": _amount(app.get("requested_amount_nrs")),
                    "tenure_months": app.get("requested_tenure_months") or 12,
                    "collateral_value_nrs": app.get("collateral_value_nrs"),
                    "loan_purpose": app.get("loan_purpose"),
                    "existing_liabilities_monthly": 0,
                    "declared_monthly_income": args.declared_income,
                },
            }
            t0 = time.perf_counter()
            result = wf.invoke(state)
            ms = (time.perf_counter() - t0) * 1000
            fo = result.get("final_output", {})
            print(f"{app['application_id']}  {fo.get('decision', '?'):11s}  PD={fo.get('pd')}  "
                  f"score={fo.get('credit_score')}  rules={','.join(fo.get('triggered_rules') or []) or '-'}  "
                  f"conf={result.get('income_confidence')}  {ms:.0f} ms")
            fh.write(json.dumps({"final_output": fo, "timings_ms": (result.get("debug_info") or {}).get("timings_ms"),
                                 "total_ms": round(ms, 2)}, default=str) + "\n")
    check = audit.verify()
    print(f"\n{len(apps)} applications in {time.perf_counter() - t_all:.1f}s; audit log {args.audit_log}: "
          f"{check['entries']} entries, chain {'OK' if check['ok'] else 'BROKEN at seq ' + str(check['first_bad_seq'])}")


if __name__ == "__main__":
    main()
