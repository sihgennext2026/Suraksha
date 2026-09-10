import { openDatabaseAsync, type SQLiteDatabase } from 'expo-sqlite';

import { DATABASE_NAME } from '@/constants/storage';
import { createLogger } from '@/utils/logger';

import { LATEST_SCHEMA_VERSION, MIGRATIONS } from './migrations';

const log = createLogger('db');

let databasePromise: Promise<SQLiteDatabase> | null = null;

/**
 * Opens the database once per process and applies any outstanding migrations.
 *
 * Concurrent callers share a single in-flight promise, so the migration runner
 * cannot execute twice if several repositories initialise at the same moment.
 */
export function getDatabase(): Promise<SQLiteDatabase> {
  databasePromise ??= open().catch((error: unknown) => {
    // Drop the cached promise on failure. A rejected promise left in place
    // would be handed to every later caller for the life of the process, so a
    // fault a retry could clear — a lock held by a dying write, a transient
    // filesystem error — would instead leave storage unusable until the app was
    // reinstalled, taking the officer's queued cases with it.
    databasePromise = null;
    throw error;
  });
  return databasePromise;
}

async function open(): Promise<SQLiteDatabase> {
  const db = await openDatabaseAsync(DATABASE_NAME);
  // WAL keeps reads from blocking the capture flow while a case is being written.
  await db.execAsync('PRAGMA journal_mode = WAL;');
  await db.execAsync('PRAGMA foreign_keys = ON;');
  await migrate(db);
  return db;
}

async function migrate(db: SQLiteDatabase): Promise<void> {
  const row = await db.getFirstAsync<{ user_version: number }>('PRAGMA user_version');
  const current = row?.user_version ?? 0;
  if (current >= LATEST_SCHEMA_VERSION) return;

  for (const migration of MIGRATIONS) {
    if (migration.version <= current) continue;
    log.info('Applying migration', { version: migration.version, name: migration.name });
    // The schema change and the version bump that records it commit together.
    // Applied separately, a failure between them would leave the database
    // migrated but still advertising the older version, and the next launch
    // would replay a migration against a schema that had already moved.
    await db.withTransactionAsync(async () => {
      await migration.up(db);
      // PRAGMA does not accept bound parameters, and the value is an integer
      // literal from our own migration list rather than user input.
      await db.execAsync(`PRAGMA user_version = ${migration.version}`);
    });
  }
}

/** Test-only hook so a suite can point at a fresh in-memory database. */
export function __resetDatabaseForTests(next: Promise<SQLiteDatabase> | null): void {
  databasePromise = next;
}

/** Parses a JSON payload column, returning null when the column is unusable. */
export function parsePayload<T>(raw: string | null | undefined): T | null {
  if (!raw) return null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    // A corrupt payload must not take down the cases list — the row still
    // renders from its summary columns, just without the detail view.
    log.warn('Discarding unreadable payload column');
    return null;
  }
}

export const toDbBool = (value: boolean): number => (value ? 1 : 0);
export const fromDbBool = (value: number | null | undefined): boolean => value === 1;
