<script lang="ts">
	import { getAuth } from '$lib/stores/auth.svelte';
	import Card from '$lib/components/ui/Card.svelte';
	import MandalaIcon from '$lib/components/ui/MandalaIcon.svelte';

	const auth = getAuth();
</script>

<div class="max-w-2xl mx-auto px-4 py-8">
	<!-- Header -->
	<div class="flex items-center gap-3 mb-8">
		<MandalaIcon size={40} color="var(--brand-navy)" />
		<div>
			<h1 class="text-3xl font-bold text-brand-charcoal">Profile</h1>
			<p class="text-brand-charcoal/60">Your account information</p>
		</div>
	</div>

	<Card class="p-6 relative overflow-hidden">
		<!-- Decorative corner -->
		<div class="absolute top-0 right-0 w-20 h-20 bg-brand-navy/5 rounded-bl-full"></div>
		
		<dl class="space-y-4">
			<div class="flex justify-between">
				<dt class="text-brand-charcoal/60">User ID</dt>
				<dd class="font-mono text-brand-charcoal">{auth.user?.id}</dd>
			</div>
			<div class="flex justify-between">
				<dt class="text-brand-charcoal/60">Email</dt>
				<dd class="text-brand-charcoal">{auth.user?.email}</dd>
			</div>
			<div class="flex justify-between">
				<dt class="text-brand-charcoal/60">Status</dt>
				<dd>
					<span class="px-2 py-1 rounded text-sm {auth.user?.is_active ? 'bg-brand-forest/10 text-brand-forest' : 'bg-brand-danger/10 text-brand-danger'}">
						{auth.user?.is_active ? 'Active' : 'Inactive'}
					</span>
				</dd>
			</div>
			<div class="flex justify-between">
				<dt class="text-brand-charcoal/60">Role</dt>
				<dd>
					<span class="px-2 py-1 rounded text-sm {auth.user?.is_admin ? 'bg-brand-navy/10 text-brand-navy' : 'bg-brand-warm-gray text-brand-charcoal/70'}">
						{auth.user?.is_admin ? 'Admin' : 'User'}
					</span>
				</dd>
			</div>
			{#if auth.user?.created_at}
				<div class="flex justify-between">
					<dt class="text-brand-charcoal/60">Member Since</dt>
					<dd class="text-brand-charcoal">{new Date(auth.user.created_at).toLocaleDateString()}</dd>
				</div>
			{/if}
		</dl>
	</Card>
</div>
