<script lang="ts">
	let {
		label,
		value = $bindable(),
		options,
		error = '',
		required = false,
		placeholder = 'Select...',
		disabled = false
	}: {
		label: string;
		value: string;
		options: { value: string; label: string }[];
		error?: string;
		required?: boolean;
		placeholder?: string;
		disabled?: boolean;
	} = $props();

	const selectId = `select-${label.toLowerCase().replace(/\s+/g, '-')}`;
</script>

<div class="space-y-1.5">
	<label for={selectId} class="block text-sm font-medium text-brand-charcoal">
		{label}
		{#if required}<span class="text-brand-burgundy ml-0.5">*</span>{/if}
	</label>
	<select
		id={selectId}
		bind:value
		{required}
		{disabled}
		class="w-full px-4 py-3 rounded-xl border text-sm transition-all duration-200 appearance-none bg-no-repeat bg-[right_12px_center] bg-[length:16px]
			focus:outline-none focus:ring-2 focus:ring-brand-gold/30 focus:border-brand-gold
			placeholder:text-brand-charcoal/30
			{disabled ? 'bg-brand-warm-gray/50 text-brand-charcoal/70 cursor-not-allowed' : ''}
			{error
				? 'border-brand-burgundy bg-brand-burgundy/5'
				: 'border-brand-border bg-white hover:border-brand-gray/30'}
			{!value ? 'text-brand-charcoal/40' : 'text-brand-charcoal'}"
		style="background-image: url(&quot;data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 24 24' stroke-width='2' stroke='%231A1A2E'%3E%3Cpath stroke-linecap='round' stroke-linejoin='round' d='M19.5 8.25l-7.5 7.5-7.5-7.5'/%3E%3C/svg%3E&quot;)"
	>
		<option value="" disabled>{placeholder}</option>
		{#each options as opt}
			<option value={opt.value}>{opt.label}</option>
		{/each}
	</select>
	{#if error}
		<p class="text-xs text-brand-burgundy font-medium">{error}</p>
	{/if}
</div>
