<script lang="ts">
	import type { Snippet } from 'svelte';

	let {
		class: className = '',
		variant = 'default',
		children
	}: {
		class?: string;
		variant?: 'default' | 'elevated' | 'outlined' | 'filled';
		children: Snippet;
	} = $props();

	const variants: Record<string, string> = {
		default: 'bg-white border border-brand-charcoal/5 shadow-xs',
		elevated: 'bg-white shadow-md border border-brand-charcoal/5',
		outlined: 'bg-white border border-brand-charcoal/10',
		filled: 'bg-brand-warm-gray border border-brand-charcoal/5'
	};
</script>

<div class="rounded-xl {variants[variant]} {className}">
	{@render children()}
</div>
