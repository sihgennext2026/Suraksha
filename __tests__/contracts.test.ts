import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import {
  DOCUMENT_TYPES,
  hasEvidence,
  moduleEnvelopes,
  SCHEMA_VERSION,
  type Envelope,
  type ScreeningCaseResult,
} from '@/contracts';
import {
  CONFIG_VERSION,
  FACE_THRESHOLDS,
  MINIMUM_EVIDENCE_WEIGHT,
  RISK_BANDS,
  ANOMALY_THRESHOLD,
} from '@/config/thresholds';
import { DOCUMENT_TYPE_DESCRIPTORS } from '@/constants/documents';
import { SCREENING_FIXTURES } from '@/services/mock/fixtures';
import { getIntegrationStatus } from '@/services/ai/registry';

/**
 * Contract conformance for the application side.
 *
 * The Python suite (`contracts/python/tests/`) proves the services emit the
 * contract. This one proves the application still agrees with it: that the
 * TypeScript mirror has not drifted from the canonical schema, that the
 * thresholds come from the shared configuration rather than from code, and that
 * every generated fixture the app replays is a valid case document.
 */

const SCHEMA = JSON.parse(
  readFileSync(join(__dirname, '..', 'contracts', 'schemas', 'ssb-screening.schema.json'), 'utf8'),
) as {
  $defs: Record<string, { enum?: string[]; const?: string; properties?: Record<string, unknown> }>;
};

const RAW_CONFIG = JSON.parse(
  readFileSync(join(__dirname, '..', 'contracts', 'config', 'thresholds.json'), 'utf8'),
) as {
  config_version: string;
  face_verification: { match: number; review: number };
};

describe('schema parity', () => {
  it('mirrors the canonical schema version', () => {
    expect(SCHEMA.$defs.schemaVersion?.const).toBe(SCHEMA_VERSION);
  });

  it('offers exactly the canonical document types', () => {
    expect([...DOCUMENT_TYPES].sort()).toEqual([...(SCHEMA.$defs.documentType?.enum ?? [])].sort());
  });

  it('has a presentation for every canonical document type', () => {
    for (const type of DOCUMENT_TYPES) {
      expect(DOCUMENT_TYPE_DESCRIPTORS[type]).toBeDefined();
      expect(DOCUMENT_TYPE_DESCRIPTORS[type].label).toBeTruthy();
    }
  });

  it('marks only passport and visa as machine-readable-zone bearing', () => {
    const withMrz = DOCUMENT_TYPES.filter((type) => DOCUMENT_TYPE_DESCRIPTORS[type].hasMrz);
    expect(withMrz.sort()).toEqual(['passport', 'visa']);
  });

  it('declares which document types the backend cannot process', () => {
    // The two extra types stay selectable, but the app must say plainly that no
    // backend module supports them rather than implying a full screening.
    const unsupported = DOCUMENT_TYPES.filter(
      (type) => !DOCUMENT_TYPE_DESCRIPTORS[type].backendSupported,
    );
    expect(unsupported.sort()).toEqual(['other', 'travel_authorization']);
  });
});

describe('threshold configuration', () => {
  it('reads the shared configuration rather than restating it', () => {
    expect(CONFIG_VERSION).toBe(RAW_CONFIG.config_version);
    expect(FACE_THRESHOLDS.match).toBe(RAW_CONFIG.face_verification.match);
    expect(FACE_THRESHOLDS.review).toBe(RAW_CONFIG.face_verification.review);
  });

  it('uses the ArcFace cosine scale, not the application’s old assumption', () => {
    // The app previously assumed matchAbove 0.85 / noMatchBelow 0.60, treating
    // similarity as a 0..1 confidence. Real ArcFace cosine similarity matches
    // around 0.30, so those numbers would have read almost every genuine subject
    // as a non-match.
    expect(FACE_THRESHOLDS.match).toBeLessThan(0.6);
    expect(FACE_THRESHOLDS.match).toBe(0.3);
    expect(FACE_THRESHOLDS.review).toBe(0.14);
    expect(FACE_THRESHOLDS.review).toBeLessThan(FACE_THRESHOLDS.match);
  });

  it('bands risk on the normalised 0..1 scale', () => {
    expect(RISK_BANDS.reviewAtOrAbove).toBeGreaterThan(0);
    expect(RISK_BANDS.reviewAtOrAbove).toBeLessThan(RISK_BANDS.highAtOrAbove);
    expect(RISK_BANDS.highAtOrAbove).toBeLessThanOrEqual(1);
  });

  it('leaves the anomaly threshold null because PatchCore is not implemented', () => {
    expect(ANOMALY_THRESHOLD).toBeNull();
  });

  it('requires the core checks to have run before a clearance stands', () => {
    expect(MINIMUM_EVIDENCE_WEIGHT).toBeGreaterThan(0.5);
  });
});

