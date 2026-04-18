# Bank Project Flow Status

This document replaces the older PDF-style flow note with the current implementation status of the project.

It answers two questions:
- What has already been implemented in the backend flow
- What is still not implemented or only partially implemented

## Current Flow

The current backend flow is now:

`Document Parser -> Income Agent -> Score Agent -> Compliance Agent`

### Implemented Flow Responsibilities

#### 1. Document Parser
Implemented:
- OCR-based document parsing for citizenship, tax clearance, and Lalpurja
- Extraction of declared tax income fields
- Extraction of tax compliance fields
- Extraction of Lalpurja as asset backing
- Cross-document citizenship collection
- Parser output shaped for downstream agents

Changed from old PDF:
- Tax document values are treated as declared/proof data, not direct usable cash flow
- Lalpurja is treated as asset backing, not income

Still not fully done:
- OCR confidence handling is still rough
- Citizenship mismatch detection is still heuristic
- Parser confidence can still be unrealistic in some cases
- Camera/front-back capture validation from the PDF is not implemented

#### 2. Income Agent
Implemented:
- Transaction categorization
- Source-wise profiling for:
  - Salary
  - Remittance
  - Local business
  - Freelance
  - Interest
  - Agriculture
- Source-wise normalization
- Source-wise weighting
- Source-wise confidence and stability logic
- Effective income aggregation
- Dedupe rule that prevents tax and asset documents from being counted as income

Changed from old PDF:
- Replaced the older salary-centric summary with a source-wise income model
- Replaced generic wallet-style thinking with:
  - `total_observed_income`
  - `total_effective_income`

Still not fully done:
- Income weighting is still heuristic and not calibrated on real lending outcomes
- Agriculture/cooperative handling exists in the taxonomy but is still basic
- No past loan history or behavioral repayment history is used

#### 3. Score Agent
Implemented:
- New Score Agent added to the orchestration graph
- Deterministic scoring, no ML model
- Outputs:
  - `credit_score`
  - `risk_tier`
  - `fraud_flags`
  - `income_mismatch_ratio`
  - `stability_score`
  - `tax_trust_score`
  - `estimated_monthly_capacity`
  - `calculated_dti`
  - `calculated_lti`
  - `suggested_loan_amount`
  - `suggested_tenure`
  - `suggested_interest_premium`
  - `top_risk_drivers`
  - `score_breakdown`
  - `scoring_confidence`
  - `citizenship_number`
  - `audit_note`

Implemented scoring behavior:
- Baseline score of `500`
- Point adjustments from:
  - income mismatch
  - stability
  - tax trust
  - income composition
  - document inconsistency
  - asset backing uplift
- Low-confidence identity mismatch is separated from hard identity mismatch
- Capacity uses `total_effective_income`
- Mismatch uses `declared_monthly_income / total_observed_income`

Changed from old PDF:
- No XGBoost
- No dependence on old income-agent field shapes
- No dependence on income agent carrying identity

Still not fully done:
- Score calibration is heuristic
- No learned model
- No loan-history features
- No camera/KYC biometric features
- No sector exposure logic
- No PEP logic

#### 4. Compliance Agent
Implemented:
- Compliance now runs after scoring
- Compliance owns final decision output
- Compliance returns:
  - `final_decision`
  - `approved_amount`
  - `approved_tenure`
  - `decision_reason`
  - `nrb_directive_cited`
  - `modifications_made`
  - `compliance_flags`
- Final decision types:
  - `APPROVE`
  - `MODIFY`
  - `REJECT`
  - `MANUAL_REVIEW`

Implemented compliance behavior:
- Reject on hard identity mismatch
- Reject on `LTI > 5.0`
- Reject on `DTI > 0.5`
- Modify when the request should be reduced or tenure extended
- Manual review for low-score but low-DTI conflict
- Prohibited-purpose rejection

Changed from old PDF:
- Compliance consumes the new scorecard shape
- Compliance uses the lean hackathon rule set instead of the full PDF matrix

Still not fully done:
- Not a full NRB directive engine
- No sector exposure rules
- No PEP escalation path
- No full conflict-resolution protocol from the PDF
- No persisted audit trail fields like officer ID, timestamped rule log, or rules checked list
- No full Pareto optimization logic for modifications

## What Was Changed from the PDF

These parts were intentionally changed:

### A. Input Shape Was Updated
Old PDF assumptions were replaced with the real current backend shape:
- `doc_monthly_income` -> `declared_monthly_income`
- generic wallet monthly -> `total_observed_income`
- repayment capacity -> `total_effective_income`
- identity source -> `extracted_docs.citizenship_number`

### B. Score Agent Is Lean and Rule-Based
Changed:
- XGBoost removed
- deterministic rule-based scoring added
- score breakdown made explicit and auditable

### C. Compliance Was Kept as Final Decision Layer
Changed:
- score agent gives soft recommendations
- compliance agent makes final approve/modify/reject/manual review decision

### D. Identity Mismatch Logic Was Softened
Changed:
- truncated OCR mismatch is treated as `identity_mismatch_low_confidence`
- clear conflict is treated as `identity_mismatch_hard`

## What Is Not Changed Yet

These things are still pending:

### Backend/Product Gaps
- API still does not execute the full graph on loan application submission
- API still does not return or persist scorecard/compliance result
- Loan application persistence does not fully store the new flow outputs
- `purpose` and `tenure_months` are not fully persisted as part of a richer application model

### Data/Document Gaps
- OCR confidence and mismatch resolution need cleanup
- Some extracted confidence values can still be unrealistic
- Full front/back capture validation is not implemented

### Risk/Compliance Gaps
- No full NRB policy rules engine
- No portfolio/sector exposure checks
- No PEP checks
- No loan-history checks
- No manual-review workflow persistence

### Testing Gaps
- Smoke tests exist
- Proper automated test coverage for all planned cases is still pending

## Current Readiness

### Ready Now
- Parser-to-income-to-score-to-compliance flow in orchestration
- Scorecard generation
- Final compliance decision generation
- Demo/hackathon-level backend logic

### Not Ready Yet
- Full API integration
- Full persistence of results
- Full NRB compliance implementation
- Production-grade auditability and test coverage

## Recommended Next Steps

1. Wire `/api/v1/loan/apply` to run the orchestration graph
2. Persist and expose `scorecard` and `compliance_result`
3. Clean parser confidence and identity mismatch quality
4. Add focused automated tests for planned borrower scenarios
5. Expand compliance only after API and persistence are stable
