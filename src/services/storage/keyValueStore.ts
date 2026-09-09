import AsyncStorage from '@react-native-async-storage/async-storage';

/**
 * Small key/value persistence for non-sensitive preferences and recovery
 * snapshots.
 *
 * The interface is intentionally narrow so the backing store can be swapped for
 * a synchronous MMKV instance in a development build without touching callers.
 * Sensitive material never goes here — see `secureStore`.
 */
export interface KeyValueStore {
  getString(key: string): Promise<string | null>;
  setString(key: string, value: string): Promise<void>;
  getJson<T>(key: string): Promise<T | null>;
  setJson<T>(key: string, value: T): Promise<void>;
  remove(key: string): Promise<void>;
  /** Removes every key under the application namespace. */
  clearNamespace(prefix: string): Promise<void>;
}

class AsyncStorageKeyValueStore implements KeyValueStore {
  async getString(key: string): Promise<string | null> {
    return AsyncStorage.getItem(key);
  }

  async setString(key: string, value: string): Promise<void> {
    await AsyncStorage.setItem(key, value);
  }

  async getJson<T>(key: string): Promise<T | null> {
    const raw = await AsyncStorage.getItem(key);
    if (raw === null) return null;
    try {
      return JSON.parse(raw) as T;
    } catch {
      // A corrupt entry is discarded rather than crashing the caller; the
      // application always has a usable default for anything stored here.
      await AsyncStorage.removeItem(key);
      return null;
    }
  }

  async setJson<T>(key: string, value: T): Promise<void> {
    await AsyncStorage.setItem(key, JSON.stringify(value));
  }

  async remove(key: string): Promise<void> {
    await AsyncStorage.removeItem(key);
  }

  async clearNamespace(prefix: string): Promise<void> {
    const keys = await AsyncStorage.getAllKeys();
    const matching = keys.filter((key) => key.startsWith(prefix));
    if (matching.length > 0) await AsyncStorage.multiRemove(matching);
  }
}

export const keyValueStore: KeyValueStore = new AsyncStorageKeyValueStore();
