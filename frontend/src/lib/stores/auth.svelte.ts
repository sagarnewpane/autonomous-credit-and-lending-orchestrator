import type { UserRead } from '$lib/types/api';
import * as auth from '$lib/services/auth';
import { loadTokens, clearTokens } from '$lib/services/api';

let user = $state<UserRead | null>(null);
let loading = $state(true);

export function getAuth() {
	return {
		get user() {
			return user;
		},
		get loading() {
			return loading;
		},
		get isAuthenticated() {
			return !!user;
		},
		get isAdmin() {
			return user?.is_admin ?? false;
		}
	};
}

export async function initAuth() {
	loading = true;
	loadTokens();
	try {
		user = await auth.getMe();
	} catch {
		user = null;
		clearTokens();
	} finally {
		loading = false;
	}
}

export async function loginUser(email: string, password: string) {
	const res = await auth.login({ email, password });
	user = res.user ?? null;
	return res;
}

export async function signupUser(email: string, password: string) {
	const res = await auth.signup({ email, password });
	user = res.user ?? null;
	return res;
}

export async function logoutUser() {
	await auth.logout();
	user = null;
}
