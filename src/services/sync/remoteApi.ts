import type { ScreeningCase } from '@/types';
import { delay } from '@/utils/delay';
import { failure } from '@/utils/errors';
import { createSeededRandom } from '@/utils/random';

/**
 * The remote case service.
 *
 * This interface is what the sync worker depends on. The mock below emulates
 * network latency and a realistic failure rate; the production implementation
 * will make the same calls against the central service. Nothing else in the
 * application talks to the network.
 */
export interface RemoteCaseApi {
  /** Uploads a completed case. Resolves with the server's record identifier. */
  uploadCase(screeningCase: ScreeningCase): Promise<{ remoteId: string; acceptedAt: string }>;
}

/**
 * Deterministic failure injection.
 *
 * One upload in roughly six fails on its first attempt, chosen from the case
 * reference so a given case fails reproducibly. This is not padding: retry,
 * backoff, and the failed-sync UI are all paths that need to be exercised
 * during a demonstration, and a queue that always succeeds never shows them.
 */
function shouldFailAttempt(caseId: string, attempt: number): boolean {
  if (attempt > 1) return false;
  const random = createSeededRandom(`sync:${caseId}`);
  return random() < 0.17;
}

class MockRemoteCaseApi implements RemoteCaseApi {
  async uploadCase(
    screeningCase: ScreeningCase,
  ): Promise<{ remoteId: string; acceptedAt: string }> {
    const random = createSeededRandom(`latency:${screeningCase.id}`);
    await delay(600 + random() * 900);

    if (shouldFailAttempt(screeningCase.id, screeningCase.sync.attempts + 1)) {
      throw failure(
        'UPLOAD_REJECTED',
        'The central service did not accept this case. It stays on this device and will be retried automatically.',
        true,
      );
    }

    return {
      remoteId: `REM-${screeningCase.id}`,
      acceptedAt: new Date().toISOString(),
    };
  }
}

export const remoteCaseApi: RemoteCaseApi = new MockRemoteCaseApi();
