"""
Build showcase/examples.json: four invented applicants run through the real pipeline.

No Track A records are used. The script writes a tiny dataset in the Track A file layout,
filled with invented values only, to a temporary folder; runs the LangGraph pipeline on
each applicant with its own audit log; and keeps what the showcase site displays,
including the raw audit lines so the browser can check the real hashes.

    python scripts/make_showcase_examples.py            # writes showcase/examples.json
"""

from __future__ import annotations

import json
import os
import random
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "showcase" / "examples.json"   # not under data/: .gitignore excludes every data/ folder
MONTHS = ["2024-01", "2024-02", "2024-03", "2024-04", "2024-05", "2024-06"]
BS_MONTH = dict(zip(MONTHS, ["2080-09", "2080-10", "2080-11", "2080-12", "2081-01", "2081-02"]))

# ---------------------------------------------------------------- invented applicants
# Every value below is made up for the showcase. Names are deliberately absent.
APPLICANTS = [
    {
        "key": "remittance",
        "label": "Remittance household",
        "story": "Her husband works in Doha and sends money home every month through a transfer "
                 "company. She wants to repair the roof before the monsoon.",
        "declared_income": 40000,
        "profile": {"occupation_en": "small trader", "education_level": "slc", "household_size": 5,
                    "land_area_ropani": 3.5, "has_esewa_account": True, "has_khalti_account": False,
                    "remittance_receiving": True, "cooperative_member": False, "kyc_tier": "mid"},
        "application": {"loan_purpose": "home_repair", "requested_amount_nrs": 150000,
                        "requested_tenure_months": 24, "collateral_type": "land",
                        "collateral_value_nrs": 600000, "existing_loan_count": 0,
                        "credit_bureau_score": 712, "nrb_blacklist_flag": False, "aml_flag": False},
        "remittances": {"months": MONTHS, "qar": 1000, "rate": 36.6},
        "wallet": {"platform": "esewa", "months": MONTHS, "credits": [], "spend_per_month": 6},
        "utility": {"months": MONTHS, "late_days": [0, -2, 0, -1, 0, -3], "mobile": True},
    },
    {
        "key": "trader",
        "label": "Market trader, wallet only",
        "story": "He sells vegetables at a weekly market and deposits the cash into a wallet. "
                 "He opened the wallet two months ago and has no bank or bureau record.",
        "declared_income": 25000,
        "profile": {"occupation_en": "small trader", "education_level": "primary", "household_size": 4,
                    "land_area_ropani": 0, "has_esewa_account": False, "has_khalti_account": True,
                    "remittance_receiving": False, "cooperative_member": False, "kyc_tier": "basic"},
        "application": {"loan_purpose": "small_trade", "requested_amount_nrs": 60000,
                        "requested_tenure_months": 12, "collateral_type": "none",
                        "collateral_value_nrs": 0, "existing_loan_count": 0,
                        "credit_bureau_score": None, "nrb_blacklist_flag": False, "aml_flag": False},
        "remittances": None,
        "wallet": {"platform": "khalti", "months": MONTHS[-2:],
                   "credits": [("wallet_topup", "financial_services", 4500, 4)], "spend_per_month": 8},
        "utility": {"months": MONTHS[-2:], "late_days": [6, 9], "mobile": False, "mobile_only": True},
    },
    {
        "key": "overstated",
        "label": "Declares more than the records show",
        "story": "A driver paid by passengers through his wallet. He declares NPR 85,000 a month "
                 "and asks for a loan to buy his own vehicle.",
        "declared_income": 85000,
        "profile": {"occupation_en": "driver", "education_level": "intermediate", "household_size": 3,
                    "land_area_ropani": 0, "has_esewa_account": True, "has_khalti_account": False,
                    "remittance_receiving": False, "cooperative_member": False, "kyc_tier": "full"},
        "application": {"loan_purpose": "vehicle_purchase", "requested_amount_nrs": 450000,
                        "requested_tenure_months": 36, "collateral_type": "none",
                        "collateral_value_nrs": 0, "existing_loan_count": 1,
                        "credit_bureau_score": 655, "nrb_blacklist_flag": False, "aml_flag": False},
        "remittances": None,
        "wallet": {"platform": "esewa", "months": MONTHS,
                   "credits": [("p2p_transfer", "transport", 1000, 20)], "spend_per_month": 10},
        "utility": {"months": MONTHS, "late_days": [0, 5, 0, 0, 12, 0], "mobile": False},
    },
    {
        "key": "blacklisted",
        "label": "Steady farm income, on the blacklist",
        "story": "A dairy farmer who sells milk through his cooperative all year. The screening "
                 "result supplied with his application puts him on the credit blacklist.",
        "declared_income": 16000,
        "profile": {"occupation_en": "farmer", "education_level": "primary", "household_size": 6,
                    "land_area_ropani": 8, "has_esewa_account": True, "has_khalti_account": False,
                    "remittance_receiving": False, "cooperative_member": True, "kyc_tier": "mid"},
        "application": {"loan_purpose": "agricultural_input", "requested_amount_nrs": 80000,
                        "requested_tenure_months": 12, "collateral_type": "land",
                        "collateral_value_nrs": 400000, "existing_loan_count": 0,
                        "credit_bureau_score": 580, "nrb_blacklist_flag": True, "aml_flag": False},
        "remittances": None,
        "wallet": {"platform": "esewa", "months": MONTHS, "credits": [], "spend_per_month": 3},
        "utility": {"months": MONTHS, "late_days": [0, 0, -1, 0, 0, 0], "mobile": False},
        "coop": {"type": "dairy", "joined_bs": 2074, "years": {2079: 2100, 2080: 2150}, "rate": 90},
    },
]


