/**
 * Canonical screening contracts — TypeScript mirror.
 *
 * The wire format is defined once, in
 * `contracts/schemas/ssb-screening.schema.json`. This file and the Python
 * package under `contracts/python/ssb_contracts/` are mirrors of it, and
 * `__tests__/contracts.test.ts` fails if either drifts.
 *
 * Everything here describes what a *service* produced. Nothing in this file is
 * an application concept: the officer decision, the sync state, the audit trail
 * and the capture metadata all live in `@/types` instead, because they belong to
 * the app rather than to the inference pipeline.
 */

export const SCHEMA_VERSION = '1.0' as const;
export type SchemaVersion = typeof SCHEMA_VERSION;

/**
 * How a module fared.
 *
 * The operative distinction is between a module that produced an adverse
 * finding and one that produced nothing. `FAILED` and `NOT_AVAILABLE` are
 * absences of evidence — never findings — and no consumer may render them as
 * though a check had failed.
 */
export type ModuleStatus = 'SUCCESS' | 'PARTIAL' | 'FAILED' | 'NOT_AVAILABLE';

export type ModuleName =
  | 'ocr'
  | 'validation'
  | 'face_verification'
  | 'document_forensics'
  | 'anomaly'
  | 'risk';

/**
 * Canonical document type. Wire values are snake_case and follow the spelling
 * the Python services already use — `driving_license`, not `driving_licence`.
 * The officer declares this; nothing infers it.
 */
export type DocumentType =
  | 'passport'
  | 'visa'
  | 'driving_license'
  | 'national_id'
  | 'permit'
  | 'travel_authorization'
  | 'other';

export const DOCUMENT_TYPES: readonly DocumentType[] = [
  'passport',
  'visa',
  'driving_license',
  'national_id',
  'permit',
  'travel_authorization',
  'other',
] as const;

export interface ModuleError {
  /** Stable machine code for logs and retry logic. Never shown to an officer. */
  code: string;
  /** Plain sentence, safe to display verbatim. */
  message: string;
  retryable?: boolean;
}

/**
 * Every module response arrives in this wrapper.
 *
 * `result` is null whenever `status` is FAILED or NOT_AVAILABLE, so a consumer
 * that sees a non-success status can stop reading — there is provably nothing
 * behind it. `hasEvidence` below is the guard that makes that a type narrowing
 * rather than a convention.
 */
export interface Envelope<TResult> {
  schema_version: SchemaVersion;
  case_id: string;
  module: ModuleName;
  status: ModuleStatus;
  /** Identifies the exact implementation, including whether it is a mock. */
  model_version: string;
  timestamp: string;
  result: TResult | null;
  errors: ModuleError[];
  duration_ms?: number | null;
}

/** Narrows an envelope to one that is guaranteed to carry a result. */
export function hasEvidence<T>(
  envelope: Envelope<T>,
): envelope is Envelope<T> & { result: T } {
  return (
    (envelope.status === 'SUCCESS' || envelope.status === 'PARTIAL') &&
    envelope.result !== null
  );
}

/** `[x, y, width, height]`, normalised 0..1 against the corrected document image. */
export type BoundingBox = readonly [number, number, number, number];

// ---------------------------------------------------------------------------
// OCR
// ---------------------------------------------------------------------------

/** How a value was read off the image. */
export type OcrFieldSource =
  | 'mrz'
  | 'label_same_line'
  | 'label_next_line'
  | 'standalone_id'
  | 'qr'
  | 'barcode'
  | 'not_found';

/**
 * Which capture or code the value was accepted from — a separate axis from
 * `source`. An officer resolving a disagreement needs to know which side a
 * value came off, and a signed code carries a different authority from a label
 * match over recognised text.
 */
export type OcrFieldOrigin = 'front' | 'back' | 'mrz' | 'qr';

/**
 * Whether the sources that supplied a field agreed.
 *
 * `CONFLICT` is never a fraud finding on its own. Two captures of one document
 * disagree for ordinary reasons — glare, a fold, a single OCR substitution —
 * and the officer is holding the document. It resolves to REVIEW, never FAIL.
 */
export type OcrFieldAgreement = 'SINGLE_SOURCE' | 'AGREED' | 'CONFLICT';

export type DocumentSide = 'front' | 'back';

/** One source's reading, retained so a disagreement shows both values. */
export interface OcrFieldReading {
  origin: OcrFieldOrigin;
  value: string | null;
  source: OcrFieldSource;
  confidence?: number | null;
}

