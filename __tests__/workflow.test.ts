import { createTestDatabase, type TestDatabase } from './support/sqliteTestDatabase';

/**
 * The end-to-end officer workflow, driven through the stores.
 *
 * This is the suite that catches a regression in the sequence the application
 * exists to support: sign in, open a case, capture, screen, decide, save
 * offline, sync when the network returns. It also covers the states an officer
 * must never be misled by — a module that did not run, a screening that was
 * interrupted, a document type no backend module supports.
 */

let mockDatabase: TestDatabase;

jest.mock('expo-sqlite', () => ({
  openDatabaseAsync: jest.fn(async () => mockDatabase),
}));

// Capture persistence is a filesystem concern with no bearing on the workflow.
jest.mock('@/services/storage/mediaStore', () => ({
  mediaStore: {
    persistCapture: jest.fn(async (_caseId: string, _kind: string, image: unknown) => image),
    removeCaseMedia: jest.fn(async () => undefined),
    usedBytes: jest.fn(async () => 0),
    availableFraction: jest.fn(async () => 0.9),
  },
}));

const mockUploadCase = jest.fn();
jest.mock('@/services/sync/remoteApi', () => ({
  remoteCaseApi: { uploadCase: (...args: unknown[]) => mockUploadCase(...args) },
}));

import { hasEvidence, type DocumentType } from '@/contracts';
import { auditRepository, caseRepository, __resetDatabaseForTests } from '@/db';
import { authService } from '@/services/api/authService';
import { syncEngine } from '@/services/sync/syncEngine';
import { useAuthStore } from '@/stores/authStore';
import { useScreeningStore } from '@/stores/screeningStore';
import type { AuthenticatedUser } from '@/types';

import { DOCUMENT_IMAGE, PERSON_IMAGE } from './support/caseFactory';

function resetDeviceStorage() {
  const secureStore = jest.requireMock('expo-secure-store') as { __reset(): void };
  const asyncStorage = jest.requireMock('@react-native-async-storage/async-storage') as {
    default: { __reset(): void };
  };
  secureStore.__reset();
  asyncStorage.default.__reset();
}

function resetStores() {
  useScreeningStore.setState({
    activeCase: null,
    phase: 'IDLE',
    running: false,
    error: null,
    restored: true,
    saving: false,
    saveError: null,
  });
  useAuthStore.setState({
    status: 'SIGNED_OUT',
    session: null,
    deviceId: null,
    error: null,
    busy: false,
  });
}

async function signIn(): Promise<AuthenticatedUser> {
  await useAuthStore.getState().bootstrap();
  const ok = await useAuthStore.getState().signIn({ officerId: 'SSB4471', pin: '4471' });
  expect(ok).toBe(true);
  const user = useAuthStore.getState().session?.user;
  if (!user) throw new Error('Sign-in did not produce a session');
  return user;
}

/** Runs a full screening, optionally forcing a specific outcome. */
async function runFullScreening(
  user: AuthenticatedUser,
  options: { documentType?: DocumentType; scenario?: string } = {},
) {
  const created = await useScreeningStore.getState().start(user);
  await useScreeningStore.getState().setDocumentType(options.documentType ?? 'passport');
  await useScreeningStore.getState().attachDocument(DOCUMENT_IMAGE);
  await useScreeningStore.getState().attachPerson(PERSON_IMAGE);
  await useScreeningStore.getState().runScreening({ scenario: options.scenario });
  return created;
}

beforeEach(async () => {
  mockDatabase = createTestDatabase();
  __resetDatabaseForTests(null);
  mockUploadCase.mockReset();
  mockUploadCase.mockResolvedValue({ remoteId: 'REM-1', acceptedAt: '2026-08-24T10:05:00.000Z' });
  resetDeviceStorage();
  resetStores();
});

afterEach(async () => {
  useScreeningStore.getState().cancelScreening();
  await mockDatabase.closeAsync();
});

