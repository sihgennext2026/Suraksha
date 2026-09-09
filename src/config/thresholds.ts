import rawThresholds from '../../contracts/config/thresholds.json';

/**
 * Thresholds, bands and weights.
 *
 * This module does not restate any number: it imports
 * `contracts/config/thresholds.json` directly, which is the single source of
 * truth the Python services read as well. There is deliberately no hand-written
 * mirror to drift out of date.
 *
 * The application uses these values for *display only* — to show an officer
 * which boundary a score fell against. It never classifies with them. Deciding
 * MATCH/REVIEW/NO_MATCH, VALID/INVALID or LOW/REVIEW/HIGH is a service
 * responsibility, and the result carries the decision already made.
 */

interface RawFace {
  match: number;
  review: number;
  source: string;
  calibration: string;
  confidence: string;
}

interface RawForensics {
  tampered_at_or_above: number;
  review_at_or_above: number;
  region_reporting_floor: number;
  confidence: string;
}

interface RawRisk {
  weights: Record<string, number>;
  bands: { review_at_or_above: number; high_at_or_above: number };
  minimum_evidence_weight: number;
  confidence: string;
}

interface RawConfig {
  config_version: string;
  face_verification: RawFace;
  document_forensics: RawForensics;
  risk_fusion: RawRisk;
  ocr: { low_confidence_below: number; review_confidence_below: number };
  anomaly: { anomalous_at_or_above: number | null };
}

const config = rawThresholds as unknown as RawConfig;

export const CONFIG_VERSION = config.config_version;

/**
 * Raw ArcFace cosine-similarity boundaries.
 *
 * These replace the application's earlier `matchAbove: 0.85` /
 * `noMatchBelow: 0.60` assumption, which was on an entirely different scale —
 * those numbers treated similarity as a 0..1 confidence, whereas the model
 * emits a cosine similarity where 0.30 is a normal match boundary. Feeding real
 * scores into the old assumption would have read almost every genuine subject
 * as a non-match.
 */
export const FACE_THRESHOLDS = {
  match: config.face_verification.match,
  review: config.face_verification.review,
} as const;

/** Provenance for the "Analysis details" sheet, so a number is never quoted bare. */
export const FACE_THRESHOLD_PROVENANCE = {
  source: config.face_verification.source,
  calibration: config.face_verification.calibration,
  confidence: config.face_verification.confidence,
} as const;

export const FORENSICS_THRESHOLDS = {
  tamperedAtOrAbove: config.document_forensics.tampered_at_or_above,
  reviewAtOrAbove: config.document_forensics.review_at_or_above,
  regionReportingFloor: config.document_forensics.region_reporting_floor,
} as const;

export const RISK_BANDS = {
  reviewAtOrAbove: config.risk_fusion.bands.review_at_or_above,
  highAtOrAbove: config.risk_fusion.bands.high_at_or_above,
} as const;

export const RISK_WEIGHTS: Readonly<Record<string, number>> = config.risk_fusion.weights;

export const MINIMUM_EVIDENCE_WEIGHT = config.risk_fusion.minimum_evidence_weight;

export const OCR_THRESHOLDS = {
  lowConfidenceBelow: config.ocr.low_confidence_below,
  reviewConfidenceBelow: config.ocr.review_confidence_below,
} as const;

/** Null: PatchCore is not implemented, so no value has been derived. */
export const ANOMALY_THRESHOLD: number | null = config.anomaly.anomalous_at_or_above;

/**
 * Every threshold block carries a note on how much it can be relied on. Shown
 * verbatim in analysis details so no figure in this application is ever
 * presented as more settled than it is.
 */
export const THRESHOLD_CONFIDENCE_NOTES = {
  face: config.face_verification.confidence,
  forensics: config.document_forensics.confidence,
  risk: config.risk_fusion.confidence,
} as const;
