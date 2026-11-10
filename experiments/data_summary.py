"""
Describe the Track A data as used in the paper (Section IV-A): table sizes, splits, the
organisers' decision labels and the synthetic repayment outcomes.

    python experiments/data_summary.py --data "/path/Track A/structured"
"""

from __future__ import annotations

import pandas as pd

import common  # noqa: F401
from common import data_dir, load_applications, load_outcomes, save_json


def main():
    d = data_dir()
    la = load_applications(d)
    lo = load_outcomes(d)
    label = la["final_decision"].astype(str).str.strip().str.lower()
    res = {
        "applicants": int(pd.read_csv(d / "applicant_profiles.csv", usecols=["applicant_id"])["applicant_id"].nunique()),
        "applications": int(len(la)),
        "splits": la["data_split"].value_counts().to_dict(),
        "organiser_label_share": label.value_counts(normalize=True).round(6).to_dict(),
        "loans_with_outcomes": int(len(lo)),
        "outcome_share": lo["outcome"].value_counts(normalize=True).round(6).to_dict(),
    }
    for name, fname in [("wallet_transactions", "mobile_money_transactions.parquet"),
                        ("remittances", "remittance_records.parquet"),
                        ("utility_payments", "utility_payments.parquet")]:
        t = pd.read_parquet(d / fname, columns=["applicant_id"])
        res[name] = {"rows": int(len(t)), "applicants": int(t["applicant_id"].nunique())}
    res["cooperative_sales_rows"] = int(len(pd.read_csv(d / "cooperative_sales.csv", low_memory=False)))
    save_json(res, "data_summary.json")
    print(res)


if __name__ == "__main__":
    main()
