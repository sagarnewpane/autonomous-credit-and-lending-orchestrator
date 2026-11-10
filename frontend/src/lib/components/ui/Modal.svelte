<script lang="ts">
	import type { Snippet } from 'svelte';

	let {
		open = $bindable(),
		title = '',
		size = 'md',
		children
	}: {
		open: boolean;
		title?: string;
		size?: 'sm' | 'md' | 'lg';
		children: Snippet;
	} = $props();

	const sizes: Record<string, string> = {
		sm: 'max-w-md',
		md: 'max-w-lg',
		lg: 'max-w-2xl'
	};

	let modalEl = $state<HTMLElement | null>(null);

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			open = false;
			return;
		}
		if (e.key === 'Tab' && modalEl) {
			const focusable = modalEl.querySelectorAll<HTMLElement>(
				'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
			);
			if (focusable.length === 0) return;
			const first = focusable[0];
			const last = focusable[focusable.length - 1];
			if (e.shiftKey) {
				if (document.activeElement === first) {
					e.preventDefault();
					last.focus();
				}
			} else {
				if (document.activeElement === last) {
					e.preventDefault();
					first.focus();
				}
			}
		}
	}

	$effect(() => {
		if (open && modalEl) {
			const focusable = modalEl.querySelectorAll<HTMLElement>(
				'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
			);
			if (focusable.length > 0) {
				focusable[0].focus();
			}
		}
	});
</script>

<svelte:window on:keydown={handleKeydown} />

{#if open}
	<div class="fixed inset-0 z-50 flex items-center justify-center p-4">
		<div
			class="fixed inset-0 bg-brand-charcoal/40 backdrop-blur-sm animate-fade-in"
			onclick={() => (open = false)}
			role="presentation"
		></div>
		<div
			bind:this={modalEl}
			role="dialog"
			aria-modal="true"
			aria-label={title || 'Dialog'}
			class="relative bg-white rounded-2xl shadow-2xl w-full {sizes[size]} mx-4 z-10 animate-scale-in overflow-hidden"
		>
			{#if title}
				<div class="flex items-center justify-between px-6 py-4 border-b border-brand-border">
					<h2 class="text-lg font-semibold text-brand-charcoal font-display">{title}</h2>
					<button
						onclick={() => (open = false)}
						class="w-8 h-8 flex items-center justify-center rounded-lg text-brand-charcoal/40 hover:text-brand-charcoal hover:bg-brand-warm-gray transition-colors"
						aria-label="Close modal"
					>
						<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
						</svg>
					</button>
				</div>
			{/if}
			<div class="p-6">
				{@render children()}
			</div>
		</div>
	</div>
{/if}
