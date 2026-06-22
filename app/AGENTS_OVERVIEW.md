# Agent System Architecture & Developer Guide

## Overview

This document provides a detailed technical overview of how the five autonomous agents work in the Dhago Credit & Lending Orchestrator system. It is designed for new developers who need to understand the data flow, responsibilities, and integration points of each agent.

---

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Application Submission                              │
│  (User submits: citizenship doc + bank statement + optional tax/lalpurja)    │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
                    ┌────────────▼──────────────┐
                    │   1. PARSER AGENT        │
                    │  (Document Intelligence)  │
                    └────────────┬──────────────┘
                                 │
                    ┌────────────▼──────────────┐
                    │   2. INCOME AGENT        │
                    │ (Transaction Analysis)    │
                    └────────────┬──────────────┘
                                 │
                    ┌────────────▼──────────────┐
                    │   3. SCORE AGENT         │
                    │  (Credit Scoring Model)   │
                    └────────────┬──────────────┘
                                 │
                    ┌────────────▼──────────────┐
                    │  4. COMPLIANCE AGENT     │
                    │  (Regulatory Enforcement) │
                    └────────────┬──────────────┘
                                 │
                    ┌────────────▼──────────────┐
                    │  5. COMPLIANCE AGENT     │
                    │   (Final Decision)        │
                    └────────────┬──────────────┘
                                 │
                        ┌────────▼────────┐
                        │ APPROVE/MODIFY/ │
                        │ REJECT/REVIEW   │
                        └─────────────────┘
```

---

## 1. PARSER AGENT (Document Intelligence)

**File:** `app/agents/parser_agent.py`  
**Entry Point:** `parser_node(state: AgentState) -> dict`

### Purpose
Extracts structured financial and identity information from uploaded documents using OCR and LLM-powered field extraction.

### Supported Documents
1. **Citizenship Certificate (नागरिकता प्रमाणपत्र)**
   - Extracts: citizenship number, name, DOB, birthplace, father/grandfather names, issued district
   - Confidence threshold: 50% of fields extracted

2. **Tax Clearance Certificate (कर चुक्ता प्रमाण पत्र)**
   - Extracts: taxpayer name, PAN, citizenship number, declared annual income, tax paid amount
   - Key financial signal: `effective_tax_rate = tax_paid / declared_income`

3. **Lalpurja (Land Deed मालपोत)**
   - Extracts: land owner, citizenship number, plot number, land area (in sq meters)
   - Indicates collateral/asset backing

### Processing Pipeline

```
Image File
    │
    ├─ [run_ocr] ──────────────────────┐
    │   - Converts image to text        │
    │   - Handles Nepali + English      │
    │   - Corrects image orientation    │
    │   - Applies denoising/sharpening  │
    │                                    │
    ├─ [detect_document_type] ────────┐
    │   - Keyword scoring              │
    │   - Returns: citizenship/tax/lalpurja
    │                                  │
    └─ [extract_*_fields] ────────────┐
        - Sends raw OCR text to Groq   │
        - LLM extracts fields as JSON  │
        - Converts Nepali → English    │
        - Calculates confidence score  │
        - Returns: extracted_fields +  │
          confidence + flags           │