def _ids(prefix):
    n = 0
    while True:
        n += 1
        yield f"{prefix}-{n:04d}"


def build_dataset(folder: Path) -> None:
    rng = random.Random(20261110)
    tx_id, rem_id, pay_id, sale_id = _ids("TX"), _ids("RM"), _ids("UP"), _ids("CS")
    profiles, apps, members, sales, txns, rems, utils = [], [], [], [], [], [], []
    for a in APPLICANTS:
        applicant_id, application_id = f"DEMO-{a['key'].upper()}", f"DEMO-{a['key'].upper()}-01"
        a["applicant_id"], a["application_id"] = applicant_id, application_id
        profiles.append({"applicant_id": applicant_id, **a["profile"],
                         "cooperative_id": "COOP-DEMO" if a.get("coop") else None})
        apps.append({"application_id": application_id, "applicant_id": applicant_id,
                     "application_date_ad": "2024-06-30", "application_date_bs": "2081-03-16",
                     "has_esewa_account": a["profile"]["has_esewa_account"],
                     "has_khalti_account": a["profile"]["has_khalti_account"],
                     "remittance_receiving": a["profile"]["remittance_receiving"],
                     "cooperative_member": a["profile"]["cooperative_member"],
                     "cooperative_id": "COOP-DEMO" if a.get("coop") else None,
                     "data_split": "public_test", **a["application"]})

        # wallet: credits that count as income, plus everyday spending
        w = a["wallet"]
        for month in w["months"]:
            y, m = map(int, month.split("-"))
            for kind, category, amount, count in w["credits"]:
                for _ in range(count):
                    day = rng.randint(1, 28)
                    amt = round(amount * rng.uniform(0.85, 1.15), -1)
                    txns.append(_txn(next(tx_id), applicant_id, w["platform"], date(y, m, day), kind,
                                     amt, "credit", category))
            for _ in range(w["spend_per_month"]):
                day = rng.randint(1, 28)
                kind, category = rng.choice([("merchant_payment", "grocery"), ("qr_payment", "restaurant"),
                                             ("merchant_payment", "medical"), ("qr_payment", "transport")])
                txns.append(_txn(next(tx_id), applicant_id, w["platform"], date(y, m, day), kind,
                                 round(rng.uniform(200, 1800), -1), "debit", category))

        # remittances through a transfer company, one a month
        r = a.get("remittances")
        if r:
            for month in r["months"]:
                y, m = map(int, month.split("-"))
                sent = date(y, m, rng.randint(3, 8))
                fx = r["qar"] * rng.choice([1.0, 1.0, 1.05, 0.95])
                rems.append({"remittance_id": next(rem_id), "applicant_id": applicant_id,
                             "sender_country_code": "QA", "sender_country_name": "Qatar",
                             "sender_city": "Doha", "transfer_service": "IME Money",
                             "transfer_date_ad": sent.isoformat(),
                             "received_date_ad": (sent + timedelta(days=1)).isoformat(),
                             "amount_foreign_currency": fx, "foreign_currency_code": "QAR",
                             "amount_nrs": round(fx * r["rate"], 2), "exchange_rate": r["rate"],
                             "transaction_fee_nrs": 300.0, "disbursement_mode": "bank_deposit",
                             "relationship_to_receiver": "spouse", "purpose_declared": "family_support",
                             "name_match_score": 1.0})

        # utility bills: electricity each month (unless mobile only), mobile when listed
        u = a["utility"]
        kinds = (["mobile"] if u.get("mobile_only") else ["electricity"] + (["mobile"] if u.get("mobile") else []))
        for kind in kinds:
            for month, late in zip(u["months"], u["late_days"]):
                y, m = map(int, month.split("-"))
                due = date(y, m, 20)
                units = rng.randint(90, 160) if kind == "electricity" else 0
                bill = round(units * 7.30, 2) if kind == "electricity" else float(rng.choice([499, 599]))
                utils.append({"payment_id": next(pay_id), "applicant_id": applicant_id,
                              "utility_type": kind, "provider": "NEA" if kind == "electricity" else "Ncell",
                              "service_number": f"{applicant_id}-{kind[:1].upper()}",
                              "billing_period_bs": BS_MONTH[month], "billing_period_ad": month,
                              "bill_amount_nrs": bill, "units_consumed": float(units),
                              "due_date_ad": due.isoformat(),
                              "payment_date_ad": (due + timedelta(days=late)).isoformat(),
                              "payment_method": a["wallet"]["platform"], "days_late": float(late),
                              "outstanding_arrears_nrs": 0.0})

        c = a.get("coop")
        if c:
            members.append({"member_id": f"M-{applicant_id}", "applicant_id": applicant_id,
                            "cooperative_id": "COOP-DEMO", "cooperative_name_en": "Invented Dairy Cooperative",
                            "cooperative_type": c["type"], "membership_year_bs": c["joined_bs"],
                            "membership_status": "active"})
            for year, litres in c["years"].items():
                sales.append({"sale_id": next(sale_id), "applicant_id": applicant_id,
                              "cooperative_id": "COOP-DEMO", "cooperative_type": c["type"],
                              "sale_year_bs": year, "season": "Annual", "commodity_en": "Milk", "unit": "L",
                              "quantity": litres, "rate_nrs_per_unit": c["rate"],
                              "total_amount_nrs": litres * c["rate"]})

    folder.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(profiles).to_csv(folder / "applicant_profiles.csv", index=False)
    pd.DataFrame(apps).to_csv(folder / "loan_applications.csv", index=False)
    pd.DataFrame(members, columns=["member_id", "applicant_id", "cooperative_id", "cooperative_name_en",
                                   "cooperative_type", "membership_year_bs", "membership_status"]) \
        .to_csv(folder / "cooperative_members.csv", index=False)
    pd.DataFrame(sales, columns=["sale_id", "applicant_id", "cooperative_id", "cooperative_type",
                                 "sale_year_bs", "season", "commodity_en", "unit", "quantity",
                                 "rate_nrs_per_unit", "total_amount_nrs"]) \
        .to_csv(folder / "cooperative_sales.csv", index=False)
    pd.DataFrame(columns=["applicant_id"]).to_csv(folder / "income_signal_features.csv", index=False)
    pd.DataFrame(txns).to_parquet(folder / "mobile_money_transactions.parquet", index=False)
    pd.DataFrame(rems, columns=["remittance_id", "applicant_id", "sender_country_code", "sender_country_name",
                                "sender_city", "transfer_service", "transfer_date_ad", "received_date_ad",
                                "amount_foreign_currency", "foreign_currency_code", "amount_nrs",
                                "exchange_rate", "transaction_fee_nrs", "disbursement_mode",
                                "relationship_to_receiver", "purpose_declared", "name_match_score"]) \
        .to_parquet(folder / "remittance_records.parquet", index=False)
    pd.DataFrame(utils).to_parquet(folder / "utility_payments.parquet", index=False)
    a_counts = {a["key"]: {"wallet": sum(t["applicant_id"] == a["applicant_id"] for t in txns),
                           "remittance": sum(r["applicant_id"] == a["applicant_id"] for r in rems),
                           "utility": sum(u["applicant_id"] == a["applicant_id"] for u in utils),
                           "coop_sales": sum(s["applicant_id"] == a["applicant_id"] for s in sales)}
                for a in APPLICANTS}
    for a in APPLICANTS:
        a["record_counts"] = a_counts[a["key"]]
        months = {t["transaction_date"][:7] for t in txns if t["applicant_id"] == a["applicant_id"]}
        months |= {r["received_date_ad"][:7] for r in rems if r["applicant_id"] == a["applicant_id"]}
        months |= {u["billing_period_ad"] for u in utils if u["applicant_id"] == a["applicant_id"]}
        a["record_counts"]["months"] = [min(months), max(months)] if months else None


