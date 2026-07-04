<script lang="ts">
	import { page } from '$app/stores';
	import { getDecision, explainDecision, adminReview, updateLoanApplication, getLoanDetail } from '$lib/services/loans';
	import type { LoanDecision, LoanExplanation, ShapFeature, AdminLoanRecord } from '$lib/types/api';
	import Card from '$lib/components/ui/Card.svelte';
	import Badge from '$lib/components/ui/Badge.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import Spinner from '$lib/components/ui/Spinner.svelte';
	import Modal from '$lib/components/ui/Modal.svelte';
	import MandalaIcon from '$lib/components/ui/MandalaIcon.svelte';
	import { getDecisionBadgeVariant, getScoreBgColor } from '$lib/utils/decisions';
	import { formatAmount, formatDate, formatJson } from '$lib/utils/format';

	const applicationId = $derived($page.params.id as string);

	let decision = $state<LoanDecision | null>(null);
	let explanation = $state<LoanExplanation | null>(null);
	let appDetail = $state<AdminLoanRecord | null>(null);
	let loading = $state(true);
	let error = $state('');
	let showOverrideModal = $state(false);
	let showEditModal = $state(false);
	let reviewDecision = $state('');
	let officerNotes = $state('');
	let submitting = $state(false);
	let submitMessage = $state('');

	// Edit state
	let editDecision = $state('');
	let editAmount = $state(0);
	let editInterestRate = $state(0);
	let editTenure = $state(0);
	let editNotes = $state('');
	let editSaving = $state(false);
	let editMessage = $state('');

	let shapFeatures = $derived<ShapFeature[]>(
		decision?.shap_features ?? [
			{ name: 'Stable Utility Payments', impact: 48, direction: 'positive' },
			{ name: 'Consistent Income', impact: 35, direction: 'positive' },
			{ name: 'Low Existing Debt', impact: 28, direction: 'positive' },
			{ name: 'High IMR', impact: -15, direction: 'negative' },
			{ name: 'Short Credit History', impact: -8, direction: 'negative' }
		]
	);

	let financialMetrics = $derived({
		imr: { value: decision?.imr ?? 1.14, status: (decision?.imr ?? 1.14) < 1.2 ? 'green' : (decision?.imr ?? 1.14) < 1.5 ? 'amber' : 'red', label: 'Income Mismatch Ratio' },
		dti: { value: decision?.dsr ?? 0.34, status: (decision?.dsr ?? 0.34) < 0.4 ? 'green' : (decision?.dsr ?? 0.34) < 0.5 ? 'amber' : 'red', label: 'Debt-to-Income' },
		lti: { value: decision?.lti ?? 2.8, status: (decision?.lti ?? 2.8) < 3.0 ? 'green' : (decision?.lti ?? 2.8) < 5.0 ? 'amber' : 'red', label: 'Loan-to-Income' }
	});

	let positiveImpact = $derived(shapFeatures.filter(f => f.direction === 'positive').reduce((sum, f) => sum + f.impact, 0));
	let negativeImpact = $derived(shapFeatures.filter(f => f.direction === 'negative').reduce((sum, f) => sum + Math.abs(f.impact), 0));
	let netImpact = $derived(positiveImpact - negativeImpact);

	function openEditModal() {
		editDecision = appDetail?.final_decision || decision?.decision || '';
		editAmount = appDetail?.approved_amount_nrs || decision?.approved_amount_npr || decision?.requested_amount_nrs || 0;
		editInterestRate = decision?.interest_rate || 11.0;
		editTenure = appDetail?.requested_tenure_months || decision?.requested_tenure_months || 12;
		editNotes = '';
		editMessage = '';
		showEditModal = true;
	}

	$effect(() => {
		if (applicationId) {
			Promise.all([
				getDecision(applicationId).catch(() => null),
				explainDecision(applicationId).catch(() => null),
				getLoanDetail(applicationId).catch(() => null)
			])
				.then(([dec, exp, detail]) => {
					decision = dec;
					explanation = exp;
					appDetail = detail?.application ?? null;
					loading = false;
				})
				.catch((err) => {
					error = err.message;
					loading = false;
				});
		}
	});

	async function handleOverride(e: Event) {
		e.preventDefault();
		if (!reviewDecision) {
			submitMessage = 'Please select a decision';
			return;
		}
		if (!officerNotes.trim()) {
			submitMessage = 'Officer notes are required';
			return;
		}

		submitting = true;
		submitMessage = '';
		try {
			const payload: Record<string, unknown> = {};
			if (reviewDecision) payload.override_decision = reviewDecision;
			if (officerNotes.trim()) payload.officer_notes = officerNotes;
			if (applicationId) {
				await adminReview(applicationId, payload);
				submitMessage = 'Override submitted successfully!';
				showOverrideModal = false;
				reviewDecision = '';
				officerNotes = '';
				// Refresh
				const [dec, exp, detail] = await Promise.all([
					getDecision(applicationId).catch(() => null),
					explainDecision(applicationId).catch(() => null),
					getLoanDetail(applicationId).catch(() => null)
				]);
				decision = dec;
				explanation = exp;
				appDetail = detail?.application ?? null;
			}
		} catch (err: unknown) {
			submitMessage = err instanceof Error ? err.message : 'Failed to submit override';
		} finally {
			submitting = false;
		}
	}

	async function handleEditSave(e: Event) {
		e.preventDefault();
		editSaving = true;
		editMessage = '';
		try {
			const updates: Record<string, unknown> = {};
			if (editDecision) updates.final_decision = editDecision;
			if (editAmount > 0) updates.approved_amount_nrs = editAmount;
			if (editInterestRate > 0) updates.interest_rate = editInterestRate;
			if (editTenure > 0) updates.requested_tenure_months = editTenure;
			if (editNotes.trim()) updates.officer_notes = editNotes;

			await updateLoanApplication(applicationId, updates);
			editMessage = 'Application updated successfully!';
			showEditModal = false;
			// Refresh
			const [dec, exp, detail] = await Promise.all([
				getDecision(applicationId).catch(() => null),
				explainDecision(applicationId).catch(() => null),
				getLoanDetail(applicationId).catch(() => null)
			]);
			decision = dec;
			explanation = exp;
			appDetail = detail?.application ?? null;
		} catch (err: unknown) {
			editMessage = err instanceof Error ? err.message : 'Failed to save';
		} finally {
			editSaving = false;
		}
	}
