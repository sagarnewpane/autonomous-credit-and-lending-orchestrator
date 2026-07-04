<script lang="ts">
	import type { Snippet } from 'svelte';

	let {
		text = '',
		children
	}: {
		text: string;
		children?: Snippet;
	} = $props();

	let show = $state(false);
	let tooltipId = $state(`tooltip-${Math.random().toString(36).slice(2, 9)}`);
</script>

<span
	class="relative inline-flex"
	role="group"
	onmouseenter={() => (show = true)}
	onmouseleave={() => (show = false)}
	onfocus={() => (show = true)}
	onblur={() => (show = false)}
	aria-describedby={show ? tooltipId : undefined}
>
	{@render children?.()}
	<span
		id={tooltipId}
		role="tooltip"
		class="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 text-xs leading-tight text-white bg-brand-charcoal rounded-lg shadow-lg whitespace-nowrap z-50 transition-opacity duration-150
			{show ? 'opacity-100 visible' : 'opacity-0 invisible'}"
	>
		{text}
		<span class="absolute top-full left-1/2 -translate-x-1/2 w-0 h-0 border-l-4 border-r-4 border-t-4 border-transparent border-t-brand-charcoal"></span>
	</span>
</span>
