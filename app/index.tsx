import React from 'react';
import { Redirect } from 'expo-router';

import { ROUTES } from '@/constants/routes';
import { useAuthStore } from '@/stores/authStore';

/**
 * Entry point. Routes to sign-in or to the dashboard based on the session that
 * was restored during boot. Rendering nothing while the status is unknown keeps
 * the splash screen visible rather than flashing a screen the officer will be
 * redirected away from a frame later.
 */
export default function BootRoute() {
  const status = useAuthStore((state) => state.status);

  if (status === 'UNKNOWN') return null;
  if (status === 'SIGNED_OUT') return <Redirect href={ROUTES.auth.login} />;
  return <Redirect href={ROUTES.app.dashboard} />;
}
