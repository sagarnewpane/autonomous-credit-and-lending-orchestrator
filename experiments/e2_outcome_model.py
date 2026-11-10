"""
E2. Probability-of-default model evaluated on synthetic repayment outcomes.

Target: outcome == "defaulted" in loan_outcomes.csv (only approved or conditionally
approved loans have outcomes, so every result here is conditional on approval).
Features: app.services.credit_features.build_feature_row, i.e. application fields plus
the features our own Income Agent computes (experiments/build_features.py). Generator
outputs and protected attributes are excluded.

Compares, on the held-out val + public_test loans:
  * the generator's credit score and default probability (reference only)
  * a single affordability ratio (instalment / observed income)
  * logistic regression
  * gradient boosting with and without monotone constraints (trained on 80% of the
    training loans, early-stopped on the other 20%), with ablations by feature group and a
    variant with protected attributes
  * the released model: the monotone specification refit on all training loans with the
    early-stopped number of rounds (this is the model the pipeline and E4/E5 use)
It also checks how the result depends on when each default happened relative to the
January-June 2024 window that the wallet, remittance and utility records cover.

Writes app/ScoringModel/pd_model/{model.json, feature_spec.json},
experiments/results/e2_outcome_model.json and figures.

    python experiments/e2_outcome_model.py --data "/path/Track A/structured"
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

import common  # noqa: F401
from common import CACHE, FIGURES, ROOT, SEED, data_dir, ensure_dirs, load_applications, load_outcomes, \
    load_profiles, records, save_json
from app.services.credit_features import CATEGORICAL_FEATURES, FEATURES, MONOTONE, NUMERIC_FEATURES, \
    build_feature_row

MODEL_DIR = ROOT / "app" / "ScoringModel" / "pd_model"
SCALING = {"pdo": 20.0, "base_score": 600.0, "base_odds": 50.0, "min_score": 300, "max_score": 850}
GRADES = [{"grade": "A", "pd_below": 0.015}, {"grade": "B", "pd_below": 0.025}, {"grade": "C", "pd_below": 0.04},
          {"grade": "D", "pd_below": 0.06}, {"grade": "E", "pd_below": 1.01}]
PROTECTED = ["gender", "marital_status", "province_en", "rural_urban"]
GROUPS = {
    "wallet": ["esewa_net_monthly", "esewa_tx_count_6months", "has_esewa_account", "has_khalti_account"],
    "remittance": ["remittance_monthly_avg", "remittance_regularity_score", "remittance_receiving"],
    "cooperative": ["cooperative_monthly_sales", "coop_tenure_years", "cooperative_member"],
    "utility": ["utility_avg_bill_nrs", "overall_on_time_rate", "util_arrears_total_nrs"],
    "bureau": ["credit_bureau_score", "has_bureau_score"],
}
# Features the Income Agent computes from transaction records ...
INCOME_STAGE = ["monthly_income_est", "income_confidence", "income_signal_count", "loan_to_annual_income",
                "instalment_to_income", "esewa_net_monthly", "esewa_tx_count_6months", "remittance_monthly_avg",
                "remittance_regularity_score", "cooperative_monthly_sales", "coop_tenure_years",
                "utility_avg_bill_nrs", "overall_on_time_rate", "util_arrears_total_nrs"]
# ... and yes/no fields from the applicant profile that describe the same channels.
PROFILE_FLAGS = ["has_esewa_account", "has_khalti_account", "remittance_receiving", "cooperative_member"]
RECORD_WINDOW = ("2024-01-01", "2024-06-30 23:59:59")  # coverage of the wallet, remittance, utility records
XGB_PARAMS = {"objective": "binary:logistic", "eval_metric": "logloss", "eta": 0.03, "max_depth": 4,
              "min_child_weight": 10, "subsample": 0.8, "colsample_bytree": 0.8, "lambda": 2.0,
              "tree_method": "hist", "seed": SEED, "nthread": 2}


def build_table(d: Path) -> pd.DataFrame:
    la = load_applications(d)
    prof = load_profiles(d).drop_duplicates("applicant_id").set_index("applicant_id")
    feats = pd.read_parquet(CACHE / "income_features.parquet").set_index("applicant_id")
    lo = load_outcomes(d)[["application_id", "outcome", "disbursement_date_ad", "months_to_event"]]
    df = la.merge(lo, on="application_id", how="inner")
    rows = []
    prof_rec = dict(zip(prof.index, records(prof.reset_index())))
    feat_rec = dict(zip(feats.index, records(feats.reset_index())))
    for app in records(df):
        p = prof_rec.get(app["applicant_id"], {})
        f = feat_rec.get(app["applicant_id"], {})
        r = build_feature_row(p, app, f)
        r.update({"application_id": app["application_id"], "data_split": app["data_split"], "outcome": app["outcome"],
                  "application_date_ad": app.get("application_date_ad"),
                  "disbursement_date_ad": app.get("disbursement_date_ad"), "months_to_event": app.get("months_to_event"),
                  "organiser_credit_score": app.get("credit_score"),
                  **{k: p.get(k) for k in PROTECTED if k in p},
                  "age": None})
        dob = pd.to_datetime(p.get("dob_ad"), errors="coerce")
        appdate = pd.to_datetime(app.get("application_date_ad"), errors="coerce")
        if pd.notna(dob) and pd.notna(appdate):
            r["age"] = (appdate - dob).days / 365.25
        rows.append(r)
    t = pd.DataFrame(rows)
    org = load_outcomes(d)[["application_id", "default_probability_model"]]
    t = t.merge(org, on="application_id", how="left")
    t["y"] = (t["outcome"] == "defaulted").astype(int)
    t["y_bad"] = t["outcome"].isin(["defaulted", "delinquent"]).astype(int)
    return t


def encode(t: pd.DataFrame, cols, cats=None):
    cats = cats or {}
    X = pd.DataFrame(index=t.index)
    for c in cols:
        if c in CATEGORICAL_FEATURES or t[c].dtype == object:
            if c not in cats:
                vals = sorted(v for v in t[c].dropna().unique())
                cats[c] = {v: i for i, v in enumerate(vals)}
            X[c] = t[c].map(cats[c]).astype(float)
        else:
            X[c] = pd.to_numeric(t[c], errors="coerce").astype(float)
    return X, cats


def ks_stat(y, p):
    order = np.argsort(p)
    y = np.asarray(y)[order]
    cum_bad = np.cumsum(y) / max(y.sum(), 1)
    cum_good = np.cumsum(1 - y) / max((1 - y).sum(), 1)
    return float(np.max(np.abs(cum_bad - cum_good)))


def ece(y, p, bins=10):
    y, p = np.asarray(y), np.asarray(p)
    qs = np.quantile(p, np.linspace(0, 1, bins + 1))
    idx = np.clip(np.searchsorted(qs, p, side="right") - 1, 0, bins - 1)
    total = 0.0
    for b in range(bins):
        m = idx == b
        if m.any():
            total += m.mean() * abs(y[m].mean() - p[m].mean())
    return float(total)


def bootstrap_auc(y, s, reps=500, seed=SEED):
    rng = np.random.default_rng(seed)
    y, s = np.asarray(y), np.asarray(s)
    vals = []
    for _ in range(reps):
        i = rng.integers(0, len(y), len(y))
        if y[i].min() != y[i].max():
            vals.append(roc_auc_score(y[i], s[i]))
    return [round(float(np.percentile(vals, 2.5)), 3), round(float(np.percentile(vals, 97.5)), 3)]


def paired_auc_diff(y, a, b, reps=1000, seed=SEED):
    """AUC(a) - AUC(b) on the same rows, with a paired bootstrap 95% interval."""
    rng = np.random.default_rng(seed)
    y, a, b = np.asarray(y), np.asarray(a), np.asarray(b)
    diffs = []
    for _ in range(reps):
        i = rng.integers(0, len(y), len(y))
        if y[i].min() != y[i].max():
            diffs.append(roc_auc_score(y[i], a[i]) - roc_auc_score(y[i], b[i]))
    return {"diff": round(float(roc_auc_score(y, a) - roc_auc_score(y, b)), 4),
            "ci95": [round(float(np.percentile(diffs, 2.5)), 4), round(float(np.percentile(diffs, 97.5)), 4)]}


def metrics(y, p, prob=True):
    out = {"auc": round(roc_auc_score(y, p), 4), "auc_95ci": bootstrap_auc(y, p), "ks": round(ks_stat(y, p), 4)}
    if prob:
        pc = np.clip(p, 1e-6, 1 - 1e-6)
        out.update({"brier": round(brier_score_loss(y, pc), 5), "log_loss": round(log_loss(y, pc), 5),
                    "ece_10bins": round(ece(y, pc), 5), "mean_pd": round(float(np.mean(pc)), 5),
                    "observed_rate": round(float(np.mean(y)), 5)})
    return out


def train_xgb(Xtr, ytr, Xva, yva, monotone=None, rounds=3000):
    params = dict(XGB_PARAMS)
    if monotone:
        params["monotone_constraints"] = "(" + ",".join(str(monotone.get(c, 0)) for c in Xtr.columns) + ")"
    dtr = xgb.DMatrix(Xtr, label=ytr, feature_names=list(Xtr.columns), missing=np.nan)
    dva = xgb.DMatrix(Xva, label=yva, feature_names=list(Xva.columns), missing=np.nan)
    booster = xgb.train(params, dtr, num_boost_round=rounds, evals=[(dva, "val")],
                        early_stopping_rounds=150, verbose_eval=False)
    return booster


def predict(booster, X):
    return booster.predict(xgb.DMatrix(X, feature_names=list(X.columns), missing=np.nan),
                           iteration_range=(0, booster.best_iteration + 1))


def fit_eval_xgb(t, tr, va, te, cols, monotone=None, label="y"):
    Xall, cats = encode(t.loc[tr | va], cols)
    Xte, _ = encode(t.loc[te], cols, cats)
    b = train_xgb(Xall.loc[t.index[tr]], t.loc[tr, label], Xall.loc[t.index[va]], t.loc[va, label], monotone)
    p = predict(b, Xte)
    return b, cats, p


def logistic(t, tr, te, cols, label="y"):
    num = [c for c in cols if c in NUMERIC_FEATURES or c == "age"]
    cat = [c for c in cols if c not in num]
    pre = ColumnTransformer([
        ("num", Pipeline([("imp", SimpleImputer(strategy="median", add_indicator=True)), ("sc", StandardScaler())]), num),
        ("cat", Pipeline([("imp", SimpleImputer(strategy="constant", fill_value="missing")),
                          ("oh", OneHotEncoder(handle_unknown="ignore"))]), cat),
    ])
    model = Pipeline([("pre", pre), ("lr", LogisticRegression(C=0.5, max_iter=2000))])
    Xtr = t.loc[tr, cols].copy()
    Xte = t.loc[te, cols].copy()
    for c in cat:
        Xtr[c] = Xtr[c].astype(object).where(Xtr[c].notna(), "missing").astype(str)
        Xte[c] = Xte[c].astype(object).where(Xte[c].notna(), "missing").astype(str)
    model.fit(Xtr, t.loc[tr, label])
    return model.predict_proba(Xte)[:, 1]


def monotone_str(cols):
    return "(" + ",".join(str(MONOTONE.get(c, 0)) for c in cols) + ")"


def main():
    d = data_dir()
    ensure_dirs()
    t = build_table(d)
    in_train = t["data_split"] == "train"
    te = t["data_split"].isin(["val", "public_test"])
    tr_idx, va_idx = train_test_split(t.index[in_train], test_size=0.2, random_state=SEED, stratify=t.loc[in_train, "y"])
    tr = t.index.isin(tr_idx)
    va = t.index.isin(va_idx)
    yte = t.loc[te, "y"].to_numpy()
    res = {"n_train": int(tr.sum()), "n_early_stop": int(va.sum()), "n_test": int(te.sum()),
           "n_features": len(FEATURES), "n_monotone": len(MONOTONE),
           "n_income_stage_features": len(INCOME_STAGE), "n_profile_flags": len(PROFILE_FLAGS),
           "default_rate_train": round(float(t.loc[in_train, "y"].mean()), 4),
           "default_rate_test": round(float(yte.mean()), 4), "n_test_defaults": int(yte.sum()),
           "label": "outcome == 'defaulted' (synthetic), approved or conditional loans only",
           "instalment_to_income_baseline_missing_value": 10.0, "models": {}}

    org_cs = pd.to_numeric(t.loc[te, "organiser_credit_score"], errors="coerce")
    m = org_cs.notna()
    res["models"]["generator credit score (reference)"] = metrics(yte[m.to_numpy()], -org_cs[m].to_numpy(), prob=False)
    org_pd = pd.to_numeric(t.loc[te, "default_probability_model"], errors="coerce")
    m2 = org_pd.notna()
    res["models"]["generator default probability (reference)"] = metrics(yte[m2.to_numpy()], org_pd[m2].to_numpy(), prob=False)
    # applicants without observed income have no ratio; they rank as the riskiest
    iti = pd.to_numeric(t.loc[te, "instalment_to_income"], errors="coerce").fillna(10).to_numpy()
    res["models"]["instalment-to-income only"] = metrics(yte, iti, prob=False)

    p_lr = logistic(t, tr | va, te, FEATURES)
    res["models"]["logistic regression"] = metrics(yte, p_lr)
    b_unc, _, p_unc = fit_eval_xgb(t, tr, va, te, FEATURES)
    res["models"]["gradient boosting, unconstrained"] = metrics(yte, p_unc)
    b_mono, cats, p_mono = fit_eval_xgb(t, tr, va, te, FEATURES, MONOTONE)
    res["models"]["gradient boosting, monotone"] = metrics(yte, p_mono)
    res["models"]["gradient boosting, monotone"]["best_iteration"] = int(b_mono.best_iteration)

    # ---- the released model: same specification, refit on all training loans -------------
    rounds = int(b_mono.best_iteration) + 1
    final = xgb.train({**XGB_PARAMS, "monotone_constraints": monotone_str(FEATURES)},
                      xgb.DMatrix(encode(t.loc[tr | va], FEATURES, cats)[0], label=t.loc[tr | va, "y"],
                                  feature_names=FEATURES, missing=np.nan),
                      num_boost_round=rounds)
    Xte_enc = encode(t.loc[te], FEATURES, cats)[0]
    p_rel = final.predict(xgb.DMatrix(Xte_enc, feature_names=FEATURES, missing=np.nan))
    res["models"]["released model"] = metrics(yte, p_rel)

    abl, diffs = {}, {}
    preds = {"monotone": p_mono, "released": p_rel, "logistic": p_lr, "unconstrained": p_unc}
    for g, cols in GROUPS.items():
        keep = [c for c in FEATURES if c not in cols]
        _, _, p = fit_eval_xgb(t, tr, va, te, keep, MONOTONE)
        abl[f"without {g}"] = metrics(yte, p)
        diffs[f"monotone minus without {g}"] = paired_auc_diff(yte, p_mono, p)
    for name, cols in [("Income-stage features", INCOME_STAGE), ("profile flags", PROFILE_FLAGS),
                       ("Income-stage features and profile flags", INCOME_STAGE + PROFILE_FLAGS)]:
        keep = [c for c in FEATURES if c not in cols]
        _, _, p = fit_eval_xgb(t, tr, va, te, keep, MONOTONE)
        abl[f"without {name}"] = metrics(yte, p)
        diffs[f"monotone minus without {name}"] = paired_auc_diff(yte, p_mono, p)
        preds[f"without {name}"] = p
    p_noinc = preds["without Income-stage features and profile flags"]
    _, _, p = fit_eval_xgb(t, tr, va, te, FEATURES + PROTECTED + ["age"], MONOTONE)
    abl["with protected attributes added"] = metrics(yte, p)
    diffs["with protected minus monotone"] = paired_auc_diff(yte, p, p_mono)
    diffs["monotone minus logistic"] = paired_auc_diff(yte, p_mono, p_lr)
    diffs["unconstrained minus monotone"] = paired_auc_diff(yte, p_unc, p_mono)
    diffs["released minus monotone"] = paired_auc_diff(yte, p_rel, p_mono)
    # logistic regression is fitted on all training loans, like the released model
    diffs["released minus logistic"] = paired_auc_diff(yte, p_rel, p_lr)
    m_all = org_cs.notna().to_numpy()
    diffs["generator score minus released"] = paired_auc_diff(yte[m_all], -org_cs[org_cs.notna()].to_numpy(), p_rel[m_all])
    res["ablations"] = abl
    res["paired_auc_differences"] = diffs
    pd.DataFrame({"application_id": t.loc[te, "application_id"].to_numpy(), "y": yte, **preds}) \
        .to_parquet(CACHE / "e2_heldout_predictions.parquet", index=False)

    # ---- timing: the transaction records cover Jan-Jun 2024, after most applications -------
    tt = t.loc[te]
    disb = pd.to_datetime(tt["disbursement_date_ad"], errors="coerce")
    event = disb + pd.to_timedelta(pd.to_numeric(tt["months_to_event"], errors="coerce") * 30.4375, unit="D")
    start, end = pd.Timestamp(RECORD_WINDOW[0]), pd.Timestamp(RECORD_WINDOW[1])
    appd = pd.to_datetime(t["application_date_ad"], errors="coerce")
    timing = {"record_window": [RECORD_WINDOW[0], RECORD_WINDOW[1][:10]],
              "loans_applied_before_window_share": round(float((appd < start).mean()), 6),
              "application_date_range": [str(appd.min().date()), str(appd.max().date())],
              "heldout_defaults_before_window_end_share": round(float((event[yte == 1] <= end).mean()), 6),
              "auc_by_default_timing": {}}
    groups = {"before the window": (event < start).to_numpy(),
              "during the window": ((event >= start) & (event <= end)).to_numpy(),
              "after the window": (event > end).to_numpy()}
    for g, mask in groups.items():
        keep = (yte == 0) | ((yte == 1) & mask)
        timing["auc_by_default_timing"][g] = {
            "defaults": int(((yte == 1) & mask).sum()),
            "monotone": round(float(roc_auc_score(yte[keep], p_mono[keep])), 4),
            "without Income-stage features and profile flags": round(float(roc_auc_score(yte[keep], p_noinc[keep])), 4)}
    res["timing"] = timing

    # secondary label: defaulted or delinquent
    _, _, p_bad = fit_eval_xgb(t, tr, va, te, FEATURES, MONOTONE, label="y_bad")
    res["secondary_label_default_or_delinquent"] = metrics(t.loc[te, "y_bad"].to_numpy(), p_bad)

    # strategy curve and calibration of the released model
    curve = []
    for thr in [0.01, 0.015, 0.02, 0.025, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10]:
        approve = p_rel < thr
        curve.append({"pd_threshold": thr, "share_below": round(float(approve.mean()), 4),
                      "default_rate_below": round(float(yte[approve].mean()), 4) if approve.any() else None,
                      "default_rate_above": round(float(yte[~approve].mean()), 4) if (~approve).any() else None})
    res["strategy_curve"] = curve
    bins = pd.qcut(p_rel, 10, labels=False, duplicates="drop")
    res["calibration_deciles"] = [{"mean_pd": round(float(p_rel[bins == b].mean()), 5),
                                   "observed_rate": round(float(yte[bins == b].mean()), 5), "n": int((bins == b).sum())}
                                  for b in sorted(set(bins))]
    gain = final.get_score(importance_type="gain")
    total = sum(gain.values()) or 1.0
    res["released_feature_gain_share"] = {k: round(v / total, 4) for k, v in sorted(gain.items(), key=lambda kv: -kv[1])}

    # ---- save the released model ------------------------------------------------------
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    final.save_model(str(MODEL_DIR / "model.json"))
    spec = {
        "features": FEATURES,
        "categories": {c: {str(k): int(v) for k, v in cats[c].items()} for c in CATEGORICAL_FEATURES},
        "monotone_constraints": MONOTONE,
        "label_definition": "P(outcome == 'defaulted') on the hackathon's Track A synthetic outcomes; trained on approved loans only",
        "excluded": {"protected_or_proxy": ["gender", "marital_status", "age", "names", "citizenship", "phone",
                                            "province", "district", "municipality", "ward", "rural_urban"],
                     "generator_outputs": ["credit_score", "composite_creditworthiness_score", "income_agent_monthly_est",
                                           "income_confidence (organiser)", "final_decision", "approved_amount_nrs",
                                           "interest_rate_pct", "processing_time_seconds", "compliance_status", "doc_completeness_score"]},
        "scaling": SCALING,
        "grades": GRADES,
        "training": {"rows": int((tr | va).sum()), "defaults": int(t.loc[tr | va, "y"].sum()),
                     "boost_rounds": rounds, "params": XGB_PARAMS, "seed": SEED},
        "heldout_metrics": res["models"]["released model"],
    }
    (MODEL_DIR / "feature_spec.json").write_text(json.dumps(spec, indent=2))
    save_json(res, "e2_outcome_model.json")

    # ---- figures --------------------------------------------------------------
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from sklearn.metrics import roc_curve
    plt.rcParams.update({"font.size": 8, "font.family": "serif",
                         "font.serif": ["Liberation Serif", "Times New Roman", "DejaVu Serif"],
                         "pdf.fonttype": 42, "ps.fonttype": 42})  # TrueType: no Type 3 fonts in the PDF
    fig, ax = plt.subplots(1, 2, figsize=(7.0, 2.6))
    for name, p, ls in [("Released model", p_rel, "-"), ("Logistic regression", p_lr, "--")]:
        fpr, tpr, _ = roc_curve(yte, p)
        ax[0].plot(fpr, tpr, ls, lw=1.2, label=f"{name} ({roc_auc_score(yte, p):.3f})")
    fpr, tpr, _ = roc_curve(yte[m.to_numpy()], -org_cs[m].to_numpy())
    ax[0].plot(fpr, tpr, ":", lw=1.2, label=f"Generator's credit score, reference ({roc_auc_score(yte[m.to_numpy()], -org_cs[m].to_numpy()):.3f})")
    ax[0].plot([0, 1], [0, 1], color="0.7", lw=0.6)
    ax[0].set_xlabel("False positive rate"); ax[0].set_ylabel("True positive rate"); ax[0].legend(frameon=False, fontsize=6.5)
    ax[0].set_title("(a) ROC, held-out default")
    cal = res["calibration_deciles"]
    ax[1].plot([c["mean_pd"] for c in cal], [c["observed_rate"] for c in cal], "o-", ms=3, lw=1)
    lim = max(max(c["mean_pd"] for c in cal), max(c["observed_rate"] for c in cal)) * 1.1
    ax[1].plot([0, lim], [0, lim], color="0.7", lw=0.6)
    ax[1].set_xlabel("Predicted PD (decile mean)"); ax[1].set_ylabel("Observed default rate")
    ax[1].set_title("(b) Calibration, released model")
    fig.tight_layout()
    fig.savefig(FIGURES / "e2_roc_calibration.pdf"); fig.savefig(FIGURES / "e2_roc_calibration.png", dpi=200)
    print(json.dumps({k: v["auc"] for k, v in res["models"].items()}, indent=1))
    print(json.dumps({k: v["auc"] for k, v in res["ablations"].items()}, indent=1))
    print(json.dumps(timing, indent=1))


if __name__ == "__main__":
    main()
