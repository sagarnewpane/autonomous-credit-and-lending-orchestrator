"""
E1. Is the Track A decision label a deterministic function of the dataset's own fields?

Fits shallow decision trees on four generator outputs (organiser credit score, organiser
income confidence, compliance status, number of compliance flags) and measures held-out
accuracy against final_decision. If a small tree reproduces the label, accuracy against
that label measures how well a model re-learns the generator's rule, not credit risk.

    python experiments/e1_label_circularity.py --data "/path/Track A/structured"
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score
from sklearn.tree import DecisionTreeClassifier, export_text

import common  # noqa: F401
from common import SEED, data_dir, load_applications, save_json


def main():
    d = data_dir()
    la = load_applications(d)
    y = la["final_decision"].astype(str).str.strip().str.lower().replace({"nan": np.nan})
    X = pd.DataFrame({
        "organiser_credit_score": pd.to_numeric(la["credit_score"], errors="coerce").fillna(-1),
        "organiser_income_confidence": pd.to_numeric(la["income_confidence"], errors="coerce").fillna(-1),
        "compliance_flagged": (la["compliance_status"].astype(str).str.lower() == "flag").astype(int),
        "compliance_failed": (la["compliance_status"].astype(str).str.lower() == "fail").astype(int),
        "n_compliance_flags": la["compliance_flags"].astype(str).str.count('"') // 2,
    })
    train = (la["data_split"] == "train") & y.notna()
    held = la["data_split"].isin(["val", "public_test"]) & y.notna()
    out = {"n_train": int(train.sum()), "n_heldout": int(held.sum()),
           "label_distribution": y[train | held].value_counts(normalize=True).round(4).to_dict(), "trees": []}
    for depth in [1, 2, 3, 4, 5, 6, 8, 10]:
        t = DecisionTreeClassifier(max_depth=depth, random_state=SEED).fit(X[train], y[train])
        p = t.predict(X[held])
        out["trees"].append({"max_depth": depth, "leaves": int(t.get_n_leaves()),
                             "heldout_accuracy": round(accuracy_score(y[held], p), 4),
                             "heldout_macro_f1": round(f1_score(y[held], p, average="macro"), 4)})
        print(f"depth {depth:2d}: leaves={t.get_n_leaves():3d} acc={out['trees'][-1]['heldout_accuracy']:.4f}")
    two = ["organiser_credit_score", "organiser_income_confidence"]
    t2 = DecisionTreeClassifier(max_depth=6, random_state=SEED).fit(X.loc[train, two], y[train])
    out["two_fields_depth6_accuracy"] = round(accuracy_score(y[held], t2.predict(X.loc[held, two])), 4)
    t3 = DecisionTreeClassifier(max_depth=3, random_state=SEED).fit(X[train], y[train])
    out["depth3_rules"] = export_text(t3, feature_names=list(X.columns), decimals=3)
    print(out["depth3_rules"])
    print("two fields, depth 6:", out["two_fields_depth6_accuracy"])
    save_json(out, "e1_label_circularity.json")


if __name__ == "__main__":
    main()
