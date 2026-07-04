<script lang="ts">
	import { getAuth } from '$lib/stores/auth.svelte';
	import { applyLoan, getApplicantProfile, getUserLoanHistory } from '$lib/services/loans';
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import Input from '$lib/components/ui/Input.svelte';
	import Select from '$lib/components/ui/Select.svelte';
	import Card from '$lib/components/ui/Card.svelte';
	import LanguageToggle from '$lib/components/ui/LanguageToggle.svelte';
	import Tooltip from '$lib/components/ui/Tooltip.svelte';
	import RiverProgress from '$lib/components/ui/RiverProgress.svelte';
	import { formatAmount, formatFileSize } from '$lib/utils/format';
	import { t, tObj } from '$lib/i18n';
	import en from '$lib/i18n/en.json';
	import NepaliDate from 'nepali-date-converter';

	const auth = getAuth();

	let lang = $state<'en' | 'ne'>('en');
	let step = $state(1);
	let loading = $state(false);
	let profileLoading = $state(true);
	let error = $state('');
	let success = $state(false);
	let applicationId = $state('');
	let isReturningApplicant = $state(false);
	let activeApplication = $state(false);
	let activeApplicationId = $state('');

	// Applicant Identification
	let fullNameEn = $state('');
	let fatherNameEn = $state('');
	let grandfatherNameEn = $state('');
	let gender = $state('');
	let maritalStatus = $state('');

	// Citizenship Details
	let citizenshipNumber = $state('');
	let citizenshipIssueDateBs = $state('');
	let citizenshipOffice = $state('');

	// Date of Birth
	let dobAd = $state('');
	let dobBs = $state('');

	// Address
	let provinceEn = $state('');
	let districtEn = $state('');
	let municipalityEn = $state('');
	let wardNo = $state('');

	// Contact
	let phonePrimary = $state('');

	// Personal Information
	let occupationEn = $state('');
	let occupationNp = $state('');
	let educationLevel = $state('');
	let householdSize = $state('2');

	// Financial Information
	let hasEsewaAccount = $state(false);
	let hasKhaltiAccount = $state(false);
	let primaryBank = $state('');
	let receivesRemittance = $state(false);
	let cooperativeMember = $state(false);
	let cooperativeId = $state('');

	// Property Information
	let landAreaRopani = $state('');

	// Loan Details
	let loanPurpose = $state('');
	let requestedAmountNrs = $state(200000);
	let requestedTenureMonths = $state('12');
	let collateralType = $state('none');
	let collateralValueNrs = $state(0);
	let existingLoanAmount = $state(0);
	let creditBureauScore = $state('');

	// Document files (dummy for showcase)
	let citizenshipFile = $state<File | null>(null);
	let kycFormFile = $state<File | null>(null);
	let lalpurjaFile = $state<File | null>(null);
	let utilityBillFile = $state<File | null>(null);
	let remittanceReceiptsFile = $state<File | null>(null);
	let cooperativeRecordsFile = $state<File | null>(null);

	let requiresLalpurja = $derived(collateralType === 'land');
	let showCooperativeUpload = $derived(cooperativeMember);
	let showRemittanceUpload = $derived(receivesRemittance);

	const tenureOptions = $derived([
		{ value: '6', label: '6 mo' },
		{ value: '12', label: '12 mo' },
		{ value: '18', label: '18 mo' },
		{ value: '24', label: '24 mo' },
		{ value: '36', label: '36 mo' }
	]);

	const occupationOptions = $derived(tObj(lang, 'occupations'));

	const householdSizeOptions = $derived(
		Array.from({ length: 8 }, (_, i) => ({
			value: String(i + 1),
			label: String(i + 1)
		}))
	);

	const purposeOptions = $derived(tObj(lang, 'purposes').map(opt => ({
		...opt,
		icon: (en.purposes as Record<string, { icon?: string }>)[opt.value]?.icon
	})));

	const collateralOptions = $derived(tObj(lang, 'collateral'));

	const genderOptions = $derived(tObj(lang, 'genderOptions'));

	const maritalStatusOptions = $derived(tObj(lang, 'maritalStatusOptions'));

	const educationLevelOptions = $derived(tObj(lang, 'educationLevelOptions'));

	const primaryBankOptions = $derived(tObj(lang, 'primaryBankOptions'));

	const existingLoanOptions = $derived([
		{ value: '0', label: '0' },
		{ value: '1', label: '1' },
		{ value: '2', label: '2' },
		{ value: '3', label: '3' }
	]);

	onMount(async () => {
		try {
			const res = await getApplicantProfile();
			if (res.has_profile && res.profile) {
				isReturningApplicant = true;
				const p = res.profile;
				fullNameEn = p.full_name_en || '';
				fatherNameEn = p.father_name_en || '';
				grandfatherNameEn = p.grandfather_name_en || '';
				gender = p.gender || '';
				maritalStatus = p.marital_status || '';
				citizenshipNumber = p.citizenship_number || '';
				citizenshipIssueDateBs = p.citizenship_date_bs || '';
				citizenshipOffice = p.citizenship_office || '';
				dobAd = p.dob_ad || '';
				dobBs = p.dob_bs || '';
				provinceEn = p.province_en || '';
				districtEn = p.district_en || '';
				municipalityEn = p.municipality_en || '';
				wardNo = p.ward_no ? String(p.ward_no) : '';
				phonePrimary = p.phone_primary ? String(p.phone_primary) : '';
				occupationEn = p.occupation_en || '';
				occupationNp = p.occupation_np || '';
				educationLevel = p.education_level || '';
				householdSize = p.household_size ? String(p.household_size) : '2';
				hasEsewaAccount = p.has_esewa_account || false;
				hasKhaltiAccount = p.has_khalti_account || false;
				primaryBank = p.primary_bank || '';
				receivesRemittance = p.remittance_receiving || false;
				cooperativeMember = p.cooperative_member || false;
				cooperativeId = p.cooperative_id || '';
				landAreaRopani = p.land_area_ropani ? String(p.land_area_ropani) : '';
				step = 2;
			}
		} catch {
			// No profile found, stay on step 1
		} finally {
			profileLoading = false;
		}

		// Check for active (pending) application
		try {
			const history = await getUserLoanHistory();
			const active = history.applications.find(
				(a) => !a.final_decision || a.final_decision === 'PENDING'
			);
			if (active) {
				activeApplication = true;
				activeApplicationId = active.application_id;
			}
		} catch {
			// Ignore errors - allow user to try applying
		}
	});

	const inputClass = 'w-full px-4 py-2.5 rounded-xl border text-sm transition-all duration-200 border-brand-border bg-white hover:border-brand-gray/30 focus:outline-none focus:ring-2 focus:ring-brand-gold/30 focus:border-brand-gold placeholder:text-brand-charcoal/30';

	function formatCitizenshipNumber(value: string): string {
		const digits = value.replace(/\D/g, '').slice(0, 11);
		if (digits.length <= 3) return digits;
		if (digits.length <= 5) return `${digits.slice(0, 3)}-${digits.slice(3)}`;
		return `${digits.slice(0, 3)}-${digits.slice(3, 5)}-${digits.slice(5)}`;
	}

	function handleDobAdChange(e: Event) {
		const input = e.target as HTMLInputElement;
		dobAd = input.value;
		if (dobAd) {
			try {
				const date = new Date(dobAd);
				const bs = new NepaliDate(date).getBS();
				dobBs = `${bs.year}-${String(bs.month + 1).padStart(2, '0')}-${String(bs.date).padStart(2, '0')}`;
			} catch {
				dobBs = '';
			}
		} else {
			dobBs = '';
		}
	}

	function validateStep1(): boolean {
		if (!fullNameEn.trim()) {
			error = t(lang, 'apply.errors.fullNameRequired');
			return false;
		}
		if (!fatherNameEn.trim()) {
			error = t(lang, 'apply.errors.fatherNameRequired');
			return false;
		}
		if (!grandfatherNameEn.trim()) {
			error = t(lang, 'apply.errors.grandfatherNameRequired');
			return false;
		}
		if (!gender) {
			error = t(lang, 'apply.errors.genderRequired');
			return false;
		}
		if (!maritalStatus) {
			error = t(lang, 'apply.errors.maritalStatusRequired');
			return false;
		}
		const citizenshipDigits = citizenshipNumber.replace(/\D/g, '');
		if (citizenshipDigits.length !== 11) {
			error = t(lang, 'apply.errors.citizenshipInvalid');
			return false;
		}
		if (!citizenshipIssueDateBs.trim()) {
			error = t(lang, 'apply.errors.citizenshipIssueDateRequired');
			return false;
		}
		if (!citizenshipOffice.trim()) {
			error = t(lang, 'apply.errors.citizenshipOfficeRequired');
			return false;
		}
		if (!dobAd) {
			error = t(lang, 'apply.errors.dobAdRequired');
			return false;
		}
		if (!dobBs.trim()) {
			error = t(lang, 'apply.errors.dobBsRequired');
			return false;
		}
		if (!provinceEn.trim()) {
			error = t(lang, 'apply.errors.provinceRequired');
			return false;
		}
		if (!districtEn.trim()) {
			error = t(lang, 'apply.errors.districtRequired');
			return false;
		}
		if (!municipalityEn.trim()) {
			error = t(lang, 'apply.errors.municipalityRequired');
			return false;
		}
		if (!wardNo.trim()) {
			error = t(lang, 'apply.errors.wardRequired');
			return false;
		}
		const phoneDigits = phonePrimary.replace(/\D/g, '');
		if (!phoneDigits || phoneDigits.length !== 10) {
			error = t(lang, 'apply.errors.phoneRequired');
			return false;
		}
		if (!occupationEn) {
			error = t(lang, 'apply.errors.occupationRequired');
			return false;
		}
		if (!educationLevel) {
			error = t(lang, 'apply.errors.educationLevelRequired');
			return false;
		}
		if (!householdSize) {
			error = t(lang, 'apply.errors.householdRequired');
			return false;
		}
		error = '';
		return true;
	}

	function validateStep2(): boolean {
		if (!primaryBank) {
			error = t(lang, 'apply.errors.primaryBankRequired');
			return false;
		}
		if (cooperativeMember && !cooperativeId.trim()) {
			error = t(lang, 'apply.errors.cooperativeIdRequired');
			return false;
		}
		if (receivesRemittance) {
			// Remittance is optional but if toggled on, just continue
		}
		if (!loanPurpose) {
			error = t(lang, 'apply.errors.purposeRequired');
			return false;
		}
		if (requestedAmountNrs < 10000) {
			error = t(lang, 'apply.errors.loanAmountInvalid');
			return false;
		}
		if (!requestedTenureMonths) {
			error = t(lang, 'apply.errors.tenureRequired');
			return false;
		}
		if (requiresLalpurja && collateralValueNrs <= 0) {
			error = t(lang, 'apply.errors.collateralValueRequired');
			return false;
		}
		error = '';
		return true;
	}

	function validateStep3(): boolean {
		error = '';
		return true;
	}

	function nextStep() {
		if (step === 1 && !validateStep1()) return;
		if (step === 2 && !validateStep2()) return;
		if (step < 3) step++;
	}

	function prevStep() {
		if (step > 1) step--;
		error = '';
	}

	function handleFileChange(e: Event, fileType: 'citizenship' | 'kyc' | 'lalpurja' | 'utility' | 'remittance' | 'cooperative') {
		const target = e.target as HTMLInputElement;
		const file = target.files?.[0] ?? null;

		if (file && file.size > 10 * 1024 * 1024) {
			error = `${file.name} exceeds 10MB limit`;
			target.value = '';
			return;
		}

		switch (fileType) {
			case 'citizenship':
				citizenshipFile = file;
				break;
			case 'kyc':
				kycFormFile = file;
				break;
			case 'lalpurja':
				lalpurjaFile = file;
				break;
			case 'utility':
				utilityBillFile = file;
				break;
			case 'remittance':
				remittanceReceiptsFile = file;
				break;
			case 'cooperative':
				cooperativeRecordsFile = file;
				break;
		}
		error = '';
	}

	function triggerCamera(inputId: string) {
		const input = document.getElementById(inputId) as HTMLInputElement;
		if (input) {
			input.setAttribute('capture', 'environment');
			input.click();
		}
	}

	function triggerFileUpload(inputId: string) {
		const input = document.getElementById(inputId) as HTMLInputElement;
		if (input) {
			input.removeAttribute('capture');
			input.click();
		}
	}

	async function handleSubmit(e: Event) {
		e.preventDefault();
		if (!validateStep3()) return;
		if (activeApplication) {
			error = 'You already have an active application. Please wait for it to be approved or rejected.';
			return;
		}

		loading = true;

		try {
			const formData = new FormData();

			// Applicant Identification
			formData.append('full_name_en', fullNameEn);
			formData.append('father_name_en', fatherNameEn);
			formData.append('grandfather_name_en', grandfatherNameEn);
			formData.append('gender', gender);
			formData.append('marital_status', maritalStatus);

			// Citizenship Details
			formData.append('citizenship_number', citizenshipNumber.replace(/\D/g, ''));
			formData.append('citizenship_issue_date_bs', citizenshipIssueDateBs);
			formData.append('citizenship_office', citizenshipOffice);

			// Date of Birth
			formData.append('dob_ad', dobAd);
			formData.append('dob_bs', dobBs);

			// Address
			formData.append('province_en', provinceEn);
			formData.append('district_en', districtEn);
			formData.append('municipality_en', municipalityEn);
			formData.append('ward_no', wardNo);

			// Contact
			formData.append('phone_primary', phonePrimary.replace(/\D/g, ''));

			// Personal Information
			formData.append('occupation_en', occupationEn);
			formData.append('occupation_np', occupationNp);
			formData.append('education_level', educationLevel);
			formData.append('household_size', householdSize);

			// Financial Information
			formData.append('has_esewa_account', String(hasEsewaAccount));
			formData.append('has_khalti_account', String(hasKhaltiAccount));
			formData.append('primary_bank', primaryBank);
			formData.append('receives_remittance', String(receivesRemittance));
			formData.append('cooperative_member', String(cooperativeMember));
			formData.append('cooperative_id', cooperativeId);

			// Property Information
			formData.append('land_area_ropani', landAreaRopani || '0');

			// Loan Details
			formData.append('loan_purpose', loanPurpose);
			formData.append('requested_amount_nrs', String(requestedAmountNrs));
			formData.append('requested_tenure_months', requestedTenureMonths);
			formData.append('collateral_type', collateralType);
			formData.append('collateral_value_nrs', String(collateralValueNrs));
			formData.append('existing_loan_amount', String(existingLoanAmount));
			formData.append('credit_bureau_score', creditBureauScore);

			// Document files (dummy)
			if (citizenshipFile) formData.append('citizenship_doc', citizenshipFile);
			if (kycFormFile) formData.append('kyc_form_doc', kycFormFile);
			if (lalpurjaFile) formData.append('lalpurja_doc', lalpurjaFile);
			if (utilityBillFile) formData.append('utility_bill', utilityBillFile);
			if (cooperativeRecordsFile) formData.append('cooperative_records', cooperativeRecordsFile);
			if (remittanceReceiptsFile) formData.append('remittance_receipt', remittanceReceiptsFile);

			const result = await applyLoan(formData);
			applicationId = result.application?.application_id || '';
			success = true;
		} catch (err: unknown) {
			error = err instanceof Error ? err.message : t(lang, 'apply.errors.applicationFailed');
		} finally {
			loading = false;
		}
	}