```

### Key Functions

#### `run_ocr(image_path, lang='nep+eng') -> str`
- Uses Tesseract 5.0 for optical character recognition
- Detects image orientation via `image_to_osd()` and auto-rotates
- Applies preprocessing: grayscale → denoise → binary threshold
- Returns raw OCR text (mix of Nepali and English)

#### `detect_document_type(raw_text: str) -> str`
- Counts keyword matches for each document type
- Returns the type with highest keyword score
- Fallback: "unknown" if no keywords matched

#### `extract_citizenship_fields(raw_text: str) -> Dict`
- Calls Groq LLM with structured prompt
- Prompt includes field descriptions in Nepali + English
- LLM converts Nepali numerals to English digits (०→0, १→1, etc.)
- Returns:
  ```json
  {
    "document_type": "citizenship",
    "status": "verified" | "low_confidence" | "failed",
    "confidence_score": 0.0-1.0,
    "extracted_fields": {
      "full_name": "...",
      "citizenship_number": "37-02-75-05633",
      "date_of_birth": "1990-05-15",
      // ... more fields
    },
    "flags": [],
    "raw_ocr_text": "..."
  }
  ```

#### `extract_tax_clearance_fields(raw_text: str) -> Dict`
- Similar structure to citizenship extraction
- Key outputs:
  - `total_income_amount`: declared annual income
  - `tax_paid_amount`: actual tax remitted
  - `effective_tax_rate`: calculated as tax_paid / total_income

#### `extract_lalpurja_fields(raw_text: str) -> Dict`
- Extracts land ownership details
- Key outputs:
  - `owner_name`: person who owns land
  - `land_area`: area in sq meters or traditional units
  - `plot_number`: cadastral plot ID
  - `location_district`: which district the land is in

#### `format_for_scoring(extracted_data: dict, doc_type: str) -> dict`
- Normalizes extracted document data into scoring-ready format
- Creates `features` dict with financial signals:
  ```python
  {
    "declared_annual_income": float,
    "declared_monthly_income": float / 12,
    "tax_compliance_flag": 1 if tax_paid > 0 else 0,
    "effective_tax_rate": tax_paid / annual_income,
    "tax_document_present": bool,
    "asset_backing": {
      "asset_type": "land",
      "ownership_documented": bool,
      "land_area": float,
      "plot_number": str,
      "district": str
    }
  }
  ```

#### `parse_documents(image_paths: List[str], document_types: List[str]) -> Dict`
- **Main orchestration function** for multi-document processing
- Validates citizenship numbers across documents (detects identity mismatches)
- Priority: tax_clearance → citizenship → lalpurja (for credibility)
- Returns unified output with flags for downstream agents:
  ```json
  {
    "citizenship_number": "37-02-75-05633",
    "agent_source": "document",
    "features": { /* financial signals */ },
    "flags": ["citizenship_mismatch_across_documents"],
    "all_citizenship_numbers_found": [("citizenship", "37-02-75-05633"), ("tax", "37-02-75-05631")],
    "raw_extracted_data": {
      "citizenship": { /* full extraction result */ },
      "tax_clearance": { /* full extraction result */ },
      "lalpurja": { /* full extraction result */ }
    }
  }
  ```

### State Input/Output

**Input (from `AgentState`):**
```python
{
  "file_paths": {
    "citizenship": "/path/to/citizen.jpg",
    "tax_clearance": "/path/to/tax.jpg",
    "lalpurja": "/path/to/lalpurja.jpg"  # optional
  }
}
```

**Output (updates state):**
```python
{
  "extracted_docs": {
    "citizenship_number": "37-02-75-05633",
    "features": { /* see above */ },
    "flags": [ /* citizenship mismatches, low confidence, etc. */ ]
  },
  "status": "parser_complete" | "parser_complete_no_files" | "parser_failed"
}
```

### Error Handling
- LLM extraction failures fall back to empty JSON with `status: "failed"`
- Missing documents don't halt pipeline (optional tax/lalpurja)
- If citizenship number cannot be extracted from any document → `status: "parser_failed"`

---

## 2. INCOME AGENT (Transaction Analysis)

**File:** `app/agents/income_agent.py`  
**Entry Point:** `analyze(state: AgentState) -> dict`

### Purpose
Analyzes bank transactions to build an income profile, validates declared income against observed cash flow, and generates risk indicators.

### Processing Pipeline

```
Bank Statement (CSV/PDF)
    │
    ├─ [parse transactions] ──────────────┐
    │   - Extract date, amount, description
    │                                      │
    ├─ [assign_tnx_category] ────────────┐
    │   - Rule-based categorization       │
    │   - Income source classification    │
    │   - Returns: category + confidence  │
    │                                      │
    ├─ [Filter unknowns] ────────────────┐
    │   - Identify transactions with      │
    │     category == UNKNOWN             │
    │                                      │
    ├─ [LLM categorization] ─────────────┐
    │   - Call Groq for ambiguous txns    │
    │   - Improves confidence             │
    │                                      │
    ├─ [Merge categories] ───────────────┐
    │   - Update rule-based results       │
    │   - Build complete categorized list │
    │                                      │
    ├─ [generate_income_profile] ───────┐
    │   - Calculate per-source metrics    │
    │   - Effective Monthly Income (EMI)  │
    │   - Income Mismatch Ratio (IMR)     │
    │                                      │
    └─ [generate_risk_indicators] ──────┐
        - DTI, LTI calculations          │
        - Fraud flags (income mismatch)  │
        - Returns risk metrics            │
