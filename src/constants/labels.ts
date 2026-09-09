import type {
  FaceDecision,
  ManipulationType,
  ModuleStatus,
  RiskLevel,
  Severity,
  ValidationCheckStatus,
  ValidationDecision,
} from '@/contracts';
import type {
  CaseStatus,
  OfficerDecisionType,
  StageStatus,
  SyncState,
} from '@/types/case';
import type { OfficerRole } from '@/types/auth';

/**
 * Every status in the application resolves to a label *and* a glyph.
 *
 * Status is never conveyed by colour alone — the glyph and the label carry it
 * independently, which is what makes the interface usable in direct sunlight,
 * in greyscale, and with a colour vision deficiency.
 *
 * The wording is evidence-oriented throughout. Nothing in this file tells an
 * officer a document is fake; findings are described as findings, and the
 * decision stays theirs.
 */
export interface StatusPresentation {
  label: string;
  /** Text glyph rendered alongside the label. */
  glyph: string;
  /** Sentence announced by assistive technology. */
  a11yLabel: string;
}

/**
 * Module status. `NOT_AVAILABLE` and `FAILED` read as absences, never as
 * failures of the document — that distinction is the whole point of the state.
 */
export const MODULE_STATUS_PRESENTATION: Record<ModuleStatus, StatusPresentation> = {
  SUCCESS: { label: 'Completed', glyph: '✓', a11yLabel: 'Completed' },
  PARTIAL: { label: 'Incomplete', glyph: '!', a11yLabel: 'Completed with a gap' },
  FAILED: { label: 'Did not run', glyph: '–', a11yLabel: 'This check could not run' },
  NOT_AVAILABLE: {
    label: 'Not available',
    glyph: '–',
    a11yLabel: 'This check was not available',
  },
};

export const SEVERITY_PRESENTATION: Record<Severity, StatusPresentation> = {
  NONE: { label: 'No finding', glyph: '✓', a11yLabel: 'No finding' },
  LOW: { label: 'Minor', glyph: '·', a11yLabel: 'Minor finding' },
  MEDIUM: { label: 'Review', glyph: '!', a11yLabel: 'Finding requiring review' },
  HIGH: { label: 'Significant', glyph: '✕', a11yLabel: 'Significant finding' },
};

export const RISK_LEVEL_PRESENTATION: Record<RiskLevel, StatusPresentation> = {
  LOW: { label: 'Low risk', glyph: '✓', a11yLabel: 'Low risk' },
  REVIEW: {
    label: 'Review required',
    glyph: '!',
    a11yLabel: 'Review required by an officer',
  },
  HIGH: { label: 'High risk', glyph: '✕', a11yLabel: 'High risk' },
};

export const STAGE_STATUS_PRESENTATION: Record<StageStatus, StatusPresentation> = {
  WAITING: { label: 'Waiting', glyph: '○', a11yLabel: 'Waiting' },
  PROCESSING: { label: 'Processing', glyph: '●', a11yLabel: 'Processing' },
  COMPLETED: { label: 'Completed', glyph: '✓', a11yLabel: 'Completed' },
  WARNING: { label: 'Finding', glyph: '!', a11yLabel: 'Completed with a finding' },
  FAILED: { label: 'Did not run', glyph: '–', a11yLabel: 'This stage could not run' },
  NOT_AVAILABLE: {
    label: 'Not available',
    glyph: '–',
    a11yLabel: 'This stage was not available',
  },
};

export const SYNC_STATE_PRESENTATION: Record<SyncState, StatusPresentation> = {
  LOCAL_ONLY: { label: 'Local only', glyph: '□', a11yLabel: 'Stored on this device only' },
  PENDING: { label: 'Pending sync', glyph: '↑', a11yLabel: 'Pending synchronisation' },
  SYNCING: { label: 'Syncing', glyph: '⟳', a11yLabel: 'Synchronising now' },
  SYNCED: { label: 'Synced', glyph: '✓', a11yLabel: 'Synchronised' },
  FAILED: { label: 'Sync failed', glyph: '✕', a11yLabel: 'Synchronisation failed' },
};

