import { create } from 'zustand';

import { auditRepository } from '@/db';
import { authService, type Credentials } from '@/services/api/authService';
import {
  ROLE_PERMISSIONS,
  type AuthSession,
  type AuthenticatedUser,
  type Permission,
} from '@/types';
import { toServiceFailure } from '@/utils/errors';

type AuthStatus = 'UNKNOWN' | 'SIGNED_OUT' | 'SIGNED_IN';

interface AuthState {
  status: AuthStatus;
  session: AuthSession | null;
  deviceId: string | null;
  /** Officer-facing message from the last failed sign-in. */
  error: string | null;
  busy: boolean;

  bootstrap(): Promise<void>;
  signIn(credentials: Credentials): Promise<boolean>;
  signOut(): Promise<void>;
  clearError(): void;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  status: 'UNKNOWN',
  session: null,
  deviceId: null,
  error: null,
  busy: false,

  /**
   * Runs once at launch: provisions the device if needed, then restores a valid
   * session. An expired session resolves to SIGNED_OUT rather than an error,
   * because from the officer's point of view it is simply time to sign in again.
   */
  async bootstrap() {
    try {
      const deviceId = await authService.ensureDeviceEnrolled();
      const session = await authService.restoreSession();
      set({
        deviceId,
        session,
        status: session ? 'SIGNED_IN' : 'SIGNED_OUT',
      });
    } catch {
      set({ status: 'SIGNED_OUT', session: null });
    }
  },

  async signIn(credentials) {
    set({ busy: true, error: null });
    try {
      const session = await authService.signIn(credentials);
      set({ session, status: 'SIGNED_IN', busy: false, error: null });
      await auditRepository.record({
        caseId: null,
        type: 'LOGIN',
        description: `${session.user.rank} ${session.user.name} signed in`,
        actorId: session.user.officerId,
        actorName: session.user.name,
        metadata: {
          offlineVerified: session.offlineVerified,
          role: session.user.role,
        },
      });
      return true;
    } catch (error) {
      set({ busy: false, error: toServiceFailure(error).message });
      return false;
    }
  },

  async signOut() {
    const session = get().session;
    if (session) {
      await auditRepository.record({
        caseId: null,
        type: 'LOGOUT',
        description: `${session.user.rank} ${session.user.name} signed out`,
        actorId: session.user.officerId,
        actorName: session.user.name,
        metadata: {},
      });
    }
    await authService.signOut();
    set({ session: null, status: 'SIGNED_OUT', error: null });
  },

  clearError() {
    set({ error: null });
  },
}));

export const selectUser = (state: AuthState): AuthenticatedUser | null =>
  state.session?.user ?? null;

export const selectAuthStatus = (state: AuthState) => state.status;

/**
 * Permission check.
 *
 * Enforcement will ultimately be server-side, but checking here from the outset
 * keeps the interface honest: a supervisor-only action is never rendered as
 * available to an officer and then rejected after they commit to it.
 */
export function hasPermission(user: AuthenticatedUser | null, permission: Permission): boolean {
  if (!user) return false;
  return ROLE_PERMISSIONS[user.role].includes(permission);
}

export function usePermission(permission: Permission): boolean {
  const user = useAuthStore(selectUser);
  return hasPermission(user, permission);
}
