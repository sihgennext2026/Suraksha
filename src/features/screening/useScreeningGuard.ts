import { useEffect } from 'react';
import { useRouter } from 'expo-router';

import { ROUTES } from '@/constants/routes';
import { useScreeningStore } from '@/stores/screeningStore';
import type { ScreeningCase } from '@/types';

type Requirement = 'CASE' | 'DOCUMENT' | 'PERSON' | 'RESULTS';

/**
 * Guards a screening screen against being reached without its prerequisites.
 *
 * Deep links, back-gesture stacks, and a restart part-way through the workflow
 * can all land an officer on a screen whose inputs do not exist. Rather than
 * rendering a half-empty screen, each screen declares what it needs and is
 * returned to the dashboard if that is missing.
 *
 * Returns the active case when the requirement is met, and null while the
 * redirect is in flight — callers render nothing in that frame.
 */
export function useScreeningGuard(requirement: Requirement = 'CASE'): ScreeningCase | null {
  const router = useRouter();
  const activeCase = useScreeningStore((state) => state.activeCase);
  const restored = useScreeningStore((state) => state.restored);
  const phase = useScreeningStore((state) => state.phase);

  // A saved case still satisfies every requirement. Without this, the frame
  // between the save completing and the navigation away from the decision
  // screen would redirect the officer to the dashboard instead.
  const satisfied = phase === 'SAVED' || isSatisfied(activeCase, requirement);

  useEffect(() => {
    // Waiting for `restored` avoids bouncing the officer off a screen during
    // the frame before an interrupted case has been read back from storage.
    if (!restored || satisfied) return;
    router.replace(ROUTES.app.dashboard);
  }, [restored, satisfied, router]);

  return satisfied ? activeCase : null;
}

function isSatisfied(activeCase: ScreeningCase | null, requirement: Requirement): boolean {
  if (!activeCase) return false;
  switch (requirement) {
    case 'CASE':
      return true;
    case 'DOCUMENT':
      return Boolean(activeCase.document);
    case 'PERSON':
      return Boolean(activeCase.document && activeCase.person);
    case 'RESULTS':
      return Boolean(activeCase.result);
    default:
      return false;
  }
}
