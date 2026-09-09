/** Stable sort helper — Array.prototype.sort is not guaranteed stable on Hermes. */
export function sortBy<T>(items: readonly T[], selector: (item: T) => number): T[] {
  return items
    .map((item, index) => ({ item, index, key: selector(item) }))
    .sort((a, b) => (a.key === b.key ? a.index - b.index : a.key - b.key))
    .map((entry) => entry.item);
}

export function groupBy<T, K extends string>(
  items: readonly T[],
  selector: (item: T) => K,
): Record<K, T[]> {
  const output = {} as Record<K, T[]>;
  for (const item of items) {
    const key = selector(item);
    (output[key] ??= []).push(item);
  }
  return output;
}

export function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}
