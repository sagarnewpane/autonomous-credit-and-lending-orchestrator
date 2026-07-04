<script lang="ts">
	import { page } from '$app/stores';
	import { getDecision, getUserLoanHistory } from '$lib/services/loans';
	import { getAuth } from '$lib/stores/auth.svelte';
	import type { LoanApplicationRecord, LoanDecision } from '$lib/types/api';
	import Card from '$lib/components/ui/Card.svelte';
	import Badge from '$lib/components/ui/Badge.svelte';
	import Spinner from '$lib/components/ui/Spinner.svelte';
	import MandalaIcon from '$lib/components/ui/MandalaIcon.svelte';
	import { getDecisionBadgeVariant, getScoreColor } from '$lib/utils/decisions';

	const auth = getAuth();
	const applicationId = $derived($page.params.id);

	let application = $state<LoanApplicationRecord | null>(null);
	let decision = $state<LoanDecision | null>(null);
	let loading = $state(true);
	let error = $state('');

	$effect(() => {
		if (auth.user && applicationId) {
			loading = true;
			Promise.all([
				getUserLoanHistory(String(auth.user.id)),
				getDecision(applicationId).catch(() => null)
			])
				.then(([history, dec]) => {
					application = history.applications.find((a) => a.application_id === applicationId) ?? null;
					decision = dec;
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
	<a href="/dashboard/applications" class="text-brand-navy hover:text-brand-navy/80 text-sm font-medium mb-4 inline-block">
		← Back to Applications
	</a>

	<!-- Header -->
	<div class="flex items-center gap-3 mb-8">
		<MandalaIcon size={40} color="var(--brand-navy)" />
		<div>
			<h1 class="text-3xl font-bold text-brand-charcoal">Application Details</h1>
			<p class="text-brand-charcoal/60">View your application and decision</p>
		</div>
	</div>

	{#if loading}
		<div class="flex justify-center py-12"><Spinner /></div>
	{:else if error}
		<div class="bg-brand-danger/10 text-brand-danger p-4 rounded-lg" role="alert">{error}</div>
	{:else if !application}
		<div class="bg-brand-gold/10 text-brand-gold p-4 rounded-lg">Application not found</div>
	{:else}
		<div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
			<!-- Application Info Card -->
			<Card class="p-6 relative overflow-hidden">
				<div class="absolute top-0 right-0 w-20 h-20 bg-brand-navy/5 rounded-bl-full"></div>
				<h2 class="text-lg font-semibold text-brand-charcoal mb-4">Application Info</h2>
				<dl class="space-y-3">
					<div class="flex justify-between">
						<dt class="text-brand-charcoal/60">Application ID</dt>
						<dd class="font-mono text-sm text-brand-charcoal">{application.application_id}</dd>
					</div>
					<div class="flex justify-between">
						<dt class="text-brand-charcoal/60">Purpose</dt>
						<dd class="capitalize text-brand-charcoal">{application.loan_purpose?.replace('_', ' ')}</dd>
					</div>
					<div class="flex justify-between">
						<dt class="text-brand-charcoal/60">Requested Amount</dt>
						<dd class="font-semibold text-brand-charcoal font-mono">NPR {application.requested_amount_nrs?.toLocaleString()}</dd>
					</div>
					<div class="flex justify-between">
						<dt class="text-brand-charcoal/60">Tenure</dt>
						<dd class="text-brand-charcoal">{application.requested_tenure_months} months</dd>
					</div>
					<div class="flex justify-between">
						<dt class="text-brand-charcoal/60">Monthly Income</dt>
						<dd class="text-brand-charcoal font-mono">NPR {application.income_agent_monthly_est?.toLocaleString()}</dd>
					</div>
					<div class="flex justify-between">
						<dt class="text-brand-charcoal/60">Cooperative Member</dt>
						<dd class="text-brand-charcoal">{application.cooperative_member ? 'Yes' : 'No'}</dd>
					</div>
				</dl>
			</Card>

			<!-- Decision Card -->
			<Card class="p-6 relative overflow-hidden">
				<div class="absolute top-0 right-0 w-20 h-20 bg-brand-gold/5 rounded-bl-full"></div>
				<h2 class="text-lg font-semibold text-brand-charcoal mb-4">Decision</h2>
				{#if decision}
					<div class="space-y-4">
						<div class="text-center py-4">
							<Badge variant={getDecisionBadgeVariant(decision.decision)}>
								<span class="text-lg px-4 py-1">{decision.decision}</span>
							</Badge>
						</div>
						<dl class="space-y-3">
							<div class="flex justify-between">
								<dt class="text-brand-charcoal/60">Credit Score</dt>
								<dd class="text-2xl font-bold font-mono {decision.credit_score && decision.credit_score >= 700 ? 'text-brand-forest' : decision.credit_score && decision.credit_score >= 500 ? 'text-brand-gold' : 'text-brand-danger'}">
									{decision.credit_score ?? 'N/A'}
								</dd>
							</div>
							<div class="flex justify-between">
								<dt class="text-brand-charcoal/60">Score Band</dt>
								<dd class="text-brand-charcoal">{decision.score_band ?? 'N/A'}</dd>
							</div>
							<div class="flex justify-between">
								<dt class="text-brand-charcoal/60">Risk Tier</dt>
								<dd class="text-brand-charcoal">{decision.risk_tier ?? 'N/A'}</dd>
							</div>
							{#if decision.approved_amount_npr}
								<div class="flex justify-between">
									<dt class="text-brand-charcoal/60">Approved Amount</dt>
									<dd class="font-semibold text-brand-forest font-mono">NPR {decision.approved_amount_npr.toLocaleString()}</dd>
								</div>
							{/if}
						</dl>
					</div>
				{:else}
					<p class="text-brand-charcoal/60 text-center py-4">Decision pending...</p>
				{/if}
			</Card>
		</div>

		<!-- Action Buttons -->
		<div class="flex gap-4 mt-6">
			<a href="/dashboard/applications/{applicationId}/decision" class="bg-brand-navy text-white px-5 py-2 rounded-lg text-sm font-medium hover:bg-brand-navy/90 transition-colors">
				View Decision Details
			</a>
			<a href="/dashboard/applications/{applicationId}/explain" class="border border-brand-gray/30 text-brand-charcoal px-5 py-2 rounded-lg text-sm font-medium hover:bg-brand-warm-gray transition-colors">
				Explain Decision
			</a>
		</div>
	{/if}
</div>
