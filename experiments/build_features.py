"""
Compute the Income Agent's features for every Track A applicant.

Uses app.agents.income_agent.compute_income_assessment, the same function the live
Income Agent node calls, on raw wallet, remittance, cooperative and utility records.
Writes experiments/cache/income_features.parquet (one row per applicant).

    python experiments/build_features.py --data "/path/Track A/structured" [--workers 2]
"""

from __future__ import annotations

import argparse
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

import common  # noqa: F401  (sets sys.path)
from common import CACHE, data_dir, ensure_dirs, records

MOBILE_COLS = ["transaction_id", "applicant_id", "platform", "transaction_date", "transaction_type",
               "amount_nrs", "direction", "counterparty_category"]
# The remittance and utility columns must include every field in income_agent.REMITTANCE_KEY
# and UTILITY_KEY, so that repeated rows are recognised exactly as in the live pipeline.
# The generator's _noise_* columns are not loaded: the Income Agent does not use them.
REMIT_COLS = ["remittance_id", "applicant_id", "sender_name", "sender_country_code", "sender_city",
              "transfer_service", "transfer_date_ad", "received_date_ad", "amount_foreign_currency",
              "foreign_currency_code", "amount_nrs", "exchange_rate", "transaction_fee_nrs", "disbursement_mode",
              "name_match_score"]
UTIL_COLS = ["payment_id", "applicant_id", "utility_type", "provider", "service_number", "billing_period_ad",
             "bill_amount_nrs", "units_consumed", "due_date_ad", "payment_date_ad", "payment_method", "days_late",
             "outstanding_arrears_nrs"]
COOP_SALES_COLS = ["applicant_id", "sale_year_bs", "season", "total_amount_nrs"]


def _group(df: pd.DataFrame, ids) -> dict:
    sub = df[df["applicant_id"].isin(ids)]
    out = {}
    for aid, g in sub.groupby("applicant_id", sort=False):
        out[aid] = records(g)
    return out


def _work(chunk):
    from app.agents.income_agent import compute_income_assessment
    rows = []
    for db_data in chunk:
        aid = db_data.pop("applicant_id")
        a = compute_income_assessment(db_data, {})
        src = a["income_profile"].get("sources", {})
        row = {"applicant_id": aid, **a["income_signal_features"],
               "remittance_share": a["remittance_share"],
               "months_of_data": a["months_of_data"],
               "income_flags": ",".join(a["income_flags"]),
               "inc_remittance": src.get("remittance_agent", {}).get("monthly_usable_income", 0.0),
               "inc_coop": src.get("COOPERATIVE_SALES", {}).get("monthly_usable_income", 0.0)}
        row["inc_wallet_other"] = row["derived_income_est"] - row["inc_remittance"] - row["inc_coop"]
        rows.append(row)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--chunk", type=int, default=2000)
    args, _ = ap.parse_known_args()
    d = data_dir()
    ensure_dirs()
    t0 = time.time()
    mobile = pd.read_parquet(d / "mobile_money_transactions.parquet", columns=MOBILE_COLS)
    remit = pd.read_parquet(d / "remittance_records.parquet", columns=REMIT_COLS)
    util = pd.read_parquet(d / "utility_payments.parquet", columns=UTIL_COLS)
    coop_sales = pd.read_csv(d / "cooperative_sales.csv", usecols=COOP_SALES_COLS)
    coop_mem = pd.read_csv(d / "cooperative_members.csv", usecols=["applicant_id", "cooperative_type", "membership_year_bs"])
    coop_mem = coop_mem.drop_duplicates("applicant_id").set_index("applicant_id")
    prof = pd.read_csv(d / "applicant_profiles.csv", usecols=["applicant_id", "occupation_en", "land_area_ropani"]) \
        .drop_duplicates("applicant_id").set_index("applicant_id")
    apps = pd.read_csv(d / "loan_applications.csv", usecols=["applicant_id", "application_date_bs"]) \
        .drop_duplicates("applicant_id").set_index("applicant_id")
    ids = list(prof.index)
    print(f"loaded tables in {time.time() - t0:.0f}s; {len(ids):,} applicants")

    from app.agents.income_agent import _safe_float, _safe_str
    results = []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = []
        for i in range(0, len(ids), args.chunk):
            chunk_ids = ids[i:i + args.chunk]
            gm, gr, gu, gc = (_group(t, chunk_ids) for t in (mobile, remit, util, coop_sales))
            chunk = []
            for aid in chunk_ids:
                cm = coop_mem.loc[aid] if aid in coop_mem.index else None
                bs = str(apps.loc[aid, "application_date_bs"]) if aid in apps.index else ""
                chunk.append({
                    "applicant_id": aid,
                    "mobile_txns": gm.get(aid, []),
                    "remittances": gr.get(aid, []),
                    "coop_sales": gc.get(aid, []),
                    "utility_payments": gu.get(aid, []),
                    "coop_member_type": _safe_str(cm["cooperative_type"]) if cm is not None else "",
                    "coop_membership_year_bs": cm["membership_year_bs"] if cm is not None else None,
                    "land_area_ropani": _safe_float(prof.loc[aid, "land_area_ropani"]) if pd.notna(prof.loc[aid, "land_area_ropani"]) else 0.0,
                    "occupation": _safe_str(prof.loc[aid, "occupation_en"], "unknown") if pd.notna(prof.loc[aid, "occupation_en"]) else "unknown",
                    "reference_bs_year": int(bs[:4]) if bs[:4].isdigit() else None,
                })
            futures.append(pool.submit(_work, chunk))
            if len(futures) >= args.workers * 2:
                results.extend(futures.pop(0).result())
                print(f"  {len(results):,} done ({time.time() - t0:.0f}s)")
        for f in futures:
            results.extend(f.result())
    out = pd.DataFrame(results)
    path = CACHE / "income_features.parquet"
    out.to_parquet(path, index=False)
    print(f"wrote {path} with {len(out):,} rows in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
