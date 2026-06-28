The document you are thinking of is called a **Backend Technical Specification (or Tech Spec / API Specification)**. It serves as the ultimate blueprint for the developers so they know exactly what to build, what tables to create, and how the security should work.

Here is the complete, detailed Backend Technical Specification for the Dhago project. You can save this as `BACKEND_SPEC.md` and hand it to your dev team.

---

# Dhago — Backend Technical Specification (Tech Spec)

## 1. System Overview
This document defines the technical architecture, API contracts, security implementations, and core business logic for the Dhago backend. It is built using **FastAPI**, **LangGraph** (for multi-agent orchestration), **PostgreSQL** (data), and **Redis** (session/cache).

---

## 2. Core Data Models (PostgreSQL Schema)

### 2.1 `loan_applications`
Stores the core state of an application.
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `application_id` | UUID | PK, Default `gen_random_uuid()` | Unique application identifier |
| `user_id` | UUID | FK -> `users.id` | Applicant reference |
| `applicant_name` | VARCHAR(255) | Not Null | Full name of applicant |
| `citizenship_number`| TEXT | Encrypted | AES-256 encrypted string |
| `requested_amount_npr`| INTEGER | Not Null | Requested loan amount |
| `requested_tenure_months`| INTEGER | Not Null | Requested tenure |
| `loan_purpose` | VARCHAR(50) | Not Null | Enum: agri, trade, education, etc. |
| `status` | VARCHAR(50) | Default `pending` | pending, processing, approved, rejected, manual_review |
| `final_decision` | JSONB | Nullable | Final decision payload from Decision Agent |
| `created_at` | TIMESTAMPTZ | Default `now()` | Application creation timestamp |

### 2.2 `audit_logs`
Immutable traceability table for NRB compliance.
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `log_id` | UUID | PK | Unique log ID |
| `application_id` | UUID | FK -> `loan_applications` | Related application |
| `agent_name` | VARCHAR(50) | Not Null | e.g., `document_agent`, `compliance_agent` |
| `action_performed` | TEXT | Not Null | Description of action taken |
| `agent_output` | JSONB | Not Null | Full JSON payload output by the agent |
| `timestamp` | TIMESTAMPTZ | Default `now()` | Action timestamp |
*(DB Trigger: `BLOCK UPDATE AND DELETE` on this table)*

---

## 3. API Specification

All endpoints are prefixed with `/api/v1`. All responses use standard HTTP status codes.

### 3.1 Authentication Endpoints

