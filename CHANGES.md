# Changes since the hackathon version

Baseline: commit `1e027fb` (2026-07-06), the code as submitted to the GIBL AI/ML Hackathon 2026.
This release (0.2.0) is the version described in the paper.

## Bugs fixed

These changed results, so numbers from the hackathon materials in `docs/hackathon-2026/` are
not comparable with the paper.

1. **Remittance dates were dropped.** `_clean_remittance_data` copied a `date` field that the
   Track A remittance records do not have (they carry `transfer_date_ad`). Every remittance lost
   its date, so remittances never reached the monthly income profile, and
   `remittance_monthly_avg` divided all transfers by a single month (about six times too high
   for a six-month history). The cleaner now keeps the transfer and received dates, sender
   country, currency and name-match score.
2. **Cooperative sales years were read as Gregorian.** Sales are recorded by Bikram Sambat year
   (for example 2080), which was turned into the Gregorian date 2080-xx-01.
   `cooperative_monthly_sales` also summed every year on record and divided by 12. Sales are
   now treated as annual figures per BS year: monthly income is the mean annual total
   divided by 12.
3. **Imputed income for farmers.** When observed income was below NPR 3,000, farmers were
   assigned NPR 20,000 a month and daily-wage workers NPR 15,000 (`OCCUPATION_FLOORS`), and
   incomes above NPR 200,000 were capped. The estimate is now left as observed and flagged
   (`LOW_OBSERVED_INCOME`, `INCOME_ANOMALY_HIGH`).
4. **KYC limit of zero.** A missing KYC tier became the string `"none"`, whose limit defaulted
   to 0, so every request from such an applicant exceeded its limit. The tier is now read from
   `applicant_profiles`, and a missing tier uses the `default_tier` in the policy file.
5. **Existing-loan count held an amount.** The loan form stored the existing loan *amount* in
   `existing_loan_count`, so in the live API the three-loan rule fired for anyone who reported
   a loan of NPR 3 or more. The form now has separate fields for the count and the monthly
   repayment.
6. **Inverted credit score.** The score was `300 + 550 × probability of the predicted class`,
   so a confident prediction of "reject" produced a high score. It is now a
   points-to-double-the-odds scaling of the probability of default, monotone by construction.
7. **Scorer failed on every call.** `model_config.json` listed 64 features while the model
   expected 60; the error path returned a score of 300. The new scorer checks the feature
   count when it loads.
8. **Self-declared screening flags.** `aml_flag` and `nrb_blacklist_flag` were fields on the
   applicant's own form. They are now read from the application record (simulated screening
   results in Track A). A missing value means "not screened" and sends the application to
   manual review (`if_missing: refer`); it is never treated as a pass.
9. **Fabricated audit and dashboard values.** The audit endpoint filled missing values with
   constants (trust 0.92, confidence 0.95, fixed factor weights) and the officer dashboard
   showed placeholder SHAP drivers and IMR, DTI and LTI values. The endpoint now returns the
   entries of the hash-chained audit log, and the dashboard shows "Not available".
10. **Circular training label.** The hackathon model learned Track A's `final_decision`, which
    is a deterministic function of other fields (a 22-leaf tree reproduces it with 99.99%
    accuracy; `experiments/e1_label_circularity.py`). The new model predicts repayment
    outcomes (default) instead.
11. **Results depended on the run date.** Cooperative tenure used `datetime.now().year + 57`, and
    future-dated records were judged against the computer's clock. Tenure is now measured
    against the BS year of the application, and records against an as-of date
    (`INCOME_AS_OF_DATE`; files mode and the experiments use 30 June 2024, the end of the Track A
    record window).
12. **Wallet top-ups became income from random sources.** Wallet credits were grouped by
    `counterparty_category`, which in Track A is unrelated to the transaction type, so a top-up
    could count as "telecom" or "grocery" income and the number of income sources was inflated.
    Credits are now grouped by transaction type: remittance receipts join the remittance
    source, and top-ups (an income proxy in the data manual that can include the applicant's own
    savings) form a separate source with a lower prior confidence.
13. **Cleaning used the generator's hidden labels.** Duplicates, currency errors, anomalies and
    unpaid bills were identified from the `_noise_*` columns, which the organisers remove from
    their hidden test split and which a lender would not have. Cleaning now uses only rules a
    lender could apply: repeated rows, exchange rates outside reference ranges, comma-formatted
    amounts, negative bills and records dated after the as-of date. Wallet transactions that the
    generator labelled as fraud patterns are kept as ordinary transactions.
14. **A duplicate feature defeated a monotone constraint.** `elec_on_time_rate` always equals
    `overall_on_time_rate`, and only the latter was constrained. The duplicate is no longer a
    model input (32 features).
15. **Applicant-entered bureau score.** The loan form took the credit bureau score from the
    applicant, and the model used it. The API no longer accepts it; the Credit Information
    Bureau lookup is not implemented, so the field stays empty.
