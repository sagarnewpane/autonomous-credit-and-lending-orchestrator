import joblib
import json
import pandas as pd
import numpy as np
import shap
from pathlib import Path
from app.models.state import AgentState
from app.db.supabase import supabase  # Assuming you use supabase like in income_agent

ML_DIR = Path("app/ScoringModel")

class CreditScorer:
    def __init__(self):
        self.model = joblib.load(ML_DIR / "model.pkl")
        self.imputer = joblib.load(ML_DIR / "imputer.pkl")
        self.explainer = shap.TreeExplainer(self.model)
        
        with open(ML_DIR / "features.json", 'r') as f:
            self.expected_features = json.load(f)
            
        print("✅ Scoring Agent initialized successfully.")

    def _get_score_band(self, score: int) -> str:
        if score >= 740: return "excellent"
        elif score >= 670: return "very_good"
        elif score >= 580: return "good"
        elif score >= 450: return "fair"
        else: return "poor"

    def _preprocess(self, data: dict) -> np.ndarray:
        df = pd.DataFrame([data])
        
        # 1. Booleans to 1/0
        bool_cols = ['nrb_blacklist_flag', 'aml_flag', 'has_lalpurja', 'remittance_receiving', 
                     'cooperative_member', 'has_esewa_account', 'has_khalti_account']
        for col in bool_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).str.lower().map({'true': 1, 'false': 0, 'nan': 0}).fillna(0).astype(int)
            else:
                df[col] = 0

        # 2. KYC Tier
        if 'kyc_tier' in df.columns:
            df['kyc_tier_encoded'] = df['kyc_tier'].map({'basic': 0, 'mid': 1, 'full': 2}).fillna(-1)
        else:
            df['kyc_tier_encoded'] = -1

        # 3. Feature Engineering Fallbacks (In case DB didn't calculate them)
        if 'lti_ratio' not in df.columns or df['lti_ratio'].isna().any():
            df['lti_ratio'] = (df['requested_amount_nrs'] / df['income_agent_monthly_est'].replace(0, np.nan)).clip(upper=100)
            
        if 'ltv_ratio' not in df.columns or df['ltv_ratio'].isna().any():
            df['ltv_ratio'] = (df['requested_amount_nrs'] / df['collateral_value_nrs'].replace(0, np.nan)).clip(upper=10)
            
        if 'credit_debit_ratio' not in df.columns or df['credit_debit_ratio'].isna().any():
            df['credit_debit_ratio'] = df['total_credit_6m'] / df['total_debit_6m'].replace(0, np.nan)
            
        if 'payment_discipline' not in df.columns or df['payment_discipline'].isna().any():
            df['payment_discipline'] = df['latest_on_time_rate']*0.5 + (1 - df['late_payment_count'].clip(upper=10)/10)*0.3 + (1 - df['unpaid_bill_count'].clip(upper=5)/5)*0.2
            
        if 'income_per_capita' not in df.columns or df['income_per_capita'].isna().any():
            df['income_per_capita'] = df['income_agent_monthly_est'] / df['household_size'].replace(0, np.nan)

        # 4. One-Hot Encoding
        if 'rural_urban' in df.columns:
            df = pd.get_dummies(df, columns=['rural_urban'], dummy_na=True)
        if 'loan_purpose' in df.columns:
            df = pd.get_dummies(df, columns=['loan_purpose'], dummy_na=True)

        # 5. Align to exact model features
        for col in self.expected_features:
            if col not in df.columns:
                df[col] = 0.0
                
        return self.imputer.transform(df[self.expected_features])

    def _get_shap_audit_trail(self, processed_data: np.ndarray) -> dict:
        shap_values = self.explainer.shap_values(processed_data)
        if isinstance(shap_values, list):
            shap_values = shap_values[1]
        elif isinstance(shap_values, np.ndarray) and shap_values.ndim == 3:
            shap_values = shap_values[:, :, 1]
            
        shap_values = shap_values[0]
        top_3_idx = np.argsort(np.abs(shap_values))[-3:][::-1]
        
        factors = []
        primary_reason = "none"
        max_neg = 0.0
        
        for idx in top_3_idx:
            feat = self.expected_features[idx]
            val = round(float(shap_values[idx]), 4)
            factors.append({"feature": feat, "impact": val, "direction": "positive" if val > 0 else "negative"})
            if val < max_neg:
                max_neg = val
                primary_reason = feat
                
        return {"primary_reason": primary_reason, "shap_top_factors": factors}

    def score_applicant(self, data: dict) -> dict:
        try:
            processed_data = self._preprocess(data)
            prob = self.model.predict_proba(processed_data)[0][1]
            
            credit_score = int(300 + (prob * 550))
            credit_score = max(300, min(850, credit_score))
            
            return {
                "credit_score": credit_score,
                "score_band": self._get_score_band(credit_score),
                "audit_trail": self._get_shap_audit_trail(processed_data)
            }
        except Exception as e:
            return {
                "credit_score": 300,
                "score_band": "poor",
                "audit_trail": {"primary_reason": f"scoring_error: {str(e)}", "shap_top_factors": []}
            }