```

### Income Source Categories

The system recognizes 6 primary income categories (both credits and debits):

**Credit (Inflows):**
1. **Salary** — regular, recurring deposits from employers
2. **Remittance** — international transfers (Western Union, IME, etc.)
3. **Local Business/QR** — small business, QR code payments, peer-to-peer
4. **Freelance** — irregular professional income
5. **Agricultural** — seasonal crop/livestock income
6. **Cooperative/Interest** — group savings, interest income

**Debit (Outflows):**
- Bills (utilities, telecom)
- Transfers (loans, family support)
- Withdrawals (cash-dependent expenses)
- Merchant/retail (point-of-sale)

### Key Functions & Services

#### `assign_tnx_category(transaction: dict) -> Tuple[Category, float]`
Located in `app/services/income_categorizer.py`

- **Rule-based categorization** using keyword matching on:
  - Merchant name (e.g., "SALARY DEPOSIT" → Salary)
  - Transaction description
  - Transfer patterns (same amount, same day of month → Salary)
- Returns: `(category_enum, confidence_score)`
- Confidence depends on keyword strength and pattern consistency

#### `categorize_txn(unknown_transactions: List[dict]) -> List[dict]`
Located in `app/services/llm_service.py`

- Calls Groq LLM for transactions the rule engine couldn't classify
- Prompt includes transaction details (amount, description, date)
- LLM returns category + confidence score
- Used as fallback for edge cases

#### `generate_income_profile(transactions: List[dict], extracted_docs: dict) -> dict`
Located in `app/services/income_profile_calculations.py`

Computes comprehensive income metrics:

```python
{
  "total_observed_income": float,              # Sum of normalized monthly income from all sources
  "primary_income_source": str,                # Most stable source (e.g., "Salary")
  "primary_income_amount": float,              # Monthly income from primary source
  "monthly_unverified_inflows": float,         # Uncategorized inflows
  "months_of_data": int,                       # Transaction history depth
  "source_breakdown": {
    "Salary": {
      "monthly_average_raw": float,
      "monthly_usable_income": float,
      "recurrence_ratio": float,
      "volatility_cv": float,
      "confidence_score": float,
      "stability_score": float
    },
    "Remittance": { /* same structure */ },
    // ... other sources
  },
  "imr": float,                              # Income Mismatch Ratio
  "declared_monthly_income": float,          # From tax clearance (if available)
  "observed_monthly_income": float,          # From transaction analysis
  "imr_flag": str,                           # "normal" | "undeclared" | "inflated"
  "seasonal_adjustment": {
    "agricultural_borrower": bool,
    "low_season_months": [5, 6, 7],          # Example: May-July
    "seasonal_volatility": float
  },
  "fallback_track_activated": bool,          # True if < 3 months data
  "fallback_sources": [ /* cooperative, mobile money, etc. */ ]
}
```

**Effective Monthly Income (EMI) Calculation:**
```
EMI = Σ (Source_Income_i × w_i)

Where:
  w_i = weight for source i (based on stability, recurrence, confidence)
  w_Salary ≈ 1.0 (most reliable)
  w_Remittance ≈ 0.8 (less stable)
  w_Freelance ≈ 0.6 (irregular)
  w_Agricultural ≈ 0.5 (seasonal)
```

**Income Mismatch Ratio (IMR):**
```
IMR = Declared Monthly Income / Observed Monthly Income

Interpretation:
  IMR ≈ 1.0 → document-income consensus (credible)
  IMR > 3.0 → declared income likely inflated
  IMR < 0.3 → undisclosed income (integrity concern or informal sources)
  IMR 1.0-1.5 → normal variation
```

#### `generate_risk_indicators(income_profile: dict, extracted_docs: dict, loan_request: dict) -> dict`
Located in `app/services/risk_calculations.py`

Calculates regulatory and risk metrics passed to compliance:

```python
{
  "calculated_dti": float,                   # Debt-to-Income ratio
  "calculated_lti": float,                   # Loan-to-Income ratio
  "estimated_monthly_capacity": float,       # Repayment capacity
  "existing_liabilities_monthly": float,     # Current debt service
  "repayment_pressure_ratio": float,         # Soft stress indicator
  "fraud_flags": [
    "identity_mismatch_low_confidence",
    "identity_mismatch_hard",
    "income_mismatch_unavailable",
    "income_mismatch_low",
    "income_mismatch_high"
  ]
}
```

**DTI Calculation:**
```
DTI = Monthly Debt Service / Gross Monthly Income
    = (Current_Liabilities + Proposed_EMI) / Effective_Monthly_Income

NRB Hard Limit: DTI ≤ 0.50
NRB Soft Limit: DTI ≤ 0.40 (triggers MODIFY)
```

**LTI Calculation:**
```
LTI = Requested Loan Amount / Annual Income
    = Requested_Loan / (Effective_Monthly_Income × 12)

