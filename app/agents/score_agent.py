from app.models.state import AgentState
from app.services.score_calculations import generate_scorecard


def score_application(state: AgentState):
    extracted_docs = state.get("extracted_docs", {})
    income_metrics = state.get("income_metrics", {})
    indicators = state.get("indicators", {})
    loan_request = state.get("loan_request", {})

    scorecard = generate_scorecard(
        extracted_docs=extracted_docs,
        income_metrics=income_metrics,
        indicators=indicators,
        loan_request=loan_request,
    )

    return {
        "scorecard": scorecard,
        "status": "scoring_complete",
    }
