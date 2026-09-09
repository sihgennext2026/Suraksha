import type { DocumentType, ScreeningCaseResult } from '@/contracts';
import { createInitialStages } from '@/stores/screeningStore';
import type { CapturedImage, ScreeningCase } from '@/types';

import genuine from '@/fixtures/screening/genuine-passport.json';
import tampered from '@/fixtures/screening/tampered-photo-replacement.json';
import faceNoMatch from '@/fixtures/screening/face-no-match.json';
import forensicsUnavailable from '@/fixtures/screening/forensics-unavailable.json';
import allModulesDown from '@/fixtures/screening/all-modules-down.json';

/**
 * Builds cases for the suites.
 *
 * The screening results here are the generated fixtures — the same documents the
 * offline mock replays, produced by the Python fusion engine. Hand-writing a
 * result would let the tests pass against a shape the backend never emits, which
 * is exactly the divergence the contract exists to prevent.
 */

export const FIXTURE_RESULTS = {
  genuine: genuine as unknown as ScreeningCaseResult,
  tampered: tampered as unknown as ScreeningCaseResult,
  faceNoMatch: faceNoMatch as unknown as ScreeningCaseResult,
  forensicsUnavailable: forensicsUnavailable as unknown as ScreeningCaseResult,
  allModulesDown: allModulesDown as unknown as ScreeningCaseResult,
};

export const DOCUMENT_IMAGE: CapturedImage = {
  uri: 'file:///cache/document.jpg',
  width: 1600,
  height: 1130,
  sizeBytes: 240_000,
  source: 'CAMERA',
  capturedAt: '2026-08-24T10:00:00.000Z',
};

export const PERSON_IMAGE: CapturedImage = {
  uri: 'file:///cache/person.jpg',
  width: 1080,
  height: 1440,
  sizeBytes: 180_000,
  source: 'CAMERA',
  capturedAt: '2026-08-24T10:01:00.000Z',
};

interface BuildOptions {
  id?: string;
  documentType?: DocumentType;
  result?: ScreeningCaseResult | null;
  status?: ScreeningCase['status'];
  decision?: ScreeningCase['decision'];
  sync?: Partial<ScreeningCase['sync']>;
}

/** Stamps a fixture with a case identity, as the mock service does at runtime. */
export function resultFor(id: string, result: ScreeningCaseResult): ScreeningCaseResult {
  return {
    ...result,
    case_id: id,
    ocr: { ...result.ocr, case_id: id },
    validation: { ...result.validation, case_id: id },
    face_verification: { ...result.face_verification, case_id: id },
    document_forensics: { ...result.document_forensics, case_id: id },
    anomaly: { ...result.anomaly, case_id: id },
    risk: { ...result.risk, case_id: id },
  };
}

export function buildCase(options: BuildOptions = {}): ScreeningCase {
  const id = options.id ?? 'SSB-2026-0001';
  const result =
    options.result === undefined ? resultFor(id, FIXTURE_RESULTS.genuine) : options.result;

  return {
    id,
    status: options.status ?? 'COMPLETED',
    documentType: options.documentType ?? result?.document_type ?? 'passport',
    document: {
      id: `doc-${id}`,
      caseId: id,
      declaredType: options.documentType ?? result?.document_type ?? 'passport',
      image: DOCUMENT_IMAGE,
    },
    person: { id: `person-${id}`, caseId: id, image: PERSON_IMAGE },
    stages: createInitialStages(),
    result,
    decision: options.decision ?? null,
    sync: {
      state: 'LOCAL_ONLY',
      lastAttemptAt: null,
      lastSyncedAt: null,
      attempts: 0,
      lastError: null,
      ...options.sync,
    },
    officerId: 'SSB4471',
    officerName: 'Krishna Raj',
    unit: '41 Bn SSB',
    postName: 'Raxaul ICP',
    createdAt: '2026-08-24T10:00:00.000Z',
    updatedAt: '2026-08-24T10:02:00.000Z',
  };
}