export interface OcrField {
  key: string;
  /** Null when the field was not found. Never guessed, never defaulted. */
  value: string | null;
  confidence?: number | null;
  /**
   * Provenance. MRZ-sourced values come from a checksummed fixed layout;
   * label-matched values come from a heuristic over free text.
   */
  source: OcrFieldSource;
  region?: BoundingBox | null;
  origin?: OcrFieldOrigin;
  agreement?: OcrFieldAgreement;
  /** Populated only where more than one source supplied a value. */
  readings?: OcrFieldReading[];
}

/**
 * A machine-readable code found on one side.
 *
 * `decoded` is null when a code was located but its payload could not be read —
 * an absence, not a finding.
 */
export interface MachineCode {
  side: DocumentSide;
  code_type: 'qr' | 'barcode';
  format?: string | null;
  decoded: string | null;
  detection_method?: string | null;
}

/**
 * What one capture produced. A side the officer did not capture is absent from
 * the list rather than present and empty.
 */
export interface SideEvidence {
  side: DocumentSide;
  detection: OcrDetection;
  language?: string | null;
  field_keys?: string[];
}

export interface MrzCheckDigit {
  field: string;
  observed: string;
  computed: string;
  valid: boolean;
}

export interface MrzPayload {
  present: boolean;
  format?: 'TD1' | 'TD2' | 'TD3' | 'MRVA' | 'MRVB' | 'NONE';
  lines: string[];
  check_digits: MrzCheckDigit[];
  /**
   * Null means the checksum was not evaluated at this stage — distinct from
   * false, which asserts it was tested and did not match. A consumer must not
   * collapse the two.
   */
  checksum_valid: boolean | null;
  confidence?: number | null;
}

export interface OcrDetection {
  detected: boolean;
  confidence?: number | null;
  box?: BoundingBox | null;
  correction_mode?: string | null;
  orientation_corrected?: boolean;
}

export interface OcrResult {
  document_type: DocumentType;
  fields: OcrField[];
  mrz: MrzPayload;
  /** The front capture's detection; per-side detail is in `sides`. */
  detection: OcrDetection;
  overall_confidence: number | null;
  language?: string | null;
  sides?: SideEvidence[];
  machine_codes?: MachineCode[];
}

// ---------------------------------------------------------------------------
// Validation
// ---------------------------------------------------------------------------

/**
 * `NOT_APPLICABLE` (the rule is irrelevant to this document type) and
 * `NOT_AVAILABLE` (the rule's input was missing) are kept apart on purpose.
 * Neither is a failure, and collapsing them would hide which one occurred.
 */
export type ValidationCheckStatus =
  | 'PASS'
  | 'FAIL'
  | 'REVIEW'
  | 'NOT_APPLICABLE'
  | 'NOT_AVAILABLE';

export type ValidationDecision = 'VALID' | 'REVIEW' | 'INVALID';

export interface ValidationCheck {
  rule_id: string;
  status: ValidationCheckStatus;
  message: string;
  observed?: string | null;
  expectation?: string | null;
  fields?: string[];
}

export interface ValidationSummary {
  passed: number;
  failed: number;
  review: number;
  not_applicable: number;
  not_available: number;
}

export interface ValidationResult {
  /** Never a statement about authenticity — only about the rule set. */
  decision: ValidationDecision;
  checks: ValidationCheck[];
  summary: ValidationSummary;
  rule_version: string;
}

// ---------------------------------------------------------------------------
// Face verification
// ---------------------------------------------------------------------------

export type FaceDecision = 'MATCH' | 'REVIEW' | 'NO_MATCH';

export interface FaceQualityMetrics {
  face_width_px?: number | null;
  face_height_px?: number | null;
  brightness?: number | null;
  blur_score?: number | null;
  yaw_proxy?: number | null;
  roll_deg?: number | null;
}

export interface FaceQualityChecks {
  face_size_ok?: boolean | null;
  brightness_ok?: boolean | null;
  blur_ok?: boolean | null;
  pose_ok?: boolean | null;
}

export interface FaceQuality {
  acceptable: boolean | null;
  /**
   * Model-provided quality score. NULL for the current ArcFace pipeline, which
   * reports gates and raw measurements rather than a single figure. Deriving a
   * number from those would be an invented confidence, so the UI renders
   * `acceptable` and the metrics instead.
   */
  score: number | null;
  metrics?: FaceQualityMetrics | null;
  checks?: FaceQualityChecks | null;
}

