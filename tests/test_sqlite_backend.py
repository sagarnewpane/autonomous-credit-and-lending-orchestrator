import json

from app.db.sqlite import SQLiteClient


def test_sqlite_query_builder_seed_and_raw(tmp_path):
    db = SQLiteClient(str(tmp_path / "test.db"))

    users = db.table("users").select("id,email,is_admin").order("id").execute().data
    assert [u["email"] for u in users] == ["admin@dhago.app", "demo@dhago.app"]
    assert users[0]["is_admin"] is True
    assert users[1]["is_admin"] is False

    db.table("loan_applications").insert({
        "application_id": "LA-TEST",
        "applicant_id": "AP-1",
        "requested_amount_nrs": 150000.0,
        "loan_purpose": "test",
        "compliance_flags": ["DSTI_CAP"],
        "final_decision": None,
    })
    row = db.table("loan_applications").select("*").eq("application_id", "LA-TEST").single().execute().data
    assert row["requested_amount_nrs"] == 150000.0
    assert row["compliance_flags"] == ["DSTI_CAP"]

    db.table("loan_applications").eq("application_id", "LA-TEST").update({
        "final_decision": "APPROVE",
        "credit_score": 610,
        "shap_features": json.dumps([]),
    })
    row = db.table("loan_applications").select("*").eq("application_id", "LA-TEST").single().execute().data
    assert row["final_decision"] == "APPROVE"
    assert row["credit_score"] == 610
    assert row["shap_features"] == []

    db.table("income_signal_features").upsert(
        {"applicant_id": "AP-1", "derived_income_est": 5},
        on_conflict="applicant_id",
    )
    db.table("income_signal_features").upsert(
        {"applicant_id": "AP-1", "derived_income_est": 7},
        on_conflict="applicant_id",
    )
    rows = db.table("income_signal_features").select("*").eq("applicant_id", "AP-1").execute().data
    assert len(rows) == 1 and rows[0]["derived_income_est"] == 7

    stats = db.raw("""
        SELECT COUNT(*) AS total,
               COUNT(CASE WHEN final_decision = 'APPROVE' THEN 1 END) AS approved,
               COALESCE(SUM(requested_amount_nrs), 0) AS requested,
               COALESCE(ROUND(AVG(CASE WHEN credit_score IS NOT NULL THEN credit_score END), 1), 0) AS avg_score
        FROM loan_applications
    """)[0]
    assert stats == {"total": 1, "approved": 1, "requested": 150000.0, "avg_score": 610.0}

    assert db.table("missing_table").select("*").eq("x", 1).single().execute().data is None
