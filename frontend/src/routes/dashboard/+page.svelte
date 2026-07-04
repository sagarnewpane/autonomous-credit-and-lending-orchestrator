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
			getUserLoanHistory(String(auth.user.id))
				.then((res) => {
					applications = res.applications;
					loading = false;
				})
				.catch((err) => {
					error = err.message;
					loading = false;
				});
		}
	});
</script>

<div class="max-w-5xl mx-auto px-4 py-8">
	<!-- Header -->
	<div class="flex items-center gap-3 mb-8">
		<MandalaIcon size={36} color="var(--brand-navy)" />
		<div>
			<h1 class="text-2xl font-display text-brand-charcoal">Dashboard</h1>
			<p class="text-brand-charcoal/50 text-sm">Welcome back, {auth.user?.email?.split('@')[0]}</p>
		</div>
	</div>

	<!-- Stats Cards -->
	<div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
		<Card class="p-5 relative overflow-hidden">
			<div class="absolute top-0 left-0 w-full h-0.5 bg-brand-navy/15"></div>
			<p class="text-xs text-brand-charcoal/45 font-medium uppercase tracking-wider mb-1.5">Total applications</p>
			<p class="text-3xl font-bold text-brand-navy font-mono">{applications.length}</p>
		</Card>
		<Card class="p-5 relative overflow-hidden">
			<div class="absolute top-0 left-0 w-full h-0.5 bg-brand-forest/15"></div>
			<p class="text-xs text-brand-charcoal/45 font-medium uppercase tracking-wider mb-1.5">Approved</p>
			<p class="text-3xl font-bold text-brand-forest font-mono">
				{applications.filter((a) => a.final_decision === 'APPROVE').length}
			</p>
		</Card>
		<Card class="p-5 relative overflow-hidden">
			<div class="absolute top-0 left-0 w-full h-0.5 bg-brand-gold/20"></div>
			<p class="text-xs text-brand-charcoal/45 font-medium uppercase tracking-wider mb-1.5">Pending</p>
			<p class="text-3xl font-bold text-brand-gold-dark font-mono">
				{applications.filter((a) => !a.final_decision || a.final_decision === 'PENDING').length}
			</p>
		</Card>
	</div>

	<!-- Recent Applications Header -->
	<div class="flex items-center justify-between mb-4">
		<h2 class="text-lg font-display text-brand-charcoal">Recent applications</h2>
		{#if hasActiveApplication}
			<span class="text-xs text-brand-charcoal/40 bg-brand-warm-gray px-3 py-1.5 rounded-lg">
				Application in progress
			</span>
		{:else}
			<a href="/dashboard/apply" class="bg-brand-navy text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-brand-navy-light transition-colors shadow-sm">
				+ New application
			</a>
		{/if}
	</div>

	<!-- Applications List -->
	{#if loading}
		<div class="flex justify-center py-12"><Spinner /></div>
	{:else if error}
		<div class="bg-brand-danger/8 text-brand-danger p-4 rounded-lg text-sm border border-brand-danger/10" role="alert">{error}</div>
	{:else if applications.length === 0}
		<Card class="p-12 text-center">
			<div class="flex justify-center mb-4">
				<MandalaIcon size={40} color="var(--brand-charcoal)" opacity={0.2} />
			</div>
			<p class="text-brand-charcoal/50 mb-3 text-sm">No loan applications yet</p>
			<a href="/dashboard/apply" class="text-brand-navy hover:text-brand-navy-light font-medium text-sm transition-colors">
				Apply for your first loan
			</a>
		</Card>
	{:else}
		<div class="space-y-2.5">
			{#each applications.slice(0, 5) as app}
				<a href="/dashboard/applications/{app.application_id}">
					<Card class="p-4 hover:shadow-md transition-all duration-300 cursor-pointer group">
						<div class="flex items-center justify-between">
							<div class="flex items-center gap-4">
								<div class="w-9 h-9 bg-brand-navy/6 rounded-lg flex items-center justify-center group-hover:bg-brand-navy/10 transition-colors">
									<MandalaIcon size={18} color="var(--brand-navy)" />
								</div>
								<div>
									<p class="font-medium text-brand-charcoal text-sm">{app.loan_purpose}</p>
									<p class="text-xs text-brand-charcoal/40 font-mono">ID: {app.application_id}</p>
								</div>
							</div>
							<div class="text-right">
								<p class="font-semibold text-brand-charcoal font-mono text-sm">NPR {app.requested_amount_nrs?.toLocaleString()}</p>
								<Badge variant={getDecisionBadgeVariant(app.final_decision)}>
									{app.final_decision || 'PENDING'}
								</Badge>
							</div>
						</div>
					</Card>
				</a>
			{/each}
		</div>
	{/if}
</div>