describe('generated fixtures', () => {
  it('ships a fixture for every state the interface has to render', () => {
    const ids = SCREENING_FIXTURES.map((fixture) => fixture.id).sort();
    expect(ids).toEqual(
      [
        'all-modules-down',
        'face-failed',
        'face-no-match',
        'face-review',
        'forensics-unavailable',
        'genuine-passport',
        'tampered-no-region',
        'tampered-photo-replacement',
        'tampered-text-and-invalid',
        'unsupported-document-type',
      ].sort(),
    );
  });

  it.each(SCREENING_FIXTURES.map((fixture) => [fixture.id, fixture.result] as const))(
    '%s is a complete case document',
    (_id, result: ScreeningCaseResult) => {
      expect(result.schema_version).toBe(SCHEMA_VERSION);
      expect(DOCUMENT_TYPES).toContain(result.document_type);
      expect(result.evidence.length).toBeGreaterThan(0);

      for (const { module, envelope } of moduleEnvelopes(result)) {
        expect(envelope.schema_version).toBe(SCHEMA_VERSION);
        expect(envelope.module).toBe(module);
        expect(envelope.model_version).toBeTruthy();
        expect(Array.isArray(envelope.errors)).toBe(true);
      }
    },
  );

  it.each(SCREENING_FIXTURES.map((fixture) => [fixture.id, fixture.result] as const))(
    '%s never carries a result behind a non-success status',
    (_id, result: ScreeningCaseResult) => {
      // The invariant every screen relies on: seeing FAILED or NOT_AVAILABLE is
      // enough to stop reading, because there is provably nothing behind it.
      for (const { envelope } of moduleEnvelopes(result)) {
        if (envelope.status === 'FAILED' || envelope.status === 'NOT_AVAILABLE') {
          expect(envelope.result).toBeNull();
          expect(envelope.errors.length).toBeGreaterThan(0);
        } else {
          expect(envelope.result).not.toBeNull();
        }
      }
    },
  );

  it('reports anomaly as not available on every fixture', () => {
    // PatchCore is not implemented. No fixture may imply otherwise.
    for (const fixture of SCREENING_FIXTURES) {
      expect(fixture.result.anomaly.status).toBe('NOT_AVAILABLE');
      expect(fixture.result.anomaly.result).toBeNull();
      expect(fixture.result.anomaly.errors[0]?.code).toBe('ANOMALY_NOT_IMPLEMENTED');
    }
  });

  it('keeps face similarity on the raw cosine scale', () => {
    for (const fixture of SCREENING_FIXTURES) {
      const face = fixture.result.face_verification;
      if (!hasEvidence(face)) continue;
      expect(face.result.similarity).toBeGreaterThanOrEqual(-1);
      expect(face.result.similarity).toBeLessThanOrEqual(1);
      expect(face.result.thresholds.match).toBe(FACE_THRESHOLDS.match);
      expect(face.result.thresholds.review).toBe(FACE_THRESHOLDS.review);
    }
  });

  it('never fabricates a face quality score', () => {
    for (const fixture of SCREENING_FIXTURES) {
      const face = fixture.result.face_verification;
      if (!hasEvidence(face)) continue;
      // The ArcFace pipeline reports gates and measurements, not a 0..1 score.
      expect(face.result.quality.document_face.score).toBeNull();
      expect(face.result.quality.live_face.score).toBeNull();
    }
  });

  it('reports every risk level on the officer-facing taxonomy only', () => {
    for (const fixture of SCREENING_FIXTURES) {
      const risk = fixture.result.risk;
      if (!hasEvidence(risk)) continue;
      expect(['LOW', 'REVIEW', 'HIGH']).toContain(risk.result.risk_level);
      expect(risk.result.risk_score).toBeGreaterThanOrEqual(0);
      expect(risk.result.risk_score).toBeLessThanOrEqual(1);
      expect(risk.result.engine_version).not.toMatch(/lightgbm/i);
    }
  });

  it('excludes absent modules from scoring and says so in the contributors', () => {
    const fixture = SCREENING_FIXTURES.find((entry) => entry.id === 'forensics-unavailable');
    const risk = fixture?.result.risk;
    if (!risk || !hasEvidence(risk)) throw new Error('fixture missing');

    const forensics = risk.result.contributors.find(
      (entry) => entry.source === 'document_forensics',
    );
    expect(forensics?.counted).toBe(false);
    expect(forensics?.weight).toBeNull();
    expect(forensics?.severity).toBe('NONE');
    expect(risk.result.evidence_coverage).toBeLessThan(1);
  });

  it('cannot clear a case where nothing was measured', () => {
    const fixture = SCREENING_FIXTURES.find((entry) => entry.id === 'all-modules-down');
    const risk = fixture?.result.risk;
    if (!risk || !hasEvidence(risk)) throw new Error('fixture missing');

    expect(risk.result.evidence_coverage).toBe(0);
    expect(risk.result.risk_level).toBe('REVIEW');
  });

  it('bands a detected tampering as high', () => {
    const fixture = SCREENING_FIXTURES.find(
      (entry) => entry.id === 'tampered-photo-replacement',
    );
    const forensics = fixture?.result.document_forensics;
    const risk = fixture?.result.risk;
    if (!forensics || !hasEvidence(forensics) || !risk || !hasEvidence(risk)) {
      throw new Error('fixture missing');
    }

    expect(forensics.result.tampered).toBe(true);
    expect(forensics.result.manipulation_type).toBe('PHOTO_REPLACEMENT');
    expect(forensics.result.suspicious_regions.length).toBeGreaterThan(0);
    expect(risk.result.risk_level).toBe('HIGH');
  });

  it('reports a tampered document with no localised region as PARTIAL', () => {
    const fixture = SCREENING_FIXTURES.find((entry) => entry.id === 'tampered-no-region');
    const forensics = fixture?.result.document_forensics;
    if (!forensics) throw new Error('fixture missing');

    // An empty region list must not be readable as "nothing found".
    expect(forensics.status).toBe('PARTIAL');
    expect(forensics.result?.tampered).toBe(true);
    expect(forensics.result?.suspicious_regions).toEqual([]);
    expect(forensics.errors[0]?.code).toBe('LOCALISATION_INCONCLUSIVE');
  });

  it('marks unsupported document types as not available rather than passing them', () => {
    const fixture = SCREENING_FIXTURES.find((entry) => entry.id === 'unsupported-document-type');
    if (!fixture) throw new Error('fixture missing');

    expect(fixture.result.document_type).toBe('travel_authorization');
    expect(fixture.result.ocr.status).toBe('NOT_AVAILABLE');
    expect(fixture.result.validation.status).toBe('NOT_AVAILABLE');
    expect(fixture.result.ocr.errors[0]?.code).toBe('UNSUPPORTED_DOCUMENT_TYPE');
  });

  it('keeps every suspicious region inside the normalised image frame', () => {
    for (const fixture of SCREENING_FIXTURES) {
      const forensics = fixture.result.document_forensics;
      if (!hasEvidence(forensics)) continue;
      for (const region of forensics.result.suspicious_regions) {
        expect(region.bbox).toHaveLength(4);
        for (const value of region.bbox) {
          expect(value).toBeGreaterThanOrEqual(0);
          expect(value).toBeLessThanOrEqual(1);
        }
      }
    }
  });

  it('keeps validation NOT_APPLICABLE and NOT_AVAILABLE apart from FAIL', () => {
    for (const fixture of SCREENING_FIXTURES) {
      const validation = fixture.result.validation;
      if (!hasEvidence(validation)) continue;
      const { summary, checks, decision } = validation.result;

      // A rule set whose only non-passes are "not evaluated" is still VALID.
      const adverse = checks.filter(
        (check) => check.status === 'FAIL' || check.status === 'REVIEW',
      );
      if (adverse.length === 0) expect(decision).toBe('VALID');
      expect(summary.failed).toBe(checks.filter((check) => check.status === 'FAIL').length);
    }
  });
});

