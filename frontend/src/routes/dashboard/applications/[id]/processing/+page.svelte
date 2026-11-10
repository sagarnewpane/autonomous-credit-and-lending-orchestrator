<script lang="ts">
	import { page } from '$app/stores';
	import { getDecision } from '$lib/services/loans';
	import { getAuth } from '$lib/stores/auth.svelte';
	import type { LoanDecision } from '$lib/types/api';
	import Card from '$lib/components/ui/Card.svelte';
	import Spinner from '$lib/components/ui/Spinner.svelte';

	const auth = getAuth();
	const applicationId = $derived($page.params.id);

	let decision = $state<LoanDecision | null>(null);
	let loading = $state(true);
	let error = $state('');
	let currentStage = $state(0);

	const stages = [
		{ label: 'Verifying Documents', labelNe: 'कागजात जाँच', icon: '📄' },
		{ label: 'Analyzing Income', labelNe: 'आम्दानी विश्लेषण', icon: '💰' },
		{ label: 'Credit Scoring', labelNe: 'क्रेडिट स्कोरिङ', icon: '📊' },
		{ label: 'NRB Compliance', labelNe: 'NRB अनुपालन', icon: '✅' },
		{ label: 'Final Decision', labelNe: 'अन्तिम निर्णय', icon: '🎯' }
	];

	$effect(() => {
		if (applicationId) {
			// Simulate processing stages
			const interval = setInterval(() => {
				if (currentStage < stages.length - 1) {
					currentStage++;
				}
			}, 1500);

			// Try to fetch decision
			const checkDecision = async () => {
				try {
					const dec = await getDecision(applicationId);
					decision = dec;
					currentStage = stages.length - 1;
					clearInterval(interval);
				} catch {
					// Decision not ready yet
				} finally {
					loading = false;
				}
			};

			const timeout = setTimeout(checkDecision, 5000);

			return () => {
				clearInterval(interval);
				clearTimeout(timeout);
			};
		}
	});
</script>

<div class="min-h-screen bg-brand-cream">
	<header class="sticky top-0 z-40 bg-white/80 backdrop-blur-lg border-b border-brand-border/50">
		<div class="max-w-2xl mx-auto px-4 py-3">
			<a href="/dashboard" class="flex items-center gap-2 text-brand-charcoal/60 hover:text-brand-charcoal transition-colors" aria-label="Back to dashboard">
				<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
				</svg>
				<span class="text-sm font-medium">Back</span>
			</a>
		</div>
	</header>

	<main class="max-w-2xl mx-auto px-4 py-8 pb-24">
		<!-- Application ID -->
		<div class="text-center mb-8 animate-fade-in-up">
			<p class="text-sm text-brand-charcoal/50 mb-1">Application ID</p>
			<p class="font-mono text-xl font-bold text-brand-navy">{applicationId}</p>
		</div>

		<!-- Processing Pipeline -->
		<Card class="p-6 mb-6 animate-fade-in-up stagger-1">
			<h2 class="text-lg font-semibold text-brand-charcoal font-display mb-6 text-center">
				Your application is being processed by our AI
			</h2>

			<div class="space-y-4" aria-live="polite" aria-atomic="false">
				{#each stages as stage, i}
					{@const isComplete = i < currentStage}
					{@const isCurrent = i === currentStage}
					{@const isPending = i > currentStage}

					<div
						class="flex items-center gap-4 p-4 rounded-xl transition-all duration-500
							{isCurrent ? 'bg-brand-navy/5 border border-brand-navy/20' : isComplete ? 'bg-brand-forest/5 border border-brand-forest/20' : 'bg-brand-warm-gray border border-brand-border opacity-60'}"
					>
						<!-- Icon -->
						<div
							class="w-12 h-12 rounded-xl flex items-center justify-center text-xl transition-all duration-500
								{isCurrent ? 'bg-brand-navy text-white animate-processing-pulse' : isComplete ? 'bg-brand-forest text-white' : 'bg-brand-warm-gray text-brand-gray'}"
						>
							{#if isComplete}
								<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7" />
								</svg>
							{:else}
								{stage.icon}
							{/if}
						</div>

						<!-- Label -->
						<div class="flex-1">
							<p class="text-sm font-semibold {isCurrent ? 'text-brand-navy' : isComplete ? 'text-brand-forest' : 'text-brand-charcoal/50'}">
								{stage.label}
							</p>
							<p class="text-xs {isCurrent ? 'text-brand-navy/60' : isComplete ? 'text-brand-forest/60' : 'text-brand-charcoal/30'}">
								{stage.labelNe}
							</p>
						</div>

						<!-- Status indicator -->
						{#if isCurrent}
							<div class="w-6 h-6 border-2 border-brand-navy border-t-transparent rounded-full animate-processing-spin"></div>
						{:else if isComplete}
							<div class="w-6 h-6 bg-brand-forest rounded-full flex items-center justify-center">
								<svg class="w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" />
								</svg>
							</div>
						{:else}
							<div class="w-6 h-6 border-2 border-brand-border rounded-full"></div>
						{/if}
					</div>

					<!-- Connector line -->
					{#if i < stages.length - 1}
						<div class="ml-8 h-4 border-l-2 border-dashed {isComplete ? 'border-brand-forest/30' : 'border-brand-border'} transition-colors duration-500"></div>
					{/if}
				{/each}
			</div>
		</Card>

		<!-- Decision Ready -->
		{#if decision}
			<div class="animate-fade-in-up">
				<Card class="p-6 text-center">
					<div class="w-16 h-16 bg-brand-forest/10 rounded-full flex items-center justify-center mx-auto mb-4">
						<svg class="w-8 h-8 text-brand-forest" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
						</svg>
					</div>
					<h3 class="text-xl text-brand-charcoal mb-2 font-display">Decision Ready!</h3>
					<p class="text-sm text-brand-charcoal/60 mb-6">Your loan decision has been made</p>

					<div class="flex flex-col gap-3">
						<a
							href="/dashboard/applications/{applicationId}/decision"
							class="bg-brand-navy text-white px-6 py-3 rounded-xl font-medium hover:bg-brand-navy-light transition-colors"
						>
							View Decision
						</a>
						<a
							href="/dashboard/applications"
							class="text-brand-charcoal/60 hover:text-brand-charcoal transition-colors text-sm"
						>
							Back to Applications
						</a>
					</div>
				</Card>
			</div>
		{:else if !loading}
			<div class="animate-fade-in-up">
				<Card class="p-6 text-center">
					<div class="w-16 h-16 bg-brand-gold/10 rounded-full flex items-center justify-center mx-auto mb-4 animate-pulse-glow">
						<svg class="w-8 h-8 text-brand-gold" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
						</svg>
					</div>
					<h3 class="text-xl text-brand-charcoal mb-2 font-display">Processing...</h3>
					<p class="text-sm text-brand-charcoal/60 mb-4">
						This usually takes 3-5 minutes. You can safely close this page.
					</p>
					<button
						onclick={() => window.location.reload()}
						class="text-brand-navy text-sm font-medium hover:underline"
					>
						Refresh to check status
					</button>
				</Card>
			</div>
		{/if}
	</main>
</div>