NRB Hard Limit: LTI ≤ 5.0
```

### State Input/Output

**Input (from `AgentState`):**
```python
{
  "raw_transactions": [
    {
      "id": "123",
      "date": "2024-01-15",
      "amount": 50000,
      "description": "SALARY DEPOSIT - ABC COMPANY",
      "type": "credit"
    },
    // ... more transactions
  ],
  "extracted_docs": {
    "features": {
      "declared_annual_income": 600000,
      "declared_monthly_income": 50000
    }
  },
  "loan_request": {
    "amount": 500000,
    "tenure_months": 24
  }
}
```

**Output (updates state):**
```python
{
  "categorized_txns": [ /* transactions with category + confidence */ ],
  "income_metrics": { /* comprehensive income profile */ },
  "indicators": { /* DTI, LTI, fraud flags */ },
  "status": "income_analysis_complete"
}
```

### Fallback Track (Thin-File Handling)
If transaction history < 3 months:
- System attempts to activate alternative data sources:
  - Cooperative passbooks (सहकारी खाता)
  - Mobile money recharge patterns (mPay, eSewa top-ups)
  - Utility payment regularity (water, electricity bills)
- Generates income profile from these signals with lower confidence
- Flags downstream agents for heightened scrutiny

---

## 3. SCORE AGENT (Credit Scoring)

**File:** `app/agents/score_agent.py`  
**Entry Point:** `score_application(state: AgentState) -> dict`

### Purpose
Combines document and income signals into a single credit score via XGBoost model, with SHAP explainability for each driver.

### Processing Pipeline

```
Income Metrics + Document Features + Loan Request
    │
    ├─ [Feature Engineering] ───────────────┐
    │   - Normalize all inputs              │
    │   - Compute derived features          │
    │   - Handle missing values             │
    │                                        │
    └─ [XGBoost Prediction] ────────────────┐
        - Load trained model                │
        - Generate score (0-1000)           │
        - Assign risk tier                  │
        - Calculate SHAP values             │
        - Extract top 3 drivers             │
```

### Feature Vector

The XGBoost model takes 15 features as input:

| # | Feature | Type | Range | Description |
|---|---------|------|-------|-------------|
| 1 | `total_observed_income` | float | 10k-250k NPR | Sum of normalized monthly income from all sources |
| 2 | `primary_source_type` | enum | 6 categories | Salary / Remittance / Business / Freelance / Ag / Cooperative |
| 3 | `primary_recurrence_ratio` | float | 0-1 | Consistency of primary income source |
| 4 | `weighted_stability_score` | float | 0-1 | Cross-source income stability |
| 5 | `combined_volatility_cv` | float | 0-∞ | Coefficient of variation (volatility) |
| 6 | `informal_income_ratio_pct` | float | 0-100 | % of income from informal sources |
| 7 | `months_of_data` | int | 1-36+ | Transaction history depth (tenure signal) |
| 8 | `tax_doc_present` | bool | 0/1 | Tax clearance certificate flag |
| 9 | `existing_liabilities_monthly` | float | 0-250k | Current monthly debt service |
| 10 | `repayment_pressure_ratio` | float | 0-1 | Soft stress ratio (liabilities / income) |
| 11 | `income_to_loan_ratio` | float | 0-∞ | Structural exposure (loan amt / monthly income) |
| 12 | `requested_loan_amount` | float | 200k-50M | Raw loan size |
| 13 | `requested_tenure_months` | int | 6-360 | Loan duration |
| 14 | `has_lalpurja` | bool | 0/1 | Land collateral present |
| 15 | `land_area_sqm` | float | 0-∞ | Collateral size in sq meters |

**Note:** DTI and LTI are **excluded** from the model to prevent circular logic — they are computed separately and used directly by the Compliance Agent.

### Key Functions

#### `generate_scorecard(extracted_docs, income_metrics, indicators, loan_request) -> dict`
Located in `app/services/score_calculations.py`

1. **Assembles feature vector** from inputs
2. **Calls XGBoost model** to predict score
3. **Calculates SHAP values** for explainability
4. **Assigns risk tier** based on score:
   - Low (700-1000)
   - Medium (550-699)
   - High (400-549)
   - Very High (< 400)

5. **Extracts top 3 SHAP drivers** (both positive and negative)

Returns:
```python
{
  "credit_score": 742,                       # 0-1000 scale
  "risk_tier": "LOW" | "MEDIUM" | "HIGH" | "VERY_HIGH",
  "fraud_flags": [
    "identity_mismatch_low_confidence",
    "income_mismatch_high"
  ],
  "calculated_dti": 0.34,
  "calculated_lti": 2.8,
  "estimated_monthly_capacity": 33000,      # EMI for debt service
  "suggested_loan_amount": 750000,
  "suggested_tenure": 36,
  "shap_top_drivers": [
    {
      "feature": "weighted_stability_score",
      "shap_value": 48.2,
      "direction": "POSITIVE"
    },
    {
      "feature": "tax_trust_score",
      "shap_value": 31.7,
      "direction": "POSITIVE"
    },
    {
      "feature": "imr",
      "shap_value": -8.4,
      "direction": "NEGATIVE"
    }
  ],
  "model_version": "v1.0_synthetic",
  "training_dataset": "synthetic_nepal_informal_sector"
}
```

### Model Details
- **Type:** XGBoost Gradient Boosting
- **Training Data:** Synthetic data calibrated to Nepal's informal sector income distribution (10k-250k NPR/month)
- **Output Scale:** 0-1000 (softmax normalized probability * 1000)
- **Explainability:** SHAP TreeExplainer for feature importance
- **Status:** Phase 1 uses synthetic labels; retraining planned after ~2,000 real repayment outcomes

### State Input/Output

**Input (from `AgentState`):**
```python
{
  "extracted_docs": { /* parser output */ },
  "income_metrics": { /* income agent output */ },
  "indicators": { /* risk indicators from income agent */ },
  "loan_request": {
    "amount": 500000,
    "tenure_months": 24
  }
}
```

**Output (updates state):**
```python
{
  "scorecard": { /* full scorecard above */ },
  "status": "scoring_complete"
}
```

---

## 4. COMPLIANCE AGENT (Regulatory Enforcement)

**File:** `app/agents/compliance_agent.py`  
**Entry Point:** `check_compliance(state: AgentState) -> dict`

### Purpose
Validates the application against Nepal Rastra Bank (NRB) Unified Directives 2080 and KYC/AML rules. **Has absolute veto authority** — no score, however high, overrides a compliance rejection.

### Processing Pipeline

```
Scorecard + Extracted Docs + Loan Request
    │
    ├─ [Extract regulatory inputs] ──────────┐
    │   - DTI, LTI from scorecard            │
    │   - Fraud flags                        │
    │   - Loan purpose, amount, tenure       │
    │                                         │
    ├─ [Check hard constraints] ────────────┐
    │   - Identity mismatches?               │
    │   - LTI > 5.0?                         │
    │   - DTI > 0.50?                        │
    │   - Prohibited purpose?                │
    │                                         │
    ├─ [Determine decision] ────────────────┐
    │   - REJECT / MODIFY / APPROVE / etc.   │
    │   - Cite specific NRB clause           │
    │                                         │
    ├─ [Build compliance result] ───────────┐
    │   - Decision + reason                  │
    │   - Suggested modifications (if any)   │
    │   - Compliance flags                   │
    │                                         │
    └─ [Format final output] ──────────────┐
        - Build_final_output()              │
        - Populate audit trail              │
