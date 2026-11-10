import csv
import io
import logging
from datetime import datetime
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from app.api.auth_dependencies.dependencies import get_current_admin_user
from app.middleware.security import log_admin_action

from app.db import db

logger = logging.getLogger("admin")
admin_router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

# ── Field Allowlists ──────────────────────────────────────────────────────
LOAN_UPDATE_FIELDS = {
    "final_decision", "approved_amount_nrs", "interest_rate_pct",
    "officer_notes", "requested_tenure_months", "collateral_type",
    "loan_purpose", "requested_amount_nrs", "compliance_status",
    "compliance_flags",
}

USER_UPDATE_FIELDS = {"is_admin", "is_active"}

VALID_DECISIONS = {"APPROVE", "MODIFY", "REJECT", "MANUAL_REVIEW", "PENDING"}


def _validate_decision(value: str) -> str:
    if value not in VALID_DECISIONS:
        raise HTTPException(status_code=400, detail=f"Invalid decision. Must be one of: {', '.join(VALID_DECISIONS)}")
    return value


# ---------------------------------------------------------------------------
# Dashboard Statistics
# ---------------------------------------------------------------------------
@admin_router.get("/stats")
def get_admin_stats(
    admin: dict = Depends(get_current_admin_user),
):
    try:
        stats_row = db.raw("""
            SELECT
                COUNT(*)::int AS total,
                COUNT(*) FILTER (WHERE final_decision = 'APPROVE')::int AS approved,
                COUNT(*) FILTER (WHERE final_decision = 'REJECT')::int AS rejected,
                COUNT(*) FILTER (WHERE final_decision IS NULL OR final_decision = 'PENDING')::int AS pending,
                COUNT(*) FILTER (WHERE compliance_status = 'flag')::int AS flagged,
                COUNT(*) FILTER (WHERE final_decision = 'MODIFY')::int AS modified,
                COUNT(*) FILTER (WHERE final_decision = 'MANUAL_REVIEW')::int AS manual,
                COALESCE(SUM(requested_amount_nrs), 0)::numeric AS total_requested,
                COALESCE(SUM(approved_amount_nrs) FILTER (WHERE final_decision = 'APPROVE'), 0)::numeric AS total_approved_amount,
                COALESCE(ROUND(AVG(credit_score) FILTER (WHERE credit_score IS NOT NULL), 1), 0)::numeric AS avg_score
            FROM loan_applications
        """)[0]

        total = stats_row["total"]
        approved = stats_row["approved"]
        rejected = stats_row["rejected"]
        pending = stats_row["pending"]
        flagged = stats_row["flagged"]
        modified = stats_row["modified"]
        manual = stats_row["manual"]

        recent = db.raw(
            "SELECT application_id, applicant_id, loan_purpose, requested_amount_nrs, "
            "credit_score, final_decision, compliance_status, application_date_ad "
            "FROM loan_applications ORDER BY application_date_ad DESC LIMIT 10"
        )

        return {
            "total_applications": total,
            "approved": approved,
            "rejected": rejected,
            "pending": pending,
            "flagged": flagged,
            "modified": modified,
            "manual_review": manual,
            "total_requested_amount": float(stats_row["total_requested"]),
            "total_approved_amount": float(stats_row["total_approved_amount"]),
            "average_credit_score": float(stats_row["avg_score"]),
            "approval_rate": round((approved / total * 100), 1) if total > 0 else 0,
            "decision_distribution": {
                "APPROVE": approved,
                "REJECT": rejected,
                "PENDING": pending,
                "MODIFY": modified,
                "MANUAL_REVIEW": manual,
            },
            "recent_activity": recent,
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to fetch admin stats")
        raise HTTPException(status_code=500, detail="Failed to fetch admin statistics")


# ---------------------------------------------------------------------------
# Loan Applications
# ---------------------------------------------------------------------------
LOAN_LIST_COLUMNS = (
    "application_id, applicant_id, loan_purpose, requested_amount_nrs, "
    "requested_tenure_months, credit_score, score_band, interest_tier, "
    "final_decision, compliance_status, application_date_ad"
)


@admin_router.get("/loans")
def get_all_loans(
    status: str = Query(None, description="Filter by status: approve, reject, pending, flag, modify"),
    search: str = Query(None, description="Search by application_id or applicant_id"),
    admin: dict = Depends(get_current_admin_user),
):
    try:
        where_parts = []
        params = []

        if status:
            status_lower = status.lower()
            if status_lower == "pending":
                where_parts.append("(final_decision IS NULL OR final_decision = 'PENDING')")
            elif status_lower == "approve":
                where_parts.append("final_decision = 'APPROVE'")
            elif status_lower == "reject":
                where_parts.append("final_decision = 'REJECT'")
            elif status_lower == "flag":
                where_parts.append("compliance_status = 'flag'")
            elif status_lower == "modify":
                where_parts.append("final_decision = 'MODIFY'")

        if search:
            where_parts.append(
                "(LOWER(application_id) LIKE %s OR LOWER(applicant_id) LIKE %s)"
            )
            sl = f"%{search.lower()}%"
            params.extend([sl, sl])

        where_clause = (" WHERE " + " AND ".join(where_parts)) if where_parts else ""

        sql = (
            f"SELECT {LOAN_LIST_COLUMNS} FROM loan_applications"
            f"{where_clause} ORDER BY application_date_ad DESC"
        )

        apps = db.raw(sql, params)

        return {
            "applications": apps,
            "total": len(apps),
            "message": "All loan applications fetched for admin dashboard.",
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to fetch loan applications")
        raise HTTPException(status_code=500, detail="Failed to fetch loan applications")


@admin_router.get("/loans/export/csv")
def export_loans_csv(
    status: str = Query(None),
    admin: dict = Depends(get_current_admin_user),
):
    try:
        where_clause = ""
        params = []

        if status:
            status_lower = status.lower()
            if status_lower == "pending":
                where_clause = " WHERE final_decision IS NULL OR final_decision = 'PENDING'"
            elif status_lower == "approve":
                where_clause = " WHERE final_decision = 'APPROVE'"
            elif status_lower == "reject":
                where_clause = " WHERE final_decision = 'REJECT'"

        sql = f"SELECT * FROM loan_applications{where_clause} ORDER BY application_date_ad DESC"
        apps = db.raw(sql, params)

        output = io.StringIO()
        if apps:
            writer = csv.DictWriter(output, fieldnames=list(apps[0].keys()))
            writer.writeheader()
            writer.writerows(apps)
        else:
            output.write("No data")

        output.seek(0)
        log_admin_action(admin["id"], "EXPORT_CSV", "loan_applications", f"status={status}")
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=loans_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            },
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to export loans")
        raise HTTPException(status_code=500, detail="Failed to export data")


@admin_router.get("/loans/{application_id}")
def get_loan_detail(
    application_id: str,
    admin: dict = Depends(get_current_admin_user),
):
    try:
        result = db.table("loan_applications").select("*").eq("application_id", application_id).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Application not found")

        return {
            "application": result.data[0],
            "message": "Application details fetched.",
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to fetch application")
        raise HTTPException(status_code=500, detail="Failed to fetch application details")


@admin_router.patch("/loans/{application_id}")
def update_loan_application(
    application_id: str,
    payload: dict = Body(default={}),
    admin: dict = Depends(get_current_admin_user),
):
    try:
        result = db.table("loan_applications").select("*").eq("application_id", application_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Application not found")

        # Validate and filter with allowlist
        filtered = {}
        for k, v in payload.items():
            if k in LOAN_UPDATE_FIELDS:
                if k == "final_decision":
                    filtered[k] = _validate_decision(v)
                else:
                    filtered[k] = v

        if not filtered:
            raise HTTPException(status_code=400, detail="No valid fields to update")

        db.table("loan_applications").eq("application_id", application_id).update(filtered)
        log_admin_action(admin["id"], "UPDATE_LOAN", application_id, f"fields={list(filtered.keys())}")

        return {
            "application_id": application_id,
            "updated_fields": filtered,
            "message": "Application updated successfully.",
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to update application")
        raise HTTPException(status_code=500, detail="Failed to update application")


@admin_router.patch("/review/{application_id}")
def admin_review(
    application_id: str,
    payload: dict = Body(default={}),
    admin: dict = Depends(get_current_admin_user),
):
    try:
        result = db.table("loan_applications").select("*").eq("application_id", application_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Application not found")

        # Apply field allowlist (same as update endpoint)
        filtered = {}
        for k, v in payload.items():
            if k in LOAN_UPDATE_FIELDS:
                if k == "final_decision":
                    filtered[k] = _validate_decision(v)
                else:
                    filtered[k] = v

        if not filtered:
            raise HTTPException(status_code=400, detail="No valid fields to update")

        db.table("loan_applications").eq("application_id", application_id).update(filtered)
        log_admin_action(admin["id"], "REVIEW_LOAN", application_id, f"fields={list(filtered.keys())}")

        return {
            "application_id": application_id,
            "review_payload": filtered,
            "message": "Admin review recorded successfully.",
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to update review")
        raise HTTPException(status_code=500, detail="Failed to record review")


@admin_router.patch("/loans/bulk")
def bulk_update_loans(
    payload: dict = Body(default={}),
    admin: dict = Depends(get_current_admin_user),
):
    try:
        application_ids = payload.get("application_ids", [])
        updates = payload.get("updates", {})

        if not application_ids or not updates:
            raise HTTPException(status_code=400, detail="application_ids and updates are required")

        if not isinstance(application_ids, list) or len(application_ids) > 100:
            raise HTTPException(status_code=400, detail="Must provide 1-100 application IDs")

        # Apply field allowlist to bulk updates
        filtered = {}
        for k, v in updates.items():
            if k in LOAN_UPDATE_FIELDS:
                if k == "final_decision":
                    filtered[k] = _validate_decision(v)
                else:
                    filtered[k] = v

        if not filtered:
            raise HTTPException(status_code=400, detail="No valid fields to update")

        count = 0
        for app_id in application_ids:
            db.table("loan_applications").eq("application_id", app_id).update(filtered)
            count += 1

        log_admin_action(admin["id"], "BULK_UPDATE_LOAN", f"{count} apps", f"fields={list(filtered.keys())}")

        return {
            "updated_count": count,
            "updates": filtered,
            "message": f"Successfully updated {count} applications.",
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to bulk update")
        raise HTTPException(status_code=500, detail="Failed to perform bulk update")


# ---------------------------------------------------------------------------
# User Management
# ---------------------------------------------------------------------------
@admin_router.get("/users")
def get_all_users(
    search: str = Query(None),
    admin: dict = Depends(get_current_admin_user),
):
    try:
        where_clause = ""
        params = []

        if search:
            where_clause = " WHERE LOWER(email) LIKE %s OR LOWER(id::text) LIKE %s"
            sl = f"%{search.lower()}%"
            params.extend([sl, sl])

        sql = (
            f"SELECT id, email, is_admin, is_active, created_at FROM users"
            f"{where_clause} ORDER BY created_at DESC"
        )

        users = db.raw(sql, params)

        return {
            "users": users,
            "total": len(users),
            "message": "All users fetched.",
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to fetch users")
        raise HTTPException(status_code=500, detail="Failed to fetch users")


@admin_router.get("/users/{user_id}")
def get_user_detail(
    user_id: str,
    admin: dict = Depends(get_current_admin_user),
):
    try:
        result = db.table("users").select("*").eq("id", user_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="User not found")

        user = result.data[0]

        loans_result = (
            db.table("loan_applications")
            .select("*")
            .eq("applicant_id", user.get("applicant_id", ""))
            .order("created_at", desc=True)
            .execute()
        )

        return {
            "user": user,
            "loan_applications": loans_result.data,
            "message": "User details fetched.",
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to fetch user detail")
        raise HTTPException(status_code=500, detail="Failed to fetch user details")


@admin_router.patch("/users/{user_id}")
def update_user(
    user_id: str,
    payload: dict = Body(default={}),
    admin: dict = Depends(get_current_admin_user),
):
    try:
        result = db.table("users").select("*").eq("id", user_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="User not found")

        # Prevent self-demotion
        if str(admin["id"]) == str(user_id):
            raise HTTPException(status_code=400, detail="Cannot modify your own admin status")

        filtered = {}
        for k, v in payload.items():
            if k in USER_UPDATE_FIELDS:
                filtered[k] = bool(v)

        if not filtered:
            raise HTTPException(status_code=400, detail="No valid fields to update")

        db.table("users").eq("id", user_id).update(filtered)
        log_admin_action(admin["id"], "UPDATE_USER", user_id, f"fields={list(filtered.keys())}")

        return {
            "user_id": user_id,
            "updated_fields": filtered,
            "message": "User updated successfully.",
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to update user")
        raise HTTPException(status_code=500, detail="Failed to update user")


# ---------------------------------------------------------------------------
# Audit Trail
# ---------------------------------------------------------------------------
@admin_router.get("/audit/{application_id}")
def audit_trail(
    application_id: str,
    admin: dict = Depends(get_current_admin_user),
):
    """
    Entries written by the pipeline for this application (app/services/audit.py), with a
    check of the whole hash chain. Nothing here is reconstructed or defaulted: if a stage
    did not run, it has no entry.
    """
    try:
        from app.services import audit

        result = db.table("loan_applications").select("application_id").eq("application_id", application_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Application not found")
        names = {"income_node": "Income Agent", "compliance_node": "Compliance Agent",
                 "scoring_node": "Score Agent", "decision_node": "Decision Agent"}
        entries = audit.read(application_id)
        logs = [{
            "id": e["seq"],
            "agent": names.get(e["agent"], e["agent"]),
            "timestamp": e["ts"],
            "output": e["payload"],
            "hash": e["hash"],
            "prev_hash": e["prev_hash"],
        } for e in entries]
        return {
            "application_id": application_id,
            "audit_logs": logs,
            "chain_check": audit.verify(),
            "message": f"Audit trail for {application_id}" if logs else "No audit entries recorded for this application.",
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to fetch audit trail")
        raise HTTPException(status_code=500, detail="Failed to fetch audit trail")
