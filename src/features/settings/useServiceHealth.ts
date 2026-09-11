import { useCallback, useEffect, useRef, useState } from 'react';

import { resolveScreeningServiceUrl } from '@/config/screeningService';
import { checkScreeningService, type ServiceHealth } from '@/services/ai/httpScreeningService';

/**
 * Whether the screening service is reachable from this device.
 *
 * The check runs when the screen opens and again whenever the address changes,
 * rather than only on a button press. An officer who mistypes an address, or
 * whose post's laptop moved to a different network, otherwise gets no signal at
 * all until a screening comes back with findings that did not come from the
 * document in front of them.
 */

export type ServiceHealthState =
  | { status: 'IDLE' }
  | { status: 'CHECKING' }
  | { status: 'DONE'; health: ServiceHealth };

export interface UseServiceHealth {
  state: ServiceHealthState;
  /** The address actually checked, after the override/build-default fallback. */
  resolvedUrl: string | null;
  check: () => void;
}

export function useServiceHealth(override: string | null): UseServiceHealth {
  const resolvedUrl = resolveScreeningServiceUrl(override);
  const [state, setState] = useState<ServiceHealthState>({ status: 'IDLE' });

  // Each run cancels the one before it, so a quick succession of edits cannot
  // land an older answer on top of a newer one.
  const inFlight = useRef<AbortController | null>(null);

  const run = useCallback(
    (url: string | null) => {
      inFlight.current?.abort();

      if (!url) {
        inFlight.current = null;
        setState({ status: 'DONE', health: { reachable: false, reason: 'No address is configured.' } });
        return;
      }

      const controller = new AbortController();
      inFlight.current = controller;
      setState({ status: 'CHECKING' });

      void checkScreeningService(url, { signal: controller.signal }).then((health) => {
        if (controller.signal.aborted) return;
        setState({ status: 'DONE', health });
      });
    },
    [],
  );

  useEffect(() => {
    run(resolvedUrl);
    return () => inFlight.current?.abort();
  }, [resolvedUrl, run]);

  const check = useCallback(() => run(resolvedUrl), [resolvedUrl, run]);

  return { state, resolvedUrl, check };
}