```

### Decision Logic (Priority Order)

The agent evaluates rules in strict priority order. **The first matching rule wins** — all downstream rules are skipped:

| Priority | Condition | Decision | Reason | NRB Reference |
|----------|-----------|----------|--------|---|
| 1 | `"identity_mismatch_hard" in fraud_flags` | **REJECT** | KYC inconsistency indicates hard conflict | NRB AML Guidelines |
| 2 | `LTI > 5.0` | **REJECT** | Loan exceeds 5x annual income limit | NRB UD 2080, Clause 5.1 |
| 3 | `DTI > 0.50` | **REJECT** | Debt burden exceeds hard repayment threshold | NRB UD 2080, Clause 5.2 |
| 4 | `credit_score < 400 AND DTI < 0.30` | **MANUAL_REVIEW** | Model risk high; ratios acceptable → needs human judgment | Clause 5.2 exception |
| 5 | `DTI > 0.40 OR loan_amt_reduced OR tenure_extended` | **MODIFY** | Adjust principal/tenure for conservative repayment | NRB UD 2080, Clause 5.2 |
| 6 | `loan_purpose in {"gambling", "illegal", "banned"}` | **REJECT** | Prohibited lending purpose | NRB UD 2080, Clause 4.2 |
| 7 | All checks pass | **APPROVE** | Application meets v1 compliance thresholds | NRB UD 2080 advisory |

### Key Functions

#### `check_compliance(state: AgentState) -> dict`
Main orchestration function.

Processes:
1. **Extracts thresholds** from scorecard (DTI, LTI, credit score)
2. **Builds compliance notes** from fraud flags:
   - `"identity_mismatch_low_confidence"` → WARNING
   - `"income_mismatch_unavailable"` → INFO
   - `"income_mismatch_high"` → ADVISORY

3. **Evaluates decision tree** (see above)
4. **Calculates suggested modifications** if DTI too high:
   ```python
   # If DTI > 0.40, reduce principal or extend tenure
   new_amount = EMI * 0.40 * 12  # Solve for amount at DTI=0.40
   new_tenure = 36 → 48 months   # Or extend period
   ```

5. **Returns compliance result:**
```python
{
  "requested_loan_amount": 500000,
  "requested_tenure": 24,
  "loan_purpose": "equipment",
  
  "final_decision": "MODIFY" | "APPROVE" | "REJECT" | "MANUAL_REVIEW",
  "approved_amount": 450000,
  "approved_tenure": 30,
  
  "decision_reason": "Request has been adjusted to fit conservative repayment thresholds.",
  "nrb_directive_cited": "NRB UD 2080, Directive 5.2",
  "modifications_made": [
    "Reduced amount from 500000.00 to 450000.00",
    "Extended tenure from 24 to 30 months"
  ],
  
  "compliance_flags": ["dti_soft_breach"],
  "credit_score": 742,
  "risk_tier": "LOW",
  "fraud_flags": [],
  "estimated_monthly_capacity": 33000,
  "calculated_dti": 0.34,
  "calculated_lti": 2.8,
  
  "audit_note": "Compliance decision generated from scorecard output and advisory repayment ratios."
}
```

### DTI and LTI Calculations

**DTI (Debt-to-Income Ratio):**
```
DTI = (Existing Monthly Debt + Proposed Monthly EMI) / Effective Monthly Income