describe('integration status', () => {
  // With no service configured the app replays fixtures, which is the state the
  // read-out must describe honestly.
  const INTEGRATION_STATUS = getIntegrationStatus(null);

  it('states plainly that tamper detection is a mock', () => {
    const forensics = INTEGRATION_STATUS.find((entry) =>
      entry.module.toLowerCase().includes('forensics'),
    );
    expect(forensics?.state).toBe('MOCK');
    expect(forensics?.implementation).toContain('mock-dinov2');
    expect(forensics?.note).toMatch(/not implemented/i);
  });

  it('states plainly that anomaly detection does not exist', () => {
    const anomaly = INTEGRATION_STATUS.find((entry) =>
      entry.module.toLowerCase().includes('anomaly'),
    );
    expect(anomaly?.state).toBe('NOT_AVAILABLE');
  });

  it('does not claim the fusion engine is LightGBM', () => {
    const risk = INTEGRATION_STATUS.find((entry) => entry.module.toLowerCase().includes('risk'));
    // The implementation must not assert a model that is not running...
    expect(risk?.implementation).not.toMatch(/lightgbm/i);
    expect(risk?.implementation).toMatch(/fusion/i);
    // ...and the note must say so explicitly, because "fusion engine" alone
    // would leave a reader free to assume the gradient-boosted model is in play.
    expect(risk?.note).toMatch(/not lightgbm/i);
  });
});

describe('envelope narrowing', () => {
  const envelope = (status: Envelope<{ a: number }>['status'], result: { a: number } | null) =>
    ({
      schema_version: SCHEMA_VERSION,
      case_id: 'X',
      module: 'ocr' as const,
      status,
      model_version: 'v1',
      timestamp: '2026-01-01T00:00:00.000Z',
      result,
      errors: [],
    }) satisfies Envelope<{ a: number }>;

  it('narrows only when a result is genuinely present', () => {
    expect(hasEvidence(envelope('SUCCESS', { a: 1 }))).toBe(true);
    expect(hasEvidence(envelope('PARTIAL', { a: 1 }))).toBe(true);
    expect(hasEvidence(envelope('FAILED', null))).toBe(false);
    expect(hasEvidence(envelope('NOT_AVAILABLE', null))).toBe(false);
    // Defensive: a malformed SUCCESS with no payload must not narrow either.
    expect(hasEvidence(envelope('SUCCESS', null))).toBe(false);
  });
});
