<script lang="ts">
	import { page } from '$app/stores';
	import { getDecision, getUserLoanHistory } from '$lib/services/loans';
	import { getAuth } from '$lib/stores/auth.svelte';
	import type { LoanApplicationRecord, LoanDecision } from '$lib/types/api';
	import Card from '$lib/components/ui/Card.svelte';
	import Badge from '$lib/components/ui/Badge.svelte';
	import Spinner from '$lib/components/ui/Spinner.svelte';
	import LanguageToggle from '$lib/components/ui/LanguageToggle.svelte';
	import { getDecisionColor, getDecisionBg, getDecisionIcon, getDecisionText, getScoreBgColor } from '$lib/utils/decisions';
	import { formatAmount } from '$lib/utils/format';

	const auth = getAuth();
	const applicationId = $derived($page.params.id);

	let lang = $state<'en' | 'ne'>('en');
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

<div class="min-h-screen bg-brand-cream">
	<header class="sticky top-0 z-40 bg-white/80 backdrop-blur-lg border-b border-brand-border/50">
		<div class="max-w-2xl mx-auto px-4 py-3 flex items-center justify-between">
			<a href="/dashboard/applications" class="flex items-center gap-2 text-brand-charcoal/60 hover:text-brand-charcoal transition-colors">
				<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
				</svg>
				<span class="text-sm font-medium">{lang === 'en' ? 'Back' : 'फिर्ता'}</span>
			</a>
			<LanguageToggle bind:lang />
		</div>
	</header>

	<main class="max-w-2xl mx-auto px-4 py-6 pb-24">
		{#if loading}
			<div class="flex justify-center py-16">
				<Spinner />
			</div>
		{:else if error}
			<div class="bg-brand-burgundy/10 text-brand-burgundy p-4 rounded-xl text-sm animate-fade-in" role="alert">
				{error}
			</div>
		{:else if !application}
			<div class="bg-brand-gold/10 text-brand-gold p-4 rounded-xl text-sm animate-fade-in">
				{lang === 'en' ? 'Application not found' : 'आवेदन फेला भएन'}
			</div>
		{:else}
			<!-- Decision Banner -->
			<div class="animate-fade-in-up">
				<div class="rounded-2xl border-2 {getDecisionBg(decision?.decision)} p-6 text-center mb-6">
					<div class="text-4xl mb-3">{getDecisionIcon(decision?.decision)}</div>
					<h1 class="text-2xl text-brand-charcoal font-display mb-1">
						{getDecisionText(decision?.decision)[lang]}
					</h1>
					<p class="text-sm text-brand-charcoal/60">
						{application.loan_purpose?.replace('_', ' ')} • NRs {formatAmount(application.requested_amount_nrs)}
					</p>
				</div>
			</div>

			<!-- Approved Amount (if approved) -->
			{#if decision?.decision === 'APPROVE' && decision?.approved_amount_npr}
				<Card class="p-6 mb-6 animate-fade-in-up stagger-1">
					<div class="text-center">
						<p class="text-sm text-brand-charcoal/50 mb-2">
							{lang === 'en' ? 'Approved Amount' : 'स्वीकृत रकम'}
						</p>
						<p class="text-4xl font-bold text-brand-forest font-mono">
							NRs {formatAmount(decision.approved_amount_npr)}
						</p>
						<p class="text-sm text-brand-charcoal/50 mt-2">
							{application.requested_tenure_months} {lang === 'en' ? 'months' : 'महिना'}
						</p>
					</div>
				</Card>
			{/if}

			<!-- Bilingual Decision Text -->
			{#if decision?.decision === 'APPROVE'}
				<Card class="p-6 mb-6 animate-fade-in-up stagger-2">
					<div class="bg-brand-warm-gray rounded-xl p-5 text-center">
						<p class="text-lg font-semibold text-brand-charcoal leading-relaxed">
							तपाईंको आवेदन {application.requested_tenure_months} महिनाको लागि NPR {formatAmount(decision.approved_amount_npr)} मा स्वीकृत गरिएको छ।
						</p>
						<p class="text-sm text-brand-charcoal/60 mt-3">
							Your application has been approved for NPR {formatAmount(decision.approved_amount_npr)} for {application.requested_tenure_months} months.
						</p>
					</div>
				</Card>
			{/if}

			<!-- Credit Score -->
			{#if decision?.credit_score}
				<Card class="p-6 mb-6 animate-fade-in-up stagger-3">
					<h2 class="text-sm font-semibold text-brand-charcoal/50 uppercase tracking-wide mb-4">
						{lang === 'en' ? 'Credit Score' : 'क्रेडिट स्कोर'}
					</h2>

					<!-- Score Gauge -->
					<div class="relative mb-4">
						<div class="h-3 bg-brand-warm-gray rounded-full overflow-hidden">
							<div
								class="h-full rounded-full transition-all duration-1000 ease-out
									{decision.credit_score >= 700 ? 'bg-brand-forest' : decision.credit_score >= 500 ? 'bg-brand-gold' : 'bg-brand-burgundy'}"
								style="width: {Math.min((decision.credit_score / 850) * 100, 100)}%"
							></div>
						</div>
						<div class="flex justify-between mt-2 text-xs text-brand-charcoal/40 font-mono">
							<span>300</span>
							<span>850</span>
						</div>
					</div>

					<div class="text-center">
						<span class="text-5xl font-bold font-mono {decision.credit_score >= 700 ? 'text-brand-forest' : decision.credit_score >= 500 ? 'text-brand-gold' : 'text-brand-burgundy'}">
							{decision.credit_score}
						</span>
						<p class="text-sm text-brand-charcoal/50 mt-1">{decision.score_band}</p>
					</div>
				</Card>
			{/if}

			<!-- Application Details -->
			<Card class="p-6 mb-6 animate-fade-in-up stagger-4">
				<h2 class="text-sm font-semibold text-brand-charcoal/50 uppercase tracking-wide mb-4">
					{lang === 'en' ? 'Application Details' : 'आवेदन विवरण'}
				</h2>

				<dl class="space-y-3">
					<div class="flex justify-between py-2 border-b border-brand-border">
						<dt class="text-sm text-brand-charcoal/60">{lang === 'en' ? 'Application ID' : 'आवेदन आईडी'}</dt>
						<dd class="font-mono text-sm font-medium text-brand-navy">{application.application_id}</dd>
					</div>
					<div class="flex justify-between py-2 border-b border-brand-border">
						<dt class="text-sm text-brand-charcoal/60">{lang === 'en' ? 'Requested Amount' : 'अनुरोध रकम'}</dt>
						<dd class="font-mono text-sm font-medium text-brand-charcoal">NRs {formatAmount(application.requested_amount_nrs)}</dd>
					</div>
					<div class="flex justify-between py-2 border-b border-brand-border">
						<dt class="text-sm text-brand-charcoal/60">{lang === 'en' ? 'Monthly Income' : 'मासिक आम्दानी'}</dt>
						<dd class="font-mono text-sm text-brand-charcoal">NRs {formatAmount(application.income_agent_monthly_est)}</dd>
					</div>
					{#if decision?.risk_tier}
						<div class="flex justify-between py-2">
							<dt class="text-sm text-brand-charcoal/60">{lang === 'en' ? 'Risk Tier' : 'जोखिम तह'}</dt>
							<dd class="text-sm font-medium text-brand-charcoal">{decision.risk_tier}</dd>
						</div>
					{/if}
				</dl>
			</Card>

			<!-- Next Steps -->
			<Card class="p-6 mb-6 animate-fade-in-up stagger-5">
				<h2 class="text-sm font-semibold text-brand-charcoal/50 uppercase tracking-wide mb-4">
					{lang === 'en' ? 'Next Steps' : 'अर्को कदम'}
				</h2>

				<div class="space-y-4">
					{#if decision?.decision === 'APPROVE'}
						<div class="flex items-start gap-3">
							<span class="w-6 h-6 bg-brand-navy text-white rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5">1</span>
							<p class="text-sm text-brand-charcoal">
								{lang === 'en'
									? 'Visit your nearest branch with your original citizenship certificate to sign the final agreement.'
									: 'अन्तिम सम्झौता हस्ताक्षर गर्न आफ्नो नजिकको शाखामा मूल नागरिकता प्रमाणपत्र लिएर जानुहोस्।'}
							</p>
						</div>
						<div class="flex items-start gap-3">
							<span class="w-6 h-6 bg-brand-navy text-white rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5">2</span>
							<p class="text-sm text-brand-charcoal">
								{lang === 'en'
									? 'Carry your land ownership document (Lalpurja) if your loan requires collateral.'
									: 'तपाईंको ऋणले जम्मा चाहिन्छ भने आफ्नो जमिन स्वामित्व कागजात (लालपुर्जा) लिएर जानुहोस्।'}
							</p>
						</div>
					{:else if decision?.decision === 'REJECT'}
						<div class="flex items-start gap-3">
							<span class="w-6 h-6 bg-brand-burgundy text-white rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
								<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
								</svg>
							</span>
							<p class="text-sm text-brand-charcoal">
								{lang === 'en'
									? 'You can reapply after 6 months. Please ensure all documents are accurate and your income matches bank statements.'
									: 'तपाईं ६ महिना पछि फेरि आवेदन गर्न सक्नुहुन्छ। कृपया सबै कागजातहरू सही छन् र तपाईंको आम्दानी बैंक स्टेटमेन्टसँग मेल खान्छ भनी सुनिश्चित गर्नुहोस्।'}
							</p>
						</div>
					{:else}
						<div class="flex items-start gap-3">
							<span class="w-6 h-6 bg-brand-gold text-white rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
								<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
								</svg>
							</span>
							<p class="text-sm text-brand-charcoal">
								{lang === 'en'
									? 'Your application is under review. We will notify you once a decision is made.'
									: 'तपाईंको आवेदन समीक्षाधीन छ। निर्णय भएपछि हामी सूचित गर्नेछौं।'}
							</p>
						</div>
					{/if}
				</div>
			</Card>

			<!-- Actions -->
			<div class="flex flex-col gap-3 animate-fade-in-up stagger-6">
				<a
					href="/dashboard/applications/{applicationId}/explain"
					class="bg-brand-navy text-white px-6 py-3 rounded-xl font-medium hover:bg-brand-navy-light transition-colors text-center"
				>
					{lang === 'en' ? 'View Detailed Explanation' : 'विस्तृत व्याख्या हेर्नुहोस्'}
				</a>
				<a
					href="/dashboard"
					class="text-brand-charcoal/60 hover:text-brand-charcoal transition-colors text-sm text-center"
				>
					{lang === 'en' ? 'Back to Dashboard' : 'ड्यासबोर्डमा फिर्ता'}
				</a>
			</div>
		{/if}
	</main>
</div>
