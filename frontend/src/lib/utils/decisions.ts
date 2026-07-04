export function getDecisionBadgeVariant(decision?: string): 'success' | 'warning' | 'danger' | 'info' | 'default' {
	if (!decision || decision === 'PENDING') return 'info';
	if (decision === 'APPROVE') return 'success';
	if (decision === 'MODIFY') return 'warning';
	if (decision === 'REJECT') return 'danger';
	return 'default';
}

export function getDecisionColor(decision?: string): string {
	if (!decision || decision === 'PENDING') return 'bg-brand-gold';
	if (decision === 'APPROVE') return 'bg-brand-forest';
	if (decision === 'REJECT') return 'bg-brand-burgundy';
	if (decision === 'MODIFY') return 'bg-brand-gold';
	return 'bg-brand-navy';
}

export function getDecisionBg(decision?: string): string {
	if (!decision || decision === 'PENDING') return 'bg-brand-gold/10 border-brand-gold/20';
	if (decision === 'APPROVE') return 'bg-brand-forest/10 border-brand-forest/20';
	if (decision === 'REJECT') return 'bg-brand-burgundy/10 border-brand-burgundy/20';
	if (decision === 'MODIFY') return 'bg-brand-gold/10 border-brand-gold/20';
	return 'bg-brand-navy/10 border-brand-navy/20';
}

export function getDecisionIcon(decision?: string): string {
	if (!decision || decision === 'PENDING') return '⏳';
	if (decision === 'APPROVE') return '✅';
	if (decision === 'REJECT') return '❌';
	if (decision === 'MODIFY') return '⚠️';
	return '📋';
}

export function getDecisionText(decision?: string): { en: string; ne: string } {
	if (!decision || decision === 'PENDING') return { en: 'Pending Review', ne: 'समीक्षा अपेक्षित' };
	if (decision === 'APPROVE') return { en: 'Approved', ne: 'स्वीकृत' };
	if (decision === 'REJECT') return { en: 'Not Approved', ne: 'स्वीकृत भएन' };
	if (decision === 'MODIFY') return { en: 'Conditionally Approved', ne: 'सशर्त स्वीकृत' };
	return { en: decision, ne: decision };
}

export function getScoreColor(score?: number): string {
	if (!score) return 'text-brand-charcoal/40';
	if (score >= 700) return 'text-brand-forest';
	if (score >= 500) return 'text-brand-gold';
	return 'text-brand-burgundy';
}

export function getScoreBgColor(score?: number): string {
	if (!score) return 'bg-brand-charcoal/40';
	if (score >= 700) return 'bg-brand-forest';
	if (score >= 500) return 'bg-brand-gold';
	return 'bg-brand-burgundy';
}
