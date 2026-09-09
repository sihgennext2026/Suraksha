import { addNetworkStateListener, getNetworkStateAsync, NetworkStateType } from 'expo-network';
import { create } from 'zustand';

import type { EventSubscription } from 'expo-modules-core';

interface ConnectivityState {
  /** Whether a network interface is up. */
  connected: boolean;
  /** Whether the internet is actually reachable through it. */
  reachable: boolean;
  connectionType: NetworkStateType;
  /** True once the first reading has landed. */
  initialised: boolean;

  start(): () => void;
  refresh(): Promise<void>;
}

/**
 * Network state.
 *
 * The application treats connectivity as an enhancement, never a dependency, so
 * this store exists purely to *report* state — nothing in the screening path
 * reads it to decide whether to proceed. Its only consumers are the sync worker
 * and the indicators that tell an officer whether their work has left the
 * device yet.
 */
export const useConnectivityStore = create<ConnectivityState>((set, get) => ({
  connected: false,
  reachable: false,
  connectionType: NetworkStateType.UNKNOWN,
  initialised: false,

  start() {
    void get().refresh();
    let subscription: EventSubscription | null = addNetworkStateListener((event) => {
      set({
        connected: event.isConnected ?? false,
        reachable: event.isInternetReachable ?? event.isConnected ?? false,
        connectionType: event.type ?? NetworkStateType.UNKNOWN,
        initialised: true,
      });
    });

    return () => {
      subscription?.remove();
      subscription = null;
    };
  },

  async refresh() {
    try {
      const state = await getNetworkStateAsync();
      set({
        connected: state.isConnected ?? false,
        reachable: state.isInternetReachable ?? state.isConnected ?? false,
        connectionType: state.type ?? NetworkStateType.UNKNOWN,
        initialised: true,
      });
    } catch {
      // A failed reading is treated as offline: the safe assumption, since it
      // keeps work queued locally rather than declaring it uploaded.
      set({ connected: false, reachable: false, initialised: true });
    }
  },
}));

export const selectIsOnline = (state: ConnectivityState) => state.connected && state.reachable;

export function connectionTypeLabel(type: NetworkStateType): string {
  switch (type) {
    case NetworkStateType.WIFI:
      return 'Wi-Fi';
    case NetworkStateType.CELLULAR:
      return 'Cellular';
    case NetworkStateType.ETHERNET:
      return 'Ethernet';
    case NetworkStateType.BLUETOOTH:
      return 'Bluetooth';
    case NetworkStateType.VPN:
      return 'VPN';
    case NetworkStateType.NONE:
      return 'No connection';
    default:
      return 'Unknown';
  }
}
