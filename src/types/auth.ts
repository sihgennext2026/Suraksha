export type OfficerRole = 'OFFICER' | 'SUPERVISOR' | 'ADMINISTRATOR';

export interface AuthenticatedUser {
  id: string;
  /** Officer identification number used at sign-in. */
  officerId: string;
  name: string;
  rank: string;
  role: OfficerRole;
  unit: string;
  postName: string;
  deviceId: string;
}

export interface AuthSession {
  user: AuthenticatedUser;
  issuedAt: string;
  expiresAt: string;
  /** True when the credential was verified against the on-device enrolment
   *  record rather than the authentication service. */
  offlineVerified: boolean;
}

/**
 * Capabilities are checked in the UI even though enforcement will ultimately be
 * server-side. Keeps permission-dependent affordances honest from day one.
 */
export type Permission =
  | 'SCREENING_CREATE'
  | 'CASE_VIEW_OWN'
  | 'CASE_VIEW_UNIT'
  | 'DECISION_CLEAR'
  | 'DECISION_HOLD'
  | 'DECISION_ESCALATE'
  | 'CASE_REOPEN'
  | 'SYNC_FORCE'
  | 'SETTINGS_MANAGE_DEVICE'
  | 'AUDIT_EXPORT';

export const ROLE_PERMISSIONS: Record<OfficerRole, readonly Permission[]> = {
  OFFICER: [
    'SCREENING_CREATE',
    'CASE_VIEW_OWN',
    'DECISION_CLEAR',
    'DECISION_HOLD',
    'DECISION_ESCALATE',
  ],
  SUPERVISOR: [
    'SCREENING_CREATE',
    'CASE_VIEW_OWN',
    'CASE_VIEW_UNIT',
    'DECISION_CLEAR',
    'DECISION_HOLD',
    'DECISION_ESCALATE',
    'CASE_REOPEN',
    'SYNC_FORCE',
    'AUDIT_EXPORT',
  ],
  ADMINISTRATOR: [
    'SCREENING_CREATE',
    'CASE_VIEW_OWN',
    'CASE_VIEW_UNIT',
    'DECISION_CLEAR',
    'DECISION_HOLD',
    'DECISION_ESCALATE',
    'CASE_REOPEN',
    'SYNC_FORCE',
    'SETTINGS_MANAGE_DEVICE',
    'AUDIT_EXPORT',
  ],
} as const;
