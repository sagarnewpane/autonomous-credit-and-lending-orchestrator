<script lang="ts">
	import { page } from '$app/stores';
	import { getAuditTrail } from '$lib/services/loans';
	import type { AuditLog } from '$lib/types/api';
	import Card from '$lib/components/ui/Card.svelte';
	import Spinner from '$lib/components/ui/Spinner.svelte';
	import MandalaIcon from '$lib/components/ui/MandalaIcon.svelte';
	import { formatTimestamp, formatDate, formatJson } from '$lib/utils/format';

	const applicationId = $derived($page.params.id);

	let auditLogs = $state<AuditLog[]>([]);
	let loading = $state(true);
	let error = $state('');
	let expandedRows = $state<Set<number>>(new Set());

	function toggleRow(id: number) {
		if (expandedRows.has(id)) {
			expandedRows.delete(id);
		} else {
			expandedRows.add(id);
		}
		expandedRows = new Set(expandedRows);
	}

	function getAgentColor(agent: string): string {
		if (agent.includes('Document')) return 'bg-brand-navy';
		if (agent.includes('Income')) return 'bg-brand-gold';
		if (agent.includes('Credit')) return 'bg-brand-forest';
		if (agent.includes('Compliance')) return 'bg-brand-burgundy';
		if (agent.includes('Decision')) return 'bg-brand-charcoal';
		return 'bg-brand-charcoal';
	}

	function getStatusColor(status: string): string {
		if (status === 'success' || status === 'pass') return 'text-brand-forest';
		if (status === 'warning' || status === 'flag') return 'text-brand-gold';
		if (status === 'error' || status === 'fail') return 'text-brand-burgundy';
		return 'text-brand-charcoal/60';
	}

	$effect(() => {
		if (applicationId) {
			getAuditTrail(applicationId)
				.then((res) => {
					auditLogs = res.audit_logs ?? [];
					loading = false;
				})
				.catch((err) => {
					error = err.message ?? 'Failed to load audit trail';
					loading = false;
				});
		}
	});
</script>

<div class="min-h-screen bg-brand-cream">
	<!-- Header -->
	<header class="bg-white border-b border-brand-border sticky top-0 z-40">
		<div class="max-w-6xl mx-auto px-4 sm:px-6 py-4">
			<div class="flex items-center justify-between">
				<div class="flex items-center gap-4">
				<a href="/admin/{applicationId}" class="text-brand-charcoal/40 hover:text-brand-charcoal transition-colors" aria-label="Back to application details">
					<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
					</svg>
				</a>
					<div class="flex items-center gap-3">
						<MandalaIcon size={32} color="var(--brand-navy)" />
						<div>
							<h1 class="text-lg text-brand-charcoal font-display">Audit Log</h1>
							<p class="text-xs text-brand-charcoal/50 font-mono">{applicationId}</p>
						</div>
					</div>
				</div>
				<div class="flex items-center gap-2">
					<span class="w-2 h-2 bg-brand-forest rounded-full animate-pulse"></span>
					<span class="text-xs text-brand-charcoal/50">Immutable Record</span>
					<svg class="w-4 h-4 text-brand-charcoal/30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
					</svg>
				</div>
			</div>
		</div>
	</header>

	<main class="max-w-6xl mx-auto px-4 sm:px-6 py-6">
		{#if loading}
			<div class="flex justify-center py-16"><Spinner /></div>
		{:else if error}
			<div class="bg-brand-burgundy/10 text-brand-burgundy p-4 rounded-xl text-sm" role="alert">{error}</div>
		{:else}
			<!-- Audit Trail -->
			<Card variant="elevated" class="overflow-hidden">
				<!-- Table Header -->
				<div class="px-6 py-4 bg-brand-warm-gray border-b border-brand-border overflow-x-auto">
					<div class="grid grid-cols-6 sm:grid-cols-12 gap-4 text-xs font-semibold text-brand-charcoal/50 uppercase tracking-wider min-w-[500px]">
						<div class="col-span-2 sm:col-span-2">Time</div>
						<div class="col-span-2 sm:col-span-2">Agent</div>
						<div class="col-span-2 sm:col-span-3">Action</div>
						<div class="col-span-0 sm:col-span-2 hidden sm:block">Status</div>
						<div class="col-span-0 sm:col-span-3 hidden sm:block">Output</div>
					</div>
				</div>

				<!-- Table Body -->
				<div class="divide-y divide-brand-border">
					{#each auditLogs as log}
						<div class="hover:bg-brand-warm-gray/30 transition-colors duration-150">
							<!-- Row -->
							<button
								onclick={() => toggleRow(log.id)}
								class="w-full px-6 py-4 text-left"
							>
								<div class="grid grid-cols-6 sm:grid-cols-12 gap-4 items-center min-w-[500px]">
									<!-- Timestamp -->
									<div class="col-span-2">
										<p class="font-mono text-xs text-brand-charcoal/60">{formatTimestamp(log.timestamp)}</p>
										<p class="text-[10px] text-brand-charcoal/30">{formatDate(log.timestamp)}</p>
									</div>

									<!-- Agent -->
									<div class="col-span-2">
										<div class="flex items-center gap-2">
											<span class="w-2 h-2 rounded-full {getAgentColor(log.agent)}"></span>
											<span class="text-sm font-medium text-brand-charcoal">{log.agent}</span>
										</div>
									</div>

									<!-- Action -->
									<div class="col-span-2 sm:col-span-3">
										<span class="text-sm text-brand-charcoal/70">{log.action}</span>
									</div>

									<!-- Status -->
									<div class="hidden sm:block sm:col-span-2">
										<span class="text-sm font-medium {getStatusColor(log.output.status as string)}">
											{(log.output.status as string)?.toUpperCase() ?? 'UNKNOWN'}
										</span>
									</div>

									<!-- Expand indicator -->
									<div class="col-span-2 sm:col-span-3 flex items-center justify-end gap-2">
										<span class="text-xs text-brand-charcoal/30">
											{expandedRows.has(log.id) ? 'Collapse' : 'Expand'}
										</span>
										<svg
											class="w-4 h-4 text-brand-charcoal/30 transition-transform duration-200 {expandedRows.has(log.id) ? 'rotate-180' : ''}"
											fill="none"
											stroke="currentColor"
											viewBox="0 0 24 24"
										>
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
										</svg>
									</div>
								</div>
							</button>

							<!-- Expanded JSON View -->
							{#if expandedRows.has(log.id)}
								<div class="px-6 pb-4 animate-fade-in">
									<div class="bg-brand-charcoal rounded-xl p-4 overflow-x-auto">
										<div class="flex items-center justify-between mb-2">
											<span class="text-xs text-white/40 font-mono">agent_output</span>
											<span class="flex items-center gap-1.5 text-[10px] text-white/30">
												<svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
													<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
												</svg>
												Immutable
											</span>
										</div>
										<pre class="text-sm text-green-400 font-mono whitespace-pre-wrap leading-relaxed">{formatJson(log.output)}</pre>
									</div>
								</div>
							{/if}
						</div>
					{/each}
				</div>

				<!-- Footer -->
				<div class="px-6 py-3 bg-brand-warm-gray/50 border-t border-brand-border flex items-center justify-between">
					<p class="text-xs text-brand-charcoal/40">
						{auditLogs.length} audit entries
					</p>
					<div class="flex items-center gap-2 text-xs text-brand-charcoal/40">
						<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
						</svg>
						Tamper-proof audit trail
					</div>
				</div>
			</Card>
		{/if}
	</main>
</div>
