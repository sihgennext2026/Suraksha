import type { Envelope, ModuleName, ScreeningCaseResult } from '@/contracts';
import { hasEvidence } from '@/contracts';
import { SCREENING_STAGE_DESCRIPTORS } from '@/constants/screening';
import { SCREENING_STAGE_ORDER, type ScreeningStageId } from '@/types/case';

import type { StageEvent } from './contracts';

/**
 * Turns a finished case document into the pipeline display.
 *
 * This is presentation, not interpretation. Every value shown is read from the
 * document the service produced: the severity was assigned by the fusion
 * engine, the status by the module itself. Nothing here re-derives a verdict
 * from a payload, which is what keeps the two service implementations showing
 * the officer the same thing for the same evidence.
 */

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

/**
 * WARNING means "this stage has something for you to look at". It is decided
 * from the severity the fusion engine already assigned, never recomputed.
 */
export function stageStatusFor(
  envelope: Envelope<unknown> | null,
  severity: string | undefined,
): StageEvent['status'] {
  if (!envelope) return 'COMPLETED';
  if (envelope.status === 'NOT_AVAILABLE') return 'NOT_AVAILABLE';
  if (envelope.status === 'FAILED') return 'FAILED';
  if (envelope.status === 'PARTIAL') return 'WARNING';
  return severity && severity !== 'NONE' ? 'WARNING' : 'COMPLETED';
}

export function detailFor(
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

/** The terminal event for one stage, given the finished document. */
export function stageEventFor(result: ScreeningCaseResult, stage: ScreeningStageId): StageEvent {
  const module = SCREENING_STAGE_DESCRIPTORS[stage].module;
  const envelope = envelopeFor(result, module);
  const severity = result.evidence.find((entry) => entry.module === module)?.severity;
  const { detail, error } = detailFor(result, stage, envelope);

  return {
    stage,
    status: stageStatusFor(envelope, severity),
    progress: 1,
    detail,
    error,
  };
}

/** Every stage's terminal event, in workflow order. */
export function stageEventsFor(result: ScreeningCaseResult): StageEvent[] {
  return SCREENING_STAGE_ORDER.map((stage) => stageEventFor(result, stage));
}

export { envelopeFor };