describe('authentication', () => {
  it('signs an enrolled officer in against the on-device record', async () => {
    const user = await signIn();
    expect(user.officerId).toBe('SSB4471');
    expect(useAuthStore.getState().session?.offlineVerified).toBe(true);
  });

  it('rejects a wrong PIN without revealing whether the officer ID exists', async () => {
    await useAuthStore.getState().bootstrap();
    const wrongPin = await useAuthStore.getState().signIn({ officerId: 'SSB4471', pin: '0000' });
    const unknownId = await useAuthStore.getState().signIn({ officerId: 'SSB9999', pin: '4471' });

    expect(wrongPin).toBe(false);
    expect(unknownId).toBe(false);
    expect(useAuthStore.getState().error).toBe(
      'That officer ID and PIN do not match a record on this device.',
    );
  });

  it('restores a valid session and records the sign-in', async () => {
    await signIn();
    expect((await authService.restoreSession())?.user.officerId).toBe('SSB4471');
    const events = await auditRepository.listRecent();
    expect(events.some((event) => event.type === 'LOGIN')).toBe(true);
  });

  it('clears the session on sign-out', async () => {
    await signIn();
    await useAuthStore.getState().signOut();
    expect(useAuthStore.getState().status).toBe('SIGNED_OUT');
    expect(await authService.restoreSession()).toBeNull();
  });
});

describe('screening workflow', () => {
  it('runs from case creation through to a saved, queued case', async () => {
    const user = await signIn();
    const created = await runFullScreening(user, { scenario: 'genuine-passport' });

    const state = useScreeningStore.getState();
    expect(state.error).toBeNull();
    expect(state.phase).toBe('RESULT');
    expect(state.activeCase?.status).toBe('AWAITING_DECISION');

    // The application stores the canonical case document, whole.
    const result = state.activeCase?.result;
    expect(result?.schema_version).toBe('1.0');
    expect(result?.case_id).toBe(created.id);
    expect(hasEvidence(result!.risk)).toBe(true);
    expect(state.activeCase?.stages.every((stage) => stage.status !== 'WAITING')).toBe(true);

    await useScreeningStore.getState().recordDecision('CLEAR', 'Verified against the register.');
    const savedId = await useScreeningStore.getState().save({ autoSync: false, online: false });

    expect(savedId).toBe(created.id);
    const stored = await caseRepository.findById(created.id);
    expect(stored?.status).toBe('COMPLETED');
    expect(stored?.decision?.decision).toBe('CLEAR');
    expect(stored?.sync.state).toBe('PENDING');
    // Round-trips byte-identically: the app is a consumer of this document.
    expect(stored?.result).toEqual(result);
  }, 30_000);

  it('records the case before any capture, so an interruption loses nothing', async () => {
    const user = await signIn();
    const created = await useScreeningStore.getState().start(user);

    const stored = await caseRepository.findById(created.id);
    expect(stored?.status).toBe('DRAFT');
    const events = await auditRepository.listForCase(created.id);
    expect(events.map((event) => event.type)).toContain('CASE_CREATED');
  });

  it('recovers an interrupted screening back to the point it can be re-run', async () => {
    const user = await signIn();
    const created = await useScreeningStore.getState().start(user);
    await useScreeningStore.getState().setDocumentType('passport');
    await useScreeningStore.getState().attachDocument(DOCUMENT_IMAGE);
    await useScreeningStore.getState().attachPerson(PERSON_IMAGE);

    // Simulate the application being killed mid-screening.
    useScreeningStore.setState({ phase: 'SCREENING', activeCase: null, restored: false });
    await useScreeningStore.getState().restore();

    const state = useScreeningStore.getState();
    expect(state.activeCase?.id).toBe(created.id);
    // Both captures survive; the officer does not ask for the document back.
    expect(state.activeCase?.document).not.toBeNull();
    expect(state.activeCase?.person).not.toBeNull();
    expect(state.phase).toBe('PERSON_CAPTURE');
    expect(state.activeCase?.stages.every((stage) => stage.status === 'WAITING')).toBe(true);
  });

  it('marks an abandoned case rather than deleting its audit trail', async () => {
    const user = await signIn();
    const created = await useScreeningStore.getState().start(user);
    await useScreeningStore.getState().abandon();

    expect((await caseRepository.findById(created.id))?.status).toBe('ABANDONED');
    const events = await auditRepository.listForCase(created.id);
    expect(events.map((event) => event.type)).toContain('CASE_ABANDONED');
  });

  it('records the assessment as it stood when the officer decided', async () => {
    const user = await signIn();
    await runFullScreening(user, { scenario: 'genuine-passport' });

    const shown = useScreeningStore.getState().activeCase?.result?.risk;
    await useScreeningStore.getState().recordDecision('CLEAR', '');
    const decision = useScreeningStore.getState().activeCase?.decision;

    expect(decision?.riskLevelAtDecision).toBe(shown?.result?.risk_level);
    expect(decision?.riskScoreAtDecision).toBe(shown?.result?.risk_score);
  }, 30_000);

  it('leaves the assessment null when no risk result was produced', async () => {
    const user = await signIn();
    await runFullScreening(user, { scenario: 'genuine-passport' });

    // A case decided without an assessment must not be given one after the fact.
    const active = useScreeningStore.getState().activeCase;
    useScreeningStore.setState({ activeCase: { ...active!, result: null } });
    await useScreeningStore.getState().recordDecision('HOLD', 'No assessment available.');

    const decision = useScreeningStore.getState().activeCase?.decision;
    expect(decision?.riskLevelAtDecision).toBeNull();
    expect(decision?.riskScoreAtDecision).toBeNull();
    expect(decision?.divergedFromRecommendation).toBe(false);
  }, 30_000);

  it('writes a complete audit trail for a finished case', async () => {
    const user = await signIn();
    const created = await runFullScreening(user, { scenario: 'genuine-passport' });
    await useScreeningStore.getState().recordDecision('CLEAR', '');
    await useScreeningStore.getState().save({ autoSync: false, online: false });

    const types = (await auditRepository.listForCase(created.id)).map((event) => event.type);
    for (const expected of [
      'CASE_CREATED',
      'DOCUMENT_TYPE_SELECTED',
      'DOCUMENT_CAPTURED',
      'PERSON_CAPTURED',
      'SCREENING_STARTED',
      'OCR_COMPLETED',
      'VALIDATION_COMPLETED',
      'FACE_VERIFIED',
      'FORENSICS_COMPLETED',
      'RISK_GENERATED',
      'OFFICER_DECISION',
      'CASE_SAVED',
    ]) {
      expect(types).toContain(expected);
    }
    // PatchCore never runs, so the trail records the gap rather than a result.
    expect(types).toContain('MODULE_UNAVAILABLE');
  }, 30_000);

  it('replays the same case identically on a second run', async () => {
    const user = await signIn();
    await runFullScreening(user);
    const first = useScreeningStore.getState().activeCase?.result?.risk.result;

    await useScreeningStore.getState().runScreening({});
    const second = useScreeningStore.getState().activeCase?.result?.risk.result;

    expect(second?.risk_score).toBe(first?.risk_score);
    expect(second?.risk_level).toBe(first?.risk_level);
  }, 40_000);
});

