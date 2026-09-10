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

/** Which modules the service can currently run. Used by the Settings read-out. */
export async function probeScreeningService(baseUrl: string): Promise<boolean> {
  try {
    const response = await fetch(`${baseUrl.replace(/\/+$/, '')}/health`, { method: 'GET' });
    return response.ok;
  } catch {
    return false;
  }
}
