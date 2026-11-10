"""
Append-only, hash-chained audit log.

Each pipeline node appends one JSON line: when it ran, for which application and what it
returned (a summary, not raw personal data). The decision entry also carries the policy
and model versions and the Income Agent's flags.

Every entry stores the hash of the previous entry. Editing or deleting an entry breaks the
chain from that point, and verify() reports where, unless every later entry is rewritten
too; deleting entries from the end leaves a valid but shorter chain. To detect both, keep
the latest hash (verify() returns it as "head") somewhere the log's writer cannot change.

Location: AUDIT_LOG_PATH (default ./audit_log.jsonl). This is a tamper-evident record for
review, not a substitute for write-once storage in production.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_LOCK = threading.Lock()
GENESIS = "0" * 64


def _path() -> Path:
    return Path(os.getenv("AUDIT_LOG_PATH", "audit_log.jsonl"))


def _canonical(entry: Dict[str, Any]) -> str:
    return json.dumps(entry, sort_keys=True, separators=(",", ":"), default=str)


def _last_hash(path: Path) -> Tuple[str, int]:
    if not path.exists() or path.stat().st_size == 0:
        return GENESIS, 0
    last_line = ""
    seq = 0
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                last_line = line
                seq += 1
    return json.loads(last_line)["hash"], seq


def record(application_id: Optional[str], agent: str, payload: Dict[str, Any]) -> str:
    """Append one entry and return its hash."""
    path = _path()
    with _LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        prev_hash, seq = _last_hash(path)
        entry = {
            "seq": seq + 1,
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "application_id": application_id,
            "agent": agent,
            "payload": payload,
            "prev_hash": prev_hash,
        }
        entry["hash"] = hashlib.sha256(_canonical(entry).encode("utf-8")).hexdigest()
        with path.open("a", encoding="utf-8") as fh:
            fh.write(_canonical(entry) + "\n")
    return entry["hash"]


def read(application_id: Optional[str] = None, path: Optional[Path] = None) -> List[Dict[str, Any]]:
    path = path or _path()
    if not path.exists():
        return []
    out = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                e = json.loads(line)
                if application_id is None or e.get("application_id") == application_id:
                    out.append(e)
    return out


def verify(path: Optional[Path] = None) -> Dict[str, Any]:
    """Recompute the chain. Returns {"ok", "entries", "first_bad_seq", "head"}; "head" is the
    hash of the last entry, to be stored elsewhere so that truncation can be detected."""
    entries = read(path=path)
    prev = GENESIS
    for e in entries:
        body = {k: v for k, v in e.items() if k != "hash"}
        if e.get("prev_hash") != prev or hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest() != e.get("hash"):
            return {"ok": False, "entries": len(entries), "first_bad_seq": e.get("seq"), "head": None}
        prev = e["hash"]
    return {"ok": True, "entries": len(entries), "first_bad_seq": None, "head": prev}


# What each node's audit entry keeps: decision-relevant outputs only, no raw transactions.
SUMMARY_KEYS = {
    "income_node": ["income_agent_monthly_est", "income_confidence", "income_signal_count",
                    "declared_monthly_income", "imr", "imr_status", "remittance_share", "income_flags"],
    "compliance_node": ["compliance_status", "compliance_flags", "compliance_notes", "policy_version"],
    "scoring_node": ["scorecard"],
    "decision_node": ["final_decision", "approved_amount_nrs", "decision_reasons", "counter_offer"],
}


def summarise(node: str, update: Dict[str, Any]) -> Dict[str, Any]:
    out = {k: update.get(k) for k in SUMMARY_KEYS.get(node, []) if k in update}
    if node == "compliance_node" and "compliance_result" in update:
        out["rule_traces"] = [
            {k: t.get(k) for k in ("rule_id", "triggered", "applicable", "action", "observed", "threshold", "provenance")}
            for t in update["compliance_result"].get("rule_traces", [])
        ]
    if node == "decision_node" and isinstance(update.get("final_output"), dict):
        fo = update["final_output"]
        out.update({k: fo.get(k) for k in ("policy_version", "model_version", "income_flags", "not_screened")})
    if node == "scoring_node" and isinstance(out.get("scorecard"), dict):
        sc = out["scorecard"]
        out["scorecard"] = {k: sc.get(k) for k in ("status", "pd", "credit_score", "risk_grade", "drivers", "model_version", "error")}
    return out
