/**
 * Jest setup shared by every suite.
 *
 * Native modules are replaced with in-memory implementations rather than empty
 * stubs, so behaviour that depends on values surviving a write-then-read — the
 * device enrolment record, a stored session, a persisted preference — is
 * genuinely exercised instead of silently returning null.
 */

jest.mock('expo-crypto', () => {
  const { createHash, randomBytes } = require('node:crypto');
  let counter = 0;
  return {
    CryptoDigestAlgorithm: { SHA256: 'SHA-256', SHA512: 'SHA-512' },
    randomUUID: () => {
      counter += 1;
      return `00000000-0000-4000-8000-${String(counter).padStart(12, '0')}`;
    },
    getRandomBytes: (length: number) => new Uint8Array(randomBytes(length)),
    getRandomBytesAsync: async (length: number) => new Uint8Array(randomBytes(length)),
    digestStringAsync: async (_algorithm: string, data: string) =>
      createHash('sha256').update(data).digest('hex'),
  };
});

jest.mock('expo-secure-store', () => {
  const store = new Map<string, string>();
  return {
    WHEN_UNLOCKED_THIS_DEVICE_ONLY: 'WHEN_UNLOCKED_THIS_DEVICE_ONLY',
    isAvailableAsync: jest.fn(async () => true),
    getItemAsync: jest.fn(async (key: string) => store.get(key) ?? null),
    setItemAsync: jest.fn(async (key: string, value: string) => {
      store.set(key, value);
    }),
    deleteItemAsync: jest.fn(async (key: string) => {
      store.delete(key);
    }),
    __reset: () => store.clear(),
  };
});

jest.mock('@react-native-async-storage/async-storage', () => {
  const store = new Map<string, string>();
  return {
    __esModule: true,
    default: {
      getItem: jest.fn(async (key: string) => store.get(key) ?? null),
      setItem: jest.fn(async (key: string, value: string) => {
        store.set(key, value);
      }),
      removeItem: jest.fn(async (key: string) => {
        store.delete(key);
      }),
      getAllKeys: jest.fn(async () => [...store.keys()]),
      multiRemove: jest.fn(async (keys: string[]) => {
        keys.forEach((key) => store.delete(key));
      }),
      __reset: () => store.clear(),
    },
  };
});

/**
 * Reanimated ships a jest mock that replaces the worklet runtime with plain
 * JavaScript. Without it, importing any animated component pulls in the native
 * worklets module, which does not exist under Jest.
 */
jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
