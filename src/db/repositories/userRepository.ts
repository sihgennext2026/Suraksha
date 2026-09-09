import type { AuthenticatedUser, OfficerRole } from '@/types';
import { nowIso } from '@/utils/date';

import { getDatabase } from '../client';

interface UserRow {
  id: string;
  officer_id: string;
  name: string;
  rank: string;
  role: string;
  unit: string;
  post_name: string;
  device_id: string;
  last_login_at: string | null;
}

/**
 * Local enrolment records for officers who have signed in on this device.
 *
 * Holding these locally is what makes offline sign-in possible at a post with no
 * connectivity. No credential material is stored here — only the profile. The
 * verifier lives in secure storage.
 */
export interface UserRepository {
  upsert(user: AuthenticatedUser): Promise<void>;
  findByOfficerId(officerId: string): Promise<AuthenticatedUser | null>;
  recordLogin(officerId: string): Promise<void>;
  listEnrolled(): Promise<AuthenticatedUser[]>;
}

function toUser(row: UserRow): AuthenticatedUser {
  return {
    id: row.id,
    officerId: row.officer_id,
    name: row.name,
    rank: row.rank,
    role: row.role as OfficerRole,
    unit: row.unit,
    postName: row.post_name,
    deviceId: row.device_id,
  };
}

class SqliteUserRepository implements UserRepository {
  async upsert(user: AuthenticatedUser): Promise<void> {
    const db = await getDatabase();
    await db.runAsync(
      `INSERT INTO users (id, officer_id, name, rank, role, unit, post_name, device_id, last_login_at)
       VALUES (?,?,?,?,?,?,?,?,NULL)
       ON CONFLICT(officer_id) DO UPDATE SET
         name = excluded.name,
         rank = excluded.rank,
         role = excluded.role,
         unit = excluded.unit,
         post_name = excluded.post_name,
         device_id = excluded.device_id`,
      [
        user.id,
        user.officerId,
        user.name,
        user.rank,
        user.role,
        user.unit,
        user.postName,
        user.deviceId,
      ],
    );
  }

  async findByOfficerId(officerId: string): Promise<AuthenticatedUser | null> {
    const db = await getDatabase();
    const row = await db.getFirstAsync<UserRow>('SELECT * FROM users WHERE officer_id = ?', [
      officerId.toUpperCase(),
    ]);
    return row ? toUser(row) : null;
  }

  async recordLogin(officerId: string): Promise<void> {
    const db = await getDatabase();
    await db.runAsync('UPDATE users SET last_login_at = ? WHERE officer_id = ?', [
      nowIso(),
      officerId.toUpperCase(),
    ]);
  }

  async listEnrolled(): Promise<AuthenticatedUser[]> {
    const db = await getDatabase();
    const rows = await db.getAllAsync<UserRow>('SELECT * FROM users ORDER BY name ASC');
    return rows.map(toUser);
  }
}

export const userRepository: UserRepository = new SqliteUserRepository();
