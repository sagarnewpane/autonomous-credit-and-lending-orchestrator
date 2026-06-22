# Dhago — Autonomous Credit & Lending Orchestrator

## Overview

This backend automates the end-to-end lending lifecycle—from document ingestion to final credit decisioning—using a multi-agent AI architecture tailored for the Nepali banking ecosystem.

The goal is to reduce manual friction, improve decision speed, and ensure compliance with Nepal Rastra Bank (NRB) regulations while maintaining strong explainability and auditability.

The system specifically targets informal-sector borrowers (farmers, vendors, remittance-dependent households) who have outgrown microfinance loan sizes but lack the documentation required by commercial banks. Its core mechanism is **document-income consensus**: declared income from official documents is cross-validated against behavioral signals from digital transaction history.

---

## System Architecture

The system is composed of **five AI agents** orchestrated through a central LangGraph pipeline:

```
Document Agent → Income Agent → Score Agent → Compliance Agent → Decision Agent
```

### 1. Document Intelligence Agent (Parser)

* Performs OCR on uploaded documents
* Extracts structured data from:
  * Citizenship certificates / Nagrikta (Devanagari + Latin)
  * Tax clearance certificates (IRD)
  * Lalpurja (land ownership documents)
* Uses Tesseract 5.0 (nep+eng) as  primary OCR engine to extract the texts; a Vision-Language Model then formats the raw text;
* Cross-validates citizenship numbers across all submitted documents
* Assigns a `doc_trust_score` (0–1) per application
* Flags low-confidence extraction for manual review; hard identity mismatches trigger an AML flag

### 2. Income Analysis Agent

* Constructs a behavioral income profile from uploaded bank statements
* Categorizes transaction inflows into six source types:
  * Salary, Remittance, Local Business/QR, Freelance, Agricultural, Cooperative/Interest
* Computes per-source stability metrics (recurrence ratio, volatility CV)
* Applies seasonal adjustment for agricultural earners — low-activity periods outside harvest windows are not penalized
* Computes the **Income Mismatch Ratio (IMR)**: declared monthly income ÷ observed monthly income
* Activates a **fallback track** when bank transaction data is insufficient (< 3 months), using cooperative records, mobile money patterns, and utility payment history as alternative signals

### 3. Risk Analysis Agent (Credit Scorer)

* Uses engineered features from the Document and Income agents
* Computes:
  * Credit score (0–1000 scale)
  * Risk tier: Low (700–1000) / Medium (550–699) / High (400–549) / Very High (< 400)
* Model: XGBoost trained on synthetic data calibrated to Nepal's informal sector income distribution (NPR 10,000–250,000/month, all income source types)
* Outputs SHAP-based explainability — top 3 risk drivers per application
* **DTI and LTI are computed by the Income Agent and passed directly to the Compliance Agent** — excluded from the scoring model feature vector to prevent model circularity

**Feature inputs (Table I from paper):**

| Feature | Description |
|---------|-------------|
| `total_effective_income` | Weighted usable monthly income (EMI proxy) |
| `primary_source_type` | Income source reliability |
| `primary_recurrence_ratio` | Primary income consistency |
| `weighted_stability_score` | Cross-source stability signal |
| `combined_volatility_cv` | Income volatility measure |
| `informal_income_ratio_pct` | Informality weighting factor |
| `months_of_data` | Transaction history depth |
| `tax_doc_present` | Document credibility signal |
| `existing_liabilities_monthly` | Absolute repayment burden |
| `repayment_pressure_ratio` | Soft repayment stress proxy |
| `income_to_loan_ratio` | Structural exposure proxy |
| `requested_loan_amount` | Loan context |
| `requested_tenure_months` | Tenure impact on repayment |
| `has_lalpurja` | Collateral presence signal |
| `land_area_sqm` | Asset strength indicator |

### 4. Regulatory Compliance Agent

* Validates application against NRB Unified Directives 2080 and KYC/AML requirements
* Enforces rules as hard constraints in strict priority order — **unconditional veto authority** over all upstream scores
* No score, however high, overrides a compliance veto
* Returns cited regulatory clauses for every decision

**Enforcement sequence:**

| Priority | Rule | Action |
|----------|------|--------|
| 1 | Identity mismatch across documents | REJECT + AML flag |
| 2 | Prohibited loan purpose (Clause 4.2) | REJECT |
| 3 | Sector exposure > 25% of Tier 1 capital | REJECT or QUEUE |
| 4 | Single-obligor concentration breach | REJECT |
| 5 | LTI > 5.0 (Clause 5.1) | REJECT |
| 6 | DTI > 0.50 (Clause 5.2) | REJECT |
| 7 | DTI 0.40–0.50 | MODIFY (adjust principal/tenure) |
| 8 | Score < 400, DTI < 0.30 | MANUAL REVIEW |
| 9 | PSL-eligible borrower | TAG + continue |
| 10 | All clear | APPROVE |

### 5. Decision Agent

