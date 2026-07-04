import type {
	LoanApplyResponse,
	LoanDecision,
	LoanExplanation,
	UserLoanHistory,
	ComplianceReferencesResponse,
	HealthCheckResponse,
	AdminLoanRecord,
	AuditTrailResponse,
	ApplicantProfileResponse,
	AdminStats,
	AdminUser,
	AdminUserDetail,
	AdminLoanDetail,
	BulkUpdatePayload,
	BulkUpdateResponse
} from '$lib/types/api';
import { apiGet, apiPostForm, apiPutForm, apiPatch, PUBLIC_API_URL } from './api';
import { getAccessToken } from './api';

export async function checkHealth(): Promise<HealthCheckResponse> {
	return apiGet<HealthCheckResponse>('/api/v1/loan/');
}

export async function applyLoan(formData: FormData): Promise<LoanApplyResponse> {
	return apiPostForm<LoanApplyResponse>('/api/v1/loan/apply', formData);
}

export async function getApplicantProfile(): Promise<ApplicantProfileResponse> {
	return apiGet<ApplicantProfileResponse>('/api/v1/loan/profile/me');
}

export async function getDecision(applicationId: string): Promise<LoanDecision> {
	return apiGet<LoanDecision>(`/api/v1/loan/decision/${applicationId}`);
}

export async function explainDecision(applicationId: string): Promise<LoanExplanation> {
	return apiGet<LoanExplanation>(`/api/v1/loan/explain/${applicationId}`);
}

export async function reuploadDocs(
	applicationId: string,
	formData: FormData
): Promise<{ application_id: string; uploaded_files: string[]; message: string }> {
	return apiPutForm(`/api/v1/loan/docs/${applicationId}`, formData);
}

export async function getUserLoanHistory(): Promise<UserLoanHistory> {
	return apiGet<UserLoanHistory>('/api/v1/loan/user/me');
}

export async function getComplianceReferences(
	applicationId: string
): Promise<ComplianceReferencesResponse> {
	return apiGet<ComplianceReferencesResponse>(
		`/api/v1/loan/compliance/references/${applicationId}`
	);
}

export async function getAllLoans(): Promise<{ applications: AdminLoanRecord[]; message: string }> {
	return apiGet<{ applications: AdminLoanRecord[]; message: string }>('/api/v1/admin/loans');
}

export async function adminReview(
	applicationId: string,
	payload: Record<string, unknown>
): Promise<{ application_id: string; review_payload: unknown; message: string }> {
	return apiPatch(`/api/v1/admin/review/${applicationId}`, payload);
}

export async function getAuditTrail(applicationId: string): Promise<AuditTrailResponse> {
	return apiGet<AuditTrailResponse>(`/api/v1/admin/audit/${applicationId}`);
}

export async function getAdminStats(): Promise<AdminStats> {
	return apiGet<AdminStats>('/api/v1/admin/stats');
}

export async function getLoanDetail(applicationId: string): Promise<AdminLoanDetail> {
	return apiGet<AdminLoanDetail>(`/api/v1/admin/loans/${applicationId}`);
}

export async function updateLoanApplication(
	applicationId: string,
	payload: Record<string, unknown>
): Promise<{ application_id: string; updated_fields: Record<string, unknown>; message: string }> {
	return apiPatch(`/api/v1/admin/loans/${applicationId}`, payload);
}

export async function bulkUpdateLoans(payload: BulkUpdatePayload): Promise<BulkUpdateResponse> {
	return apiPatch<BulkUpdateResponse>('/api/v1/admin/loans/bulk', payload);
}

export async function getAllUsers(search?: string): Promise<{ users: AdminUser[]; total: number; message: string }> {
	const params = search ? `?search=${encodeURIComponent(search)}` : '';
	return apiGet(`/api/v1/admin/users${params}`);
}

export async function getUserDetail(userId: string): Promise<AdminUserDetail> {
	return apiGet<AdminUserDetail>(`/api/v1/admin/users/${userId}`);
}

export async function updateUser(
	userId: string,
	payload: Record<string, unknown>
): Promise<{ user_id: string; updated_fields: Record<string, unknown>; message: string }> {
	return apiPatch(`/api/v1/admin/users/${userId}`, payload);
}

export function getExportUrl(status?: string): string {
	const token = getAccessToken();
	const params = status ? `?status=${status}` : '';
	return `${PUBLIC_API_URL}/api/v1/admin/loans/export/csv${params}`;
}
