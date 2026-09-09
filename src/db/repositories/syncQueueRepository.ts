import type { CaseId } from '@/types';
import { nowIso } from '@/utils/date';
import { newId } from '@/utils/id';

import { getDatabase } from '../client';
import type { CountRow, SyncQueueRow } from '../rows';

export type SyncOperation = 'UPLOAD_CASE';
export type SyncEntryState = 'PENDING' | 'IN_FLIGHT' | 'FAILED' | 'COMPLETED';

export interface SyncQueueEntry {
  id: string;
  caseId: CaseId;
  operation: SyncOperation;
  state: SyncEntryState;
  attempts: number;
  lastError: string | null;
  nextRetryAt: string | null;
  enqueuedAt: string;
  updatedAt: string;
}

/**
 * Durable outbox for cases awaiting upload.
 *
 * `case_id` carries a UNIQUE constraint and enqueue is an upsert, which is what
 * makes duplicate prevention structural rather than a race the worker has to
 * win: re-saving a case that is already queued updates the existing entry
 * instead of adding a second one.
 */
export interface SyncQueueRepository {
  enqueue(caseId: CaseId, operation?: SyncOperation): Promise<SyncQueueEntry>;
  /** Entries eligible to run now: pending, and past any backoff deadline. */
  claimable(now?: string, limit?: number): Promise<SyncQueueEntry[]>;
  markInFlight(id: string): Promise<void>;
  markCompleted(id: string): Promise<void>;
  markFailed(id: string, error: string, nextRetryAt: string | null): Promise<void>;
  pendingCount(): Promise<number>;
  failedCount(): Promise<number>;
  listAll(): Promise<SyncQueueEntry[]>;
  /** Returns any entry stranded IN_FLIGHT by a crash back to PENDING. */
  recoverStranded(): Promise<number>;
  clearCompleted(): Promise<void>;
}

function toEntry(row: SyncQueueRow): SyncQueueEntry {
  return {
    id: row.id,
    caseId: row.case_id,
    operation: row.operation as SyncOperation,
    state: row.state as SyncEntryState,
    attempts: row.attempts,
    lastError: row.last_error,
    nextRetryAt: row.next_retry_at,
    enqueuedAt: row.enqueued_at,
    updatedAt: row.updated_at,
  };
}

class SqliteSyncQueueRepository implements SyncQueueRepository {
  async enqueue(caseId: CaseId, operation: SyncOperation = 'UPLOAD_CASE'): Promise<SyncQueueEntry> {
    const db = await getDatabase();
    const timestamp = nowIso();
    await db.runAsync(
      `INSERT INTO sync_queue (id, case_id, operation, state, attempts, last_error, next_retry_at, enqueued_at, updated_at)
       VALUES (?,?,?,'PENDING',0,NULL,NULL,?,?)
       ON CONFLICT(case_id) DO UPDATE SET
         state = 'PENDING',
         operation = excluded.operation,
         last_error = NULL,
         next_retry_at = NULL,
         updated_at = excluded.updated_at`,
      [newId(), caseId, operation, timestamp, timestamp],
    );
    const row = await db.getFirstAsync<SyncQueueRow>('SELECT * FROM sync_queue WHERE case_id = ?', [
      caseId,
    ]);
    if (!row) throw new Error('Sync entry vanished immediately after enqueue');
    return toEntry(row);
  }

  async claimable(now: string = nowIso(), limit = 10): Promise<SyncQueueEntry[]> {
    const db = await getDatabase();
    const rows = await db.getAllAsync<SyncQueueRow>(
      `SELECT * FROM sync_queue
       WHERE state IN ('PENDING','FAILED')
         AND (next_retry_at IS NULL OR next_retry_at <= ?)
       ORDER BY enqueued_at ASC
       LIMIT ?`,
      [now, limit],
    );
    return rows.map(toEntry);
  }

  async markInFlight(id: string): Promise<void> {
    const db = await getDatabase();
    await db.runAsync("UPDATE sync_queue SET state = 'IN_FLIGHT', updated_at = ? WHERE id = ?", [
      nowIso(),
      id,
    ]);
  }

  async markCompleted(id: string): Promise<void> {
    const db = await getDatabase();
    await db.runAsync(
      "UPDATE sync_queue SET state = 'COMPLETED', last_error = NULL, next_retry_at = NULL, updated_at = ? WHERE id = ?",
      [nowIso(), id],
    );
  }

  async markFailed(id: string, error: string, nextRetryAt: string | null): Promise<void> {
    const db = await getDatabase();
    await db.runAsync(
      `UPDATE sync_queue SET
         state = 'FAILED',
         attempts = attempts + 1,
         last_error = ?,
         next_retry_at = ?,
         updated_at = ?
       WHERE id = ?`,
      [error, nextRetryAt, nowIso(), id],
    );
  }

  async pendingCount(): Promise<number> {
    const db = await getDatabase();
    const row = await db.getFirstAsync<CountRow>(
      "SELECT COUNT(*) AS count FROM sync_queue WHERE state IN ('PENDING','FAILED','IN_FLIGHT')",
    );
    return row?.count ?? 0;
  }

  async failedCount(): Promise<number> {
    const db = await getDatabase();
    const row = await db.getFirstAsync<CountRow>(
      "SELECT COUNT(*) AS count FROM sync_queue WHERE state = 'FAILED'",
    );
    return row?.count ?? 0;
  }

  async listAll(): Promise<SyncQueueEntry[]> {
    const db = await getDatabase();
    const rows = await db.getAllAsync<SyncQueueRow>(
      'SELECT * FROM sync_queue ORDER BY enqueued_at DESC',
    );
    return rows.map(toEntry);
  }

  async recoverStranded(): Promise<number> {
    const db = await getDatabase();
    const result = await db.runAsync(
      "UPDATE sync_queue SET state = 'PENDING', updated_at = ? WHERE state = 'IN_FLIGHT'",
      [nowIso()],
    );
    return result.changes;
  }

  async clearCompleted(): Promise<void> {
    const db = await getDatabase();
    await db.runAsync("DELETE FROM sync_queue WHERE state = 'COMPLETED'");
  }
}

export const syncQueueRepository: SyncQueueRepository = new SqliteSyncQueueRepository();
