-- Optional columns written by the Score and Decision agents (PostgreSQL).
-- The pipeline works without them; the agents log a warning and skip these fields.
ALTER TABLE loan_applications ADD COLUMN IF NOT EXISTS pd_estimate DOUBLE PRECISION;
ALTER TABLE loan_applications ADD COLUMN IF NOT EXISTS shap_features TEXT;
ALTER TABLE loan_applications ADD COLUMN IF NOT EXISTS model_version TEXT;
ALTER TABLE loan_applications ADD COLUMN IF NOT EXISTS policy_version TEXT;
ALTER TABLE loan_applications ADD COLUMN IF NOT EXISTS income_mismatch_ratio DOUBLE PRECISION;
ALTER TABLE loan_applications ADD COLUMN IF NOT EXISTS dsr DOUBLE PRECISION;
ALTER TABLE loan_applications ADD COLUMN IF NOT EXISTS loan_to_income DOUBLE PRECISION;
