export function formatAmount(amount?: number): string {
	if (!amount) return '—';
	return new Intl.NumberFormat('en-IN').format(amount);
}

export function formatFileSize(bytes: number): string {
	if (bytes < 1024) return bytes + ' B';
	if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
	return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

export function formatTimestamp(ts: string): string {
	const date = new Date(ts);
	return date.toLocaleString('en-US', {
		hour: '2-digit',
		minute: '2-digit',
		second: '2-digit',
		hour12: true
	});
}

export function formatDate(ts: string): string {
	const date = new Date(ts);
	return date.toLocaleString('en-US', {
		year: 'numeric',
		month: 'short',
		day: 'numeric'
	});
}

export function formatJson(obj: unknown, indent: number = 0): string {
	if (typeof obj !== 'object' || obj === null) {
		return JSON.stringify(obj);
	}
	const spaces = '  '.repeat(indent);
	const innerSpaces = '  '.repeat(indent + 1);

	if (Array.isArray(obj)) {
		if (obj.length === 0) return '[]';
		const items = obj.map(item => `${innerSpaces}${formatJson(item, indent + 1)}`);
		return `[\n${items.join(',\n')}\n${spaces}]`;
	}

	const entries = Object.entries(obj);
	if (entries.length === 0) return '{}';
	const lines = entries.map(([key, value]) => `${innerSpaces}"${key}": ${formatJson(value, indent + 1)}`);
	return `{\n${lines.join(',\n')}\n${spaces}}`;
}
