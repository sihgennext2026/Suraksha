import type { ScreeningCaseResult } from '@/contracts';
import { SCREENING_STAGE_ORDER } from '@/types/case';
import { ScreeningServiceError } from '@/types';
import { AbortError } from '@/utils/delay';
import { createLogger } from '@/utils/logger';

import { failure } from '@/utils/errors';

import type { ScreeningRequest, ScreeningService } from './contracts';
import { stageEventsFor } from './stageEvents';

const log = createLogger('screening-http');

/**
 * Talks to the real screening service.
 *
 * The captures are uploaded and the canonical case document comes back
 * assembled. Nothing is computed here: no threshold is applied, no score is
 * rescaled, no missing module is filled in. That is the same discipline the
 * mock follows, for the same reason — a second implementation of the policy in
 * the app is exactly what the contract layer exists to prevent.
 *
 * TODO(production): the post's service address belongs in device management
 * rather than in app settings, and the upload needs mutual TLS so a capture
 * cannot be intercepted on a post's local network.
 */

/** How long a single screening may take before the officer is told it failed. */
const REQUEST_TIMEOUT_MS = 120_000;

export interface HttpScreeningOptions {
  /** Base URL of the screening service, e.g. `http://10.50.0.177:8000`. */
  baseUrl: string;
  timeoutMs?: number;
}

export class HttpScreeningService implements ScreeningService {
  private readonly baseUrl: string;
  private readonly timeoutMs: number;

  constructor(options: HttpScreeningOptions) {
    this.baseUrl = options.baseUrl.replace(/\/+$/, '');
    this.timeoutMs = options.timeoutMs ?? REQUEST_TIMEOUT_MS;
  }

  async screen(request: ScreeningRequest): Promise<ScreeningCaseResult> {
    const body = new FormData();
    body.append('case_id', request.caseId);
    body.append('document_type', request.documentType);
    body.append('document', asUpload(request.documentImage.uri, 'document.jpg'));
    body.append('person', asUpload(request.personImage.uri, 'person.jpg'));
    if (request.documentBackImage) {
      body.append('document_back', asUpload(request.documentBackImage.uri, 'document_back.jpg'));
    }

    // The service runs the modules in one call, so there is no per-stage
    // progress to stream. The indicator is advanced to PROCESSING for every
    // stage up front and resolved from the returned document, which keeps the
    // officer's view honest: it never claims a stage finished before the
    // evidence for it exists.
    markAllProcessing(request.onStage);

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.timeoutMs);
    const abort = () => controller.abort();
    request.signal?.addEventListener('abort', abort);

    try {
      const response = await fetch(`${this.baseUrl}/screen`, {
        method: 'POST',
        body,
        signal: controller.signal,
      });

      if (!response.ok) {
        const detail = await response.text().catch(() => '');
        log.warn('Screening service rejected the request', {
          status: response.status,
          ok: false,
        });
        void detail;
        throw failure(
          'SERVICE_REJECTED',
          `The screening service rejected the request (${response.status}).`,
        );
      }

      const result = (await response.json()) as ScreeningCaseResult;
      emitStages(result, request.onStage);
      return result;
    } catch (error) {
      if (request.signal?.aborted) throw new AbortError();
      if (controller.signal.aborted) {
        throw failure('SERVICE_TIMEOUT', 'The screening service did not respond in time.');
      }
      if (error instanceof ScreeningServiceError) throw error;
      log.warn('Screening request failed', { ok: false });
      throw failure(
        'SERVICE_UNREACHABLE',
        'The screening service could not be reached. Check the address in Settings and that the phone is on the same network.',
      );
    } finally {
      clearTimeout(timeout);
      request.signal?.removeEventListener('abort', abort);
    }
  }
}

/**
 * React Native's FormData takes a `{uri, name, type}` object for a file and
 * streams it from disk, so a multi-megabyte capture never has to be base64'd
 * through the bridge.
 */
function asUpload(uri: string, name: string): never {
  return { uri, name, type: 'image/jpeg' } as never;
}

function markAllProcessing(onStage: ScreeningRequest['onStage']): void {
  if (!onStage) return;
  for (const stage of SCREENING_STAGE_ORDER) {
    onStage({ stage, status: 'PROCESSING', progress: 0, detail: null, error: null });
  }
}

function emitStages(result: ScreeningCaseResult, onStage: ScreeningRequest['onStage']): void {
  if (!onStage) return;
  for (const event of stageEventsFor(result)) onStage(event);
}

/** One module's availability, as the service reports it. */
export interface ServiceModuleHealth {
  module: string;
  available: boolean;
  reason: string | null;
}

export type ServiceHealth =
  | { reachable: true; modules: ServiceModuleHealth[] }
  | { reachable: false; reason: string };

/**
 * An interactive check, so it fails fast rather than leaving a spinner up.
 * A screening itself is allowed two minutes; deciding whether an address is
 * even correct should take seconds.
 */
const HEALTH_TIMEOUT_MS = 6_000;

/**
 * Asks the service which modules it can currently run.
 *
 * Worth doing from Settings rather than waiting for a screening to fail: an
 * unreachable service is indistinguishable, from the officer's side, from a
 * configured one — the app quietly falls back to replaying a generated
 * document, and the first sign of trouble would otherwise be findings that did
 * not come from the capture in front of them.
 */
export async function checkScreeningService(
  baseUrl: string | null,
  options: { signal?: AbortSignal } = {},
): Promise<ServiceHealth> {
  if (!baseUrl) {
    return { reachable: false, reason: 'No address is configured.' };
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), HEALTH_TIMEOUT_MS);
  const abort = () => controller.abort();
  options.signal?.addEventListener('abort', abort);

  try {
    const response = await fetch(`${baseUrl.replace(/\/+$/, '')}/health`, {
      method: 'GET',
      signal: controller.signal,
    });
    if (!response.ok) {
      return { reachable: false, reason: `The service answered with ${response.status}.` };
    }

    const body = (await response.json()) as {
      modules?: Record<string, { available?: boolean; reason?: string | null }>;
    };
    const modules = Object.entries(body.modules ?? {}).map(([module, entry]) => ({
      module,
      available: entry?.available === true,
      reason: entry?.reason ?? null,
    }));
    return { reachable: true, modules };
  } catch {
    if (options.signal?.aborted) {
      return { reachable: false, reason: 'The check was cancelled.' };
    }
    if (controller.signal.aborted) {
      return { reachable: false, reason: 'No answer within six seconds.' };
    }
    // Deliberately not the raw error: "Network request failed" tells an officer
    // nothing they can act on, and the two things worth checking are the same
    // every time.
    return {
      reachable: false,
      reason: 'Could not connect. Check the address and that this device is on the same network.',
    };
  } finally {
    clearTimeout(timeout);
    options.signal?.removeEventListener('abort', abort);
  }
}
