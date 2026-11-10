import type {
	UserCreate,
	TokenResponse,
	UserRead,
	RefreshRequest
} from '$lib/types/api';
import { apiPost, apiGet, setTokens, clearTokens } from './api';

export async function signup(data: UserCreate): Promise<TokenResponse> {
	const res = await apiPost<TokenResponse>('/api/v1/auth/signup', data);
	setTokens(res.access_token, res.refresh_token);
	return res;
}

export async function login(data: UserCreate): Promise<TokenResponse> {
	const res = await apiPost<TokenResponse>('/api/v1/auth/login', data);
	setTokens(res.access_token, res.refresh_token);
	return res;
}

export async function refreshToken(token: string): Promise<TokenResponse> {
	const res = await apiPost<TokenResponse>('/api/v1/auth/refresh', {
		refresh_token: token
	} as RefreshRequest);
	setTokens(res.access_token, res.refresh_token);
	return res;
}

export async function getMe(): Promise<UserRead> {
	return apiGet<UserRead>('/api/v1/auth/me');
}

export async function logout(): Promise<void> {
	try {
		await apiPost('/api/v1/auth/logout');
	} finally {
		clearTokens();
	}
}
