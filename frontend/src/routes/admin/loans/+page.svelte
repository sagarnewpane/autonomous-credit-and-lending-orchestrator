<script lang="ts">
	import { page } from '$app/stores';
	import { getAllLoans, bulkUpdateLoans, getExportUrl } from '$lib/services/loans';
	import type { AdminLoanRecord } from '$lib/types/api';
	import Card from '$lib/components/ui/Card.svelte';
	import Badge from '$lib/components/ui/Badge.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import Spinner from '$lib/components/ui/Spinner.svelte';
	import Modal from '$lib/components/ui/Modal.svelte';
	import MandalaIcon from '$lib/components/ui/MandalaIcon.svelte';
	import { getDecisionBadgeVariant, getScoreColor } from '$lib/utils/decisions';
	import { formatAmount, formatDate } from '$lib/utils/format';

	let applications = $state<AdminLoanRecord[]>([]);
	let loading = $state(true);
	let error = $state('');
	let filter = $state('all');
	let searchQuery = $state('');
	let selectedIds = $state<Set<string>>(new Set());
	let showBulkModal = $state(false);
	let bulkDecision = $state('');
	let bulkNotes = $state('');
	let bulkSubmitting = $state(false);
	let bulkMessage = $state('');
	let sortField = $state<'application_date_ad' | 'requested_amount_nrs' | 'credit_score'>('application_date_ad');
	let sortDesc = $state(true);

	// Read initial filter from URL
	$effect(() => {
		const urlFilter = $page.url.searchParams.get('status');
		if (urlFilter) filter = urlFilter;
		const exportParam = $page.url.searchParams.get('export');
		if (exportParam === 'true') {
			downloadExport();
		}
	});

	let filtered = $derived(
		applications
			.filter((a) => {
				const matchesFilter = filter === 'all' ||
					(filter === 'approved' && a.final_decision === 'APPROVE') ||
					(filter === 'rejected' && a.final_decision === 'REJECT') ||
					(filter === 'pending' && (!a.final_decision || a.final_decision === 'PENDING')) ||
					(filter === 'flagged' && a.compliance_status === 'flag') ||
					(filter === 'modified' && a.final_decision === 'MODIFY') ||
					(filter === 'manual' && a.final_decision === 'MANUAL_REVIEW');

				const matchesSearch = !searchQuery ||
					a.application_id?.toLowerCase().includes(searchQuery.toLowerCase()) ||
					a.applicant_id?.toLowerCase().includes(searchQuery.toLowerCase()) ||
					(a as unknown as Record<string, unknown>)['citizenship_extracted_name']?.toString().toLowerCase().includes(searchQuery.toLowerCase());

				return matchesFilter && matchesSearch;
			})
			.sort((a, b) => {
				const aVal = a[sortField] ?? 0;
				const bVal = b[sortField] ?? 0;
				if (sortDesc) return aVal > bVal ? -1 : 1;
				return aVal < bVal ? -1 : 1;
			})
	);

	let metrics = $derived({
		total: applications.length,
		pending: applications.filter(a => !a.final_decision || a.final_decision === 'PENDING').length,
		approved: applications.filter(a => a.final_decision === 'APPROVE').length,
		rejected: applications.filter(a => a.final_decision === 'REJECT').length,
		flagged: applications.filter(a => a.compliance_status === 'flag').length,
		modified: applications.filter(a => a.final_decision === 'MODIFY').length,
		manual: applications.filter(a => a.final_decision === 'MANUAL_REVIEW').length
	});

	let allSelected = $derived(
		filtered.length > 0 && filtered.every(a => selectedIds.has(a.application_id))
	);

	function toggleSelectAll() {
		if (allSelected) {
			selectedIds = new Set();
		} else {
			selectedIds = new Set(filtered.map(a => a.application_id));
		}
	}

	function toggleSelect(id: string) {
		const next = new Set(selectedIds);
		if (next.has(id)) {
			next.delete(id);
		} else {
			next.add(id);
		}
		selectedIds = next;
	}

	function handleSort(field: typeof sortField) {
		if (sortField === field) {
			sortDesc = !sortDesc;
		} else {
			sortField = field;
			sortDesc = true;
		}
	}

	function downloadExport() {
		const url = getExportUrl(filter === 'all' ? undefined : filter);
		window.open(url, '_blank');
	}

	async function handleBulkUpdate(e: Event) {
		e.preventDefault();
		if (!bulkDecision) {
			bulkMessage = 'Please select a decision';
			return;
		}
		if (!bulkNotes.trim()) {
			bulkMessage = 'Notes are required';
			return;
		}

		bulkSubmitting = true;
		bulkMessage = '';
		try {
			const updates: Record<string, unknown> = {
				final_decision: bulkDecision,
				officer_notes: bulkNotes
			};
			await bulkUpdateLoans({
				application_ids: Array.from(selectedIds),
				updates
			});
			bulkMessage = `Successfully updated ${selectedIds.size} applications`;
			showBulkModal = false;
			selectedIds = new Set();
			bulkDecision = '';
			bulkNotes = '';
			// Refresh data
			loading = true;
			const res = await getAllLoans();
			applications = res.applications;
			loading = false;
		} catch (err: unknown) {
			bulkMessage = err instanceof Error ? err.message : 'Failed to update';
		} finally {
			bulkSubmitting = false;
		}
	}

	$effect(() => {
		getAllLoans()
			.then((res) => {
				applications = res.applications;
				loading = false;
			})
			.catch((err) => {
				error = err.message;
				loading = false;
			});
	});
