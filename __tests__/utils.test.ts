import { clamp, groupBy, sortBy } from '@/utils/array';
import { formatDate, formatRelative, isPast, yearsBetween } from '@/utils/date';
import { formatBytes, formatDurationMs, formatPercent, groupMrzLine } from '@/utils/format';
import { maskDocumentNumber, maskName } from '@/utils/mask';
import { createSeededRandom, jitterUnit, seededInt, seededPick } from '@/utils/random';
import { toServiceFailure, isAbortError, failure } from '@/utils/errors';
import { delay } from '@/utils/delay';

/**
 * Utility behaviour that other layers depend on being exactly right: personal
 * data never leaves these functions unmasked, mock inference stays reproducible,
 * and no thrown value reaches an officer as a stack trace or a code.
 */

describe('masking', () => {
  it('leaves only the last four characters of a document number', () => {
    expect(maskDocumentNumber('P4821736')).toBe('••••1736');
    expect(maskDocumentNumber('NID884120')).toBe('•••••4120');
  });

  it('masks a short number entirely rather than revealing most of it', () => {
    expect(maskDocumentNumber('ABC')).toBe('•••');
    expect(maskDocumentNumber('AB12')).toBe('••••');
  });

  it('returns null when there is nothing to mask', () => {
    expect(maskDocumentNumber(null)).toBeNull();
    expect(maskDocumentNumber(undefined)).toBeNull();
    expect(maskDocumentNumber('')).toBeNull();
  });

  it('keeps a name recognisable without making it identifying', () => {
    expect(maskName('Krishna Raj')).toBe('K•••••• R••');
    expect(maskName('A B')).toBe('A B');
  });
});

describe('formatting', () => {
  it('presents a unit score as a whole percentage', () => {
    expect(formatPercent(0.912)).toBe('91%');
    expect(formatPercent(1)).toBe('100%');
    expect(formatPercent(0)).toBe('0%');
  });

  it('clamps a score that falls outside the unit range', () => {
    expect(formatPercent(1.4)).toBe('100%');
    expect(formatPercent(-0.2)).toBe('0%');
  });

  it('formats durations at a resolution an officer can use', () => {
    expect(formatDurationMs(340)).toBe('340 ms');
    expect(formatDurationMs(999)).toBe('999 ms');
    expect(formatDurationMs(1500)).toBe('1.5 s');
    expect(formatDurationMs(12_300)).toBe('12.3 s');
  });

  it('formats storage sizes', () => {
    expect(formatBytes(512)).toBe('512 B');
    expect(formatBytes(2048)).toBe('2.0 KB');
    expect(formatBytes(5 * 1024 * 1024)).toBe('5.0 MB');
  });

  it('groups an MRZ line so it can be read back character by character', () => {
    expect(groupMrzLine('P<INDSHARMA<<ANIL', 5)).toEqual(['P<IND', 'SHARM', 'A<<AN', 'IL']);
  });
});

describe('dates', () => {
  it('formats a calendar date unambiguously', () => {
    expect(formatDate('2003-05-12')).toBe('12 May 2003');
  });

  it('renders an absent date as a dash rather than as an error', () => {
    expect(formatDate(null)).toBe('—');
    expect(formatDate(undefined)).toBe('—');
  });

  it('returns the raw value when a date cannot be parsed', () => {
    expect(formatDate('not-a-date')).toBe('not-a-date');
  });

  it('computes whole years, not rounded ones', () => {
    const reference = new Date('2026-05-11T00:00:00.000Z');
    // The day before the birthday, the subject is still 22.
    expect(yearsBetween('2003-05-12', reference)).toBe(22);
    expect(yearsBetween('2003-05-11', reference)).toBe(23);
  });

  it('recognises a past date', () => {
    const reference = new Date('2026-08-24T00:00:00.000Z');
    expect(isPast('2020-01-01', reference)).toBe(true);
    expect(isPast('2030-01-01', reference)).toBe(false);
  });

  it('describes recency coarsely', () => {
    const now = new Date('2026-08-24T12:00:00.000Z').getTime();
    expect(formatRelative('2026-08-24T11:59:50.000Z', now)).toBe('just now');
    expect(formatRelative('2026-08-24T11:30:00.000Z', now)).toBe('30 min ago');
    expect(formatRelative('2026-08-24T09:00:00.000Z', now)).toBe('3 hours ago');
    expect(formatRelative('2026-08-22T12:00:00.000Z', now)).toBe('2 days ago');
  });
});