def _txn(tid, applicant_id, platform, day, kind, amount, direction, category):
    n = int(tid.split("-")[1])  # deterministic time of day
    return {"transaction_id": tid, "applicant_id": applicant_id, "platform": platform,
            "transaction_date": f"{day.isoformat()} {10 + n % 9:02d}:{(n * 7) % 60:02d}:00",
            "transaction_type": kind, "amount_nrs": f"{amount:.2f}", "direction": direction,
            "counterparty_category": category, "is_festival_period": False, "amt": float(amount)}


def run(folder: Path) -> list:
    os.environ["DATA_BACKEND"] = "files"
    os.environ["TRACK_A_DIR"] = str(folder)
    sys.path.insert(0, str(ROOT))
    import logging
    logging.basicConfig(level=logging.WARNING)
    from app.agents.pipeline import get_workflow
    from app.services.credit_features import LABELS
    from app.services.policy_engine import load_policy

    rules = {r["id"]: r for r in load_policy()["rules"]}
    wf = get_workflow()
    examples = []
    for a in APPLICANTS:
        log = folder / f"audit_{a['key']}.jsonl"
        os.environ["AUDIT_LOG_PATH"] = str(log)
        app = a["application"]
        state = {"applicant_id": a["applicant_id"], "application_id": a["application_id"],
                 "loan_request": {"amount": app["requested_amount_nrs"],
                                  "tenure_months": app["requested_tenure_months"],
                                  "collateral_value_nrs": app["collateral_value_nrs"],
                                  "loan_purpose": app["loan_purpose"], "existing_liabilities_monthly": 0,
                                  "declared_monthly_income": a["declared_income"]}}
        res = wf.invoke(state)
        fo = res["final_output"]
        sources = (res.get("income_metrics") or {}).get("sources", {})
        traces = (res.get("compliance_result") or {}).get("rule_traces", [])
        examples.append({
            "key": a["key"], "label": a["label"], "story": a["story"],
            "application": {"declared_monthly_income": a["declared_income"], **{
                k: app[k] for k in ("loan_purpose", "requested_amount_nrs", "requested_tenure_months",
                                    "collateral_type", "collateral_value_nrs", "existing_loan_count")},
                "has_bureau_score": app["credit_bureau_score"] is not None,
                "kyc_tier": a["profile"]["kyc_tier"], "occupation": a["profile"]["occupation_en"]},
            "records": a["record_counts"],
            "income": {
                "observed_monthly": res.get("income_agent_monthly_est"),
                "confidence": res.get("income_confidence"),
                "imr": res.get("imr"), "imr_status": res.get("imr_status"),
                "remittance_share": res.get("remittance_share"),
                "flags": res.get("income_flags") or [],
                "sources": [{"source": k, "monthly": v.get("monthly_usable_income"),
                             "months": v.get("months_observed") or v.get("months_active"),
                             "confidence": v.get("confidence_score")} for k, v in sources.items()],
                "on_time_rate": (res.get("income_signal_features") or {}).get("overall_on_time_rate"),
            },
            "compliance": {
                "status": res.get("compliance_status"),
                "traces": [{"rule_id": t["rule_id"], "description": rules[t["rule_id"]]["description"].strip(),
                            "applicable": t.get("applicable"), "triggered": t.get("triggered"),
                            "action": t.get("action"), "observed": t.get("observed"),
                            "threshold": t.get("threshold"), "note": t.get("note"),
                            "provenance": t.get("provenance")} for t in traces],
            },
            "score": None if fo.get("pd") is None else {
                "pd": fo["pd"], "credit_score": fo["credit_score"], "risk_grade": fo["risk_grade"],
                "drivers": [{"feature": d["feature"], "label": d["label"], "value": d["value"],
                             "shap": d["shap_log_odds"], "direction": d["direction"]}
                            for d in fo.get("drivers", [])]},
            "decision": {k: fo.get(k) for k in ("decision", "approved_amount_nrs", "reasons", "counter_offer",
                                                "illustrative_rate_pct", "policy_version", "model_version")},
            "audit_lines": [line for line in log.read_text(encoding="utf-8").splitlines() if line.strip()],
        })
        print(f"{a['key']:12s} {fo['decision']:12s} PD={fo.get('pd')} grade={fo.get('risk_grade')} "
              f"rules={fo.get('triggered_rules')} conf={res.get('income_confidence')} imr={res.get('imr')} "
              f"observed={res.get('income_agent_monthly_est')}")
    return examples


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp) / "invented"
        build_dataset(folder)
        examples = run(folder)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {"note": "Invented applicants, run through the pipeline by scripts/make_showcase_examples.py. "
                       "No Track A records are used.",
               "labels": {}, "examples": examples}
    from app.services.credit_features import LABELS
    from app.services.policy_engine import load_policy
    spec = json.loads((ROOT / "app" / "ScoringModel" / "pd_model" / "feature_spec.json").read_text())
    payload["labels"] = LABELS
    payload["model"] = {"grades": spec["grades"], "scaling": spec["scaling"],
                        "monotone": spec["monotone_constraints"]}
    payload["decision_rules"] = load_policy()["decision"]
    OUT.write_text(json.dumps(payload, indent=1, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
