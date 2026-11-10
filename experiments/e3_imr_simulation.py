"""
E3. When does the declared-versus-observed income check (IMR) work?

IMR = declared / observed monthly income. Track A has no declared income and no true
income, so this is a scenario study with stated assumptions:

  true income      T
  observed income  O = v * T      v = share of income visible in wallet, remittance,
                                    cooperative and utility records (0 < v <= 1)
  honest report    D = e * T      e ~ LogNormal(0, sigma_e): rounding and uncertainty
  misreport        D = m * T      overstatement m ~ U(1.5, 5) or understatement m ~ U(0.1, 0.5)

so IMR = e / v for honest applicants and m / v for misreporters: the observed income
cancels, and the check's behaviour is set by how much income the records miss. The data
contribute the mix of income types, the share of applicants for whom observed income is
too low to compute IMR, and the remittance share used for the relaxed upper bound.

Income types (income_type below): "remittance" means remittances are at least half of the
applicant's observed income, whatever the occupation; otherwise "salaried" is a government
employee, teacher or nurse/health worker, "agriculture" a farmer, and "other informal"
everyone else (daily-wage, trade, service, artisan, driver, business owner and applicants
recorded as remittance-dependent whose observed income is mostly not remittances).
The simulation covers all 100,000 applicants with enough observed income, not only the
held-out split. In the threshold sweep the remittance households' bound is max(bound, 5).

Visibility v is drawn from a Beta distribution whose mean depends on the income type and
the scenario (SCENARIOS below). These means are assumptions to be replaced by lender
data; results are reported for each scenario rather than as estimates.

    python experiments/e3_imr_simulation.py --data "/path/Track A/structured"
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import common  # noqa: F401
from common import CACHE, FIGURES, SEED, data_dir, ensure_dirs, load_profiles, save_json

SALARIED = {"government employee", "teacher", "nurse/health worker"}
AGRI = {"farmer"}
SCENARIOS = {  # mean visible share of income by type
    "S1 all income visible": {"salaried": 1.0, "remittance": 1.0, "agriculture": 1.0, "other informal": 1.0},
    "S2 moderate gap": {"salaried": 0.9, "remittance": 0.85, "agriculture": 0.6, "other informal": 0.5},
    "S3 large gap": {"salaried": 0.8, "remittance": 0.7, "agriculture": 0.4, "other informal": 0.3},
}
KAPPA = 12.0           # Beta concentration
SIGMA_E = 0.2          # honest reporting noise (log scale)
PREV_OVER, PREV_UNDER = 0.05, 0.02
LOW, HIGH, HIGH_REMIT = 0.3, 3.0, 5.0
MIN_OBSERVED = 1000


def income_type(occ: str, remittance_share: float) -> str:
    if remittance_share >= 0.5:
        return "remittance"
    occ = (occ or "").strip().lower()
    if occ in SALARIED:
        return "salaried"
    if occ in AGRI:
        return "agriculture"
    return "other informal"


def draw_visibility(rng, mean: float, n: int) -> np.ndarray:
    if mean >= 0.999:
        return np.ones(n)
    a, b = mean * KAPPA, (1 - mean) * KAPPA
    return np.clip(rng.beta(a, b, n), 0.02, 1.0)


def simulate(df: pd.DataFrame, scenario: dict, rng, low=LOW, high=HIGH, high_remit=HIGH_REMIT):
    n = len(df)
    v = np.empty(n)
    for t, mean in scenario.items():
        m = (df["income_type"] == t).to_numpy()
        v[m] = draw_visibility(rng, mean, int(m.sum()))
    u = rng.random(n)
    over = u < PREV_OVER
    under = (u >= PREV_OVER) & (u < PREV_OVER + PREV_UNDER)
    honest = ~(over | under)
    factor = rng.lognormal(0.0, SIGMA_E, n)
    factor[over] = rng.uniform(1.5, 5.0, int(over.sum()))
    factor[under] = rng.uniform(0.1, 0.5, int(under.sum()))
    imr = factor / v
    upper = np.where(df["remittance_share"].to_numpy() >= 0.5, high_remit, high)
    flag = (imr < low) | (imr > upper)
    return honest, over, under, flag


def summarise(df, honest, over, under, flag):
    rows = []
    for t in ["salaried", "remittance", "agriculture", "other informal", "all"]:
        m = np.ones(len(df), bool) if t == "all" else (df["income_type"] == t).to_numpy()
        h, o, u = honest & m, over & m, under & m
        fpr = flag[h].mean() if h.any() else np.nan
        tpr_over = flag[o].mean() if o.any() else np.nan
        tpr_under = flag[u].mean() if u.any() else np.nan
        flagged = flag & m
        precision = ((over | under) & flagged).sum() / flagged.sum() if flagged.any() else np.nan
        rows.append({"income_type": t, "n": int(m.sum()), "false_flag_rate_honest": round(float(fpr), 6),
                     "detect_overstatement": round(float(tpr_over), 6), "detect_understatement": round(float(tpr_under), 6),
                     "flag_rate": round(float(flag[m].mean()), 6), "precision_of_flags": round(float(precision), 6)})
    return rows


def main():
    d = data_dir()
    ensure_dirs()
    feats = pd.read_parquet(CACHE / "income_features.parquet")
    prof = load_profiles(d)[["applicant_id", "occupation_en"]].drop_duplicates("applicant_id")
    df = feats.merge(prof, on="applicant_id", how="left")
    df["income_type"] = [income_type(o, r) for o, r in zip(df["occupation_en"], df["remittance_share"])]
    computable = df["derived_income_est"] >= MIN_OBSERVED
    out = {"assumptions": {"visibility_means": SCENARIOS, "beta_concentration": KAPPA, "honest_noise_sigma": SIGMA_E,
                           "prevalence_overstate": PREV_OVER, "prevalence_understate": PREV_UNDER,
                           "thresholds": {"low": LOW, "high": HIGH, "high_remittance": HIGH_REMIT},
                           "min_observed_income": MIN_OBSERVED, "seed": SEED},
           "population": {"applicants": int(len(df)), "imr_not_computable": int((~computable).sum()),
                          "imr_not_computable_share": round(float((~computable).mean()), 6),
                          "not_computable_by_type": df.loc[~computable, "income_type"].value_counts().to_dict(),
                          "type_mix_computable": df.loc[computable, "income_type"].value_counts(normalize=True).round(6).to_dict()},
           "scenarios": {}, "threshold_sensitivity": []}
    dc = df.loc[computable].reset_index(drop=True)
    for name, sc in SCENARIOS.items():
        rng = np.random.default_rng(SEED)
        res = simulate(dc, sc, rng)
        out["scenarios"][name] = summarise(dc, *res)
    for name, sc in SCENARIOS.items():
        for high in [2.0, 3.0, 4.0, 5.0, 6.0]:
            rng = np.random.default_rng(SEED)
            honest, over, under, flag = simulate(dc, sc, rng, high=high, high_remit=max(high, HIGH_REMIT))
            out["threshold_sensitivity"].append({
                "scenario": name, "upper_threshold": high,
                "false_flag_rate_honest": round(float(flag[honest].mean()), 6),
                "detect_overstatement": round(float(flag[over].mean()), 6),
                "false_flag_other_informal": round(float(flag[honest & (dc["income_type"] == "other informal").to_numpy()].mean()), 6),
            })
    save_json(out, "e3_imr_simulation.json")
    for name, rows in out["scenarios"].items():
        print(name)
        for r in rows:
            print("   ", r)
    # figure: false-flag rate of honest applicants vs detection, by threshold and scenario
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 8, "font.family": "serif",
                         "font.serif": ["Liberation Serif", "Times New Roman", "DejaVu Serif"],
                         "pdf.fonttype": 42, "ps.fonttype": 42})  # TrueType: no Type 3 fonts in the PDF
    fig, ax = plt.subplots(figsize=(3.4, 2.5))
    for name, marker in zip(SCENARIOS, ["o", "s", "^"]):
        pts = [r for r in out["threshold_sensitivity"] if r["scenario"] == name]
        ax.plot([p["false_flag_rate_honest"] for p in pts], [p["detect_overstatement"] for p in pts],
                marker=marker, ms=3, lw=1, label=name)
        first = name == next(iter(SCENARIOS))  # S1 points lie on the y-axis: label them on the left
        for p in pts:
            if p["upper_threshold"] in (2.0, 3.0, 6.0):
                ax.annotate(f"{p['upper_threshold']:.0f}", (p["false_flag_rate_honest"], p["detect_overstatement"]),
                            textcoords="offset points", xytext=(-4, -2) if first else (3, -7),
                            ha="right" if first else "left", fontsize=6)
    from matplotlib.ticker import PercentFormatter
    ax.xaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    ax.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    ax.set_xlim(left=-0.03)
    ax.set_xlabel("Honest applicants flagged")
    ax.set_ylabel("Overstatements caught")
    ax.legend(frameon=False, fontsize=6)
    fig.tight_layout()
    fig.savefig(FIGURES / "e3_imr_tradeoff.pdf"); fig.savefig(FIGURES / "e3_imr_tradeoff.png", dpi=200)


if __name__ == "__main__":
    main()
