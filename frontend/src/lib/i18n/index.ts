import en from './en.json';

type Lang = 'en' | 'ne';

function getNestedValue(obj: Record<string, any>, path: string): string | undefined {
	return path.split('.').reduce((current, key) => current?.[key], obj) as string | undefined;
}

export function t(lang: Lang, key: string): string {
	if (lang === 'en') {
		return getNestedValue(en, key) ?? key;
	}

	const value = getNestedValue(en, key);
	if (!value || typeof value !== 'string') return key;

	const neKey = key.endsWith('Ne') ? key : `${key}Ne`;
	const neValue = getNestedValue(en, neKey);
	return neValue ?? value;
}

export function tObj(lang: Lang, key: string): { value: string; label: string; ne: string }[] {
	const obj = getNestedValue(en, key) as Record<string, { en: string; ne: string; icon?: string }> | undefined;
	if (!obj) return [];
	return Object.entries(obj).map(([k, v]) => ({
		value: k,
		label: lang === 'en' ? `${v.en} (${v.ne})` : `${v.ne} (${v.en})`,
		ne: v.ne
	}));
}
