# Dhago — Autonomous Credit & Lending Orchestrator

> **Built for the GIBL AI/ML Hackathon 2026 — Track A**
> *Aligning with Nepal Rastra Bank (NRB) Unified Directives 2080*

## Overview

**Dhago** (धागो — "thread") is a backend system that automates the end-to-end lending lifecycle—from document ingestion to final credit decisioning—using a multi-agent AI architecture tailored for the Nepali banking ecosystem.

The system specifically targets informal-sector borrowers (farmers, vendors, remittance-dependent households) who have outgrown microfinance loan sizes but lack the formal payslips or credit histories required by commercial banks. Its core mechanism is **document-income consensus**: declared income from official documents is cross-validated against behavioral signals from digital transaction history.

The pipeline is composed of **five AI agents** orchestrated through a central LangGraph state machine:

1. **Document Agent** — Performs OCR (Tesseract + VLM) on Nagrikta, Lalpurja, and tax documents to extract structured data and assign a trust score.
2. **Income Agent** — Profiles transaction history, categorizes inflows, and computes the Income Mismatch Ratio (IMR), DTI, and LTI.
3. **Score Agent** — Uses XGBoost to generate a 300–850 credit score and SHAP explainability drivers.
4. **Compliance Agent** — Enforces NRB Unified Directives 2080 as hard constraints with unconditional veto authority.
5. **Decision Agent** — Resolves all upstream outputs into a final decision (`APPROVE`, `MODIFY`, `MANUAL_REVIEW`, `REJECT`) with bilingual explanations.

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11+, FastAPI, LangGraph, LangChain |
| ML/OCR | XGBoost, SHAP, Tesseract, Ollama (Llama 3.3-70B, Chandra-OCR-2) |
| Database | PostgreSQL 17 (via Docker), psycopg2 |
| Auth | JWT (PyJWT + bcrypt) |
| Frontend | SvelteKit 2, Svelte 5 (runes), Tailwind CSS 4, TypeScript 6 |
| Infra | Docker Compose, Gunicorn + Uvicorn |

---

## Setup & Installation

### Prerequisites

* Python 3.11+
* Node.js 18+ (for frontend)
* PostgreSQL 17 (via Docker or local install)
* Ollama running locally (for LLM/OCR inference)

### 1. Clone the repository

```bash
git clone <your-repo-link>
cd autonomous-credit-and-lending-orchestrator
```

### 2. Start the database

```bash
docker compose up -d
```

This starts PostgreSQL 17 on port `5432` and pgAdmin on port `5050`.

### 3. Set up the backend

```bash
python -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

Create a `.env` file in the project root:

```env
DB_URL=postgresql://user:password@localhost:5432/lending
JWT_SECRET_KEY=change-me-to-a-real-256-bit-secret-in-production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
```

Initialize the database schema:

```bash
psql -U user -d lending -h localhost -f cleaned_db/schema.sql
```

Optionally load seed data:

```bash
psql -U user -d lending -h localhost -f cleaned_db/load_data.sql
```

### 4. Set up the frontend

```bash
cd frontend
npm install
```

The frontend env is preconfigured to point at `http://localhost:8000`. To change it, edit `frontend/.env`:

```
PUBLIC_API_URL=http://localhost:8000
```

### 5. Start Ollama

Pull the required models:

```bash
ollama pull llama3.3:70b
```

Ensure Ollama is running on `http://localhost:11434`.

---

## Quick Start

With everything installed, start the backend and frontend in separate terminals:

**Terminal 1 — Backend:**

```bash
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 — Frontend:**

```bash
cd frontend
npm run dev
```

| Service | URL |
|---------|-----|
| Frontend (SvelteKit) | `http://localhost:5173` |
| Backend API (Swagger) | `http://localhost:8000/docs` |
| pgAdmin | `http://localhost:5050` |

### Test the pipeline

Submit a loan application:

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

Check the decision:

```bash
curl -X GET "http://localhost:8000/api/v1/loan/decision/{application_id}"
```

### Access the admin panel

1. Navigate to `http://localhost:5173/admin/login`
2. Sign in with an admin account
3. From the dashboard you can:
   - View stats, decision distribution, and recent activity
   - Browse, search, filter, and bulk-update loan applications
   - Export loan data as CSV
   - Review individual applications with AI explainability (SHAP)
   - Override AI decisions with officer notes
   - View immutable audit trails per application
   - Manage users (toggle admin access, activate/deactivate)
