<script lang="ts">
	import { loginUser, getAuth } from '$lib/stores/auth.svelte';
	import { goto } from '$app/navigation';
	import Button from '$lib/components/ui/Button.svelte';
	import Input from '$lib/components/ui/Input.svelte';
	import Mandala from '$lib/components/ui/Mandala.svelte';
	import MandalaIcon from '$lib/components/ui/MandalaIcon.svelte';

	const auth = getAuth();

	let email = $state('');
	let password = $state('');
	let error = $state('');
	let loading = $state(false);

	async function handleSubmit(e: Event) {
		e.preventDefault();
		error = '';
		loading = true;
		try {
			const res = await loginUser(email, password);
			if (res.user?.is_admin) {
				goto('/admin');
			} else {
				error = 'You do not have admin access.';
				const { logoutUser } = await import('$lib/stores/auth.svelte');
				await logoutUser();
			}
		} catch (err: unknown) {
			error = err instanceof Error ? err.message : 'Login failed';
		} finally {
			loading = false;
		}
	}
</script>

<div class="min-h-[80vh] flex items-center justify-center px-4 relative">
	<!-- Background Mandala -->
	<div class="absolute inset-0 flex items-center justify-center pointer-events-none">
		<Mandala size={600} color="var(--brand-navy)" opacity={0.03} animate={true} />
	</div>
	
	<div class="w-full max-w-md relative">
		<!-- Header -->
		<div class="text-center mb-8">
			<div class="w-16 h-16 bg-brand-charcoal rounded-xl flex items-center justify-center mx-auto mb-4">
				<svg class="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
				</svg>
			</div>
			<h1 class="text-3xl font-bold text-brand-charcoal">Admin Access</h1>
			<p class="text-brand-charcoal/60 mt-2">Authorized personnel only</p>
		</div>

		<!-- Form Card -->
		<div class="bg-white p-8 rounded-2xl shadow-sm border border-brand-border relative overflow-hidden">
			<!-- Decorative corner -->
			<div class="absolute top-0 right-0 w-20 h-20 bg-brand-navy/5 rounded-bl-full"></div>
			
			{#if error}
				<div class="bg-brand-danger/10 text-brand-danger p-3 rounded-lg mb-4 text-sm">
					{error}
				</div>
			{/if}

			<form onsubmit={handleSubmit} class="space-y-4">
				<Input label="Email" type="email" bind:value={email} required placeholder="admin@autolend.com" />
				<Input label="Password" type="password" bind:value={password} required placeholder="••••••••" />

				<Button type="submit" {loading} class="w-full">
					Sign In as Admin
				</Button>
			</form>

			<p class="text-center text-sm text-brand-charcoal/60 mt-6">
				<a href="/auth/login" class="text-brand-navy hover:text-brand-navy/80 font-medium">← Back to regular login</a>
			</p>
		</div>
	</div>
</div>
