<script lang="ts">
	let {
		currentStep = 1,
		totalSteps = 3,
		labels = []
	}: {
		currentStep: number;
		totalSteps?: number;
		labels?: string[];
	} = $props();
</script>

<div class="relative py-6">
	<!-- River SVG -->
	<svg class="w-full h-16" viewBox="0 0 400 64" preserveAspectRatio="xMidYMid meet">
		<!-- Background river path -->
		<path
			d="M 0 32 Q 66 12, 133 32 T 266 32 T 400 32"
			fill="none"
			stroke="var(--brand-border)"
			stroke-width="4"
			stroke-linecap="round"
		/>

		<!-- Active river path with gradient -->
		<defs>
			<linearGradient id="riverGradient" x1="0%" y1="0%" x2="100%" y2="0%">
				<stop offset="0%" stop-color="var(--brand-navy)" />
				<stop offset="50%" stop-color="var(--brand-gold)" />
				<stop offset="100%" stop-color="var(--brand-forest)" />
			</linearGradient>
		</defs>

		<path
			d="M 0 32 Q 66 12, 133 32 T 266 32 T 400 32"
			fill="none"
			stroke="url(#riverGradient)"
			stroke-width="4"
			stroke-linecap="round"
			class="transition-all duration-700 ease-out"
			style="stroke-dasharray: 600; stroke-dashoffset: {600 - (currentStep / totalSteps) * 600}"
		/>

		<!-- Step markers -->
		{#each Array(totalSteps) as _, i}
			{@const x = (i / (totalSteps - 1)) * 370 + 15}
			{@const isActive = i + 1 <= currentStep}
			{@const isCurrent = i + 1 === currentStep}

			<!-- Marker circle -->
			<circle
				cx={x}
				cy="32"
				r={isCurrent ? "12" : "10"}
				fill={isActive ? "var(--brand-navy)" : "var(--brand-white)"}
				stroke={isActive ? "var(--brand-navy)" : "var(--brand-border)"}
				stroke-width={isCurrent ? "3" : "2"}
				class="transition-all duration-500"
			/>

			<!-- Step number -->
			<text
				x={x}
				y="37"
				text-anchor="middle"
				class="text-[11px] font-semibold transition-colors duration-500"
				fill={isActive ? "var(--brand-white)" : "var(--brand-gray)"}
			>
				{i + 1}
			</text>

			<!-- Pulse ring for current step -->
			{#if isCurrent}
				<circle
					cx={x}
					cy="32"
					r="16"
					fill="none"
					stroke="var(--brand-gold)"
					stroke-width="2"
					class="animate-pulse-glow"
					style="animation-delay: {i * 0.2}s"
				/>
			{/if}
		{/each}
	</svg>

	<!-- Labels -->
	{#if labels.length > 0}
		<div class="flex justify-between mt-3 px-0">
			{#each labels as label, i}
				<span
					class="text-xs font-medium text-center transition-colors duration-300 flex-1
						{i + 1 === currentStep ? 'text-brand-navy' : i + 1 < currentStep ? 'text-brand-forest' : 'text-brand-charcoal/40'}"
				>
					{label}
				</span>
			{/each}
		</div>
	{/if}
</div>