16. **Loan form.** The frontend labelled the monthly-repayment field as the total outstanding
    loan amount and did not send the existing-loan count or declared income. Both fields were
    added and the label corrected. The lock file was out of date (`npm ci` failed); it was
    refreshed, `.env.example` added and four type errors fixed, so `npm run build` and
    `npm run check` pass.

## Added

- **Policy as configuration.** `config/policy_rules.yaml` and `app/services/policy_engine.py`:
  eight rules, each with a provenance label (hackathon rule, hackathon field, regulator
  reported, design) and an action (veto, refer, flag). A hash of the file is written with every
  decision.
- **Declared-versus-observed income check.** IMR = declared / observed monthly income,
  computed only when observed income is at least NPR 1,000. Outside 0.3–3.0 (5.0 for
  households where remittances are most of observed income) the case is referred for review.
  Declared income is a new optional field on the loan form.
- **Affordability check and counter-offer.** Debt service to income (DSTI) with an annuity
  instalment at an assumed 14% rate, capped at 50%. When the cap is exceeded the Decision
  Agent reports the largest affordable amount and the tenure needed for the full amount.
- **Probability-of-default model.** Gradient boosting with monotone constraints, trained on
  repayment outcomes by `experiments/e2_outcome_model.py`, saved as XGBoost JSON (no pickle)
  with `feature_spec.json`. SHAP values give the drivers shown to the credit officer. Gender,
  marital status, age and location are not model inputs.
- **Decision Agent.** Outcomes are approve, conditional, refer and decline. Only a veto rule
  declines; thin files (income confidence below 0.40) go to manual review instead of being
  rejected.
- **Audit log.** `app/services/audit.py` appends one hash-chained entry per agent step. The
  decision entry records the policy and model versions, the Income Agent's flags and any
  unscreened rules. `verify()` reports the first edited entry and returns the latest hash
  ("head"): editing an entry is detected unless every later entry is rewritten, and deleting
  entries from the end is detected only by comparing the head with a copy kept elsewhere.
  The model version hashes both `model.json` and `feature_spec.json`.
  `GET /admin/audit/{application_id}` reads the log.
- **Offline mode.** `DATA_BACKEND=files` runs the pipeline and API on the Track A files
  without PostgreSQL; `scripts/run_offline.py` scores applications from the command line.
- **Experiments.** `experiments/` reproduces every number and figure in the paper
  (`run_all.py`).
- **Tests.** 41 tests in `tests/` (policy engine, income agent regressions, decision rules,
  audit tamper detection, in-memory backend, scoring, API smoke test, end-to-end offline run).
  `pytest` at the repository root runs them; one needs the Track A data and is skipped
  without it.
- **Database migration.** `scripts/sql/2026_11_add_assessment_columns.sql` adds the columns
  for PD, SHAP drivers, model and policy versions, IMR, DSTI and loan-to-income.
- **Showcase site.** `showcase/` is a static one-page walkthrough of the pipeline on four
  invented applicants, with an in-browser check of the audit hashes; it deploys on Vercel
  without a build step. `scripts/make_showcase_examples.py` runs the invented applicants
  through the graph and writes `showcase/examples.json`; no Track A records are used.
- **Event media.** `docs/media/` holds photos and a short video from the onsite round
  (metadata stripped) and the showcase walkthrough used in the README.

## Changed

- The Document Agent (OCR) is not part of the pipeline. `app/agents/parser_agent.py` is kept
  as a prototype with a status note; the Tesseract path and Ollama model names are optional
  settings. No OCR accuracy is claimed.
- `POST /api/v1/loan/apply` returns the PD, risk grade, reasons, triggered rules, drivers,
  IMR, policy and model versions, and states that the output is a recommendation for a
  credit officer.
- Requirements are split into `requirements.txt` (core, pinned), `requirements-ocr.txt` and
  `requirements-dev.txt`. Python 3.13.
- A warning is logged when `JWT_SECRET_KEY` is not set; `scripts/legacy/test_apply.py` reads its
  token from an environment variable instead of a hard-coded string.
- The officer's reasons include the Income Agent's flags (very low or very high observed
  income).
- The compliance-references endpoint attaches rule sources from the policy file only when the
  file's version matches the one recorded for the application.
- `EXISTING_LOANS` is labelled as a design choice: the data manual's rule NRB-SEC-003 is a
  sector exposure limit with no threshold, and "three or more loans" is our reading.

## Moved or removed

- Hackathon model files and the unused rule-based scorecard: `legacy/` (not imported).
- Hackathon slides, documentation and team photo: `docs/hackathon-2026/`.
- Hackathon-era database, OCR and API scripts, and the tests that need PostgreSQL and Ollama:
  `scripts/legacy/` (see its README; the database scripts were already broken).
- Removed the manuscript PDF (the paper is distributed separately), the unused
  `app/services/income_categorizer.py`, `.DS_Store` files, and `tests/parser_agent_output.json`
  (OCR output of sample identity documents, with names and ID numbers).
