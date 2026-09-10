import type { DocumentType, ScreeningCaseResult } from '@/contracts';
import { DOCUMENT_TYPE_DESCRIPTORS } from '@/constants/documents';

import allModulesDown from '@/fixtures/screening/all-modules-down.json';
import faceFailed from '@/fixtures/screening/face-failed.json';
import faceNoMatch from '@/fixtures/screening/face-no-match.json';
import faceReview from '@/fixtures/screening/face-review.json';
import forensicsUnavailable from '@/fixtures/screening/forensics-unavailable.json';
import genuinePassport from '@/fixtures/screening/genuine-passport.json';
import tamperedNoRegion from '@/fixtures/screening/tampered-no-region.json';
import tamperedPhotoReplacement from '@/fixtures/screening/tampered-photo-replacement.json';
import tamperedTextAndInvalid from '@/fixtures/screening/tampered-text-and-invalid.json';
import unsupportedDocumentType from '@/fixtures/screening/unsupported-document-type.json';

/**
 * Canonical case documents for offline development and demonstration.
 *
 * These are GENERATED, not hand-written — `contracts/python/tools/
 * generate_screening_fixtures.py` produces them by running the real Python
 * fusion engine, and they are committed so an offline checkout needs no Python.
 *
 * That indirection is the point. The application contains no fusion logic, no
 * validation rules and no decision boundaries; when it has no backend it
 * replays what the backend would have said. Editing these files by hand would
 * reintroduce exactly the divergence this integration removed — regenerate
 * instead.
 */
export interface ScreeningFixture {
  id: string;
  result: ScreeningCaseResult;
}

const FIXTURES: readonly ScreeningFixture[] = [
  { id: 'genuine-passport', result: genuinePassport as unknown as ScreeningCaseResult },
  { id: 'face-review', result: faceReview as unknown as ScreeningCaseResult },
  { id: 'face-no-match', result: faceNoMatch as unknown as ScreeningCaseResult },
  { id: 'face-failed', result: faceFailed as unknown as ScreeningCaseResult },
  {
    id: 'tampered-photo-replacement',
    result: tamperedPhotoReplacement as unknown as ScreeningCaseResult,
  },
  {
    id: 'tampered-text-and-invalid',
    result: tamperedTextAndInvalid as unknown as ScreeningCaseResult,
  },
  { id: 'tampered-no-region', result: tamperedNoRegion as unknown as ScreeningCaseResult },
  {
    id: 'forensics-unavailable',
    result: forensicsUnavailable as unknown as ScreeningCaseResult,
  },
  {
    id: 'unsupported-document-type',
    result: unsupportedDocumentType as unknown as ScreeningCaseResult,
  },
  { id: 'all-modules-down', result: allModulesDown as unknown as ScreeningCaseResult },
];

export const SCREENING_FIXTURES = FIXTURES;

export function fixtureById(id: string): ScreeningFixture | undefined {
  return FIXTURES.find((fixture) => fixture.id === id);
}

/**
 * Chooses which fixture a case replays.
 *
 * Selection is derived from the case reference so a given case replays
 * identically on every run and across restarts — a demonstration can be
 * rehearsed and a defect can be reproduced. Fixtures whose document type
 * matches the officer's declared type are preferred, so a passport screening
 * never plays back a national identity card's findings.
 */
/**
 * Which fixtures may stand in for a declared document type.
 *
 * Falling back to the whole set was wrong in two ways. A type no backend module
 * supports could replay a passport's findings, showing the officer confident MRZ
 * check digits for a document that was never parsed — the exact "borrowing
 * another type's rules" that DOCUMENT_TYPE_DESCRIPTORS says must not happen. And
 * a supported type with no fixture of its own, such as a driving licence, could
 * replay a passport's machine-readable zone even though the card has none.
 */
function poolFor(documentType: DocumentType): readonly ScreeningFixture[] {
  const descriptor = DOCUMENT_TYPE_DESCRIPTORS[documentType];

  if (!descriptor.backendSupported) {
    const unsupported = fixtureById('unsupported-document-type');
    if (unsupported) return [unsupported];
  }

  const exact = FIXTURES.filter((fixture) => fixture.result.document_type === documentType);
  if (exact.length > 0) return exact;

  // No fixture for this type: stand in only for one that carries the same
  // machine-readable zone characteristic, and that a backend module supports.
  const comparable = FIXTURES.filter((fixture) => {
    const other = DOCUMENT_TYPE_DESCRIPTORS[fixture.result.document_type];
    return other.backendSupported && other.hasMrz === descriptor.hasMrz;
  });
  return comparable.length > 0 ? comparable : FIXTURES;
}

export function selectFixture(caseId: string, documentType: DocumentType): ScreeningFixture {
  const pool = poolFor(documentType);

  let hash = 0;
  for (let index = 0; index < caseId.length; index += 1) {
    hash = (hash * 31 + caseId.charCodeAt(index)) >>> 0;
  }
  return pool[hash % pool.length] as ScreeningFixture;
}
