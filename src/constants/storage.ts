/**
 * Keys are namespaced so a future migration can enumerate and clear a single
 * generation of stored data without touching anything else.
 */
const NS = 'ssb.suraksha.v1';

/** Written to expo-secure-store. Hardware-backed where the device supports it. */
export const SECURE_KEYS = {
  /** Serialised AuthSession. Cleared on sign-out. */
  session: `${NS}.secure.session`,
  /** Per-device enrolment record, including the credential verifier. */
  enrolment: `${NS}.secure.enrolment`,
  /** Stable device identifier issued at setup. */
  deviceId: `${NS}.secure.deviceId`,
} as const;

/** Written to the general key/value store. Non-sensitive only. */
export const STORAGE_KEYS = {
  themePreference: `${NS}.settings.theme`,
  settings: `${NS}.settings.general`,
  /** Snapshot of an in-progress screening, for crash/restart recovery. */
  activeScreening: `${NS}.screening.active`,
  schemaVersion: `${NS}.db.schemaVersion`,
  lastSyncAt: `${NS}.sync.lastSyncAt`,
} as const;

export const DATABASE_NAME = 'ssb-suraksha.db';

/** Sub-directory of the document directory holding retained case imagery. */
export const CASE_MEDIA_DIRECTORY = 'case-media';
