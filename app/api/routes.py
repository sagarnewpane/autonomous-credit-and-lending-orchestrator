from typing import Annotated, List, Optional

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import LoanApplication, UploadedDocument

router = APIRouter(prefix="/api/v1/loan", tags=["api"])


# Home endpoint for the loan API
@router.get("/")
async def home():
    return {"message": "Hello!"}


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
    # Use this specific Annotated pattern:
    documents: Annotated[Optional[List[UploadFile]], File()] = None,
    db: Session = Depends(get_db),
):

    try:
        application = LoanApplication(
            applicant_name=applicant_name,
            user_id=user_id,
            loan_amount=loan_amount,
            loan_purpose=loan_purpose,
            monthly_income=monthly_income,
            monthly_debt=monthly_debt,
        )
        db.add(application)
        db.flush()  # assign application.id before commit
        assert application.id is not None  # Type assertion after flush

        saved_documents: list[UploadedDocument] = []
        if documents:
            for doc in documents:
                content = await doc.read()
                document = UploadedDocument(
                    application_id=application.id,
                    file_name=doc.filename or "unknown",
                    content_type=doc.content_type,
                    file_size_bytes=len(content),
                )
                db.add(document)
                saved_documents.append(document)
                await doc.close()

        db.commit()
        db.refresh(application)

        return {
            "message": "Loan application submitted successfully!",
            "application": {
                "id": application.id,
                "applicant_name": application.applicant_name,
                "user_id": application.user_id,
                "loan_amount": application.loan_amount,
                "loan_purpose": application.loan_purpose,
                "tenure_months": tenure_months,
                "monthly_income": application.monthly_income,
                "monthly_debt": application.monthly_debt,
                "created_at": application.created_at.isoformat(),
                "updated_at": application.updated_at.isoformat(),
            },
            "uploaded_documents": [
                {
                    "id": d.id,
                    "file_name": d.file_name,
                    "content_type": d.content_type,
                    "file_size_bytes": d.file_size_bytes,
                    "uploaded_at": d.uploaded_at.isoformat(),
                }
                for d in saved_documents
            ],
        }
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to persist loan application: {str(exc)}",
        ) from exc



# Endpoint for getting the loan decision decided by the system
@router.get("/decision/{application_id}")
async def get_decision(application_id: str):
    return {"message": f"Loan decision for application {application_id}"}


# Endpoint for returning the explainability on the decision
@router.get("/explain/{application_id}")
async def explain_decision(application_id: str):
    return {
        "application_id": application_id,
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
    return {
        "user_id": user_id,
        "applications": [],
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


# Endpoint for Admin to view all loans
@router.get("/loans")
async def get_all_loans(db: Session = Depends(get_db)):
    try:
        loans = db.query(LoanApplication).all()
        result = []
        for loan in loans:
            result.append(
                {
                    "id": loan.id,
                    "applicant_name": loan.applicant_name,
                    "user_id": loan.user_id,
                    "loan_amount": loan.loan_amount,
                    "loan_purpose": loan.loan_purpose,
                    "monthly_income": loan.monthly_income,
                    "monthly_debt": loan.monthly_debt,
                    "created_at": loan.created_at.isoformat(),
                    "updated_at": loan.updated_at.isoformat(),
                    "documents": [
                        {
                            "id": d.id,
                            "file_name": d.file_name,
                            "content_type": d.content_type,
                            "file_size_bytes": d.file_size_bytes,
                            "uploaded_at": d.uploaded_at.isoformat(),
                        }
                        for d in loan.documents
                    ],
                }
            )
        return {
            "applications": result,
            "message": "All loan applications fetched for admin dashboard.",
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch loan applications: {str(exc)}",
        ) from exc


# Endpoint for Admin Review (Human-in-the-loop)
@router.patch("/admin/review/{application_id}")
async def admin_review(
    application_id: str,
    payload: dict = Body(default={}),
):
    return {
        "application_id": application_id,
        "review_payload": payload,
        "message": "Admin review recorded successfully.",
    }
