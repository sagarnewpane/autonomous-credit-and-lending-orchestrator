<script lang="ts">
	import { page } from '$app/stores';
	import { explainDecision, getComplianceReferences } from '$lib/services/loans';
	import type { LoanExplanation, ComplianceReferencesResponse } from '$lib/types/api';
	import Card from '$lib/components/ui/Card.svelte';
	import Spinner from '$lib/components/ui/Spinner.svelte';
	import MandalaIcon from '$lib/components/ui/MandalaIcon.svelte';

	const applicationId = $derived($page.params.id);

	let explanation = $state<LoanExplanation | null>(null);
	let compliance = $state<ComplianceReferencesResponse | null>(null);
	let loading = $state(true);
	let error = $state('');

	$effect(() => {
		if (applicationId) {
			Promise.all([
				explainDecision(applicationId).catch(() => null),
				getComplianceReferences(applicationId).catch(() => null)
			])
				.then(([exp, comp]) => {
					explanation = exp;
					compliance = comp;
					loading = false;
				})
				.catch((err) => {
					error = err.message;
					loading = false;
				});
		}
	});
</script>

<div class="max-w-4xl mx-auto px-4 py-8">
	<!-- Back Link -->
	<a href="/dashboard/applications/{applicationId}" class="text-brand-navy hover:text-brand-navy/80 text-sm font-medium mb-4 inline-block">
		← Back to Application
	</a>

	<!-- Header -->
	<div class="flex items-center gap-3 mb-8">
		<MandalaIcon size={40} color="var(--brand-navy)" />
		<div>
			<h1 class="text-3xl font-bold text-brand-charcoal">Decision Explanation</h1>
			<p class="text-brand-charcoal/60">Understand your loan decision</p>
		</div>
	</div>

	{#if loading}
		<div class="flex justify-center py-12"><Spinner /></div>
	{:else if error}
		<div class="bg-brand-danger/10 text-brand-danger p-4 rounded-lg" role="alert">{error}</div>
	{:else}
		<div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
			<!-- Credit Analysis Card -->
			<Card class="p-6 relative overflow-hidden">
				<div class="absolute top-0 right-0 w-20 h-20 bg-brand-navy/5 rounded-bl-full"></div>
				<h2 class="text-lg font-semibold text-brand-charcoal mb-4">Credit Analysis</h2>
				{#if explanation}
					<dl class="space-y-3">
						<div class="flex justify-between">
							<dt class="text-brand-charcoal/60">Credit Score</dt>
							<dd class="font-semibold text-brand-charcoal font-mono">{explanation.credit_score ?? 'N/A'}</dd>
						</div>
						<div class="flex justify-between">
							<dt class="text-brand-charcoal/60">Score Band</dt>
							<dd class="text-brand-charcoal">{explanation.score_band ?? 'N/A'}</dd>
						</div>
						<div class="flex justify-between">
							<dt class="text-brand-charcoal/60">Decision</dt>
							<dd class="font-medium text-brand-charcoal">{explanation.decision ?? 'PENDING'}</dd>
						</div>
					</dl>
				{:else}
					<p class="text-brand-charcoal/60">No explanation data available</p>
				{/if}
			</Card>

			<!-- Compliance Status Card -->
			<Card class="p-6 relative overflow-hidden">
				<div class="absolute top-0 right-0 w-20 h-20 bg-brand-gold/5 rounded-bl-full"></div>
				<h2 class="text-lg font-semibold text-brand-charcoal mb-4">Compliance Status</h2>
				{#if explanation}
					<dl class="space-y-3">
						<div class="flex justify-between">
							<dt class="text-brand-charcoal/60">Status</dt>
							<dd>
								<span class="px-2 py-1 rounded text-sm font-medium
									{explanation.compliance_status === 'pass' ? 'bg-brand-forest/10 text-brand-forest' :
									  explanation.compliance_status === 'flag' ? 'bg-brand-gold/10 text-brand-gold' :
									  'bg-brand-danger/10 text-brand-danger'}">
									{explanation.compliance_status ?? 'N/A'}
								</span>
							</dd>
						</div>
						<div>
							<dt class="text-brand-charcoal/60 mb-2">Flags</dt>
							<dd>
								{#if explanation.compliance_flags}
									<div class="bg-brand-warm-gray p-3 rounded-lg text-sm font-mono text-brand-charcoal">
										{explanation.compliance_flags}
									</div>
								{:else}
									<span class="text-brand-charcoal/40">None</span>
								{/if}
							</dd>
						</div>
					</dl>
				{:else}
					<p class="text-brand-charcoal/60">No compliance data available</p>
				{/if}
			</Card>
		</div>

		<!-- NRB Directive References -->
		{#if compliance && compliance.references.length > 0}
			<Card class="p-6 mt-6 relative overflow-hidden">
				<div class="absolute top-0 right-0 w-24 h-24 bg-brand-navy/5 rounded-bl-full"></div>
				<h2 class="text-lg font-semibold text-brand-charcoal mb-4">NRB Directive References</h2>
				<div class="space-y-4">
					{#each compliance.references as ref}
						<div class="border-l-4 border-brand-navy pl-4">
							<h3 class="font-medium text-brand-charcoal">{ref.clause}</h3>
							<p class="text-sm text-brand-charcoal/70 mt-1">{ref.text}</p>
							<p class="text-xs text-brand-charcoal/40 mt-1 font-mono">
								Relevance: {(ref.relevance_score * 100).toFixed(0)}%
							</p>
						</div>
					{/each}
				</div>
			</Card>
		{/if}
	{/if}
</div>
