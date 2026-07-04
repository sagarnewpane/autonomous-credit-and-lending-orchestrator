<script lang="ts">
	let {
		label,
		type = 'text',
		value = $bindable(),
		error = '',
		placeholder = '',
		required = false,
		disabled = false,
		helpText = ''
	}: {
		label: string;
		type?: string;
		value: string | number;
		error?: string;
		placeholder?: string;
		required?: boolean;
		disabled?: boolean;
		helpText?: string;
	} = $props();

	const inputId = `input-${label.toLowerCase().replace(/\s+/g, '-')}`;
</script>

<div class="space-y-1.5">
	<label for={inputId} class="block text-sm font-medium text-brand-charcoal">
		{label}
		{#if required}<span class="text-brand-gold ml-0.5">*</span>{/if}
	</label>
	<input
		id={inputId}
		{type}
		{placeholder}
		{required}
		{disabled}
		bind:value
		class="w-full px-3.5 py-2.5 rounded-lg border text-sm transition-all duration-200
			focus:outline-none focus:ring-2 focus:ring-brand-gold/20 focus:border-brand-gold
			disabled:bg-brand-warm-gray disabled:cursor-not-allowed
			placeholder:text-brand-charcoal/30
			{error
				? 'border-brand-burgundy bg-brand-burgundy/5'
				: 'border-brand-charcoal/10 bg-white hover:border-brand-charcoal/20'}"
	/>
	{#if helpText && !error}
		<p class="text-xs text-brand-charcoal/40">{helpText}</p>
	{/if}
	{#if error}
		<p class="text-xs text-brand-burgundy font-medium">{error}</p>
	{/if}
</div>
