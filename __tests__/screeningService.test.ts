import type { ScreeningCaseResult } from '@/contracts';
import { ScreeningServiceError } from '@/types';
import type { CapturedImage } from '@/types/document';
import { normaliseServiceUrl, resolveScreeningServiceUrl } from '@/config/screeningService';
import { HttpScreeningService } from '@/services/ai/httpScreeningService';
import { getScreeningService, isUsingRealScreening } from '@/services/ai/registry';
import { MockScreeningService } from '@/services/mock/mockScreeningService';
import { SCREENING_STAGE_ORDER } from '@/types/case';

import genuinePassport from '@/fixtures/screening/genuine-passport.json';

/**
 * The boundary between the app and real inference.
 *
 * What matters here is not that the client can parse JSON — it is that the app
 * never invents a result. The service's document is stored as it arrived, a
 * service that cannot be reached raises rather than falling back to a fixture,
 * and a configured address takes the fixtures out of the screening path
 * entirely.
 */

const CAPTURE: CapturedImage = {
  uri: 'file:///captures/document.jpg',
  width: 1600,
  height: 1200,
  capturedAt: '2026-09-10T10:00:00.000Z',
  sizeBytes: 1024,
  source: 'CAMERA',
};

function buildRequest(overrides: Record<string, unknown> = {}) {
  return {
    caseId: 'SSB-2026-0001',
    documentType: 'passport' as const,
    documentImage: CAPTURE,
    personImage: { ...CAPTURE, uri: 'file:///captures/person.jpg' },
    ...overrides,
  };
}

const DOCUMENT = genuinePassport as unknown as ScreeningCaseResult;

describe('service address', () => {
  it('rejects an address that is not a usable origin', () => {
    expect(normaliseServiceUrl('10.0.0.5:8000')).toBeNull();
    expect(normaliseServiceUrl('   ')).toBeNull();
    expect(normaliseServiceUrl(null)).toBeNull();
    // A trailing slash is a typo, not a different service.
    expect(normaliseServiceUrl('http://10.0.0.5:8000/')).toBe('http://10.0.0.5:8000');
  });

  it('prefers the officer override over the build default', () => {
    expect(resolveScreeningServiceUrl('http://10.0.0.9:8000')).toBe('http://10.0.0.9:8000');
    // A malformed override must not silently disable screening.
    expect(resolveScreeningServiceUrl('nonsense')).toBe(resolveScreeningServiceUrl(null));
  });
});

describe('choosing an implementation', () => {
  it('uses the real service when an address is configured', () => {
    expect(getScreeningService({ serviceUrl: 'http://10.0.0.5:8000' })).toBeInstanceOf(
      HttpScreeningService,
    );
    expect(isUsingRealScreening('http://10.0.0.5:8000')).toBe(true);
  });

  it('takes the fixtures out of the real path entirely', () => {
    // A forced scenario is a fixture selector. Against a real service it must
    // not apply: replaying an invented outcome over a capture the officer just
    // took is indistinguishable, to them, from a genuine finding.
    const service = getScreeningService({
      serviceUrl: 'http://10.0.0.5:8000',
      scenario: 'tampered-text-and-invalid',
    });
    expect(service).toBeInstanceOf(HttpScreeningService);
    expect(service).not.toBeInstanceOf(MockScreeningService);
  });

  it('falls back to replaying a document when nothing is configured', () => {
    expect(getScreeningService({ serviceUrl: null })).toBeInstanceOf(MockScreeningService);
    expect(isUsingRealScreening(null)).toBe(false);
  });
});

describe('http screening service', () => {
  const fetchMock = jest.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    (global as unknown as { fetch: unknown }).fetch = fetchMock;
  });

  it('uploads both captures and the officer’s declared type', async () => {
    fetchMock.mockResolvedValue({ ok: true, json: async () => DOCUMENT });
    const service = new HttpScreeningService({ baseUrl: 'http://10.0.0.5:8000' });

    await service.screen(buildRequest());

    const [url, init] = fetchMock.mock.calls[0] as [string, { method: string; body: FormData }];
    expect(url).toBe('http://10.0.0.5:8000/screen');
    expect(init.method).toBe('POST');
    // The captures must actually be sent; a screening that analysed nothing
    // would still return a plausible-looking document.
    // React Native's FormData exposes `_parts`; the standard one this test
    // environment provides exposes an iterator. Read whichever is present so
    // the assertion is about what was sent, not about which polyfill ran.
    const body = init.body as unknown as {
      _parts?: [string, unknown][];
      keys?: () => Iterable<string>;
    };
    const keys = body._parts
      ? body._parts.map(([key]) => key)
      : Array.from(body.keys?.() ?? []);

    expect(keys).toEqual(
      expect.arrayContaining(['case_id', 'document_type', 'document', 'person']),
    );
  });

  it('returns the service’s document without altering it', async () => {
    fetchMock.mockResolvedValue({ ok: true, json: async () => DOCUMENT });
    const service = new HttpScreeningService({ baseUrl: 'http://10.0.0.5:8000' });

    const result = await service.screen(buildRequest());

    // Byte-for-byte: no threshold applied, no score rescaled, no absent module
    // filled in. Everything in the record is the service's.
    expect(result).toEqual(DOCUMENT);
  });

  it('reports every stage from the returned document', async () => {
    fetchMock.mockResolvedValue({ ok: true, json: async () => DOCUMENT });
    const service = new HttpScreeningService({ baseUrl: 'http://10.0.0.5:8000' });

    const terminal = new Map<string, string>();
    await service.screen(
      buildRequest({
        onStage: (event: { stage: string; status: string; progress: number }) => {
          if (event.progress === 1) terminal.set(event.stage, event.status);
        },
      }),
    );

    expect(terminal.size).toBe(SCREENING_STAGE_ORDER.length);
    // The module that does not exist must show as not-run, never as a pass.
    expect(terminal.get('ANOMALY_ANALYSIS')).toBe('NOT_AVAILABLE');
  });

  it('raises when the service cannot be reached rather than inventing a result', async () => {
    fetchMock.mockRejectedValue(new Error('Network request failed'));
    const service = new HttpScreeningService({ baseUrl: 'http://10.0.0.5:8000' });

    // Must be the application's own error type: `toServiceFailure` recognises
    // it by `instanceof`, and a look-alike class would leave the officer with a
    // generic "something went wrong" instead of the reason and the fix.
    await expect(service.screen(buildRequest())).rejects.toBeInstanceOf(ScreeningServiceError);
    await expect(service.screen(buildRequest())).rejects.toThrow(/could not be reached/i);
  });

  it('raises on a rejected request rather than treating it as a clear result', async () => {
    fetchMock.mockResolvedValue({ ok: false, status: 503, text: async () => 'starting' });
    const service = new HttpScreeningService({ baseUrl: 'http://10.0.0.5:8000' });

    await expect(service.screen(buildRequest())).rejects.toThrow(/503/);
  });
});
