import type { IsoDate, IsoDateTime } from '@/types';

const MONTHS = [
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
] as const;

export function nowIso(): IsoDateTime {
  return new Date().toISOString();
}

/** `12 May 2003`. Returns the raw input when it is not a parseable date. */
export function formatDate(value: IsoDate | IsoDateTime | null | undefined): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return `${String(date.getUTCDate()).padStart(2, '0')} ${MONTHS[date.getUTCMonth()]} ${date.getUTCFullYear()}`;
}

/** `24 Aug 2026, 14:32`. Rendered in local time — officers work in local time. */
export function formatDateTime(value: IsoDateTime | null | undefined): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const day = String(date.getDate()).padStart(2, '0');
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  return `${day} ${MONTHS[date.getMonth()]} ${date.getFullYear()}, ${hours}:${minutes}`;
}

/** `14:32:07` — used in the audit timeline where ordering matters. */
export function formatTimeWithSeconds(value: IsoDateTime | null | undefined): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return [date.getHours(), date.getMinutes(), date.getSeconds()]
    .map((part) => String(part).padStart(2, '0'))
    .join(':');
}

/** `2 hours ago`, `just now`. Coarse by design — precision lives in the audit. */
export function formatRelative(value: IsoDateTime | null | undefined, now = Date.now()): string {
  if (!value) return '—';
  const then = new Date(value).getTime();
  if (Number.isNaN(then)) return '—';
  const seconds = Math.round((now - then) / 1000);
  if (seconds < 45) return 'just now';
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} ${hours === 1 ? 'hour' : 'hours'} ago`;
  const days = Math.round(hours / 24);
  if (days < 7) return `${days} ${days === 1 ? 'day' : 'days'} ago`;
  return formatDate(value);
}

/** Whole years between a date of birth and a reference date. */
export function yearsBetween(from: IsoDate, to: Date = new Date()): number | null {
  const start = new Date(from);
  if (Number.isNaN(start.getTime())) return null;
  let years = to.getUTCFullYear() - start.getUTCFullYear();
  const monthDelta = to.getUTCMonth() - start.getUTCMonth();
  if (monthDelta < 0 || (monthDelta === 0 && to.getUTCDate() < start.getUTCDate())) {
    years -= 1;
  }
  return years;
}

export function isPast(value: IsoDate | IsoDateTime, reference: Date = new Date()): boolean {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return false;
  return date.getTime() < reference.getTime();
}
