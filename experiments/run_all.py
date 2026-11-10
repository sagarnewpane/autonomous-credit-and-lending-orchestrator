"""
Reproduce every number and figure in the paper.

    python experiments/run_all.py --data "/path/Track A/structured"

Order: data_summary -> build_features (about 11 minutes on 2 cores) -> E1 -> E2 (trains and
saves the deployed model) -> E3 -> E4 -> E5, then writes experiments/results/summary.json.
About 15 minutes in all.
Pass --skip-features to reuse experiments/cache/income_features.parquet, or --summary-only
to rebuild summary.json from the existing results.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time

import common  # noqa: F401
from common import CACHE, EXP, RESULTS, data_dir, save_json

STEPS = ["data_summary.py", "build_features.py", "e1_label_circularity.py", "e2_outcome_model.py",
         "e3_imr_simulation.py", "e4_routing_fairness.py", "e5_pipeline_run.py"]
RESULT_FILES = ["data_summary", "e1_label_circularity", "e2_outcome_model", "e3_imr_simulation",
                "e4_routing_fairness", "e5_pipeline_run"]


def build_summary() -> dict:
    """Collect the numbers quoted in the paper into one file."""
    r = {n: json.loads((RESULTS / f"{n}.json").read_text()) for n in RESULT_FILES}
    data, e1, e2, e3, e4, e5 = (r[k] for k in RESULT_FILES)
    released = e2["models"]["released model"]
    groups = {g: {k: {m: v.get(m) for m in ("n", "approve_or_conditional", "thin_file", "auc")} for k, v in tab.items()}
              for g, tab in e4["groups"].items() if g in ("gender", "rural_urban", "province")}
    return {
        "data": data,
        "e1_best_tree": max(e1["trees"], key=lambda t: t["heldout_accuracy"]),
        "e1_two_fields_accuracy": e1["two_fields_depth6_accuracy"],
        "e2_split": {k: e2[k] for k in ("n_train", "n_early_stop", "n_test", "n_test_defaults")},
        "e2_auc": {k: (v["auc"], v["auc_95ci"]) for k, v in e2["models"].items()},
        "e2_ablation_auc": {k: (v["auc"], v["auc_95ci"]) for k, v in e2["ablations"].items()},
        "e2_released_calibration": {k: released[k] for k in ("brier", "ece_10bins", "mean_pd", "observed_rate")},
        "e2_timing": e2["timing"],
        "e2_paired_differences": e2["paired_auc_differences"],
        "e2_secondary_label_auc": e2["secondary_label_default_or_delinquent"]["auc"],
        "e3_population": e3["population"],
        "e3_by_scenario_and_type": {k: v for k, v in e3["scenarios"].items()},
        "e3_threshold_sensitivity": e3["threshold_sensitivity"],
        "e4_decision_mix": e4["decision_mix"], "e4_rule_trigger_rates": e4["rule_trigger_rates"],
        "e4_thin_file": {"share": e4["thin_file_share"], "new_decisions": e4["thin_file_decisions_new"]},
        "e4_default_rate_by_decision": e4["with_outcomes"]["default_rate_by_decision"],
        "e4_dsti": {"applicable_share": e4["dsti_applicable_share"],
                    "trigger_rate_if_true_income_is_k_times_observed":
                        e4["dsti_trigger_rate_if_true_income_is_k_times_observed"]},
        "e4_observed_income": {k: e4[k] for k in ["median_observed_monthly_income",
                               "median_observed_monthly_income_if_positive", "share_without_observed_income",
                               "median_requested_amount"]},
        "e4_groups": groups,
        "e4_top_driver": e4["top_driver"],
        "e4_dsti_and_referrals": e4["dsti_and_referrals"],
        "e5": {k: e5[k] for k in ["n", "agreement_with_batch_decisions", "max_abs_pd_difference_vs_batch",
                                  "audit_chain", "latency_ms"]},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-features", action="store_true")
    ap.add_argument("--summary-only", action="store_true")
    args, _ = ap.parse_known_args()
    if not args.summary_only:
        d = data_dir()
        for step in STEPS:
            if step == "build_features.py" and args.skip_features and (CACHE / "income_features.parquet").exists():
                print(f"skip {step}")
                continue
            t0 = time.time()
            print(f"== {step}", flush=True)
            subprocess.run([sys.executable, str(EXP / step), "--data", str(d)], check=True, cwd=str(EXP))
            print(f"   done in {time.time() - t0:.0f}s", flush=True)
    summary = build_summary()
    save_json(summary, "summary.json")
    print(json.dumps(summary, indent=1)[:2000])


if __name__ == "__main__":
    main()
