<script lang="ts">
	import { page } from '$app/stores';
	import MandalaIcon from '$lib/components/ui/MandalaIcon.svelte';

	const links = [
		{ href: '/dashboard', label: 'Overview', icon: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0a1 1 0 01-1-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 01-1 1' },
		{ href: '/dashboard/apply', label: 'Apply for loan', icon: 'M12 4v16m8-8H4' },
		{ href: '/dashboard/applications', label: 'My applications', icon: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z' },
		{ href: '/dashboard/profile', label: 'Profile', icon: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z' }
	];

	function isActive(href: string, pathname: string): boolean {
		if (href === '/dashboard') return pathname === '/dashboard';
		return pathname.startsWith(href);
	}
</script>

<aside class="w-60 bg-white border-r border-brand-charcoal/5 min-h-screen p-4 hidden lg:block">
	<div class="mb-6 pb-4 border-b border-brand-charcoal/5">
		<a href="/dashboard" class="flex items-center gap-2.5">
			<MandalaIcon size={22} color="var(--brand-navy)" />
			<span class="text-base text-brand-navy font-display tracking-tight">Dhago</span>
		</a>
	</div>

	<nav class="space-y-0.5">
		{#each links as link}
			<a
				href={link.href}
				class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200
					{isActive(link.href, $page.url.pathname)
						? 'bg-brand-navy/8 text-brand-navy'
						: 'text-brand-charcoal/45 hover:bg-brand-warm-gray hover:text-brand-charcoal'}"
			>
				<svg class="w-4.5 h-4.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d={link.icon} />
				</svg>
				{link.label}
			</a>
		{/each}
	</nav>
</aside>
