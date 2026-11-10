"""
Score Agent: probability of default (PD) from a gradient-boosted model.

The model (app/ScoringModel/pd_model/) is trained by experiments/e2_outcome_model.py on
the synthetic repayment outcomes in the Track A data. It is stored in XGBoost's native
JSON format, with a feature specification that fixes the column order, the category
codes and the monotone constraints, so serving cannot drift from training.

The score is a standard points-to-double-the-odds scaling of PD (higher score = lower
risk), so it is monotone in PD by construction. SHAP values give the per-application
drivers shown to the credit officer.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from app.db import db
from app.models.state import AgentState
from app.services.credit_features import LABELS, build_feature_row

logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).resolve().parents[1] / "ScoringModel" / "pd_model"


def pd_to_score(pd_value: float, spec: Dict[str, Any]) -> int:
    """Points-to-double-odds scaling: score = offset + factor * ln(odds of repayment)."""
    s = spec["scaling"]
    p = min(max(float(pd_value), 1e-6), 1 - 1e-6)
    factor = s["pdo"] / math.log(2)
    offset = s["base_score"] - factor * math.log(s["base_odds"])
    score = offset + factor * math.log((1 - p) / p)
    return int(round(min(max(score, s["min_score"]), s["max_score"])))


def risk_grade(pd_value: float, spec: Dict[str, Any]) -> str:
    for grade in spec["grades"]:
        if pd_value < grade["pd_below"]:
            return grade["grade"]
    return spec["grades"][-1]["grade"]


class CreditScorer:
    """Loads the PD model once and scores single applications."""

    def __init__(self, model_dir: Path = MODEL_DIR):
        import xgboost as xgb

        self.model_dir = Path(model_dir)
        self.spec = json.loads((self.model_dir / "feature_spec.json").read_text())
        model_path = self.model_dir / "model.json"
        self.booster = xgb.Booster()
        self.booster.load_model(str(model_path))
        self.features: List[str] = self.spec["features"]
        self.categorical: Dict[str, Dict[str, int]] = self.spec["categories"]
        # The version covers both files: the spec holds the category codes, score scaling and grades.
        self.model_version = hashlib.sha256(
            model_path.read_bytes() + (self.model_dir / "feature_spec.json").read_bytes()
        ).hexdigest()[:12]
        n_model = self.booster.num_features()
        if n_model != len(self.features):
            raise ValueError(
                f"Model expects {n_model} features but feature_spec lists {len(self.features)}"
            )
        self._explainer = None

    def _vector(self, row: Dict[str, Any]) -> np.ndarray:
        values = []
        for f in self.features:
            v = row.get(f)
            if f in self.categorical:
                code = self.categorical[f].get(v) if v is not None else None
                values.append(np.nan if code is None else float(code))
            else:
                values.append(np.nan if v is None else float(v))
        return np.asarray([values], dtype=float)

    def predict_pd(self, row: Dict[str, Any]) -> float:
        import xgboost as xgb

        dm = xgb.DMatrix(self._vector(row), feature_names=self.features, missing=np.nan)
        return float(self.booster.predict(dm)[0])

    def drivers(self, row: Dict[str, Any], top_k: int = 5) -> List[Dict[str, Any]]:
        """Top SHAP contributions on the log-odds scale; positive raises PD."""
        try:
            import shap

            if self._explainer is None:
                self._explainer = shap.TreeExplainer(self.booster)
            contrib = self._explainer.shap_values(self._vector(row))[0]
        except Exception as e:  # SHAP is explanatory only; never block a decision on it
            logger.error(f"[Score Agent] SHAP failed: {e}")
            return []
        order = np.argsort(-np.abs(contrib))[:top_k]
        out = []
        for i in order:
            f = self.features[i]
            out.append({
                "feature": f,
                "label": LABELS.get(f, f),
                "value": row.get(f),
                "shap_log_odds": round(float(contrib[i]), 4),
                "direction": "raises risk" if contrib[i] > 0 else "lowers risk",
            })
        return out

    def score(self, row: Dict[str, Any]) -> Dict[str, Any]:
        pd_value = self.predict_pd(row)
        return {
            "status": "ok",
            "pd": round(pd_value, 5),
            "credit_score": pd_to_score(pd_value, self.spec),
            "risk_grade": risk_grade(pd_value, self.spec),
            "drivers": self.drivers(row),
            "model_version": self.model_version,
            "model_label": self.spec.get("label_definition"),
        }


@lru_cache(maxsize=1)
def get_scorer() -> CreditScorer:
    return CreditScorer()


def _fetch_single(table: str, key: str, value: Optional[str]) -> Dict[str, Any]:
    if not value:
        return {}
    try:
        return db.table(table).select("*").eq(key, value).single().execute().data or {}
    except Exception as e:
        logger.error(f"[Score Agent] lookup failed on {table}: {e}")
        return {}


def scoring_node(state: AgentState) -> Dict[str, Any]:
    """LangGraph entry point for the Score Agent."""
    profile = _fetch_single("applicant_profiles", "applicant_id", state.get("applicant_id"))
    application = _fetch_single("loan_applications", "application_id", state.get("application_id"))
    income_features = state.get("income_signal_features") or {}
    row = build_feature_row(profile, application, income_features, state.get("loan_request"))

    try:
        scorecard = get_scorer().score(row)
    except Exception as e:
        # A failed score is reported as such and routes to manual review downstream.
        logger.error(f"[Score Agent] scoring failed: {e}")
        scorecard = {"status": "error", "error": str(e), "pd": None, "credit_score": None,
                     "risk_grade": None, "drivers": []}
    scorecard["features"] = row

    application_id = state.get("application_id")
    if application_id and scorecard.get("status") == "ok":
        try:
            db.table("loan_applications").eq("application_id", application_id).update({
                "credit_score": scorecard["credit_score"],
                "score_band": scorecard["risk_grade"],
            })
        except Exception as e:
            logger.error(f"[Score Agent] DB update failed for {application_id}: {e}")
        try:  # columns added by scripts/sql/2026_11_add_assessment_columns.sql
            db.table("loan_applications").eq("application_id", application_id).update({
                "pd_estimate": scorecard["pd"],
                "shap_features": json.dumps(scorecard["drivers"]),
                "model_version": scorecard.get("model_version"),
            })
        except Exception as e:
            logger.warning(f"[Score Agent] optional columns not saved for {application_id}: {e}")

    return {"scorecard": scorecard}
