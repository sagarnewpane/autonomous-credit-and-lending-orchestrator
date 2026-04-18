import asyncio
import json

from app.agents.compliance_agent import check_compliance
from app.agents.score_agent import score_application
from app.models.state import AgentState
from app.services.income_profile_calculations import generate_income_profile
from app.services.risk_calculations import generate_risk_indicators


async def run_test():
    with open("data/categorized_transactions.json", "r") as f:
        categorized_transactions = json.load(f)

    extracted_docs = {
        "citizenship_number": "47-03-00-0003",
        "features": {
            "declared_annual_income": 108000.0,
            "declared_monthly_income": 9000.0,
            "tax_compliance_flag": 1,
            "tax_paid_amount": 29990.0,
            "effective_tax_rate": 0.27769,
            "tax_document_present": True,
            "asset_backing": {
                "has_lalpurja": True,
                "asset_type": "land",
                "ownership_documented": True,
                "land_area": 149.03,
                "plot_number": None,
                "district": "झापा",
                "owner_name": "तुलसा अधिकारी",
                "document_confidence": 0.92,
            },
        },
        "flags": ["citizenship_mismatch_across_documents"],
        "all_citizenship_numbers_found": [
            ("citizenship", "47-03"),
            ("lalpurja", "47-03-00-0003"),
        ],
    }

    loan_request = {
        "amount": 500000,
        "existing_liabilities_monthly": 0,
        "purpose": "business",
        "tenure_months": 12,
    }

    income_metrics = generate_income_profile(categorized_transactions, extracted_docs)
    indicators = generate_risk_indicators(income_metrics, extracted_docs, loan_request)

    state: AgentState = {
        "file_paths": {},
        "raw_transactions": categorized_transactions,
        "extracted_docs": extracted_docs,
        "categorized_txns": categorized_transactions,
        "income_metrics": income_metrics,
        "indicators": indicators,
        "loan_request": loan_request,
        "scorecard": {},
        "compliance_result": {},
        "final_output": {},
        "status": "income_analysis_complete",
        "compliance_notes": [],
        "errors": [],
    }

    state.update(score_application(state))
    state.update(check_compliance(state))

    print(json.dumps(
        state["final_output"],
        indent=2,
        ensure_ascii=False,
    ))


if __name__ == "__main__":
    asyncio.run(run_test())
