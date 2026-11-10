"""
E4. Decision routing, thin files and subgroup checks on the held-out applicants.

Runs the deployed decision logic (policy engine + PD model + Decision Agent rules, the same
functions the pipeline nodes call) on every val and public_test application, then reports:
  * the decision mix, and how many thin-file applicants (income confidence below 0.40)
    are referred rather than rejected as in the hackathon version;
  * default rates of the loans that have synthetic outcomes, by new decision;
  * by gender, province and rural/urban: decision rates, thin-file rates, AUC and
    calibration-in-the-large of the PD model.
Protected attributes are used here only for auditing; the model does not see them.

    python experiments/e4_routing_fairness.py --data "/path/Track A/structured"
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

import common  # noqa: F401
from common import CACHE, data_dir, ensure_dirs, load_applications, load_outcomes, load_profiles, records, save_json
from app.agents.decision_agent import decide
from app.agents.score_agent import CreditScorer, pd_to_score, risk_grade
from app.services.credit_features import build_feature_row
from app.services.policy_engine import evaluate, load_policy


def main():
    d = data_dir()
    ensure_dirs()
    la = load_applications(d)
    la = la[la["data_split"].isin(["val", "public_test"])].copy()
    prof = load_profiles(d).drop_duplicates("applicant_id").set_index("applicant_id")
    feats = pd.read_parquet(CACHE / "income_features.parquet").set_index("applicant_id")
    lo = load_outcomes(d)[["application_id", "outcome"]]
    policy = load_policy()
    # the same policy without the debt-service cap, to see which referrals depend on it alone
    policy_wo_dsti = {**policy, "rules": [r for r in policy["rules"] if r["id"] != "DSTI_CAP"]}
    scorer = CreditScorer()
    prof_rec = dict(zip(prof.index, records(prof.reset_index())))
    feat_rec = dict(zip(feats.index, records(feats.reset_index())))

    rows, vectors = [], []
    for app in records(la):
        p = prof_rec.get(app["applicant_id"], {})
        f = feat_rec.get(app["applicant_id"], {})
        fr = build_feature_row(p, app, f)
        vectors.append(scorer._vector(fr)[0])
        inputs = {
            "requested_amount_nrs": app.get("requested_amount_nrs"),
            "requested_tenure_months": app.get("requested_tenure_months") or 12,
            "collateral_value_nrs": app.get("collateral_value_nrs"),
            "loan_purpose": app.get("loan_purpose"),
            "existing_liabilities_monthly": 0,
            "existing_loan_count": app.get("existing_loan_count"),
            "kyc_tier": p.get("kyc_tier"),
            "nrb_blacklist_flag": app.get("nrb_blacklist_flag"),
            "aml_flag": app.get("aml_flag"),
            "monthly_income": f.get("derived_income_est"),
            "imr": None, "imr_status": "not_declared",
            "remittance_share": f.get("remittance_share"),
        }
        comp = evaluate(inputs, policy)
        comp_wo = evaluate(inputs, policy_wo_dsti)
        rows.append({"application_id": app["application_id"], "applicant_id": app["applicant_id"],
                     "gender": p.get("gender"), "province": p.get("province_en"), "rural_urban": p.get("rural_urban"),
                     "occupation": p.get("occupation_en"), "income_confidence": f.get("income_confidence"),
                     "monthly_income": f.get("derived_income_est"), "amount": app.get("requested_amount_nrs"),
                     "tenure": app.get("requested_tenure_months") or 12, "compliance_status": comp["status"],
                     "triggered": comp["triggered_rules"], "organiser_decision": str(app.get("final_decision") or "").lower(),
                     "status_wo_dsti": comp_wo["status"], "triggered_wo_dsti": comp_wo["triggered_rules"]})
    import xgboost as xgb
    X = np.vstack(vectors)
    dmat = xgb.DMatrix(X, feature_names=scorer.features, missing=np.nan)
    pdv = scorer.booster.predict(dmat)
    # Which feature is each applicant's largest driver (exact TreeSHAP, log-odds scale)?
    contrib = scorer.booster.predict(dmat, pred_contribs=True)[:, :-1]  # last column is the bias
    top = np.abs(contrib).argmax(axis=1)
    top_names = pd.Series([scorer.features[i] for i in top])
    rem = scorer.features.index("remittance_monthly_avg")
    no_rem_top_risk = (top == rem) & (np.nan_to_num(X[:, rem]) == 0) & (contrib[:, rem] > 0)
    top_driver = {"share_by_feature": top_names.value_counts(normalize=True).head(6).round(6).to_dict(),
                  "no_transfer_company_remittance_is_top_risk_driver": round(float(no_rem_top_risk.mean()), 6)}
    print("top driver:", top_driver)
    out_rows = []
    for r, p in zip(rows, pdv):
        state = {"loan_request": {"amount": r["amount"], "tenure_months": r["tenure"], "existing_liabilities_monthly": 0},
                 "income_agent_monthly_est": r["monthly_income"], "income_confidence": r["income_confidence"],
                 "compliance_status": r["compliance_status"], "compliance_flags": r["triggered"],
                 "compliance_message": None,
                 "scorecard": {"status": "ok", "pd": float(p), "risk_grade": risk_grade(float(p), scorer.spec),
                               "credit_score": pd_to_score(float(p), scorer.spec)}}
        dec = decide(state, policy)
        dec_wo = decide({**state, "compliance_status": r["status_wo_dsti"], "compliance_flags": r["triggered_wo_dsti"]},
                        policy_wo_dsti)
        out_rows.append({**{k: v for k, v in r.items() if k not in ("triggered", "triggered_wo_dsti", "status_wo_dsti")},
                         "pd": float(p), "decision": dec["final_decision"], "decision_without_dsti": dec_wo["final_decision"],
                         "triggered": ",".join(r["triggered"])})
    df = pd.DataFrame(out_rows).merge(lo, on="application_id", how="left")
    df.to_parquet(CACHE / "e4_decisions.parquet", index=False)
    thin = df["income_confidence"].fillna(0) < policy["decision"]["min_income_confidence"]
    res = {"n": int(len(df)),
           "decision_mix": df["decision"].value_counts(normalize=True).round(6).to_dict(),
           "compliance_mix": df["compliance_status"].value_counts(normalize=True).round(6).to_dict(),
           "rule_trigger_rates": {rid: round(float(df["triggered"].str.contains(rid).mean()), 6)
                                  for rid in [r["id"] for r in policy["rules"]]},
           "thin_file_share": round(float(thin.mean()), 6),
           "thin_file_decisions_new": df.loc[thin, "decision"].value_counts().to_dict(),
           "thin_file_rejected_by_hackathon_rule": int(thin.sum()),
           "organiser_label_vs_new_decision": pd.crosstab(df["organiser_decision"], df["decision"]).to_dict()}
    has = df["outcome"].notna()
    res["with_outcomes"] = {"n": int(has.sum()),
                            "default_rate_by_decision": df[has].assign(y=(df.loc[has, "outcome"] == "defaulted").astype(int))
                            .groupby("decision")["y"].agg(["mean", "count"]).round(6).to_dict(orient="index")}
    groups = {}
    for g in ["gender", "rural_urban", "province", "occupation"]:
        tab = {}
        for val, sub in df.groupby(g):
            s = {"n": int(len(sub)),
                 "approve_or_conditional": round(float(sub["decision"].isin(["approve", "conditional"]).mean()), 6),
                 "refer": round(float((sub["decision"] == "refer").mean()), 6),
                 "decline": round(float((sub["decision"] == "decline").mean()), 6),
                 "thin_file": round(float((sub["income_confidence"].fillna(0) < 0.40).mean()), 6)}
            so = sub[sub["outcome"].notna()]
            if len(so) and so["outcome"].eq("defaulted").nunique() == 2:
                y = so["outcome"].eq("defaulted").astype(int)
                s.update({"n_outcomes": int(len(so)), "auc": round(float(roc_auc_score(y, so["pd"])), 6),
                          "mean_pd": round(float(so["pd"].mean()), 6), "observed_default": round(float(y.mean()), 6)})
            tab[str(val)] = s
        groups[g] = tab
    res["groups"] = groups
    res["top_driver"] = top_driver
    ref = df["decision"] == "refer"
    res["dsti_and_referrals"] = {
        "referred_with_dsti_triggered": round(float(df.loc[ref, "triggered"].str.contains("DSTI_CAP").mean()), 6),
        "referred_only_because_of_dsti": round(float((df.loc[ref, "decision_without_dsti"] != "refer").mean()), 6),
        "decision_mix_without_dsti": df["decision_without_dsti"].value_counts(normalize=True).round(6).to_dict()}
    # How strict is the 50% debt-service cap when only digitally observed income counts?
    from app.services.policy_engine import monthly_instalment
    rate = float(policy["assumptions"]["annual_interest_rate_for_affordability"])
    inst = np.array([monthly_instalment(a or 0.0, rate, int(t or 12)) for a, t in zip(df["amount"], df["tenure"])])
    inc = df["monthly_income"].fillna(0).to_numpy()
    pos = inc > 0  # the rule does not apply without observed income
    res["dsti_applicable_share"] = round(float(pos.mean()), 6)
    res["dsti_trigger_rate_if_true_income_is_k_times_observed"] = {
        str(k): round(float(np.mean(inst[pos] > 0.5 * k * inc[pos])), 6) for k in (1, 1.5, 2, 3, 5)}
    res["median_observed_monthly_income"] = round(float(np.median(inc)), 1)
    res["median_observed_monthly_income_if_positive"] = round(float(np.median(inc[pos])), 1)
    res["share_without_observed_income"] = round(float(1 - pos.mean()), 6)
    res["median_requested_amount"] = round(float(np.nanmedian(df["amount"].astype(float))), 1)
    save_json(res, "e4_routing_fairness.json")
    print({k: res[k] for k in ["n", "decision_mix", "compliance_mix", "thin_file_share", "thin_file_decisions_new"]})
    print(res["with_outcomes"])
    print({g: {k: (v["approve_or_conditional"], v.get("auc")) for k, v in t.items()} for g, t in groups.items() if g != "occupation"})


if __name__ == "__main__":
    main()
