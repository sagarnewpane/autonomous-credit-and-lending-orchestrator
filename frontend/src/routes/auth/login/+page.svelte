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
			await loginUser(email, password);
			if (auth.isAdmin) {
				goto('/admin');
			} else {
				goto('/dashboard');
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
		<Mandala size={500} color="var(--brand-navy)" opacity={0.03} animate={true} />
	</div>

	<div class="w-full max-w-md relative">
		<!-- Header -->
		<div class="text-center mb-8">
			<div class="flex justify-center mb-4">
				<MandalaIcon size={40} color="var(--brand-navy)" />
			</div>
			<h1 class="text-3xl font-display text-brand-charcoal">Welcome back</h1>
			<p class="text-brand-charcoal/50 mt-2 text-sm">Sign in to Dhago</p>
		</div>

		<!-- Form Card -->
		<div class="bg-white p-8 rounded-2xl shadow-sm border border-brand-charcoal/5 relative overflow-hidden">
			<!-- Subtle accent line -->
			<div class="absolute top-0 left-0 w-full h-0.5 bg-gradient-to-r from-brand-navy via-brand-gold to-brand-forest"></div>

			{#if error}
				<div class="bg-brand-danger/8 text-brand-danger p-3 rounded-lg mb-4 text-sm border border-brand-danger/10">
					{error}
				</div>
			{/if}

			<form onsubmit={handleSubmit} class="space-y-4">
				<Input label="Email" type="email" bind:value={email} required placeholder="you@example.com" />
				<Input label="Password" type="password" bind:value={password} required placeholder="Enter your password" />

				<Button type="submit" {loading} class="w-full">
					Sign in
				</Button>
			</form>

			<p class="text-center text-sm text-brand-charcoal/50 mt-6">
				Don't have an account?
				<a href="/auth/signup" class="text-brand-navy hover:text-brand-navy-light font-medium transition-colors">Create one</a>
			</p>
		</div>
	</div>
</div>
