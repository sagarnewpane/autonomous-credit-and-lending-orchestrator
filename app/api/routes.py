from typing import Annotated, Any, Dict, Optional
import os
import uuid
import shutil
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from app.db import db
from app.api.auth_dependencies.dependencies import get_current_user
from datetime import date
from app.services.date_utils import bs_to_ad, ad_to_bs

logger = logging.getLogger("routes")

router = APIRouter(prefix="/api/v1/loan", tags=["api"])

# Nepali → English occupation mapping
OCCUPATION_NP_TO_EN: dict[str, str] = {
    "किसान": "Farmer",
    "दैनिक ज्याला मजदुर": "Daily Wage Worker",
    "सानो व्यापारी": "Small Trader",
    "सेवा कर्मचारी": "Service Worker",
    "रेमिट्यान्स निर्भर": "Remittance Dependent",
    "कारीगर": "Artisan",
    "सरकारी कर्मचारी": "Government Employee",
    "व्यवसायी": "Business Owner",
    "शिक्षक": "Teacher",
    "चालक": "Driver",
    "नर्स/स्वास्थ्य कर्मचारी": "Nurse/Health Worker",
    "किसानी": "Farmer",
    "मजदुर": "Daily Wage Worker",
    "व्यापार": "Small Trader",
    "सरकारी जागिर": "Government Employee",
    "निजी क्षेत्र": "Service Worker",
    "शिक्षण": "Teacher",
    "स्वास्थ्य": "Nurse/Health Worker",
    "पशुपालन": "Farmer",
    "सिँचाइ": "Farmer",
    "कृषि": "Farmer",
}

# doc_type -> form field name, used to drive both saving and registry inserts
DOCUMENT_FIELDS = [
    "citizenship",
    "kyc_form",
    "bank_statement",
    "lalpurja",
    "utility_bill",
    "cooperative",
    "remittance",
]

# ── Input Validation Helpers ──────────────────────────────────────────────
_MAX_STRING_LENGTH = 255
_MAX_AMOUNT = 100_000_000  # 100 million NPR
_MIN_AMOUNT = 1_000
_MAX_TENURE = 360  # 30 years
_MIN_TENURE = 1
_MAX_HOUSEHOLD = 50


def _validate_string(value: str, field_name: str, max_length: int = _MAX_STRING_LENGTH) -> str:
    """Sanitize and validate string input."""
    value = value.strip()
    if len(value) > max_length:
        raise HTTPException(status_code=400, detail=f"{field_name} exceeds maximum length of {max_length}")
    return value


def _validate_amount(value: float, field_name: str) -> float:
    """Validate numeric amount."""
    if value < 0:
        raise HTTPException(status_code=400, detail=f"{field_name} cannot be negative")
    if value > _MAX_AMOUNT:
        raise HTTPException(status_code=400, detail=f"{field_name} exceeds maximum allowed value")
    return value


@router.get("/")
def home():
    try:
        db.table("loan_applications").select("application_id").limit(1).execute()
        return {"message": "System all Okay!", "database": "connected"}
    except Exception:
        raise HTTPException(status_code=503, detail="Database connection failed")


# ── Helpers ──────────────────────────────────────────────────────────────

def _drop_empty(d: Dict[str, Any]) -> Dict[str, Any]:
    """Keep only truthy values (mirrors the old 'optional fields' filtering)."""
    return {k: v for k, v in d.items() if v not in (None, "")}