scorer = CreditScorer()

# ============================================================================
# LANGGRAPH NODE
# ============================================================================

# ============================================================================
# LANGGRAPH NODE
# ============================================================================

def scoring_node(state: AgentState):
    """Entry point for the Scoring Agent. Fetches master data from DB, merges with state."""
    
    applicant_id = state.get("applicant_id")
    if not applicant_id:
        return {"status": "scoring_failed", "error": "Missing applicant_id"}

    # 1. Fetch static & historical features from the DB Master Table
    try:
        db_response = supabase.table('scoring_feature_matrix') \
            .select('*') \
            .eq('applicant_id', applicant_id) \
            .single() \
            .execute()
            
        db_data = db_response.data or {}
        db_fetch_success = bool(db_data)
    except Exception as e:
        print(f"[Scoring Agent] DB Fetch Error for {applicant_id}: {e}")
        db_data = {}
        db_fetch_success = False

    # 2. Fetch dynamic data calculated by the Income Agent in LangGraph
    income_indicators = state.get("indicators", {})
    income_est = state.get("income_agent_monthly_est", 0)
    income_conf = state.get("income_confidence", 0.0)
    
    # Extract upstream LTI/LTV if the Income Agent calculated them
    upstream_lti = income_indicators.get("calculated_lti")
    upstream_ltv = income_indicators.get("calculated_ltv")

    # 3. Merge DB data and State data (State overrides DB for dynamic fields)
    applicant_data = {
        **db_data,  # Unpack all static/historical features from DB
        
        # Override with dynamic Income Agent calculations
        "income_agent_monthly_est": income_est,
        "income_confidence": income_conf,
        "lti_ratio": upstream_lti if upstream_lti is not None else db_data.get("lti_ratio"),
        "ltv_ratio": upstream_ltv if upstream_ltv is not None else db_data.get("ltv_ratio"),
        
        # Ensure booleans are present if DB stored them as strings
        "has_lalpurja": state.get("extracted_docs", {}).get("features", {}).get("asset_backing", {}).get("has_lalpurja", db_data.get("has_lalpurja", False))
    }

    # 4. Run the model
    result = scorer.score_applicant(applicant_data)
    
    # 5. Return comprehensive dictionary for debugging
    return {
        "status": "scoring_complete",
        "applicant_id": applicant_id,
        "scorecard": {
            "credit_score": result["credit_score"],
            "score_band": result["score_band"],
            "audit_trail": result["audit_trail"],
        },
        "debug_info": {
            "db_fetch_success": db_fetch_success,
            "upstream_inputs": {
                "income_agent_monthly_est": income_est,
                "income_confidence": income_conf,
                "upstream_lti": upstream_lti,
                "upstream_ltv": upstream_ltv,
            },
            # This is the exact dictionary passed into _preprocess()
            "model_input_features": applicant_data 
        }
    }