export interface FaceVerificationResult {
  /**
   * RAW cosine similarity in [-1, 1] between two 512-D ArcFace embeddings.
   * NOT a probability and NOT a percentage. Never rescale it, and never render
   * it with a percent sign.
   */
  similarity: number;
  decision: FaceDecision;
  /** The boundaries in force when this result was produced. */
  thresholds: { match: number; review: number };
  quality: { document_face: FaceQuality; live_face: FaceQuality };
  embedding_dim?: number | null;
}

// ---------------------------------------------------------------------------
// Document forensics
// ---------------------------------------------------------------------------

export type ManipulationType =
  | 'PHOTO_REPLACEMENT'
  | 'TEXT_MANIPULATION'
  | 'STAMP_SIGNATURE_MANIPULATION'
  | 'COPY_PASTE_SPLICING'
  | 'OTHER'
  | 'NONE';

export interface SuspiciousRegion {
  bbox: BoundingBox;
  score: number;
  note?: string | null;
}

export interface DocumentForensicsResult {
  tampered: boolean;
  /** Classification-head score. A model output, not a probability of fraud. */
  tamper_score: number;
  manipulation_type: ManipulationType;
  type_score?: number | null;
  /**
   * May legitimately be empty even when `tampered` is true: the classifier can
   * fire without the localiser resolving a region. An empty list is never
   * evidence of authenticity.
   */
  suspicious_regions: SuspiciousRegion[];
}

// ---------------------------------------------------------------------------
// Anomaly (PatchCore — not implemented)
// ---------------------------------------------------------------------------

export interface AnomalyResult {
  anomaly_score: number;
  anomalous: boolean;
  threshold?: number | null;
  reference_set_size?: number | null;
  suspicious_regions: SuspiciousRegion[];
}

// ---------------------------------------------------------------------------
// Risk
// ---------------------------------------------------------------------------

export type RiskLevel = 'LOW' | 'REVIEW' | 'HIGH';
export type Severity = 'NONE' | 'LOW' | 'MEDIUM' | 'HIGH';

export interface RiskContributor {
  source: ModuleName;
  /** The module's own vocabulary: NO_MATCH, INVALID, TAMPERED, NOT_AVAILABLE. */
  signal: string;
  impact: string;
  severity: Severity;
  /** Null for contributors excluded from scoring. */
  weight: number | null;
  /** False when the module produced no evidence and was not scored. */
  counted: boolean;
}

export interface RiskResult {
  /** Normalised 0..1. Defined by configuration, not measured from data. */
  risk_score: number;
  risk_level: RiskLevel;
  contributors: RiskContributor[];
  bands?: { review_at_or_above: number; high_at_or_above: number };
  /** Fraction of the configured weight that was actually available. */
  evidence_coverage: number;
  escalations?: string[];
  narrative?: string;
  engine_version: string;
  config_version?: string;
}

// ---------------------------------------------------------------------------
// Case-level result
// ---------------------------------------------------------------------------

export interface EvidenceItem {
  module: ModuleName;
  status: ModuleStatus;
  severity: Severity;
  headline: string;
  detail: string;
}

/**
 * What the officer-facing application consumes.
 *
 * Assembled by the backend, never by the frontend. The app renders this
 * document; it does not derive findings from the module payloads itself, does
 * not decide what a missing module means, and does not rank the evidence.
 */
export interface ScreeningCaseResult {
  schema_version: SchemaVersion;
  case_id: string;
  document_type: DocumentType;
  ocr: Envelope<OcrResult>;
  validation: Envelope<ValidationResult>;
  face_verification: Envelope<FaceVerificationResult>;
  document_forensics: Envelope<DocumentForensicsResult>;
  anomaly: Envelope<AnomalyResult>;
  risk: Envelope<RiskResult>;
  evidence: EvidenceItem[];
  generated_at: string;
}

/** Every module envelope on a case, in pipeline order. */
export function moduleEnvelopes(
  result: ScreeningCaseResult,
): { module: ModuleName; envelope: Envelope<unknown> }[] {
  return [
    { module: 'ocr' as const, envelope: result.ocr },
    { module: 'validation' as const, envelope: result.validation },
    { module: 'face_verification' as const, envelope: result.face_verification },
    { module: 'document_forensics' as const, envelope: result.document_forensics },
    { module: 'anomaly' as const, envelope: result.anomaly },
    { module: 'risk' as const, envelope: result.risk },
  ];
}