def _run_pipeline(applicant_id: str, application_id: str, fields: Dict[str, Any]) -> Dict[str, Any]:
    """Runs the LangGraph pipeline; falls back to a manual-review response on failure."""
    logger.info(f"Pipeline START | applicant={applicant_id} | application={application_id}")
    try:
        from app.agents.pipeline import build_test_workflow

        workflow = build_test_workflow()
        initial_state = {
            "applicant_id": applicant_id,
            "application_id": application_id,
            "loan_request": fields,
        }
        final_state = workflow.invoke(initial_state)
        logger.info(f"Pipeline complete | decision={final_state.get('final_decision')}")

        # === SAVE ALL RESULTS TO loan_applications ===
        scorecard = final_state.get("scorecard", {})
        update_data = {
            "income_agent_monthly_est": final_state.get("income_agent_monthly_est"),
            "income_confidence": final_state.get("income_confidence"),
            "credit_score": scorecard.get("credit_score"),
            "score_band": scorecard.get("score_band"),
            "compliance_status": final_state.get("compliance_status"),
            "compliance_flags": final_state.get("compliance_flags"),
            "final_decision": final_state.get("final_decision"),
            "approved_amount_nrs": final_state.get("approved_amount_nrs"),
            "interest_tier": final_state.get("interest_tier"),
            "interest_rate_pct": final_state.get("interest_rate_pct"),
            "decision_reason": final_state.get("decision_reason"),
        }
        # Filter out None values
        update_data = {k: v for k, v in update_data.items() if v is not None}

        try:
            db.table("loan_applications") \
                .eq("application_id", application_id) \
                .update(update_data)
        except Exception:
            logger.exception("Failed to save pipeline results")

        return {
            "message": "Application processed successfully.",
            "application_id": application_id,
            "applicant_id": applicant_id,
            "final_decision": final_state.get("final_decision"),
            "credit_score": scorecard.get("credit_score"),
            "approved_amount": final_state.get("approved_amount_nrs"),
            "interest_tier": final_state.get("interest_tier"),
            "decision_reason": final_state.get("decision_reason"),
        }
    except Exception:
        logger.exception("Pipeline error")
        return {
            "message": "Loan application submitted (pipeline error - manual review needed).",
            "application_id": application_id,
            "applicant_id": applicant_id,
            "application": {
                "application_id": application_id,
                "applicant_id": applicant_id,
                "requested_amount_nrs": fields.get("amount"),
                "loan_purpose": fields.get("loan_purpose"),
                "requested_tenure_months": fields.get("tenure_months"),
            },
        }


# ── Endpoint ─────────────────────────────────────────────────────────────

