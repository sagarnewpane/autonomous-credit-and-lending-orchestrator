<script lang="ts">
	import { getAuth } from '$lib/stores/auth.svelte';
	import { getUserLoanHistory } from '$lib/services/loans';
	import type { LoanApplicationRecord } from '$lib/types/api';
	import Card from '$lib/components/ui/Card.svelte';
	import Badge from '$lib/components/ui/Badge.svelte';
	import Spinner from '$lib/components/ui/Spinner.svelte';
	import MandalaIcon from '$lib/components/ui/MandalaIcon.svelte';
	import { getDecisionBadgeVariant } from '$lib/utils/decisions';

	const auth = getAuth();

	let applications = $state<LoanApplicationRecord[]>([]);
	let loading = $state(true);
	let error = $state('');

	let hasActiveApplication = $derived(
		applications.some((a) => !a.final_decision || a.final_decision === 'PENDING')
	);

	$effect(() => {
		if (auth.user) {
			getUserLoanHistory()
				.then((res) => {
					applications = res.applications;
					loading = false;
				})
				.catch((err) => {
					error = err.message;
					loading = false;
				});
		} else {
			loading = false;
		}
	});
</script>

<div class="max-w-6xl mx-auto px-4 py-8">
	<!-- Header -->
	<div class="flex items-center justify-between mb-8">
		<div class="flex items-center gap-3">
			<MandalaIcon size={40} color="var(--brand-navy)" />
			<div>
				<h1 class="text-3xl font-bold text-brand-charcoal">My Applications</h1>
				<p class="text-brand-charcoal/60">View and track your loan applications</p>
			</div>
		</div>
		{#if hasActiveApplication}
			<span class="text-sm text-brand-charcoal/40 bg-brand-warm-gray px-4 py-2 rounded-lg">
				Application in progress
			</span>
		{:else}
			<a href="/dashboard/apply" class="bg-brand-navy text-white px-5 py-2 rounded-lg text-sm font-medium hover:bg-brand-navy/90 transition-colors">
				+ New Application
			</a>
		{/if}
	</div>

	{#if loading}
		<div class="flex justify-center py-12"><Spinner /></div>
	{:else if error}
		<div class="bg-brand-danger/10 text-brand-danger p-4 rounded-lg" role="alert">{error}</div>
	{:else if applications.length === 0}
		<Card class="p-12 text-center">
			<div class="flex justify-center mb-4">
				<MandalaIcon size={48} color="var(--brand-charcoal)" opacity={0.3} />
			</div>
			<p class="text-brand-charcoal/60 mb-4">No applications found</p>
			<a href="/dashboard/apply" class="text-brand-navy hover:text-brand-navy/80 font-medium">
				Apply for a loan →
			</a>
		</Card>
	{:else}
		<div class="bg-white rounded-2xl shadow-sm border border-brand-border overflow-hidden">
			<table class="w-full">
				<thead class="bg-brand-warm-gray border-b border-brand-border">
					<tr>
						<th class="px-6 py-3 text-left text-xs font-medium text-brand-charcoal/60 uppercase">Application ID</th>
						<th class="px-6 py-3 text-left text-xs font-medium text-brand-charcoal/60 uppercase">Purpose</th>
						<th class="px-6 py-3 text-left text-xs font-medium text-brand-charcoal/60 uppercase">Amount</th>
						<th class="px-6 py-3 text-left text-xs font-medium text-brand-charcoal/60 uppercase">Tenure</th>
						<th class="px-6 py-3 text-left text-xs font-medium text-brand-charcoal/60 uppercase">Score</th>
						<th class="px-6 py-3 text-left text-xs font-medium text-brand-charcoal/60 uppercase">Decision</th>
						<th class="px-6 py-3 text-left text-xs font-medium text-brand-charcoal/60 uppercase"></th>
					</tr>
				</thead>
				<tbody class="divide-y divide-brand-border">
					{#each applications as app}
						<tr class="hover:bg-brand-warm-gray/50 transition-colors">
							<td class="px-6 py-4 text-sm font-mono text-brand-charcoal">{app.application_id}</td>
							<td class="px-6 py-4 text-sm text-brand-charcoal/70 capitalize">{app.loan_purpose?.replace('_', ' ')}</td>
							<td class="px-6 py-4 text-sm font-medium text-brand-charcoal font-mono">NPR {app.requested_amount_nrs?.toLocaleString()}</td>
							<td class="px-6 py-4 text-sm text-brand-charcoal/70">{app.requested_tenure_months} mo</td>
							<td class="px-6 py-4 text-sm text-brand-charcoal/70 font-mono">{app.credit_score ?? '—'}</td>
							<td class="px-6 py-4">
								<Badge variant={getDecisionBadgeVariant(app.final_decision)}>
									{app.final_decision || 'PENDING'}
								</Badge>
							</td>
							<td class="px-6 py-4">
								<a href="/dashboard/applications/{app.application_id}" class="text-brand-navy hover:text-brand-navy/80 text-sm font-medium">
									View →
								</a>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</div>
