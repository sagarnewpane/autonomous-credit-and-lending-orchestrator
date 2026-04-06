# Autonomous Credit & Lending Orchestrator (GIBL Hackathon)

## Overview

This backend prototype automates the end-to-end lending lifecycle—from document ingestion to final credit decisioning—using a multi-agent AI architecture tailored for the Nepali banking ecosystem.

The goal is to reduce manual friction, improve decision speed, and ensure compliance with Nepal Rastra Bank (NRB) regulations while maintaining strong explainability and auditability.

---

## System Architecture

The system is composed of three core AI agents orchestrated through a central pipeline:

### 1. Document Intelligence Agent (Parser)

* Performs OCR on uploaded documents
* Extracts structured data from:

  * Citizenship certificates (Nepali)
  * Income statements
  * Lalpurja (land ownership documents)
* Handles Devanagari text using OCR tools like EasyOCR or PaddleOCR
* Flags low-confidence extraction for re-upload

### 2. Risk Analysis Agent (Credit Scorer)

* Uses:

  * Parsed document data
  * Mock or real internal banking data
* Computes:

  * Risk score (0–1 scale or 0–900 scale)
  * Debt Service Ratio (DSR)
* Outputs explainable reasoning + intermediate calculations

### 3. Regulatory Compliance Agent

* Validates application against:

  * NRB Unified Directives
  * KYC requirements
* Uses Retrieval-Augmented Generation (RAG) with a vector database (ChromaDB)
* Returns cited regulatory clauses (no hallucinations)

---

## Project Structure

```
project-root/
│── app/
│   ├── main.py
│   ├── api/
│   │   ├── routes.py
│   ├── agents/
│   │   ├── parser_agent.py
│   │   ├── risk_agent.py
│   │   ├── compliance_agent.py
│   ├── services/
│   │   ├── orchestrator.py
│   ├── db/
│   │   ├── models.py
│   │   ├── database.py
│── requirements.txt
│── README.md
│── .venv
```

---

## Getting Started

### Prerequisites

* Python 3.10+
* PostgreSQL
* OpenAI API Key (or local LLM)

---

### Installation

1. Clone the repository:

```bash
git clone <your-repo-link>
cd <repo-folder>
```

2. Create virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # macOS/Linux
venv\\Scripts\\activate     # Windows
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Configure environment variables:

```env
DATABASE_URL=postgresql://user:password@localhost/gibl_db
OPENAI_API_KEY=your_api_key_here
```

---

## API Endpoints 

### 1. Loan Application Submission

**POST** `/api/v1/loan/apply`

Submit a new loan application.

---

### 2. Final Credit Decision

**GET** `/api/v1/loan/decision/{application_id}`

Returns approval/rejection with summary reasoning.

---

### 4. Explainability Deep Dive (NEW)

**GET** `/api/v1/loan/explain/{application_id}`

Provides full transparency into AI decision-making.

**Response Example:**

```json
{
  "risk_score": 0.42,
  "decision": "Rejected",
  "dsr": {
    "formula": "Total Monthly Debt / Gross Monthly Income",
    "value": 0.67,
    "threshold": 0.5
  },
  "factors": [
    "High existing loan obligations",
    "Income variability detected"
  ],
  "compliance_flags": [
    "NRB_Directive_Clause_5.2 triggered"
  ]
}
```

---

### 5. Document Re-upload / Correction (NEW)

**PUT** `/api/v1/loan/docs/{application_id}`

Allows user or banker to re-upload failed or low-quality documents without restarting the application.

---

### 6. User Loan History (NEW)

**GET** `/api/v1/loans/user/{user_id}`

Returns all past and active loan applications for a user.

Used for:

* Loan overlap detection
* Behavioral credit analysis

---

### 7. Compliance Reference Fetcher 

**GET** `/api/v1/compliance/references/{application_id}`

Returns actual NRB document snippets used during validation.

**Response Example:**

```json
{
  "references": [
    {
      "clause": "NRB Unified Directive 5.2",
      "text": "Banks must ensure DSR does not exceed 50%...",
      "relevance_score": 0.91
    }
  ]
}
```

---

### 8. Admin Dashboard 

**GET** `/api/v1/loans`

Returns all applications for internal banking dashboard.

---

### 9. Admin Review (Human-in-the-loop)

**PATCH** `/api/v1/admin/review/{application_id}`

Allows banker override or confirmation.

---

## Multi-Agent Orchestration Flow

1. User submits application
2. Parser Agent extracts data

   * If confidence < threshold → flag for re-upload
3. Risk Agent computes:

   * Risk score
   * DSR
4. Compliance Agent:

   * Retrieves NRB clauses via RAG
   * Validates eligibility
5. Orchestrator:

   * Aggregates outputs
   * Stores reasoning trace
6. Decision Engine:

   * Generates final decision + explanation
7. Optional Human Review

---

## Decision Engine (Critical Component)

The system must:

* Provide **transparent reasoning**
* Output **interpretable financial metrics (DSR, risk score)**
* Link decisions to **real regulatory clauses**
* Maintain **audit logs for every step**

Without explainability, the prototype fails evaluation.
