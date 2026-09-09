/** Formats a 0..1 score as a whole percentage, e.g. `91%`. */
export function formatPercent(value: number, fractionDigits = 0): string {
  const clamped = Math.min(1, Math.max(0, value));
  return `${(clamped * 100).toFixed(fractionDigits)}%`;
}

/** Formats a 0..100 risk score, e.g. `82`. */
export function formatScore(value: number): string {
  return String(Math.round(value));
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ['KB', 'MB', 'GB'];
  let value = bytes / 1024;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  return `${value.toFixed(value >= 10 ? 0 : 1)} ${units[unitIndex]}`;
}

export function formatDurationMs(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}

/** `KRISHNA RAJ` from `Krishna  raj`. Used for name fields read off documents. */
export function toDocumentCase(value: string): string {
  return value.trim().replace(/\s+/g, ' ').toUpperCase();
}

/** Splits an MRZ line into fixed-width groups so it stays scannable by eye. */
export function groupMrzLine(line: string, groupSize = 10): string[] {
  const groups: string[] = [];
  for (let i = 0; i < line.length; i += groupSize) {
    groups.push(line.slice(i, i + groupSize));
  }
  return groups;
}

export function pluralise(count: number, singular: string, plural?: string): string {
  return count === 1 ? singular : (plural ?? `${singular}s`);
}
