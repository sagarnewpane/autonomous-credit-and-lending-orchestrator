<script lang="ts">
	import { getAuth } from '$lib/stores/auth.svelte';
	import Mandala from '$lib/components/ui/Mandala.svelte';
	import MandalaIcon from '$lib/components/ui/MandalaIcon.svelte';

	const auth = getAuth();
</script>

<div class="min-h-screen">
	<!-- Hero Section -->
	<section class="relative bg-brand-warm-gray overflow-hidden">
		<!-- Mandala background - self-drawing on load -->
		<div class="absolute right-[-10%] top-1/2 -translate-y-1/2 pointer-events-none">
			<Mandala size={700} color="var(--brand-navy)" opacity={0.045} animate={false} draw={true} />
		</div>

		<!-- Subtle gradient wash -->
		<div class="absolute inset-0 bg-gradient-to-br from-brand-warm-gray via-brand-warm-gray to-brand-gold/[0.03]"></div>

		<div class="relative max-w-6xl mx-auto px-4 sm:px-6 py-16 md:py-24">
			<div class="grid lg:grid-cols-2 gap-12 lg:gap-16 items-center">
				<!-- Left: Content -->
				<div class="animate-fade-in-up">
					<div class="inline-flex items-center gap-2 bg-brand-navy/5 px-3.5 py-1.5 rounded-full text-xs font-medium mb-6 border border-brand-navy/8">
						<span class="w-1.5 h-1.5 bg-brand-gold rounded-full"></span>
						<span class="text-brand-navy/70">NRB compliant</span>
					</div>

					<h1 class="text-4xl md:text-5xl lg:text-[3.5rem] mb-5 leading-[1.1] font-display text-brand-charcoal">
						Loan decisions<br />
						in <span class="text-gradient">three minutes</span>
					</h1>

					<p class="text-base md:text-lg text-brand-charcoal/55 mb-8 max-w-md leading-relaxed">
						AI-powered lending for Nepal's informal sector. Upload your documents, get a fair score, receive an instant decision.
					</p>

					<div class="flex flex-col sm:flex-row gap-3">
						{#if auth.isAuthenticated}
							<a href="/dashboard" class="inline-flex items-center justify-center bg-brand-gold text-white px-7 py-3.5 rounded-lg font-semibold text-sm hover:bg-brand-gold-dark transition-all duration-200 shadow-gold">
								Go to Dashboard
							</a>
						{:else}
							<a href="/auth/signup" class="inline-flex items-center justify-center bg-brand-gold text-white px-7 py-3.5 rounded-lg font-semibold text-sm hover:bg-brand-gold-dark transition-all duration-200 shadow-gold">
								Apply now
							</a>
							<a href="/auth/login" class="inline-flex items-center justify-center border border-brand-charcoal/15 text-brand-charcoal/70 px-7 py-3.5 rounded-lg font-semibold text-sm hover:bg-brand-charcoal/5 transition-all duration-200">
								Sign in
							</a>
						{/if}
					</div>
				</div>

				<!-- Right: Stats Panel -->
				<div class="glass rounded-2xl p-7 border border-white/50 animate-fade-in-up" style="animation-delay: 0.15s">
					<div class="grid grid-cols-2 gap-4">
						<div class="text-center p-4 rounded-xl bg-brand-navy/[0.04]">
							<div class="text-3xl font-bold mb-1 font-mono text-brand-navy">3-5</div>
							<div class="text-brand-charcoal/45 text-xs font-medium uppercase tracking-wider">Minutes to decision</div>
						</div>
						<div class="text-center p-4 rounded-xl bg-brand-gold/[0.06]">
							<div class="text-3xl font-bold mb-1 font-mono text-brand-gold-dark">300-850</div>
							<div class="text-brand-charcoal/45 text-xs font-medium uppercase tracking-wider">Credit score range</div>
						</div>
						<div class="text-center p-4 rounded-xl bg-brand-forest/[0.06]">
							<div class="text-3xl font-bold mb-1 font-mono text-brand-forest">100%</div>
							<div class="text-brand-charcoal/45 text-xs font-medium uppercase tracking-wider">Automated OCR</div>
						</div>
						<div class="text-center p-4 rounded-xl bg-brand-navy/[0.04]">
							<div class="text-3xl font-bold mb-1 font-mono text-brand-navy">24/7</div>
							<div class="text-brand-charcoal/45 text-xs font-medium uppercase tracking-wider">Always available</div>
						</div>
					</div>
				</div>
			</div>
		</div>
	</section>

	<!-- Features Section -->
	<section class="py-20 bg-white relative">
		<div class="max-w-6xl mx-auto px-4 sm:px-6">
			<div class="mb-14">
				<div class="flex items-center gap-2.5 mb-3">
					<MandalaIcon size={22} color="var(--brand-navy)" />
					<span class="text-xs font-semibold text-brand-navy/60 uppercase tracking-widest">Capabilities</span>
				</div>
				<h2 class="text-3xl md:text-4xl font-display text-brand-charcoal">Built for Nepal's lending reality</h2>
			</div>

			<div class="grid md:grid-cols-3 gap-5">
				<!-- Feature 1: OCR -->
				<div class="group p-7 rounded-2xl border border-brand-charcoal/6 bg-white hover:border-brand-navy/15 transition-all duration-300 relative overflow-hidden">
					<div class="absolute top-0 left-0 w-full h-0.5 bg-brand-navy/10 group-hover:bg-brand-navy/30 transition-colors"></div>
					<div class="w-10 h-10 bg-brand-navy/8 rounded-lg flex items-center justify-center mb-5">
						<svg class="w-5 h-5 text-brand-navy" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
						</svg>
					</div>
					<h3 class="text-base font-semibold text-brand-charcoal mb-2 font-display">Document OCR</h3>
					<p class="text-sm text-brand-charcoal/50 leading-relaxed">Automated extraction from Nagrikta, Lalpurja, and tax documents using AI vision models.</p>
				</div>

				<!-- Feature 2: Credit Scoring -->
				<div class="group p-7 rounded-2xl border border-brand-charcoal/6 bg-white hover:border-brand-gold/20 transition-all duration-300 relative overflow-hidden">
					<div class="absolute top-0 left-0 w-full h-0.5 bg-brand-gold/15 group-hover:bg-brand-gold/40 transition-colors"></div>
					<div class="w-10 h-10 bg-brand-gold/8 rounded-lg flex items-center justify-center mb-5">
						<svg class="w-5 h-5 text-brand-gold-dark" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
						</svg>
					</div>
					<h3 class="text-base font-semibold text-brand-charcoal mb-2 font-display">Credit scoring</h3>
					<p class="text-sm text-brand-charcoal/50 leading-relaxed">XGBoost-powered 300-850 score with SHAP explainability for transparent decisions.</p>
				</div>

				<!-- Feature 3: Compliance -->
				<div class="group p-7 rounded-2xl border border-brand-charcoal/6 bg-white hover:border-brand-forest/15 transition-all duration-300 relative overflow-hidden">
					<div class="absolute top-0 left-0 w-full h-0.5 bg-brand-forest/10 group-hover:bg-brand-forest/30 transition-colors"></div>
					<div class="w-10 h-10 bg-brand-forest/8 rounded-lg flex items-center justify-center mb-5">
						<svg class="w-5 h-5 text-brand-forest" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
						</svg>
					</div>
					<h3 class="text-base font-semibold text-brand-charcoal mb-2 font-display">NRB compliance</h3>
					<p class="text-sm text-brand-charcoal/50 leading-relaxed">Automated checks against Nepal Rastra Bank Unified Directives with full audit trail.</p>
				</div>
			</div>
		</div>
	</section>

	<!-- How It Works Section -->
	<section class="py-20 bg-brand-warm-gray relative">
		<div class="max-w-6xl mx-auto px-4 sm:px-6">
			<div class="mb-14">
				<div class="flex items-center gap-2.5 mb-3">
					<MandalaIcon size={22} color="var(--brand-navy)" />
					<span class="text-xs font-semibold text-brand-navy/60 uppercase tracking-widest">Process</span>
				</div>
				<h2 class="text-3xl md:text-4xl font-display text-brand-charcoal">Three steps to a decision</h2>
			</div>

			<div class="grid md:grid-cols-3 gap-6 relative">
				<!-- Connector line -->
				<div class="absolute top-8 left-[16.7%] right-[16.7%] h-px bg-gradient-to-r from-brand-navy/15 via-brand-gold/20 to-brand-forest/15 hidden md:block"></div>

				<!-- Step 1 -->
				<div class="relative">
					<div class="w-16 h-16 bg-brand-navy text-white rounded-2xl flex items-center justify-center mb-5 text-xl font-bold shadow-lg shadow-brand-navy/15 relative z-10">
						1
					</div>
					<h3 class="text-base font-semibold text-brand-charcoal mb-1.5 font-display">Upload documents</h3>
					<p class="text-sm text-brand-charcoal/50 leading-relaxed">Snap photos of your ID, land deed, and tax documents.</p>
				</div>

				<!-- Step 2 -->
				<div class="relative">
					<div class="w-16 h-16 bg-brand-gold text-white rounded-2xl flex items-center justify-center mb-5 text-xl font-bold shadow-lg shadow-brand-gold/20 relative z-10">
						2
					</div>
					<h3 class="text-base font-semibold text-brand-charcoal mb-1.5 font-display">AI processes</h3>
					<p class="text-sm text-brand-charcoal/50 leading-relaxed">Our AI extracts data, scores your credit, and checks compliance.</p>
				</div>

				<!-- Step 3 -->
				<div class="relative">
					<div class="w-16 h-16 bg-brand-forest text-white rounded-2xl flex items-center justify-center mb-5 text-xl font-bold shadow-lg shadow-brand-forest/15 relative z-10">
						3
					</div>
					<h3 class="text-base font-semibold text-brand-charcoal mb-1.5 font-display">Get your answer</h3>
					<p class="text-sm text-brand-charcoal/50 leading-relaxed">Receive instant approval or detailed feedback with next steps.</p>
				</div>
			</div>
		</div>
	</section>

	<!-- CTA Section -->
	<section class="py-20 bg-brand-navy text-white relative overflow-hidden">
		<!-- Mandala background -->
		<div class="absolute right-[-5%] top-1/2 -translate-y-1/2 pointer-events-none opacity-[0.04]">
			<Mandala size={500} color="white" opacity={1} animate={true} />
		</div>

		<div class="relative max-w-3xl mx-auto px-4 sm:px-6 text-center">
			<h2 class="text-3xl md:text-4xl font-display text-white mb-4">Start lending smarter</h2>
			<p class="text-base text-white/45 mb-8 max-w-xl mx-auto leading-relaxed">
				Join the banks and microfinance institutions automating credit decisions for Nepal's informal sector.
			</p>
			<div class="flex flex-col sm:flex-row gap-3 justify-center">
				{#if !auth.isAuthenticated}
					<a href="/auth/signup" class="inline-flex items-center justify-center bg-brand-gold text-white px-7 py-3.5 rounded-lg font-semibold text-sm hover:bg-brand-gold-dark transition-all duration-200 shadow-gold">
						Create free account
					</a>
				{/if}
				<a href="/auth/login" class="inline-flex items-center justify-center border border-white/20 text-white/80 px-7 py-3.5 rounded-lg font-semibold text-sm hover:bg-white/10 transition-all duration-200">
					Sign in
				</a>
			</div>
		</div>
	</section>

	<!-- Footer -->
	<footer class="bg-brand-charcoal text-white py-10 relative">
		<div class="max-w-6xl mx-auto px-4 sm:px-6">
			<div class="grid md:grid-cols-3 gap-8 mb-8">
				<!-- Logo & Description -->
				<div>
					<div class="flex items-center gap-2.5 mb-3">
						<MandalaIcon size={20} color="var(--brand-gold)" />
						<span class="text-base text-white font-display">Dhago</span>
					</div>
					<p class="text-sm text-white/35 leading-relaxed">Autonomous lending and credit system for Nepal's informal sector.</p>
				</div>

				<!-- Quick Links -->
				<div>
					<h4 class="text-xs font-semibold text-white/50 uppercase tracking-wider mb-4">Navigate</h4>
					<ul class="space-y-2 text-sm text-white/35">
						<li><a href="/auth/login" class="hover:text-brand-gold transition-colors">Sign in</a></li>
						<li><a href="/auth/signup" class="hover:text-brand-gold transition-colors">Create account</a></li>
						<li><a href="/dashboard" class="hover:text-brand-gold transition-colors">Dashboard</a></li>
					</ul>
				</div>

				<!-- Contact -->
				<div>
					<h4 class="text-xs font-semibold text-white/50 uppercase tracking-wider mb-4">Contact</h4>
					<ul class="space-y-2 text-sm text-white/35">
						<li>Kathmandu, Nepal</li>
						<li>support@autolend.com.np</li>
					</ul>
				</div>
			</div>

			<!-- Bottom bar -->
			<div class="border-t border-white/8 pt-6 flex flex-col md:flex-row justify-between items-center gap-3">
				<p class="text-xs text-white/25">&copy; 2025 Dhago. All rights reserved.</p>
				<div class="flex items-center gap-1.5 text-xs text-white/25">
					<span>Built for Nepal</span>
					<MandalaIcon size={12} color="var(--brand-gold)" />
				</div>
			</div>
		</div>
	</footer>
</div>
