import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

import { createLogger } from '@/utils/logger';

const log = createLogger('secure-store');

/**
 * Hardware-backed storage for the session, the device enrolment record, and the
 * credential verifier. Values are written with `WHEN_UNLOCKED_THIS_DEVICE_ONLY`
 * so they are unavailable while the device is locked and are never migrated to
 * a restored device.
 *
 * TODO(production): the enrolment record must additionally be wrapped with a key
 * held in the platform keystore and rotated by the device management service.
 */
const OPTIONS: SecureStore.SecureStoreOptions = {
  keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
};

export interface SecureStorage {
  get(key: string): Promise<string | null>;
  set(key: string, value: string): Promise<void>;
  getJson<T>(key: string): Promise<T | null>;
  setJson<T>(key: string, value: T): Promise<void>;
  remove(key: string): Promise<void>;
  isAvailable(): Promise<boolean>;
}

class ExpoSecureStorage implements SecureStorage {
  async isAvailable(): Promise<boolean> {
    if (Platform.OS === 'web') return false;
    try {
      return await SecureStore.isAvailableAsync();
    } catch {
      return false;
    }
  }

  async get(key: string): Promise<string | null> {
    try {
      return await SecureStore.getItemAsync(key, OPTIONS);
    } catch (error) {
      // A read failure must not strand the officer at a blank screen — it is
      // treated as "no stored value", which routes them to sign-in.
      log.warn('Secure read failed; treating as absent', { key, ok: false });
      void error;
      return null;
    }
  }

  async set(key: string, value: string): Promise<void> {
    await SecureStore.setItemAsync(key, value, OPTIONS);
  }

  async getJson<T>(key: string): Promise<T | null> {
    const raw = await this.get(key);
    if (raw === null) return null;
    try {
      return JSON.parse(raw) as T;
    } catch {
      await this.remove(key);
      return null;
    }
  }

  async setJson<T>(key: string, value: T): Promise<void> {
    await this.set(key, JSON.stringify(value));
  }

  async remove(key: string): Promise<void> {
    try {
      await SecureStore.deleteItemAsync(key, OPTIONS);
    } catch {
      // Deleting a key that was never written is not an error worth surfacing.
    }
  }
}

export const secureStore: SecureStorage = new ExpoSecureStorage();
