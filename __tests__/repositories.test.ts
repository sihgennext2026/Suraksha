import { createTestDatabase, type TestDatabase } from './support/sqliteTestDatabase';

/**
 * Repository behaviour against a real SQLite engine.
 *
 * The schema under test is the one that ships: these suites run the actual
 * migration and then exercise the upserts, the cascade deletes, and the queries
 * the list and dashboard depend on.
 */

// Named `mock*` so the hoisted factory below is allowed to reference it.
let mockDatabase: TestDatabase;

jest.mock('expo-sqlite', () => ({
  openDatabaseAsync: jest.fn(async () => mockDatabase),
}));

import {
  getDatabase,
  auditRepository,
  caseRepository,
  syncQueueRepository,
  userRepository,
  __resetDatabaseForTests,
} from '@/db';
import { FIXTURE_RESULTS, buildCase, resultFor } from './support/caseFactory';

beforeEach(() => {
  mockDatabase = createTestDatabase();
  // Each suite gets a fresh database, so the migration runs from scratch every
  // time rather than being tested once against a warm connection.
  __resetDatabaseForTests(null);
});

afterEach(async () => {
  await mockDatabase.closeAsync();
});

describe('case repository', () => {
  it('applies the migration and round-trips a complete case', async () => {
    const original = buildCase();
    await caseRepository.save(original);

    const loaded = await caseRepository.findById(original.id);
    expect(loaded).not.toBeNull();
    expect(loaded?.id).toBe(original.id);
    expect(loaded?.documentType).toBe('passport');
    expect(loaded?.document?.image.uri).toBe('file:///cache/document.jpg');
    expect(loaded?.person?.image.uri).toBe('file:///cache/person.jpg');
    expect(loaded?.result?.ocr.result?.fields.length).toBeGreaterThan(0);
    expect(loaded?.result?.risk.result?.risk_level).toBe('LOW');
    // Stored verbatim: what comes back is what the service said.
    expect(loaded?.result).toEqual(original.result);
    expect(loaded?.stages).toHaveLength(8);
  });

  it('masks the document number in the summary rather than storing it whole', async () => {
    await caseRepository.save(buildCase());
    const [summary] = await caseRepository.listSummaries();

    expect(summary?.maskedDocumentNumber).toBe('••••1736');
    expect(summary?.maskedDocumentNumber).not.toContain('P482');
    expect(summary?.subjectName).toBe('ANIL KUMAR SHARMA');
  });

  it('updates rather than duplicates when the same case is saved twice', async () => {
    const original = buildCase();
    await caseRepository.save(original);
    await caseRepository.save({
      ...original,
      status: 'AWAITING_DECISION',
      result: resultFor(original.id, FIXTURE_RESULTS.tampered),
    });

    const summaries = await caseRepository.listSummaries();
    expect(summaries).toHaveLength(1);
    expect(summaries[0]?.status).toBe('AWAITING_DECISION');
    expect(summaries[0]?.riskLevel).toBe('HIGH');
    expect(summaries[0]?.riskScore).toBeGreaterThan(0);
  });

  it('allocates case references sequentially within a year', async () => {
    const first = await caseRepository.nextReference(2026);
    const second = await caseRepository.nextReference(2026);
    const otherYear = await caseRepository.nextReference(2027);

    expect(first).toBe('SSB-2026-0001');
    expect(second).toBe('SSB-2026-0002');
    expect(otherYear).toBe('SSB-2027-0001');
  });

  it('filters by risk, status and document type together', async () => {
    await caseRepository.save(buildCase({ id: 'SSB-2026-0001' }));
    await caseRepository.save(
      buildCase({
        id: 'SSB-2026-0002',
        status: 'AWAITING_DECISION',
        documentType: 'national_id',
        result: resultFor('SSB-2026-0002', FIXTURE_RESULTS.tampered),
      }),
    );

    const highRisk = await caseRepository.listSummaries({ riskLevel: ['HIGH'] });
    expect(highRisk.map((entry) => entry.id)).toEqual(['SSB-2026-0002']);

    const passports = await caseRepository.listSummaries({ documentType: ['passport'] });
    expect(passports.map((entry) => entry.id)).toEqual(['SSB-2026-0001']);

    const combined = await caseRepository.listSummaries({
      riskLevel: ['HIGH'],
      documentType: ['passport'],
    });
    expect(combined).toHaveLength(0);
  });

  it('searches by case reference and by masked document number', async () => {
    await caseRepository.save(buildCase({ id: 'SSB-2026-0042' }));

    expect(await caseRepository.listSummaries({ search: '0042' })).toHaveLength(1);
    expect(await caseRepository.listSummaries({ search: '1736' })).toHaveLength(1);
    expect(await caseRepository.listSummaries({ search: 'nothing' })).toHaveLength(0);
  });

  it('counts the caseload the dashboard reports', async () => {
    await caseRepository.save(buildCase({ id: 'SSB-2026-0001', status: 'CAPTURING' }));
    await caseRepository.save(buildCase({ id: 'SSB-2026-0002', status: 'AWAITING_DECISION' }));
    await caseRepository.save(
      buildCase({
        id: 'SSB-2026-0003',
        result: resultFor('SSB-2026-0003', FIXTURE_RESULTS.tampered),
      }),
    );

    const counts = await caseRepository.counts();
    expect(counts.total).toBe(3);
    expect(counts.active).toBe(1);
    expect(counts.awaitingDecision).toBe(1);
    expect(counts.highRisk).toBe(1);
  });

  it('records a decision and reads it back with the risk level as it stood', async () => {
    const withDecision = buildCase({
      decision: {
        id: 'dec-1',
        caseId: 'SSB-2026-0001',
        decision: 'HOLD',
        remarks: 'Subject could not explain the travel history.',
        officerId: 'SSB4471',
        officerName: 'Krishna Raj',
        decidedAt: '2026-08-24T10:05:00.000Z',
        riskLevelAtDecision: 'REVIEW',
        riskScoreAtDecision: 0.58,
        divergedFromRecommendation: true,
      },
    });
    await caseRepository.save(withDecision);

    const decision = await caseRepository.findDecision('SSB-2026-0001');
    expect(decision?.decision).toBe('HOLD');
    expect(decision?.divergedFromRecommendation).toBe(true);
    // The stored level is the one shown at the time, not one recomputed from
    // the current risk result.
    expect(decision?.riskLevelAtDecision).toBe('REVIEW');
    expect(decision?.riskScoreAtDecision).toBe(0.58);
  });

  it('tracks sync state transitions and counts failures', async () => {
    await caseRepository.save(buildCase());

    await caseRepository.updateSync('SSB-2026-0001', 'FAILED', 'Upload rejected');
    let loaded = await caseRepository.findById('SSB-2026-0001');
    expect(loaded?.sync.state).toBe('FAILED');
    expect(loaded?.sync.attempts).toBe(1);
    expect(loaded?.sync.lastError).toBe('Upload rejected');

    await caseRepository.updateSync('SSB-2026-0001', 'SYNCED');
    loaded = await caseRepository.findById('SSB-2026-0001');
    expect(loaded?.sync.state).toBe('SYNCED');
    expect(loaded?.sync.lastSyncedAt).not.toBeNull();
    // A success must not increment the failure counter.
    expect(loaded?.sync.attempts).toBe(1);
  });

  it('returns null for a case that is not held on the device', async () => {
    expect(await caseRepository.findById('SSB-2026-9999')).toBeNull();
  });
});

