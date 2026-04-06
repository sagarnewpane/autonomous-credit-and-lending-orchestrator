from fastapi import APIRouter, Body, File, UploadFile

router = APIRouter(prefix="/api/v1/loan", tags=["api"])


# Home endpoint for the loan API
@router.get("/")
async def home():
    return {"message": "Hello!"}


# Endpoint for applying a loan
@router.post("/apply")
async def apply_loan():
    return {"message": "Loan application submitted successfully!"}


# Endpoint for getting the loan decision decsided by the system
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
    files: list[UploadFile] = File(default=[]),
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
async def get_all_loans():
    return {
        "applications": [],
        "message": "All loan applications fetched for admin dashboard.",
    }


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