@router.post("/apply")
def apply_loan(
    current_user: dict = Depends(get_current_user),
    full_name_en: str = Form(...),
    father_name_en: str = Form(...),
    grandfather_name_en: str = Form(...),
    gender: str = Form(...),
    marital_status: str = Form(...),
    citizenship_number: str = Form(...),
    citizenship_issue_date_bs: str = Form(""),
    citizenship_office: str = Form(""),
    dob_ad: str = Form(...),
    dob_bs: str = Form(...),
    province_en: str = Form(""),
    district_en: str = Form(""),
    municipality_en: str = Form(""),
    ward_no: str = Form(""),
    phone_primary: str = Form(...),
    occupation_en: str = Form(...),
    occupation_np: str = Form(""),
    education_level: str = Form(...),
    household_size: int = Form(...),
    has_esewa_account: bool = Form(False),
    esewa_account_id: str = Form(""),
    has_khalti_account: bool = Form(False),
    khalti_account_id: str = Form(""),
    primary_bank: str = Form(...),
    receives_remittance: bool = Form(False),
    cooperative_member: bool = Form(False),
    cooperative_id: str = Form(""),
    land_area_ropani: float = Form(0),
    loan_purpose: str = Form(...),
    requested_amount_nrs: float = Form(...),
    requested_tenure_months: int = Form(...),
    collateral_type: str = Form(...),
    collateral_value_nrs: float = Form(...),
    existing_loan_amount: float = Form(0),
    credit_bureau_score: str = Form(""),
    aml_flag: bool = Form(False),
    nrb_blacklist_flag: bool = Form(False),
):
    try:
        # Validate inputs
        full_name_en = _validate_string(full_name_en, "Full name")
        citizenship_number = _validate_string(citizenship_number, "Citizenship number")
        requested_amount_nrs = _validate_amount(requested_amount_nrs, "Loan amount")
        collateral_value_nrs = _validate_amount(collateral_value_nrs, "Collateral value")

        if requested_amount_nrs < _MIN_AMOUNT:
            raise HTTPException(status_code=400, detail=f"Loan amount must be at least NPR {_MIN_AMOUNT:,}")
        if requested_tenure_months < _MIN_TENURE or requested_tenure_months > _MAX_TENURE:
            raise HTTPException(status_code=400, detail=f"Tenure must be between {_MIN_TENURE} and {_MAX_TENURE} months")
        if household_size < 1 or household_size > _MAX_HOUSEHOLD:
            raise HTTPException(status_code=400, detail=f"Household size must be between 1 and {_MAX_HOUSEHOLD}")

        applicant_id = current_user.get("applicant_id")
        if not applicant_id:
            applicant_id = f"AP-{uuid.uuid4().hex[:8].upper()}"
            db.table("users").eq("id", current_user["id"]).update({"applicant_id": applicant_id})

        # Check if user already has an active (pending) application
        active_apps = db.table("loan_applications") \
            .select("application_id") \
            .eq("applicant_id", applicant_id) \
            .is_null("final_decision") \
            .limit(1) \
            .execute().data
        if active_apps:
            raise HTTPException(
                status_code=409,
                detail="You already have an active application. Please wait for it to be approved or rejected before applying again."
            )

        resolved_occupation_en = occupation_en or OCCUPATION_NP_TO_EN.get(occupation_np, occupation_np)

        # 1. Upsert applicant profile
        profile_data = {
            "applicant_id": applicant_id,
            "full_name_en": full_name_en,
            "citizenship_number": citizenship_number,
            "phone_primary": phone_primary,
            "gender": gender,
            "dob_ad": dob_ad,
            "dob_bs": dob_bs,
            "father_name_en": father_name_en,
            "grandfather_name_en": grandfather_name_en,
            "marital_status": marital_status,
            "occupation_en": resolved_occupation_en,
            "education_level": education_level,
            "household_size": int(household_size),
            "land_area_ropani": float(land_area_ropani),
            "has_esewa_account": bool(has_esewa_account),
            "has_khalti_account": bool(has_khalti_account),
            "primary_bank": primary_bank,
            "remittance_receiving": bool(receives_remittance),
            "cooperative_member": bool(cooperative_member),
            **_drop_empty({
                "occupation_np": occupation_np,
                "esewa_account_id": esewa_account_id,
                "khalti_account_id": khalti_account_id,
                "cooperative_id": cooperative_id,
                "province_en": province_en,
                "district_en": district_en,
                "municipality_en": municipality_en,
                "ward_no": int(ward_no) if ward_no else None,
                "citizenship_date_bs": citizenship_issue_date_bs,
                "citizenship_office": citizenship_office,
            }),
        }

        profile_exists = db.table("applicant_profiles") \
            .select("applicant_id").eq("applicant_id", applicant_id).execute().data
        if profile_exists:
            db.table("applicant_profiles").eq("applicant_id", applicant_id).update(profile_data)
        else:
            db.table("applicant_profiles").insert(profile_data)

        saved_profile = db.table("applicant_profiles") \
            .select("*").eq("applicant_id", applicant_id).limit(1).execute().data[0]

        # 2. Always create a new application_id for each application
        application_id = f"LA-{uuid.uuid4().hex[:8].upper()}"

        # 3. Create loan application record
        application_data = {
            "application_id": application_id,
            "applicant_id": applicant_id,
            "application_date_ad":  str(date.today()),
            "application_date_bs": ad_to_bs(str(date.today())),
            "loan_purpose": loan_purpose,
            "requested_amount_nrs": float(requested_amount_nrs),
            "requested_tenure_months": int(requested_tenure_months),
            "collateral_type": collateral_type,
            "collateral_value_nrs": float(collateral_value_nrs),
            "has_esewa_account": saved_profile.get("has_esewa_account", False),
            "has_khalti_account": saved_profile.get("has_khalti_account", False),
            "remittance_receiving": saved_profile.get("remittance_receiving", False),
            "cooperative_member": saved_profile.get("cooperative_member", False),
            "cooperative_id": saved_profile.get("cooperative_id"),
            "province_en": saved_profile.get("province_en"),
            "district_en": saved_profile.get("district_en"),
            "municipality_en": saved_profile.get("municipality_en"),
            "ward_no": saved_profile.get("ward_no"),
            **_drop_empty({
                "existing_loan_count": float(existing_loan_amount),
                "credit_bureau_score": float(credit_bureau_score) if credit_bureau_score else None,
                "aml_flag": str(aml_flag).lower(),
                "nrb_blacklist_flag": str(nrb_blacklist_flag).lower(),
            }),
        }
        db.table("loan_applications").insert(application_data)

        # 4. Run the AI pipeline (falls back gracefully on failure)
        pipeline_fields = {
            "amount": requested_amount_nrs,
            "tenure_months": requested_tenure_months,
            "collateral_value_nrs": collateral_value_nrs,
            "existing_liabilities_monthly": existing_loan_amount,
            "loan_purpose": loan_purpose,
        }
        return _run_pipeline(applicant_id, application_id, pipeline_fields)

    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to process application")
        raise HTTPException(status_code=500, detail="Failed to process application. Please try again later.")


