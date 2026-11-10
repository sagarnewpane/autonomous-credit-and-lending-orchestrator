<script lang="ts">
	let {
		size = 400,
		color = 'currentColor',
		opacity = 0.1,
		animate = true,
		draw = false,
		class: className = ''
	}: {
		size?: number;
		color?: string;
		opacity?: number;
		animate?: boolean;
		draw?: boolean;
		class?: string;
	} = $props();
</script>

<svg
	width={size}
	height={size}
	viewBox="0 0 200 200"
	class="{animate && !draw ? 'animate-mandala-spin' : ''} {className}"
	style="opacity: {opacity}"
	xmlns="http://www.w3.org/2000/svg"
	aria-hidden="true"
>
	<!-- Outer ring -->
	<circle cx="100" cy="100" r="96" fill="none" stroke={color} stroke-width="0.4"
		class={draw ? 'animate-mandala-draw' : ''}
		style={draw ? 'animation-delay: 0s' : ''}
	/>
	<circle cx="100" cy="100" r="92" fill="none" stroke={color} stroke-width="0.25"
		class={draw ? 'animate-mandala-draw' : ''}
		style={draw ? 'animation-delay: 0.1s' : ''}
	/>

	<!-- Outer decorative dots -->
	{#each Array(24) as _, i}
		{@const angle = (i * 15) * (Math.PI / 180)}
		{@const x = 100 + 89 * Math.cos(angle)}
		{@const y = 100 + 89 * Math.sin(angle)}
		<circle cx={x} cy={y} r="1" fill={color} opacity="0.35"
			class={draw ? 'animate-mandala-draw' : ''}
			style={draw ? `animation-delay: ${0.15 + i * 0.03}s` : ''}
		/>
	{/each}

	<!-- 8-fold petal structure -->
	{#each Array(8) as _, i}
		{@const angle = (i * 45) * (Math.PI / 180)}
		{@const angleNext = ((i * 45) + 22.5) * (Math.PI / 180)}

		<!-- Main spoke -->
		{@const x1 = 100 + 28 * Math.cos(angle)}
		{@const y1 = 100 + 28 * Math.sin(angle)}
		{@const x2 = 100 + 85 * Math.cos(angle)}
		{@const y2 = 100 + 85 * Math.sin(angle)}
		<line x1={x1} y1={y1} x2={x2} y2={y2} stroke={color} stroke-width="0.4"
			class={draw ? 'animate-mandala-draw' : ''}
			style={draw ? `animation-delay: ${0.2 + i * 0.08}s` : ''}
		/>

		<!-- Leaf shape between spokes -->
		{@const leafBase = 100 + 35 * Math.cos(angleNext)}
		{@const leafBaseY = 100 + 35 * Math.sin(angleNext)}
		{@const leafTip = 100 + 70 * Math.cos(angleNext)}
		{@const leafTipY = 100 + 70 * Math.sin(angleNext)}
		{@const leafCtrl1x = 100 + 50 * Math.cos(angleNext - 0.25)}
		{@const leafCtrl1y = 100 + 50 * Math.sin(angleNext - 0.25)}
		{@const leafCtrl2x = 100 + 50 * Math.cos(angleNext + 0.25)}
		{@const leafCtrl2y = 100 + 50 * Math.sin(angleNext + 0.25)}
		<path
			d="M {leafBase} {leafBaseY} Q {leafCtrl1x} {leafCtrl1y} {leafTip} {leafTipY} Q {leafCtrl2x} {leafCtrl2y} {leafBase} {leafBaseY}"
			fill="none"
			stroke={color}
			stroke-width="0.35"
			class={draw ? 'animate-mandala-draw' : ''}
			style={draw ? `animation-delay: ${0.35 + i * 0.08}s` : ''}
		/>

		<!-- Inner petal curve -->
		{@const innerCtrl1x = 100 + 42 * Math.cos(angle - 0.2)}
		{@const innerCtrl1y = 100 + 42 * Math.sin(angle - 0.2)}
		{@const innerCtrl2x = 100 + 42 * Math.cos(angle + 0.2)}
		{@const innerCtrl2y = 100 + 42 * Math.sin(angle + 0.2)}
		{@const innerTip = 100 + 55 * Math.cos(angle)}
		{@const innerTipY = 100 + 55 * Math.sin(angle)}
		<path
			d="M {100 + 28 * Math.cos(angle)} {100 + 28 * Math.sin(angle)} Q {innerCtrl1x} {innerCtrl1y} {innerTip} {innerTipY} Q {innerCtrl2x} {innerCtrl2y} {100 + 28 * Math.cos(angle)} {100 + 28 * Math.sin(angle)}"
			fill="none"
			stroke={color}
			stroke-width="0.3"
			class={draw ? 'animate-mandala-draw' : ''}
			style={draw ? `animation-delay: ${0.5 + i * 0.06}s` : ''}
		/>
	{/each}

	<!-- Inner concentric circles -->
	<circle cx="100" cy="100" r="65" fill="none" stroke={color} stroke-width="0.3"
		class={draw ? 'animate-mandala-draw' : ''}
		style={draw ? 'animation-delay: 0.3s' : ''}
	/>
	<circle cx="100" cy="100" r="28" fill="none" stroke={color} stroke-width="0.45"
		class={draw ? 'animate-mandala-draw' : ''}
		style={draw ? 'animation-delay: 0.6s' : ''}
	/>
	<circle cx="100" cy="100" r="22" fill="none" stroke={color} stroke-width="0.3"
		class={draw ? 'animate-mandala-draw' : ''}
		style={draw ? 'animation-delay: 0.7s' : ''}
	/>

	<!-- Center ornament -->
	<circle cx="100" cy="100" r="12" fill="none" stroke={color} stroke-width="0.4"
		class={draw ? 'animate-mandala-draw' : ''}
		style={draw ? 'animation-delay: 0.8s' : ''}
	/>
	<circle cx="100" cy="100" r="4" fill={color} opacity="0.2"
		class={draw ? 'animate-mandala-draw' : ''}
		style={draw ? 'animation-delay: 0.9s' : ''}
	/>

	<!-- Mid-ring decorative dots -->
	{#each Array(16) as _, i}
		{@const angle = (i * 22.5) * (Math.PI / 180)}
		{@const x = 100 + 45 * Math.cos(angle)}
		{@const y = 100 + 45 * Math.sin(angle)}
		<circle cx={x} cy={y} r="1.2" fill={color} opacity="0.25"
			class={draw ? 'animate-mandala-draw' : ''}
			style={draw ? `animation-delay: ${0.4 + i * 0.04}s` : ''}
		/>
	{/each}
</svg>
