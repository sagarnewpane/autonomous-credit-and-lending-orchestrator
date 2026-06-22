-- Create all tables for the credit/lending dataset

-- Applicant profiles
CREATE TABLE IF NOT EXISTS applicant_profiles (
    applicant_id TEXT PRIMARY KEY,
    full_name_en TEXT,
    father_name_en TEXT,
    grandfather_name_en TEXT,
    citizenship_number TEXT,
    citizenship_date_bs TEXT,
    citizenship_office TEXT,
    dob_ad DATE,
    dob_bs TEXT,
    gender TEXT,
    marital_status TEXT,
    province_en TEXT,
    district_en TEXT,
    municipality_en TEXT,
    ward_no NUMERIC,
    phone_primary TEXT,
    occupation_en TEXT,
    occupation_np TEXT,
    education_level TEXT,
    household_size NUMERIC,
    land_area_ropani NUMERIC,
    has_esewa_account BOOLEAN,
    has_khalti_account BOOLEAN,
    esewa_account_id TEXT,
    khalti_account_id TEXT,
    primary_bank TEXT,
    remittance_receiving BOOLEAN,
    cooperative_member BOOLEAN,
    cooperative_id TEXT,
    kyc_tier TEXT,
    rural_urban TEXT,
    profile_created_date DATE
);

-- Cooperative members
CREATE TABLE IF NOT EXISTS cooperative_members (
    member_id TEXT PRIMARY KEY,
    applicant_id TEXT,
    cooperative_id TEXT,
    cooperative_name_en TEXT,
    cooperative_name_np TEXT,
    cooperative_type TEXT,
    province_en TEXT,
    district_en TEXT,
    municipality_en TEXT,
    membership_year_bs TEXT,
    share_count NUMERIC,
    share_value_each_nrs NUMERIC,
    total_share_value_nrs NUMERIC,
    last_annual_dividend_nrs NUMERIC,
    outstanding_loan_nrs NUMERIC,
    coop_loan_repayment_status TEXT,
    membership_status TEXT
);

-- Cooperative sales
CREATE TABLE IF NOT EXISTS cooperative_sales (
    sale_id TEXT PRIMARY KEY,
    applicant_id TEXT,
    cooperative_id TEXT,
    cooperative_type TEXT,
    province_en TEXT,
    district_en TEXT,
    municipality_en TEXT,
    sale_year_bs TEXT,
    season TEXT,
    commodity_en TEXT,
    unit TEXT,
    quantity NUMERIC,
    rate_nrs_per_unit NUMERIC,
    total_amount_nrs NUMERIC
);

-- Document registry
CREATE TABLE IF NOT EXISTS document_registry (
    document_id TEXT PRIMARY KEY,
    applicant_id TEXT,
    document_type TEXT,
    document_subtype TEXT,
    file_path TEXT,
    file_format TEXT,
    page_count NUMERIC,
    scan_dpi NUMERIC,
    ocr_complexity_tag TEXT,
    language_primary TEXT,
    language_secondary TEXT,
    has_stamp BOOLEAN,
    has_signature BOOLEAN,
    has_handwritten_fields BOOLEAN,
    is_rotated BOOLEAN,
    rotation_angle_degrees NUMERIC,
    upload_date_bs TEXT,
    ocr_model_baseline_cer NUMERIC,
    verified_by_agent BOOLEAN,
    verification_confidence NUMERIC,
    anomaly_flag BOOLEAN,
    ground_truth_path TEXT
);

-- Loan applications
CREATE TABLE IF NOT EXISTS loan_applications (
    application_id TEXT PRIMARY KEY,
    applicant_id TEXT,
    application_date_ad DATE,
    application_date_bs TEXT,
    loan_purpose TEXT,
    requested_amount_nrs NUMERIC,
    requested_tenure_months NUMERIC,
    province_en TEXT,
    district_en TEXT,
    municipality_en TEXT,
    ward_no NUMERIC,
    rural_urban TEXT,
    collateral_type TEXT,
    collateral_value_nrs NUMERIC,
    has_esewa_account BOOLEAN,
    has_khalti_account BOOLEAN,
    remittance_receiving BOOLEAN,
    cooperative_member BOOLEAN,
    cooperative_id TEXT,
    existing_loan_count NUMERIC,
    credit_bureau_score NUMERIC,
    nrb_blacklist_flag BOOLEAN,
    aml_flag BOOLEAN,
    doc_completeness_score NUMERIC,
    income_agent_monthly_est NUMERIC,
    income_confidence NUMERIC,
    credit_score NUMERIC,
    score_band TEXT,
    compliance_status TEXT,
    compliance_flags TEXT,
    final_decision TEXT,
    approved_amount_nrs NUMERIC,
    interest_rate_pct NUMERIC,
    interest_tier TEXT,
    processing_time_seconds NUMERIC,
    data_split TEXT
);

-- Mobile money transactions
CREATE TABLE IF NOT EXISTS mobile_money_transactions (
    transaction_id TEXT PRIMARY KEY,
    applicant_id TEXT,
    platform TEXT,
    transaction_date DATE,
    transaction_type TEXT,
    amount_nrs NUMERIC,
    direction TEXT,
    counterparty_category TEXT,
    geolocation_district TEXT,
    is_festival_period BOOLEAN
);

-- Parsed mobile wallet transactions
CREATE TABLE IF NOT EXISTS parsed_mobile_wallet_transactions (
    transaction_id TEXT PRIMARY KEY,
    applicant_id TEXT,
    platform TEXT,
    transaction_date DATE,
    transaction_type TEXT,
    amount_nrs NUMERIC,
    direction TEXT,
    counterparty_category TEXT,
    geolocation_district TEXT,
    is_festival_period BOOLEAN
);

-- Remittance records
CREATE TABLE IF NOT EXISTS remittance_records (
    remittance_id TEXT PRIMARY KEY,
    applicant_id TEXT,
    receiver_name_en TEXT,
    receiver_district_en TEXT,
    receiver_municipality_en TEXT,
    sender_name TEXT,
    sender_country_code TEXT,
    sender_country_name TEXT,
    sender_city TEXT,
    transfer_service TEXT,
    transfer_date_ad DATE,
    received_date_ad DATE,
    amount_foreign_currency NUMERIC,
    foreign_currency_code TEXT,
    amount_nrs NUMERIC,
    exchange_rate NUMERIC,
    transaction_fee_nrs NUMERIC,
    disbursement_mode TEXT,
    relationship_to_receiver TEXT,
    purpose_declared TEXT,
    name_match_score NUMERIC
);

-- Utility payments
CREATE TABLE IF NOT EXISTS utility_payments (
    payment_id TEXT PRIMARY KEY,
    applicant_id TEXT,
    province_en TEXT,
    district_en TEXT,
    municipality_en TEXT,
    ward_no NUMERIC,
    utility_type TEXT,
    provider TEXT,
    service_number TEXT,
    billing_period_bs TEXT,
    billing_period_ad TEXT,
    bill_amount_nrs NUMERIC,
    units_consumed NUMERIC,
    due_date_ad DATE,
    payment_date_ad DATE,
    payment_method TEXT,
    days_late NUMERIC,
    cumulative_on_time_rate NUMERIC,
    outstanding_arrears_nrs NUMERIC
);
