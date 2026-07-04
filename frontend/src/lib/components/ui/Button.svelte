<script lang="ts">
	import type { Snippet } from 'svelte';

	let {
		variant = 'primary',
		size = 'md',
		disabled = false,
		loading = false,
		type = 'button',
		class: className = '',
		onclick,
		children
	}: {
		variant?: 'primary' | 'secondary' | 'danger' | 'ghost' | 'success' | 'warning';
		size?: 'sm' | 'md' | 'lg';
		disabled?: boolean;
		loading?: boolean;
		type?: 'button' | 'submit' | 'reset';
		class?: string;
		onclick?: (e: MouseEvent) => void;
		children: Snippet;
	} = $props();

	const base = 'inline-flex items-center justify-center gap-2 font-medium transition-all duration-200 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg active:scale-[0.98]';

	const sizes: Record<string, string> = {
		sm: 'px-3 py-1.5 text-sm',
		md: 'px-5 py-2.5 text-sm',
		lg: 'px-6 py-3 text-base'
	};

	const variants: Record<string, string> = {
		primary: 'bg-brand-navy text-white hover:bg-brand-navy-light shadow-sm hover:shadow-md',
		secondary: 'bg-brand-warm-gray text-brand-charcoal hover:bg-brand-charcoal/8 border border-brand-charcoal/8',
		danger: 'bg-brand-burgundy text-white hover:bg-brand-burgundy-light shadow-sm',
		ghost: 'bg-transparent text-brand-charcoal/60 hover:bg-brand-charcoal/5 hover:text-brand-charcoal',
		success: 'bg-brand-forest text-white hover:bg-brand-forest-light shadow-sm',
		warning: 'bg-brand-gold text-brand-charcoal hover:bg-brand-gold-dark shadow-sm'
	};
</script>

<button
	{type}
	{disabled}
	class="{base} {sizes[size]} {variants[variant]} {className}"
	onclick={onclick}
>
	{#if loading}
		<svg class="animate-spin h-4 w-4" viewBox="0 0 24 24">
			<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
			<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
		</svg>
	{/if}
	{@render children()}
</button>
