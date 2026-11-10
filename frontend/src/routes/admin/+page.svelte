<script lang="ts">
	import { getAdminStats } from '$lib/services/loans';
	import type { AdminStats, AdminLoanRecord } from '$lib/types/api';
	import Card from '$lib/components/ui/Card.svelte';
	import Badge from '$lib/components/ui/Badge.svelte';
	import Spinner from '$lib/components/ui/Spinner.svelte';
	import MandalaIcon from '$lib/components/ui/MandalaIcon.svelte';
	import { getDecisionBadgeVariant, getScoreColor } from '$lib/utils/decisions';
	import { formatAmount, formatDate } from '$lib/utils/format';

	let stats = $state<AdminStats | null>(null);
	let loading = $state(true);
	let error = $state('');

	$effect(() => {
		getAdminStats()
			.then((res) => {
				stats = res;
				loading = false;
			})
			.catch((err) => {
				error = err.message;
				loading = false;
			});
	});

	function getBarWidth(value: number, max: number): string {
		if (max === 0) return '0%';
		return `${(value / max) * 100}%`;
	}
</script>

<div class="max-w-7xl mx-auto px-4 sm:px-6 py-8">
	<!-- Header -->
	<div class="flex items-center justify-between mb-8">
		<div class="flex items-center gap-3">
			<MandalaIcon size={40} color="var(--brand-navy)" />
			<div>
				<h1 class="text-3xl font-bold text-brand-charcoal">Admin Dashboard</h1>
				<p class="text-brand-charcoal/60">Overview of all lending operations</p>
			</div>
		</div>
		<div class="flex items-center gap-3">
			<a
				href="/admin/loans"
				class="px-4 py-2 bg-brand-navy text-white rounded-xl text-sm font-medium hover:bg-brand-navy-light transition-colors"
			>
				View All Loans
			</a>
			<a
				href="/admin/users"
				class="px-4 py-2 bg-white text-brand-charcoal border border-brand-border rounded-xl text-sm font-medium hover:bg-brand-warm-gray transition-colors"
			>
				Manage Users
			</a>
		</div>
	</div>

	{#if loading}
		<div class="flex justify-center py-20"><Spinner /></div>
	{:else if error}
		<div class="bg-brand-danger/10 text-brand-danger p-4 rounded-xl text-sm" role="alert">{error}</div>
	{:else if stats}
		<!-- Primary Stats -->
		<div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
			<Card class="p-6 relative overflow-hidden">
				<div class="absolute top-0 right-0 w-20 h-20 bg-brand-navy/5 rounded-bl-full"></div>
				<p class="text-xs text-brand-charcoal/50 uppercase tracking-wider font-medium mb-2">Total Applications</p>
				<p class="text-4xl font-bold text-brand-navy font-mono">{stats.total_applications}</p>
				<p class="text-xs text-brand-charcoal/40 mt-2">
					{stats.approval_rate}% approval rate
				</p>
			</Card>

			<Card class="p-6 relative overflow-hidden">
				<div class="absolute top-0 right-0 w-20 h-20 bg-brand-forest/5 rounded-bl-full"></div>
				<p class="text-xs text-brand-charcoal/50 uppercase tracking-wider font-medium mb-2">Approved</p>
				<p class="text-4xl font-bold text-brand-forest font-mono">{stats.approved}</p>
				<p class="text-xs text-brand-charcoal/40 mt-2">
					NPR {formatAmount(stats.total_approved_amount)} total
				</p>
			</Card>

			<Card class="p-6 relative overflow-hidden">
				<div class="absolute top-0 right-0 w-20 h-20 bg-brand-burgundy/5 rounded-bl-full"></div>
				<p class="text-xs text-brand-charcoal/50 uppercase tracking-wider font-medium mb-2">Rejected</p>
				<p class="text-4xl font-bold text-brand-burgundy font-mono">{stats.rejected}</p>
				<p class="text-xs text-brand-charcoal/40 mt-2">
					{stats.flagged} flagged for review
				</p>
			</Card>

			<Card class="p-6 relative overflow-hidden">
				<div class="absolute top-0 right-0 w-20 h-20 bg-brand-gold/5 rounded-bl-full"></div>
				<p class="text-xs text-brand-charcoal/50 uppercase tracking-wider font-medium mb-2">Pending</p>
				<p class="text-4xl font-bold text-brand-gold font-mono">{stats.pending}</p>
				<p class="text-xs text-brand-charcoal/40 mt-2">
					Awaiting decision
				</p>
			</Card>
		</div>

		<!-- Secondary Stats Row -->
		<div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
			<div class="bg-white rounded-xl p-4 border border-brand-border">
				<p class="text-xs text-brand-charcoal/50 uppercase tracking-wider mb-1">Total Requested</p>
				<p class="text-lg font-bold text-brand-navy font-mono">NPR {formatAmount(stats.total_requested_amount)}</p>
			</div>
			<div class="bg-white rounded-xl p-4 border border-brand-border">
				<p class="text-xs text-brand-charcoal/50 uppercase tracking-wider mb-1">Avg Credit Score</p>
				<p class="text-lg font-bold font-mono {getScoreColor(stats.average_credit_score)}">{stats.average_credit_score}</p>
			</div>
			<div class="bg-white rounded-xl p-4 border border-brand-border">
				<p class="text-xs text-brand-charcoal/50 uppercase tracking-wider mb-1">Modified</p>
				<p class="text-lg font-bold text-brand-gold font-mono">{stats.modified}</p>
			</div>
			<div class="bg-white rounded-xl p-4 border border-brand-border">
				<p class="text-xs text-brand-charcoal/50 uppercase tracking-wider mb-1">Manual Review</p>
				<p class="text-lg font-bold text-brand-charcoal font-mono">{stats.manual_review}</p>
			</div>
		</div>

		<!-- Two Column Layout -->
		<div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
			<!-- Decision Distribution -->
			<Card class="p-6 lg:col-span-1">
				<h2 class="text-sm font-semibold text-brand-charcoal/50 uppercase tracking-wider mb-5 flex items-center gap-2">
					<span class="w-2 h-2 bg-brand-navy rounded-full"></span>
					Decision Distribution
				</h2>

				<div class="space-y-4">
					{#each Object.entries(stats.decision_distribution) as [decision, count]}
						{@const maxVal = Math.max(...Object.values(stats.decision_distribution))}
						<div>
							<div class="flex items-center justify-between mb-1.5">
								<div class="flex items-center gap-2">
									<Badge variant={getDecisionBadgeVariant(decision)} size="xs">
										{decision}
									</Badge>
								</div>
								<span class="text-sm font-mono font-semibold text-brand-charcoal">{count}</span>
							</div>
							<div class="h-2 bg-brand-warm-gray rounded-full overflow-hidden">
								<div
									class="h-full rounded-full transition-all duration-700 ease-out
										{decision === 'APPROVE' ? 'bg-brand-forest' :
										  decision === 'REJECT' ? 'bg-brand-burgundy' :
										  decision === 'MODIFY' ? 'bg-brand-gold' :
										  decision === 'MANUAL_REVIEW' ? 'bg-brand-charcoal' :
										  'bg-brand-navy'}"
									style="width: {getBarWidth(count, maxVal)}"
								></div>
							</div>
						</div>
					{/each}
				</div>

				<!-- Summary -->
				<div class="mt-6 pt-4 border-t border-brand-border">
					<div class="flex items-center justify-between text-sm">
						<span class="text-brand-charcoal/50">Total Processed</span>
						<span class="font-mono font-semibold text-brand-navy">{stats.total_applications}</span>
					</div>
				</div>
			</Card>

			<!-- Recent Activity -->
			<div class="lg:col-span-2">
				<div class="flex items-center justify-between mb-4">
					<h2 class="text-sm font-semibold text-brand-charcoal/50 uppercase tracking-wider flex items-center gap-2">
						<span class="w-2 h-2 bg-brand-gold rounded-full"></span>
						Recent Activity
					</h2>
					<a href="/admin/loans" class="text-brand-navy hover:text-brand-navy-light text-sm font-medium transition-colors">
						View All →
					</a>
				</div>

				<Card class="overflow-hidden">
					<div class="divide-y divide-brand-border">
						{#each stats.recent_activity as app, i}
							<a
								href="/admin/{app.application_id}"
								class="flex items-center justify-between px-5 py-4 hover:bg-brand-warm-gray/50 transition-colors"
							>
								<div class="flex items-center gap-4 min-w-0">
									<div class="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0
										{app.final_decision === 'APPROVE' ? 'bg-brand-forest/10' :
										  app.final_decision === 'REJECT' ? 'bg-brand-burgundy/10' :
										  app.final_decision === 'MODIFY' ? 'bg-brand-gold/10' :
										  'bg-brand-navy/10'}">
										<span class="text-lg">
											{app.final_decision === 'APPROVE' ? '✓' :
											  app.final_decision === 'REJECT' ? '✕' :
											  app.final_decision === 'MODIFY' ? '⚠' : '○'}
										</span>
									</div>
									<div class="min-w-0">
										<p class="text-sm font-medium text-brand-charcoal truncate font-mono">
											{app.application_id}
										</p>
										<p class="text-xs text-brand-charcoal/40 truncate">
											{app.loan_purpose?.replace('_', ' ') || 'N/A'} · NPR {formatAmount(app.requested_amount_nrs)}
										</p>
									</div>
								</div>
								<div class="flex items-center gap-3 flex-shrink-0 ml-4">
									<div class="text-right hidden sm:block">
										<p class="text-xs font-mono {getScoreColor(app.credit_score)}">{app.credit_score ?? '—'}</p>
										<p class="text-[10px] text-brand-charcoal/30">{app.application_date_ad ? formatDate(app.application_date_ad) : ''}</p>
									</div>
									<Badge variant={getDecisionBadgeVariant(app.final_decision)} size="xs">
										{app.final_decision || 'PENDING'}
									</Badge>
								</div>
							</a>
						{:else}
							<div class="px-5 py-10 text-center text-sm text-brand-charcoal/40">
								No recent activity
							</div>
						{/each}
					</div>
				</Card>
			</div>
		</div>

		<!-- Quick Actions -->
		<div class="mt-8">
			<h2 class="text-sm font-semibold text-brand-charcoal/50 uppercase tracking-wider mb-4 flex items-center gap-2">
				<span class="w-2 h-2 bg-brand-forest rounded-full"></span>
				Quick Actions
			</h2>
			<div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
				<a
					href="/admin/loans?status=pending"
					class="bg-white rounded-xl p-4 border border-brand-border hover:border-brand-gold/30 hover:shadow-sm transition-all group"
				>
					<div class="w-10 h-10 bg-brand-gold/10 rounded-xl flex items-center justify-center mb-3 group-hover:scale-105 transition-transform">
						<svg class="w-5 h-5 text-brand-gold" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
						</svg>
					</div>
					<p class="text-sm font-medium text-brand-charcoal">Review Pending</p>
					<p class="text-xs text-brand-charcoal/40 mt-0.5">{stats.pending} applications</p>
				</a>

				<a
					href="/admin/loans?status=flag"
					class="bg-white rounded-xl p-4 border border-brand-border hover:border-brand-burgundy/30 hover:shadow-sm transition-all group"
				>
					<div class="w-10 h-10 bg-brand-burgundy/10 rounded-xl flex items-center justify-center mb-3 group-hover:scale-105 transition-transform">
						<svg class="w-5 h-5 text-brand-burgundy" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 21v-4m0 0V5a2 2 0 012-2h6.5l1 1H21l-3 6 3 6h-8.5l-1-1H5a2 2 0 00-2 2zm9-13.5V9" />
						</svg>
					</div>
					<p class="text-sm font-medium text-brand-charcoal">Compliance Flags</p>
					<p class="text-xs text-brand-charcoal/40 mt-0.5">{stats.flagged} flagged</p>
				</a>

				<a
					href="/admin/loans?export=true"
					class="bg-white rounded-xl p-4 border border-brand-border hover:border-brand-navy/30 hover:shadow-sm transition-all group"
				>
					<div class="w-10 h-10 bg-brand-navy/10 rounded-xl flex items-center justify-center mb-3 group-hover:scale-105 transition-transform">
						<svg class="w-5 h-5 text-brand-navy" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
						</svg>
					</div>
					<p class="text-sm font-medium text-brand-charcoal">Export Data</p>
					<p class="text-xs text-brand-charcoal/40 mt-0.5">Download CSV</p>
				</a>

				<a
					href="/admin/users"
					class="bg-white rounded-xl p-4 border border-brand-border hover:border-brand-forest/30 hover:shadow-sm transition-all group"
				>
					<div class="w-10 h-10 bg-brand-forest/10 rounded-xl flex items-center justify-center mb-3 group-hover:scale-105 transition-transform">
						<svg class="w-5 h-5 text-brand-forest" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
						</svg>
					</div>
					<p class="text-sm font-medium text-brand-charcoal">Manage Users</p>
					<p class="text-xs text-brand-charcoal/40 mt-0.5">User management</p>
				</a>
			</div>
		</div>
	{/if}
</div>