describe('audit repository', () => {
  it('keeps events in chronological order for a case', async () => {
    await caseRepository.save(buildCase());

    await auditRepository.record({
      caseId: 'SSB-2026-0001',
      type: 'CASE_CREATED',
      description: 'Case opened',
      actorId: 'SSB4471',
      actorName: 'Krishna Raj',
    });
    await auditRepository.record({
      caseId: 'SSB-2026-0001',
      type: 'OFFICER_DECISION',
      description: 'Officer cleared the subject',
      actorId: 'SSB4471',
      actorName: 'Krishna Raj',
      metadata: { decision: 'CLEAR' },
    });

    const events = await auditRepository.listForCase('SSB-2026-0001');
    expect(events).toHaveLength(2);
    expect(events[0]?.type).toBe('CASE_CREATED');
    expect(events[1]?.type).toBe('OFFICER_DECISION');
    expect(events[1]?.metadata.decision).toBe('CLEAR');
  });

  it('removes a case audit trail only when the case itself is purged', async () => {
    await caseRepository.save(buildCase());
    await auditRepository.record({
      caseId: 'SSB-2026-0001',
      type: 'CASE_CREATED',
      description: 'Case opened',
      actorId: 'SSB4471',
      actorName: 'Krishna Raj',
    });

    expect(await auditRepository.listForCase('SSB-2026-0001')).toHaveLength(1);
    await caseRepository.remove('SSB-2026-0001');
    expect(await auditRepository.listForCase('SSB-2026-0001')).toHaveLength(0);
  });
});

