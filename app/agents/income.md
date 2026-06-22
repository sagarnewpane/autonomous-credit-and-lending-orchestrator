# Income Agent — Detailed Technical Reference
## GIBL AI/ML Hackathon 2026 — Track A: Autonomous Credit & Lending Orchestrator

---

> **Agent Role:** Alternative Income Estimator  
> **Position in Pipeline:** Stage 1 of 5 (feeds Score Agent → Compliance Agent → Decision Agent)  
> **Primary Output:** `income_agent_monthly_est` + `income_confidence`  
> **Domain:** Alternative Data · Financial Inclusion · Rural Nepal Credit

---

## Table of Contents

1. [Agent Overview](#1-agent-overview)
2. [Input Data Sources](#2-input-data-sources)
   - 2.1 Mobile Money Transactions (eSewa / Khalti)
   - 2.2 Remittance Records
   - 2.3 Cooperative Sales
   - 2.4 Utility Payment Regularity
   - 2.5 Applicant Profile Metadata
3. [Output Fields](#3-output-fields)
4. [Income Signal Taxonomy](#4-income-signal-taxonomy)
5. [Confidence Scoring Logic](#5-confidence-scoring-logic)
6. [Decision Thresholds](#6-decision-thresholds)
7. [Data Joins & Keys](#7-data-joins--keys)
8. [Data Quality Issues to Handle](#8-data-quality-issues-to-handle)
9. [Feature Engineering Guide](#9-feature-engineering-guide)
10. [Evaluation Metric](#10-evaluation-metric)
11. [Nepal Context & Domain Notes](#11-nepal-context--domain-notes)
12. [Code Snippets](#12-code-snippets)

---

## 1. Agent Overview

The **Income Agent** is the first stage of the multi-agent credit orchestration pipeline. Its sole purpose is to estimate a monthly income figure for loan applicants who have **no formal payslips, tax returns, or CIB credit bureau history** — the credit-invisible population the entire dataset is built around.

Approximately **72% of applicants** have a NULL `credit_bureau_score`, meaning formal credit infrastructure simply cannot serve them. The Income Agent bridges this gap by aggregating **alternative data signals** from four transactional sources and one profile source into a single coherent monthly income estimate.

### Pipeline Position

```
[Raw Data Tables]
       │
       ▼
┌──────────────────────┐
│    INCOME AGENT      │  ← You are building this
│                      │
│  Inputs:             │
│  • mobile_money_tx   │
│  • remittance_recs   │
│  • coop_sales        │
│  • utility_payments  │
│  • applicant profile │
│                      │
│  Outputs:            │
│  • monthly_est (NRs) │
│  • confidence (0–1)  │
└──────────────────────┘
       │
       ▼
┌──────────────────────┐
│    SCORE AGENT       │  (XGBoost credit scorer)
└──────────────────────┘
       │
       ▼
┌──────────────────────┐
│  COMPLIANCE AGENT    │  (NRB rule checker)
└──────────────────────┘
       │
       ▼
┌──────────────────────┐
│  DECISION AGENT      │  (approve/conditional/refer/reject)
└──────────────────────┘
```

### Why Income Estimation is Hard Here

- Most applicants are **smallholder farmers, daily wage workers, remittance-dependent households, or rural traders** — income is seasonal, informal, and multi-stream.
- **Not all customers have all data types.** Coverage is deliberately sparse and realistic:
  - Mobile wallet data: ~69% of customers
  - Remittance data: ~36% of customers
  - Cooperative data: ~41% of customers
  - Utility payments: ~98% of customers (strongest coverage)
- Income signals must be triangulated and weighted by reliability and coverage depth.

---

## 2. Input Data Sources

### 2.1 Mobile Money Transactions (`mobile_money_transactions.parquet`)

The **primary and richest income signal source**. Contains ~2.27 million rows of individual eSewa and Khalti wallet transactions over 6 months (January–June 2024).

**File:** `structured/mobile_money_transactions.parquet`  
**Load:** `pd.read_parquet("structured/mobile_money_transactions.parquet")`  
**Coverage:** ~69% of applicants (those with `has_esewa_account = True` or `has_khalti_account = True`)

#### Key Columns for Income Estimation

| Column | Type | Relevance |
|---|---|---|
| `applicant_id` | STRING | Join key |
| `transaction_date` | TIMESTAMP | Time-series aggregation |
| `transaction_type` | STRING | Income signal filter |
| `amount_nrs` | STRING* | Transaction amount (must be cleaned) |
| `direction` | STRING | `credit` = income proxy; `debit` = expense |
| `counterparty_category` | STRING | Signal context |
| `is_festival_period` | BOOLEAN | Spending spike flag; exclude from income baseline |
| `platform` | STRING | `esewa` or `khalti` |
| `_noise_anomaly_flag` | BOOLEAN | Filter out fraud transactions before income calc |
| `_noise_anomaly_type` | STRING | Fraud type label (train/val only) |

*`amount_nrs` is stored as a STRING due to injected comma-formatted noise (e.g., `"1,500.00"`). Always clean before use.

#### Income-Relevant Transaction Types

| transaction_type | % of Transactions | Income Signal? | Notes |
|---|---|---|---|
| `remittance_receipt` | 10% | ✅ Strong | Direct cash income from abroad |
| `wallet_topup` | 7% | ✅ Moderate | Proxy for cash income deposited |
| `merchant_payment` | 28% | ❌ Expense | Debit; indicates spending capacity |
| `p2p_transfer` | 22% | ⚠️ Ambiguous | Could be income or expense |
| `utility_payment` | 18% | ❌ Expense | Creditworthiness signal only |
| `qr_payment` | 10% | ❌ Expense | Merchant payment via QR |
| `wallet_withdrawal` | 3% | ⚠️ Ambiguous | Cash-out could follow income receipt |
| `loan_repayment` | 2% | ❌ Liability | Signals existing debt obligation |

#### Fraud Anomaly Types to Exclude

Before computing income, **filter out transactions flagged as anomalies** (~1.7% of all transactions):

| Anomaly Type | Description | Income Impact |
|---|---|---|
| `midnight_round` | Round-amount transactions between midnight and 4 AM | Artificially inflates income |
| `future_timestamp` | Transactions dated in 2026 (impossible) | Invalid data point |
| `velocity_burst` | 10+ transactions in 5 minutes, 8× normal amount | Fraudulent income spike |

> **Note:** `_noise_anomaly_type` labels are available in train/val/public_test but **removed from hidden_test**. You must build anomaly detection logic for the hidden test split.

#### Festival Period Handling

`is_festival_period = True` covers **Dashain and Tihar** (months 3–4 of BS calendar, roughly October). Spending spikes significantly during these periods and should be **normalized or excluded** when computing a baseline monthly income.

---
### 2.2 Remittance Records (`remittance_records.parquet`)

International money transfers received by ~36% of customers from family members working abroad. Nepal's remittances represent approximately **25% of GDP**, making this a critical income channel for rural households.

**File:** `structured/remittance_records.parquet`  
**Load:** `pd.read_parquet("structured/remittance_records.parquet")`  
**Coverage:** ~36% of applicants (`remittance_receiving = True` in profiles)

#### Key Columns for Income Estimation

| Column | Type | Relevance |
|---|---|---|
| `applicant_id` | STRING | Join key |
| `transfer_date_ad` | DATE | Monthly aggregation |
| `received_date_ad` | DATE | Actual receipt date |
| `amount_nrs` | FLOAT | NRs amount received (clean, no noise) |
| `amount_foreign_currency` | FLOAT | Source currency amount |
| `foreign_currency_code` | STRING | Source currency (may have noise) |
| `exchange_rate` | FLOAT | Conversion rate applied |
| `sender_country_code` | STRING | Geographic origin of remittance |
| `transfer_service` | STRING | IME Money, Prabhu Money, etc. |
| `disbursement_mode` | STRING | How funds were received |
| `name_match_score` | FLOAT | Data quality indicator |
| `_noise_name_corrupt` | BOOLEAN | 12% of records: sender name truncated |
| `_noise_wrong_currency` | BOOLEAN | 2.5%: wrong currency code |
| `_noise_impossible_rate` | BOOLEAN | 2%: exchange rate 10× actual |
| `_noise_duplicate` | BOOLEAN | 2.5%: exact duplicate rows |

#### Data Quality Filters Required

Before using remittance data for income estimation:

1. **Deduplicate:** Remove rows where `_noise_duplicate = True` (or detect independently in hidden test)
2. **Fix impossible exchange rates:** `exchange_rate` that is 10× actual will massively inflate `amount_nrs` — detect and correct using reference rates:
   - QAR: ~39 NRs | SAR: ~35.5 NRs | AED: ~36.8 NRs | MYR: ~29.5 NRs | USD: ~133.5 NRs | INR: ~1.6 NRs
3. **Soft-flag low name match scores:** `name_match_score < 0.80` may indicate a different sender; treat with lower confidence weight
4. **Ignore wrong currency codes:** `_noise_wrong_currency = True` rows may have unreliable `amount_nrs` if computed from wrong rate

#### Sender Country Distribution

| Country | Code | Share |
|---|---|---|
| Qatar | QA | 38% |
| Saudi Arabia | SA | 24% |
| UAE | AE | 14% |
| Malaysia | MY | 11% |
| India | IN | 7% |
| South Korea | KR | 3% |
| USA | US | 2% |
| Japan | JP | 1% |

#### Income Signal Interpretation

- Remittances are **highly regular** for most recipients (typically monthly or bi-monthly)
- Use `amount_nrs` summed over the 6-month period and divided by 6 for monthly average
- Higher `name_match_score` → higher confidence weight
- `disbursement_mode`:
  - `bank_deposit` (65%): Most traceable; highest confidence
  - `mobile_wallet` (25%): Traceable via eSewa/Khalti
  - `cash_pickup` (10%): Least verifiable; lower confidence weight

---

### 2.3 Cooperative Sales (`cooperative_sales.csv` + `cooperative_members.csv`)

Agricultural commodity sale records for applicants who are cooperative members (~41% of applicants). This source captures **seasonal agricultural income** for farmers, dairy producers, and vegetable growers.

**Files:**
- `structured/cooperative_members.csv` — membership metadata
- `structured/cooperative_sales.csv` — individual sale transactions

**Coverage:** ~41% of applicants (cooperative members), minus ~3% ghost memberships

#### Key Columns from `cooperative_members.csv`

| Column | Relevance |
|---|---|
| `applicant_id` | Join key |
| `cooperative_id` | Link to sales |
| `cooperative_type` | Determines commodity type and expected income range |
| `membership_year_bs` | Tenure; longer = more reliable member |
| `share_count` | Investment size; proxy for economic standing |
| `last_annual_dividend_nrs` | Direct income: dividend paid most recent year |
| `outstanding_loan_nrs` | Liability; may indicate cash-flow stress |
| `coop_loan_repayment_status` | `overdue` = negative signal |
| `membership_status` | `suspended` = negative; `active` = positive |

#### Key Columns from `cooperative_sales.csv`

| Column | Relevance |
|---|---|
| `applicant_id` | Join key |
| `cooperative_id` | Link to membership |
| `cooperative_type` | Context for income type |
| `sale_year_bs` | Temporal reference |
| `season` | `Kharif` / `Rabi` / `Annual` — for annualization |
| `commodity_en` | Commodity sold |
| `quantity` | Volume of produce |
| `rate_nrs_per_unit` | Price per unit (NRs) |
| `total_amount_nrs` | Primary income figure for that sale |

#### Commodity Price Reference

| Cooperative Type | Commodity | Rate (NRs/unit) |
|---|---|---|
| agricultural | Paddy | 35/kg |
| agricultural | Vegetables | 42/kg |
| agricultural | Maize | 28/kg |
| agricultural | Wheat | 32/kg |
| dairy | Milk | 90/L |
| dairy | Ghee | 1,200/kg |
| dairy | Curd | 180/kg |
| vegetable | Tomato | 55/kg |
| vegetable | Potato | 28/kg |
| vegetable | Cabbage | 35/kg |
| vegetable | Onion | 60/kg |
| coffee_tea | Coffee Beans | 400/kg |
| coffee_tea | Tea Leaves | 120/kg |
| savings_credit | — | No commodity sales |

#### Annualizing Seasonal Sales

Cooperative sales are recorded **per season**, not per month. To compute a monthly income figure:

- **Kharif season** (monsoon, June–November): ~6 months
- **Rabi season** (winter, October–March): ~6 months
- **Annual** (e.g., dairy — year-round): Divide total by 12

```python
# Monthly income from cooperative sales (example)
sales_monthly = sales.groupby('applicant_id')['total_amount_nrs'].sum() / 6
```

> **Ghost Membership Warning:** ~3% of applicants have `cooperative_member = True` in their profile but **no row in `cooperative_members`**. These are cross-table integrity errors. Do not assume zero sales — flag them as data quality issues and reduce confidence accordingly.

---

### 2.4 Utility Payments (`utility_payments.parquet`)

Monthly NEA electricity and Ncell mobile bill payment records for ~98% of applicants. While utility bills do not directly measure income, **payment regularity is a proven proxy for financial discipline and income stability** in alternative credit models.

**File:** `structured/utility_payments.parquet`  
**Load:** `pd.read_parquet("structured/utility_payments.parquet")`  
**Coverage:** ~98% of applicants (strongest coverage of all tables)

#### Key Columns for Income / Creditworthiness

| Column | Relevance |
|---|---|
| `applicant_id` | Join key |
| `utility_type` | `electricity` or `mobile` |
| `provider` | `NEA` or `Ncell` |
| `billing_period_ad` | Monthly aggregation |
| `bill_amount_nrs` | Proxy for consumption level → income proxy |
| `units_consumed` | Electricity usage (kWh); higher = wealthier household |
| `days_late` | Payment punctuality |
| `cumulative_on_time_rate` | **Key income stability signal** |
| `outstanding_arrears_nrs` | Unpaid debt; negative signal |
| `_noise_forced_unpaid` | 15%: artificially set to unpaid — highest noise rate |
| `_noise_negative_bill` | 0.8%: negative bill amounts |
| `_noise_zero_units` | 1.2%: zero units consumed despite non-zero bill |

#### On-Time Payment Rate Interpretation

The `cumulative_on_time_rate` is the most valuable creditworthiness signal in this table:

| Rate | Interpretation | Income Confidence Weight |
|---|---|---|
| ≥ 0.90 | Excellent payer | +High |
| 0.70–0.89 | Good payer | +Moderate |
| 0.50–0.69 | Moderate payer | Neutral |
| < 0.50 | Poor payer | −Negative |

> **Critical Noise Alert:** `_noise_forced_unpaid` affects **15% of records** — the highest noise rate of any column in the dataset. A bill marked as unpaid may have been artificially set that way. In the hidden test set, this label is removed. Build noise-robust payment regularity features (e.g., use median on-time rate rather than raw rate).

#### Electricity as Income Proxy

Monthly electricity consumption (`units_consumed`) correlates with household economic activity:
- Urban, wealthier households consume more electricity (refrigerators, ACs, computers)
- Agricultural households show seasonal spikes (irrigation pumps during Kharif)
- Rule: `bill_amount_nrs ≈ units_consumed × 7.30` — use this to detect and fix zero-units noise

---

### 2.5 Applicant Profile Metadata (`applicant_profiles.csv`)

While not transactional, several profile fields are useful **prior signals** for income estimation before any transaction data is aggregated.

**File:** `structured/applicant_profiles.csv`  
**Coverage:** 100% of applicants (master table)

#### Relevant Profile Fields for Income Priors

| Column | Relevance |
|---|---|
| `applicant_id` | Primary key |
| `occupation_en` | Direct income category indicator |
| `household_size` | Affects per-capita income and serviceability |
| `land_area_ropani` | Asset indicator; >0 = land owner |
| `rural_urban` | Urban = higher base income; rural = seasonal |
| `has_esewa_account` | Wallet data availability flag |
| `has_khalti_account` | Wallet data availability flag |
| `remittance_receiving` | Remittance data availability flag |
| `cooperative_member` | Cooperative data availability flag |
| `kyc_tier` | `full` tier applicants have more verified income proof |

#### Occupation-Based Income Priors

Use `occupation_en` to set baseline income expectations before aggregating transaction data:

| Occupation | Typical Monthly Income (NRs) | Primary Signal Source |
|---|---|---|
| `Government Employee` | 30,000–80,000 | (No payslip in dataset; use wallet patterns) |
| `Business Owner` | 20,000–100,000 | Mobile money merchant inflows |
| `Teacher` | 20,000–50,000 | Wallet patterns |
| `Nurse/Health Worker` | 18,000–45,000 | Wallet patterns |
| `Small Trader` | 10,000–40,000 | Merchant QR receipts |
| `Driver` | 8,000–25,000 | P2P transfers, wallet topups |
| `Farmer` | 5,000–20,000 (seasonal) | Cooperative sales |
| `Artisan` | 6,000–18,000 | Wallet topups, P2P |
| `Remittance Dependent` | 10,000–35,000 | Remittance records |
| `Daily Wage Worker` | 4,000–12,000 | Irregular wallet topups |

---

## 3. Output Fields

The Income Agent produces exactly two output fields, stored in `loan_applications.csv`:

### `income_agent_monthly_est`

| Property | Detail |
|---|---|
| **Column name** | `income_agent_monthly_est` |
| **Type** | INTEGER |
| **Nullable** | No |
| **Range** | 3,000 – 200,000 (NRs) |
| **Unit** | Nepali Rupees (NRs) per month |
| **Description** | Estimated monthly income aggregated from all available alternative data sources. This is a **model output**, not self-reported income. |

### `income_confidence`

| Property | Detail |
|---|---|
| **Column name** | `income_confidence` |
| **Type** | FLOAT |
| **Nullable** | No |
| **Range** | 0.05 – 0.97 |
| **Description** | Confidence score (0–1) representing certainty in the income estimate. Lower scores reflect data sparsity or signal inconsistency. |

---

## 4. Income Signal Taxonomy

The Income Agent must intelligently combine signals from multiple sources. Below is the full taxonomy of available signals and their reliability:

```
INCOME SIGNALS
│
├── DIRECT INCOME SIGNALS (High Confidence Weight)
│   ├── Remittance receipts in mobile_money_transactions
│   │   └── transaction_type = "remittance_receipt" AND direction = "credit"
│   ├── Remittance records (amount_nrs, cleaned)
│   │   └── remittance_records.amount_nrs (after noise filtering)
│   └── Cooperative commodity sales
│       └── cooperative_sales.total_amount_nrs (annualized)
│
├── PROXY INCOME SIGNALS (Moderate Confidence Weight)
│   ├── Wallet top-ups
│   │   └── transaction_type = "wallet_topup" AND direction = "credit"
│   ├── P2P transfers received (net positive)
│   │   └── transaction_type = "p2p_transfer" AND direction = "credit"
│   ├── Cooperative dividend
│   │   └── cooperative_members.last_annual_dividend_nrs / 12
│   └── Electricity consumption level
│       └── utility_payments.units_consumed (economic activity proxy)
│
├── CREDITWORTHINESS SIGNALS (Indirect — Adjusts Confidence)
│   ├── Utility on-time payment rate
│   │   └── utility_payments.cumulative_on_time_rate
│   ├── Cooperative loan repayment status
│   │   └── cooperative_members.coop_loan_repayment_status
│   └── Outstanding arrears
│       └── utility_payments.outstanding_arrears_nrs
│
└── PRIOR / METADATA SIGNALS (Baseline Only)
    ├── Occupation category
    │   └── applicant_profiles.occupation_en
    ├── Land ownership
    │   └── applicant_profiles.land_area_ropani > 0
    └── Rural/urban classification
        └── applicant_profiles.rural_urban
```

---

## 5. Confidence Scoring Logic

The `income_confidence` score is determined by three factors:

### Factor 1: Number of Independent Income Signals

Each independent data source that contributes a signal increases confidence:

| Signal Available | Confidence Boost |
|---|---|
| Mobile wallet data (eSewa/Khalti) | + |
| Remittance records | + |
| Cooperative sales data | + |
| Multiple months of data (not just 1–2) | + |

- **1 source only:** Low confidence (< 0.40 likely)
- **2 sources:** Moderate confidence
- **3+ sources:** High confidence (> 0.70 possible)

### Factor 2: Signal Consistency Over Time

Low variance in monthly income estimates across the 6-month observation window increases confidence:

- **Consistent monthly amounts:** High confidence — stable income
- **High variability:** Lower confidence — seasonal or irregular income
- **Seasonal workers** (e.g., farmers) will show natural variability during Kharif/Rabi cycles — penalize less if seasonality is explained by occupation

### Factor 3: Data Recency

More recent data is weighted higher:
- Transactions from months 5–6 (June 2024): Full weight
- Transactions from months 1–2 (January–February 2024): Reduced weight
- Older cooperative sales (sale_year_bs = 2078–2079): Lowest weight

### Confidence Thresholds and Their Downstream Impact

| Confidence Score | Downstream Effect |
|---|---|
| < 0.40 | Likely `reject` decision from Decision Agent |
| 0.40 – 0.70 | Approved with **15% haircut** on loan amount (`approved_amount_nrs = requested × 0.85`) |
| > 0.70 | Full loan amount may be approved (if other criteria met) |

---

## 6. Decision Thresholds

The Income Agent's outputs feed into two critical downstream rules:

### Loan-to-Income (LTI) Ratio — NRB Rule `NRB-LTI-002`

```
LTI = requested_amount_nrs / income_agent_monthly_est
```

- **Limit:** LTI must not exceed **36×** monthly income for agricultural loans
- **Violation:** `LTI_EXCEEDED` appears in `compliance_flags`
- **Impact:** If your income estimate is too low, borderline loans will trigger this rule → fewer approvals
- **Impact:** If your income estimate is too high, LTI violations will be missed → compliance failure

### Haircut Rule

When `income_confidence < 0.70`:
```
approved_amount_nrs = requested_amount_nrs × 0.85
```
This means `approved_amount_nrs < requested_amount_nrs` in the output — do not treat this as an error.

### KYC Loan Ceiling Interaction

Income alone does not determine approval — KYC tier also caps the maximum loan:

| KYC Tier | Max Loan (NRs) | Income Agent Relevance |
|---|---|---|
| `basic` | 1,00,000 | LTI ratio applies within this ceiling |
| `mid` | 5,00,000 | LTI ratio applies within this ceiling |
| `full` | No ceiling | Income estimate is the binding constraint |

---

## 7. Data Joins & Keys

All tables join on `applicant_id` (format: `AP-NNNNNN`, e.g. `AP-050234`).

```python
import pandas as pd

# Load all income-relevant tables
profiles = pd.read_csv("structured/applicant_profiles.csv")
loans    = pd.read_csv("structured/loan_applications.csv")
tx       = pd.read_parquet("structured/mobile_money_transactions.parquet")
rem      = pd.read_parquet("structured/remittance_records.parquet")
util     = pd.read_parquet("structured/utility_payments.parquet")
coop_mem = pd.read_csv("structured/cooperative_members.csv")
coop_sal = pd.read_csv("structured/cooperative_sales.csv")

# Join example: get all income data for one applicant
ap = "AP-050234"
ap_tx   = tx[tx["applicant_id"] == ap]
ap_rem  = rem[rem["applicant_id"] == ap]
ap_util = util[util["applicant_id"] == ap]
ap_mem  = coop_mem[coop_mem["applicant_id"] == ap]
ap_sal  = coop_sal[coop_sal["applicant_id"] == ap]
```

### Cooperative Join Chain

Cooperative sales require a two-table join:
```
cooperative_sales.applicant_id → cooperative_members.applicant_id
cooperative_sales.cooperative_id → cooperative_members.cooperative_id
```

---

## 8. Data Quality Issues to Handle

The Income Agent must be robust to injected noise. Below is every data quality issue that directly affects income estimation:

### Mobile Money Transactions

| Issue | Column | Rate | Fix |
|---|---|---|---|
| Comma-formatted amounts | `amount_nrs` | 3% | `str.replace(",", "")` then `pd.to_numeric(..., errors="coerce")` |
| Future timestamps (2026) | `transaction_date` | 0.8% | Filter: `transaction_date <= "2024-06-30"` |
| Fraud anomalies (midnight_round, velocity_burst) | `_noise_anomaly_flag` | 1.7% | Exclude from income computation |
| NULL counterparty | `counterparty_category` | 4% | Use transaction_type as fallback for categorization |

### Remittance Records

| Issue | Column | Rate | Fix |
|---|---|---|---|
| Truncated sender names (last 2 chars dropped) | `sender_name` | 12% | Use `name_match_score` < 0.80 as quality flag; down-weight confidence |
| Wrong currency code (shows USD regardless) | `foreign_currency_code` | 2.5% | Verify against `sender_country_code` |
| Impossible exchange rate (10× actual) | `exchange_rate` | 2% | Detect outliers using reference rates; recalculate `amount_nrs` |
| Exact duplicate rows | entire row | 2.5% | Deduplicate before aggregation |

### Cooperative Data

| Issue | Description | Rate | Fix |
|---|---|---|---|
| Ghost memberships | `cooperative_member = True` in profile, no row in cooperative_members | 3% of members | Cross-check before join; flag as data quality issue |
| Members of `savings_credit` coops have no sales | Not a noise issue — by design | ~20% of coop members | Expect zero `cooperative_sales` rows; use dividend only |

### Utility Payments

| Issue | Column | Rate | Fix |
|---|---|---|---|
| Artificially set to unpaid | `payment_date_ad` = NULL | 15% of records | **Highest noise rate.** Use median on-time rate; flag outliers |
| Negative bill amounts | `bill_amount_nrs` | 0.8% | Take absolute value or drop |
| Zero units with non-zero bill | `units_consumed` | 1.2% | Impute: `units = bill_amount_nrs / 7.30` |
| Duplicate rows | entire row | 1.5% | Deduplicate |

---

## 9. Feature Engineering Guide

Recommended features to derive for income estimation:

### From Mobile Money Transactions

```python
# Clean amounts first
tx["amount_clean"] = pd.to_numeric(
    tx["amount_nrs"].astype(str).str.replace(",", "").str.replace("Rs. ", ""),
    errors="coerce"
)

# Filter: only clean, credit transactions for income
income_tx = tx[
    (tx["direction"] == "credit") &
    (tx["_noise_anomaly_flag"] == False) &
    (tx["is_festival_period"] == False) &
    (tx["transaction_type"].isin(["remittance_receipt", "wallet_topup"]))
]

# Monthly average credit inflows
monthly_income_wallet = (
    income_tx.groupby("applicant_id")["amount_clean"].sum() / 6
)

# Transaction frequency (activity signal)
tx_frequency = tx.groupby("applicant_id")["transaction_id"].count()

# Income regularity (std dev of monthly credits — lower = more stable)
tx["month"] = pd.to_datetime(tx["transaction_date"]).dt.month
monthly_by_user = income_tx.groupby(["applicant_id", "month"])["amount_clean"].sum()
income_std = monthly_by_user.groupby("applicant_id").std()
```

### From Remittance Records

```python
# Detect impossible exchange rates (>5× reference)
REFERENCE_RATES = {"QA": 39, "SA": 35.5, "AE": 36.8, "MY": 29.5, "US": 133.5, "IN": 1.6}

# Clean remittance amount
rem_clean = rem[rem["_noise_duplicate"] == False].copy()
rem_clean["amount_nrs_clean"] = rem_clean.apply(
    lambda r: r["amount_foreign_currency"] * REFERENCE_RATES.get(r["sender_country_code"], r["exchange_rate"])
    if r["_noise_impossible_rate"] else r["amount_nrs"],
    axis=1
)

# Monthly remittance income
monthly_remittance = rem_clean.groupby("applicant_id")["amount_nrs_clean"].sum() / 6
```

### From Cooperative Sales

```python
# Annualize sales to monthly figures
coop_sal["monthly_income"] = coop_sal.apply(
    lambda r: r["total_amount_nrs"] / 6 if r["season"] in ["Kharif", "Rabi"]
              else r["total_amount_nrs"] / 12,  # Annual (dairy)
    axis=1
)

monthly_coop_income = coop_sal.groupby("applicant_id")["monthly_income"].sum()

# Add dividend income
coop_mem["monthly_dividend"] = coop_mem["last_annual_dividend_nrs"] / 12
```

### From Utility Payments

```python
# Use median on-time rate (robust to noise)
util_clean = util[util["_noise_forced_unpaid"] == False]
ontime_rate = util_clean.groupby("applicant_id")["cumulative_on_time_rate"].median()

# Average electricity bill (economic activity proxy)
elec = util_clean[util_clean["utility_type"] == "electricity"]
avg_elec_bill = elec.groupby("applicant_id")["bill_amount_nrs"].mean()
```

### Final Income Aggregation

```python
# Combine all income signals
income_df = pd.DataFrame(index=profiles["applicant_id"])
income_df["wallet_income"]    = monthly_income_wallet
income_df["remittance_income"] = monthly_remittance
income_df["coop_income"]      = monthly_coop_income + coop_mem.set_index("applicant_id")["monthly_dividend"]

# Count available signals per applicant
income_df["signal_count"] = income_df[
    ["wallet_income", "remittance_income", "coop_income"]
].notna().sum(axis=1)

# Weighted average or sum (depending on your model)
income_df["income_est"] = income_df[
    ["wallet_income", "remittance_income", "coop_income"]
].sum(axis=1, min_count=1)

# Confidence from signal count + on-time rate
income_df["confidence"] = (income_df["signal_count"] / 3) * 0.7 + ontime_rate * 0.3
income_df["confidence"] = income_df["confidence"].clip(0.05, 0.97)
```

---

## 10. Evaluation Metric

The Income Agent is evaluated independently with:

### Income RMSE

```
Income RMSE = √( mean( (income_agent_monthly_est − ground_truth_monthly_income)² ) )
```

| Metric | Target | Notes |
|---|---|---|
| **Income RMSE** | **< NRs 5,000** | vs. ground truth monthly income in labels |

This means your estimate must be within approximately **NRs 5,000/month** of the true income on average. Given the income range of NRs 3,000–200,000, this is roughly a ±5–15% error tolerance for mid-range incomes.

### Downstream Impact on Credit Metrics

The income estimate also indirectly affects:
- **Decision Accuracy** (> 0.78): Wrong income → wrong LTI → wrong decision
- **NRB Compliance Rate** (= 1.00): Income estimate that misses LTI violations = compliance failure
- **Macro F1** (> 0.72): Income confidence affects `approve` vs. `conditional` vs. `refer` classification

---

## 11. Nepal Context & Domain Notes

### Bikram Sambat (BS) Calendar

Nepal's official calendar is approximately 56–57 years ahead of Gregorian (AD). All government documents (Lalpurja, citizenship) use BS exclusively.

| Gregorian (AD) | Bikram Sambat (BS) |
|---|---|
| 2024 | 2081 |
| 2023 | 2080 |

When computing tenure (e.g., cooperative membership duration), use the BS year: `2081 − membership_year_bs`.

### Agricultural Seasons Relevant to Income

| Season | BS Months | Gregorian Approx. | Crops |
|---|---|---|---|
| Kharif (खरिफ) | Ashadh–Kartik (3–7) | June–November | Paddy, Maize |
| Rabi (रबी) | Kartik–Chaitra (7–12) | October–March | Wheat, Vegetables |
| Festival Season | Ashwin–Kartik (6–7) | October | Dashain / Tihar spending spike |

### Nepal's Remittance Economy

- Remittances = ~25% of Nepal's GDP
- Primary sending countries: Qatar, Saudi Arabia, UAE (Gulf Corridor, ~76% combined), Malaysia (11%), India (7%)
- Transfer services: IME Money (dominant, India corridor), Prabhu Money (Gulf corridor), Himal Remit (Korea/Japan)
- Typical disbursement: monthly or bi-monthly

### Mobile Wallet Ecosystem

- **eSewa** (Fonepay network): ~58% of dataset users. Largest wallet. Supports bill payments, merchant QR, P2P, remittance.
- **Khalti**: ~32% of dataset users. Popular with younger urban users.
- Some applicants have both wallets. In the dataset, `esewa` is preferred when both exist.

### Cooperatives (सहकारी / Sahakari)

Agricultural cooperatives play a major financial role in rural Nepal:
- Members sell produce collectively at better prices
- Receive annual dividends on shares
- Can borrow at cooperative rates (lower than bank rates)
- Regulated by the Department of Cooperatives

**Income estimation note:** A member of a `savings_credit` cooperative has **no commodity sales** — their income contribution from the cooperative comes only via dividends.

---

## 12. Code Snippets

### Loading All Income-Relevant Tables

```python
import pandas as pd

profiles  = pd.read_csv("structured/applicant_profiles.csv")
loans     = pd.read_csv("structured/loan_applications.csv")
tx        = pd.read_parquet("structured/mobile_money_transactions.parquet")
rem       = pd.read_parquet("structured/remittance_records.parquet")
util      = pd.read_parquet("structured/utility_payments.parquet")
coop_mem  = pd.read_csv("structured/cooperative_members.csv")
coop_sal  = pd.read_csv("structured/cooperative_sales.csv")
```

### Selective Column Load (Faster for Large Parquets)

```python
tx_income = pd.read_parquet(
    "structured/mobile_money_transactions.parquet",
    columns=["applicant_id", "transaction_type", "amount_nrs",
             "direction", "transaction_date", "is_festival_period",
             "_noise_anomaly_flag"]
)
```

### Cleaning Transaction Amounts

```python
tx["amount_nrs_clean"] = pd.to_numeric(
    tx["amount_nrs"].astype(str)
      .str.replace(",", "")
      .str.replace("Rs. ", ""),
    errors="coerce"
)
```

### Detecting Impossible Exchange Rates

```python
COUNTRY_TO_REFERENCE_NRS = {
    "QA": 39.0, "SA": 35.5, "AE": 36.8,
    "MY": 29.5, "US": 133.5, "IN": 1.6,
    "KR": 0.10, "JP": 0.89
}

def is_rate_impossible(row):
    ref = COUNTRY_TO_REFERENCE_NRS.get(row["sender_country_code"])
    if ref is None:
        return False
    return row["exchange_rate"] > ref * 3  # 3× threshold

rem["rate_suspicious"] = rem.apply(is_rate_impossible, axis=1)
```

### Ghost Membership Detection

```python
# Applicants marked as coop members in profile
declared_members = set(
    profiles[profiles["cooperative_member"] == True]["applicant_id"]
)
# Applicants with an actual row in cooperative_members
actual_members = set(coop_mem["applicant_id"])

# Ghost memberships
ghost = declared_members - actual_members
print(f"Ghost memberships detected: {len(ghost)}")
```

### Computing Income Confidence

```python
def compute_confidence(row, ontime_rates):
    signals = 0
    if pd.notna(row.get("wallet_income")): signals += 1
    if pd.notna(row.get("remittance_income")): signals += 1
    if pd.notna(row.get("coop_income")): signals += 1

    signal_score = signals / 3.0
    ontime = ontime_rates.get(row["applicant_id"], 0.5)

    confidence = (signal_score * 0.7) + (ontime * 0.3)
    return round(min(max(confidence, 0.05), 0.97), 4)
```

---

## Quick Reference Card

| Item | Value |
|---|---|
| Primary output field | `income_agent_monthly_est` (INTEGER, NRs/month) |
| Confidence field | `income_confidence` (FLOAT, 0.05–0.97) |
| Income RMSE target | < NRs 5,000 |
| Confidence → haircut threshold | < 0.70 → 15% haircut |
| Confidence → reject threshold | < 0.40 → likely reject |
| LTI cap (NRB rule) | 36× monthly income |
| Data observation window | 6 months (Jan–Jun 2024) |
| Join key across all tables | `applicant_id` (format: `AP-NNNNNN`) |
| Highest noise column | `_noise_forced_unpaid` (15% of utility records) |
| Ghost membership rate | ~3% of declared cooperative members |
| Fraud transaction rate | ~1.7% of mobile money transactions |

---

*This document is derived from the GIBL AI/ML Hackathon 2026 — Track A Data Description & Technical Reference Manual.*  
*Focus: Income Agent design, data sources, feature engineering, and evaluation.*