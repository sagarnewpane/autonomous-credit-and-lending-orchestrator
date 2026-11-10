import pandas as pd

from app.db.memory import MemoryClient


def test_query_update_upsert(tmp_path):
    pd.DataFrame({"application_id": ["A", "B"], "applicant_id": ["X", "Y"], "requested_amount_nrs": [100.0, 200.0]}) \
        .to_csv(tmp_path / "loan_applications.csv", index=False)
    db = MemoryClient(str(tmp_path))
    row = db.table("loan_applications").select("*").eq("application_id", "B").single().execute().data
    assert row["applicant_id"] == "Y"
    db.table("loan_applications").eq("application_id", "A").update({"final_decision": "refer", "credit_score": 610})
    a = db.table("loan_applications").select("final_decision,credit_score").eq("application_id", "A").single().execute().data
    assert a == {"final_decision": "refer", "credit_score": 610}
    db.table("income_signal_features").upsert({"applicant_id": "X", "derived_income_est": 5}, on_conflict="applicant_id")
    db.table("income_signal_features").upsert({"applicant_id": "X", "derived_income_est": 7}, on_conflict="applicant_id")
    rows = db.table("income_signal_features").select("*").eq("applicant_id", "X").execute().data
    assert len(rows) == 1 and rows[0]["derived_income_est"] == 7
    assert db.table("missing_table").select("*").eq("x", 1).single().execute().data is None
