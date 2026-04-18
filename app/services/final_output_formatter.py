from typing import Any, Dict


def build_final_output(state: Dict[str, Any]) -> Dict[str, Any]:
    extracted_docs = state.get("extracted_docs", {})
    income_metrics = state.get("income_metrics", {})
    scorecard = state.get("scorecard", {})
    compliance_result = state.get("compliance_result", {})
    loan_request = state.get("loan_request", {})
    compliance_notes = state.get("compliance_notes", []) or []

    income_section = income_metrics.get("income", {})
    document_validation = income_metrics.get("document_validation", {})

    return {
        "application": {
            "citizenship_number": extracted_docs.get("citizenship_number"),
            "loan_amount_requested": loan_request.get("amount"),
            "loan_purpose": loan_request.get("purpose"),
            "requested_tenure": loan_request.get("tenure_months"),
            "status": state.get("status"),
        },
        "borrower_profile": {
            "primary_income_source": income_section.get("primary_income_source"),
            "total_observed_income": income_section.get("total_observed_income"),
            "total_effective_income": income_section.get("total_effective_income"),
            "declared_monthly_income": document_validation.get("declared_monthly_income"),
            "months_of_data": income_section.get("months_of_data"),
            "informal_income_ratio_%": income_metrics.get("composition", {}).get("informal_income_ratio_%"),
            "asset_backing": document_validation.get("asset_backing") or {},
        },
        "score_summary": {
            "credit_score": scorecard.get("credit_score"),
            "risk_tier": scorecard.get("risk_tier"),
            "scoring_confidence": scorecard.get("scoring_confidence"),
            "estimated_monthly_capacity": scorecard.get("estimated_monthly_capacity"),
            "income_mismatch_ratio": scorecard.get("income_mismatch_ratio"),
            "stability_score": scorecard.get("stability_score"),
            "tax_trust_score": scorecard.get("tax_trust_score"),
            "fraud_flags": scorecard.get("fraud_flags"),
            "top_risk_drivers": scorecard.get("top_risk_drivers"),
        },
        "decision_summary": {
            "final_decision": compliance_result.get("final_decision"),
            "approved_amount": compliance_result.get("approved_amount"),
            "approved_tenure": compliance_result.get("approved_tenure"),
            "decision_reason": compliance_result.get("decision_reason"),
            "nrb_directive_cited": compliance_result.get("nrb_directive_cited"),
            "modifications_made": compliance_result.get("modifications_made"),
            "compliance_flags": compliance_result.get("compliance_flags"),
        },
        "notes": compliance_notes,
    }
