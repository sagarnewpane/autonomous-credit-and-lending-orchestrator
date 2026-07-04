<script lang="ts">
	import { getAllUsers, updateUser, getUserDetail } from '$lib/services/loans';
	import type { AdminUser } from '$lib/types/api';
	import Card from '$lib/components/ui/Card.svelte';
	import Badge from '$lib/components/ui/Badge.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import Spinner from '$lib/components/ui/Spinner.svelte';
	import Modal from '$lib/components/ui/Modal.svelte';
	import MandalaIcon from '$lib/components/ui/MandalaIcon.svelte';
	import { formatDate } from '$lib/utils/format';

	let users = $state<AdminUser[]>([]);
	let loading = $state(true);
	let error = $state('');
	let searchQuery = $state('');
	let showDetailModal = $state(false);
	let selectedUser = $state<AdminUser | null>(null);
	let userLoans = $state<unknown[]>([]);
	let loadingDetail = $state(false);

	let filtered = $derived(
		users.filter((u) => {
			if (!searchQuery) return true;
			const q = searchQuery.toLowerCase();
			return u.email?.toLowerCase().includes(q) || u.id?.toLowerCase().includes(q);
		})
	);

	let metrics = $derived({
		total: users.length,
		admins: users.filter(u => u.is_admin).length,
		active: users.filter(u => u.is_active).length,
		inactive: users.filter(u => !u.is_active).length
	});

	$effect(() => {
		loadUsers();
	});

	async function loadUsers() {
		loading = true;
		try {
			const res = await getAllUsers();
			users = res.users;
		} catch (err: unknown) {
			error = err instanceof Error ? err.message : 'Failed to load users';
		} finally {
			loading = false;
		}
	}

	async function viewUser(user: AdminUser) {
		selectedUser = user;
		showDetailModal = true;
		loadingDetail = true;
		try {
			const res = await getUserDetail(user.id);
			userLoans = res.loan_applications;
		} catch {
			userLoans = [];
		} finally {
			loadingDetail = false;
		}
	}

	async function toggleAdmin(user: AdminUser) {
		try {
			await updateUser(user.id, { is_admin: !user.is_admin });
			await loadUsers();
		} catch (err: unknown) {
			error = err instanceof Error ? err.message : 'Failed to update user';
		}
	}

	async function toggleActive(user: AdminUser) {
		try {
			await updateUser(user.id, { is_active: !user.is_active });
			await loadUsers();
		} catch (err: unknown) {
			error = err instanceof Error ? err.message : 'Failed to update user';
		}
	}
</script>

