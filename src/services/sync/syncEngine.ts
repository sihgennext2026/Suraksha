import { auditRepository, caseRepository, syncQueueRepository } from '@/db';
import type { CaseId } from '@/types';
import { nowIso } from '@/utils/date';
import { toServiceFailure } from '@/utils/errors';
import { createLogger } from '@/utils/logger';

import { remoteCaseApi, type RemoteCaseApi } from './remoteApi';

const log = createLogger('sync');

/** Exponential backoff, capped so a long outage does not push retries hours out. */
const BACKOFF_SCHEDULE_MS = [15_000, 60_000, 300_000, 900_000] as const;
const MAX_ATTEMPTS = 6;

export interface SyncRunSummary {
  attempted: number;
  succeeded: number;
  failed: number;
  /** Set when the run was skipped because the device is offline. */
  skippedOffline: boolean;
}

export interface SyncEngine {
  /** Queues a case for upload. Safe to call repeatedly for the same case. */
  enqueue(caseId: CaseId): Promise<void>;
  /** Processes everything eligible. Resolves when the queue is drained or stalls. */
  run(options?: { online: boolean; actorId: string; actorName: string }): Promise<SyncRunSummary>;
  pendingCount(): Promise<number>;
  failedCount(): Promise<number>;
  /** Clears any backoff so a manual retry runs immediately. */
  retryNow(): Promise<void>;
}

function backoffFor(attempts: number): string {
  const index = Math.min(attempts, BACKOFF_SCHEDULE_MS.length - 1);
  const delayMs = BACKOFF_SCHEDULE_MS[index] as number;
  return new Date(Date.now() + delayMs).toISOString();
}

/**
 * The synchronisation worker.
 *
 * Ordering of operations is deliberate and matters for correctness:
 *
 *  1. The queue entry is marked IN_FLIGHT before the upload starts, so a crash
 *     mid-upload leaves a trace rather than a silently dropped case. Stranded
 *     entries are recovered to PENDING at startup.
 *  2. The case row is only marked SYNCED after the server has acknowledged it.
 *     A case is never shown as safely uploaded on the strength of a request the
 *     device merely sent.
 *  3. Failures keep the case on the device and schedule a backoff. Nothing is
 *     ever deleted locally as a consequence of a sync attempt.
 */
class QueueSyncEngine implements SyncEngine {
  private running = false;

  constructor(private readonly api: RemoteCaseApi) {}

  async enqueue(caseId: CaseId): Promise<void> {
    await syncQueueRepository.enqueue(caseId);
    await caseRepository.updateSync(caseId, 'PENDING');
  }

  async run(
    options: { online: boolean; actorId: string; actorName: string } = {
      online: true,
      actorId: 'system',
      actorName: 'System',
    },
  ): Promise<SyncRunSummary> {
    const summary: SyncRunSummary = {
      attempted: 0,
      succeeded: 0,
      failed: 0,
      skippedOffline: false,
    };

    if (!options.online) {
      summary.skippedOffline = true;
      return summary;
    }

    // A second concurrent run would race the same queue entries; the caller
    // simply gets an empty summary and the in-progress run continues.
    if (this.running) return summary;
    this.running = true;

    try {
      await syncQueueRepository.recoverStranded();
      const entries = await syncQueueRepository.claimable(nowIso(), 10);

      for (const entry of entries) {
        summary.attempted += 1;

        const screeningCase = await caseRepository.findById(entry.caseId);
        if (!screeningCase) {
          // The case was purged locally; the queue entry has nothing to upload.
          await syncQueueRepository.markCompleted(entry.id);
          continue;
        }

        await syncQueueRepository.markInFlight(entry.id);
        await caseRepository.updateSync(entry.caseId, 'SYNCING');

        try {
          await this.api.uploadCase(screeningCase);
          await syncQueueRepository.markCompleted(entry.id);
          await caseRepository.updateSync(entry.caseId, 'SYNCED');
          await auditRepository.record({
            caseId: entry.caseId,
            type: 'CASE_SYNCED',
            description: 'Case uploaded to the central service',
            actorId: options.actorId,
            actorName: options.actorName,
            metadata: { attempts: entry.attempts + 1 },
          });
          summary.succeeded += 1;
        } catch (error) {
          const serviceFailure = toServiceFailure(error);
          const attempts = entry.attempts + 1;
          const exhausted = attempts >= MAX_ATTEMPTS;

          await syncQueueRepository.markFailed(
            entry.id,
            serviceFailure.message,
            exhausted ? null : backoffFor(attempts),
          );
          await caseRepository.updateSync(entry.caseId, 'FAILED', serviceFailure.message);
          await auditRepository.record({
            caseId: entry.caseId,
            type: 'SYNC_FAILED',
            description: exhausted
              ? 'Upload failed and will not be retried automatically'
              : 'Upload failed and will be retried',
            actorId: options.actorId,
            actorName: options.actorName,
            metadata: { attempts, retryable: !exhausted },
          });
          summary.failed += 1;
          log.warn('Case upload failed', { caseId: entry.caseId, attempts });
        }
      }

      await syncQueueRepository.clearCompleted();
      return summary;
    } finally {
      this.running = false;
    }
  }

  async pendingCount(): Promise<number> {
    return syncQueueRepository.pendingCount();
  }

  async failedCount(): Promise<number> {
    return syncQueueRepository.failedCount();
  }

  async retryNow(): Promise<void> {
    const entries = await syncQueueRepository.listAll();
    for (const entry of entries) {
      if (entry.state === 'FAILED') {
        // Re-enqueuing resets state and clears the backoff deadline.
        await syncQueueRepository.enqueue(entry.caseId, entry.operation);
        await caseRepository.updateSync(entry.caseId, 'PENDING');
      }
    }
  }
}

export const syncEngine: SyncEngine = new QueueSyncEngine(remoteCaseApi);
