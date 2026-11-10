import json

from app.services import audit


def _write(log, n=3):
    for i in range(n):
        audit.record(f"APP-{i}", "decision_node", {"final_decision": "approve", "i": i})


def test_hash_chain_detects_an_edited_entry(tmp_path, monkeypatch):
    log = tmp_path / "audit.jsonl"
    monkeypatch.setenv("AUDIT_LOG_PATH", str(log))
    _write(log)
    res = audit.verify()
    assert (res["ok"], res["entries"], res["first_bad_seq"]) == (True, 3, None) and len(res["head"]) == 64
    lines = log.read_text().splitlines()
    entry = json.loads(lines[1])
    entry["payload"]["final_decision"] = "decline"
    lines[1] = json.dumps(entry)
    log.write_text("\n".join(lines) + "\n")
    res = audit.verify()
    assert not res["ok"] and res["first_bad_seq"] == 2


def test_truncation_is_caught_only_by_a_stored_head(tmp_path, monkeypatch):
    """Deleting entries from the end leaves a valid chain; comparing the head with a copy
    kept elsewhere detects it. This is the documented limitation of a plain hash chain."""
    log = tmp_path / "audit.jsonl"
    monkeypatch.setenv("AUDIT_LOG_PATH", str(log))
    _write(log)
    stored_head = audit.verify()["head"]
    lines = log.read_text().splitlines()
    log.write_text("\n".join(lines[:-1]) + "\n")
    res = audit.verify()
    assert res["ok"] and res["entries"] == 2
    assert res["head"] != stored_head


def test_read_filters_by_application(tmp_path, monkeypatch):
    monkeypatch.setenv("AUDIT_LOG_PATH", str(tmp_path / "a.jsonl"))
    audit.record("A", "income_node", {})
    audit.record("B", "income_node", {})
    assert [e["application_id"] for e in audit.read("A")] == ["A"]
