from fastapi import APIRouter, Body, Depends, HTTPException
import sys
from pathlib import Path

from app.api.auth_dependencies.dependencies import get_current_admin_user

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.db.supabase import supabase

admin_router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@admin_router.get("/loans")
async def get_all_loans(
    admin: dict = Depends(get_current_admin_user),
):
    try:
        result = supabase.table("loan_applications").select("*").execute()
        return {
            "applications": result.data,
            "message": "All loan applications fetched for admin dashboard.",
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch loan applications: {str(exc)}",
        ) from exc


@admin_router.patch("/review/{application_id}")
async def admin_review(
    application_id: str,
    payload: dict = Body(default={}),
    admin: dict = Depends(get_current_admin_user),
):
    try:
        supabase.table("loan_applications").update(payload).eq("application_id", application_id).execute()
        return {
            "application_id": application_id,
            "review_payload": payload,
            "message": "Admin review recorded successfully.",
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update review: {str(exc)}",
        ) from exc


@admin_router.get("/audit/{application_id}")
async def audit_trail(
    application_id: str,
    admin: dict = Depends(get_current_admin_user),
):
    return {
        "message": f"Audit Trail for {application_id}"
    }
