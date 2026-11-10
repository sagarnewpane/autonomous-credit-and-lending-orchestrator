"""Integration test: the full graph on real Track A rows. Skipped unless TRACK_A_DIR is set."""
import os

import pytest

pytestmark = pytest.mark.skipif(not os.getenv("TRACK_A_DIR"), reason="TRACK_A_DIR not set")


def test_pipeline_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setenv("AUDIT_LOG_PATH", str(tmp_path / "audit.jsonl"))
    from app.agents.pipeline import get_workflow
    from app.db import db
    from app.services import audit

    apps = db.table("loan_applications").select("*").eq("data_split", "public_test").limit(3).execute().data
    wf = get_workflow()
    for app in apps:
        out = wf.invoke({"applicant_id": app["applicant_id"], "application_id": app["application_id"],
                         "loan_request": {"amount": 100000, "tenure_months": 24, "existing_liabilities_monthly": 0,
                                          "declared_monthly_income": 20000}})
        assert out["final_decision"] in {"approve", "conditional", "refer", "decline"}
        assert out["final_output"]["policy_version"]
        assert out["imr_status"] in {"computed", "insufficient_observed", "not_declared"}
    check = audit.verify()
    assert check["ok"] and check["entries"] >= 3 * 3
