import type {
  Envelope,
  ModuleName,
  ModuleStatus,
  ScreeningCaseResult,
} from '@/contracts';
import { hasEvidence } from '@/contracts';
import { SCREENING_STAGE_DESCRIPTORS } from '@/constants/screening';
import type {
  ScreeningRequest,
  ScreeningService,
  StageEvent,
} from '@/services/ai/contracts';
import { SCREENING_STAGE_ORDER, type ScreeningStageId } from '@/types/case';
import { nowIso } from '@/utils/date';
import { delay } from '@/utils/delay';
import { createSeededRandom, seededRange } from '@/utils/random';

import { fixtureById, selectFixture } from './fixtures';

export const MOCK_SCREENING_VERSION = 'mock-screening-backend-1.0.0';

/**
 * Offline stand-in for the screening backend.
 *
 * It computes nothing. It selects a generated case document, replays it stage by
 * stage with realistic latency, and hands back the document unchanged. Every
 * finding, every band and every decision inside it came from the Python engine
 * that produced the fixture.
 *
 * That is what keeps the application free of a second implementation. Swapping
 * this for an HTTP client is a one-line change in the registry, and no consumer
 * can tell the difference because there is no logic here to diverge.
 */

/** Emulated per-stage latency, in the range the real modules take on-device. */
const STAGE_DURATION_MS: Record<ScreeningStageId, [number, number]> = {
  DOCUMENT_DETECTION: [380, 620],
  DOCUMENT_PROCESSING: [260, 460],
  OCR_MRZ: [850, 1400],
  RULE_VALIDATION: [160, 300],
  FACE_VERIFICATION: [650, 1100],
  DOCUMENT_FORENSICS: [1100, 1800],
  ANOMALY_ANALYSIS: [90, 160],
  RISK_ASSESSMENT: [300, 520],
};

/**
 * Maps a module envelope onto the stage indicator.
 *
 * This is presentation, not interpretation: WARNING means "this stage has
 * something for you to look at", and it is decided from the severity the fusion
 * engine already assigned, never re-derived from the payload.
 */
function stageStatusFor(
  envelope: Envelope<unknown> | null,
  severity: string | undefined,
): StageEvent['status'] {
  if (!envelope) return 'COMPLETED';
  if (envelope.status === 'NOT_AVAILABLE') return 'NOT_AVAILABLE';
  if (envelope.status === 'FAILED') return 'FAILED';
  if (envelope.status === 'PARTIAL') return 'WARNING';
  return severity && severity !== 'NONE' ? 'WARNING' : 'COMPLETED';
}

function envelopeFor(
  result: ScreeningCaseResult,
  module: ModuleName | null,
): Envelope<unknown> | null {
  if (!module) return null;
  return {
    ocr: result.ocr,
    validation: result.validation,
    face_verification: result.face_verification,
    document_forensics: result.document_forensics,
    anomaly: result.anomaly,
    risk: result.risk,
  }[module] as Envelope<unknown>;
}

function detailFor(
  result: ScreeningCaseResult,
  stage: ScreeningStageId,
  envelope: Envelope<unknown> | null,
): { detail: string | null; error: string | null } {
  if (envelope && (envelope.status === 'FAILED' || envelope.status === 'NOT_AVAILABLE')) {
    return { detail: null, error: envelope.errors[0]?.message ?? null };
  }

  const module = SCREENING_STAGE_DESCRIPTORS[stage].module;
  const item = result.evidence.find((entry) => entry.module === module);

  if (stage === 'RISK_ASSESSMENT') {
    const risk = hasEvidence(result.risk) ? result.risk.result : null;
    return {
      detail: risk ? `${risk.risk_level} · score ${risk.risk_score.toFixed(2)}` : null,
      error: null,
    };
  }
  if (stage === 'DOCUMENT_DETECTION') {
    const ocr = hasEvidence(result.ocr) ? result.ocr.result : null;
    return {
      detail: ocr?.detection.detected
        ? 'Document located in the frame'
        : 'Document could not be located',
      error: null,
    };
  }
  if (stage === 'DOCUMENT_PROCESSING') {
    const ocr = hasEvidence(result.ocr) ? result.ocr.result : null;
    return {
      detail: ocr?.detection.orientation_corrected
        ? 'Orientation corrected and perspective rectified'
        : 'Perspective rectified',
      error: null,
    };
  }
  return { detail: item?.detail ?? null, error: null };
}

export class MockScreeningService implements ScreeningService {
  /**
   * `scenario` forces a specific outcome, so Settings can put a device into any
   * module state on demand. Without it the fixture is derived from the case
   * reference, which keeps a given case replaying identically.
   */
  constructor(private readonly scenario?: string) {}

  async screen(request: ScreeningRequest): Promise<ScreeningCaseResult> {
    const fixture =
      (this.scenario ? fixtureById(this.scenario) : undefined) ??
      selectFixture(request.caseId, request.documentType);
    const timestamp = nowIso();

    // The fixture is stamped with this case's identity so the stored record is
    // indistinguishable in shape from a real one.
    const result: ScreeningCaseResult = {
      ...fixture.result,
      case_id: request.caseId,
      document_type: request.documentType,
      generated_at: timestamp,
      ocr: restamp(fixture.result.ocr, request.caseId, timestamp),
      validation: restamp(fixture.result.validation, request.caseId, timestamp),
      face_verification: restamp(fixture.result.face_verification, request.caseId, timestamp),
      document_forensics: restamp(
        fixture.result.document_forensics,
        request.caseId,
        timestamp,
      ),
      anomaly: restamp(fixture.result.anomaly, request.caseId, timestamp),
      risk: restamp(fixture.result.risk, request.caseId, timestamp),
    };

    const random = createSeededRandom(request.caseId);

    for (const stage of SCREENING_STAGE_ORDER) {
      const module = SCREENING_STAGE_DESCRIPTORS[stage].module;
      const envelope = envelopeFor(result, module);
      const severity = result.evidence.find((entry) => entry.module === module)?.severity;

      request.onStage?.({
        stage,
        status: 'PROCESSING',
        progress: 0,
        detail: null,
        error: null,
      });

      const [min, max] = STAGE_DURATION_MS[stage];
      const duration = seededRange(random, min, max);
      const steps = 6;
      for (let step = 1; step <= steps; step += 1) {
        await delay(duration / steps, request.signal);
        request.onStage?.({
          stage,
          status: 'PROCESSING',
          progress: step / steps,
          detail: null,
          error: null,
        });
      }

      const { detail, error } = detailFor(result, stage, envelope);
      request.onStage?.({
        stage,
        status: stageStatusFor(envelope, severity),
        progress: 1,
        detail,
        error,
      });
    }

    return result;
  }
}

function restamp<T>(envelope: Envelope<T>, caseId: string, timestamp: string): Envelope<T> {
  return { ...envelope, case_id: caseId, timestamp };
}

/** Which module statuses the current fixture set can produce. Used by tests. */
export function fixtureStatuses(result: ScreeningCaseResult): Record<ModuleName, ModuleStatus> {
  return {
    ocr: result.ocr.status,
    validation: result.validation.status,
    face_verification: result.face_verification.status,
    document_forensics: result.document_forensics.status,
    anomaly: result.anomaly.status,
    risk: result.risk.status,
  };
}
