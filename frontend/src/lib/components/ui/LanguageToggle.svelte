<script lang="ts">
	let {
		lang = $bindable('en')
	}: {
		lang: 'en' | 'ne';
	} = $props();

	function toggle() {
		lang = lang === 'en' ? 'ne' : 'en';
	}
</script>

<button
	onclick={toggle}
	class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium transition-all duration-200
		{lang === 'en'
			? 'bg-brand-navy text-white'
			: 'bg-brand-gold text-brand-charcoal'}"
	aria-label="Switch language"
>
	<span class="text-xs opacity-70">EN</span>
	<span class="w-4 h-px bg-current opacity-40"></span>
	<span class="text-xs font-semibold">{lang === 'en' ? 'नेपाली' : 'English'}</span>
</button>
