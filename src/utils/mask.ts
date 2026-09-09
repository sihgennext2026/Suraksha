/**
 * Document numbers are personal data. Lists, logs, and sync payload summaries
 * only ever carry a masked form; the full value stays in the encrypted case
 * record and is shown solely on the OCR screen an officer opened deliberately.
 */
export function maskDocumentNumber(value: string | null | undefined): string | null {
  if (!value) return null;
  const trimmed = value.replace(/\s+/g, '');
  if (trimmed.length <= 4) return '•'.repeat(trimmed.length);
  return `${'•'.repeat(Math.max(2, trimmed.length - 4))}${trimmed.slice(-4)}`;
}

/** `K••••• R••` — enough to recognise a case, not enough to identify a person. */
export function maskName(value: string | null | undefined): string | null {
  if (!value) return null;
  return value
    .trim()
    .split(/\s+/)
    .map((part) => (part.length <= 1 ? part : `${part[0]}${'•'.repeat(part.length - 1)}`))
    .join(' ');
}
