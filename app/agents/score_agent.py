import joblib
import json
import pandas as pd
import numpy as np
import shap
from pathlib import Path
from app.models.state import AgentState
from app.db import db

ML_DIR = Path(__file__).resolve().parent.parent / "ScoringModel"


class CreditScorer:
    """
    Loads the artifacts produced by the training notebook:
      - xgboost_4class_model.pkl : the trained model
      - ordinal_encoder.pkl      : OrdinalEncoder fit on TRAIN categorical columns only
      - train_medians.pkl        : per-column medians from TRAIN, for consistent imputation
      - model_config.json        : feature list, categorical/numeric column split, class mapping

    Everything about how a row gets turned into numbers is driven by these four
    files, not hardcoded here. If you retrain the model with a different feature
    set, this class picks it up automatically - no code changes needed.
    """

    def __init__(self):
        self.model = joblib.load(ML_DIR / "xgboost_4class_model.pkl")
        self.encoder = joblib.load(ML_DIR / "ordinal_encoder.pkl")
        self.train_medians = joblib.load(ML_DIR / "train_medians.pkl")
        self.explainer = shap.TreeExplainer(self.model)

        with open(ML_DIR / "model_config.json", "r") as fp:
            self.model_config = json.load(fp)

        self.features = self.model_config["features"]
        self.class_mapping = {int(k): v for k, v in self.model_config["class_mapping"].items()}

        # Derive categorical/numeric splits from config or feature names
        if "categorical_cols" in self.model_config and "numeric_cols" in self.model_config:
            self.categorical_cols = self.model_config["categorical_cols"]
            self.numeric_cols = self.model_config["numeric_cols"]
        else:
            # Fallback: infer from feature names
            self.categorical_cols = [f for f in self.features if f in {
                "application_date_bs", "loan_purpose", "province_en", "district_en",
                "municipality_en", "rural_urban", "collateral_type", "cooperative_id",
                "gender", "marital_status", "occupation_en", "education_level",
                "kyc_tier", "coop_cooperative_type", "coop_coop_loan_repayment_status",
                "coop_membership_status",
            }]
            self.numeric_cols = [f for f in self.features if f not in self.categorical_cols]

        print(f"✅ Scoring Agent initialized — {len(self.features)} features "
              f"({len(self.categorical_cols)} categorical, {len(self.numeric_cols)} numeric).")

    def _get_score_band(self, score: int) -> str:
        if score >= 800: return "excellent"
        elif score >= 700: return "very_good"
        elif score >= 600: return "good"
        elif score >= 500: return "fair"
        else: return "poor"

    def _engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Reproduces the exact derived-feature logic from the training notebook."""

        # --- date-derived features ---
        app_date = pd.to_datetime(df.get("application_date_ad"), errors="coerce")
        # a live application with no date yet is being scored "now"
        app_date = app_date.fillna(pd.Timestamp.today())
        df["application_month"] = app_date.dt.month
        df["application_dayofweek"] = app_date.dt.dayofweek

        dob = pd.to_datetime(df.get("dob_ad"), errors="coerce")
        age = (pd.Timestamp.today() - dob).dt.days / 365.25
        df["age"] = age.clip(18, 100)

        # --- ratio features (must match notebook exactly) ---
        requested = pd.to_numeric(df.get("requested_amount_nrs"), errors="coerce")
        collateral = pd.to_numeric(df.get("collateral_value_nrs"), errors="coerce").replace(0, np.nan)
        income = pd.to_numeric(df.get("derived_income_est"), errors="coerce")
        alt_score = pd.to_numeric(df.get("credit_score"), errors="coerce").replace(0, np.nan)

        df["lti_ratio"] = (requested / collateral).clip(0, 10)
        df["income_to_loan_ratio"] = income / requested.replace(0, np.nan)
        df["amount_to_score_ratio"] = requested / alt_score

        # --- score availability flags (two distinct scores: CIB vs. alternative) ---
        df["has_cib_score"] = pd.to_numeric(df.get("credit_bureau_score"), errors="coerce").notna().astype(int)
        df["has_alt_score"] = pd.to_numeric(df.get("credit_score"), errors="coerce").notna().astype(int)

        return df

    def _preprocess(self, data: dict) -> np.ndarray:
        df = pd.DataFrame([data])
        df = self._engineer_features(df)

        # add any expected feature that's missing from this applicant's data
        for col in self.features:
            if col not in df.columns:
                df[col] = np.nan

        # categorical: same OrdinalEncoder fit on TRAIN, applied here unchanged.
        # NOTE: the encoder is case-sensitive because it was fit on raw strings
        # during training (no .lower() applied). Whatever casing convention the
        # training data used (e.g. "male", "rural") must be used here too, or
        # values will fall through to the unknown-category code (-1).
        if self.categorical_cols:
            df[self.categorical_cols] = self.encoder.transform(
                df[self.categorical_cols].astype(str)
            )

        # numeric: coerce, then impute with TRAIN medians (not this applicant's
        # own value, not a hardcoded default) so imputation matches training
        for col in self.numeric_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df[self.numeric_cols] = df[self.numeric_cols].fillna(self.train_medians).fillna(-1)

        return df[self.features].astype(float).values

    def _get_shap_audit_trail(self, processed_data: np.ndarray, predicted_class_idx: int) -> dict:
        shap_raw = self.explainer.shap_values(processed_data)

        if isinstance(shap_raw, list):
            # older SHAP API: one array per class
            class_shap = shap_raw[predicted_class_idx][0]
        elif isinstance(shap_raw, np.ndarray) and shap_raw.ndim == 3:
            # (rows, features, classes)
            class_shap = shap_raw[0, :, predicted_class_idx]
        else:
            class_shap = shap_raw[0]

        top_3_idx = np.argsort(np.abs(class_shap))[-3:][::-1]

        factors = []
        primary_reason = "none"
        max_neg = 0.0

        for idx in top_3_idx:
            feat = self.features[idx]
            val = round(float(class_shap[idx]), 4)
            factors.append({"feature": feat, "impact": val, "direction": "positive" if val > 0 else "negative"})
            if val < max_neg:
                max_neg = val
                primary_reason = feat

        return {"primary_reason": primary_reason, "shap_top_factors": factors}

    def score_applicant(self, data: dict) -> dict:
        try:
            processed_data = self._preprocess(data)

            probs = self.model.predict_proba(processed_data)[0]
            predicted_class_idx = int(np.argmax(probs))
            predicted_label = self.class_mapping[predicted_class_idx]

            class_probabilities = {
                self.class_mapping[i]: round(float(probs[i]), 4)
                for i in range(len(probs))
            }

            max_prob = float(probs[predicted_class_idx])
            credit_score = int(300 + (max_prob * 550))
            credit_score = max(300, min(850, credit_score))

            return {
                "credit_score": credit_score,
                "score_band": self._get_score_band(credit_score),
                "decision": predicted_label,
                "class_probabilities": class_probabilities,
                "audit_trail": self._get_shap_audit_trail(processed_data, predicted_class_idx),
            }
        except Exception as e:
            return {
                "credit_score": 300,
                "score_band": "poor",
                "decision": "reject",
                "class_probabilities": {},
                "audit_trail": {"primary_reason": f"scoring_error: {str(e)}", "shap_top_factors": []},
            }


scorer = CreditScorer()

# ============================================================================
# LANGGRAPH NODE
# ============================================================================

def scoring_node(state: AgentState):
    """Entry point for the Scoring Agent. Fetches master data from DB, merges with state."""

    applicant_id = state.get("applicant_id")
    application_id = state.get("application_id")
    if not applicant_id:
        return {"status": "scoring_failed", "error": "Missing applicant_id"}

    # 1. Fetch static & historical features from the DB Master Table
    try:
        db_response = db.table('master_dataset_clean') \
            .select('*') \
            .eq('application_id', application_id) \
            .single() \
            .execute()

        db_data = db_response.data or {}
        db_fetch_success = bool(db_data)
    except Exception as e:
        print(f"[Scoring Agent] DB Fetch Error for {application_id}: {e}")
        db_data = {}
        db_fetch_success = False

    # 2. Fetch dynamic data calculated by the Income Agent in LangGraph
    income_est = state.get("income_agent_monthly_est", 0)
    income_conf = state.get("income_confidence", 0.0)

    print(f"[Scoring Agent] DB data keys: {list(db_data.keys())}")

    # 3. Merge DB data and State data (State overrides DB for dynamic fields).
    # lti_ratio / income_to_loan_ratio are deliberately NOT taken from the Income
    # Agent's upstream calculation here - the model was trained on a specific
    # formula (see _engineer_features), and using a differently-defined ratio
    # under the same feature name would silently corrupt predictions the same
    # way the old factorize() mismatch did. They're recomputed fresh below.
    applicant_data = {
        **db_data,  # Unpacks all static/historical features from DB

        # Fix column name mismatches (master table uses _en suffix)
        "gender": db_data.get("gender_en", db_data.get("gender", "unknown")),
        "marital_status": db_data.get("marital_status_en", db_data.get("marital_status", "unknown")),

        # Override with dynamic Income Agent calculations
        "income_agent_monthly_est": income_est,
        "income_confidence": income_conf,
        "derived_income_est": income_est if income_est else db_data.get("derived_income_est"),
    }

    print(f"[Scoring Agent] Applicant data for model: gender={applicant_data.get('gender')}, "
          f"marital_status={applicant_data.get('marital_status')}")

    # 4. Run the model
    print(f"[Scoring Agent] Running model...")
    result = scorer.score_applicant(applicant_data)
    print(f"[Scoring Agent] Result: credit_score={result['credit_score']}, "
          f"score_band={result['score_band']}, decision={result['decision']}")

    # 5. Save scoring results to database immediately
    if application_id:
        try:
            db.table("loan_applications") \
                .update({"credit_score": result["credit_score"], "score_band": result["score_band"]}) \
                .eq("application_id", application_id) \
                .execute()
        except Exception as e:
            print(f"[Scoring Agent] DB Save Error for {application_id}: {e}")

    return {
        "status": "scoring_complete",
        "applicant_id": applicant_id,
        "scorecard": {
            "credit_score": result["credit_score"],
            "score_band": result["score_band"],
            "decision": result["decision"],
            "class_probabilities": result["class_probabilities"],
            "audit_trail": result["audit_trail"],
        },
        "debug_info": {
            "db_fetch_success": db_fetch_success,
            "upstream_inputs": {
                "income_agent_monthly_est": income_est,
                "income_confidence": income_conf,
            },
            "model_input_features": applicant_data,
        },
    }