describe('a module that did not run', () => {
  it('completes the screening and records the gap', async () => {
    const user = await signIn();
    await runFullScreening(user, { scenario: 'forensics-unavailable' });

    const result = useScreeningStore.getState().activeCase?.result;
    expect(result?.document_forensics.status).toBe('FAILED');
    expect(result?.document_forensics.result).toBeNull();
    // The screening still completed. One module going down does not stop it.
    expect(useScreeningStore.getState().activeCase?.status).toBe('AWAITING_DECISION');
    expect(hasEvidence(result!.risk)).toBe(true);
  }, 30_000);

  it('never becomes a pass', async () => {
    const user = await signIn();
    await runFullScreening(user, { scenario: 'forensics-unavailable' });

    const risk = useScreeningStore.getState().activeCase?.result?.risk.result;
    const forensics = risk?.contributors.find(
      (entry) => entry.source === 'document_forensics',
    );
    expect(forensics?.counted).toBe(false);
    expect(forensics?.severity).toBe('NONE');
    // A case whose tamper check never ran cannot be cleared as low risk.
    expect(risk?.risk_level).not.toBe('LOW');
  }, 30_000);

  it('shows the stage as not-run rather than as a failure of the document', async () => {
    const user = await signIn();
    await runFullScreening(user, { scenario: 'forensics-unavailable' });

    const stage = useScreeningStore
      .getState()
      .activeCase?.stages.find((entry) => entry.id === 'DOCUMENT_FORENSICS');
    expect(stage?.status).toBe('FAILED');
    expect(stage?.error).toBeTruthy();
  }, 30_000);

  it('reports an unsupported document type without borrowing another type’s rules', async () => {
    const user = await signIn();
    await runFullScreening(user, {
      documentType: 'travel_authorization',
      scenario: 'unsupported-document-type',
    });

    const result = useScreeningStore.getState().activeCase?.result;
    expect(result?.ocr.status).toBe('NOT_AVAILABLE');
    expect(result?.validation.status).toBe('NOT_AVAILABLE');
    expect(result?.validation.result).toBeNull();
    expect(result?.risk.result?.risk_level).not.toBe('LOW');
  }, 30_000);

  it('always reports anomaly as not available', async () => {
    const user = await signIn();
    await runFullScreening(user);

    const anomaly = useScreeningStore.getState().activeCase?.result?.anomaly;
    expect(anomaly?.status).toBe('NOT_AVAILABLE');
    expect(anomaly?.result).toBeNull();
  }, 30_000);
});

