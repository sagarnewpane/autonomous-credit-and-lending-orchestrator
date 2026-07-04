<script lang="ts">
	let {
		size = 24,
		color = 'currentColor',
		opacity = 1,
		class: className = ''
	}: {
		size?: number;
		color?: string;
		opacity?: number;
		class?: string;
	} = $props();
</script>

<svg
	width={size}
	height={size}
	viewBox="0 0 24 24"
	class={className}
	style="opacity: {opacity}"
	xmlns="http://www.w3.org/2000/svg"
	aria-hidden="true"
>
	<!-- Outer ring -->
	<circle cx="12" cy="12" r="11" fill="none" stroke={color} stroke-width="0.5" />

	<!-- 8 spokes -->
	{#each Array(8) as _, i}
		{@const angle = (i * 45) * (Math.PI / 180)}
		{@const x1 = 12 + 4.5 * Math.cos(angle)}
		{@const y1 = 12 + 4.5 * Math.sin(angle)}
		{@const x2 = 12 + 10 * Math.cos(angle)}
		{@const y2 = 12 + 10 * Math.sin(angle)}
		<line x1={x1} y1={y1} x2={x2} y2={y2} stroke={color} stroke-width="0.45" />
	{/each}

	<!-- Inner petals -->
	{#each Array(8) as _, i}
		{@const angle = (i * 45 + 22.5) * (Math.PI / 180)}
		{@const cx = 12 + 7 * Math.cos(angle)}
		{@const cy = 12 + 7 * Math.sin(angle)}
		<circle cx={cx} cy={cy} r="1" fill={color} opacity="0.2" />
	{/each}

	<!-- Center -->
	<circle cx="12" cy="12" r="4.5" fill="none" stroke={color} stroke-width="0.4" />
	<circle cx="12" cy="12" r="2" fill={color} opacity="0.25" />
</svg>
