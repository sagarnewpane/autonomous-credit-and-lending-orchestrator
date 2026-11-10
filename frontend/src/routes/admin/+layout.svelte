<script lang="ts">
	import { getAuth } from '$lib/stores/auth.svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import type { Snippet } from 'svelte';
	import MandalaIcon from '$lib/components/ui/MandalaIcon.svelte';

	let { children }: { children: Snippet } = $props();
	const auth = getAuth();

	const currentPath = $derived($page.url.pathname);
	const isLoginPage = $derived(currentPath === '/admin/login');

	function isActive(path: string): boolean {
		if (path === '/admin') return currentPath === '/admin';
		return currentPath.startsWith(path);
	}

	$effect(() => {
		if (!auth.loading && !isLoginPage && (!auth.isAuthenticated || !auth.isAdmin)) {
			goto('/admin/login');
		}
	});
</script>

{#if isLoginPage || auth.isAdmin}
	<div class="flex min-h-screen bg-brand-warm-gray">
		<!-- Admin Sidebar -->
		<aside class="w-60 bg-brand-navy text-white p-4 hidden lg:block flex-shrink-0">
			<!-- Brand -->
			<div class="mb-6 pb-4 border-b border-white/10">
				<a href="/admin" class="flex items-center gap-2.5">
					<MandalaIcon size={22} color="var(--brand-gold)" />
					<span class="text-base text-white font-display tracking-tight">Dhago Admin</span>
				</a>
			</div>

			<!-- Navigation -->
			<nav class="space-y-1">
				<a
					href="/admin"
					class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors
						{isActive('/admin') && !isActive('/admin/loans') && !isActive('/admin/users')
							? 'bg-white/15 text-white'
							: 'text-white/50 hover:bg-white/10 hover:text-white'}"
				>
					<svg class="w-4.5 h-4.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0a1 1 0 01-1-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 01-1 1" />
					</svg>
					Dashboard
				</a>

				<a
					href="/admin/loans"
					class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors
						{isActive('/admin/loans') ? 'bg-white/15 text-white' : 'text-white/50 hover:bg-white/10 hover:text-white'}"
				>
					<svg class="w-4.5 h-4.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
					</svg>
					All Loans
				</a>

				<a
					href="/admin/loans?status=pending"
					class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors
						{currentPath === '/admin/loans' && $page.url.searchParams.get('status') === 'pending'
							? 'bg-white/15 text-white'
							: 'text-white/50 hover:bg-white/10 hover:text-white'}"
				>
					<svg class="w-4.5 h-4.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
					</svg>
					Pending Review
				</a>

				<a
					href="/admin/loans?status=flag"
					class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors
						{currentPath === '/admin/loans' && $page.url.searchParams.get('status') === 'flag'
							? 'bg-white/15 text-white'
							: 'text-white/50 hover:bg-white/10 hover:text-white'}"
				>
					<svg class="w-4.5 h-4.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M3 21v-4m0 0V5a2 2 0 012-2h6.5l1 1H21l-3 6 3 6h-8.5l-1-1H5a2 2 0 00-2 2zm9-13.5V9" />
					</svg>
					Compliance Flags
				</a>

				<!-- Divider -->
				<div class="border-t border-white/10 my-3"></div>

				<a
					href="/admin/users"
					class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors
						{isActive('/admin/users') ? 'bg-white/15 text-white' : 'text-white/50 hover:bg-white/10 hover:text-white'}"
				>
					<svg class="w-4.5 h-4.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
					</svg>
					User Management
				</a>
			</nav>

			<!-- User Info at Bottom -->
			<div class="mt-auto pt-4 border-t border-white/10 absolute bottom-4 left-4 right-4">
				<div class="flex items-center gap-3">
					<div class="w-8 h-8 rounded-lg bg-white/10 flex items-center justify-center flex-shrink-0">
						<span class="text-xs font-bold text-white">
							{auth.user?.email?.charAt(0).toUpperCase() || 'A'}
						</span>
					</div>
					<div class="min-w-0">
						<p class="text-xs font-medium text-white/80 truncate">{auth.user?.email || 'Admin'}</p>
						<button
							onclick={() => {
								import('$lib/stores/auth.svelte').then(m => m.logoutUser());
								goto('/admin/login');
							}}
							class="text-[10px] text-white/40 hover:text-white/70 transition-colors"
						>
							Sign out
						</button>
					</div>
				</div>
			</div>
		</aside>

		<!-- Main Content -->
		<main class="flex-1 min-h-screen overflow-x-hidden">
			<!-- Mobile Header -->
			<div class="lg:hidden bg-white border-b border-brand-border px-4 py-3 flex items-center justify-between sticky top-0 z-40">
				<a href="/admin" class="flex items-center gap-2">
					<MandalaIcon size={24} color="var(--brand-navy)" />
					<span class="text-sm font-display text-brand-charcoal">Dhago Admin</span>
				</a>
				<div class="flex items-center gap-3">
					<a href="/admin/loans" class="text-xs text-brand-navy font-medium">Loans</a>
					<a href="/admin/users" class="text-xs text-brand-navy font-medium">Users</a>
					<button
						onclick={() => {
							import('$lib/stores/auth.svelte').then(m => m.logoutUser());
							goto('/admin/login');
						}}
						class="text-xs text-brand-charcoal/40 hover:text-brand-charcoal"
					>
						Sign out
					</button>
				</div>
			</div>

			{@render children()}
		</main>
	</div>
{:else}
	<div class="flex items-center justify-center min-h-[80vh]">
		<div class="text-center">
			<div class="w-8 h-8 border-3 border-brand-navy/20 border-t-brand-navy rounded-full animate-spin mx-auto mb-4"></div>
			<p class="text-brand-charcoal/50 text-sm">Loading...</p>
		</div>
	</div>
{/if}
