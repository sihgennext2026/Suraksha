/**
 * Deterministic pseudo-random generator.
 *
 * Mock inference must be reproducible: the same case must always produce the
 * same scores, otherwise a demo cannot be rehearsed and a bug cannot be
 * reproduced. Every mock service derives its jitter from a seed built out of the
 * case identifier, so results are stable across runs and app restarts.
 */
export function createSeededRandom(seed: string): () => number {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < seed.length; i += 1) {
    h ^= seed.charCodeAt(i);
    h = Math.imul(h, 16777619) >>> 0;
  }
  // mulberry32
  let state = h >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Deterministic value in [min, max]. */
export function seededRange(random: () => number, min: number, max: number): number {
  return min + random() * (max - min);
}

/** Deterministic integer in [min, max] inclusive. */
export function seededInt(random: () => number, min: number, max: number): number {
  return Math.floor(seededRange(random, min, max + 1 - Number.EPSILON));
}

/** Deterministic choice from a non-empty list. */
export function seededPick<T>(random: () => number, items: readonly T[]): T {
  if (items.length === 0) throw new Error('seededPick requires a non-empty list');
  const index = Math.min(items.length - 1, Math.floor(random() * items.length));
  return items[index] as T;
}

/** Applies bounded deterministic jitter to a base value, clamped to 0..1. */
export function jitterUnit(random: () => number, base: number, spread: number): number {
  const value = base + (random() - 0.5) * 2 * spread;
  return Math.min(1, Math.max(0, Number(value.toFixed(4))));
}