#### `POST /auth/login`
*   **Description:** Authenticates a user (loan officer/admin) and returns JWT tokens.
*   **Request Body:** `{"email": "string", "password": "string"}`
*   **Response (200 OK):**
```json
{
  "access_token": "eyJhbGci...",
  "refresh_token": "eyJhbGci...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

#### `POST /auth/refresh`
*   **Description:** Generates a new access token using a refresh token.
*   **Headers:** `Authorization: Bearer <refresh_token>`
*   **Response (200 OK):** `{ "access_token": "string", "token_type": "bearer" }`

---

### 3.2 Loan Application Endpoints

#### `POST /loan/apply`
*   **Description:** Submits a new loan application. Triggers the LangGraph pipeline. Requires `multipart/form-data`.
*   **Auth:** Optional (can be public for customer-facing apps, or Officer-level).
*   **Form Data:**
    *   `applicant_name` (string, required)
    *   `citizenship_number` (string, required)
    *   `requested_amount_npr` (int, required, range: 200000-50000000)
    *   `requested_tenure_months` (int, required, range: 6-360)
    *   `loan_purpose` (string, required)
    *   `citizenship_doc` (file, required, jpg/png/pdf)
    *   `bank_statement` (file, required, csv/pdf)
    *   `lalpurja_doc` (file, optional)
*   **Response (201 Created):**
```json
{
  "application_id": "uuid-string",
  "status": "processing",
  "message": "Application received. AI agents are processing the data."
}
```

#### `GET /loan/decision/{application_id}`
*   **Description:** Fetches the final credit decision.
*   **Auth Required:** Loan Officer, Admin, or Applicant.
*   **Response (200 OK):**
```json
{
  "application_id": "uuid-string",
  "decision": "APPROVE",
  "approved_amount_npr": 750000,
  "approved_tenure_months": 36,
  "credit_score": 742,
  "risk_tier": "LOW",
  "customer_explanation": {
    "en": "Approved for NPR 750,000 over 36 months. Strong income consistency was the key positive factor.",
    "ne": "तपाईंको आवेदन ३६ महिनाको लागि NPR ७,५०,००० मा स्वीकृत गरिएको छ।"
  }
}
```

#### `GET /loan/explain/{application_id}`
*   **Description:** Deep dive into AI reasoning (SHAP values, financial metrics).
*   **Auth Required:** Senior Officer, Compliance Officer.
*   **Response (200 OK):**
```json
{
  "credit_score": 742,
  "imr": 1.14,
  "dti": 0.34,
  "lti": 2.8,
  "shap_top_drivers": [
    { "feature": "weighted_stability_score", "shap_value": 48.2, "direction": "POSITIVE" },
    { "feature": "tax_trust_score", "shap_value": 31.7, "direction": "POSITIVE" }
  ],
  "compliance_flags": []
}
```

#### `GET /loan/audit/{application_id}`
*   **Description:** Returns the immutable audit trail for NRB inspection.
*   **Auth Required:** Compliance Officer, Admin.
*   **Response (200 OK):**
```json
{
  "application_id": "uuid-string",
  "logs": [
    {
      "agent_name": "document_agent",
      "action_performed": "OCR Extraction & Trust Scoring",
      "agent_output": { "doc_trust_score": 0.92 },
      "timestamp": "2026-06-26T12:00:00Z"
    },
    {
      "agent_name": "compliance_agent",
      "action_performed": "NRB Directive Check",
      "agent_output": { "status": "pass", "flags": [] },
      "timestamp": "2026-06-26T12:00:05Z"
    }
  ]
}
```

#### `PATCH /loan/admin/review/{application_id}`
*   **Description:** Human-in-the-loop override. Allows an officer to override an AI decision.
*   **Auth Required:** Senior Officer, Admin.
*   **Request Body:**
```json
{
  "override_decision": "APPROVE",
  "officer_notes": "Verified cooperative dividends manually. Approving full amount."
}
```
*   **Response (200 OK):** Returns the updated decision object.

---

## 4. Security Implementation Matrix

The backend must implement the following security controls via FastAPI Middleware and Dependencies.

| Control | Implementation Strategy |
|---------|-------------------------|
| **Access Control (RBAC)** | Create an `enum` of roles (`LOAN_OFFICER`, `SENIOR_OFFICER`, `COMPLIANCE_OFFICER`, `ADMIN`). Use FastAPI `Depends(get_current_user_with_role("SENIOR_OFFICER"))` on protected routes. |
| **Session Management** | Use `fastapi-jwt-auth` or custom JWT logic. Access Token TTL: 30 mins. Refresh Token TTL: 7 days. Store `jti` (JWT ID) in Redis upon logout to maintain a blacklist. |
| **Encryption (PII)** | Use Python `cryptography` library (Fernet/AES-256-GCM). Create a utility `encrypt_pii(text)` and `decrypt_pii(text)`. Apply to `citizenship_number`, `phone_number`, and `email` before DB insertion. |
| **Hashed Passwords** | Use `passlib[bcrypt]` with a cost factor of 12. Never store plaintext passwords. |
| **Input Validations** | Use Pydantic `BaseModel` for all JSON payloads. For file uploads, check `magic.from_buffer()` to verify MIME type (prevent disguised executables). Limit file size to 10MB. |
| **Parameterized Queries** | Use SQLAlchemy 2.0 ORM exclusively. No raw `cursor.execute("SELECT * FROM users WHERE id = " + id)`. |
| **Security Headers** | Add a FastAPI Middleware to inject headers: `Strict-Transport-Security`, `X-Frame-Options: DENY`, `Content-Security-Policy: default-src 'self'`, `X-Content-Type-Options: nosniff`. |
| **Error Handling** | Use FastAPI exception handlers. Catch all `Exception` and return a generic `{"detail": "Internal Server Error"}` to the client. Log the full traceback to the server console/Sentry. |
| **Traceability** | Create a Postgres trigger: `CREATE TRIGGER prevent_audit_update BEFORE UPDATE OR DELETE ON audit_logs FOR EACH ROW EXECUTE PROCEDURE raise_exception('Audit logs are immutable');` |

---

## 5. LangGraph Multi-Agent Architecture

The core pipeline is a directed acyclic graph (DAG) managed by LangGraph. State is passed via a Python `TypedDict`.

### 5.1 `AgentState` Schema
```python
class AgentState(TypedDict, total=False):
    # Inputs
    application_id: str
    applicant_id: str
    loan_request: Dict[str, Any]
    extracted_docs: Dict[str, Any]
    
    # Income Agent
    income_metrics: Dict[str, Any]
    indicators: Dict[str, Any] # Contains DTI, LTI, IMR
    income_agent_monthly_est: int
    income_confidence: float
    
    # Compliance Agent
    compliance_status: str # pass, flag, veto
    compliance_flags: List[str]
    
    # Score Agent
    scorecard: Dict[str, Any] # credit_score, band, shap
    
    # Decision Agent
    final_decision: str
    approved_amount_nrs: int
    interest_tier: str
    
    # System
    debug_info: Dict[str, Any]
    status: str
```

### 5.2 Execution Flow
1.  `START` -> **Income Agent**: Ingests transaction data, calculates IMR, DTI, LTI.
2.  **Income Agent** -> **Compliance Agent**: Checks NRB rules. If `veto`, short-circuits to `END`.
3.  **Compliance Agent** -> **Score Agent**: Runs XGBoost, generates SHAP values.
4.  **Score Agent** -> **Decision Agent**: Applies business matrix (Approve/Modify/Reject) and generates Nepali/English explanations.
5.  **Decision Agent** -> `END`: Persists final JSON to Postgres `loan_applications.final_decision`.

---

## 6. Core Business Logic Formulas

Developers must implement the following formulas exactly as specified to meet hackathon NRB compliance requirements.

### 6.1 Income Mismatch Ratio (IMR)
`IMR = Declared_Monthly_Income / Observed_Monthly_Income`
*   If `IMR > 3.0` (or `5.0` for remittance-dependent) -> Flag as document inflation.
*   If `IMR < 0.3` -> Flag as undisclosed income.

### 6.2 Loan-to-Income (LTI) & Debt-to-Income (DTI)
*   `LTI = Requested_Loan_Amount / Monthly_Income` (Hard Reject if `> 5.0` or `> 36.0` for Agri)
*   `DTI = Total_Monthly_Debt / Monthly_Income` (Hard Reject if `> 0.50`. Modify if `0.40 - 0.50`)

### 6.3 The 15% Haircut Rule
If the application is approved but:
*   `income_confidence < 0.70` OR
*   `compliance_status == "flag"`
Then the `approved_amount_nrs` must be calculated as:
`approved_amount_nrs = int(requested_amount * 0.85)`