</script>

<div class="min-h-screen bg-brand-cream">
	<!-- Header -->
	<header class="bg-white border-b border-brand-border sticky top-0 z-40">
		<div class="max-w-7xl mx-auto px-4 sm:px-6 py-4">
			<div class="flex items-center justify-between">
				<div class="flex items-center gap-4">
					<a href="/admin/loans" class="text-brand-charcoal/40 hover:text-brand-charcoal transition-colors" aria-label="Back to loans list">
						<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
						</svg>
					</a>
					<div class="flex items-center gap-3">
						<MandalaIcon size={32} color="var(--brand-navy)" />
						<div>
							<h1 class="text-lg text-brand-charcoal font-display">Application Review</h1>
							<p class="text-xs text-brand-charcoal/50 font-mono">{applicationId}</p>
						</div>
					</div>
				</div>
				<div class="flex items-center gap-3">
					<a href="/admin/{applicationId}/audit" class="text-sm text-brand-navy hover:text-brand-navy-light font-medium transition-colors hidden sm:inline-flex items-center gap-1">
						<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
						</svg>
						Audit Trail
					</a>
					<Button variant="secondary" size="sm" onclick={openEditModal}>
						<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
						</svg>
						Edit
					</Button>
					<Button variant="primary" size="sm" onclick={() => (showOverrideModal = true)}>
						Override Decision
					</Button>
				</div>
			</div>
		</div>
	</header>

	<main class="max-w-7xl mx-auto px-4 sm:px-6 py-6">
		{#if loading}
			<div class="flex justify-center py-16"><Spinner /></div>
		{:else if error}
			<div class="bg-brand-burgundy/10 text-brand-burgundy p-4 rounded-xl text-sm" role="alert">{error}</div>
		{:else}
			<!-- Success Message -->
			{#if (submitMessage && submitMessage.includes('success')) || (editMessage && editMessage.includes('success'))}
				<div class="bg-brand-forest/10 text-brand-forest p-4 rounded-xl text-sm mb-6 animate-fade-in flex items-center gap-3">
					<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
					</svg>
					{submitMessage || editMessage}
				</div>
			{/if}

			<!-- Applicant Info Banner -->
			{#if appDetail}
				<div class="bg-white rounded-2xl border border-brand-border p-5 mb-6">
					<div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
						<div class="flex items-center gap-4">
							<div class="w-14 h-14 rounded-2xl bg-brand-navy/10 flex items-center justify-center flex-shrink-0">
								<svg class="w-7 h-7 text-brand-navy" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
								</svg>
							</div>
							<div>
								<h2 class="text-lg font-semibold text-brand-charcoal">
									{(appDetail as unknown as Record<string, unknown>)['citizenship_extracted_name'] as string || appDetail.applicant_id || 'Unknown Applicant'}
								</h2>
								<div class="flex flex-wrap items-center gap-3 text-sm text-brand-charcoal/50">
									<span class="font-mono">{appDetail.applicant_id}</span>
									{#if (appDetail as unknown as Record<string, unknown>)['citizenship_number']}
										<span>•</span>
										<span class="font-mono">{(appDetail as unknown as Record<string, unknown>)['citizenship_number'] as string}</span>
									{/if}
									{#if (appDetail as unknown as Record<string, unknown>)['phone_primary']}
										<span>•</span>
										<span>{(appDetail as unknown as Record<string, unknown>)['phone_primary'] as string}</span>
									{/if}
								</div>
							</div>
						</div>
						<div class="flex items-center gap-4">
							<div class="text-right">
								<p class="text-xs text-brand-charcoal/40">Applied</p>
								<p class="text-sm font-medium text-brand-charcoal">{appDetail.application_date_ad ? formatDate(appDetail.application_date_ad) : '—'}</p>
							</div>
							<div class="text-right">
								<p class="text-xs text-brand-charcoal/40">User ID</p>
								<p class="text-sm font-mono text-brand-navy">{appDetail.applicant_id || '—'}</p>
							</div>
						</div>
					</div>
				</div>
			{/if}

			<!-- Split View Layout -->
			<div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
				<!-- Left Panel: The Facts -->
				<div class="space-y-6">
					<!-- Decision Matrix Card -->
					<Card class="p-6">
						<h2 class="text-sm font-semibold text-brand-charcoal/50 uppercase tracking-wider mb-4 flex items-center gap-2">
							<span class="w-2 h-2 bg-brand-navy rounded-full"></span>
							Decision Matrix
						</h2>

						{#if decision}
							<!-- Decision Banner -->
							<div class="rounded-xl border-2 {decision.decision === 'APPROVE' ? 'border-brand-forest/30 bg-brand-forest/5' : decision.decision === 'REJECT' ? 'border-brand-burgundy/30 bg-brand-burgundy/5' : 'border-brand-gold/30 bg-brand-gold/5'} p-4 mb-4">
								<div class="flex items-center justify-between">
									<div>
										<p class="text-xs text-brand-charcoal/50 mb-1">Final AI Decision</p>
										<Badge variant={getDecisionBadgeVariant(decision.decision)} size="md">
											{decision.decision}
										</Badge>
									</div>
									{#if decision.approved_amount_npr}
										<div class="text-right">
											<p class="text-xs text-brand-charcoal/50 mb-1">Approved Amount</p>
											<p class="text-xl font-bold text-brand-forest font-mono">NPR {formatAmount(decision.approved_amount_npr)}</p>
										</div>
									{/if}
								</div>
							</div>

							<!-- Score and Risk -->
							<div class="grid grid-cols-2 gap-4">
								<div class="bg-brand-warm-gray rounded-xl p-4">
									<p class="text-xs text-brand-charcoal/50 mb-1">Credit Score</p>
									<div class="flex items-end gap-2">
										<span class="text-3xl font-bold font-mono {decision.credit_score && decision.credit_score >= 700 ? 'text-brand-forest' : decision.credit_score && decision.credit_score >= 500 ? 'text-brand-gold' : 'text-brand-burgundy'}">
											{decision.credit_score ?? '—'}
										</span>
										<span class="text-xs text-brand-charcoal/40 mb-1">/ 850</span>
									</div>
									<!-- Mini gauge -->
									<div class="h-1.5 bg-brand-warm-gray rounded-full mt-2 overflow-hidden">
										<div
											class="h-full rounded-full {decision.credit_score && decision.credit_score >= 700 ? 'bg-brand-forest' : decision.credit_score && decision.credit_score >= 500 ? 'bg-brand-gold' : 'bg-brand-burgundy'}"
											style="width: {decision.credit_score ? (decision.credit_score / 850) * 100 : 0}%"
										></div>
									</div>
								</div>
								<div class="bg-brand-warm-gray rounded-xl p-4">
									<p class="text-xs text-brand-charcoal/50 mb-1">Risk Tier</p>
									<p class="text-xl font-bold text-brand-charcoal">{decision.risk_tier ?? '—'}</p>
									<p class="text-xs text-brand-charcoal/40 mt-1">{decision.score_band ?? ''}</p>
								</div>
							</div>

							<!-- Interest Tier -->
							<div class="mt-4 bg-brand-navy/5 rounded-xl p-4 flex items-center justify-between">
								<div>
									<p class="text-xs text-brand-charcoal/50">Interest Tier</p>
									<p class="text-sm font-semibold text-brand-navy">{decision?.risk_tier ?? 'Base'} ({decision?.interest_rate ?? 11.0}%)</p>
								</div>
								<span class="w-10 h-10 bg-brand-navy/10 rounded-lg flex items-center justify-center">
									<svg class="w-5 h-5 text-brand-navy" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
									</svg>
								</span>
							</div>
						{:else}
							<p class="text-brand-charcoal/40 text-center py-8">No decision available</p>
						{/if}
					</Card>

					<!-- Financial Metrics Card -->
					<Card class="p-6">
						<h2 class="text-sm font-semibold text-brand-charcoal/50 uppercase tracking-wider mb-4 flex items-center gap-2">
							<span class="w-2 h-2 bg-brand-forest rounded-full"></span>
							Financial Metrics
						</h2>

						<div class="space-y-3">
							{#each Object.entries(financialMetrics) as [key, metric]}
								<div class="flex items-center justify-between p-3 bg-brand-warm-gray rounded-xl">
									<div>
										<p class="text-sm font-medium text-brand-charcoal">{metric.label}</p>
										<p class="text-xs text-brand-charcoal/40 uppercase">{key.toUpperCase()}</p>
									</div>
									<div class="text-right">
										<span class="text-xl font-bold font-mono {metric.status === 'green' ? 'text-brand-forest' : metric.status === 'amber' ? 'text-brand-gold' : 'text-brand-burgundy'}">
											{metric.value}
										</span>
										<div class="flex items-center gap-1 justify-end mt-0.5">
											<span class="w-1.5 h-1.5 rounded-full {metric.status === 'green' ? 'bg-brand-forest' : metric.status === 'amber' ? 'bg-brand-gold' : 'bg-brand-burgundy'}"></span>
											<span class="text-[10px] text-brand-charcoal/50">
												{metric.status === 'green' ? 'Consensus' : metric.status === 'amber' ? 'Caution' : 'Alert'}
											</span>
										</div>
									</div>
								</div>
							{/each}
						</div>
					</Card>

					<!-- Compliance & Audit Trail Card -->
					<Card class="p-6">
						<h2 class="text-sm font-semibold text-brand-charcoal/50 uppercase tracking-wider mb-4 flex items-center gap-2">
							<span class="w-2 h-2 bg-brand-gold rounded-full"></span>
							Compliance & Audit Trail
						</h2>

						<!-- NRB Checks -->
						<div class="mb-4">
							<p class="text-xs text-brand-charcoal/50 mb-2">NRB Checks</p>
							<div class="space-y-2">
								{#each ['Income Verification', 'Debt Limits', 'Collateral Validation', 'AML Screening'] as check}
									{@const passed = explanation?.compliance_status !== 'fail'}
									<div class="flex items-center gap-2 text-sm">
										<span class="w-5 h-5 {passed ? 'bg-brand-forest/10' : 'bg-brand-burgundy/10'} rounded-full flex items-center justify-center">
											{#if passed}
												<svg class="w-3 h-3 text-brand-forest" fill="none" stroke="currentColor" viewBox="0 0 24 24">
													<path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" />
												</svg>
											{:else}
												<svg class="w-3 h-3 text-brand-burgundy" fill="none" stroke="currentColor" viewBox="0 0 24 24">
													<path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M6 18L18 6M6 6l12 12" />
												</svg>
											{/if}
										</span>
										<span class="text-brand-charcoal/70">{check}</span>
									</div>
								{/each}
							</div>
						</div>

						<!-- Decision Summary -->
						<div>
							<p class="text-xs text-brand-charcoal/50 mb-2">Decision Summary</p>
							<div class="space-y-2">
								<div class="flex items-start gap-3 text-sm">
									<div class="w-2 h-2 bg-brand-navy/20 rounded-full mt-1.5 flex-shrink-0"></div>
									<div>
										<span class="font-medium text-brand-charcoal">Purpose:</span>
										<span class="text-brand-charcoal/60">{decision?.loan_purpose?.replace('_', ' ') ?? 'N/A'}</span>
									</div>
								</div>
								<div class="flex items-start gap-3 text-sm">
									<div class="w-2 h-2 bg-brand-navy/20 rounded-full mt-1.5 flex-shrink-0"></div>
									<div>
										<span class="font-medium text-brand-charcoal">Amount:</span>
										<span class="text-brand-charcoal/60">NPR {formatAmount(decision?.requested_amount_nrs ?? 0)}</span>
									</div>
								</div>
								<div class="flex items-start gap-3 text-sm">
									<div class="w-2 h-2 bg-brand-navy/20 rounded-full mt-1.5 flex-shrink-0"></div>
									<div>
										<span class="font-medium text-brand-charcoal">Tenure:</span>
										<span class="text-brand-charcoal/60">{decision?.requested_tenure_months ?? 'N/A'} months</span>
									</div>
								</div>
								<div class="flex items-start gap-3 text-sm">
									<div class="w-2 h-2 bg-brand-navy/20 rounded-full mt-1.5 flex-shrink-0"></div>
									<div>
										<span class="font-medium text-brand-charcoal">Collateral:</span>
										<span class="text-brand-charcoal/60">{decision?.collateral_type ?? 'None'}</span>
									</div>
								</div>
								{#if decision?.interest_rate}
									<div class="flex items-start gap-3 text-sm">
										<div class="w-2 h-2 bg-brand-navy/20 rounded-full mt-1.5 flex-shrink-0"></div>
										<div>
											<span class="font-medium text-brand-charcoal">Interest Rate:</span>
											<span class="text-brand-charcoal/60">{decision.interest_rate}%</span>
										</div>
									</div>
								{/if}
							</div>
						</div>

						<!-- Officer Notes -->
						{#if (appDetail as unknown as Record<string, unknown>)['officer_notes']}
							<div class="mt-4 bg-brand-gold/5 rounded-xl p-3 border border-brand-gold/20">
								<p class="text-xs text-brand-charcoal/50 mb-1">Officer Notes</p>
								<p class="text-sm text-brand-charcoal">{(appDetail as unknown as Record<string, unknown>)['officer_notes'] as string}</p>
							</div>
						{/if}
					</Card>
				</div>

				<!-- Right Panel: AI Explainability -->
				<div class="space-y-6">
					<!-- SHAP Explainability Card -->
					<Card class="p-6">
						<h2 class="text-sm font-semibold text-brand-charcoal/50 uppercase tracking-wider mb-4 flex items-center gap-2">
							<span class="w-2 h-2 bg-brand-burgundy rounded-full"></span>
							AI Explainability (SHAP)
						</h2>

						<p class="text-xs text-brand-charcoal/50 mb-6">Top features influencing the credit score</p>

						<!-- SHAP Bar Chart -->
						<div class="space-y-3">
							{#each shapFeatures as feature}
								{@const maxImpact = 50}
								{@const widthPercent = Math.abs(feature.impact) / maxImpact * 100}
								<div>
									<div class="flex items-center justify-between mb-1">
										<span class="text-sm text-brand-charcoal">{feature.name}</span>
										<span class="text-sm font-mono font-semibold {feature.direction === 'positive' ? 'text-brand-forest' : 'text-brand-burgundy'}">
											{feature.direction === 'positive' ? '+' : ''}{feature.impact} pts
										</span>
									</div>
									<div class="h-2 bg-brand-warm-gray rounded-full overflow-hidden">
										<div
											class="h-full rounded-full transition-all duration-700 ease-out {feature.direction === 'positive' ? 'bg-brand-forest' : 'bg-brand-burgundy'}"
											style="width: {widthPercent}%"
										></div>
									</div>
								</div>
							{/each}
						</div>

						<!-- Summary -->
						<div class="mt-6 bg-brand-warm-gray rounded-xl p-4">
							<p class="text-xs text-brand-charcoal/50 mb-1">Net Impact</p>
							<p class="text-lg font-bold {netImpact >= 0 ? 'text-brand-forest' : 'text-brand-burgundy'} font-mono">
								{netImpact >= 0 ? '+' : ''}{netImpact} points
							</p>
							<p class="text-xs text-brand-charcoal/40 mt-1">
								Overall positive factors outweigh negative by {negativeImpact > 0 ? (positiveImpact / negativeImpact).toFixed(1) : '∞'}x
							</p>
						</div>
					</Card>

					<!-- Compliance Status Card -->
					{#if explanation}
						<Card class="p-6">
							<h2 class="text-sm font-semibold text-brand-charcoal/50 uppercase tracking-wider mb-4 flex items-center gap-2">
								<span class="w-2 h-2 {explanation.compliance_status === 'pass' ? 'bg-brand-forest' : explanation.compliance_status === 'flag' ? 'bg-brand-gold' : 'bg-brand-burgundy'} rounded-full"></span>
								Compliance Status
							</h2>

							<div class="flex items-center gap-3 mb-4">
								<span class="px-3 py-1.5 rounded-lg text-sm font-semibold
									{explanation.compliance_status === 'pass' ? 'bg-brand-forest/10 text-brand-forest' :
									  explanation.compliance_status === 'flag' ? 'bg-brand-gold/10 text-brand-gold' :
									  'bg-brand-burgundy/10 text-brand-burgundy'}">
									{explanation.compliance_status?.toUpperCase() ?? 'UNKNOWN'}
								</span>
							</div>

							{#if explanation.compliance_flags}
								<div class="bg-brand-warm-gray rounded-xl p-3">
									<p class="text-xs text-brand-charcoal/50 mb-1">Flags</p>
									<p class="text-sm text-brand-charcoal font-mono">{explanation.compliance_flags}</p>
								</div>
							{/if}
						</Card>
					{/if}

					<!-- Document Extraction Card -->
					<Card class="p-6">
						<h2 class="text-sm font-semibold text-brand-charcoal/50 uppercase tracking-wider mb-4 flex items-center gap-2">
							<span class="w-2 h-2 bg-brand-navy rounded-full"></span>
							Extracted Data
						</h2>

						<div class="space-y-3">
							<!-- Income & Debt Analysis -->
							<div class="bg-brand-warm-gray rounded-xl p-4">
								<p class="text-xs text-brand-charcoal/50 mb-2">Income & Debt Analysis</p>
								<div class="grid grid-cols-2 gap-4 text-sm">
									<div>
										<span class="text-brand-charcoal/40">Monthly Income:</span>
										<span class="font-mono text-brand-forest font-medium ml-1">NPR {formatAmount(decision?.income_agent_monthly_est ?? 0)}</span>
									</div>
									<div>
										<span class="text-brand-charcoal/40">Monthly Debt:</span>
										<span class="font-mono text-brand-charcoal ml-1">NPR {formatAmount(decision?.monthly_debt ?? 0)}</span>
									</div>
									<div>
										<span class="text-brand-charcoal/40">DSR:</span>
										<span class="font-mono {(decision?.dsr ?? 0) < 0.4 ? 'text-brand-forest' : 'text-brand-gold'} font-medium ml-1">
											{((decision?.dsr ?? 0) * 100).toFixed(1)}%
										</span>
									</div>
									<div>
										<span class="text-brand-charcoal/40">IMR:</span>
										<span class="font-mono {(decision?.imr ?? 0) < 1.2 ? 'text-brand-forest' : 'text-brand-gold'} font-medium ml-1">
											{decision?.imr?.toFixed(2) ?? 'N/A'}
										</span>
									</div>
								</div>
							</div>

							<!-- Credit Score Breakdown -->
							<div class="bg-brand-warm-gray rounded-xl p-4">
								<p class="text-xs text-brand-charcoal/50 mb-2">Credit Assessment</p>
								<div class="grid grid-cols-2 gap-4 text-sm">
									<div>
										<span class="text-brand-charcoal/40">Score:</span>
										<span class="font-mono font-bold {(decision?.credit_score ?? 0) >= 700 ? 'text-brand-forest' : (decision?.credit_score ?? 0) >= 500 ? 'text-brand-gold' : 'text-brand-burgundy'} ml-1">
											{decision?.credit_score ?? 'N/A'}
										</span>
									</div>
									<div>
										<span class="text-brand-charcoal/40">Band:</span>
										<span class="font-mono text-brand-charcoal ml-1">{decision?.score_band ?? 'N/A'}</span>
									</div>
									<div>
										<span class="text-brand-charcoal/40">LTI:</span>
										<span class="font-mono {(decision?.lti ?? 0) < 3 ? 'text-brand-forest' : 'text-brand-gold'} font-medium ml-1">
											{decision?.lti?.toFixed(1) ?? 'N/A'}x
										</span>
									</div>
									<div>
										<span class="text-brand-charcoal/40">Risk Tier:</span>
										<span class="font-mono text-brand-charcoal ml-1">{decision?.risk_tier ?? 'N/A'}</span>
									</div>
								</div>
							</div>
						</div>
					</Card>

					<!-- Raw Application Data Card -->
					{#if appDetail}
						<Card class="p-6">
							<h2 class="text-sm font-semibold text-brand-charcoal/50 uppercase tracking-wider mb-4 flex items-center gap-2">
								<span class="w-2 h-2 bg-brand-charcoal/30 rounded-full"></span>
								Raw Application Data
							</h2>
							<div class="bg-brand-charcoal rounded-xl p-4 overflow-x-auto max-h-64 overflow-y-auto">
								<pre class="text-xs text-green-400 font-mono whitespace-pre-wrap leading-relaxed">{formatJson(appDetail)}</pre>
							</div>
						</Card>
					{/if}
				</div>
			</div>
		{/if}
	</main>
</div>

<!-- Override Modal -->
<Modal bind:open={showOverrideModal} title="Override AI Decision" size="md">
	<form onsubmit={handleOverride} class="space-y-4">
		<div>
			<label for="override-decision" class="block text-sm font-medium text-brand-charcoal mb-1.5">
				Change Decision To
			</label>
			<select
				id="override-decision"
				bind:value={reviewDecision}
				class="w-full px-4 py-3 rounded-xl border border-brand-border text-sm focus:outline-none focus:ring-2 focus:ring-brand-gold/30 focus:border-brand-gold"
			>
				<option value="">Select decision...</option>
				<option value="APPROVE">Approve</option>
				<option value="MODIFY">Modify (Conditional)</option>
				<option value="REJECT">Reject</option>
				<option value="MANUAL_REVIEW">Manual Review</option>
			</select>
		</div>

		<div>
			<label for="officer-notes" class="block text-sm font-medium text-brand-charcoal mb-1.5">
				Officer Notes <span class="text-brand-burgundy">*</span>
			</label>
			<textarea
				id="officer-notes"
				bind:value={officerNotes}
				rows="4"
				placeholder="Explain the reason for this override..."
				required
				class="w-full px-4 py-3 rounded-xl border border-brand-border text-sm focus:outline-none focus:ring-2 focus:ring-brand-gold/30 focus:border-brand-gold resize-none"
			></textarea>
		</div>

		{#if submitMessage && !submitMessage.includes('success')}
			<div class="bg-brand-burgundy/10 text-brand-burgundy p-3 rounded-xl text-sm">{submitMessage}</div>
		{/if}

		<div class="flex gap-3 pt-2">
			<Button variant="secondary" onclick={() => (showOverrideModal = false)} class="flex-1">Cancel</Button>
			<Button type="submit" variant="primary" loading={submitting} class="flex-1">Submit Override</Button>
		</div>
	</form>
</Modal>

<!-- Edit Modal -->
<Modal bind:open={showEditModal} title="Edit Application" size="md">
	<form onsubmit={handleEditSave} class="space-y-4">
		<div>
			<label for="edit-decision" class="block text-sm font-medium text-brand-charcoal mb-1.5">
				Decision
			</label>
			<select
				id="edit-decision"
				bind:value={editDecision}
				class="w-full px-4 py-3 rounded-xl border border-brand-border text-sm focus:outline-none focus:ring-2 focus:ring-brand-gold/30 focus:border-brand-gold"
			>
				<option value="">No change</option>
				<option value="APPROVE">Approve</option>
				<option value="MODIFY">Modify (Conditional)</option>
				<option value="REJECT">Reject</option>
				<option value="MANUAL_REVIEW">Manual Review</option>
				<option value="PENDING">Pending</option>
			</select>
		</div>

		<div class="grid grid-cols-2 gap-4">
			<div>
				<label for="edit-amount" class="block text-sm font-medium text-brand-charcoal mb-1.5">
					Approved Amount (NPR)
				</label>
				<input
					id="edit-amount"
					type="number"
					bind:value={editAmount}
					min="0"
					class="w-full px-4 py-3 rounded-xl border border-brand-border text-sm focus:outline-none focus:ring-2 focus:ring-brand-gold/30 focus:border-brand-gold font-mono"
				/>
			</div>
			<div>
				<label for="edit-interest" class="block text-sm font-medium text-brand-charcoal mb-1.5">
					Interest Rate (%)
				</label>
				<input
					id="edit-interest"
					type="number"
					bind:value={editInterestRate}
					min="0"
					max="30"
					step="0.1"
					class="w-full px-4 py-3 rounded-xl border border-brand-border text-sm focus:outline-none focus:ring-2 focus:ring-brand-gold/30 focus:border-brand-gold font-mono"
				/>
			</div>
		</div>

		<div>
			<label for="edit-tenure" class="block text-sm font-medium text-brand-charcoal mb-1.5">
				Tenure (months)
			</label>
			<input
				id="edit-tenure"
				type="number"
				bind:value={editTenure}
				min="1"
				max="360"
				class="w-full px-4 py-3 rounded-xl border border-brand-border text-sm focus:outline-none focus:ring-2 focus:ring-brand-gold/30 focus:border-brand-gold font-mono"
			/>
		</div>

		<div>
			<label for="edit-notes" class="block text-sm font-medium text-brand-charcoal mb-1.5">
				Officer Notes
			</label>
			<textarea
				id="edit-notes"
				bind:value={editNotes}
				rows="3"
				placeholder="Add any notes about this change..."
				class="w-full px-4 py-3 rounded-xl border border-brand-border text-sm focus:outline-none focus:ring-2 focus:ring-brand-gold/30 focus:border-brand-gold resize-none"
			></textarea>
		</div>

		{#if editMessage}
			<div class="p-3 rounded-xl text-sm {editMessage.includes('success') ? 'bg-brand-forest/10 text-brand-forest' : 'bg-brand-burgundy/10 text-brand-burgundy'}">
				{editMessage}
			</div>
		{/if}

		<div class="flex gap-3 pt-2">
			<Button variant="secondary" onclick={() => (showEditModal = false)} class="flex-1">Cancel</Button>
			<Button type="submit" variant="primary" loading={editSaving} class="flex-1">Save Changes</Button>
		</div>
	</form>
</Modal>
