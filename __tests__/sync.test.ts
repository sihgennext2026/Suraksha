import { createTestDatabase, type TestDatabase } from './support/sqliteTestDatabase';

/**
 * Synchronisation behaviour.
 *
 * The properties under test are the ones an officer relies on without being
 * able to see them: a case is never reported as uploaded before the server has
 * accepted it, a failure never removes anything locally, a queue survives a
 * crash, and being offline is a no-op rather than an error.
 */

let mockDatabase: TestDatabase;

jest.mock('expo-sqlite', () => ({
  openDatabaseAsync: jest.fn(async () => mockDatabase),
}));

const mockUploadCase = jest.fn();
jest.mock('@/services/sync/remoteApi', () => ({
  remoteCaseApi: {
    uploadCase: (...args: unknown[]) => mockUploadCase(...args),
  },
}));

import {
  auditRepository,
  caseRepository,
  syncQueueRepository,
  __resetDatabaseForTests,
} from '@/db';
import { createInitialStages } from '@/stores/screeningStore';
import { syncEngine } from '@/services/sync/syncEngine';
import { ScreeningServiceError, type ScreeningCase } from '@/types';

const ACTOR = { actorId: 'SSB4471', actorName: 'Krishna Raj' };

function buildCase(id: string): ScreeningCase {
  return {
    id,
    status: 'COMPLETED',
    documentType: 'passport',
    document: null,
    person: null,
    stages: createInitialStages(),
    result: null,
    decision: null,
    sync: {
      state: 'LOCAL_ONLY',
      lastAttemptAt: null,
      lastSyncedAt: null,
      attempts: 0,
      lastError: null,
    },
    officerId: 'SSB4471',
    officerName: 'Krishna Raj',
    unit: '41 Bn SSB',
    postName: 'Raxaul ICP',
    createdAt: '2026-08-24T10:00:00.000Z',
    updatedAt: '2026-08-24T10:00:00.000Z',
  };
}

beforeEach(async () => {
  mockDatabase = createTestDatabase();
  __resetDatabaseForTests(null);
  mockUploadCase.mockReset();
  mockUploadCase.mockResolvedValue({ remoteId: 'REM-1', acceptedAt: '2026-08-24T10:03:00.000Z' });
});

afterEach(async () => {
  await mockDatabase.closeAsync();
});

describe('sync engine', () => {
  it('marks a case synced only after the server accepts it', async () => {
    await caseRepository.save(buildCase('SSB-2026-0001'));
    await syncEngine.enqueue('SSB-2026-0001');

    const queued = await caseRepository.findById('SSB-2026-0001');
    expect(queued?.sync.state).toBe('PENDING');

    const summary = await syncEngine.run({ online: true, ...ACTOR });
    expect(summary).toMatchObject({ attempted: 1, succeeded: 1, failed: 0 });

    const uploaded = await caseRepository.findById('SSB-2026-0001');
    expect(uploaded?.sync.state).toBe('SYNCED');
    expect(uploaded?.sync.lastSyncedAt).not.toBeNull();
    expect(mockUploadCase).toHaveBeenCalledTimes(1);
  });

  it('does nothing at all while the device is offline', async () => {
    await caseRepository.save(buildCase('SSB-2026-0001'));
    await syncEngine.enqueue('SSB-2026-0001');

    const summary = await syncEngine.run({ online: false, ...ACTOR });

    expect(summary.skippedOffline).toBe(true);
    expect(summary.attempted).toBe(0);
    expect(mockUploadCase).not.toHaveBeenCalled();
    // The case stays queued rather than being marked failed: offline is not an
    // error condition in this application.
    const stored = await caseRepository.findById('SSB-2026-0001');
    expect(stored?.sync.state).toBe('PENDING');
  });

  it('keeps a failed case on the device and schedules a retry', async () => {
    mockUploadCase.mockRejectedValue(
      new ScreeningServiceError({
        code: 'UPLOAD_REJECTED',
        message: 'The central service did not accept this case.',
        retryable: true,
      }),
    );

    await caseRepository.save(buildCase('SSB-2026-0001'));
    await syncEngine.enqueue('SSB-2026-0001');
    const summary = await syncEngine.run({ online: true, ...ACTOR });

    expect(summary).toMatchObject({ attempted: 1, succeeded: 0, failed: 1 });

    const stored = await caseRepository.findById('SSB-2026-0001');
    expect(stored).not.toBeNull();
    expect(stored?.sync.state).toBe('FAILED');
    expect(stored?.sync.lastError).toContain('did not accept');

    const [entry] = await syncQueueRepository.listAll();
    expect(entry?.state).toBe('FAILED');
    expect(entry?.attempts).toBe(1);
    expect(entry?.nextRetryAt).not.toBeNull();
  });

  it('holds a failed case behind its backoff until a manual retry clears it', async () => {
    mockUploadCase.mockRejectedValueOnce(
      new ScreeningServiceError({ code: 'X', message: 'Rejected', retryable: true }),
    );

    await caseRepository.save(buildCase('SSB-2026-0001'));
    await syncEngine.enqueue('SSB-2026-0001');
    await syncEngine.run({ online: true, ...ACTOR });

    // A second run inside the backoff window must not re-attempt.
    const blocked = await syncEngine.run({ online: true, ...ACTOR });
    expect(blocked.attempted).toBe(0);

    await syncEngine.retryNow();
    const retried = await syncEngine.run({ online: true, ...ACTOR });
    expect(retried.succeeded).toBe(1);
    expect((await caseRepository.findById('SSB-2026-0001'))?.sync.state).toBe('SYNCED');
  });

  it('never uploads the same case twice from repeated enqueues', async () => {
    await caseRepository.save(buildCase('SSB-2026-0001'));
    await syncEngine.enqueue('SSB-2026-0001');
    await syncEngine.enqueue('SSB-2026-0001');
    await syncEngine.enqueue('SSB-2026-0001');

    const summary = await syncEngine.run({ online: true, ...ACTOR });
    expect(summary.attempted).toBe(1);
    expect(mockUploadCase).toHaveBeenCalledTimes(1);
  });

  it('completes a queue entry whose case has been purged locally', async () => {
    await caseRepository.save(buildCase('SSB-2026-0001'));
    await syncEngine.enqueue('SSB-2026-0001');
    await caseRepository.remove('SSB-2026-0001');

    const summary = await syncEngine.run({ online: true, ...ACTOR });
    expect(mockUploadCase).not.toHaveBeenCalled();
    expect(summary.failed).toBe(0);
  });

  it('records the outcome of every attempt in the audit trail', async () => {
    await caseRepository.save(buildCase('SSB-2026-0001'));
    await syncEngine.enqueue('SSB-2026-0001');
    await syncEngine.run({ online: true, ...ACTOR });

    const events = await auditRepository.listForCase('SSB-2026-0001');
    expect(events.map((event) => event.type)).toContain('CASE_SYNCED');
  });

  it('drains several queued cases in one run', async () => {
    for (const id of ['SSB-2026-0001', 'SSB-2026-0002', 'SSB-2026-0003']) {
      await caseRepository.save(buildCase(id));
      await syncEngine.enqueue(id);
    }

    const summary = await syncEngine.run({ online: true, ...ACTOR });
    expect(summary.attempted).toBe(3);
    expect(summary.succeeded).toBe(3);
    expect(await syncEngine.pendingCount()).toBe(0);
  });
});