@router.get("/decision/{application_id}")
def get_decision(
    application_id: str,
    current_user: dict = Depends(get_current_user),
):
    result = db.table("loan_applications").select("*").eq("application_id", application_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Application not found")

    app_data = result.data[0]

    # Ownership check: users can only view their own applications unless admin
    if not current_user.get("is_admin") and app_data.get("applicant_id") != current_user.get("applicant_id"):
        raise HTTPException(status_code=403, detail="Access denied")

    return {
        "application_id": application_id,
        "decision": app_data.get("final_decision") or "PENDING",
        "approved_amount_npr": app_data.get("approved_amount_nrs"),
        "credit_score": app_data.get("credit_score"),
        "score_band": app_data.get("score_band"),
        "risk_tier": app_data.get("interest_tier"),
        "loan_purpose": app_data.get("loan_purpose"),
        "requested_amount_nrs": app_data.get("requested_amount_nrs"),
        "requested_tenure_months": app_data.get("requested_tenure_months"),
        "income_agent_monthly_est": app_data.get("income_agent_monthly_est"),
        "collateral_type": app_data.get("collateral_type"),
        "monthly_debt": app_data.get("monthly_debt"),
        "dsr": app_data.get("dsr"),
        "imr": app_data.get("income_mismatch_ratio"),
        "lti": app_data.get("loan_to_income"),
        "interest_rate": app_data.get("interest_rate"),
        "compliance_status": app_data.get("compliance_status"),
        "shap_features": app_data.get("shap_features"),
    }


@router.get("/explain/{application_id}")
def explain_decision(
    application_id: str,
    current_user: dict = Depends(get_current_user),
):
    result = db.table("loan_applications").select("*").eq("application_id", application_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Application not found")

    app_data = result.data[0]

    # Ownership check
    if not current_user.get("is_admin") and app_data.get("applicant_id") != current_user.get("applicant_id"):
        raise HTTPException(status_code=403, detail="Access denied")

    return {
        "application_id": application_id,
        "credit_score": app_data.get("credit_score"),
        "score_band": app_data.get("score_band"),
        "decision": app_data.get("final_decision") or "PENDING",
        "compliance_status": app_data.get("compliance_status"),
        "compliance_flags": app_data.get("compliance_flags", "[]"),
    }


@router.put("/docs/{application_id}")
def reupload_documents(
    application_id: str,
    files: Annotated[list[UploadFile], File(..., description="Files to re-upload")],
    current_user: dict = Depends(get_current_user),
):
    # Verify application exists and user owns it
    result = db.table("loan_applications").select("applicant_id").eq("application_id", application_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Application not found")

    app_data = result.data[0]
    if not current_user.get("is_admin") and app_data.get("applicant_id") != current_user.get("applicant_id"):
        raise HTTPException(status_code=403, detail="Access denied")

    # Validate file types and sizes
    allowed_types = {"image/jpeg", "image/png", "image/webp", "application/pdf", "text/csv", "text/plain"}
    max_size_mb = 10
    uploaded = []
    for f in files:
        if f.content_type and f.content_type not in allowed_types:
            raise HTTPException(status_code=400, detail=f"File type {f.content_type} is not allowed")
        if f.size and f.size > max_size_mb * 1024 * 1024:
            raise HTTPException(status_code=400, detail=f"File {f.filename} exceeds {max_size_mb}MB limit")
        uploaded.append(f.filename)

    return {
        "application_id": application_id,
        "uploaded_files": uploaded,
        "message": "Documents received for re-validation.",
    }


@router.get("/user/me")
def get_user_loan_history(current_user: dict = Depends(get_current_user)):
    applicant_id = current_user.get("applicant_id")
    if not applicant_id:
        return {"applicant_id": None, "applications": [], "message": "No applicant profile linked."}

    result = db.table("loan_applications").select("*").eq("applicant_id", applicant_id).execute()
    return {
        "applicant_id": applicant_id,
        "applications": result.data,
        "message": "User loan history fetched successfully.",
    }


@router.get("/profile/me")
def get_applicant_profile(current_user: dict = Depends(get_current_user)):
    applicant_id = current_user.get("applicant_id")
    if not applicant_id:
        return {"has_profile": False, "profile": None}

    result = db.table("applicant_profiles") \
        .select("*").eq("applicant_id", applicant_id).limit(1).execute()
    if not result.data:
        return {"has_profile": False, "profile": None}
    return {"has_profile": True, "profile": result.data[0]}


@router.get("/compliance/references/{application_id}")
def get_compliance_references(
    application_id: str,
    current_user: dict = Depends(get_current_user),
):
    # Verify application exists and user owns it
    result = db.table("loan_applications").select("applicant_id").eq("application_id", application_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Application not found")

    app_data = result.data[0]
    if not current_user.get("is_admin") and app_data.get("applicant_id") != current_user.get("applicant_id"):
        raise HTTPException(status_code=403, detail="Access denied")

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