<div class="min-h-screen bg-brand-cream">
	<!-- Header -->
	<header class="bg-white border-b border-brand-border sticky top-0 z-40">
		<div class="max-w-7xl mx-auto px-4 sm:px-6 py-4">
			<div class="flex items-center justify-between">
				<div class="flex items-center gap-3">
					<MandalaIcon size={36} color="var(--brand-navy)" />
					<div>
						<h1 class="text-xl text-brand-charcoal font-display">User Management</h1>
						<p class="text-xs text-brand-charcoal/50">Manage admin and regular users</p>
					</div>
				</div>
				<div class="flex items-center gap-3">
					<div class="relative hidden sm:block">
						<svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-brand-charcoal/30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
						</svg>
						<input
							type="text"
							bind:value={searchQuery}
							placeholder="Search by email or ID..."
							class="pl-10 pr-4 py-2 rounded-xl border border-brand-border text-sm focus:outline-none focus:ring-2 focus:ring-brand-gold/30 focus:border-brand-gold w-64"
						/>
					</div>
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
			<!-- Metrics -->
			<div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
				<div class="bg-brand-navy/5 rounded-xl p-4 border border-brand-border/50">
					<p class="text-xs font-medium text-brand-charcoal/50 uppercase tracking-wide">Total Users</p>
					<p class="text-2xl font-bold text-brand-navy font-mono mt-1">{metrics.total}</p>
				</div>
				<div class="bg-brand-forest/5 rounded-xl p-4 border border-brand-border/50">
					<p class="text-xs font-medium text-brand-charcoal/50 uppercase tracking-wide">Admins</p>
					<p class="text-2xl font-bold text-brand-forest font-mono mt-1">{metrics.admins}</p>
				</div>
				<div class="bg-brand-gold/5 rounded-xl p-4 border border-brand-border/50">
					<p class="text-xs font-medium text-brand-charcoal/50 uppercase tracking-wide">Active</p>
					<p class="text-2xl font-bold text-brand-gold font-mono mt-1">{metrics.active}</p>
				</div>
				<div class="bg-brand-burgundy/5 rounded-xl p-4 border border-brand-border/50">
					<p class="text-xs font-medium text-brand-charcoal/50 uppercase tracking-wide">Inactive</p>
					<p class="text-2xl font-bold text-brand-burgundy font-mono mt-1">{metrics.inactive}</p>
				</div>
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
						placeholder="Search by email or ID..."
						class="w-full pl-10 pr-4 py-3 rounded-xl border border-brand-border text-sm focus:outline-none focus:ring-2 focus:ring-brand-gold/30 focus:border-brand-gold"
					/>
				</div>
			</div>

			<!-- Users Table -->
			<Card variant="elevated" class="overflow-hidden">
				<div class="overflow-x-auto">
					<table class="w-full">
						<thead>
							<tr class="bg-brand-warm-gray border-b border-brand-border">
								<th class="px-4 sm:px-6 py-3 text-left text-xs font-semibold text-brand-charcoal/50 uppercase tracking-wider">User</th>
								<th class="px-4 sm:px-6 py-3 text-left text-xs font-semibold text-brand-charcoal/50 uppercase tracking-wider hidden sm:table-cell">ID</th>
								<th class="px-4 sm:px-6 py-3 text-left text-xs font-semibold text-brand-charcoal/50 uppercase tracking-wider">Role</th>
								<th class="px-4 sm:px-6 py-3 text-left text-xs font-semibold text-brand-charcoal/50 uppercase tracking-wider">Status</th>
								<th class="px-4 sm:px-6 py-3 text-left text-xs font-semibold text-brand-charcoal/50 uppercase tracking-wider hidden md:table-cell">Created</th>
								<th class="px-4 sm:px-6 py-3 text-right text-xs font-semibold text-brand-charcoal/50 uppercase tracking-wider">Actions</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-brand-border">
							{#each filtered as user}
								<tr class="hover:bg-brand-warm-gray/50 transition-colors duration-150">
									<td class="px-4 sm:px-6 py-4">
										<div class="flex items-center gap-3">
											<div class="w-9 h-9 rounded-xl bg-brand-navy/10 flex items-center justify-center flex-shrink-0">
												<span class="text-sm font-bold text-brand-navy">
													{user.email?.charAt(0).toUpperCase() || '?'}
												</span>
											</div>
											<div>
												<p class="text-sm font-medium text-brand-charcoal">{user.email}</p>
												<p class="text-xs text-brand-charcoal/40 sm:hidden font-mono">{user.id?.slice(0, 8)}...</p>
											</div>
										</div>
									</td>
									<td class="px-4 sm:px-6 py-4 hidden sm:table-cell">
										<p class="font-mono text-xs text-brand-charcoal/50">{user.id?.slice(0, 12)}...</p>
									</td>
									<td class="px-4 sm:px-6 py-4">
										{#if user.is_admin}
											<Badge variant="warning" size="sm">Admin</Badge>
										{:else}
											<Badge variant="default" size="sm">User</Badge>
										{/if}
									</td>
									<td class="px-4 sm:px-6 py-4">
										{#if user.is_active}
											<span class="flex items-center gap-1.5 text-sm text-brand-forest">
												<span class="w-2 h-2 bg-brand-forest rounded-full"></span>
												Active
											</span>
										{:else}
											<span class="flex items-center gap-1.5 text-sm text-brand-charcoal/40">
												<span class="w-2 h-2 bg-brand-charcoal/20 rounded-full"></span>
												Inactive
											</span>
										{/if}
									</td>
									<td class="px-4 sm:px-6 py-4 hidden md:table-cell">
										<p class="text-sm text-brand-charcoal/50">{user.created_at ? formatDate(user.created_at) : '—'}</p>
									</td>
									<td class="px-4 sm:px-6 py-4 text-right">
										<div class="flex items-center justify-end gap-2">
											<button
												onclick={() => viewUser(user)}
												class="px-3 py-1.5 text-xs font-medium text-brand-navy hover:text-brand-navy-light bg-brand-navy/5 hover:bg-brand-navy/10 rounded-lg transition-colors"
											>
												View
											</button>
											<button
												onclick={() => toggleAdmin(user)}
												class="px-3 py-1.5 text-xs font-medium {user.is_admin ? 'text-brand-burgundy hover:text-brand-burgundy-light bg-brand-burgundy/5 hover:bg-brand-burgundy/10' : 'text-brand-forest hover:text-brand-forest-light bg-brand-forest/5 hover:bg-brand-forest/10'} rounded-lg transition-colors"
											>
												{user.is_admin ? 'Revoke Admin' : 'Make Admin'}
											</button>
											<button
												onclick={() => toggleActive(user)}
												class="px-3 py-1.5 text-xs font-medium {user.is_active ? 'text-brand-burgundy hover:text-brand-burgundy-light bg-brand-burgundy/5 hover:bg-brand-burgundy/10' : 'text-brand-forest hover:text-brand-forest-light bg-brand-forest/5 hover:bg-brand-forest/10'} rounded-lg transition-colors"
											>
												{user.is_active ? 'Deactivate' : 'Activate'}
											</button>
										</div>
									</td>
								</tr>
							{:else}
								<tr>
									<td colspan="6" class="px-6 py-12 text-center">
										<p class="text-brand-charcoal/40 text-sm">No users found</p>
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>

				<div class="px-4 sm:px-6 py-3 bg-brand-warm-gray/50 border-t border-brand-border">
					<p class="text-xs text-brand-charcoal/40">
						Showing {filtered.length} of {users.length} users
					</p>
				</div>
			</Card>
		{/if}
	</main>
</div>

<!-- User Detail Modal -->
<Modal bind:open={showDetailModal} title="User Details" size="lg">
	{#if selectedUser}
		<div class="space-y-6">
			<!-- User Info -->
			<div class="flex items-center gap-4">
				<div class="w-14 h-14 rounded-2xl bg-brand-navy/10 flex items-center justify-center flex-shrink-0">
					<span class="text-xl font-bold text-brand-navy">
						{selectedUser.email?.charAt(0).toUpperCase() || '?'}
					</span>
				</div>
				<div>
					<h3 class="text-lg font-semibold text-brand-charcoal">{selectedUser.email}</h3>
					<div class="flex items-center gap-3 text-sm text-brand-charcoal/50">
						<span class="font-mono text-xs">{selectedUser.id}</span>
						{#if selectedUser.is_admin}
							<Badge variant="warning" size="sm">Admin</Badge>
						{/if}
						{#if !selectedUser.is_active}
							<Badge variant="danger" size="sm">Inactive</Badge>
						{/if}
					</div>
				</div>
			</div>

			<!-- User Info Grid -->
			<div class="grid grid-cols-2 gap-4">
				<div class="bg-brand-warm-gray rounded-xl p-3">
					<p class="text-xs text-brand-charcoal/50">Created</p>
					<p class="text-sm font-medium text-brand-charcoal mt-0.5">{selectedUser.created_at ? formatDate(selectedUser.created_at) : '—'}</p>
				</div>
				<div class="bg-brand-warm-gray rounded-xl p-3">
					<p class="text-xs text-brand-charcoal/50">Applicant ID</p>
					<p class="text-sm font-mono text-brand-navy mt-0.5">{selectedUser.applicant_id || '—'}</p>
				</div>
			</div>

			<!-- Loan Applications -->
			<div>
				<h4 class="text-sm font-semibold text-brand-charcoal/50 uppercase tracking-wider mb-3">
					Loan Applications ({userLoans.length})
				</h4>
	{#if loadingDetail}
						<div class="flex justify-center py-6"><Spinner /></div>
					{:else if userLoans.length > 0}
						<div class="space-y-2">
							{#each userLoans as loan}
								{@const loanRecord = loan as Record<string, unknown>}
								<a
									href="/admin/{loanRecord.application_id}"
									class="block bg-brand-warm-gray rounded-xl p-4 hover:bg-brand-navy/5 transition-colors"
								>
									<div class="flex items-center justify-between">
										<div>
											<p class="font-mono text-sm font-medium text-brand-navy">{loanRecord.application_id}</p>
											<p class="text-xs text-brand-charcoal/50 capitalize">{(loanRecord.loan_purpose as string)?.replace('_', ' ') || 'N/A'}</p>
										</div>
										<div class="text-right">
											<p class="font-mono text-sm font-medium text-brand-charcoal">NPR {(loanRecord.requested_amount_nrs as number)?.toLocaleString()}</p>
											<p class="text-xs text-brand-charcoal/40">{loanRecord.credit_score ? `Score: ${loanRecord.credit_score}` : 'No score'}</p>
										</div>
									</div>
								</a>
							{/each}
						</div>
					{:else}
						<p class="text-sm text-brand-charcoal/40 text-center py-6">No loan applications</p>
					{/if}
			</div>

			<!-- Actions -->
			<div class="flex gap-3 pt-2 border-t border-brand-border">
				<Button
					variant={selectedUser.is_admin ? 'danger' : 'success'}
					size="sm"
					onclick={() => { toggleAdmin(selectedUser!); showDetailModal = false; }}
				>
					{selectedUser.is_admin ? 'Revoke Admin' : 'Make Admin'}
				</Button>
				<Button
					variant={selectedUser.is_active ? 'danger' : 'success'}
					size="sm"
					onclick={() => { toggleActive(selectedUser!); showDetailModal = false; }}
				>
					{selectedUser.is_active ? 'Deactivate' : 'Activate'}
				</Button>
			</div>
		</div>
	{/if}
</Modal>
