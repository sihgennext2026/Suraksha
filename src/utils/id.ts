import { randomUUID } from 'expo-crypto';

/** Opaque unique identifier for rows that are never shown to officers. */
export function newId(): string {
  return randomUUID();
}

/**
 * Human-readable case reference, e.g. `SSB-2026-0842`. The sequence is per year
 * and comes from the local database, so references stay meaningful offline.
 */
export function formatCaseReference(year: number, sequence: number): string {
  return `SSB-${year}-${String(sequence).padStart(4, '0')}`;
}
