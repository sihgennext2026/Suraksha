import * as Crypto from 'expo-crypto';

import { SECURE_KEYS } from '@/constants/storage';
import { userRepository } from '@/db';
import { secureStore } from '@/services/storage';
import type { AuthSession, AuthenticatedUser, OfficerRole } from '@/types';
import { nowIso } from '@/utils/date';
import { failure } from '@/utils/errors';
import { newId } from '@/utils/id';

/**
 * Authentication.
 *
 * The design constraint that shapes this module is that a border post may have
 * no connectivity for days, so sign-in cannot depend on a network round trip.
 * The device holds an enrolment record for each officer authorised on it,
 * containing a salted SHA-256 verifier of their PIN — never the PIN itself, and
 * never anything that could be replayed against the central service.
 *
 * TODO(production):
 *  - Replace SHA-256 with a memory-hard KDF (Argon2id) via a native module; a
 *    single hash round is not adequate against an attacker with the device.
 *  - Enrolment records must be provisioned and revoked by the device management
 *    service, with an expiry that forces periodic re-authentication online.
 *  - Add a failed-attempt lockout backed by a monotonic clock the officer
 *    cannot reset by changing the device time.
 */

interface EnrolmentRecord {
  officerId: string;
  /** Hex SHA-256 of `salt + pin`. The PIN itself is never persisted. */
  verifier: string;
  salt: string;
  user: AuthenticatedUser;
  enrolledAt: string;
}

interface EnrolmentStore {
  deviceId: string;
  records: EnrolmentRecord[];
}

/** Session lifetime. Short enough that a mislaid device is not an open door. */
const SESSION_DURATION_MS = 12 * 60 * 60 * 1000;

export interface Credentials {
  officerId: string;
  pin: string;
}

export interface AuthService {
  /** Provisions this device and its authorised officers on first launch. */
  ensureDeviceEnrolled(): Promise<string>;
  signIn(credentials: Credentials): Promise<AuthSession>;
  signOut(): Promise<void>;
  /** Returns the stored session when it is still valid, otherwise null. */
  restoreSession(): Promise<AuthSession | null>;
  /** Officers enrolled on this device, for the sign-in hint on the login screen. */
  enrolledOfficers(): Promise<AuthenticatedUser[]>;
}

async function hashPin(pin: string, salt: string): Promise<string> {
  return Crypto.digestStringAsync(Crypto.CryptoDigestAlgorithm.SHA256, `${salt}:${pin}`);
}

function randomSalt(): string {
  const bytes = Crypto.getRandomBytes(16);
  return Array.from(bytes)
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('');
}

/**
 * The officers provisioned on a demonstration device.
 *
 * In production this list arrives from the device management service at
 * enrolment. The PINs here exist only so the prototype can be signed into; they
 * are hashed with a per-record salt before anything is written to storage, so
 * the stored form is the same shape production will use.
 */
const SEED_OFFICERS: { user: Omit<AuthenticatedUser, 'deviceId'>; pin: string }[] = [
  {
    user: {
      id: 'usr-officer-1',
      officerId: 'SSB4471',
      name: 'Krishna Raj',
      rank: 'Assistant Commandant',
      role: 'OFFICER' as OfficerRole,
      unit: '41 Bn SSB',
      postName: 'Raxaul ICP',
    },
    pin: '4471',
  },
  {
    user: {
      id: 'usr-supervisor-1',
      officerId: 'SSB2210',
      name: 'Meera Nair',
      rank: 'Deputy Commandant',
      role: 'SUPERVISOR' as OfficerRole,
      unit: '41 Bn SSB',
      postName: 'Raxaul ICP',
    },
    pin: '2210',
  },
  {
    user: {
      id: 'usr-admin-1',
      officerId: 'SSB1000',
      name: 'Arun Bhatt',
      rank: 'Commandant',
      role: 'ADMINISTRATOR' as OfficerRole,
      unit: '41 Bn SSB',
      postName: 'Raxaul ICP',
    },
    pin: '1000',
  },
];

class DeviceAuthService implements AuthService {
  async ensureDeviceEnrolled(): Promise<string> {
    const existing = await secureStore.getJson<EnrolmentStore>(SECURE_KEYS.enrolment);
    if (existing) return existing.deviceId;

    const deviceId = `SSB-DEV-${newId().slice(0, 8).toUpperCase()}`;
    const records: EnrolmentRecord[] = [];

    for (const seed of SEED_OFFICERS) {
      const salt = randomSalt();
      const user: AuthenticatedUser = { ...seed.user, deviceId };
      records.push({
        officerId: seed.user.officerId,
        salt,
        verifier: await hashPin(seed.pin, salt),
        user,
        enrolledAt: nowIso(),
      });
      await userRepository.upsert(user);
    }

    await secureStore.setJson<EnrolmentStore>(SECURE_KEYS.enrolment, { deviceId, records });
    await secureStore.set(SECURE_KEYS.deviceId, deviceId);
    return deviceId;
  }

  async signIn({ officerId, pin }: Credentials): Promise<AuthSession> {
    const store = await secureStore.getJson<EnrolmentStore>(SECURE_KEYS.enrolment);
    if (!store) {
      throw failure(
        'DEVICE_NOT_ENROLLED',
        'This device has not been set up for screening. Complete device setup before signing in.',
        false,
      );
    }

    const normalisedId = officerId.trim().toUpperCase();
    const record = store.records.find((entry) => entry.officerId === normalisedId);

    // The same message is returned whether the officer ID is unknown or the PIN
    // is wrong, so the screen cannot be used to enumerate valid officer IDs.
    const rejection = failure(
      'INVALID_CREDENTIALS',
      'That officer ID and PIN do not match a record on this device.',
      true,
    );
    if (!record) throw rejection;

    const candidate = await hashPin(pin, record.salt);
    if (candidate !== record.verifier) throw rejection;

    const issuedAt = new Date();
    const session: AuthSession = {
      user: record.user,
      issuedAt: issuedAt.toISOString(),
      expiresAt: new Date(issuedAt.getTime() + SESSION_DURATION_MS).toISOString(),
      // Verified against the on-device enrolment record rather than the central
      // service. Surfaced on the login screen so officers know which it was.
      offlineVerified: true,
    };

    await secureStore.setJson(SECURE_KEYS.session, session);
    await userRepository.recordLogin(record.officerId);
    return session;
  }

  async signOut(): Promise<void> {
    await secureStore.remove(SECURE_KEYS.session);
  }

  async restoreSession(): Promise<AuthSession | null> {
    const session = await secureStore.getJson<AuthSession>(SECURE_KEYS.session);
    if (!session) return null;
    if (new Date(session.expiresAt).getTime() <= Date.now()) {
      await secureStore.remove(SECURE_KEYS.session);
      return null;
    }
    return session;
  }

  async enrolledOfficers(): Promise<AuthenticatedUser[]> {
    const store = await secureStore.getJson<EnrolmentStore>(SECURE_KEYS.enrolment);
    return store?.records.map((record) => record.user) ?? [];
  }
}

export const authService: AuthService = new DeviceAuthService();

/**
 * The seeded sign-in credentials, for the demonstration hint on the login
 * screen. Exported separately so nothing in the authentication path itself can
 * accidentally read a PIN.
 */
export const DEMO_CREDENTIALS = SEED_OFFICERS.map((seed) => ({
  officerId: seed.user.officerId,
  name: seed.user.name,
  role: seed.user.role,
  pin: seed.pin,
}));
