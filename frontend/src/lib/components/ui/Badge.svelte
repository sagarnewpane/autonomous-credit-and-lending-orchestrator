<script lang="ts">
	import type { Snippet } from 'svelte';

	let {
		variant = 'default',
		size = 'sm',
		children
	}: {
		variant?: 'default' | 'success' | 'warning' | 'danger' | 'info';
		size?: 'xs' | 'sm' | 'md';
		children: Snippet;
	} = $props();

	const variants: Record<string, string> = {
		default: 'bg-brand-charcoal/8 text-brand-charcoal/60',
		success: 'bg-brand-forest/10 text-brand-forest',
		warning: 'bg-brand-gold/15 text-brand-gold-dark',
		danger: 'bg-brand-burgundy/10 text-brand-burgundy',
		info: 'bg-brand-navy/8 text-brand-navy'
	};

	const sizes: Record<string, string> = {
		xs: 'px-1.5 py-0.5 text-[10px]',
		sm: 'px-2 py-0.5 text-[11px]',
		md: 'px-2.5 py-1 text-xs'
	};
</script>

<span class="inline-flex items-center font-semibold rounded-full tracking-wide {variants[variant]} {sizes[size]}">
	{@render children()}
</span>