describe('sync queue repository', () => {
  beforeEach(async () => {
    await caseRepository.save(buildCase());
  });

  it('does not queue the same case twice', async () => {
    await syncQueueRepository.enqueue('SSB-2026-0001');
    await syncQueueRepository.enqueue('SSB-2026-0001');

    const entries = await syncQueueRepository.listAll();
    expect(entries).toHaveLength(1);
    expect(await syncQueueRepository.pendingCount()).toBe(1);
  });

  it('holds a failed entry back until its retry deadline passes', async () => {
    const entry = await syncQueueRepository.enqueue('SSB-2026-0001');
    const future = new Date(Date.now() + 60_000).toISOString();
    await syncQueueRepository.markFailed(entry.id, 'Upload rejected', future);

    expect(await syncQueueRepository.claimable(new Date().toISOString())).toHaveLength(0);
    expect(
      await syncQueueRepository.claimable(new Date(Date.now() + 120_000).toISOString()),
    ).toHaveLength(1);
    expect(await syncQueueRepository.failedCount()).toBe(1);
  });

  it('recovers entries stranded in flight by a crash', async () => {
    const entry = await syncQueueRepository.enqueue('SSB-2026-0001');
    await syncQueueRepository.markInFlight(entry.id);

    expect(await syncQueueRepository.claimable()).toHaveLength(0);
    expect(await syncQueueRepository.recoverStranded()).toBe(1);
    expect(await syncQueueRepository.claimable()).toHaveLength(1);
  });

  it('clears completed entries without touching outstanding ones', async () => {
    const entry = await syncQueueRepository.enqueue('SSB-2026-0001');
    await syncQueueRepository.markCompleted(entry.id);
    await syncQueueRepository.clearCompleted();

    expect(await syncQueueRepository.listAll()).toHaveLength(0);
    expect(await syncQueueRepository.pendingCount()).toBe(0);
  });
});

describe('user repository', () => {
  it('stores an enrolment profile and finds it case-insensitively', async () => {
    await userRepository.upsert({
      id: 'usr-1',
      officerId: 'SSB4471',
      name: 'Krishna Raj',
      rank: 'Assistant Commandant',
      role: 'OFFICER',
      unit: '41 Bn SSB',
      postName: 'Raxaul ICP',
      deviceId: 'SSB-DEV-TEST',
    });

    const found = await userRepository.findByOfficerId('ssb4471');
    expect(found?.name).toBe('Krishna Raj');
    expect(found?.role).toBe('OFFICER');
    expect(await userRepository.listEnrolled()).toHaveLength(1);
  });
});

describe('database connection', () => {
  it('does not cache a failed open, so a later call can recover', async () => {
    const { openDatabaseAsync } = jest.requireMock('expo-sqlite') as {
      openDatabaseAsync: jest.Mock;
    };
    __resetDatabaseForTests(null);

    openDatabaseAsync.mockRejectedValueOnce(new Error('database is locked'));
    await expect(getDatabase()).rejects.toThrow('database is locked');

    // A rejected promise left in the cache would be handed to every later
    // caller for the life of the process, so a lock that clears in a second
    // would still leave storage unusable until the app was reinstalled.
    await expect(getDatabase()).resolves.toBe(mockDatabase);
  });
});