* Terminal stage — resolves all upstream outputs into a final decision
* Outputs one of: **APPROVE**, **MODIFY**, **MANUAL_REVIEW**, **REJECT**
* Generates customer-facing explanation in plain **Nepali and English**
* For rejections: states reason in plain terms and describes what the applicant can do to improve eligibility
* Edge cases (PEP matches, dual thin-file profiles) are routed to a human review queue with priority tags

---

## Key Features

### Effective Monthly Income (EMI)
EMI = Σ (Source_Income_i × w_i)

Each weight depends on source classification confidence, income stability, recurrence behavior, and documentary support. EMI is more conservative than raw observed inflow and is the foundation for all DTI and LTI calculations.

### Income Mismatch Ratio (IMR)
IMR = Declared Monthly Income / Observed Monthly Income

* IMR ≈ 1.0 → document-income consensus; credibility signal
* IMR > 3.0 → potential document inflation; anomaly flag
* IMR < 0.3 → potential undisclosed income; anomaly flag
* For remittance-dependent applicants: upper threshold relaxed to 5.0

### Fallback Track (Thin-File / No Digital Footprint)
When bank transaction history is insufficient, the system activates an alternative scoring pathway using cooperative passbooks, mobile money recharge patterns, and utility payment regularity — ensuring the system does not re-exclude the population it was built to serve.

### Dual Thin-File Edge Case
If both `doc_trust_score < 0.30` and `transaction_months < 3`, the pipeline halts before scoring and routes directly to high-priority manual review. The officer review brief includes a list of supplementary documents that would unlock the standard pathway.

---

## Project Structure

```
dhago/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── api/
│   │   ├── routes.py
│   ├── agents/
│   │   ├── pipeline.py          # LangGraph graph definition
│   │   ├── state.py             # AgentState schema
│   │   ├── document_agent.py
│   │   ├── income_agent.py
│   │   ├── score_agent.py
│   │   ├── compliance_agent.py
│   │   └── decision_agent.py
│   ├── services/
│   │   ├── orchestrator.py
│   │   ├── ocr_service.py
│   │   ├── ml_service.py
│   │   └── storage_service.py
│   ├── db/
│   │   ├── models.py
│   │   └── database.py
│   └── security/
│       ├── jwt_handler.py
│       ├── encryption.py
│       └── rbac.py
├── models/                      # XGBoost + SHAP artifacts
├── requirements.txt
├── .env.example
└── README.md
```

---

## Getting Started

### Prerequisites

* Python 3.11+
* PostgreSQL 15+
* Redis 7+
* Local LLM server (Ollama / vLLM) for Llama 3.3-70B

### Installation

```bash
# 1. Clone the repository
git clone <your-repo-link>
cd dhago

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate       # macOS/Linux
venv\Scripts\activate          # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
```

### Environment Variables

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost/dhago_db
REDIS_URL=redis://localhost:6379/0

# JWT
JWT_SECRET_KEY=your-256-bit-secret
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30

# Encryption (AES-256 for PII fields)
FIELD_ENCRYPTION_KEY=base64-encoded-32-byte-key

# Local LLM
LLM_BASE_URL=http://localhost:11434
LLM_MODEL_NAME=llama3.3:70b

