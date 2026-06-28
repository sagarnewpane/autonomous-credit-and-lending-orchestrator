from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Body, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from app.db.supabase import supabase

# Prefix for the endpoint for the API
router = APIRouter(prefix="/api/v1/loan", tags=["api"])


# Home endpoint for the loan API
@router.get("/")
async def home():
    try:
        supabase.table("loan_applications").select("application_id").limit(1).execute()
        return {"message": "System all Okay!", "database": "connected"}
    except Exception:
        raise HTTPException(status_code=503, detail="Database connection failed")


# Endpoint for applying a loan
@router.post("/apply")
async def apply_loan(
    applicant_name: str = Form(...),
    user_id: str = Form(...),
    loan_amount: float = Form(...),
    loan_purpose: str = Form(...),
    tenure_months: int = Form(...),
    monthly_income: float = Form(...),
    monthly_debt: float = Form(...),
    collateral_type: float = Form(...),
    cooperative_member: bool = Form(...), 
    documents: Annotated[Optional[List[UploadFile]], File()] = None,
):
    try:
        import uuid
        application_id = f"LA-{uuid.uuid4().hex[:8].upper()}"

        application_data = {
            "application_id": application_id,
            "applicant_id": user_id,
            "loan_purpose": loan_purpose,
            "requested_amount_nrs": loan_amount,
            "requested_tenure_months": tenure_months,
            "income_agent_monthly_est": monthly_income,
            "collateral_type": collateral_type,
            "cooperative_member": cooperative_member,
        }

        supabase.table("loan_applications").insert(application_data).execute()

        # TODO - store the uploaded files properly
        

        return {
            "message": "Loan application submitted successfully!",
            "application": {
                "application_id": application_id,
                "applicant_name": applicant_name,
                "user_id": user_id,
                "loan_amount": loan_amount,
                "loan_purpose": loan_purpose,
                "tenure_months": tenure_months,
                "monthly_income": monthly_income,
                "monthly_debt": monthly_debt,
            },
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to persist loan application: {str(exc)}",
        ) from exc


# Endpoint for getting the loan decision
@router.get("/decision/{application_id}")
async def get_decision(application_id: str):
    result = supabase.table("loan_applications").select("*").eq("application_id", application_id).execute()

    if not result.data:
        raise HTTPException(status_code=404, detail=f"Application {application_id} not found")

    app_data = result.data[0]
    return {
        "application_id": application_id,
        "decision": app_data.get("final_decision") or "PENDING",
        "approved_amount_npr": app_data.get("approved_amount_nrs"),
        "credit_score": app_data.get("credit_score"),
        "score_band": app_data.get("score_band"),
        "risk_tier": app_data.get("interest_tier"),
    }


# Endpoint for returning the explainability on the decision
@router.get("/explain/{application_id}")
async def explain_decision(application_id: str):
    result = supabase.table("loan_applications").select("*").eq("application_id", application_id).execute()

    if not result.data:
        raise HTTPException(status_code=404, detail=f"Application {application_id} not found")

    app_data = result.data[0]
    return {
        "application_id": application_id,
        "credit_score": app_data.get("credit_score"),
        "score_band": app_data.get("score_band"),
        "decision": app_data.get("final_decision") or "PENDING",
        "compliance_status": app_data.get("compliance_status"),
        "compliance_flags": app_data.get("compliance_flags", "[]"),
    }


# Endpoint for Document Re-upload / Correction
@router.put("/docs/{application_id}")
async def reupload_documents(
    application_id: str,
    files: Annotated[list[UploadFile], File(..., description="Files to re-upload")],
):
    return {
        "application_id": application_id,
        "uploaded_files": [f.filename for f in files],
        "message": "Documents received for re-validation.",
    }


# Endpoint for User Loan History
@router.get("/user/{user_id}")
async def get_user_loan_history(user_id: str):
    result = supabase.table("loan_applications").select("*").eq("applicant_id", user_id).execute()

    return {
        "user_id": user_id,
        "applications": result.data,
        "message": "User loan history fetched successfully.",
    }


# Endpoint for Compliance Reference Fetcher
@router.get("/compliance/references/{application_id}")
async def get_compliance_references(application_id: str):
    return {
        "application_id": application_id,
        "references": [
            {
                "clause": "NRB Unified Directive 5.2",
                "text": "Banks must ensure DSR does not exceed 50%...",
                "relevance_score": 0.91,
            }
        ],
    }