Example:
  - EMI = NPR 50,000/month
  - Existing debt = NPR 5,000/month
  - Requested loan = NPR 500,000 at 24 months
  - Monthly EMI = 500,000 / 24 ≈ 20,833
  - DTI = (5,000 + 20,833) / 50,000 = 0.517 → EXCEEDS 0.50 limit → REJECT
```

**LTI (Loan-to-Income Ratio):**
```
LTI = Requested Loan Amount / Annual Income
    = Requested_Loan / (EMI × 12)

Example:
  - Requested = 500,000
  - EMI = 50,000/month
  - Annual = 50,000 × 12 = 600,000
  - LTI = 500,000 / 600,000 = 0.833 → Within 5.0 limit
```

### Fraud Flag Interpretation

| Flag | Meaning | Compliance Impact |
|------|---------|-------------------|
| `identity_mismatch_low_confidence` | OCR extraction confidence < 50% on citizenship cert | WARNING added; DTI/LTI still evaluated |
| `identity_mismatch_hard` | Citizenship numbers differ across documents (e.g., passport vs tax form) | **AUTOMATIC REJECT** — KYC failure |
| `income_mismatch_unavailable` | No tax clearance; relying on transaction analysis only | INFO note; decision proceeds with lower confidence |
| `income_mismatch_low` | Observed income materially below declared (IMR < 0.3) | ADVISORY; suggests undisclosed income or informal sources; decision proceeds |
| `income_mismatch_high` | Declared income materially below observed (IMR > 3.0) | ADVISORY; suggests document inflation; decision proceeds with scrutiny |

### State Input/Output

**Input (from `AgentState`):**
```python
{
  "extracted_docs": { /* parser output */ },
  "scorecard": { /* score agent output */ },
  "compliance_notes": [],  # Optional prior warnings
  "loan_request": {
    "amount": 500000,
    "tenure_months": 24,
    "purpose": "equipment"
  }
}
```

**Output (updates state):**
```python
{
  "compliance_notes": [
    "WARNING: Citizenship mismatch appears driven by incomplete or low-confidence OCR.",
    "ADVISORY: Declared income is materially below observed cash flow."
  ],
  "compliance_result": { /* full compliance result above */ },
  "final_output": { /* see Decision Agent */ },
  "status": "compliance_checks_complete"
}
```

---

## 5. DECISION AGENT (Final Output Formatter)

**File:** `app/agents/compliance_agent.py` (final_output formatting)  
**Entry Point:** `build_final_output(state: dict) -> dict`

### Purpose
Converts all agent outputs into a human-readable, customer-facing, and audit-friendly final decision package. Generates explanations in both **English and Nepali**.

### Processing Pipeline

```
Full Agent State (all upstream results)
    │
    ├─ [Extract decision] ──────────────────┐
    │   - From compliance agent             │
    │   - APPROVE/MODIFY/REJECT/REVIEW      │
    │                                        │
    ├─ [Build explanation] ─────────────────┐
    │   - Cite top SHAP drivers             │
    │   - Translate to plain language       │
    │   - Generate Nepali version           │
    │                                        │
    ├─ [Compile audit trail] ──────────────┐
    │   - Per-agent timestamps              │
    │   - Status progression                │
    │   - All flags and warnings            │
    │                                        │
    ├─ [Assemble decision document] ───────┐
    │   - Approved amount / tenure          │
    │   - Next steps (if approve)           │
    │   - Re-eligibility path (if reject)   │
    │   - Manual review routing (if needed) │
    │                                        │
    └─ [Return to user] ───────────────────┐
        - JSON response + persistence      │
