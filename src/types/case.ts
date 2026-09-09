import type { DocumentType, RiskLevel, ScreeningCaseResult } from '@/contracts';

import type { CaseId, IsoDateTime } from './common';
import type { DocumentRecord, PersonCaptureRecord } from './document';

/**
 * The eight stages of the screening pipeline, in execution order.
 *
 * These are a *progress* concept, owned by the application: they describe what
 * the officer is watching happen. The findings themselves arrive as contract
 * envelopes on `ScreeningCase.result`.
 */
export type ScreeningStageId =
  | 'DOCUMENT_DETECTION'
  | 'DOCUMENT_PROCESSING'
  | 'OCR_MRZ'
  | 'RULE_VALIDATION'
  | 'FACE_VERIFICATION'
  | 'DOCUMENT_FORENSICS'
  | 'ANOMALY_ANALYSIS'
  | 'RISK_ASSESSMENT';

export const SCREENING_STAGE_ORDER: readonly ScreeningStageId[] = [
  'DOCUMENT_DETECTION',
  'DOCUMENT_PROCESSING',
  'OCR_MRZ',
  'RULE_VALIDATION',
  'FACE_VERIFICATION',
  'DOCUMENT_FORENSICS',
  'ANOMALY_ANALYSIS',
  'RISK_ASSESSMENT',
] as const;

/**
 * `NOT_AVAILABLE` is distinct from `FAILED`: the first means the stage never
 * ran (not implemented, or unsupported for this document type), the second that
 * it ran and could not finish. Neither is an adverse finding.
 */
export type StageStatus =
  | 'WAITING'
  | 'PROCESSING'
  | 'COMPLETED'
  | 'WARNING'
  | 'FAILED'
  | 'NOT_AVAILABLE';

export interface ScreeningStageState {
  id: ScreeningStageId;
  status: StageStatus;
  /** 0..1 within this stage. Only meaningful while PROCESSING. */
  progress: number;
  /** One-line result once the stage settles. */
  detail: string | null;
  startedAt: IsoDateTime | null;
  completedAt: IsoDateTime | null;
  /** Officer-facing text. Present when status is FAILED or NOT_AVAILABLE. */
  error: string | null;
}

/** Where a case sits in the officer's workflow. */
export type CaseStatus =
  | 'DRAFT'
  | 'CAPTURING'
  | 'SCREENING'
  | 'AWAITING_DECISION'
  | 'COMPLETED'
  | 'ABANDONED';

export type OfficerDecisionType = 'CLEAR' | 'HOLD' | 'ESCALATE';

export interface OfficerDecision {
  id: string;
  caseId: CaseId;
  decision: OfficerDecisionType;
  remarks: string;
  officerId: string;
  officerName: string;
  decidedAt: IsoDateTime;
  /**
   * The assessment shown to the officer at the moment they decided, retained so
   * a later model or threshold change cannot retroactively alter what they were
   * told. Null when the screening produced no risk result at all.
   */
  riskLevelAtDecision: RiskLevel | null;
  riskScoreAtDecision: number | null;
  /** True when the officer's decision diverges from the system recommendation. */
  divergedFromRecommendation: boolean;
}

export type AuditEventType =
  | 'LOGIN'
  | 'LOGOUT'
  | 'CASE_CREATED'
  | 'DOCUMENT_TYPE_SELECTED'
  | 'DOCUMENT_CAPTURED'
  | 'DOCUMENT_CONFIRMED'
  | 'PERSON_CAPTURED'
  | 'SCREENING_STARTED'
  | 'DETECTION_COMPLETED'
  | 'OCR_COMPLETED'
  | 'VALIDATION_COMPLETED'
  | 'FACE_VERIFIED'
  | 'FORENSICS_COMPLETED'
  | 'ANOMALY_COMPLETED'
  | 'RISK_GENERATED'
  | 'MODULE_UNAVAILABLE'
  | 'SCREENING_FAILED'
  | 'OFFICER_DECISION'
  | 'CASE_SAVED'
  | 'CASE_ABANDONED'
  | 'CASE_SYNCED'
  | 'SYNC_FAILED';

export interface AuditEvent {
  id: string;
  caseId: CaseId | null;
  type: AuditEventType;
  description: string;
  actorId: string;
  actorName: string;
  occurredAt: IsoDateTime;
  /** Small, non-sensitive key/value context. Never holds biometric data. */
  metadata: Record<string, string | number | boolean>;
}

export type SyncState = 'LOCAL_ONLY' | 'PENDING' | 'SYNCING' | 'SYNCED' | 'FAILED';

export interface SyncStatus {
  state: SyncState;
  lastAttemptAt: IsoDateTime | null;
  lastSyncedAt: IsoDateTime | null;
  attempts: number;
  lastError: string | null;
}

export interface ScreeningCase {
  id: CaseId;
  status: CaseStatus;
  documentType: DocumentType;
  document: DocumentRecord | null;
  person: PersonCaptureRecord | null;
  stages: ScreeningStageState[];
  /**
   * The canonical case document, exactly as the screening service returned it.
   * The application stores and renders this; it does not build it, amend it, or
   * derive findings from the module payloads itself.
   */
  result: ScreeningCaseResult | null;
  decision: OfficerDecision | null;
  sync: SyncStatus;
  officerId: string;
  officerName: string;
  unit: string;
  postName: string;
  createdAt: IsoDateTime;
  updatedAt: IsoDateTime;
}

/** Denormalised row used by the cases list. Avoids loading full result blobs. */
export interface CaseSummary {
  id: CaseId;
  status: CaseStatus;
  documentType: DocumentType;
  /** Masked document number, e.g. `••••4821`. Never the full value. */
  maskedDocumentNumber: string | null;
  subjectName: string | null;
  riskLevel: RiskLevel | null;
  riskScore: number | null;
  decision: OfficerDecisionType | null;
  syncState: SyncState;
  officerName: string;
  createdAt: IsoDateTime;
  updatedAt: IsoDateTime;
}