</script>

<div class="min-h-screen bg-brand-cream">
	<!-- Header -->
	<header class="bg-white border-b border-brand-border sticky top-0 z-40">
		<div class="max-w-7xl mx-auto px-4 sm:px-6 py-4">
			<div class="flex items-center justify-between">
				<div class="flex items-center gap-3">
					<MandalaIcon size={36} color="var(--brand-navy)" />
					<div>
						<h1 class="text-xl text-brand-charcoal font-display">Loan Applications</h1>
						<p class="text-xs text-brand-charcoal/50">Admin Dashboard</p>
					</div>
				</div>
				<div class="flex items-center gap-3">
					<!-- Search -->
					<div class="relative hidden sm:block">
						<svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-brand-charcoal/30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
						</svg>
						<input
							type="text"
							bind:value={searchQuery}
							placeholder="Search by ID or name..."
							class="pl-10 pr-4 py-2 rounded-xl border border-brand-border text-sm focus:outline-none focus:ring-2 focus:ring-brand-gold/30 focus:border-brand-gold w-64"
						/>
					</div>
					<button
						onclick={downloadExport}
						class="px-3 py-2 bg-white border border-brand-border rounded-xl text-sm font-medium text-brand-charcoal hover:bg-brand-warm-gray transition-colors flex items-center gap-2"
					>
						<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
						</svg>
						Export
					</button>
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
			<!-- Metrics Row -->
			<div class="grid grid-cols-3 sm:grid-cols-7 gap-3 mb-6">
				{#each [
					{ value: 'all', label: 'All', count: metrics.total, color: 'text-brand-navy', bg: 'bg-brand-navy/5' },
					{ value: 'pending', label: 'Pending', count: metrics.pending, color: 'text-brand-gold', bg: 'bg-brand-gold/5' },
					{ value: 'approved', label: 'Approved', count: metrics.approved, color: 'text-brand-forest', bg: 'bg-brand-forest/5' },
					{ value: 'rejected', label: 'Rejected', count: metrics.rejected, color: 'text-brand-burgundy', bg: 'bg-brand-burgundy/5' },
					{ value: 'flagged', label: 'Flagged', count: metrics.flagged, color: 'text-brand-burgundy', bg: 'bg-brand-burgundy/5' },
					{ value: 'modified', label: 'Modified', count: metrics.modified, color: 'text-brand-gold', bg: 'bg-brand-gold/5' },
					{ value: 'manual', label: 'Manual', count: metrics.manual, color: 'text-brand-charcoal', bg: 'bg-brand-charcoal/5' }
				] as f}
					<button
						onclick={() => (filter = f.value)}
						class="{f.bg} rounded-xl p-3 border border-brand-border/50 text-left transition-all hover:shadow-sm
							{filter === f.value ? 'ring-2 ring-brand-navy/20' : ''}"
					>
						<p class="text-[10px] font-medium text-brand-charcoal/50 uppercase tracking-wide">{f.label}</p>
						<p class="text-xl font-bold {f.color} font-mono mt-0.5">{f.count}</p>
					</button>
				{/each}
			</div>

			<!-- Mobile Search -->
			<div class="sm:hidden mb-4">
				<div class="relative">
					<svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-brand-charcoal/30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
					</svg>
					<input
						type="text"
						bind:value={searchQuery}
						placeholder="Search by ID or name..."
						class="w-full pl-10 pr-4 py-3 rounded-xl border border-brand-border text-sm focus:outline-none focus:ring-2 focus:ring-brand-gold/30 focus:border-brand-gold"
					/>
				</div>
			</div>

			<!-- Bulk Actions Bar -->
			{#if selectedIds.size > 0}
				<div class="bg-brand-navy/5 border border-brand-navy/20 rounded-xl p-3 mb-4 flex items-center justify-between animate-fade-in">
					<div class="flex items-center gap-3">
						<span class="w-8 h-8 bg-brand-navy text-white rounded-lg flex items-center justify-center text-sm font-bold">
							{selectedIds.size}
						</span>
						<span class="text-sm font-medium text-brand-navy">
							{selectedIds.size} application{selectedIds.size > 1 ? 's' : ''} selected
						</span>
					</div>
					<div class="flex items-center gap-2">
						<button
							onclick={() => { selectedIds = new Set(); }}
							class="px-3 py-1.5 text-sm text-brand-charcoal/60 hover:text-brand-charcoal transition-colors"
						>
							Clear
						</button>
						<button
							onclick={() => { showBulkModal = true; bulkMessage = ''; }}
							class="px-4 py-1.5 bg-brand-navy text-white rounded-lg text-sm font-medium hover:bg-brand-navy-light transition-colors"
						>
							Bulk Update
						</button>
					</div>
				</div>
			{/if}

			<!-- Data Table -->
			<Card variant="elevated" class="overflow-hidden">
				<div class="overflow-x-auto">
					<table class="w-full">
						<thead>
							<tr class="bg-brand-warm-gray border-b border-brand-border">
								<th class="px-4 py-3 w-10">
									<input
										type="checkbox"
										checked={allSelected}
										onchange={toggleSelectAll}
										class="w-4 h-4 rounded border-brand-border text-brand-navy focus:ring-brand-gold/30"
									/>
								</th>
								<th class="px-4 sm:px-5 py-3 text-left text-xs font-semibold text-brand-charcoal/50 uppercase tracking-wider cursor-pointer hover:text-brand-charcoal" onclick={() => handleSort('application_date_ad')}>
									<div class="flex items-center gap-1">
										Date
										{#if sortField === 'application_date_ad'}
											<svg class="w-3 h-3 {sortDesc ? '' : 'rotate-180'}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
												<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7" />
											</svg>
										{/if}
									</div>
								</th>
								<th class="px-4 sm:px-5 py-3 text-left text-xs font-semibold text-brand-charcoal/50 uppercase tracking-wider hidden sm:table-cell">App ID</th>
								<th class="px-4 sm:px-5 py-3 text-left text-xs font-semibold text-brand-charcoal/50 uppercase tracking-wider">Amount</th>
								<th class="px-4 sm:px-5 py-3 text-left text-xs font-semibold text-brand-charcoal/50 uppercase tracking-wider hidden md:table-cell">Purpose</th>
								<th class="px-4 sm:px-5 py-3 text-left text-xs font-semibold text-brand-charcoal/50 uppercase tracking-wider hidden md:table-cell cursor-pointer hover:text-brand-charcoal" onclick={() => handleSort('credit_score')}>
									<div class="flex items-center gap-1">
										Score
										{#if sortField === 'credit_score'}
											<svg class="w-3 h-3 {sortDesc ? '' : 'rotate-180'}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
												<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7" />
											</svg>
										{/if}
									</div>
								</th>
								<th class="px-4 sm:px-5 py-3 text-left text-xs font-semibold text-brand-charcoal/50 uppercase tracking-wider hidden lg:table-cell">Risk</th>
								<th class="px-4 sm:px-5 py-3 text-left text-xs font-semibold text-brand-charcoal/50 uppercase tracking-wider">Decision</th>
								<th class="px-4 sm:px-5 py-3 text-left text-xs font-semibold text-brand-charcoal/50 uppercase tracking-wider hidden lg:table-cell">Compliance</th>
								<th class="px-4 sm:px-5 py-3"></th>
							</tr>
						</thead>
						<tbody class="divide-y divide-brand-border">
							{#each filtered as app, i}
								<tr class="hover:bg-brand-warm-gray/50 transition-colors duration-150 {selectedIds.has(app.application_id) ? 'bg-brand-navy/3' : ''}" style="animation-delay: {i * 20}ms">
									<td class="px-4 py-4">
										<input
											type="checkbox"
											checked={selectedIds.has(app.application_id)}
											onchange={() => toggleSelect(app.application_id)}
											class="w-4 h-4 rounded border-brand-border text-brand-navy focus:ring-brand-gold/30"
										/>
									</td>
									<td class="px-4 sm:px-5 py-4">
										<p class="text-xs text-brand-charcoal/50">{app.application_date_ad ? formatDate(app.application_date_ad) : '—'}</p>
									</td>
									<td class="px-4 sm:px-5 py-4 hidden sm:table-cell">
										<p class="font-mono text-sm font-medium text-brand-navy">{app.application_id}</p>
									</td>
									<td class="px-4 sm:px-5 py-4">
										<p class="font-mono text-sm font-medium text-brand-charcoal">NPR {formatAmount(app.requested_amount_nrs)}</p>
									</td>
									<td class="px-4 sm:px-5 py-4 hidden md:table-cell">
										<p class="text-sm text-brand-charcoal/70 capitalize">{app.loan_purpose?.replace('_', ' ') || '—'}</p>
									</td>
									<td class="px-4 sm:px-5 py-4 hidden md:table-cell">
										<span class="font-mono text-lg font-bold {getScoreColor(app.credit_score)}">
											{app.credit_score ?? '—'}
										</span>
									</td>
									<td class="px-4 sm:px-5 py-4 hidden lg:table-cell">
										<span class="text-sm text-brand-charcoal/70">{app.risk_tier ?? '—'}</span>
									</td>
									<td class="px-4 sm:px-5 py-4">
										<Badge variant={getDecisionBadgeVariant(app.final_decision)}>
											{app.final_decision || 'PENDING'}
										</Badge>
									</td>
									<td class="px-4 sm:px-5 py-4 hidden lg:table-cell">
										{#if app.compliance_status === 'flag'}
											<span class="px-2 py-1 rounded text-xs font-medium bg-brand-burgundy/10 text-brand-burgundy">Flagged</span>
										{:else if app.compliance_status === 'pass'}
											<span class="px-2 py-1 rounded text-xs font-medium bg-brand-forest/10 text-brand-forest">Pass</span>
										{:else}
											<span class="text-xs text-brand-charcoal/40">—</span>
										{/if}
									</td>
									<td class="px-4 sm:px-5 py-4">
										<a
											href="/admin/{app.application_id}"
											class="inline-flex items-center gap-1 text-sm font-medium text-brand-navy hover:text-brand-navy-light transition-colors"
										>
											Review
											<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
												<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
											</svg>
										</a>
									</td>
								</tr>
							{:else}
								<tr>
									<td colspan="10" class="px-6 py-12 text-center">
										<p class="text-brand-charcoal/40 text-sm">No applications found</p>
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>

				<!-- Footer -->
				<div class="px-4 sm:px-6 py-3 bg-brand-warm-gray/50 border-t border-brand-border flex items-center justify-between">
					<p class="text-xs text-brand-charcoal/40">
						Showing {filtered.length} of {applications.length} applications
					</p>
					{#if selectedIds.size > 0}
						<p class="text-xs text-brand-navy font-medium">
							{selectedIds.size} selected
						</p>
					{/if}
				</div>
			</Card>
		{/if}
	</main>
</div>

<!-- Bulk Update Modal -->
<Modal bind:open={showBulkModal} title="Bulk Update Applications" size="md">
	<form onsubmit={handleBulkUpdate} class="space-y-4">
		<p class="text-sm text-brand-charcoal/60">
			This will update {selectedIds.size} application{selectedIds.size > 1 ? 's' : ''} with the same decision and notes.
		</p>

		<div>
			<label for="bulk-decision" class="block text-sm font-medium text-brand-charcoal mb-1.5">
				Decision <span class="text-brand-burgundy">*</span>
			</label>
			<select
				id="bulk-decision"
				bind:value={bulkDecision}
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
			<label for="bulk-notes" class="block text-sm font-medium text-brand-charcoal mb-1.5">
				Officer Notes <span class="text-brand-burgundy">*</span>
			</label>
			<textarea
				id="bulk-notes"
				bind:value={bulkNotes}
				rows="3"
				placeholder="Explain the reason for this bulk update..."
				required
				class="w-full px-4 py-3 rounded-xl border border-brand-border text-sm focus:outline-none focus:ring-2 focus:ring-brand-gold/30 focus:border-brand-gold resize-none"
			></textarea>
		</div>

		{#if bulkMessage}
			<div class="p-3 rounded-xl text-sm {bulkMessage.includes('success') ? 'bg-brand-forest/10 text-brand-forest' : 'bg-brand-burgundy/10 text-brand-burgundy'}">
				{bulkMessage}
			</div>
		{/if}

		<div class="flex gap-3 pt-2">
			<Button variant="secondary" onclick={() => (showBulkModal = false)} class="flex-1">Cancel</Button>
			<Button type="submit" variant="primary" loading={bulkSubmitting} class="flex-1">Update {selectedIds.size} Applications</Button>
		</div>
	</form>
</Modal>