```

### Output Format

```json
{
  "application_id": "APP-2024-001234",
  "applicant_name": "Ram Bahadur Thapa",
  "citizenship_number": "37-02-75-05633",
  
  "decision": "APPROVE",
  "approved_amount_npr": 450000,
  "approved_tenure_months": 30,
  
  "credit_score": 742,
  "risk_tier": "LOW",
  
  "key_metrics": {
    "monthly_usable_income": 50000,
    "declared_monthly_income": 48000,
    "income_mismatch_ratio": 0.96,
    "dti": 0.34,
    "lti": 2.8,
    "estimated_monthly_capacity": 33000,
    "tax_compliance_flag": 1
  },
  
  "decision_factors": [
    "Consistent income pattern over 12 months (salary primary source)",
    "Valid tax documentation present (effective tax rate 8.5%)",
    "Strong cross-source stability despite informal income component",
    "Land collateral documented (Lalpurja: 2.5 ropani)",
    "Repayment ratios comfortably within NRB thresholds"
  ],
  
  "fraud_flags": [],
  "compliance_flags": [],
  
  "next_steps": {
    "instruction_en": "Your loan has been approved. Please visit the branch with your citizenship card and thumbprint for final disbursement.",
    "instruction_ne": "तपाईंको ऋण स्वीकृत भएको छ। अंतिम वितरणको लागि तपाईंको नागरिकता कार्ड र औंठछाप सहित शाखामा आउनुहोस्।"
  },
  
  "customer_explanation": {
    "summary_en": "Congratulations! Your loan application for NPR 450,000 over 30 months has been approved.",
    "summary_ne": "बधाई छ! तपाईंको ३० महिनाको लागि NPR ४,५०,००० को ऋण आवेदन स्वीकृत भएको छ।",
    "reason_en": "Our analysis shows consistent income from multiple reliable sources and strong repayment capacity.",
    "reason_ne": "हाम्रो विश्लेषण दर्शाता छ कि तपाईंसँग एकाधिक विश्वस्त स्रोतहरूबाट सुसंगत आय र शक्तिशाली पुनर्भुगतान क्षमता छ।"
  },
  
  "rejection_path": null,  # null if approved; populated if rejected
  
  "audit_trail": {
    "submission_time": "2024-01-15T10:30:00Z",
    "parser_agent": {
      "status": "success",
      "timestamp": "2024-01-15T10:31:00Z",
      "confidence_score": 0.92
    },
    "income_agent": {
      "status": "success",
      "timestamp": "2024-01-15T10:32:00Z",
      "income_months": 12
    },
    "score_agent": {
      "status": "success",
      "timestamp": "2024-01-15T10:33:00Z",
      "score": 742
    },
    "compliance_agent": {
      "status": "success",
      "timestamp": "2024-01-15T10:34:00Z",
      "decision": "APPROVE"
    }
  },
  
  "model_metadata": {
    "scorecard_version": "v1.0_synthetic",
    "compliance_rules_version": "NRB_UD_2080_v1",
    "generated_at": "2024-01-15T10:34:30Z"
  }
}
```

### Rejection Example

If decision is REJECT:

```json
{
  "decision": "REJECT",
  "rejection_reason_en": "Your application does not meet current lending criteria due to a hard identity conflict detected across submitted documents.",
  "rejection_reason_ne": "तपाईंको आवेदन बुझाइएको कागजातहरूमा पहिचान द्वन्द्वको कारण वर्तमान ऋण मानदण्ड पूरा गर्दैन।",
  
  "re_eligibility_path_en": "To reapply, please:\n1. Obtain updated citizenship certificate from Local Administration Office\n2. Resubmit with consistent identity across all documents\n3. Include recent tax clearance to strengthen income documentation",
  "re_eligibility_path_ne": "पुनः आवेदन गर्न कृपया:\n1. स्थानीय निकाय कार्यालयबाट अद्यतन नागरिकता प्रमाण पत्र प्राप्त गर्नुहोस्\n2. सबै कागजातहरूमा सुसंगत पहिचान सहित पुनः बुझाउनुहोस्\n3. आय कागजातलाई शक्तिशाली गर्न हाल तलब रिक्यूशन समेत समावेश गर्नुहोस्",
  
  "nrb_directive_cited": "NRB AML Guidelines — KYC Requirement",
  
  "manual_review_assigned": false
}
```

---

## Data Flow Summary

```
┌─────────────────────────────────────────────────────────────────────┐
│                        AGENT STATE (Shared)                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  PARSER AGENT adds:                                                  │
│  ├─ extracted_docs.citizenship_number                               │
│  ├─ extracted_docs.features (declared_income, tax_compliance, etc.) │
│  └─ extracted_docs.flags (identity mismatches, low confidence)      │
│                                                                       │
│  INCOME AGENT adds:                                                  │
│  ├─ income_metrics (EMI, IMR, source breakdown)                     │
│  ├─ categorized_txns (all txns with category + confidence)          │
│  └─ indicators (DTI, LTI, fraud flags)                              │
│                                                                       │
│  SCORE AGENT adds:                                                   │
│  ├─ scorecard.credit_score                                          │
│  ├─ scorecard.risk_tier                                             │
│  ├─ scorecard.shap_top_drivers                                      │
│  └─ scorecard.suggested_amount/tenure                               │
│                                                                       │
│  COMPLIANCE AGENT adds:                                              │
│  ├─ compliance_result.final_decision (APPROVE/MODIFY/REJECT)        │
│  ├─ compliance_result.approved_amount                               │
│  ├─ compliance_result.nrb_directive_cited                           │
│  └─ final_output (formatted decision document)                      │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## AgentState Schema

