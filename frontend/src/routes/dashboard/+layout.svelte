<script lang="ts">
	import Sidebar from '$lib/components/layout/Sidebar.svelte';
	import { getAuth } from '$lib/stores/auth.svelte';
	import { goto } from '$app/navigation';
	import type { Snippet } from 'svelte';

	let { children }: { children: Snippet } = $props();
	const auth = getAuth();

	$effect(() => {
		if (!auth.loading && !auth.isAuthenticated) {
			goto('/auth/login');
		}
	});
</script>

{#if auth.isAuthenticated}
	<div class="flex">
		<Sidebar />
		<main class="flex-1 p-6">
			{@render children()}
		</main>
	</div>
{/if}