describe('offline behaviour', () => {
  it('completes a screening and saves it with no network at any point', async () => {
    const user = await signIn();
    const created = await runFullScreening(user, { scenario: 'genuine-passport' });
    await useScreeningStore.getState().recordDecision('CLEAR', '');
    await useScreeningStore.getState().save({ autoSync: true, online: false });

    // Auto-sync was on, but the device was offline: nothing was attempted.
    expect(mockUploadCase).not.toHaveBeenCalled();
    const stored = await caseRepository.findById(created.id);
    expect(stored?.status).toBe('COMPLETED');
    expect(stored?.sync.state).toBe('PENDING');
  }, 30_000);

  it('uploads the queued case once the network returns', async () => {
    const user = await signIn();
    const created = await runFullScreening(user, { scenario: 'genuine-passport' });
    await useScreeningStore.getState().recordDecision('CLEAR', '');
    await useScreeningStore.getState().save({ autoSync: false, online: false });

    const summary = await syncEngine.run({
      online: true,
      actorId: user.officerId,
      actorName: user.name,
    });

    expect(summary.succeeded).toBe(1);
    expect((await caseRepository.findById(created.id))?.sync.state).toBe('SYNCED');
  }, 30_000);
});

describe('reliability of the screening run', () => {
  it('still completes the screening when the audit trail cannot be written', async () => {
    const user = await signIn();

    // The audit trail shares a database with everything else, so a disk fault
    // hits it too. It must not take the screening down with it: this used to
    // throw out of `runScreening` after `running` had been set, leaving a
    // progress indicator that never stopped and a guard that refused a retry.
    const record = jest
      .spyOn(auditRepository, 'record')
      .mockRejectedValue(new Error('database or disk is full'));

    try {
      await runFullScreening(user);
    } finally {
      record.mockRestore();
    }

    const state = useScreeningStore.getState();
    expect(state.running).toBe(false);
    expect(state.error).toBeNull();
    expect(state.phase).toBe('RESULT');
    // The officer still has findings to act on, which is the point.
    expect(state.activeCase?.result).not.toBeNull();
    expect(state.activeCase?.status).toBe('AWAITING_DECISION');
  }, 30_000);
});

describe('fixture selection for a declared document type', () => {
  it('never borrows a parsed document’s findings for an unsupported type', async () => {
    const user = await signIn();
    // No scenario is forced here: this is the path an officer actually takes,
    // and 'other' has no fixture of its own, so it exercises the fallback.
    await runFullScreening(user, { documentType: 'other' });

    const result = useScreeningStore.getState().activeCase?.result;
    expect(result?.document_type).toBe('other');
    // The modules must report that they did not run, not a passport's verdicts.
    expect(result?.ocr.status).toBe('NOT_AVAILABLE');
    expect(result?.validation.status).toBe('NOT_AVAILABLE');
    expect(result?.validation.result).toBeNull();
  }, 30_000);

  it('does not replay a machine-readable zone for a card that has none', async () => {
    const user = await signIn();
    await runFullScreening(user, { documentType: 'driving_license' });

    const result = useScreeningStore.getState().activeCase?.result;
    expect(result?.document_type).toBe('driving_license');
    // A driving licence carries no MRZ, so standing in a passport's check-digit
    // findings would put fabricated evidence in front of the officer. The
    // licence is a backend-supported type, so extraction must have produced
    // evidence — asserting that first keeps this from passing vacuously.
    const ocr = result?.ocr;
    if (!ocr || !hasEvidence(ocr)) {
      throw new Error('A supported document type should still produce OCR evidence');
    }
    expect(ocr.result.mrz?.present ?? false).toBe(false);
  }, 30_000);
});

