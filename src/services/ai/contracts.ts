import type {
  AnomalyResult,
  DocumentForensicsResult,
  DocumentType,
  Envelope,
  FaceVerificationResult,
  OcrResult,
  RiskResult,
  ScreeningCaseResult,
  ValidationResult,
} from '@/contracts';
import type { CapturedImage } from '@/types/document';
import type { ScreeningStageId } from '@/types/case';

/**
 * The service boundary.
 *
 * Everything the application knows about inference is declared here. No screen,
 * store or repository names an implementation, so swapping the offline mock for
 * an HTTP client — or for on-device runtimes at the edge — is a change to
 * `registry.ts` alone.
 *
 * Every method returns a canonical `Envelope`. Failure is a value, not an
 * exception: a module that could not run resolves with `status: 'FAILED'` so one
 * module going down cannot take the screening with it. These interfaces reject
 * only for genuinely exceptional conditions such as cancellation.
 */

export interface InferenceOptions {
  /** Cancels in-flight work when the officer leaves the screening. */
  signal?: AbortSignal;
  /** 0..1 progress within the stage, for the pipeline display. */
  onProgress?: (progress: number) => void;
}

/** Extraction: detection, rectification, OCR and MRZ reading. */
export interface DocumentVerificationService {
  extract(
    caseId: string,
    image: CapturedImage,
    declaredType: DocumentType,
    options?: InferenceOptions,
  ): Promise<Envelope<OcrResult>>;
}

/** Deterministic rule checking over the extracted fields. */
export interface ValidationService {
  validate(
    caseId: string,
    ocr: Envelope<OcrResult>,
    declaredType: DocumentType,
    options?: InferenceOptions,
  ): Promise<Envelope<ValidationResult>>;
}

/** 1:1 comparison of the document portrait against the live capture. */
export interface FaceVerificationService {
  verify(
    caseId: string,
    documentImage: CapturedImage,
    personImage: CapturedImage,
    options?: InferenceOptions,
  ): Promise<Envelope<FaceVerificationResult>>;
}

/**
 * Tamper detection.
 *
 * The production implementation will be DINOv2 ViT-B/14 with a forensic
 * classification head and a patch localisation head. Until it exists, a mock
 * satisfies this interface and emits the identical contract. Replacing it
 * changes nothing above this line.
 */
export interface DocumentForensicsService {
  analyse(
    caseId: string,
    image: CapturedImage,
    declaredType: DocumentType,
    options?: InferenceOptions,
  ): Promise<Envelope<DocumentForensicsResult>>;
}

/**
 * Unsupervised deviation from the genuine-document distribution.
 *
 * PatchCore is not implemented. The interface exists so the module can be added
 * without a contract change; every current implementation resolves with
 * `status: 'NOT_AVAILABLE'`.
 */
export interface AnomalyService {
  analyse(
    caseId: string,
    image: CapturedImage,
    declaredType: DocumentType,
    options?: InferenceOptions,
  ): Promise<Envelope<AnomalyResult>>;
}

/** Evidence fusion. Consumes module envelopes, produces a graded assessment. */
export interface RiskService {
  fuse(
    caseId: string,
    evidence: {
      ocr: Envelope<OcrResult>;
      validation: Envelope<ValidationResult>;
      face_verification: Envelope<FaceVerificationResult>;
      document_forensics: Envelope<DocumentForensicsResult>;
      anomaly: Envelope<AnomalyResult>;
    },
    options?: InferenceOptions,
  ): Promise<Envelope<RiskResult>>;
}

/** Reported as the pipeline advances, so the officer sees where the run is. */
export interface StageEvent {
  stage: ScreeningStageId;
  status: 'PROCESSING' | 'COMPLETED' | 'WARNING' | 'FAILED' | 'NOT_AVAILABLE';
  progress: number;
  detail: string | null;
  error: string | null;
}

export interface ScreeningRequest {
  caseId: string;
  /** Declared by the officer. Nothing infers it. */
  documentType: DocumentType;
  documentImage: CapturedImage;
  personImage: CapturedImage;
  signal?: AbortSignal;
  onStage?: (event: StageEvent) => void;
}

/**
 * The interface the application actually uses.
 *
 * One call returns the assembled case document. Orchestration and fusion are
 * backend responsibilities: if the app sequenced the modules itself it would
 * have to decide what a missing one means, and that is precisely the policy this
 * integration moved out of the frontend.
 */
export interface ScreeningService {
  screen(request: ScreeningRequest): Promise<ScreeningCaseResult>;
}

/** Every module service, for a deployment that calls them individually. */
export interface ScreeningModuleServices {
  documentVerification: DocumentVerificationService;
  validation: ValidationService;
  faceVerification: FaceVerificationService;
  documentForensics: DocumentForensicsService;
  anomaly: AnomalyService;
  risk: RiskService;
}