describe('deterministic randomness', () => {
  it('produces the same sequence for the same seed', () => {
    const first = createSeededRandom('SSB-2026-0042');
    const second = createSeededRandom('SSB-2026-0042');
    const a = [first(), first(), first()];
    const b = [second(), second(), second()];
    expect(a).toEqual(b);
  });

  it('produces different sequences for different seeds', () => {
    const a = createSeededRandom('SSB-2026-0042');
    const b = createSeededRandom('SSB-2026-0043');
    expect(a()).not.toBe(b());
  });

  it('keeps derived values inside their stated bounds', () => {
    const random = createSeededRandom('bounds');
    for (let index = 0; index < 200; index += 1) {
      const value = seededInt(random, 3, 7);
      expect(value).toBeGreaterThanOrEqual(3);
      expect(value).toBeLessThanOrEqual(7);
    }
  });

  it('picks reproducibly from a list', () => {
    const options = ['a', 'b', 'c', 'd'];
    expect(seededPick(createSeededRandom('pick'), options)).toBe(
      seededPick(createSeededRandom('pick'), options),
    );
  });

  it('refuses to pick from an empty list rather than returning undefined', () => {
    expect(() => seededPick(createSeededRandom('x'), [])).toThrow();
  });

  it('keeps jitter inside the unit range', () => {
    const random = createSeededRandom('jitter');
    for (let index = 0; index < 200; index += 1) {
      const value = jitterUnit(random, 0.98, 0.1);
      expect(value).toBeGreaterThanOrEqual(0);
      expect(value).toBeLessThanOrEqual(1);
    }
  });
});

describe('error handling', () => {
  it('passes a service failure through with its officer-facing message', () => {
    const result = toServiceFailure(
      failure('OCR_FAILED', 'Text could not be extracted from this document.', true),
    );
    expect(result.code).toBe('OCR_FAILED');
    expect(result.message).toBe('Text could not be extracted from this document.');
    expect(result.retryable).toBe(true);
  });

  it('never lets an unexpected error reach an officer as a code or a stack', () => {
    const result = toServiceFailure(new Error('TypeError: undefined is not an object'));
    expect(result.message).toBe('Something went wrong. Please try again.');
    expect(result.message).not.toContain('TypeError');
  });

  it('handles a non-error throw', () => {
    const result = toServiceFailure('something odd');
    expect(result.code).toBe('UNKNOWN');
    expect(result.message).toBe('Something went wrong. Please try again.');
  });

  it('recognises a cancellation as distinct from a fault', async () => {
    const controller = new AbortController();
    const pending = delay(1000, controller.signal);
    controller.abort();

    await expect(pending).rejects.toThrow();
    await pending.catch((error: unknown) => {
      expect(isAbortError(error)).toBe(true);
      expect(toServiceFailure(error).code).toBe('ABORTED');
    });
  });

  it('rejects immediately when the signal is already aborted', async () => {
    const controller = new AbortController();
    controller.abort();
    await expect(delay(1000, controller.signal)).rejects.toThrow();
  });
});

describe('array helpers', () => {
  it('sorts stably, preserving the order of equal keys', () => {
    const items = [
      { id: 'a', weight: 1 },
      { id: 'b', weight: 1 },
      { id: 'c', weight: 0 },
      { id: 'd', weight: 1 },
    ];
    expect(sortBy(items, (item) => item.weight).map((item) => item.id)).toEqual([
      'c',
      'a',
      'b',
      'd',
    ]);
  });

  it('groups by a key', () => {
    const grouped = groupBy(
      [
        { source: 'FACE', id: 1 },
        { source: 'OCR', id: 2 },
        { source: 'FACE', id: 3 },
      ],
      (item) => item.source as 'FACE' | 'OCR',
    );
    expect(grouped.FACE).toHaveLength(2);
    expect(grouped.OCR).toHaveLength(1);
  });

  it('clamps to the given range', () => {
    expect(clamp(120, 0, 100)).toBe(100);
    expect(clamp(-4, 0, 100)).toBe(0);
    expect(clamp(42, 0, 100)).toBe(42);
  });
});
