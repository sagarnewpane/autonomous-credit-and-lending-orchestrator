import { PUBLIC_API_URL } from '$env/static/public';
export { PUBLIC_API_URL } from '$env/static/public';

let accessToken: string | null = null;
let refreshToken: string | null = null;

export function setTokens(access: string, refresh: string) {
	accessToken = access;
	refreshToken = refresh;
	if (typeof window !== 'undefined') {
		localStorage.setItem('access_token', access);
		localStorage.setItem('refresh_token', refresh);
	}
}

export function clearTokens() {
	accessToken = null;
	refreshToken = null;
	if (typeof window !== 'undefined') {
		localStorage.removeItem('access_token');
		localStorage.removeItem('refresh_token');
	}
}

export function loadTokens() {
	if (typeof window !== 'undefined') {
		accessToken = localStorage.getItem('access_token');
		refreshToken = localStorage.getItem('refresh_token');
	}
}

export function getAccessToken(): string | null {
	return accessToken;
}

async function tryRefresh(): Promise<boolean> {
	if (!refreshToken) return false;
	try {
		const res = await fetch(`${PUBLIC_API_URL}/api/v1/auth/refresh`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ refresh_token: refreshToken })
		});
		if (!res.ok) return false;
		const data = await res.json();
		setTokens(data.access_token, data.refresh_token);
		return true;
	} catch {
		return false;
	}
}

export async function apiFetch(
	path: string,
	options: RequestInit = {}
): Promise<Response> {
	const url = `${PUBLIC_API_URL}${path}`;
	const headers = new Headers(options.headers);

	if (accessToken) {
		headers.set('Authorization', `Bearer ${accessToken}`);
	}

	let res = await fetch(url, { ...options, headers });

	if (res.status === 401 && refreshToken) {
		const refreshed = await tryRefresh();
		if (refreshed) {
			headers.set('Authorization', `Bearer ${accessToken}`);
			res = await fetch(url, { ...options, headers });
		}
	}

	return res;
}

export async function apiGet<T>(path: string): Promise<T> {
	const res = await apiFetch(path);
	if (!res.ok) {
		const err = await res.json().catch(() => ({ detail: 'Request failed' }));
		throw new Error(err.detail || `HTTP ${res.status}`);
	}
	return res.json();
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
	const res = await apiFetch(path, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: body ? JSON.stringify(body) : undefined
	});
	if (!res.ok) {
		const err = await res.json().catch(() => ({ detail: 'Request failed' }));
		throw new Error(err.detail || `HTTP ${res.status}`);
	}
	return res.json();
}

export async function apiPostForm<T>(path: string, formData: FormData): Promise<T> {
	const res = await apiFetch(path, {
		method: 'POST',
		body: formData
	});
	if (!res.ok) {
		const err = await res.json().catch(() => ({ detail: 'Request failed' }));
		throw new Error(err.detail || `HTTP ${res.status}`);
	}
	return res.json();
}

export async function apiPutForm<T>(path: string, formData: FormData): Promise<T> {
	const res = await apiFetch(path, {
		method: 'PUT',
		body: formData
	});
	if (!res.ok) {
		const err = await res.json().catch(() => ({ detail: 'Request failed' }));
		throw new Error(err.detail || `HTTP ${res.status}`);
	}
	return res.json();
}

export async function apiPatch<T>(path: string, body?: unknown): Promise<T> {
	const res = await apiFetch(path, {
		method: 'PATCH',
		headers: { 'Content-Type': 'application/json' },
		body: body ? JSON.stringify(body) : undefined
	});
	if (!res.ok) {
		const err = await res.json().catch(() => ({ detail: 'Request failed' }));
		throw new Error(err.detail || `HTTP ${res.status}`);
	}
	return res.json();
}