# NRB thresholds
DTI_HARD_LIMIT=0.50
LTI_HARD_LIMIT=5.0
IMR_UPPER_THRESHOLD=3.0
IMR_LOWER_THRESHOLD=0.3
```

---

## API Endpoints

### 1. Loan Application Submission

**POST** `/api/v1/loan/apply`

Submit a new loan application. Accepts multipart form data.

| Field | Type | Required |
|-------|------|----------|
| `applicant_name` | string | ✓ |
| `citizenship_number` | string | ✓ |
| `requested_amount_npr` | integer (200k–50M) | ✓ |
| `requested_tenure_months` | integer (6–360) | ✓ |
| `loan_purpose` | enum | ✓ |
| `declared_occupation` | enum | ✓ |
| `citizenship_doc` | file (JPG/PNG/PDF) | ✓ |
| `bank_statement` | file (CSV/PDF) | ✓ |
| `tax_clearance_doc` | file | ✗ |
| `lalpurja_doc` | file | ✗ |
| `cooperative_records` | file | ✗ |

---

### 2. Final Credit Decision

**GET** `/api/v1/loan/decision/{application_id}`

Returns approval/rejection with summary reasoning.

```json
{
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

---

### 3. Explainability Deep Dive

**GET** `/api/v1/loan/explain/{application_id}`

Provides full transparency into AI decision-making via SHAP values and IMR.

```json
{
  "credit_score": 742,
  "risk_tier": "LOW",
  "decision": "APPROVE",
  "imr": 1.14,
  "dti": 0.34,
  "lti": 2.8,
  "dsr": {
    "formula": "Total Monthly Debt / Gross Monthly Income",
    "value": 0.34,
    "threshold": 0.50
  },
  "shap_top_drivers": [
    { "feature": "weighted_stability_score", "shap_value": 48.2, "direction": "POSITIVE" },
    { "feature": "tax_trust_score",          "shap_value": 31.7, "direction": "POSITIVE" },
    { "feature": "imr",                       "shap_value": -8.4, "direction": "NEGATIVE" }
  ],
  "factors": [
    "Consistent income pattern over 12 months",
    "Valid tax documentation present",
    "Minor income-document discrepancy detected"
  ],
  "compliance_flags": []
}
```

---

### 4. Document Re-upload / Correction

**PUT** `/api/v1/loan/docs/{application_id}`

Re-upload failed or low-quality documents without restarting the application. Pipeline re-runs from the Document Agent.

---

### 5. User Loan History

**GET** `/api/v1/loans/user/{user_id}`

Returns all past and active loan applications for a user. Used for loan overlap detection and behavioral credit analysis.

---

### 6. Compliance Reference Fetcher

**GET** `/api/v1/loan/compliance/references/{application_id}`

Returns actual NRB directive clauses cited during validation.

```json
{
  "references": [
    {
      "clause": "NRB Unified Directive 2080 — Clause 5.2",
      "text": "Banks must ensure DSR does not exceed 50%...",
      "relevance_score": 0.91
    }
  ]
}
```

---

### 7. Admin Dashboard

**GET** `/api/v1/loan/loans`

Returns all applications for the internal banking dashboard.

---

### 8. Admin Review (Human-in-the-Loop)

**PATCH** `/api/v1/loan/admin/review/{application_id}`

Allows a loan officer or compliance officer to override or confirm an automated decision. All overrides are logged in the audit trail with officer ID and timestamp.

---

### 9. Audit Trail

**GET** `/api/v1/loan/audit/{application_id}`

Returns the full immutable per-step audit trail for an application. Every agent action is logged with a timestamp and agent identifier. Required for NRB supervisory inspection.

---

### 10. System Check

**GET** `/api/v1/loan/system-check`

Returns the status of the system

---

## Multi-Agent Orchestration Flow

```
1. User submits application (documents + bank statement)
        ↓
2. Document Agent — OCR extraction + trust scoring
   └─ Low confidence? → flag for re-upload
        ↓
3. Income Agent — transaction profiling + IMR computation
   └─ Thin-file? → activate fallback track (cooperative / utility data)
   └─ Dual thin-file? → route to MANUAL REVIEW immediately
        ↓
4. Score Agent — XGBoost scoring + SHAP explainability
        ↓
5. Compliance Agent — NRB 2080 hard rule enforcement (veto authority)
   └─ REJECT / MODIFY / QUEUE as needed
        ↓
6. Decision Agent — final decision + Nepali/English explanation
        ↓
7. Human Review (if escalated) — loan officer queue with priority tags
```

---

## Decision Engine

The system produces:

* **Transparent reasoning** — SHAP drivers link score to specific features
* **Interpretable financial metrics** — DSR, IMR, DTI, LTI shown with formulas and thresholds
* **Real regulatory clause citations** — every compliance decision cites the specific NRB 2080 clause
* **Audit logs for every step** — immutable, timestamped, per-agent entries
* **Bilingual customer explanations** — plain Nepali and English; rejections include a path to re-eligibility

---

## Security

| Control | Implementation |
|---------|---------------|
| Authentication | JWT (access 30 min, refresh 7 days) with Redis-backed blacklist on logout |
| Access Control | RBAC — loan_officer / senior_officer / compliance_officer / admin |
| Encryption | AES-256-GCM on all PII database fields; documents encrypted at rest in object storage |
| Password Hashing | bcrypt (cost factor 12) |
| Input Validation | Pydantic schemas + file MIME detection from magic bytes + ClamAV scan |
| SQL Injection | SQLAlchemy ORM with parameterized queries only — no raw string SQL |
| Security Headers | HSTS, X-Frame-Options, CSP, X-Content-Type-Options |
| Error Handling | Full tracebacks logged server-side only; clients receive generic safe message |
| Audit Trail | Immutable PostgreSQL table (trigger blocks UPDATE/DELETE); 7-year retention per NRB |

---

## Important Limitations (Phase 1)

* **Synthetic training data** — the XGBoost model is trained on synthetic labels, not observed Nepali loan repayment outcomes. Treat output as a decision-support heuristic, not an autonomous decision. Real-outcome retraining begins after ~2,000 labeled loans accumulate.
* **AML completeness** — Phase 1 includes cross-document identity validation and PEP screening. Full FIU-Nepal SAR reporting and OFAC/UN sanctions screening are Phase 2. All APPROVE outputs require human AML clearance before disbursement.
* **Wallet API access** — eSewa and Khalti do not currently offer public APIs for third-party credit applications. Bank statement uploads (CSV/PDF) are the primary transaction data source.

---

*Dhago Backend v1.0 · Nepal Rastra Bank Unified Directives 2080 · Python 3.11 · FastAPI*
*Built for the GIBL Hackathon*