describe('reverse-side capture', () => {
  it('records the reverse against the document and survives a reload', async () => {
    const user = await signIn();
    const created = await useScreeningStore.getState().start(user);
    await useScreeningStore.getState().setDocumentType('driving_license');
    await useScreeningStore.getState().attachDocument(DOCUMENT_IMAGE);
    await useScreeningStore
      .getState()
      .attachDocumentBack({ ...DOCUMENT_IMAGE, uri: 'file:///captures/back.jpg' });

    // The reverse is a row of its own in `documents`, so the round trip is what
    // proves it is actually stored rather than only held in memory.
    const reloaded = await caseRepository.findById(created.id);
    expect(reloaded?.document?.backImage?.uri).toBe('file:///captures/back.jpg');
  }, 30_000);

  it('discards a reverse when the front is retaken', async () => {
    const user = await signIn();
    await useScreeningStore.getState().start(user);
    await useScreeningStore.getState().setDocumentType('driving_license');
    await useScreeningStore.getState().attachDocument(DOCUMENT_IMAGE);
    await useScreeningStore
      .getState()
      .attachDocumentBack({ ...DOCUMENT_IMAGE, uri: 'file:///captures/back.jpg' });

    // The two images must be of the same document. Keeping an old reverse
    // beside a new front would merge readings the officer never paired.
    await useScreeningStore.getState().attachDocument(DOCUMENT_IMAGE);

    expect(useScreeningStore.getState().activeCase?.document?.backImage).toBeNull();
  }, 30_000);

  it('screens without a reverse rather than demanding one', async () => {
    const user = await signIn();
    await runFullScreening(user, { documentType: 'driving_license' });

    const state = useScreeningStore.getState();
    expect(state.activeCase?.document?.backImage).toBeNull();
    // A missing reverse must not block the workflow.
    expect(state.activeCase?.result).not.toBeNull();
    expect(state.phase).toBe('RESULT');
  }, 30_000);
});

describe('reverse-side pairing safety', () => {
  it('discards a reverse whose front was retaken while it was being stored', async () => {
    const user = await signIn();
    await useScreeningStore.getState().start(user);
    await useScreeningStore.getState().setDocumentType('driving_license');
    await useScreeningStore.getState().attachDocument(DOCUMENT_IMAGE);

    // Persisting is asynchronous. Retake the front while the reverse is in
    // flight: the two images are then of different captures, and pairing them
    // would merge readings from documents the officer never put together.
    const media = jest.requireMock('@/services/storage/mediaStore') as {
      mediaStore: { persistCapture: jest.Mock };
    };
    media.mediaStore.persistCapture.mockImplementationOnce(async (_case, _kind, img) => {
      await useScreeningStore
        .getState()
        .attachDocument({ ...DOCUMENT_IMAGE, uri: 'file:///captures/front-retaken.jpg' });
      return img;
    });

    await useScreeningStore
      .getState()
      .attachDocumentBack({ ...DOCUMENT_IMAGE, uri: 'file:///captures/back.jpg' });

    const document = useScreeningStore.getState().activeCase?.document;
    expect(document?.image.uri).toBe('file:///captures/front-retaken.jpg');
    expect(document?.backImage).toBeNull();
  }, 30_000);

  it('does not attach a reverse to a different case', async () => {
    const user = await signIn();
    await useScreeningStore.getState().start(user);
    await useScreeningStore.getState().setDocumentType('driving_license');
    await useScreeningStore.getState().attachDocument(DOCUMENT_IMAGE);

    const media = jest.requireMock('@/services/storage/mediaStore') as {
      mediaStore: { persistCapture: jest.Mock };
    };
    media.mediaStore.persistCapture.mockImplementationOnce(async (_case, _kind, img) => {
      // The officer abandons this case and opens another mid-capture.
      await useScreeningStore.getState().start(user);
      return img;
    });

    await useScreeningStore
      .getState()
      .attachDocumentBack({ ...DOCUMENT_IMAGE, uri: 'file:///captures/back.jpg' });

    expect(useScreeningStore.getState().activeCase?.document).toBeNull();
  }, 30_000);
});
