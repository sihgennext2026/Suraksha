import type {
  AnomalyResult,
  DocumentForensicsResult,
  DocumentType,
  Envelope,
  FaceVerificationResult,
  OcrResult,
  RiskResult,
  ValidationResult,
} from '@/contracts';
import type {
  AnomalyService,
  DocumentForensicsService,
  DocumentVerificationService,
  FaceVerificationService,
  RiskService,
  ValidationService,
} from '@/services/ai/contracts';
import type { CapturedImage } from '@/types/document';
import { nowIso } from '@/utils/date';

import { fixtureById, selectFixture, type ScreeningFixture } from './fixtures';

/**
 * Per-module offline implementations.
 *
 * A deployment that calls each module separately — an edge device running the
 * runtimes locally, say — binds these instead of the single screening service.
 * They exist mainly to keep the module boundaries real: every one of them can be
 * replaced independently, which is what the DINOv2 swap below depends on.
 */

function pick(caseId: string, documentType: DocumentType, scenario?: string): ScreeningFixture {
  return (scenario ? fixtureById(scenario) : undefined) ?? selectFixture(caseId, documentType);
}

function restamp<T>(envelope: Envelope<T>, caseId: string): Envelope<T> {
  return { ...envelope, case_id: caseId, timestamp: nowIso() };
}

export class MockDocumentVerificationService implements DocumentVerificationService {
  constructor(private readonly scenario?: string) {}

  async extract(
    caseId: string,
    _image: CapturedImage,
    declaredType: DocumentType,
  ): Promise<Envelope<OcrResult>> {
    return restamp(pick(caseId, declaredType, this.scenario).result.ocr, caseId);
  }
}

export class MockValidationService implements ValidationService {
  constructor(private readonly scenario?: string) {}

  async validate(
    caseId: string,
    _ocr: Envelope<OcrResult>,
    declaredType: DocumentType,
  ): Promise<Envelope<ValidationResult>> {
    return restamp(pick(caseId, declaredType, this.scenario).result.validation, caseId);
  }
}

export class MockFaceVerificationService implements FaceVerificationService {
  constructor(private readonly scenario?: string) {}

  async verify(
    caseId: string,
    _documentImage: CapturedImage,
    _personImage: CapturedImage,
  ): Promise<Envelope<FaceVerificationResult>> {
    return restamp(pick(caseId, 'passport', this.scenario).result.face_verification, caseId);
  }
}

/**
 * MOCK DINOv2 tamper detection.
 *
 * The replaceable boundary this whole integration is built around. When the real
 * model exists it becomes:
 *
 *     MockDocumentForensicsService  ->  DinoV2DocumentForensicsService
 *
 * and nothing above changes — not the risk engine, not the case schema, not the
 * database, not a single screen. The scenario data itself lives in the Python
 * mock (`contracts/python/ssb_contracts/services/forensics_mock.py`) so both
 * sides of the system exercise the same eight states.
 */
export class MockDocumentForensicsService implements DocumentForensicsService {
  constructor(private readonly scenario?: string) {}

  async analyse(
    caseId: string,
    _image: CapturedImage,
    declaredType: DocumentType,
  ): Promise<Envelope<DocumentForensicsResult>> {
    return restamp(pick(caseId, declaredType, this.scenario).result.document_forensics, caseId);
  }
}

/**
 * PatchCore is not implemented, so this always reports NOT_AVAILABLE. It is a
 * real implementation of the interface rather than a stub, so the day the module
 * lands the only change is which class the registry binds.
 */
export class UnavailableAnomalyService implements AnomalyService {
  async analyse(
    caseId: string,
    _image: CapturedImage,
    _declaredType: DocumentType,
  ): Promise<Envelope<AnomalyResult>> {
    return {
      schema_version: '1.0',
      case_id: caseId,
      module: 'anomaly',
      status: 'NOT_AVAILABLE',
      model_version: 'not-available',
      timestamp: nowIso(),
      result: null,
      errors: [
        {
          code: 'ANOMALY_NOT_IMPLEMENTED',
          message:
            'Anomaly detection (PatchCore) is not implemented. This document has ' +
            'not been compared against a reference distribution.',
          retryable: false,
        },
      ],
    };
  }
}

export class MockRiskService implements RiskService {
  constructor(private readonly scenario?: string) {}

  async fuse(
    caseId: string,
    _evidence: Parameters<RiskService['fuse']>[1],
  ): Promise<Envelope<RiskResult>> {
    // Deliberately replays the fused result rather than computing one: fusion is
    // backend policy, and a second implementation here would be free to drift
    // from the engine that ships.
    return restamp(pick(caseId, 'passport', this.scenario).result.risk, caseId);
  }
}
