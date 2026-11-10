<script lang="ts">
	import '../app.css';
	import Navbar from '$lib/components/layout/Navbar.svelte';
	import { initAuth } from '$lib/stores/auth.svelte';
	import { page } from '$app/stores';
	import type { Snippet } from 'svelte';

	let { children }: { children: Snippet } = $props();

	let ready = $state(false);
	const isAdminRoute = $derived($page.url.pathname.startsWith('/admin'));

	let initialized = false;

	$effect(() => {
		if (initialized) return;
		initialized = true;
		initAuth().then(() => {
			ready = true;
		});
	});
</script>

<div class="min-h-screen bg-brand-warm-gray">
	{#if !isAdminRoute}
		<Navbar />
	{/if}
	{#if ready}
		{@render children()}
	{:else}
		<div class="flex items-center justify-center min-h-[80vh]">
			<div class="text-center">
				<div class="w-8 h-8 border-3 border-brand-navy/20 border-t-brand-navy rounded-full animate-spin mx-auto mb-4"></div>
				<p class="text-brand-charcoal/50 text-sm">Loading...</p>
			</div>
		</div>
	{/if}
</div>