</script>

<div class="min-h-screen bg-brand-cream">
	<header class="sticky top-0 z-40 bg-white/80 backdrop-blur-lg border-b border-brand-border/50">
		<div class="max-w-2xl mx-auto px-4 py-3 flex items-center justify-between">
			<a href="/dashboard" class="flex items-center gap-2 text-brand-charcoal/60 hover:text-brand-charcoal transition-colors">
				<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
				</svg>
				<span class="text-sm font-medium">{t(lang, 'apply.back')}</span>
			</a>
			<LanguageToggle bind:lang />
		</div>
	</header>

	<main class="max-w-2xl mx-auto px-4 py-6 pb-24">
		{#if success}
			<div class="animate-fade-in-up text-center py-12">
				<div class="w-20 h-20 bg-brand-forest/10 rounded-full flex items-center justify-center mx-auto mb-6">
					<svg class="w-10 h-10 text-brand-forest" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
					</svg>
				</div>
				<h1 class="text-2xl text-brand-charcoal mb-2 font-display">
					{t(lang, 'apply.success.title')}
				</h1>
				<p class="text-brand-charcoal/60 mb-6">
					{t(lang, 'apply.success.description')}
				</p>
				{#if applicationId}
					<div class="bg-white rounded-xl border border-brand-border p-4 inline-block mb-6">
						<p class="text-xs text-brand-charcoal/50 mb-1">{t(lang, 'apply.success.appId')}</p>
						<p class="font-mono text-lg font-semibold text-brand-navy">{applicationId}</p>
					</div>
				{/if}
				<div class="flex flex-col gap-3">
					<a href="/dashboard/applications" class="bg-brand-navy text-white px-6 py-3 rounded-xl font-medium hover:bg-brand-navy-light transition-colors">
						{t(lang, 'apply.success.trackStatus')}
					</a>
					<a href="/dashboard" class="text-brand-charcoal/60 hover:text-brand-charcoal transition-colors text-sm">
						{t(lang, 'apply.success.backToDashboard')}
					</a>
				</div>
			</div>
		{:else}
			{#if profileLoading}
				<div class="text-center py-16">
					<div class="w-10 h-10 border-4 border-brand-navy/20 border-t-brand-navy rounded-full animate-spin mx-auto mb-4"></div>
					<p class="text-sm text-brand-charcoal/50">{t(lang, 'apply.loadingProfile')}</p>
				</div>
			{:else if activeApplication}
				<div class="animate-fade-in-up text-center py-12">
					<div class="w-20 h-20 bg-brand-gold/10 rounded-full flex items-center justify-center mx-auto mb-6">
						<svg class="w-10 h-10 text-brand-gold-dark" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
						</svg>
					</div>
					<h1 class="text-2xl text-brand-charcoal mb-2 font-display">
						Application In Progress
					</h1>
					<p class="text-brand-charcoal/60 mb-4 max-w-md mx-auto">
						You already have an active application that is being reviewed. You can only apply for a new loan once your current application is approved or rejected.
					</p>
					{#if activeApplicationId}
						<div class="bg-white rounded-xl border border-brand-border p-4 inline-block mb-6">
							<p class="text-xs text-brand-charcoal/50 mb-1">Your active application</p>
							<p class="font-mono text-lg font-semibold text-brand-navy">{activeApplicationId}</p>
						</div>
					{/if}
					<div class="flex flex-col gap-3">
						<a href="/dashboard/applications" class="bg-brand-navy text-white px-6 py-3 rounded-xl font-medium hover:bg-brand-navy-light transition-colors">
							View Application Status
						</a>
						<a href="/dashboard" class="text-brand-charcoal/60 hover:text-brand-charcoal transition-colors text-sm">
							Back to Dashboard
						</a>
					</div>
				</div>
			{:else}
			<div class="mb-6 animate-fade-in-up">
				<h1 class="text-2xl text-brand-charcoal font-display">
					{t(lang, 'apply.title')}
				</h1>
				<p class="text-sm text-brand-charcoal/50 mt-1">
					{t(lang, 'apply.subtitle')}
				</p>
			</div>

			<div class="mb-8 animate-fade-in-up stagger-1">
				<RiverProgress
					currentStep={step}
					totalSteps={3}
					labels={[
						t(lang, 'apply.step1.title'),
						t(lang, 'apply.step2.title'),
						t(lang, 'apply.step3.title')
					]}
				/>
			</div>

			{#if error}
				<div class="bg-brand-burgundy/10 text-brand-burgundy p-4 rounded-xl mb-6 text-sm font-medium animate-fade-in flex items-start gap-3" role="alert">
					<svg class="w-5 h-5 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
					</svg>
					{error}
				</div>
			{/if}

			<form onsubmit={handleSubmit}>
				{#if step === 1}
					<Card class="p-6 animate-slide-in-right">
						<h2 class="text-lg font-semibold text-brand-charcoal mb-5 font-display flex items-center gap-2">
							<span class="w-8 h-8 bg-brand-navy text-white rounded-lg flex items-center justify-center text-sm font-bold">1</span>
							{t(lang, 'apply.step1.title')}
						</h2>
						<p class="text-sm text-brand-charcoal/50 mb-6">
							{t(lang, 'apply.step1.description')}
						</p>

						{#if isReturningApplicant}
							<div class="bg-brand-forest/10 border border-brand-forest/20 p-4 rounded-xl mb-6 flex items-start gap-3">
								<svg class="w-5 h-5 text-brand-forest flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
								</svg>
								<div>
									<p class="text-sm font-medium text-brand-charcoal">{t(lang, 'apply.step1.returningBanner')}</p>
									<p class="text-xs text-brand-charcoal/50 mt-1">{t(lang, 'apply.step1.returningBannerHint')}</p>
								</div>
							</div>
						{/if}

						<div class="space-y-6">
							<!-- Applicant Identification -->
							<div>
								<h3 class="text-sm font-semibold text-brand-navy mb-3 flex items-center gap-2">
									<span class="w-5 h-5 bg-brand-navy/10 rounded flex items-center justify-center">
										<svg class="w-3 h-3 text-brand-navy" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
										</svg>
									</span>
									{t(lang, 'apply.step1.sectionIdentification')}
								</h3>
								<div class="grid grid-cols-1 sm:grid-cols-2 gap-x-5 gap-y-4">
									<div class="sm:col-span-2">
										<label for="full-name" class="block text-sm font-medium text-brand-charcoal mb-1.5">
											{t(lang, 'apply.step1.fullName')} <span class="text-brand-burgundy">*</span>
										</label>
										<input
											id="full-name"
											type="text"
											bind:value={fullNameEn}
											placeholder={t(lang, 'apply.step1.fullNamePlaceholder')}
											class={inputClass}
										/>
									</div>

									<div>
										<label for="father-name" class="block text-sm font-medium text-brand-charcoal mb-1.5">
											{t(lang, 'apply.step1.fatherName')} <span class="text-brand-burgundy">*</span>
										</label>
										<input
											id="father-name"
											type="text"
											bind:value={fatherNameEn}
											placeholder={t(lang, 'apply.step1.fatherNamePlaceholder')}
											class={inputClass}
										/>
									</div>

									<div>
										<label for="grandfather-name" class="block text-sm font-medium text-brand-charcoal mb-1.5">
											{t(lang, 'apply.step1.grandfatherName')} <span class="text-brand-burgundy">*</span>
										</label>
										<input
											id="grandfather-name"
											type="text"
											bind:value={grandfatherNameEn}
											placeholder={t(lang, 'apply.step1.grandfatherNamePlaceholder')}
											class={inputClass}
										/>
									</div>

									<Select
										label={t(lang, 'apply.step1.gender')}
										bind:value={gender}
										options={genderOptions}
										required
										placeholder={t(lang, 'apply.step1.genderPlaceholder')}
									/>

									<Select
										label={t(lang, 'apply.step1.maritalStatus')}
										bind:value={maritalStatus}
										options={maritalStatusOptions}
										required
										placeholder={t(lang, 'apply.step1.maritalStatusPlaceholder')}
									/>
								</div>
							</div>

							<!-- Citizenship Details -->
							<div>
								<h3 class="text-sm font-semibold text-brand-navy mb-3 flex items-center gap-2">
									<span class="w-5 h-5 bg-brand-navy/10 rounded flex items-center justify-center">
										<svg class="w-3 h-3 text-brand-navy" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
										</svg>
									</span>
									{t(lang, 'apply.step1.sectionCitizenship')}
								</h3>
								<div class="grid grid-cols-1 sm:grid-cols-2 gap-x-5 gap-y-4">
									<div>
										<label for="citizenship-number" class="block text-sm font-medium text-brand-charcoal mb-1.5">
											{t(lang, 'apply.step1.citizenship')} <span class="text-brand-burgundy">*</span>
										</label>
										<input
											id="citizenship-number"
											type="text"
											bind:value={citizenshipNumber}
											oninput={() => { citizenshipNumber = formatCitizenshipNumber(citizenshipNumber); }}
											placeholder="DDD-DDD-DDDDD"
											maxlength="13"
											class={inputClass}
										/>
										<p class="text-xs text-brand-charcoal/40 mt-1">{t(lang, 'apply.step1.citizenshipHint')}</p>
									</div>

									<div>
										<label for="citizenship-issue-date" class="block text-sm font-medium text-brand-charcoal mb-1.5">
											{t(lang, 'apply.step1.citizenshipIssueDate')} <span class="text-brand-burgundy">*</span>
										</label>
										<input
											id="citizenship-issue-date"
											type="text"
											bind:value={citizenshipIssueDateBs}
											placeholder={t(lang, 'apply.step1.citizenshipIssueDatePlaceholder')}
											class={inputClass}
										/>
										<p class="text-xs text-brand-charcoal/40 mt-1">{t(lang, 'apply.step1.citizenshipIssueDateHint')}</p>
									</div>

									<div class="sm:col-span-2">
										<label for="citizenship-office" class="block text-sm font-medium text-brand-charcoal mb-1.5">
											{t(lang, 'apply.step1.citizenshipOffice')} <span class="text-brand-burgundy">*</span>
										</label>
										<input
											id="citizenship-office"
											type="text"
											bind:value={citizenshipOffice}
											placeholder={t(lang, 'apply.step1.citizenshipOfficePlaceholder')}
											class={inputClass}
										/>
									</div>
								</div>
							</div>

							<!-- Date of Birth -->
							<div>
								<h3 class="text-sm font-semibold text-brand-navy mb-3 flex items-center gap-2">
									<span class="w-5 h-5 bg-brand-navy/10 rounded flex items-center justify-center">
										<svg class="w-3 h-3 text-brand-navy" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
										</svg>
									</span>
									{t(lang, 'apply.step1.sectionDob')}
								</h3>
								<div class="grid grid-cols-1 sm:grid-cols-2 gap-x-5 gap-y-4">
									<div>
										<label for="dob-ad" class="block text-sm font-medium text-brand-charcoal mb-1.5">
											{t(lang, 'apply.step1.dobAd')} <span class="text-brand-burgundy">*</span>
										</label>
										<input
											id="dob-ad"
											type="date"
											value={dobAd}
											onchange={handleDobAdChange}
											class={inputClass}
										/>
									</div>

									<div>
										<label for="dob-bs" class="block text-sm font-medium text-brand-charcoal mb-1.5">
											{t(lang, 'apply.step1.dobBs')} <span class="text-brand-burgundy">*</span>
										</label>
										<input
											id="dob-bs"
											type="text"
											bind:value={dobBs}
											placeholder={t(lang, 'apply.step1.dobBsPlaceholder')}
											class={inputClass}
										/>
										<p class="text-xs text-brand-charcoal/40 mt-1">{t(lang, 'apply.step1.dobBsPlaceholder')}</p>
									</div>
								</div>
							</div>

							<!-- Address -->
							<div>
								<h3 class="text-sm font-semibold text-brand-navy mb-3 flex items-center gap-2">
									<span class="w-5 h-5 bg-brand-navy/10 rounded flex items-center justify-center">
										<svg class="w-3 h-3 text-brand-navy" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
										</svg>
									</span>
									{t(lang, 'apply.step1.sectionAddress')}
								</h3>
								<div class="grid grid-cols-1 sm:grid-cols-2 gap-x-5 gap-y-4">
									<div>
										<label for="province" class="block text-sm font-medium text-brand-charcoal mb-1.5">
											{t(lang, 'apply.step1.province')} <span class="text-brand-burgundy">*</span>
										</label>
										<input
											id="province"
											type="text"
											bind:value={provinceEn}
											placeholder={t(lang, 'apply.step1.provincePlaceholder')}
											class={inputClass}
										/>
									</div>

									<div>
										<label for="district" class="block text-sm font-medium text-brand-charcoal mb-1.5">
											{t(lang, 'apply.step1.district')} <span class="text-brand-burgundy">*</span>
										</label>
										<input
											id="district"
											type="text"
											bind:value={districtEn}
											placeholder={t(lang, 'apply.step1.districtPlaceholder')}
											class={inputClass}
										/>
									</div>

									<div>
										<label for="municipality" class="block text-sm font-medium text-brand-charcoal mb-1.5">
											{t(lang, 'apply.step1.municipality')} <span class="text-brand-burgundy">*</span>
										</label>
										<input
											id="municipality"
											type="text"
											bind:value={municipalityEn}
											placeholder={t(lang, 'apply.step1.municipalityPlaceholder')}
											class={inputClass}
										/>
									</div>

									<div>
										<label for="ward-no" class="block text-sm font-medium text-brand-charcoal mb-1.5">
											{t(lang, 'apply.step1.wardNo')} <span class="text-brand-burgundy">*</span>
										</label>
										<input
											id="ward-no"
											type="text"
											bind:value={wardNo}
											placeholder={t(lang, 'apply.step1.wardNoPlaceholder')}
											class={inputClass}
										/>
									</div>
								</div>
							</div>

							<!-- Contact -->
							<div>
								<h3 class="text-sm font-semibold text-brand-navy mb-3 flex items-center gap-2">
									<span class="w-5 h-5 bg-brand-navy/10 rounded flex items-center justify-center">
										<svg class="w-3 h-3 text-brand-navy" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
										</svg>
									</span>
									{t(lang, 'apply.step1.sectionContact')}
								</h3>
								<div class="grid grid-cols-1 sm:grid-cols-2 gap-x-5 gap-y-4">
									<div class="sm:col-span-2">
										<label for="phone-primary" class="block text-sm font-medium text-brand-charcoal mb-1.5">
											{t(lang, 'apply.step1.phonePrimary')} <span class="text-brand-burgundy">*</span>
										</label>
										<input
											id="phone-primary"
											type="tel"
											bind:value={phonePrimary}
											placeholder={t(lang, 'apply.step1.phonePrimaryPlaceholder')}
											maxlength="10"
											class={inputClass}
										/>
									</div>
								</div>
							</div>

							<!-- Personal Information -->
							<div>
								<h3 class="text-sm font-semibold text-brand-navy mb-3 flex items-center gap-2">
									<span class="w-5 h-5 bg-brand-navy/10 rounded flex items-center justify-center">
										<svg class="w-3 h-3 text-brand-navy" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
										</svg>
									</span>
									{t(lang, 'apply.step1.sectionPersonal')}
								</h3>
								<div class="grid grid-cols-1 sm:grid-cols-2 gap-x-5 gap-y-4">
								<div class="sm:col-span-2">
									<label for="occupation-en" class="block text-sm font-medium text-brand-charcoal mb-1.5">
										{t(lang, 'apply.step1.occupationEn')} <span class="text-brand-burgundy">*</span>
									</label>
									<select
										id="occupation-en"
										bind:value={occupationEn}
										onchange={(e) => {
											const selected = occupationOptions.find(o => o.value === (e.target as HTMLSelectElement).value);
											occupationNp = selected?.ne || '';
										}}
										class={inputClass}
									>
										<option value="">{t(lang, 'apply.step1.occupationPlaceholder')}</option>
										{#each occupationOptions as opt}
											<option value={opt.value}>{opt.label}</option>
										{/each}
									</select>
								</div>

									<Select
										label={t(lang, 'apply.step1.educationLevel')}
										bind:value={educationLevel}
										options={educationLevelOptions}
										required
										placeholder={t(lang, 'apply.step1.educationLevelPlaceholder')}
									/>

									<Select
										label={t(lang, 'apply.step1.householdSize')}
										bind:value={householdSize}
										options={householdSizeOptions}
										required
										placeholder={t(lang, 'apply.step1.householdSizePlaceholder')}
									/>
								</div>
							</div>
						</div>
					</Card>

				{:else if step === 2}
				<Card class="p-6 animate-slide-in-right">
					<h2 class="text-lg font-semibold text-brand-charcoal mb-5 font-display flex items-center gap-2">
						<span class="w-8 h-8 bg-brand-navy text-white rounded-lg flex items-center justify-center text-sm font-bold">2</span>
						{t(lang, 'apply.step2.title')}
					</h2>

					<div class="space-y-6">
						<!-- Financial Information -->
						<div>
							<h3 class="text-sm font-semibold text-brand-navy mb-3 flex items-center gap-2">
								<span class="w-5 h-5 bg-brand-navy/10 rounded flex items-center justify-center">
									<svg class="w-3 h-3 text-brand-navy" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
									</svg>
								</span>
								{t(lang, 'apply.step2.sectionFinancial')}
							</h3>
							<div class="grid grid-cols-1 sm:grid-cols-2 gap-x-5 gap-y-4">
								<div class="col-span-1 sm:col-span-2">
									<div class="grid grid-cols-2 gap-3">
										<div class="flex items-center justify-between py-3 px-4 bg-white rounded-xl border border-brand-border">
											<label for="esewa-toggle" class="text-sm font-medium text-brand-charcoal cursor-pointer">
												{t(lang, 'apply.step2.hasEsewaAccount')}
											</label>
											<button
												id="esewa-toggle"
												type="button"
												onclick={() => hasEsewaAccount = !hasEsewaAccount}
												class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-brand-gold/30
													{hasEsewaAccount ? 'bg-brand-forest' : 'bg-brand-charcoal/20'}"
											>
												<span class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform duration-200 shadow-sm
													{hasEsewaAccount ? 'translate-x-6' : 'translate-x-1'}" />
											</button>
										</div>

										<div class="flex items-center justify-between py-3 px-4 bg-white rounded-xl border border-brand-border">
											<label for="khalti-toggle" class="text-sm font-medium text-brand-charcoal cursor-pointer">
												{t(lang, 'apply.step2.hasKhaltiAccount')}
											</label>
											<button
												id="khalti-toggle"
												type="button"
												onclick={() => hasKhaltiAccount = !hasKhaltiAccount}
												class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-brand-gold/30
													{hasKhaltiAccount ? 'bg-brand-forest' : 'bg-brand-charcoal/20'}"
											>
												<span class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform duration-200 shadow-sm
													{hasKhaltiAccount ? 'translate-x-6' : 'translate-x-1'}" />
											</button>
										</div>
									</div>
								</div>

								<div class="sm:col-span-2">
									<Select
										label={t(lang, 'apply.step2.primaryBank')}
										bind:value={primaryBank}
										options={primaryBankOptions}
										required
										placeholder={t(lang, 'apply.step2.primaryBankPlaceholder')}
									/>
								</div>

								<div class="col-span-1 sm:col-span-2">
									<div class="grid grid-cols-2 gap-3">
										<div class="flex items-center justify-between py-3 px-4 bg-white rounded-xl border border-brand-border">
											<label for="remittance-toggle" class="text-sm font-medium text-brand-charcoal cursor-pointer">
												{t(lang, 'apply.step2.receivesRemittance')}
											</label>
											<button
												id="remittance-toggle"
												type="button"
												onclick={() => receivesRemittance = !receivesRemittance}
												class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-brand-gold/30
													{receivesRemittance ? 'bg-brand-forest' : 'bg-brand-charcoal/20'}"
											>
												<span class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform duration-200 shadow-sm
													{receivesRemittance ? 'translate-x-6' : 'translate-x-1'}" />
											</button>
										</div>

										<div class="flex items-center justify-between py-3 px-4 bg-white rounded-xl border border-brand-border">
											<label for="cooperative-toggle" class="text-sm font-medium text-brand-charcoal cursor-pointer">
												{t(lang, 'apply.step2.cooperativeMember')}
											</label>
											<button
												id="cooperative-toggle"
												type="button"
												onclick={() => cooperativeMember = !cooperativeMember}
												class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-brand-gold/30
													{cooperativeMember ? 'bg-brand-forest' : 'bg-brand-charcoal/20'}"
											>
												<span class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform duration-200 shadow-sm
													{cooperativeMember ? 'translate-x-6' : 'translate-x-1'}" />
											</button>
										</div>
									</div>
								</div>

								{#if cooperativeMember}
									<div class="sm:col-span-2">
										<label for="cooperative-id" class="block text-sm font-medium text-brand-charcoal mb-1.5">
											{t(lang, 'apply.step2.cooperativeId')} <span class="text-brand-burgundy">*</span>
										</label>
										<input
											id="cooperative-id"
											type="text"
											bind:value={cooperativeId}
											placeholder={t(lang, 'apply.step2.cooperativeIdPlaceholder')}
											class={inputClass}
										/>
									</div>
								{/if}
							</div>
						</div>

						<!-- Property Information -->
						<div>
							<h3 class="text-sm font-semibold text-brand-navy mb-3 flex items-center gap-2">
								<span class="w-5 h-5 bg-brand-navy/10 rounded flex items-center justify-center">
									<svg class="w-3 h-3 text-brand-navy" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
									</svg>
								</span>
								{t(lang, 'apply.step2.sectionProperty')}
							</h3>
							<div class="grid grid-cols-1 sm:grid-cols-2 gap-x-5 gap-y-4">
								<div>
									<label for="land-area" class="block text-sm font-medium text-brand-charcoal mb-1.5">
										{t(lang, 'apply.step2.landAreaRopani')}
									</label>
									<input
										id="land-area"
										type="number"
										bind:value={landAreaRopani}
										placeholder={t(lang, 'apply.step2.landAreaRopaniPlaceholder')}
										min="0"
										step="0.1"
										class="w-full px-4 py-2.5 rounded-xl border text-sm transition-all duration-200 border-brand-border bg-white hover:border-brand-gray/30 focus:outline-none focus:ring-2 focus:ring-brand-gold/30 focus:border-brand-gold font-mono placeholder:text-brand-charcoal/30"
									/>
									<p class="text-xs text-brand-charcoal/40 mt-1">{t(lang, 'apply.step2.landAreaRopaniHint')}</p>
								</div>
							</div>
						</div>

						<!-- Loan Details -->
						<div>
							<h3 class="text-sm font-semibold text-brand-navy mb-3 flex items-center gap-2">
								<span class="w-5 h-5 bg-brand-navy/10 rounded flex items-center justify-center">
									<svg class="w-3 h-3 text-brand-navy" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
									</svg>
								</span>
								{t(lang, 'apply.step2.sectionLoan')}
							</h3>
							<div class="space-y-5">
								<div>
									<label for="loan-amount" class="block text-sm font-medium text-brand-charcoal mb-3">
										{t(lang, 'apply.step2.loanAmount')} <span class="text-brand-burgundy">*</span>
									</label>
									<div class="bg-brand-warm-gray rounded-xl p-4">
										<div class="text-center mb-4">
											<span class="text-3xl font-bold text-brand-navy font-mono">NRs {formatAmount(requestedAmountNrs)}</span>
										</div>
										<input
											id="loan-amount"
											type="range"
											min="10000"
											max="5000000"
											step="10000"
											bind:value={requestedAmountNrs}
											class="w-full h-2 bg-brand-warm-gray rounded-full appearance-none cursor-pointer accent-brand-navy
												[&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-6 [&::-webkit-slider-thumb]:h-6 [&::-webkit-slider-thumb]:bg-brand-navy [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:cursor-pointer [&::-webkit-slider-thumb]:shadow-lg
												[&::-moz-range-thumb]:w-6 [&::-moz-range-thumb]:h-6 [&::-moz-range-thumb]:bg-brand-navy [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:border-0 [&::-moz-range-thumb]:cursor-pointer"
										/>
										<div class="flex justify-between text-xs text-brand-charcoal/40 mt-2 font-mono">
											<span>NRs 10,000</span>
											<span>NRs 50,00,000</span>
										</div>
									</div>
								</div>

								<div>
									<span id="tenure-label" class="block text-sm font-medium text-brand-charcoal mb-3">
										{t(lang, 'apply.step2.tenure')} <span class="text-brand-burgundy">*</span>
									</span>
									<div class="grid grid-cols-3 sm:grid-cols-5 gap-2" role="group" aria-labelledby="tenure-label">
										{#each tenureOptions as opt}
											<button
												type="button"
												onclick={() => requestedTenureMonths = opt.value}
												class="py-3 px-2 rounded-xl text-sm font-medium transition-all duration-200 border-2
													{requestedTenureMonths === opt.value
														? 'bg-brand-navy text-white border-brand-navy shadow-sm'
														: 'bg-white text-brand-charcoal/70 border-brand-border hover:border-brand-gray/30'}"
											>
												{opt.label}
											</button>
										{/each}
									</div>
								</div>

								<div>
									<span id="purpose-label" class="block text-sm font-medium text-brand-charcoal mb-3">
										{t(lang, 'apply.step2.purpose')} <span class="text-brand-burgundy">*</span>
									</span>
									<div class="grid grid-cols-2 sm:grid-cols-5 gap-2" role="group" aria-labelledby="purpose-label">
										{#each purposeOptions as opt}
											<button
												type="button"
												onclick={() => loanPurpose = opt.value}
												class="flex flex-col items-center gap-1.5 p-3 rounded-xl border-2 transition-all duration-200
													{loanPurpose === opt.value
														? 'bg-brand-navy/5 border-brand-navy shadow-sm'
														: 'bg-white border-brand-border hover:border-brand-gray/30 hover:bg-brand-warm-gray'}"
											>
												<span class="text-xl">{opt.icon}</span>
												<span class="text-xs font-medium text-center leading-tight text-brand-charcoal/70">
													{opt.label}
												</span>
											</button>
										{/each}
									</div>
								</div>

								<div>
									<span id="collateral-label" class="block text-sm font-medium text-brand-charcoal mb-3">
										{t(lang, 'apply.step2.collateralType')} <span class="text-brand-burgundy">*</span>
									</span>
									<div class="grid grid-cols-2 gap-3" role="group" aria-labelledby="collateral-label">
										{#each collateralOptions as opt}
											<button
												type="button"
												onclick={() => collateralType = opt.value}
												class="p-4 rounded-xl border-2 text-left transition-all duration-200
													{collateralType === opt.value
														? 'bg-brand-navy/5 border-brand-navy'
														: 'bg-white border-brand-border hover:border-brand-gray/30'}"
											>
												<span class="text-sm font-medium text-brand-charcoal">{opt.label}</span>
											</button>
										{/each}
									</div>
								</div>

								{#if requiresLalpurja}
									<div class="bg-brand-gold/10 border border-brand-gold/20 p-4 rounded-xl flex items-start gap-3">
										<svg class="w-5 h-5 text-brand-gold flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
										</svg>
										<p class="text-sm text-brand-charcoal/70">
											{t(lang, 'apply.step2.lalpurjaNote')}
										</p>
									</div>

									<div>
										<div class="flex items-center gap-2 mb-1.5">
											<label for="collateral-value" class="text-sm font-medium text-brand-charcoal">
												{t(lang, 'apply.step2.collateralValue')} <span class="text-brand-burgundy">*</span>
											</label>
											<Tooltip text={t(lang, 'apply.step2.collateralValueTooltip')}>
												<span class="w-4 h-4 rounded-full bg-brand-charcoal/10 text-brand-charcoal/50 flex items-center justify-center text-[10px] font-bold cursor-help">?</span>
											</Tooltip>
										</div>
										<input
											id="collateral-value"
											type="number"
											bind:value={collateralValueNrs}
											placeholder="1000000"
											min="0"
											class="w-full px-4 py-3 rounded-xl border text-sm transition-all duration-200 border-brand-border bg-white hover:border-brand-gray/30 focus:outline-none focus:ring-2 focus:ring-brand-gold/30 focus:border-brand-gold font-mono placeholder:text-brand-charcoal/30"
										/>
										<p class="text-xs text-brand-charcoal/40 mt-1.5">
											{t(lang, 'apply.step2.collateralValueHint')}
										</p>
									</div>
								{/if}

								<div>
									<label for="existing-loan-amount" class="block text-sm font-medium text-brand-charcoal mb-1.5">
										{t(lang, 'apply.step2.existingLoanAmount')}
									</label>
									<input
										id="existing-loan-amount"
										type="number"
										bind:value={existingLoanAmount}
										placeholder="0"
										min="0"
										class="w-full px-4 py-2.5 rounded-xl border text-sm transition-all duration-200 border-brand-border bg-white hover:border-brand-gray/30 focus:outline-none focus:ring-2 focus:ring-brand-gold/30 focus:border-brand-gold font-mono placeholder:text-brand-charcoal/30"
									/>
									<p class="text-xs text-brand-charcoal/40 mt-1">
										{t(lang, 'apply.step2.existingLoanAmountHint')}
									</p>
								</div>

								<div>
									<label for="credit-bureau-score" class="block text-sm font-medium text-brand-charcoal mb-1.5">
										{t(lang, 'apply.step2.creditBureauScore')}
									</label>
									<input
										id="credit-bureau-score"
										type="text"
										bind:value={creditBureauScore}
										placeholder={t(lang, 'apply.step2.creditBureauScorePlaceholder')}
										class="w-full px-4 py-2.5 rounded-xl border text-sm transition-all duration-200 border-brand-border bg-white hover:border-brand-gray/30 focus:outline-none focus:ring-2 focus:ring-brand-gold/30 focus:border-brand-gold font-mono placeholder:text-brand-charcoal/30"
									/>
									<p class="text-xs text-brand-charcoal/40 mt-1">
										{t(lang, 'apply.step2.creditBureauScoreHint')}
									</p>
								</div>
							</div>
						</div>
					</div>
				</Card>

				{:else if step === 3}
				<Card class="p-6 animate-slide-in-right">
					<h2 class="text-lg font-semibold text-brand-charcoal mb-5 font-display flex items-center gap-2">
						<span class="w-8 h-8 bg-brand-navy text-white rounded-lg flex items-center justify-center text-sm font-bold">3</span>
						{t(lang, 'apply.step3.title')}
					</h2>
					<p class="text-sm text-brand-charcoal/50 mb-6">
						{t(lang, 'apply.step3.description')}
					</p>

					<div class="space-y-5">
						<div class="border-2 border-dashed {citizenshipFile ? 'border-brand-forest bg-brand-forest/5' : 'border-brand-border bg-white'} rounded-xl p-5 transition-all duration-200">
							<div class="flex items-center justify-between mb-3">
								<div>
									<p class="font-medium text-brand-charcoal text-sm">
										{t(lang, 'apply.step3.citizenship')}
									</p>
									<p class="text-xs text-brand-charcoal/50 mt-0.5">{t(lang, 'common.fileFormats')}</p>
								</div>
								{#if citizenshipFile}
									<span class="w-8 h-8 bg-brand-forest/10 rounded-full flex items-center justify-center">
										<svg class="w-4 h-4 text-brand-forest" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
										</svg>
									</span>
								{/if}
							</div>
							<input id="citizenship-upload" type="file" accept=".jpg,.jpeg,.png,.pdf" onchange={(e) => handleFileChange(e, 'citizenship')} class="hidden" />
							{#if citizenshipFile}
								<p class="text-sm text-brand-forest font-medium mb-3">✓ {citizenshipFile.name} ({formatFileSize(citizenshipFile.size)})</p>
							{/if}
							<div class="flex gap-3">
								<button type="button" onclick={() => triggerCamera('citizenship-upload')} class="flex-1 flex items-center justify-center gap-2 py-3 px-4 bg-brand-navy text-white rounded-xl text-sm font-medium hover:bg-brand-navy-light transition-colors">
									<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
									</svg>
									{t(lang, 'apply.step3.takePhoto')}
								</button>
								<button type="button" onclick={() => triggerFileUpload('citizenship-upload')} class="flex-1 flex items-center justify-center gap-2 py-3 px-4 bg-brand-warm-gray text-brand-charcoal rounded-xl text-sm font-medium hover:bg-brand-warm-gray transition-colors border border-brand-border">
									<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
									</svg>
									{t(lang, 'apply.step3.uploadFile')}
								</button>
							</div>
						</div>

						<div class="border-2 border-dashed {kycFormFile ? 'border-brand-forest bg-brand-forest/5' : 'border-brand-border bg-white'} rounded-xl p-5 transition-all duration-200">
							<div class="flex items-center justify-between mb-3">
								<div>
									<p class="font-medium text-brand-charcoal text-sm">
										{t(lang, 'apply.step3.kycForm')}
									</p>
									<p class="text-xs text-brand-charcoal/50 mt-0.5">{t(lang, 'common.fileFormats')}</p>
								</div>
								{#if kycFormFile}
									<span class="w-8 h-8 bg-brand-forest/10 rounded-full flex items-center justify-center">
										<svg class="w-4 h-4 text-brand-forest" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
										</svg>
									</span>
								{/if}
							</div>
							<input id="kyc-upload" type="file" accept=".jpg,.jpeg,.png,.pdf" onchange={(e) => handleFileChange(e, 'kyc')} class="hidden" />
							{#if kycFormFile}
								<p class="text-sm text-brand-forest font-medium mb-3">✓ {kycFormFile.name} ({formatFileSize(kycFormFile.size)})</p>
							{/if}
							<div class="flex gap-3">
								<button type="button" onclick={() => triggerCamera('kyc-upload')} class="flex-1 flex items-center justify-center gap-2 py-3 px-4 bg-brand-navy text-white rounded-xl text-sm font-medium hover:bg-brand-navy-light transition-colors">
									<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
									</svg>
									{t(lang, 'apply.step3.takePhoto')}
								</button>
								<button type="button" onclick={() => triggerFileUpload('kyc-upload')} class="flex-1 flex items-center justify-center gap-2 py-3 px-4 bg-brand-warm-gray text-brand-charcoal rounded-xl text-sm font-medium hover:bg-brand-warm-gray transition-colors border border-brand-border">
									<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
									</svg>
									{t(lang, 'apply.step3.uploadFile')}
								</button>
							</div>
						</div>

						<div class="border-2 border-dashed {utilityBillFile ? 'border-brand-forest bg-brand-forest/5' : 'border-brand-border bg-white'} rounded-xl p-5 transition-all duration-200">
							<div class="flex items-center justify-between mb-3">
								<div>
									<p class="font-medium text-brand-charcoal text-sm">
										{t(lang, 'apply.step3.utilityBill')}
									</p>
									<p class="text-xs text-brand-charcoal/50 mt-0.5">{t(lang, 'apply.step3.utilityBillHint')}</p>
								</div>
								{#if utilityBillFile}
									<span class="w-8 h-8 bg-brand-forest/10 rounded-full flex items-center justify-center">
										<svg class="w-4 h-4 text-brand-forest" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
										</svg>
									</span>
								{/if}
							</div>
							<input id="utility-upload" type="file" accept=".jpg,.jpeg,.png,.pdf" onchange={(e) => handleFileChange(e, 'utility')} class="hidden" />
							{#if utilityBillFile}
								<p class="text-sm text-brand-forest font-medium mb-3">✓ {utilityBillFile.name} ({formatFileSize(utilityBillFile.size)})</p>
							{/if}
							<div class="flex gap-3">
								<button type="button" onclick={() => triggerCamera('utility-upload')} class="flex-1 flex items-center justify-center gap-2 py-3 px-4 bg-brand-navy text-white rounded-xl text-sm font-medium hover:bg-brand-navy-light transition-colors">
									<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
									</svg>
									{t(lang, 'apply.step3.takePhoto')}
								</button>
								<button type="button" onclick={() => triggerFileUpload('utility-upload')} class="flex-1 flex items-center justify-center gap-2 py-3 px-4 bg-brand-warm-gray text-brand-charcoal rounded-xl text-sm font-medium hover:bg-brand-warm-gray transition-colors border border-brand-border">
									<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
									</svg>
									{t(lang, 'apply.step3.uploadFile')}
								</button>
							</div>
						</div>

						{#if requiresLalpurja}
							<div class="border-2 border-dashed {lalpurjaFile ? 'border-brand-forest bg-brand-forest/5' : 'border-brand-gold/40 bg-brand-gold/5'} rounded-xl p-5 transition-all duration-200">
								<div class="flex items-center justify-between mb-3">
									<div>
										<p class="font-medium text-brand-charcoal text-sm">
											{t(lang, 'apply.step3.lalpurja')}
										</p>
										<p class="text-xs text-brand-charcoal/50 mt-0.5">{t(lang, 'apply.step3.lalpurjaHint')}</p>
									</div>
									{#if lalpurjaFile}
										<span class="w-8 h-8 bg-brand-forest/10 rounded-full flex items-center justify-center">
											<svg class="w-4 h-4 text-brand-forest" fill="none" stroke="currentColor" viewBox="0 0 24 24">
												<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
											</svg>
										</span>
									{/if}
								</div>
								<input id="lalpurja-upload" type="file" accept=".jpg,.jpeg,.png,.pdf" onchange={(e) => handleFileChange(e, 'lalpurja')} class="hidden" />
								{#if lalpurjaFile}
									<p class="text-sm text-brand-forest font-medium mb-3">✓ {lalpurjaFile.name} ({formatFileSize(lalpurjaFile.size)})</p>
								{/if}
								<div class="flex gap-3">
									<button type="button" onclick={() => triggerCamera('lalpurja-upload')} class="flex-1 flex items-center justify-center gap-2 py-3 px-4 bg-brand-navy text-white rounded-xl text-sm font-medium hover:bg-brand-navy-light transition-colors">
										<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
										</svg>
										{t(lang, 'apply.step3.takePhoto')}
									</button>
									<button type="button" onclick={() => triggerFileUpload('lalpurja-upload')} class="flex-1 flex items-center justify-center gap-2 py-3 px-4 bg-brand-warm-gray text-brand-charcoal rounded-xl text-sm font-medium hover:bg-brand-warm-gray transition-colors border border-brand-border">
										<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
										</svg>
										{t(lang, 'apply.step3.uploadFile')}
									</button>
								</div>
							</div>
						{/if}

						{#if showCooperativeUpload}
							<div class="border-2 border-dashed {cooperativeRecordsFile ? 'border-brand-forest bg-brand-forest/5' : 'border-brand-border bg-white'} rounded-xl p-5 transition-all duration-200">
								<div class="flex items-center justify-between mb-3">
									<div>
										<p class="font-medium text-brand-charcoal text-sm">
											{t(lang, 'apply.step3.cooperative')}
										</p>
										<p class="text-xs text-brand-charcoal/50 mt-0.5">{t(lang, 'apply.step3.cooperativeHint')}</p>
									</div>
									{#if cooperativeRecordsFile}
										<span class="w-8 h-8 bg-brand-forest/10 rounded-full flex items-center justify-center">
											<svg class="w-4 h-4 text-brand-forest" fill="none" stroke="currentColor" viewBox="0 0 24 24">
												<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
											</svg>
										</span>
									{/if}
								</div>
								<input id="cooperative-upload" type="file" accept=".jpg,.jpeg,.png,.pdf,.csv" onchange={(e) => handleFileChange(e, 'cooperative')} class="hidden" />
								{#if cooperativeRecordsFile}
									<p class="text-sm text-brand-forest font-medium mb-3">✓ {cooperativeRecordsFile.name} ({formatFileSize(cooperativeRecordsFile.size)})</p>
								{/if}
								<div class="flex gap-3">
									<button type="button" onclick={() => triggerCamera('cooperative-upload')} class="flex-1 flex items-center justify-center gap-2 py-3 px-4 bg-brand-navy text-white rounded-xl text-sm font-medium hover:bg-brand-navy-light transition-colors">
										<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
										</svg>
										{t(lang, 'apply.step3.takePhoto')}
									</button>
									<button type="button" onclick={() => triggerFileUpload('cooperative-upload')} class="flex-1 flex items-center justify-center gap-2 py-3 px-4 bg-brand-warm-gray text-brand-charcoal rounded-xl text-sm font-medium hover:bg-brand-warm-gray transition-colors border border-brand-border">
										<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
										</svg>
										{t(lang, 'apply.step3.uploadFile')}
									</button>
								</div>
							</div>
						{/if}

						{#if showRemittanceUpload}
							<div class="border-2 border-dashed {remittanceReceiptsFile ? 'border-brand-forest bg-brand-forest/5' : 'border-brand-border bg-white'} rounded-xl p-5 transition-all duration-200">
								<div class="flex items-center justify-between mb-3">
									<div>
										<p class="font-medium text-brand-charcoal text-sm">
											{t(lang, 'apply.step3.remittance')}
										</p>
										<p class="text-xs text-brand-charcoal/50 mt-0.5">{t(lang, 'apply.step3.remittanceHint')}</p>
									</div>
									{#if remittanceReceiptsFile}
										<span class="w-8 h-8 bg-brand-forest/10 rounded-full flex items-center justify-center">
											<svg class="w-4 h-4 text-brand-forest" fill="none" stroke="currentColor" viewBox="0 0 24 24">
												<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
											</svg>
										</span>
									{/if}
								</div>
								<input id="remittance-upload" type="file" accept=".jpg,.jpeg,.png,.pdf,.csv" onchange={(e) => handleFileChange(e, 'remittance')} class="hidden" />
								{#if remittanceReceiptsFile}
									<p class="text-sm text-brand-forest font-medium mb-3">✓ {remittanceReceiptsFile.name} ({formatFileSize(remittanceReceiptsFile.size)})</p>
								{/if}
								<button type="button" onclick={() => triggerFileUpload('remittance-upload')} class="w-full flex items-center justify-center gap-2 py-3 px-4 bg-brand-warm-gray text-brand-charcoal rounded-xl text-sm font-medium hover:bg-brand-warm-gray transition-colors border border-brand-border">
									<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
									</svg>
									{t(lang, 'apply.step3.uploadReceipts')}
								</button>
							</div>
						{/if}
					</div>
				</Card>
				{/if}

				<div class="flex justify-between mt-6 gap-4">
					{#if step > 1}
						<Button variant="secondary" size="lg" onclick={prevStep}>
							<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
							</svg>
							{t(lang, 'apply.back')}
						</Button>
					{:else}
						<div></div>
					{/if}

					{#if step < 3}
						<Button variant="primary" size="lg" onclick={nextStep} class="flex-1 sm:flex-none">
							{t(lang, 'apply.continue')}
							<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
							</svg>
						</Button>
					{:else}
						<Button type="submit" variant="success" size="lg" {loading} class="flex-1 sm:flex-none">
							{#if !loading}
								<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
								</svg>
							{/if}
							{t(lang, 'apply.submit')}
						</Button>
					{/if}
				</div>
			</form>
		{/if}
		{/if}
	</main>
</div>
