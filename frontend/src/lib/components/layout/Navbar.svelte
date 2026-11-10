<script lang="ts">
	import { getAuth, logoutUser } from '$lib/stores/auth.svelte';
	import { goto } from '$app/navigation';
	import MandalaIcon from '$lib/components/ui/MandalaIcon.svelte';

	const auth = getAuth();
	let mobileMenuOpen = $state(false);

	async function handleLogout() {
		await logoutUser();
		goto('/auth/login');
	}
</script>

<nav class="bg-white/80 backdrop-blur-lg border-b border-brand-charcoal/5 px-4 py-3 sticky top-0 z-50">
	<div class="max-w-6xl mx-auto flex items-center justify-between">
		<a href="/" class="flex items-center gap-2.5 group">
			<MandalaIcon size={26} color="var(--brand-navy)" />
			<span class="text-lg text-brand-navy font-display tracking-tight">Dhago</span>
		</a>

		<!-- Desktop Navigation -->
		<div class="hidden md:flex items-center gap-6">
			{#if auth.isAuthenticated}
				<a href="/dashboard" class="text-sm font-medium text-brand-charcoal/60 hover:text-brand-navy transition-colors">
					Dashboard
				</a>
				{#if auth.isAdmin}
					<a href="/admin/loans" class="text-sm font-medium text-brand-charcoal/60 hover:text-brand-navy transition-colors">
						Admin
					</a>
				{/if}
				<div class="flex items-center gap-4 pl-4 border-l border-brand-charcoal/10">
					<div class="w-8 h-8 bg-brand-navy/10 rounded-full flex items-center justify-center">
						<span class="text-xs font-bold text-brand-navy">{auth.user?.email?.charAt(0).toUpperCase()}</span>
					</div>
					<button onclick={handleLogout} class="text-sm text-brand-charcoal/50 hover:text-brand-burgundy transition-colors font-medium">
						Log out
					</button>
				</div>
			{:else}
				<a href="/auth/login" class="text-sm font-medium text-brand-charcoal/60 hover:text-brand-navy transition-colors">
					Sign in
				</a>
				<a href="/auth/signup" class="bg-brand-navy text-white px-5 py-2 rounded-lg text-sm font-medium hover:bg-brand-navy-light transition-colors shadow-sm">
					Get started
				</a>
			{/if}
		</div>

		<!-- Mobile Menu Button -->
		<button
			onclick={() => (mobileMenuOpen = !mobileMenuOpen)}
			class="md:hidden w-10 h-10 flex items-center justify-center rounded-lg hover:bg-brand-warm-gray transition-colors"
			aria-label={mobileMenuOpen ? 'Close menu' : 'Open menu'}
			aria-expanded={mobileMenuOpen}
			aria-controls="mobile-menu"
		>
			<svg class="w-5 h-5 text-brand-charcoal" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				{#if mobileMenuOpen}
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
				{:else}
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
				{/if}
			</svg>
		</button>
	</div>

	<!-- Mobile Menu -->
	{#if mobileMenuOpen}
		<div id="mobile-menu" class="md:hidden mt-3 pb-3 border-t border-brand-charcoal/5 animate-fade-in-down">
			{#if auth.isAuthenticated}
				<div class="pt-3 space-y-1">
					<a href="/dashboard" class="block px-4 py-2.5 text-sm font-medium text-brand-charcoal/70 hover:bg-brand-warm-gray rounded-lg transition-colors">
						Dashboard
					</a>
					{#if auth.isAdmin}
						<a href="/admin/loans" class="block px-4 py-2.5 text-sm font-medium text-brand-charcoal/70 hover:bg-brand-warm-gray rounded-lg transition-colors">
							Admin
						</a>
					{/if}
					<button
						onclick={handleLogout}
						class="w-full text-left px-4 py-2.5 text-sm font-medium text-brand-burgundy hover:bg-brand-burgundy/5 rounded-lg transition-colors"
					>
						Log out
					</button>
				</div>
			{:else}
				<div class="pt-3 space-y-1">
					<a href="/auth/login" class="block px-4 py-2.5 text-sm font-medium text-brand-charcoal/70 hover:bg-brand-warm-gray rounded-lg transition-colors">
						Sign in
					</a>
					<a href="/auth/signup" class="block px-4 py-2.5 text-sm font-medium text-brand-navy bg-brand-navy/5 rounded-lg transition-colors">
						Get started
					</a>
				</div>
			{/if}
		</div>
	{/if}
</nav>
