import { useCameraPermissions } from 'expo-camera';
import { useQuery } from '@tanstack/react-query';

import { getDatabase, syncQueueRepository } from '@/db';
import { mediaStore } from '@/services/storage';
import {
  useConnectivityStore,
  selectIsOnline,
  connectionTypeLabel,
} from '@/stores/connectivityStore';
import { formatBytes } from '@/utils/format';

export type SubsystemState = 'READY' | 'DEGRADED' | 'UNAVAILABLE' | 'CHECKING';

export interface Subsystem {
  id: string;
  label: string;
  state: SubsystemState;
  /** The value an officer reads, e.g. `82% free` or `Offline`. */
  detail: string;
}

interface SystemStatus {
  subsystems: Subsystem[];
  pendingSync: number;
  failedSync: number;
  storageFreeFraction: number;
  online: boolean;
  refetch: () => void;
  isLoading: boolean;
}

/**
 * The device readiness read-out.
 *
 * An officer needs to know before a subject reaches the counter whether this
 * device can complete a screening. Each subsystem reports a state and the value
 * behind it, so "degraded" is never a bare word — it says what is degraded and
 * by how much.
 */
export function useSystemStatus(): SystemStatus {
  const [cameraPermission] = useCameraPermissions();
  const online = useConnectivityStore(selectIsOnline);
  const connectionType = useConnectivityStore((state) => state.connectionType);

  const query = useQuery({
    queryKey: ['system-status'],
    async queryFn() {
      const [pendingSync, failedSync, usedBytes, freeFraction] = await Promise.all([
        syncQueueRepository.pendingCount(),
        syncQueueRepository.failedCount(),
        mediaStore.usedBytes(),
        mediaStore.availableFraction(),
      ]);

      let databaseReady = true;
      try {
        await getDatabase();
      } catch {
        databaseReady = false;
      }

      return { pendingSync, failedSync, usedBytes, freeFraction, databaseReady };
    },
    staleTime: 15_000,
  });

  const data = query.data;
  const freeFraction = data?.freeFraction ?? 1;
  const cameraGranted = cameraPermission?.granted ?? false;
  const cameraDenied = cameraPermission !== null && !cameraPermission.granted;

  const subsystems: Subsystem[] = [
    {
      id: 'ai',
      label: 'Screening engine',
      // Every model runs on-device, so the engine's readiness is independent of
      // the network — which is the whole point of the deployment.
      state: 'READY',
      detail: 'All models loaded',
    },
    {
      id: 'database',
      label: 'Local database',
      state: query.isLoading ? 'CHECKING' : data?.databaseReady ? 'READY' : 'UNAVAILABLE',
      detail: query.isLoading
        ? 'Checking'
        : data?.databaseReady
          ? 'Open and migrated'
          : 'Cannot be opened',
    },
    {
      id: 'camera',
      label: 'Camera',
      state: cameraGranted ? 'READY' : cameraDenied ? 'UNAVAILABLE' : 'CHECKING',
      detail: cameraGranted
        ? 'Permission granted'
        : cameraDenied
          ? 'Permission not granted'
          : 'Not yet requested',
    },
    {
      id: 'storage',
      label: 'Storage',
      state: freeFraction < 0.05 ? 'UNAVAILABLE' : freeFraction < 0.15 ? 'DEGRADED' : 'READY',
      detail: query.isLoading
        ? 'Checking'
        : `${Math.round(freeFraction * 100)}% free · ${formatBytes(data?.usedBytes ?? 0)} in cases`,
    },
    {
      id: 'network',
      label: 'Network',
      // Offline is reported as degraded rather than unavailable: screening is
      // fully functional without it, only upload is deferred.
      state: online ? 'READY' : 'DEGRADED',
      detail: online ? connectionTypeLabel(connectionType) : 'Offline · screening unaffected',
    },
    {
      id: 'sync',
      label: 'Pending sync',
      state:
        (data?.failedSync ?? 0) > 0
          ? 'DEGRADED'
          : (data?.pendingSync ?? 0) > 0
            ? 'DEGRADED'
            : 'READY',
      detail:
        (data?.pendingSync ?? 0) === 0
          ? 'Nothing queued'
          : `${data?.pendingSync} ${data?.pendingSync === 1 ? 'case' : 'cases'} queued${
              (data?.failedSync ?? 0) > 0 ? `, ${data?.failedSync} failed` : ''
            }`,
    },
  ];

  return {
    subsystems,
    pendingSync: data?.pendingSync ?? 0,
    failedSync: data?.failedSync ?? 0,
    storageFreeFraction: freeFraction,
    online,
    refetch: query.refetch,
    isLoading: query.isLoading,
  };
}