Located in `app/models/state.py`:

```python
class AgentState(TypedDict):
    # User input
    file_paths: Dict[str, str]              # File type → path mapping
    raw_transactions: List[Dict]            # Bank statement txns
    loan_request: Dict                      # Amount, tenure, purpose
    
    # Parser output
    extracted_docs: Dict                    # Citizenship, income, assets
    
    # Income output
    categorized_txns: List[Dict]
    income_metrics: Dict
    indicators: Dict                        # DTI, LTI, fraud flags
    
    # Score output
    scorecard: Dict
    
    # Compliance output
    compliance_notes: List[str]
    compliance_result: Dict
    
    # Final output
    final_output: Dict
    
    # Metadata
    status: str                             # Current step status
    errors: List[str]                       # Error tracking
    audit_trail: List[Dict]                 # Per-step timestamps
```

---

## Testing & Debugging

### Running Agents Locally

Each agent can be tested independently:

```python
# Test parser
from app.agents.parser_agent import parser_node

state = {
    "file_paths": {
        "citizenship": "/path/to/citizen.jpg",
        "tax_clearance": "/path/to/tax.jpg"
    }
}
result = parser_node(state)
print(result["extracted_docs"])

# Test income
from app.agents.income_agent import analyze

state["raw_transactions"] = [...]  # Mock transactions
result = analyze(state)
print(f"Monthly Usable Income: {result['income_metrics']['total_observed_income']}")
```

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| OCR returning gibberish | Low-quality image or rotated | Try preprocessing before passing to Tesseract |
| LLM extraction failing | Groq API key missing/invalid | Check `GROQ_API_KEY` in `.env` |
| Income categorization low confidence | Ambiguous merchant descriptions | Manually categorize or improve keyword dictionary |
| DTI calculated incorrectly | Existing liabilities not provided | Ensure `existing_liabilities_monthly` in income profile |

---

## Key Takeaways for New Developers

1. **Agent Separation of Concerns**: Each agent has ONE responsibility. Parser extracts documents. Income analyzes transactions. Score models risk. Compliance enforces rules. Final formats output.

2. **State is Immutable**: Each agent returns a dict to **merge** into state, never modifying state directly.

3. **LLM is a Tool**: Parser and Income agents use Groq LLM for field extraction and categorization, but fallbacks exist for failures.

4. **Compliance is Sovereign**: No score overrides compliance rules. The priority order is strict and cannot be bypassed by upstream agents.

5. **Explainability is Built-In**: SHAP values from the Score Agent + NRB clause citations from Compliance Agent + plain-language explanations from Decision Agent ensure full transparency to end users and regulators.

6. **Flags Drive Downstream Logic**: Parser flags (identity mismatches) → Income flags (income mismatches) → Score model observes flags → Compliance enforces hard constraints based on flags.

7. **Fallback Tracks Exist**: If data is insufficient (thin file, low OCR confidence), the system routes to manual review rather than auto-rejecting, ensuring inclusive lending.

---

## References

- **NRB Unified Directives 2080** — Nepal Rastra Bank lending rules (cited throughout compliance decisions)
- **XGBoost Documentation** — Model training and SHAP explainability
- **Tesseract OCR** — Language detection, orientation detection, text extraction
- **Groq API Docs** — Fast LLM inference for field extraction and categorization
- **LangGraph** — Agent orchestration framework (if used in pipeline.py)

---

*Last Updated: 2024-01-15*  
*For questions or updates, reach out to the development team.*
