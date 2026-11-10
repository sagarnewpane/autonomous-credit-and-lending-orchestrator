export interface UserCreate {
	email: string;
	password: string;
}

export interface UserRead {
	id: number;
	email: string;
	applicant_id?: string;
	is_active: boolean;
	is_admin: boolean;
	created_at?: string;
}

export interface TokenResponse {
	access_token: string;
	refresh_token: string;
	token_type: string;
	expires_in: number;
	user?: UserRead;
}

export interface RefreshRequest {
	refresh_token: string;
}

export interface LoanApplicationData {
	application_id: string;
	applicant_name: string;
	user_id: string;
	loan_amount: number;
	loan_purpose: string;
	tenure_months: number;
	monthly_income: number;
	monthly_debt: number;
}

export interface LoanApplyResponse {
	message: string;
	application: LoanApplicationData;
}

export interface LoanDecision {
	application_id: string;
	decision: string;
	approved_amount_npr?: number;
	credit_score?: number;
	score_band?: string;
	risk_tier?: string;
	loan_purpose?: string;
	requested_amount_nrs?: number;
	requested_tenure_months?: number;
	income_agent_monthly_est?: number;
	collateral_type?: string;
	monthly_debt?: number;
	dsr?: number;
	imr?: number;
	lti?: number;
	interest_rate?: number;
	compliance_status?: string;
	shap_features?: ShapFeature[];
}

export interface ShapFeature {
	name: string;
	impact: number;
	direction: 'positive' | 'negative';
}

export interface LoanExplanation {
	application_id: string;
	credit_score?: number;
	score_band?: string;
	decision?: string;
	compliance_status?: string;
	compliance_flags?: string;
}

export interface ComplianceReference {
	clause: string;
	text: string;
	relevance_score: number;
}

export interface ComplianceReferencesResponse {
	application_id: string;
	references: ComplianceReference[];
}

export interface UserLoanHistory {
	user_id: string;
	applications: LoanApplicationRecord[];
	message: string;
}

export interface LoanApplicationRecord {
	application_id: string;
	applicant_id: string;
	loan_purpose: string;
	requested_amount_nrs: number;
	requested_tenure_months: number;
	income_agent_monthly_est: number;
	collateral_type: number;
	cooperative_member: boolean;
	final_decision?: string;
	credit_score?: number;
	score_band?: string;
	interest_tier?: string;
	application_date_ad?: string;
	created_at?: string;
}

export interface AdminLoanRecord extends LoanApplicationRecord {
	status?: string;
	compliance_status?: string;
	compliance_flags?: string;
	approved_amount_nrs?: number;
	risk_tier?: string;
}

export interface AdminReviewPayload {
	override_decision?: string;
	officer_notes?: string;
	[key: string]: unknown;
}

export interface AuditLog {
	id: number;
	agent: string;
	action: string;
	timestamp: string;
	output: Record<string, unknown>;
}

export interface AuditTrailResponse {
	application_id: string;
	audit_logs: AuditLog[];
	message: string;
}

export interface AdminStats {
	total_applications: number;
	approved: number;
	rejected: number;
	pending: number;
	flagged: number;
	modified: number;
	manual_review: number;
	total_requested_amount: number;
	total_approved_amount: number;
	average_credit_score: number;
	approval_rate: number;
	decision_distribution: Record<string, number>;
	recent_activity: AdminLoanRecord[];
}

export interface AdminUser {
	id: string;
	email: string;
	is_active: boolean;
	is_admin: boolean;
	created_at?: string;
	applicant_id?: string;
}

export interface AdminUserDetail {
	user: AdminUser;
	loan_applications: AdminLoanRecord[];
	message: string;
}

export interface AdminLoanDetail {
	application: AdminLoanRecord;
	message: string;
}

export interface BulkUpdatePayload {
	application_ids: string[];
	updates: Record<string, unknown>;
}

export interface BulkUpdateResponse {
	updated_count: number;
	updates: Record<string, unknown>;
	message: string;
}

export interface HealthCheckResponse {
	message: string;
	database: string;
}

export interface ApplicantProfile {
	applicant_id: string;
	full_name_en: string;
	father_name_en: string;
	grandfather_name_en: string;
	citizenship_number: string;
	citizenship_date_bs?: string;
	citizenship_office?: string;
	dob_ad: string;
	dob_bs: string;
	gender: string;
	marital_status: string;
	province_en?: string;
	district_en?: string;
	municipality_en?: string;
	ward_no?: number;
	phone_primary: string;
	occupation_en: string;
	occupation_np?: string;
	education_level: string;
	household_size: number;
	land_area_ropani?: number;
	has_esewa_account: boolean;
	esewa_account_id?: string;
	has_khalti_account: boolean;
	khalti_account_id?: string;
	primary_bank: string;
	remittance_receiving: boolean;
	cooperative_member: boolean;
	cooperative_id?: string;
}

export interface ApplicantProfileResponse {
	has_profile: boolean;
	profile: ApplicantProfile | null;
}
