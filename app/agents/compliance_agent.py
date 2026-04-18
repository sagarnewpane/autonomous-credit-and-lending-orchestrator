from app.models.state import AgentState
from app.services.final_output_formatter import build_final_output


def check_compliance(state: AgentState):
    extracted_docs = state.get("extracted_docs", {})
    scorecard = state.get("scorecard", {})
    compliance_notes = list(state.get("compliance_notes", []) or [])
    loan_request = state.get("loan_request", {})

    fraud_flags = scorecard.get("fraud_flags", [])
    requested_amount = float(loan_request.get("amount", 500000) or 500000)
    requested_tenure = int(loan_request.get("tenure_months", 12) or 12)
    requested_purpose = str(loan_request.get("purpose", "general") or "general")

    dti = float(scorecard.get("calculated_dti", 0) or 0)
    lti = float(scorecard.get("calculated_lti", 0) or 0)
    suggested_amount = float(scorecard.get("suggested_loan_amount", requested_amount) or requested_amount)
    suggested_tenure = int(scorecard.get("suggested_tenure", requested_tenure) or requested_tenure)
    credit_score = int(scorecard.get("credit_score", 0) or 0)

    if "identity_mismatch_low_confidence" in fraud_flags:
        compliance_notes.append("WARNING: Citizenship mismatch appears driven by incomplete or low-confidence OCR.")
    if "identity_mismatch_hard" in fraud_flags:
        compliance_notes.append("WARNING: Hard citizenship mismatch detected across documents.")
    if "income_mismatch_low" in fraud_flags:
        compliance_notes.append("ADVISORY: Declared income is materially below observed cash flow.")
    if "income_mismatch_high" in fraud_flags:
        compliance_notes.append("ADVISORY: Declared income materially exceeds observed cash flow.")

    final_decision = "APPROVE"
    approved_amount = requested_amount
    approved_tenure = requested_tenure
    decision_reason = "Application meets current v1 compliance thresholds."
    nrb_directive_cited = "NRB UD 2080 - advisory hackathon ruleset"
    modifications_made = []
    compliance_flags = []

    if "identity_mismatch_hard" in fraud_flags:
        final_decision = "REJECT"
        approved_amount = 0.0
        decision_reason = "KYC inconsistency indicates a hard identity conflict."
        nrb_directive_cited = "NRB AML Guidelines"
        compliance_flags.append("identity_mismatch_hard")
    elif lti > 5.0:
        final_decision = "REJECT"
        approved_amount = 0.0
        decision_reason = "Requested loan exceeds the 5x annual-income limit."
        nrb_directive_cited = "NRB UD 2080, Directive 5.1"
        compliance_flags.append("lti_limit_breach")
    elif dti > 0.5:
        final_decision = "REJECT"
        approved_amount = 0.0
        decision_reason = "Debt burden exceeds the hard repayment threshold."
        nrb_directive_cited = "NRB UD 2080, Directive 5.2"
        compliance_flags.append("dti_hard_breach")
    elif credit_score < 400 and dti < 0.3:
        final_decision = "MANUAL_REVIEW"
        decision_reason = "Model risk is high even though repayment ratios are currently acceptable."
        compliance_flags.append("model_capacity_conflict")
    elif dti > 0.4 or suggested_amount < requested_amount or suggested_tenure != requested_tenure:
        final_decision = "MODIFY"
        approved_amount = suggested_amount
        approved_tenure = suggested_tenure
        decision_reason = "Request has been adjusted to fit conservative repayment thresholds."
        nrb_directive_cited = "NRB UD 2080, Directive 5.2"
        if approved_amount != requested_amount:
            modifications_made.append(
                f"Reduced amount from {requested_amount:.2f} to {approved_amount:.2f}"
            )
        if approved_tenure != requested_tenure:
            modifications_made.append(
                f"Extended tenure from {requested_tenure} to {approved_tenure} months"
            )

    if requested_purpose.lower() in {"gambling", "illegal", "banned"}:
        final_decision = "REJECT"
        approved_amount = 0.0
        approved_tenure = requested_tenure
        decision_reason = "Loan purpose is prohibited under the current lending ruleset."
        nrb_directive_cited = "NRB UD 2080, Directive 4.2"
        compliance_flags.append("prohibited_purpose")

    compliance_result = {
        "requested_loan_amount": requested_amount,
        "requested_tenure": requested_tenure,
        "loan_purpose": requested_purpose,
        "final_decision": final_decision,
        "approved_amount": round(approved_amount, 2),
        "approved_tenure": approved_tenure,
        "decision_reason": decision_reason,
        "nrb_directive_cited": nrb_directive_cited,
        "modifications_made": modifications_made,
        "compliance_flags": compliance_flags,
        "credit_score": credit_score,
        "risk_tier": scorecard.get("risk_tier"),
        "fraud_flags": fraud_flags,
        "estimated_monthly_capacity": scorecard.get("estimated_monthly_capacity"),
        "calculated_dti": dti,
        "calculated_lti": lti,
        "audit_note": "Compliance decision generated from scorecard output and advisory repayment ratios.",
    }

    if extracted_docs.get("flags") and "citizenship_mismatch_across_documents" in extracted_docs.get("flags", []):
        compliance_notes.append("INFO: Parser flagged a document mismatch; scorecard classification was applied before final decision.")

    final_output = build_final_output(
        {
            **state,
            "compliance_notes": compliance_notes,
            "compliance_result": compliance_result,
            "status": "compliance_checks_complete",
        }
    )

    return {
        "compliance_notes": compliance_notes,
        "compliance_result": compliance_result,
        "final_output": final_output,
        "status": "compliance_checks_complete",
    }
