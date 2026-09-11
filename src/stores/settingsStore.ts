import { create } from 'zustand';

import { STORAGE_KEYS } from '@/constants/storage';
import { keyValueStore } from '@/services/storage';
import type { ThemePreference } from '@/theme';

interface PersistedSettings {
  theme: ThemePreference;
  autoSync: boolean;
  hapticFeedback: boolean;
  /**
   * Forces a specific screening scenario. Every module state the officer can
   * meet - a tampered document, a failed module, an unsupported document type -
   * is reachable this way, so the recovery paths can be exercised on real
   * hardware rather than only in tests.
   */
  forcedScenario: string | null;
  /** Overrides connectivity so offline behaviour can be shown on demand. */
  forceOffline: boolean;
  /**
   * Address of the screening service that runs the models, overriding the one
   * the build ships with. Null uses the build's. When neither resolves, the app
   * has nothing to call and replays a generated document instead.
   */
  screeningServiceUrl: string | null;
}

interface SettingsState extends PersistedSettings {
  hydrated: boolean;
  hydrate(): Promise<void>;
  setTheme(theme: ThemePreference): void;
  setAutoSync(enabled: boolean): void;
  setHapticFeedback(enabled: boolean): void;
  setForcedScenario(scenario: string | null): void;
  setForceOffline(enabled: boolean): void;
  setScreeningServiceUrl(url: string | null): void;
}

const DEFAULTS: PersistedSettings = {
  theme: 'light',
  autoSync: true,
  hapticFeedback: true,
  forcedScenario: null,
  forceOffline: false,
  screeningServiceUrl: null,
};

/**
 * Device preferences.
 *
 * Writes are fire-and-forget to storage: a setting that fails to persist is not
 * worth interrupting the officer for, and the in-memory value is authoritative
 * for the session either way.
 */
export const useSettingsStore = create<SettingsState>((set, get) => {
  function persist(): void {
    const { theme, autoSync, hapticFeedback, forcedScenario, forceOffline, screeningServiceUrl } =
      get();
    void keyValueStore.setJson<PersistedSettings>(STORAGE_KEYS.settings, {
      theme,
      autoSync,
      hapticFeedback,
      forcedScenario,
      forceOffline,
      screeningServiceUrl,
    });
  }

  return {
    ...DEFAULTS,
    hydrated: false,

    async hydrate() {
      const stored = await keyValueStore.getJson<PersistedSettings>(STORAGE_KEYS.settings);
      set({ ...DEFAULTS, ...(stored ?? {}), hydrated: true });
    },

    setTheme(theme) {
      set({ theme });
      persist();
    },
    setAutoSync(autoSync) {
      set({ autoSync });
      persist();
    },
    setHapticFeedback(hapticFeedback) {
      set({ hapticFeedback });
      persist();
    },
    setForcedScenario(forcedScenario) {
      set({ forcedScenario });
      persist();
    },
    setForceOffline(forceOffline) {
      set({ forceOffline });
      persist();
    },
    setScreeningServiceUrl(screeningServiceUrl) {
      set({ screeningServiceUrl });
      persist();
    },
  };
});

/** Selectors. Components subscribe to one value so unrelated changes do not re-render them. */
export const selectTheme = (state: SettingsState) => state.theme;
export const selectAutoSync = (state: SettingsState) => state.autoSync;
export const selectForcedScenario = (state: SettingsState) => state.forcedScenario;
export const selectForceOffline = (state: SettingsState) => state.forceOffline;
export const selectScreeningServiceUrl = (state: SettingsState) => state.screeningServiceUrl;
