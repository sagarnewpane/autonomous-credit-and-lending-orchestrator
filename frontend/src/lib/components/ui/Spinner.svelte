<script lang="ts">
	let {
		size = 'md'
	}: {
		size?: 'sm' | 'md' | 'lg';
	} = $props();

	const sizes: Record<string, string> = {
		sm: 'h-4 w-4',
		md: 'h-8 w-8',
		lg: 'h-12 w-12'
	};
</script>

<svg class="animate-spin {sizes[size]} text-brand-navy" viewBox="0 0 24 24">
	<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
	<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
</svg>