export const CASE_STATUS_PRESENTATION: Record<CaseStatus, StatusPresentation> = {
  DRAFT: { label: 'Draft', glyph: '□', a11yLabel: 'Draft' },
  CAPTURING: { label: 'Capturing', glyph: '◐', a11yLabel: 'Capture in progress' },
  SCREENING: { label: 'Screening', glyph: '●', a11yLabel: 'Screening in progress' },
  AWAITING_DECISION: {
    label: 'Awaiting decision',
    glyph: '!',
    a11yLabel: 'Awaiting officer decision',
  },
  COMPLETED: { label: 'Completed', glyph: '✓', a11yLabel: 'Completed' },
  ABANDONED: { label: 'Abandoned', glyph: '–', a11yLabel: 'Abandoned' },
};

export const DECISION_PRESENTATION: Record<OfficerDecisionType, StatusPresentation> = {
  CLEAR: { label: 'Cleared', glyph: '✓', a11yLabel: 'Cleared by officer' },
  HOLD: { label: 'Held for review', glyph: '!', a11yLabel: 'Held for review by officer' },
  ESCALATE: { label: 'Escalated', glyph: '▲', a11yLabel: 'Escalated by officer' },
};

export const FACE_DECISION_PRESENTATION: Record<FaceDecision, StatusPresentation> = {
  MATCH: { label: 'Match', glyph: '✓', a11yLabel: 'Faces match' },
  REVIEW: { label: 'Review required', glyph: '!', a11yLabel: 'Face comparison inconclusive' },
  NO_MATCH: { label: 'No match', glyph: '✕', a11yLabel: 'Faces do not match' },
};

export const VALIDATION_DECISION_PRESENTATION: Record<
  ValidationDecision,
  StatusPresentation
> = {
  VALID: { label: 'All rules passed', glyph: '✓', a11yLabel: 'All applicable rules passed' },
  REVIEW: { label: 'Inconclusive', glyph: '!', a11yLabel: 'One or more rules were inconclusive' },
  INVALID: { label: 'Rules failed', glyph: '✕', a11yLabel: 'One or more rules failed' },
};

export const VALIDATION_STATUS_PRESENTATION: Record<
  ValidationCheckStatus,
  StatusPresentation
> = {
  PASS: { label: 'Pass', glyph: '✓', a11yLabel: 'Rule passed' },
  FAIL: { label: 'Fail', glyph: '✕', a11yLabel: 'Rule failed' },
  REVIEW: { label: 'Inconclusive', glyph: '!', a11yLabel: 'Rule was inconclusive' },
  NOT_APPLICABLE: {
    label: 'Not applicable',
    glyph: '–',
    a11yLabel: 'Rule does not apply to this document type',
  },
  NOT_AVAILABLE: {
    label: 'Not evaluated',
    glyph: '·',
    a11yLabel: 'Rule could not be evaluated because its input was missing',
  },
};

/**
 * Manipulation classes. Worded as observations rather than accusations: the
 * model reports a pattern, the officer decides what it means.
 */
export const MANIPULATION_TYPE_LABELS: Record<ManipulationType, string> = {
  PHOTO_REPLACEMENT: 'Photo replacement',
  TEXT_MANIPULATION: 'Text manipulation',
  STAMP_SIGNATURE_MANIPULATION: 'Stamp or signature manipulation',
  COPY_PASTE_SPLICING: 'Copy-paste or splicing',
  OTHER: 'Unrecognised manipulation',
  NONE: 'No manipulation detected',
};

export const ROLE_LABEL: Record<OfficerRole, string> = {
  OFFICER: 'Officer',
  SUPERVISOR: 'Supervisor',
  ADMINISTRATOR: 'Administrator',
};
