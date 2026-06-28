# Dhago — Autonomous Credit & Lending Orchestrator

> **Built for the GIBL AI/ML Hackathon 2026 — Track A**
> *Aligning with Nepal Rastra Bank (NRB) Unified Directives 2080*

## Overview

**Dhago** (धागो — "thread") is a backend system that automates the end-to-end lending lifecycle—from document ingestion to final credit decisioning—using a multi-agent AI architecture tailored for the Nepali banking ecosystem. 

The system specifically targets informal-sector borrowers (farmers, vendors, remittance-dependent households) who have outgrown microfinance loan sizes but lack the formal payslips or credit histories required by commercial banks. Its core mechanism is **document-income consensus**: declared income from official documents is cross-validated against behavioral signals from digital transaction history.

The pipeline is composed of **five AI agents** orchestrated through a central LangGraph state machine:
1. **Document Agent:** Performs OCR (Tesseract + VLM) on Nagrikta, Lalpurja, and tax documents to extract structured data and assign a trust score.
2. **Income Agent:** Profiles transaction history, categorizes inflows, and computes the Income Mismatch Ratio (IMR), DTI, and LTI.
3. **Score Agent:** Uses XGBoost to generate a 300–850 credit score and SHAP explainability drivers.
4. **Compliance Agent:** Enforces NRB Unified Directives 2080 as hard constraints with unconditional veto authority.
5. **Decision Agent:** Resolves all upstream outputs into a final decision (`APPROVE`, `MODIFY`, `MANUAL_REVIEW`, `REJECT`) with bilingual explanations.

---

## Setup & Installation

### Prerequisites
* Python 3.11+
* PostgreSQL 15+
* Redis 7+
* Local LLM server (Ollama / vLLM) running Llama 3.3-70B

### Installation Steps

1. **Clone the repository**
   ```bash
   git clone <your-repo-link>
   cd dhago
   ```

2. **Create and activate a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate       # macOS/Linux
   # venv\Scripts\activate        # Windows
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   Create a `.env` file in the root directory based on the following template:
   ```env
   # Database & Cache
   DATABASE_URL=postgresql+asyncpg://user:password@localhost/dhago_db
   REDIS_URL=redis://localhost:6379/0

   # Security
   JWT_SECRET_KEY=your-256-bit-secret
   JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
   FIELD_ENCRYPTION_KEY=base64-encoded-32-byte-key

   # Local LLM (for Document Agent formatting)
   LLM_BASE_URL=http://localhost:11434
   LLM_MODEL_NAME=llama3.3:70b

   # NRB Thresholds
   DTI_HARD_LIMIT=0.50
   LTI_HARD_LIMIT=5.0
   IMR_UPPER_THRESHOLD=3.0
   IMR_LOWER_THRESHOLD=0.3
   ```

5. **Initialize the database**
   Ensure your PostgreSQL server is running, then apply the migrations/schema:
   ```bash
   # Example command (adjust based on your actual ORM setup)
   alembic upgrade head
   ```

---

## Quick Start

Once the installation and environment setup are complete, you can start the FastAPI server and test the pipeline.

1. **Start the FastAPI Server**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

2. **Access the API Documentation**
   Open your browser and navigate to the interactive Swagger UI:
   ```
   http://localhost:8000/docs
   ```

3. **Submit a Test Application**
   You can test the endpoint by submitting a multipart form data request via `curl` or Postman:

   ```bash
   curl -X POST "http://localhost:8000/api/v1/loan/apply" \
     -H "accept: application/json" \
     -H "Content-Type: multipart/form-data" \
     -F "applicant_name=Sagar Newpane" \
     -F "citizenship_number=045-076-12345" \
     -F "requested_amount_npr=750000" \
     -F "requested_tenure_months=36" \
     -F "loan_purpose=agricultural_input" \
     -F "declared_occupation=Farmer" \
     -F "citizenship_doc=@/path/to/citizenship.jpg" \
     -F "bank_statement=@/path/to/statement.csv"
   ```

4. **Check the Decision**
   Use the `application_id` returned from the previous step to fetch the final credit decision:
   ```bash
   curl -X GET "http://localhost:8000/api/v1/loan/decision/{application_id}"
   ```